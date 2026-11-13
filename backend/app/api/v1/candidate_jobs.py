import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.domain.application_decision_schemas import (
    CandidateApplicationDecisionResponse,
)
from app.domain.application_tracking_schemas import (
    CandidateApplicationTrackResponse,
)
from app.domain.explanation_schemas import (
    CandidateApplicationExplanationResponse,
)
from app.domain.job_schemas import (
    JobApplicationCreate,
    JobApplicationListItem,
    JobApplicationResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
    JobSearchParams,
    JobSearchResponse,
    SavedJobResponse,
)
from app.domain.models import User
from app.domain.schemas import MessageResponse
from app.services.applications.application_decision_service import (
    ApplicationDecisionService,
)
from app.services.applications.candidate_application_tracking_service import (
    CandidateApplicationTrackingService,
)
from app.services.jobs.candidate_job_service import CandidateJobService
from app.services.screening.access import ApplicationAccessDeniedError
from app.services.screening.application_explanation_service import (
    ApplicationExplanationService,
)

router = APIRouter(prefix="/candidate/jobs", tags=["candidate-jobs"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CandidateJobService:
    return CandidateJobService(db)


def _get_explanation_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationExplanationService:
    return ApplicationExplanationService(db)


def _get_decision_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationDecisionService:
    return ApplicationDecisionService(db)


def _get_tracking_service(
    db: AsyncSession = Depends(get_db),
) -> CandidateApplicationTrackingService:
    return CandidateApplicationTrackingService(db)


@router.get("/dashboard")
async def get_dashboard(
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_candidate_dashboard(current_user.id)


@router.get("/search", response_model=JobSearchResponse)
async def search_jobs(
    q: str | None = None,
    employment_type: str | None = None,
    location: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    skills: str | None = None,
    status: str | None = "published",
    page: int = 1,
    page_size: int = 20,
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    skill_list = skills.split(",") if skills else None
    params = JobSearchParams(
        q=q,
        employment_type=employment_type,
        location=location,
        salary_min=salary_min,
        salary_max=salary_max,
        skills=skill_list,
        status=status,
        page=page,
        page_size=page_size,
    )
    return await service.search_jobs(params)


@router.post("/apply", response_model=JobApplicationResponse, status_code=201)
async def apply_for_job(
    body: JobApplicationCreate,
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        return await service.apply(current_user.id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/applications", response_model=list[JobApplicationListItem])
async def my_applications(
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_my_applications(current_user.id)


@router.get(
    "/applications/{application_id}/explanation",
    response_model=CandidateApplicationExplanationResponse,
)
async def get_my_application_explanation(
    application_id: uuid.UUID,
    service: ApplicationExplanationService = Depends(_get_explanation_service),
    current_user: User = Depends(require_role("candidate")),
):
    """Phase 6 "How Your Profile Matches This Role" for one application.

    Same authoritative explanation as the recruiter view, projected through an
    explicit candidate-safe allowlist: no recruiter notes, no ranking or
    recommendation, no engine formulas, no other candidate's data.

    Access is ownership-only. A request for somebody else's application returns
    the same 404 as a non-existent id, so application ids cannot be probed.
    """
    try:
        return await service.get_candidate_explanation(application_id, current_user)
    except (NotFoundError, ApplicationAccessDeniedError):
        raise HTTPException(status_code=404, detail="Application not found")


@router.get(
    "/applications/decisions",
    response_model=list[CandidateApplicationDecisionResponse],
)
async def get_my_application_decisions(
    service: ApplicationDecisionService = Depends(_get_decision_service),
    current_user: User = Depends(require_role("candidate")),
):
    """Phase 8: the candidate's decision view for all their applications.

    Scoped to the caller's own applications, so the list page needs one request
    instead of one per row. Same explicit allowlist as the single-application
    endpoint: no internal note, no recruiter identity, no score, no ranking, no
    fairness data and no audit trail.
    """
    return await service.get_candidate_decisions(current_user)


# Declared after the static ``/applications/decisions`` route on purpose: a bare
# ``/applications/{application_id}`` would otherwise capture ``decisions`` as an
# application id and answer that request with a 404-shaped tracking payload.
@router.get(
    "/applications/{application_id}",
    response_model=CandidateApplicationTrackResponse,
)
async def get_my_application_track(
    application_id: uuid.UUID,
    service: CandidateApplicationTrackingService = Depends(_get_tracking_service),
    current_user: User = Depends(require_role("candidate")),
):
    """Phase 9: where one of the candidate's applications stands.

    Reads the application row and its immutable
    ``ApplicationStatusHistory`` trail, and renders progress strictly from the
    statuses actually recorded. The decision block is the same reviewed
    candidate-safe projection the decision endpoint returns, and ``can_withdraw``
    comes from the same transition map the write path enforces, so the client
    holds no lifecycle rules of its own.

    The response is an allowlist: no internal note, no recruiter identity, no
    free-text transition reason, no history comments or metadata, no screening
    error text, no score, no ranking, no fairness data and no audit trail.

    Access is ownership-only; another candidate's id returns the same 404 as a
    non-existent one, so ids cannot be probed.
    """
    try:
        return await service.get_application_track(application_id, current_user)
    except (NotFoundError, ApplicationAccessDeniedError):
        raise HTTPException(status_code=404, detail="Application not found")


@router.get(
    "/applications/{application_id}/decision",
    response_model=CandidateApplicationDecisionResponse,
)
async def get_my_application_decision(
    application_id: uuid.UUID,
    service: ApplicationDecisionService = Depends(_get_decision_service),
    current_user: User = Depends(require_role("candidate")),
):
    """Phase 8: the candidate's view of a decision on their application.

    Returns the application status, the approved candidate-facing reason and
    when the decision was made. It deliberately excludes the recruiter's
    internal note, the recruiter's identity, the screening score, the AI
    recommendation, ranking position, fairness context and audit data: the
    response is built from an explicit allowlist of stored fields.

    Access is ownership-only, and a request for another candidate's application
    returns the same 404 as a non-existent id so ids cannot be probed.
    """
    try:
        return await service.get_candidate_decision(application_id, current_user)
    except (NotFoundError, ForbiddenError):
        raise HTTPException(status_code=404, detail="Application not found")


@router.post("/applications/{application_id}/withdraw", response_model=MessageResponse)
async def withdraw_application(
    application_id: uuid.UUID,
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.withdraw_application(application_id, current_user)
    return MessageResponse(message="Application withdrawn")


@router.post("/saved", response_model=SavedJobResponse, status_code=201)
async def save_job(
    job_id: uuid.UUID,
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        saved = await service.save_job(current_user.id, job_id)
        return SavedJobResponse(job_id=saved.job_id, created_at=saved.created_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/saved", response_model=list[JobListResponse])
async def saved_jobs(
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_saved_jobs(current_user.id)


@router.delete("/saved/{job_id}", response_model=MessageResponse)
async def unsave_job(
    job_id: uuid.UUID,
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    removed = await service.unsave_job(current_user.id, job_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Saved job not found")
    return MessageResponse(message="Job unsaved")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_detail(
    job_id: uuid.UUID,
    service: CandidateJobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    job = await service.get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or unavailable")
    return job
