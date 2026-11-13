"""Read-only recruiter screening detail for a single application (Phase 5).

This service is deliberately thin. It authorizes, loads what already exists
and composes existing contracts. It never recalculates a score, never re-runs
ranking, never rebuilds skill intelligence and never re-parses a resume:

* the screening result is the persisted ``ScreeningResult`` row, resolved by
  ``application_id`` so a candidate's other applications can never leak in;
* requirement level matching, evidence and fit scores come from the Phase 2
  ``FitService`` (cache backed);
* evidence depth, strengths, evidence gaps and the narrative summary come from
  the Phase 3 ``CandidateIntelService`` (cache backed).

Each intelligence source is isolated: if one is unavailable the rest of the
detail is still returned with that section flagged.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes, selectinload

from app.core.exceptions import NotFoundError
from app.domain.enums import ScreeningStatus
from app.domain.models import JobApplication, User
from app.repositories.candidate.resume import ResumeRepository
from app.repositories.screening.screening import ScreeningResultRepository
from app.services.jobs.recruiter_job_service import RecruiterJobService
from app.services.screening.access import authorize_job_access
from app.services.screening.fit_service import FitService
from app.services.screening.intel_service import CandidateIntelService

logger = logging.getLogger(__name__)

SCREENING_DIMENSIONS: tuple[tuple[str, str, str], ...] = (
    ("skills", "Skills", "skill_match_score"),
    ("experience", "Experience", "experience_match_score"),
    ("education", "Education", "education_match_score"),
    ("projects", "Projects", "project_match_score"),
    ("certifications", "Certifications", "certification_match_score"),
    ("location", "Location", "location_match_score"),
    ("employment_type", "Employment type", "employment_type_match_score"),
    ("semantic", "Semantic", "semantic_match_score"),
)

NO_ENGINE_VERSION = (
    "The stored screening result does not record an algorithm or model version."
)
NO_RECRUITER_RESUME_VIEWER = (
    "Recruiters have no resume viewer in this release, so the resume file is "
    "not opened from here. Evidence quotes come from the stored parsed resume."
)
NO_STALENESS_DETECTION = (
    "This release does not flag a screening result as stale when the job or "
    "the candidate resume changes after screening."
)
NO_CONFIDENCE_VALUE = (
    "The screening engine does not produce a confidence value, so none is shown."
)


def _list_of_strings(value) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


class ApplicationScreeningDetailService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.screening_repo = ScreeningResultRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.intel_service = CandidateIntelService(session)
        self.fit_service = FitService(session)

    async def get_detail(
        self,
        application_id: uuid.UUID,
        actor: User,
    ) -> dict:
        application = await self._load_application(application_id)
        job = await authorize_job_access(self.session, application.job_id, actor)
        screening = await self._resolve_screening(application)
        attributes.set_committed_value(
            application,
            "screening_result",
            [screening] if screening is not None else [],
        )

        job_intel, intel_error = await self._load_job_intel(application, actor)
        fit, fit_error = await self._load_fit(application, actor)

        evidence_intelligence = job_intel.get("candidate_intelligence") if job_intel else None
        job_context = job_intel.get("job_context") if job_intel else None
        candidate = application.candidate
        primary_resume = await self.resume_repo.get_primary(application.candidate_id)
        resume_id = primary_resume.id if primary_resume else application.resume_id
        screening_resume_id = screening.resume_id if screening is not None else None
        resume_matches: bool | None = None
        if screening is not None and resume_id is not None and screening_resume_id is not None:
            resume_matches = resume_id == screening_resume_id

        limitations = [NO_CONFIDENCE_VALUE, NO_STALENESS_DETECTION, NO_RECRUITER_RESUME_VIEWER]
        if screening is not None:
            limitations.append(NO_ENGINE_VERSION)

        return {
            "application": {
                "id": application.id,
                "job_id": application.job_id,
                "candidate_id": application.candidate_id,
                "resume_id": application.resume_id,
                "status": application.status,
                "applied_at": application.created_at,
                "updated_at": application.updated_at,
                "cover_letter": application.cover_letter,
                "decision_reason": application.decision_reason,
                "decision_comment": application.decision_comment,
                "decided_at": application.decided_at,
                "screening": {
                    "effective_status": RecruiterJobService.effective_screening_status(application),
                    "recorded_status": application.screening_status
                    or ScreeningStatus.NOT_STARTED.value,
                    "attempts": application.screening_attempts or 0,
                    "task_id": application.screening_task_id,
                    "error": application.screening_error,
                    "started_at": application.screening_started_at,
                    "completed_at": application.screening_completed_at,
                },
            },
            "candidate": {
                "id": application.candidate_id,
                "name": candidate.full_name if candidate else "",
                "email": candidate.email if candidate else "",
                "resume_id": resume_id,
                "has_resume": resume_id is not None,
            },
            "job": {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "employment_type": job.employment_type,
                "experience_required": job.experience_required,
                "education_required": job.education_required,
                "required_skills": _list_of_strings(job.required_skills),
                "preferred_skills": _list_of_strings(job.preferred_skills),
            },
            "screening_result": screening,
            "match_breakdown": self._match_breakdown(screening),
            "evidence_intelligence": evidence_intelligence,
            "evidence_intelligence_section": {
                "available": evidence_intelligence is not None,
                "reason": intel_error,
            },
            "fit": fit,
            "fit_section": {"available": fit is not None, "reason": fit_error},
            "job_context": job_context,
            "job_context_section": {
                "available": job_context is not None,
                "reason": intel_error,
            },
            "freshness": {
                "screened_at": screening.created_at if screening is not None else None,
                "screening_resume_id": screening_resume_id,
                "application_resume_id": application.resume_id,
                "resume_matches_application": resume_matches,
                "engine_version": None,
                "fit_engine_version": (fit or {}).get("engine_version"),
                "evidence_engine_version": (job_intel or {}).get("engine_version"),
            },
            "limitations": limitations,
        }

    async def _load_application(self, application_id: uuid.UUID) -> JobApplication:
        result = await self.session.execute(
            select(JobApplication)
            .options(
                selectinload(JobApplication.candidate),
                selectinload(JobApplication.job),
            )
            .where(JobApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise NotFoundError("Application not found")
        return application

    async def _resolve_screening(self, application: JobApplication):
        screening = await self.screening_repo.get_by_application(application.id)
        if screening is not None:
            return screening
        return await self.screening_repo.get_by_job_and_candidate(
            application.job_id, application.candidate_id,
        )

    async def _load_job_intel(
        self, application: JobApplication, actor: User,
    ) -> tuple[dict | None, str | None]:
        try:
            payload = await self.intel_service.get_job_intel(
                application.job_id, application.candidate_id, actor,
            )
        except Exception as exc:  # noqa: BLE001 - one section must not break the page
            logger.warning(
                "Evidence intelligence unavailable for application %s",
                application.id, exc_info=True,
            )
            return None, f"Evidence intelligence unavailable: {exc}"
        if not payload:
            return None, "Evidence intelligence unavailable for this application."
        return payload, None

    async def _load_fit(
        self, application: JobApplication, actor: User,
    ) -> tuple[dict | None, str | None]:
        try:
            payload = await self.fit_service.get_fit(
                application.job_id, application.candidate_id, actor,
            )
        except Exception as exc:  # noqa: BLE001 - one section must not break the page
            logger.warning(
                "Fit analysis unavailable for application %s",
                application.id, exc_info=True,
            )
            return None, f"Fit analysis unavailable: {exc}"
        if not payload:
            return None, "Fit analysis unavailable for this application."
        return payload, None

    @staticmethod
    def _match_breakdown(screening) -> list[dict]:
        if screening is None:
            return []
        return [
            {
                "key": key,
                "label": label,
                "score": getattr(screening, column),
                "source_column": column,
            }
            for key, label, column in SCREENING_DIMENSIONS
        ]
