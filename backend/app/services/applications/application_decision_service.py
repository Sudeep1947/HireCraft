"""Phase 8 recruiter decision service.

Every human decision on an application flows through here. The service does not
own the lifecycle rules: it validates the *decision* (type, structured reason,
required fields) and then delegates the status change to
:class:`ApplicationLifecycleService`, which remains the single authority for
what transitions are legal and for who may make them.

Design notes:
- A decision is never derived from a screening score, an AI recommendation or a
  fairness metric. The caller must supply the decision explicitly; there is no
  code path here that reads a score to pick an outcome.
- ``JobApplication.decision_reason_code`` stores the controlled
  ``RejectionReason`` value. The candidate-facing message is projected from
  that code in :mod:`app.domain.application_decision_schemas`, so the private
  recruiter note can never become candidate-facing text.
- Status, decision history and audit are written in the caller's transaction,
  which the route commits; a failure anywhere rolls all of it back.
- Notifications are *not* sent here. The route hands them to the post-commit
  dispatcher so a notification failure cannot corrupt a committed decision.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.application_decision_schemas import (
    ApplicationDecisionCreate,
    ApplicationDecisionHistory,
    ApplicationDecisionHistoryItem,
    ApplicationDecisionOptions,
    ApplicationDecisionOption,
    ApplicationDecisionResult,
    CandidateApplicationDecisionResponse,
    CANDIDATE_STATUS_LABELS,
    RejectionReasonOption,
    REJECTION_REASON_CANDIDATE_MESSAGES,
    REJECTION_REASON_RECRUITER_LABELS,
    candidate_status_message,
)
from app.domain.enums import (
    ApplicationDecisionType,
    ApplicationStatus,
    AuditEventType,
    RejectionReason,
)
from app.domain.models import Job, JobApplication, User
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
    STAFF_TRANSITIONS,
    TERMINAL_STATUSES,
)

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")

# Used only when a stored status string is unrecognized, so response
# construction cannot fail on legacy data.
_FALLBACK_STATUS = ApplicationStatus.APPLIED

# Recruiter-facing copy for each decision. The description states the effect on
# the application so the recruiter confirms a status change, not a score.
DECISION_LABELS: dict[ApplicationDecisionType, str] = {
    ApplicationDecisionType.KEEP_UNDER_REVIEW: "Keep Under Review",
    ApplicationDecisionType.SHORTLIST: "Shortlist",
    ApplicationDecisionType.REJECT: "Reject",
    ApplicationDecisionType.SELECT: "Select",
    ApplicationDecisionType.HIRE: "Hire Candidate",
}

DECISION_DESCRIPTIONS: dict[ApplicationDecisionType, str] = {
    ApplicationDecisionType.KEEP_UNDER_REVIEW: (
        "Record that you are continuing to review this application. The "
        "application stays Under Review and no decision is made."
    ),
    ApplicationDecisionType.SHORTLIST: (
        "Move this application to Shortlisted. This is a real decision, not a "
        "suggestion from the screening score."
    ),
    ApplicationDecisionType.REJECT: (
        "Reject this application. A reason is required and the candidate will "
        "see the approved wording for that reason."
    ),
    # Phase 13: the wording is explicit that this is a choice made by a person
    # and that it is not yet a hire, because the two are separate outcomes.
    ApplicationDecisionType.SELECT: (
        "Select this candidate as your choice for this role. This is your own "
        "decision, not a suggestion from a score, an assessment result or an "
        "interview. Selecting is not the same as being hired: the offer still "
        "has to be extended and accepted."
    ),
    ApplicationDecisionType.HIRE: (
        "Officially hire this candidate for this role. This is the final positive "
        "decision that marks the application as Hired."
    ),
}


class ApplicationDecisionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lifecycle = ApplicationLifecycleService(session)

    # ── Record a decision ───────────────────────────────────────────
    async def record_decision(
        self,
        application_id: uuid.UUID,
        payload: ApplicationDecisionCreate,
        actor: User,
    ) -> ApplicationDecisionResult:
        """Validate and record one explicit recruiter decision.

        Raises:
            ValidationError (422): unknown decision, or a reason supplied when
                it is not allowed / missing when it is required.
            NotFoundError (404): unknown application or job.
            ForbiddenError (403): actor may not decide on this application.
            ConflictError (409): the decision is not legal from the current
                status, or the application changed concurrently.
        """
        decision = ApplicationDecisionType.from_value(payload.decision.value)
        if decision is None:  # defensive: Pydantic already constrains this
            raise ValidationError(f"Invalid decision: {payload.decision!r}")

        # Authorization + existence are resolved by the lifecycle service, the
        # same call a plain transition would make.
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)

        reason_code = (
            payload.rejection_reason.value if payload.rejection_reason else None
        )
        if decision.requires_rejection_reason and reason_code is None:
            raise ValidationError(
                "A rejection reason is required when rejecting an application",
                extra={"allowed": [r.value for r in RejectionReason]},
            )
        if not decision.requires_rejection_reason and reason_code is not None:
            raise ValidationError(
                "A rejection reason may only be supplied when rejecting",
            )

        previous_status = ApplicationStatus.from_value(app.status)
        if previous_status is None:
            raise ConflictError(
                f"Application is in an unrecognized status: {app.status!r}",
                extra={"application_id": str(application_id)},
            )
        if previous_status in TERMINAL_STATUSES:
            raise ConflictError(
                f"Application is already {previous_status.value}; a decision can "
                f"no longer be recorded",
                extra={"application_id": str(application_id),
                       "status": previous_status.value},
            )

        # Guard against a decision that repeats the state it is already in. The
        # lifecycle service no-ops on an unchanged status, so a duplicate
        # submission would otherwise look successful while writing nothing.
        if decision is ApplicationDecisionType.KEEP_UNDER_REVIEW:
            if previous_status in TERMINAL_STATUSES:
                raise ConflictError(
                    "Keep on hold / under review is not available for closed applications",
                    extra={"application_id": str(application_id),
                           "status": previous_status.value},
                )
        elif decision.target_status == previous_status:
            raise ConflictError(
                f"Application is already {previous_status.value}",
                extra={"application_id": str(application_id),
                       "status": previous_status.value},
            )

        metadata: dict = {"decision": decision.value}
        if reason_code:
            metadata["reason_code"] = reason_code

        if decision is ApplicationDecisionType.KEEP_UNDER_REVIEW:
            # Explicit "still reviewing" choice: recorded, but no status change.
            updated = await self.lifecycle.record_review_decision(
                application_id, actor,
                decision=decision.value,
                comment=payload.internal_note,
                metadata=metadata,
            )
            changed_status = False
            decided_at = datetime.now(timezone.utc)
        else:
            updated = await self.lifecycle.transition_application(
                application_id,
                decision.target_status.value,
                actor,
                # The controlled reason label goes in the legacy free-text
                # ``decision_reason`` field so existing staff surfaces show
                # something meaningful; the private note goes only to
                # ``decision_comment``/history. The candidate projection uses
                # ``reason_code`` alone.
                reason=(
                    REJECTION_REASON_RECRUITER_LABELS[payload.rejection_reason]
                    if payload.rejection_reason else None
                ),
                comment=payload.internal_note,
                metadata=metadata,
                reason_code=reason_code,
            )
            changed_status = updated.status != previous_status.value
            decided_at = updated.decided_at or datetime.now(timezone.utc)

        status = ApplicationStatus.from_value(updated.status) or previous_status
        await self._audit_decision(
            app=app, job=job, actor=actor, decision=decision,
            reason_code=reason_code, status=status,
            changed_status=changed_status,
        )

        # One projection, two consumers: the recruiter response and the
        # candidate notification carry byte-identical approved wording.
        candidate_message = candidate_status_message(
            status, job.title, payload.rejection_reason,
        )

        return ApplicationDecisionResult(
            application_id=application_id,
            decision=decision,
            previous_status=previous_status,
            status=status,
            changed_status=changed_status,
            rejection_reason=payload.rejection_reason,
            rejection_reason_label=(
                REJECTION_REASON_RECRUITER_LABELS.get(payload.rejection_reason)
                if payload.rejection_reason else None
            ),
            internal_note=payload.internal_note,
            candidate_status_label=CANDIDATE_STATUS_LABELS.get(
                status, status.value.replace("_", " ").title(),
            ),
            candidate_message=candidate_message,
            decided_at=decided_at,
            decided_by=actor.id,
        )

    # ── Available decisions (drives the UI, no client-side rules) ───
    async def get_decision_options(
        self, application_id: uuid.UUID, actor: User,
    ) -> ApplicationDecisionOptions:
        """Return the decisions the actor may legally record right now.

        The frontend renders these, so the transition table lives only on the
        server and the two cannot drift.
        """
        app, _job = await self.lifecycle.authorize_staff_access(application_id, actor)
        current = ApplicationStatus.from_value(app.status)
        if current is None:
            raise ConflictError(f"Unrecognized status: {app.status!r}")

        allowed = STAFF_TRANSITIONS.get(current, set())
        status_is_final = current in TERMINAL_STATUSES
        job_title = _job.title or "this role"

        options: list[ApplicationDecisionOption] = []
        for decision in ApplicationDecisionType:
            if decision is ApplicationDecisionType.HIRE:
                continue
            target = decision.target_status
            if decision is ApplicationDecisionType.KEEP_UNDER_REVIEW:
                # Only meaningful while the application is actually in review.
                available = current == ApplicationStatus.UNDER_REVIEW
                reason = (
                    None if available
                    else "Only available while the application is Under Review"
                )
            elif status_is_final:
                available = False
                reason = f"Application is already {current.value}"
            else:
                available = target in allowed
                reason = (
                    None if available
                    else f"Not allowed from {current.value.replace('_', ' ')}"
                )
            options.append(
                ApplicationDecisionOption(
                    decision=decision,
                    label=DECISION_LABELS[decision],
                    description=DECISION_DESCRIPTIONS[decision],
                    target_status=target,
                    requires_rejection_reason=decision.requires_rejection_reason,
                    available=available,
                    unavailable_reason=reason,
                    # The wording the candidate would actually be sent, read from
                    # the single reviewed projection rather than recomposed by
                    # the client. It is withheld for a decision that sends no
                    # notification (keep under review) and for a rejection,
                    # whose text depends on the reason the recruiter has not
                    # chosen yet -- those are previewed in ``rejection_reasons``
                    # once a reason is selected.
                    candidate_message=(
                        None
                        if (
                            decision is ApplicationDecisionType.KEEP_UNDER_REVIEW
                            or decision.requires_rejection_reason
                        )
                        else candidate_status_message(target, job_title, None)
                    ),
                )
            )

        return ApplicationDecisionOptions(
            application_id=application_id,
            current_status=current,
            status_is_final=status_is_final,
            options=options,
            rejection_reasons=[
                RejectionReasonOption(
                    value=reason,
                    label=REJECTION_REASON_RECRUITER_LABELS[reason],
                    candidate_message=template.format(job_title=job_title),
                )
                for reason, template in REJECTION_REASON_CANDIDATE_MESSAGES.items()
            ],
        )

    # ── Decision history (staff) ────────────────────────────────────
    async def get_decision_history(
        self, application_id: uuid.UUID, actor: User,
    ) -> ApplicationDecisionHistory:
        """Return the full immutable decision trail for staff review."""
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        records = await self.lifecycle.list_history(application_id)

        changed_by_ids = {r.changed_by for r in records if r.changed_by}
        names = await self._actor_names(changed_by_ids)

        items: list[ApplicationDecisionHistoryItem] = []
        for record in records:
            meta = record.metadata_json or {}
            raw_decision = meta.get("decision")
            decision = (
                ApplicationDecisionType.from_value(raw_decision)
                if raw_decision else None
            )
            raw_reason = meta.get("reason_code")
            reason = RejectionReason.from_value(raw_reason) if raw_reason else None
            items.append(
                ApplicationDecisionHistoryItem(
                    id=record.id,
                    decision=decision,
                    from_status=ApplicationStatus.from_value(record.from_status or ""),
                    to_status=(
                        ApplicationStatus.from_value(record.to_status)
                        or _FALLBACK_STATUS
                    ),
                    rejection_reason=reason,
                    rejection_reason_label=(
                        REJECTION_REASON_RECRUITER_LABELS.get(reason) if reason else None
                    ),
                    internal_note=record.comment,
                    changed_by=record.changed_by,
                    changed_by_name=names.get(record.changed_by),
                    changed_at=record.changed_at,
                )
            )

        status = ApplicationStatus.from_value(app.status) or _FALLBACK_STATUS
        reason = (
            RejectionReason.from_value(app.decision_reason_code)
            if app.decision_reason_code else None
        )
        return ApplicationDecisionHistory(
            application_id=application_id,
            status=status,
            decided_by=app.decided_by,
            decided_at=app.decided_at,
            rejection_reason=reason,
            internal_note=app.decision_comment,
            candidate_message=candidate_status_message(status, job.title, reason),
            history=items,
        )

    # ── Candidate-safe view ─────────────────────────────────────────
    async def get_candidate_decision(
        self, application_id: uuid.UUID, candidate: User,
    ) -> CandidateApplicationDecisionResponse:
        """Return the decision projection a candidate is allowed to see.

        Candidate ownership is enforced here and nowhere else, so a candidate
        cannot read another candidate's decision by guessing an id. The response
        carries no internal note, no recruiter identity, no score, no ranking, no
        fairness data and no audit trail.
        """
        app = await self.lifecycle.application_repo.get(application_id)
        if not app or app.candidate_id != candidate.id:
            # Same error for "does not exist" and "not yours": no existence leak.
            raise NotFoundError("Application not found")
        job = await self.session.get(Job, app.job_id)
        return self.build_candidate_decision_payload(app, job)

    async def get_candidate_decisions(
        self, candidate: User,
    ) -> list[CandidateApplicationDecisionResponse]:
        """Return the decision projection for all of a candidate's applications.

        Scoped to the caller's own applications by construction, so a list view
        needs one request instead of one per application. Each entry carries the
        same candidate-safe allowlist as :meth:`get_candidate_decision`.
        """
        apps = await self.lifecycle.application_repo.list_by_candidate(candidate.id)
        if not apps:
            return []
        job_ids = {app.job_id for app in apps}
        jobs = {
            job.id: job
            for job in (
                await self.session.execute(
                    select(Job).where(Job.id.in_(job_ids))
                )
            ).scalars().all()
        }
        return [
            self.build_candidate_decision_payload(app, jobs.get(app.job_id))
            for app in apps
        ]

    def build_candidate_decision_payload(
        self, app: JobApplication, job: Job | None,
    ) -> CandidateApplicationDecisionResponse:
        """Build the candidate-safe decision projection for one application.

        Public so read-only candidate surfaces (the Phase 9 tracking view) reuse
        this exact projection instead of re-deriving candidate wording, which
        would risk the tracking page and the decision page telling the candidate
        two different things about the same status.
        """
        status = ApplicationStatus.from_value(app.status) or _FALLBACK_STATUS
        reason = (
            RejectionReason.from_value(app.decision_reason_code)
            if app.decision_reason_code else None
        )
        job_title = job.title if job else ""
        return CandidateApplicationDecisionResponse(
            application_id=app.id,
            job_id=app.job_id,
            job_title=job_title,
            status=status,
            status_label=CANDIDATE_STATUS_LABELS.get(
                status, status.value.replace("_", " ").title(),
            ),
            decision_outcome=_candidate_outcome(status),
            rejection_reason=reason,
            candidate_message=candidate_status_message(status, job_title, reason),
            decided_at=app.decided_at,
            is_decision_final=status in TERMINAL_STATUSES,
        )

    # ── Internals ───────────────────────────────────────────────────
    async def _audit_decision(
        self,
        *,
        app: JobApplication,
        job: Job,
        actor: User,
        decision: ApplicationDecisionType,
        reason_code: str | None,
        status: ApplicationStatus,
        changed_status: bool,
    ) -> None:
        """Audit the explicit human decision separately from the raw status flip.

        Details are limited to non-sensitive context: the decision, the reason
        code, the statuses and the ids. The internal note is deliberately not
        copied into audit details.
        """
        details = {
            "job_id": str(job.id),
            "candidate_id": str(app.candidate_id),
            "decision": decision.value,
            "status": status.value,
            "status_changed": changed_status,
            "reason_code": reason_code,
        }
        await self.lifecycle.audit_service.log(
            event_type=AuditEventType.APPLICATION_DECISION_RECORDED,
            action="application_decision_recorded",
            user_id=actor.id,
            organization_id=job.organization_id,
            resource_type="job_application",
            resource_id=str(app.id),
            details=details,
        )
        if decision is ApplicationDecisionType.REJECT:
            await self.lifecycle.audit_service.log(
                event_type=AuditEventType.APPLICATION_REJECTED,
                action="application_rejected",
                user_id=actor.id,
                organization_id=job.organization_id,
                resource_type="job_application",
                resource_id=str(app.id),
                details=details,
            )
        if decision is ApplicationDecisionType.SELECT:
            await self.lifecycle.audit_service.log(
                event_type=AuditEventType.APPLICATION_SELECTED,
                action="application_selected",
                user_id=actor.id,
                organization_id=job.organization_id,
                resource_type="job_application",
                resource_id=str(app.id),
                details=details,
            )
        AUDIT_LOGGER.info(
            "APPLICATION_DECISION | actor=%s application=%s decision=%s reason_code=%s",
            actor.id, app.id, decision.value, reason_code,
        )

    async def _actor_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Resolve display names for decision actors (staff view only)."""
        if not ids:
            return {}
        rows = await self.session.execute(
            select(User.id, User.full_name).where(User.id.in_(ids))
        )
        return {row[0]: row[1] for row in rows.all()}


def _candidate_outcome(status: ApplicationStatus) -> str:
    return {
        ApplicationStatus.UNDER_REVIEW: "under_review",
        ApplicationStatus.SHORTLISTED: "shortlisted",
        # Phase 13: a positive, final-as-seen-by-the-candidate outcome, kept
        # distinct from "offer" and "hired" so the two are never conflated.
        ApplicationStatus.SELECTED: "selected",
        ApplicationStatus.REJECTED: "not_selected",
    }.get(status, status.value)
