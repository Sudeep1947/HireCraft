"""Application-level screening orchestration (Phase 2).

Thin orchestration layer that connects a ``JobApplication`` -> candidate -> job
to the *existing* matching/ranking engine. This module deliberately computes no
scores itself: every dimension and the overall score come from
``ScreeningService`` / ``MatchingEngine``. Its responsibilities are:

- server-side, organization-aware authorization (never trusts the client);
- a lifecycle guard: finalized (hired/rejected/withdrawn) applications cannot
  be screened;
- an immutable ``APPLICATION_SCREENED`` audit record with the result summary;
- persistence through the existing ``ScreeningResult`` model, now explicitly
  linked to the application;
- a ranking refresh so an application screening participates in job rankings.

There is NO automatic status change and NO hiring/rejection decision here; the
result is decision support only.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.domain.enums import ApplicationStatus, AuditEventType
from app.domain.models import Job, JobApplication, ScreeningResult, User
from app.repositories.jobs.job import JobApplicationRepository
from app.services.applications.application_lifecycle_service import TERMINAL_STATUSES
from app.services.audit_service import AuditService
from app.services.screening.access import (
    JobAccessDeniedError,
    JobNotFoundError,
    authorize_job_access,
)
from app.services.screening.screening_service import ScreeningService

logger = logging.getLogger(__name__)


class ApplicationScreeningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.application_repo = JobApplicationRepository(session)
        self.screening_service = ScreeningService(session)
        self.audit_service = AuditService(session)

    # ─── Commands ──────────────────────────────────────────────────────

    async def screen_application(
        self,
        application_id: uuid.UUID,
        actor: User,
        weights: dict[str, float] | None = None,
    ) -> ScreeningResult:
        """Run the existing screening engine for a single application.

        Raises:
            NotFoundError (404): unknown application/job.
            ForbiddenError (403): actor cannot access the application's job.
            ConflictError (409): the application is already finalized.
            ValidationError (422): the candidate has no profile to screen.
        """
        app, job = await self._load_authorized(application_id, actor)
        return await self._execute(app, job, actor_id=actor.id, trigger="manual", weights=weights)

    async def screen_application_system(
        self,
        application_id: uuid.UUID,
        weights: dict[str, float] | None = None,
    ) -> ScreeningResult:
        """Run screening on behalf of the platform (automatic, no human actor).

        Same engine and persistence as :meth:`screen_application`, but skips the
        actor-based job authorization (there is no requesting user) and records
        the audit entry with ``user_id=None`` and a ``system`` marker.
        """
        app = await self.application_repo.get(application_id)
        if not app:
            raise NotFoundError("Application not found")
        job = await self.session.get(Job, app.job_id)
        if not job:
            raise NotFoundError("Job not found")
        return await self._execute(app, job, actor_id=None, trigger="automatic", weights=weights)

    async def _execute(
        self,
        app: JobApplication,
        job: Job,
        *,
        actor_id: uuid.UUID | None,
        trigger: str,
        weights: dict[str, float] | None = None,
    ) -> ScreeningResult:
        current = ApplicationStatus.from_value(app.status)
        if current in TERMINAL_STATUSES:
            raise ConflictError(
                "A finalized application cannot be screened",
                extra={"application_id": str(app.id), "status": app.status},
            )

        try:
            screening = await self.screening_service.screen_candidate(
                job, app.candidate_id, weights,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))

        # screen_candidate already resolves the application link; keep it
        # correct if the result predates the application or was resolved by a
        # different path.
        if screening.application_id != app.id:
            await self.screening_service.screening_repo.update(
                screening.id, application_id=app.id,
            )
            screening = await self.screening_service.screening_repo.get(screening.id)

        # Keep job rankings consistent with the refreshed screening.
        await self.screening_service.update_rankings(job.id)

        await self.audit_service.log(
            event_type=AuditEventType.APPLICATION_SCREENED,
            action="application_screened",
            user_id=actor_id,
            organization_id=job.organization_id,
            resource_type="job_application",
            resource_id=str(app.id),
            details={
                "job_id": str(job.id),
                "candidate_id": str(app.candidate_id),
                "screening_result_id": str(screening.id),
                "overall_match_score": screening.overall_match_score,
                "recommendation": screening.recommendation,
                "trigger": trigger,
                "actor": "system" if actor_id is None else "user",
            },
        )
        logger.info(
            "APPLICATION_SCREENED | trigger=%s actor=%s application=%s job=%s score=%s",
            trigger, actor_id, app.id, job.id, screening.overall_match_score,
        )
        return screening

    # ─── Queries ───────────────────────────────────────────────────────

    async def get_application_screening(
        self, application_id: uuid.UUID, actor: User,
    ) -> ScreeningResult | None:
        app, _job = await self._load_authorized(application_id, actor)
        return await self.screening_service.screening_repo.get_by_application(app.id)

    # ─── Helpers ───────────────────────────────────────────────────────

    async def _load_authorized(
        self, application_id: uuid.UUID, actor: User,
    ) -> tuple[JobApplication, Job]:
        app = await self.application_repo.get(application_id)
        if not app:
            raise NotFoundError("Application not found")
        job = await self.session.get(Job, app.job_id)
        if not job:
            raise NotFoundError("Job not found")
        try:
            await authorize_job_access(self.session, job.id, actor)
        except JobNotFoundError:
            raise NotFoundError("Job not found")
        except JobAccessDeniedError as exc:
            raise ForbiddenError(str(exc))
        return app, job
