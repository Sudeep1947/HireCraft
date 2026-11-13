"""Application lifecycle service.

The single, deterministic, validated and audited path for all application
status transitions in the platform. Recruiter/candidate endpoints, the
simulation shortlist flow and the demo pipeline all route through here so the
transition rules, actor authorization and history are enforced exactly once.

Design notes:
- Statuses are the canonical ``ApplicationStatus`` values, and no new states
  are introduced here. Phase 11 added ``INTERVIEWED`` to the enum for a
  completed application-linked interview; the transition rules for it live in
  ``STAFF_TRANSITIONS`` below, alongside the rest of the funnel.
- A transition is valid only if ``(current, target)`` exists in the actor's
  transition map. There are NO AI-driven status decisions; this module is
  purely deterministic rules. In particular no interview score, evaluation or
  scorecard can reach this service on its own: only a recruiter action does.
- Authorization mirrors ``services/screening/access.py``: the job owner is
  always allowed; otherwise an active organization membership in a staff
  role is required. The frontend is never trusted for org scoping.
- The status flip uses a compare-and-swap update so concurrent changes raise
  a 409 instead of being silently overwritten.
- History + audit are written inside the same session/transaction that the
  caller (route) commits, so a rollback undoes everything atomically.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domain.enums import ApplicationStatus, AuditEventType
from app.domain.models import Job, JobApplication, User
from app.repositories.jobs.job import (
    ApplicationStatusHistoryRepository,
    JobApplicationRepository,
)
from app.repositories.membership import OrganizationMembershipRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")

# Roles allowed to drive staff-side transitions on an organization's jobs.
# Mirrors the org staff roles used by the screening access layer.
ORG_STAFF_ROLES = {
    "recruiter",
    "hr",
    "hr_manager",
    "organization_admin",
    "admin",
}

# Statuses that represent a reached decision; they capture the deciding actor.
# Phase 8 adds SHORTLISTED: a shortlist is an explicit human decision, so it
# records who decided and when just like a rejection does.
# Phase 13 adds SELECTED: recording *who selected* the candidate and when is the
# whole point of the decision, so it is treated identically.
DECISION_STATUSES = {
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.SELECTED,
    ApplicationStatus.OFFERED,
    ApplicationStatus.HIRED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}

TERMINAL_STATUSES = {
    ApplicationStatus.HIRED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}

# Transitions available to staff (job owner or org staff member).
# A recruiting funnel: applied -> review/shortlist -> interview -> offer -> hire,
# with rejection allowed at every active stage. Staff can never set WITHDRAWN.
STAFF_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: {
        ApplicationStatus.UNDER_REVIEW,
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.UNDER_REVIEW: {
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.SHORTLISTED: {
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.SELECTED,
        ApplicationStatus.OFFERED,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.INTERVIEW_SCHEDULED: {
        ApplicationStatus.INTERVIEWED,
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.SELECTED,
        ApplicationStatus.OFFERED,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    },
    # Phase 11: an application-linked interview completed. This is a factual
    # stage, not a verdict -- the recruiter may still shortlist, offer or
    # reject, and an interview score never reaches here on its own.
    ApplicationStatus.INTERVIEWED: {
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.SELECTED,
        ApplicationStatus.OFFERED,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    },
    # Phase 13: the recruiter chose this candidate. Non-terminal on purpose --
    # SELECTED means "chosen", not "hired", so the offer can still be extended
    # (OFFERED) or the process can still fall through (REJECTED, typically
    # position_filled). Reaching it always requires an explicit human decision.
    ApplicationStatus.SELECTED: {
        ApplicationStatus.OFFERED,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.OFFERED: {
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.HIRED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}

# A candidate may only withdraw their own application, and only before it is
# finalized (hired/rejected) or already withdrawn.
CANDIDATE_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.UNDER_REVIEW: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.SHORTLISTED: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.INTERVIEW_SCHEDULED: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.INTERVIEWED: {ApplicationStatus.WITHDRAWN},
    # Phase 13: mirrors OFFERED -- having been selected is not yet being hired,
    # so the candidate may still withdraw before an offer is accepted.
    ApplicationStatus.SELECTED: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.OFFERED: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.HIRED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}


class ApplicationLifecycleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.application_repo = JobApplicationRepository(session)
        self.history_repo = ApplicationStatusHistoryRepository(session)
        self.membership_repo = OrganizationMembershipRepository(session)
        self.audit_service = AuditService(session)

    # ── Creation record ─────────────────────────────────────────────
    async def record_creation(
        self, application: JobApplication, actor: User,
        reason: str | None = None, comment: str | None = None,
    ) -> JobApplication:
        """Write the ``applied`` history record + audit entry for a new
        application. Called by application-creation paths."""
        organization_id = await self._job_organization_id(application.job_id)
        await self.history_repo.create(
            application_id=application.id,
            organization_id=organization_id,
            from_status=None,
            to_status=ApplicationStatus.APPLIED.value,
            changed_by=actor.id,
            reason=reason,
            comment=comment,
        )
        await self.audit_service.log(
            event_type=AuditEventType.APPLICATION_CREATED,
            action="application_created",
            user_id=actor.id,
            organization_id=organization_id,
            resource_type="job_application",
            resource_id=str(application.id),
            details={"job_id": str(application.job_id), "status": application.status},
        )
        AUDIT_LOGGER.info(
            "APPLICATION_CREATED | actor=%s application=%s job=%s",
            actor.id, application.id, application.job_id,
        )
        return application

    # ── Core transition ─────────────────────────────────────────────
    async def transition_application(
        self,
        application_id: uuid.UUID,
        target_status: str,
        actor: User,
        *,
        reason: str | None = None,
        comment: str | None = None,
        metadata: dict | None = None,
        reason_code: str | None = None,
    ) -> JobApplication:
        """Validate and perform a single status transition.

        ``reason_code`` carries the validated, controlled decision vocabulary
        (Phase 8 ``RejectionReason``) when the transition is a rejection. It is
        stored separately from the free-text ``reason`` so the candidate-facing
        projection can be built from a controlled value and never from
        recruiter prose.

        Raises:
            ValidationError (422): unknown target status.
            NotFoundError (404): unknown application or job.
            ForbiddenError (403): actor has no access or may not use this status.
            ConflictError (409): illegal transition or concurrent modification.
        """
        target = ApplicationStatus.from_value(target_status)
        if target is None:
            raise ValidationError(
                f"Invalid application status: {target_status!r}",
                extra={"allowed": [s.value for s in ApplicationStatus]},
            )

        app = await self.application_repo.get(application_id)
        if not app:
            raise NotFoundError("Application not found")
        job = await self.session.get(Job, app.job_id)
        if not job:
            raise NotFoundError("Job not found")

        transitions, actor_label = await self._transitions_for(app, job, actor)

        current = ApplicationStatus.from_value(app.status)
        if current is None:
            raise ConflictError(
                f"Application is in an unrecognized status: {app.status!r}",
                extra={"application_id": str(application_id)},
            )

        if current == target:
            # Requested transition is a no-op; report success without churn.
            return app

        if target not in transitions.get(current, set()):
            allowed_anywhere = {t for allowed in transitions.values() for t in allowed}
            if target not in allowed_anywhere:
                raise ForbiddenError(
                    f"{actor_label} may not set an application to {target.value}",
                    extra={"application_id": str(application_id), "to": target.value},
                )
            raise ConflictError(
                f"Invalid application status transition: "
                f"{current.value} -> {target.value}",
                extra={"application_id": str(application_id),
                       "from": current.value, "to": target.value},
            )

        # Decision fields capture who decided and why for decisive statuses.
        from_status = app.status
        extras: dict = {}
        if target in DECISION_STATUSES:
            now = datetime.now(timezone.utc)
            extras = {"decided_by": actor.id, "decided_at": now}
            if reason:
                extras["decision_reason"] = reason
            if comment:
                extras["decision_comment"] = comment
            if reason_code:
                extras["decision_reason_code"] = reason_code

        updated = await self.application_repo.update_status_if_current(
            application_id, from_status, target.value, **extras,
        )
        if not updated:
            raise ConflictError(
                "Application status changed concurrently; review current state and retry",
                extra={"application_id": str(application_id), "to": target.value},
            )

        history_metadata = dict(metadata or {})
        if reason_code:
            history_metadata.setdefault("reason_code", reason_code)

        await self.history_repo.create(
            application_id=application_id,
            organization_id=job.organization_id,
            from_status=from_status,
            to_status=target.value,
            changed_by=actor.id,
            reason=reason,
            comment=comment,
            metadata_json=history_metadata or None,
        )
        await self.audit_service.log(
            event_type=AuditEventType.APPLICATION_STATUS_CHANGED,
            action="application_status_changed",
            user_id=actor.id,
            organization_id=job.organization_id,
            resource_type="job_application",
            resource_id=str(application_id),
            details={
                "job_id": str(job.id),
                "from": from_status,
                "to": target.value,
                "reason": reason,
                "reason_code": reason_code,
            },
        )
        AUDIT_LOGGER.info(
            "APPLICATION_STATUS | actor=%s application=%s from=%s to=%s reason=%s",
            actor.id, application_id, from_status, target.value, reason,
        )
        return updated

    # ── Non-transitioning decision record (Phase 8) ─────────────────
    async def record_review_decision(
        self,
        application_id: uuid.UUID,
        actor: User,
        *,
        decision: str,
        comment: str | None = None,
        metadata: dict | None = None,
    ) -> JobApplication:
        """Record a deliberate staff decision that does not change the status.

        Used for "keep under review": the application is already
        ``UNDER_REVIEW``, so there is no transition to perform, but the recruiter
        still made an explicit choice that belongs in the immutable history and
        the audit trail. Authorization uses the same staff/candidate resolution
        as a transition, so this cannot become a back door around RBAC.
        """
        app = await self.application_repo.get(application_id)
        if not app:
            raise NotFoundError("Application not found")
        job = await self.session.get(Job, app.job_id)
        if not job:
            raise NotFoundError("Job not found")

        transitions, actor_label = await self._transitions_for(app, job, actor)
        if transitions is CANDIDATE_TRANSITIONS:
            raise ForbiddenError(
                f"{actor_label} may not record a review decision",
                extra={"application_id": str(application_id)},
            )

        current = ApplicationStatus.from_value(app.status)
        if current is None:
            raise ConflictError(
                f"Application is in an unrecognized status: {app.status!r}",
                extra={"application_id": str(application_id)},
            )

        history_metadata = dict(metadata or {})
        history_metadata["decision"] = decision
        history_metadata["status_changed"] = False

        await self.history_repo.create(
            application_id=application_id,
            organization_id=job.organization_id,
            from_status=current.value,
            to_status=current.value,
            changed_by=actor.id,
            reason=None,
            comment=comment,
            metadata_json=history_metadata,
        )
        await self.audit_service.log(
            event_type=AuditEventType.APPLICATION_STATUS_CHANGED,
            action="application_status_changed",
            user_id=actor.id,
            organization_id=job.organization_id,
            resource_type="job_application",
            resource_id=str(application_id),
            details={
                "job_id": str(job.id),
                "from": current.value,
                "to": current.value,
                "decision": decision,
                "status_changed": False,
            },
        )
        AUDIT_LOGGER.info(
            "APPLICATION_DECISION_NO_TRANSITION | actor=%s application=%s decision=%s",
            actor.id, application_id, decision,
        )
        return app

    # ── Queries ─────────────────────────────────────────────────────
    async def authorize_staff_access(
        self, application_id: uuid.UUID, actor: User,
    ) -> tuple[JobApplication, Job]:
        """Resolve an application and require staff access to it.

        This is the read-side counterpart of a transition, using the identical
        authorization rules: job owner, or an active organization membership in
        a staff role. Callers that only need to view decision data (options,
        history) use this so they cannot drift from the write path. Raises
        NotFoundError (404) for unknown records and ForbiddenError (403) when
        the actor has no access, including a candidate acting on their own
        application.
        """
        app = await self.application_repo.get(application_id)
        if not app:
            raise NotFoundError("Application not found")
        job = await self.session.get(Job, app.job_id)
        if not job:
            raise NotFoundError("Job not found")
        await self._transitions_for(app, job, actor)
        return app, job

    async def list_history(
        self, application_id: uuid.UUID, limit: int = 100,
    ) -> list:
        """Return the immutable history trail for an application."""
        return await self.history_repo.list_by_application(application_id, limit=limit)

    # ── Helpers ─────────────────────────────────────────────────────
    async def _job_organization_id(self, job_id: uuid.UUID) -> uuid.UUID | None:
        job = await self.session.get(Job, job_id)
        return job.organization_id if job else None

    async def _transitions_for(
        self, app: JobApplication, job: Job, actor: User,
    ) -> tuple[dict[ApplicationStatus, set[ApplicationStatus]], str]:
        """Resolve which transition map applies to this actor, enforcing
        access control. Never trusts client-supplied org ids.
        Returns (transitions, actor_label) for error reporting."""
        # Candidate acting on their own application: only withdrawal counts.
        if app.candidate_id == actor.id:
            return CANDIDATE_TRANSITIONS, "Candidate"

        if job.recruiter_id == actor.id:
            return STAFF_TRANSITIONS, "Staff"

        if job.organization_id:
            membership = await self.membership_repo.get_active_membership(
                actor.id, job.organization_id,
            )
            if membership and membership.role in ORG_STAFF_ROLES:
                return STAFF_TRANSITIONS, "Staff"

        raise ForbiddenError(
            "You do not have permission to update this application",
            extra={"application_id": str(app.id)},
        )