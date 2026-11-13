import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.domain.enums import ApplicationStatus, HiringRecommendation, ScreeningStatus
from app.domain.application_assessment_schemas import (
    OUTCOME_ASSIGNED,
    JobAssessmentAssignRequest,
    JobAssessmentAssignResult,
    JobAssessmentCreateAndAssignRequest,
    JobAssessmentOptions,
)
from app.api.v1.assessments import queue_assignment_notification
from app.domain.application_decision_schemas import (
    ApplicationDecisionCreate,
    ApplicationDecisionHistory,
    ApplicationDecisionOptions,
    ApplicationDecisionResult,
)
from app.domain.job_schemas import (
    ApplicantSummaryResponse,
    JobApplicationDetailResponse,
    JobApplicationUpdate,
    JobApplicantsResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
    JobUpdate,
    RecruiterNoteCreate,
    RecruiterNoteResponse,
)
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.domain.explanation_schemas import RecruiterApplicationExplanationResponse
from app.domain.fairness_context_schemas import (
    ApplicationFairnessContextResponse,
)
from app.domain.models import Job, User
from app.domain.schemas import MessageResponse
from app.domain.screening_schemas import (
    ApplicationScreeningDetailResponse,
    ScreeningResultResponse,
)
from app.services.applications.application_decision_notification import (
    queue_decision_notification,
)
from app.services.applications.application_decision_service import (
    ApplicationDecisionService,
)
from app.services.applications.application_screening_service import (
    ApplicationScreeningService,
)
from app.services.assessment.application_assessment_service import (
    ApplicationAssessmentIntegrationService,
)
from app.services.jobs.recruiter_job_service import RecruiterJobService
from app.services.fairness.fairness_engine import DEFAULT_MINIMUM_GROUP_SIZE
from app.services.fairness.screening_fairness_context_service import (
    ScreeningFairnessContextService,
)
from app.services.screening.access import (
    CandidateNotAccessibleError,
    JobAccessDeniedError,
    JobNotFoundError,
)
from app.services.screening.application_explanation_service import (
    ApplicationExplanationService,
)
from app.services.screening.screening_detail_service import (
    ApplicationScreeningDetailService,
)

router = APIRouter(prefix="/recruiter/jobs", tags=["recruiter-jobs"])


def _get_service(db: AsyncSession = Depends(get_db)) -> RecruiterJobService:
    return RecruiterJobService(db)


def _get_screening_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationScreeningService:
    return ApplicationScreeningService(db)


def _get_screening_detail_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationScreeningDetailService:
    return ApplicationScreeningDetailService(db)


def _get_explanation_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationExplanationService:
    return ApplicationExplanationService(db)


def _get_fairness_context_service(
    db: AsyncSession = Depends(get_db),
) -> ScreeningFairnessContextService:
    return ScreeningFairnessContextService(db)


def _get_decision_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationDecisionService:
    return ApplicationDecisionService(db)


def _get_assessment_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationAssessmentIntegrationService:
    return ApplicationAssessmentIntegrationService(db)


def _raise_decision_http(exc: Exception) -> None:
    """Map decision-layer domain errors onto the existing HTTP contract."""
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=422, detail=str(exc))
    raise exc


@router.get("/dashboard")
async def get_dashboard(
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    return await service.get_recruiter_dashboard(current_user.id)


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    body: JobCreate,
    organization_id: uuid.UUID | None = Query(None),
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Create a job inside the caller's organization (or an explicit one)."""
    return await service.create_job(current_user.id, body, organization_id)


@router.get("", response_model=list[JobListResponse])
async def list_jobs(
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    return await service.list_jobs(current_user.id)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    job = await service.get_job(job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID,
    body: JobUpdate,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    job = await service.update_job(job_id, current_user.id, body)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", response_model=MessageResponse)
async def delete_job(
    job_id: uuid.UUID,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    deleted = await service.delete_job(job_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return MessageResponse(message="Job deleted")


@router.patch("/{job_id}/status", response_model=JobResponse)
async def change_job_status(
    job_id: uuid.UUID,
    status: str,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    valid_statuses = {"draft", "published", "closed", "archived"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    job = await service.change_job_status(job_id, current_user.id, status)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get(
    "/{job_id}/applicants/summary",
    response_model=ApplicantSummaryResponse,
)
async def list_applicant_summary(
    job_id: uuid.UUID,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    return await service.get_job_applicant_summary(job_id, current_user)


@router.get("/{job_id}/applicants", response_model=JobApplicantsResponse)
async def list_applicants(
    job_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=200),
    application_status: ApplicationStatus | None = Query(default=None),
    screening_status: ScreeningStatus | None = Query(default=None),
    recommendation: HiringRecommendation | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    sort_by: Literal[
        "newest", "oldest", "score_high", "score_low", "name_asc", "name_desc",
        "created_at", "-created_at", "overall_match_score", "-overall_match_score",
        "candidate_name", "-candidate_name", "status", "-status",
    ] = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    return await service.get_job_applicants(
        job_id,
        current_user,
        q=q,
        application_status=application_status,
        screening_status=screening_status,
        recommendation=recommendation,
        min_score=min_score,
        max_score=max_score,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}/applications", response_model=list[JobApplicationDetailResponse])
async def list_applications(
    job_id: uuid.UUID,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    return await service.get_applications_for_job(job_id, current_user)


@router.patch("/applications/{application_id}/status", response_model=MessageResponse)
async def update_application_status(
    application_id: uuid.UUID,
    body: JobApplicationUpdate,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Generic status transition (existing Phase 1 contract).

    Recruiter decisions with a structured reason and a candidate-facing
    outcome belong on ``POST /applications/{application_id}/decision``; this
    endpoint stays for existing callers and the simulation shortlist flow.
    """
    await service.update_application_status(
        application_id, current_user, body.status.value,
        reason=body.reason, comment=body.comment,
    )
    return MessageResponse(message=f"Application status updated to {body.status.value}")


# ── Phase 8: explicit recruiter decisions ────────────────────────────────

@router.get(
    "/applications/{application_id}/decision-options",
    response_model=ApplicationDecisionOptions,
)
async def get_application_decision_options(
    application_id: uuid.UUID,
    service: ApplicationDecisionService = Depends(_get_decision_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Which decisions this recruiter may record right now, and why.

    Server-authoritative: the UI renders these instead of a hardcoded
    transition table, so lifecycle rules exist only on the server.
    """
    try:
        return await service.get_decision_options(application_id, current_user)
    except (NotFoundError, ForbiddenError, ConflictError, ValidationError) as exc:
        _raise_decision_http(exc)


@router.post(
    "/applications/{application_id}/decision",
    response_model=ApplicationDecisionResult,
)
async def record_application_decision(
    application_id: uuid.UUID,
    body: ApplicationDecisionCreate,
    background_tasks: BackgroundTasks,
    service: ApplicationDecisionService = Depends(_get_decision_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Record an explicit human decision: keep under review, shortlist or reject.

    The decision is never derived from a screening score, an AI recommendation
    or a fairness metric. Rejection requires a controlled reason; the internal
    note stays private and the candidate sees only the approved projection of
    that reason.

    Status, decision history and audit are written in this request's
    transaction. The candidate notification is queued afterwards and runs in
    its own session, so a notification failure cannot corrupt the decision.
    """
    try:
        result = await service.record_decision(application_id, body, current_user)
    except (NotFoundError, ForbiddenError, ConflictError, ValidationError) as exc:
        _raise_decision_http(exc)

    # The notification reuses the approved candidate wording the decision
    # result already carries, so the queued message and the candidate-facing
    # API projection can never disagree. A decision that did not change the
    # status (keep under review) tells the candidate nothing new, so it sends
    # no notification.
    app = await service.lifecycle.application_repo.get(application_id)
    if result.changed_status and app is not None:
        queue_decision_notification(
            background_tasks,
            application_id=application_id,
            candidate_id=app.candidate_id,
            status=result.status,
            candidate_message=result.candidate_message,
        )
    return result


@router.get(
    "/applications/{application_id}/decision-history",
    response_model=ApplicationDecisionHistory,
)
async def get_application_decision_history(
    application_id: uuid.UUID,
    service: ApplicationDecisionService = Depends(_get_decision_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Full immutable decision trail for staff, including internal notes."""
    try:
        return await service.get_decision_history(application_id, current_user)
    except (NotFoundError, ForbiddenError, ConflictError, ValidationError) as exc:
        _raise_decision_http(exc)


@router.post(
    "/applications/{application_id}/screen",
    response_model=ScreeningResultResponse,
)
async def screen_application(
    application_id: uuid.UUID,
    service: ApplicationScreeningService = Depends(_get_screening_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Run the existing screening engine for a single application.

    Decision support only: no status change and no hiring decision is made.
    """
    return await service.screen_application(application_id, current_user)


@router.get(
    "/applications/{application_id}/screening",
    response_model=ScreeningResultResponse,
)
async def get_application_screening(
    application_id: uuid.UUID,
    service: ApplicationScreeningService = Depends(_get_screening_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    result = await service.get_application_screening(application_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Screening result not found")
    return result


@router.get(
    "/applications/{application_id}/screening-detail",
    response_model=ApplicationScreeningDetailResponse,
)
async def get_application_screening_detail(
    application_id: uuid.UUID,
    service: ApplicationScreeningDetailService = Depends(_get_screening_detail_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Read-only screening detail for one application.

    Authorization is derived from the application's own job, so there is no
    job identifier in the path to substitute and no hiring decision is made.
    """
    try:
        return await service.get_detail(application_id, current_user)
    except (NotFoundError, JobNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ForbiddenError, JobAccessDeniedError, CandidateNotAccessibleError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get(
    "/applications/{application_id}/explanation",
    response_model=RecruiterApplicationExplanationResponse,
)
async def get_application_explanation(
    application_id: uuid.UUID,
    service: ApplicationExplanationService = Depends(_get_explanation_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Phase 6 "Why This Score?" for one application.

    Read-only, and derived from the same persisted ``ScreeningResult`` the
    applicant list and screening detail already show, so the explanation can
    never disagree with the score. Authorization comes from the application's
    own job: there is no job identifier in the path to substitute, and no
    hiring decision is made or implied.
    """
    try:
        return await service.get_recruiter_explanation(application_id, current_user)
    except (NotFoundError, JobNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ForbiddenError, JobAccessDeniedError, CandidateNotAccessibleError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get(
    "/applications/{application_id}/fairness-context",
    response_model=ApplicationFairnessContextResponse,
)
async def get_application_fairness_context(
    application_id: uuid.UUID,
    minimum_group_size: int = Query(
        DEFAULT_MINIMUM_GROUP_SIZE, ge=1, le=100,
    ),
    service: ScreeningFairnessContextService = Depends(
        _get_fairness_context_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Phase 7 fairness and bias context for one application.

    The metrics describe the job's *screened population*, not this individual;
    the application is reported only as a member of that population. Read-only:
    no score, status, rank or screening result is written, and fairness is never
    combined with the match score. Authorization comes from the application's
    own job, so there is no job identifier in the path to substitute.
    """
    try:
        return await service.get_application_fairness_context(
            application_id, current_user, minimum_group_size=minimum_group_size,
        )
    except (NotFoundError, JobNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ForbiddenError, JobAccessDeniedError, CandidateNotAccessibleError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))


class RecruiterNoteUpdate(BaseModel):
    note: str = Field(..., min_length=1)


@router.put("/applications/{application_id}/notes/{note_id}", response_model=RecruiterNoteResponse)
async def update_note(
    application_id: uuid.UUID,
    note_id: uuid.UUID,
    body: RecruiterNoteUpdate,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    note = await service.update_recruiter_note(
        note_id, application_id, current_user, body.note,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/applications/{application_id}/notes/{note_id}", response_model=MessageResponse)
async def delete_note(
    application_id: uuid.UUID,
    note_id: uuid.UUID,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    deleted = await service.delete_recruiter_note(
        note_id, application_id, current_user,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return MessageResponse(message="Note deleted")


@router.post("/applications/{application_id}/notes", response_model=RecruiterNoteResponse, status_code=201)
async def add_note(
    application_id: uuid.UUID,
    body: RecruiterNoteCreate,
    service: RecruiterJobService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    note = await service.add_recruiter_note(application_id, current_user, body)
    if not note:
        raise HTTPException(status_code=404, detail="Application not found")
    return note


# ── Phase 1: job-specific, candidate-specific bulk assessment assignment ──
#
# The per-application assessment routes in ``assessments.py`` answer "assign this
# to *this* candidate". Hiring is a batch activity: a recruiter opens one job,
# sees only that job's applicants, ticks the several they want to evaluate and
# assigns one assessment to all of them at once. These routes are the job-scoped
# front door onto exactly the same assignment engine -- same eligibility rule,
# same SQL-scoped catalog, same attempt rows -- so a batch is never held to a
# different standard than a single assignment.
#
# The job in the path is the only identity input beyond the assessment and the
# chosen schedules: there is no ``candidate_id`` or ``recruiter_id`` in any body,
# and every application id is verified to belong to this job before it is written.


@router.get(
    "/{job_id}/assessment-options",
    response_model=JobAssessmentOptions,
)
async def list_job_assessment_options(
    job_id: uuid.UUID,
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_assessment_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """The assessments this recruiter may assign to this job's applicants.

    The job-scoped counterpart of the per-application options endpoint: the same
    SQL-scoped catalog, keyed by the job so the bulk screen can render the choices
    before any candidate is selected. Whether a *particular* candidate may receive
    an assessment is decided per row at assignment time, not guessed here.
    """
    return await service.get_job_assessment_options(job_id, current_user)


@router.post(
    "/{job_id}/assessments/assign",
    response_model=JobAssessmentAssignResult,
    status_code=201,
)
async def bulk_assign_job_assessment(
    job_id: uuid.UUID,
    body: JobAssessmentAssignRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_assessment_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Assign an existing assessment to several of this job's applicants.

    Partial-success by design: every requested candidate gets one outcome row
    (``assigned`` / ``already_assigned`` / ``skipped`` with a reason), so a single
    ineligible applicant cannot block the rest. The whole batch is written in this
    request's single transaction, and only applications that actually belong to
    this job are touched -- a pasted-in foreign application id is reported as
    ``not_an_applicant``, not assigned.

    The application status is deliberately unchanged: an assessment is evidence
    the recruiter reads before deciding, so assigning one must not shortlist or
    reject anyone.
    """
    result = await service.assign_to_job_applicants(job_id, body, current_user)
    # Commit before queueing, so the notification's own session can never run
    # against an assignment the business transaction has not persisted yet.
    await db.commit()
    _queue_bulk_assignment_notifications(background_tasks, result)
    return result


@router.post(
    "/{job_id}/assessments/create-and-assign",
    response_model=JobAssessmentAssignResult,
    status_code=201,
)
async def bulk_create_and_assign_job_assessment(
    job_id: uuid.UUID,
    body: JobAssessmentCreateAndAssignRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_assessment_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Author one assessment for this job and assign it to several applicants.

    The assessment is created once and scoped to the job in the path (the request
    carries no ``job_id``), then assigned to every eligible selected candidate
    through the same engine as the existing-assessment route, so both entry points
    produce identical assignments.
    """
    result = await service.create_and_assign_to_job_applicants(
        job_id, body, current_user,
    )
    await db.commit()
    _queue_bulk_assignment_notifications(background_tasks, result)
    return result


def _queue_bulk_assignment_notifications(
    background_tasks: BackgroundTasks,
    result: JobAssessmentAssignResult,
) -> None:
    """Queue one assignment notification per newly assigned candidate.

    Runs after the transaction commits, and each notification is delivered on its
    own session with a per-attempt dedupe key, so a delivery failure can neither
    roll back the batch nor produce a duplicate. Only newly created assignments
    notify: an ``already_assigned`` candidate is not told again, and a skipped one
    is not an event.
    """
    for item in result.items:
        if (
            item.outcome != OUTCOME_ASSIGNED
            or item.attempt_id is None
            or item.candidate_id is None
        ):
            continue
        queue_assignment_notification(
            background_tasks,
            attempt_id=item.attempt_id,
            candidate_id=item.candidate_id,
            title=item.assessment_title,
            scheduled_for=item.scheduled_for,
            job_title=result.job_title,
            action_link=item.assessment_link,
        )
