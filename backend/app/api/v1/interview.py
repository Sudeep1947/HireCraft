import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.domain.application_interview_schemas import (
    ApplicationInterviewAdvanceRequest,
    ApplicationInterviewCancelRequest,
    ApplicationInterviewCompleteRequest,
    ApplicationInterviewEvidence,
    ApplicationInterviewFeedback,
    ApplicationInterviewFeedbackRequest,
    ApplicationInterviewOptions,
    ApplicationInterviewRejectRequest,
    ApplicationInterviewRescheduleRequest,
    ApplicationInterviewScheduleRequest,
    ApplicationInterviewScheduleResult,
    ApplicationInterviewStageActionResult,
    HRInterviewerOption,
)
from app.domain.interview_schemas import (
    CodingAssessmentGenerateRequest,
    CodingAssessmentResponse,
    CodingSubmissionRequest,
    CodingSubmissionResponse,
    InterviewAnswerRequest,
    InterviewCompleteRequest,
    InterviewDashboardResponse,
    InterviewDetailResponse,
    InterviewGenerateRequest,
    InterviewGenerateResponse,
    InterviewListResponse,
    InterviewNotesRequest,
    InterviewScheduleRequest,
    InterviewStartRequest,
    MockInterviewStartResponse,
    AnswerSubmitResponse,
    ScorecardCreateRequest,
    ScorecardResponse,
    CandidateInterviewDashboardResponse,
)
from app.domain.interview_room_schemas import InterviewRoomState
from app.domain.models import CodingAssessment, Interview, Job, JobApplication, User
from app.services.applications.application_decision_notification import (
    queue_decision_notification,
)
from app.services.interview.application_interview_notification import (
    queue_interview_notification,
    queue_staff_application_notification,
    queue_staff_interview_notification,
)
from app.services.interview.application_interview_service import (
    ApplicationInterviewIntegrationService,
)
from app.services.interview.coding_engine import CodingEngine
from app.services.interview.interview_access import (
    load_interview_for_read,
    load_interview_for_staff_read,
    load_interview_for_staff_write,
    require_job_staff_access,
    require_own_coding_assessment,
    require_own_interview,
    require_own_question,
)
from app.services.interview.interview_analytics import InterviewAnalytics
from app.services.interview.interview_service import InterviewService
from app.services.interview.interview_room_service import InterviewRoomService
from app.services.interview.mock_interview import MockInterviewService
from app.services.screening.access import (
    CandidateNotAccessibleError,
    authorize_candidate_access,
    authorized_job_ids,
)

router = APIRouter(prefix="/interview", tags=["interview"])

logger = logging.getLogger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> InterviewService:
    return InterviewService(db)


def _get_analytics(db: AsyncSession = Depends(get_db)) -> InterviewAnalytics:
    return InterviewAnalytics(db)


def _get_application_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationInterviewIntegrationService:
    return ApplicationInterviewIntegrationService(db)


def _get_room_service(db: AsyncSession = Depends(get_db)) -> InterviewRoomService:
    return InterviewRoomService(db)


# ─── Generate Questions ────────────────────────────────────────────


@router.post("/generate", response_model=InterviewGenerateResponse)
async def generate_questions(
    body: InterviewGenerateRequest,
    service: InterviewService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    try:
        result = await service.generate_questions(
            job_id=body.job_id,
            recruiter_id=current_user.id,
            categories=body.categories,
            difficulty=body.difficulty,
            count=body.count,
            candidate_id=body.candidate_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from app.domain.interview_schemas import QuestionResponse
    questions = [
        QuestionResponse(
            id=uuid.uuid4(),
            question_text=q["question_text"],
            category=q["category"],
            difficulty=q["difficulty"],
            order_index=idx,
            context=q.get("context"),
        )
        for idx, q in enumerate(result["questions"])
    ]

    return InterviewGenerateResponse(
        interview_id=uuid.uuid4(),
        questions=questions,
        total_questions=result["total_questions"],
        categories=result["categories"],
        difficulty=result["difficulty"],
    )


# ─── Schedule Interview ────────────────────────────────────────────


@router.post("/schedule")
async def schedule_interview(
    body: InterviewScheduleRequest,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Legacy job+candidate scheduling, kept for the mock/practice flow.

    Prefer ``POST /interview/applications/{application_id}/schedule``: this
    endpoint takes the job and candidate from the request, so it can schedule an
    interview for a candidate who never applied. It is still tenant-checked --
    the job must belong to the caller's organization or be owned by them -- but
    it cannot validate the candidate against any application.
    """
    await require_job_staff_access(db, body.job_id, current_user)
    try:
        interview = await service.schedule_interview(
            job_id=body.job_id,
            candidate_id=body.candidate_id,
            recruiter_id=current_user.id,
            scheduled_at=body.scheduled_at,
            duration_minutes=body.duration_minutes,
            categories=body.categories,
            difficulty=body.difficulty,
            question_count=body.question_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "message": "Interview scheduled successfully",
        "interview_id": str(interview.id),
        "status": interview.status,
    }


# ─── Start Mock Interview ─────────────────────────────────────────


@router.post("/mock/start", response_model=MockInterviewStartResponse)
async def start_mock_interview(
    body: InterviewStartRequest,
    service: InterviewService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    from app.domain.models import Job
    from app.db.session import async_session_factory

    interview = await service.session.get(Job, body.interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        from app.domain.interview_schemas import QuestionResponse
        result = await service.start_mock_interview(
            candidate_id=current_user.id,
            job_id=body.interview_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    first = result["first_question"]
    first_q = QuestionResponse(
        id=first.id,
        question_text=first.question_text,
        category=first.category,
        difficulty=first.difficulty,
        order_index=first.order_index,
        context=first.context,
    ) if first else QuestionResponse(
        id=uuid.uuid4(),
        question_text="No questions available",
        category="technical",
        difficulty="medium",
        order_index=0,
    )

    return MockInterviewStartResponse(
        interview_id=result["interview_id"],
        job_id=result["job_id"],
        job_title=result["job_title"],
        first_question=first_q,
        total_questions=result["total_questions"],
        message="Mock interview started. Answer each question to proceed.",
    )


# ─── Submit Answer ─────────────────────────────────────────────────


@router.post("/mock/answer", response_model=AnswerSubmitResponse)
async def submit_answer(
    body: InterviewAnswerRequest,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("candidate")),
):
    """Submit an answer to one of the caller's own interview questions.

    The question id is untrusted input, so it is resolved to its interview and
    checked against the caller. Without that check any candidate could answer any
    question in the system and receive a full evaluation of somebody else's
    interview content.
    """
    try:
        await require_own_question(db, body.question_id, current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Question not found") from exc

    from app.domain.interview_schemas import EvaluationResponse, QuestionResponse
    try:
        result = await service.submit_answer(
            question_id=body.question_id,
            answer_text=body.answer_text,
            time_taken_seconds=body.time_taken_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    eval_data = result["evaluation"]
    evaluation = EvaluationResponse(id=result["answer_id"], **eval_data)

    next_q = None
    if result["next_question"]:
        nq = result["next_question"]
        next_q = QuestionResponse(
            id=nq.id,
            question_text=nq.question_text,
            category=nq.category,
            difficulty=nq.difficulty,
            order_index=nq.order_index,
            context=nq.context,
        )

    return AnswerSubmitResponse(
        answer_id=result["answer_id"],
        evaluation=evaluation,
        next_question=next_q,
        questions_remaining=result["questions_remaining"],
    )


# ─── Complete Mock Interview ──────────────────────────────────────


@router.post("/mock/complete")
async def complete_mock_interview(
    body: InterviewCompleteRequest,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("candidate")),
):
    """Finish one of the caller's own mock interviews.

    Scoped to the caller, so an interview id from another candidate cannot be
    completed -- and cannot be used to read back that candidate's aggregate
    score and feedback summary.
    """
    try:
        await require_own_interview(db, body.interview_id, current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Interview not found") from exc

    try:
        result = await service.complete_interview(body.interview_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "interview_id": str(result["interview_id"]),
        "overall_score": result["overall_score"],
        "strong_areas": result["strong_areas"],
        "weak_areas": result["weak_areas"],
        "improvement_suggestions": result["improvement_suggestions"],
        "feedback_summary": result["feedback_summary"],
    }


# ─── List Interviews ──────────────────────────────────────────────


@router.get("/list", response_model=InterviewListResponse)
async def list_interviews(
    service: InterviewService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate", "hr", "recruiter")),
):
    role = current_user.roles[0].role.name if current_user.roles else "candidate"
    items = await service.list_interviews(current_user.id, role)
    return InterviewListResponse(items=items, total=len(items))


# ─── Dashboard ────────────────────────────────────────────────────


@router.get("/dashboard")
async def get_dashboard(
    service: InterviewService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate", "hr", "recruiter")),
):
    role = current_user.roles[0].role.name if current_user.roles else "candidate"
    return await service.get_dashboard(current_user.id, role)


# ─── Analytics ────────────────────────────────────────────────────


@router.get("/analytics")
async def get_analytics(
    service: InterviewAnalytics = Depends(_get_analytics),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Interview analytics, scoped to the caller.

    A recruiter sees their own interviews. An HR user sees the interviews for the
    jobs they may read, resolved through ``authorized_job_ids`` -- the same
    job-owner-or-active-member rule the screening layer enforces -- rather than
    by dropping the filter, which is what made this endpoint raise for HR and
    what would have turned it into a cross-tenant read.
    """
    role = current_user.roles[0].role.name if current_user.roles else "recruiter"
    if role == "recruiter":
        return await service.get_analytics(recruiter_id=current_user.id)
    return await service.get_analytics(
        job_ids=await authorized_job_ids(db, current_user),
    )


# ─── Candidate Scorecards ─────────────────────────────────────────


@router.get("/scorecard/{candidate_id}")
async def get_candidate_scorecards(
    candidate_id: uuid.UUID,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Every scorecard for one candidate, across the jobs the caller may read.

    Scoped with ``authorize_candidate_access``, which requires the candidate to
    have applied to at least one job the caller owns or shares through their
    organization. Without it any recruiter could read any candidate's overall
    scores and AI summaries across tenants by supplying their id.
    """
    try:
        await authorize_candidate_access(db, candidate_id, current_user)
    except CandidateNotAccessibleError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    return await service.get_candidate_scorecards(candidate_id)


# ─── Get Interview Detail ─────────────────────────────────────────


@router.get("/{interview_id}")
async def get_interview(
    interview_id: uuid.UUID,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("candidate", "hr", "recruiter")),
):
    """Interview detail: questions, answers and, for staff, assessments.

    Authorized against the interview's job (for staff) or the candidate column
    (for the candidate), so an id from another tenant returns the same 404 as a
    missing one.

    The candidate's own copy is narrowed: no scorecard (so no recommendation,
    hiring confidence or recruiter notes), no interview evaluations on a real
    interview, and no interviewer identity. A mock interview keeps its
    evaluations, because reading the AI feedback on their own practice answers is
    the point of the mock flow.
    """
    interview = await load_interview_for_read(db, interview_id, current_user)
    result = await service.get_interview_detail(
        interview_id, for_candidate=interview.candidate_id == current_user.id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Interview not found")
    return result


# ─── Shared Interview Room (attendance) ────────────────────────────
#
# Declared here, among the per-interview routes, because a room *is* an
# interview: both participants address the same ``interview_id`` and there is one
# room per interview. These two endpoints are the missing link between the
# recruiter who schedules (Phase 11) and the recruiter who later records the
# interview completed and decides (Phase 8). They add no scheduling and no
# decision; they record who actually turned up.


@router.get("/{interview_id}/room", response_model=InterviewRoomState)
async def get_interview_room(
    interview_id: uuid.UUID,
    service: InterviewRoomService = Depends(_get_room_service),
    current_user: User = Depends(require_role("candidate", "hr", "recruiter")),
):
    """The shared room for one interview, without joining it.

    Open to both participants and to job staff, and authorized against the same
    job-scoped-or-is-the-candidate rule as the interview detail endpoint, so a
    recruiter from another organization gets the same 404 as a missing id.

    Deliberately a pure read: polling this to run a countdown must not mark
    anybody as present and must not start the interview. Attendance is recorded
    only by ``POST .../join``.

    Returns one shape for both roles with ``your_role`` naming the caller, so the
    same component serves the candidate and the interviewer. Presence is reported
    as whether the *other* party is here and never as identity, so this response
    cannot disclose the interviewer's account to the candidate.
    """
    return await service.get_room_state(interview_id, current_user)


@router.post("/{interview_id}/join", response_model=InterviewRoomState)
async def join_interview_room(
    interview_id: uuid.UUID,
    service: InterviewRoomService = Depends(_get_room_service),
    current_user: User = Depends(require_role("candidate", "hr", "recruiter")),
):
    """Enter the shared room, recording attendance.

    The first participant in moves the interview from ``scheduled`` to
    ``in_progress`` and stamps ``started_at``. That is the transition Phase 11's
    reschedule/cancel/complete guards already honoured but that nothing ever
    wrote, so an interview's status finally reflects that it was actually held.

    Joining does **not** complete the interview, does not advance the application
    past ``INTERVIEW_SCHEDULED``, and never selects or rejects the candidate.
    Those remain the explicit Phase 11 completion and Phase 8 decision actions,
    which own their transitions, locking, history and notifications.

    Idempotent: rejoining returns the current state instead of erroring, so a
    reload or a retried request cannot lock somebody out of a room they are in.
    A refused join raises 409 carrying the controlled reason, which the read
    endpoint reports as ``can_join``/``unavailable_reason``, so the UI renders
    the same answer the server would give rather than a dead button.
    """
    return await service.join(interview_id, current_user)


# ─── Evaluate Interview ───────────────────────────────────────────


@router.post("/{interview_id}/evaluate")
async def evaluate_interview(
    interview_id: uuid.UUID,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    await load_interview_for_staff_write(db, interview_id, current_user)
    try:
        scorecard = await service.evaluate_interview(interview_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return scorecard


# ─── Get Scorecard ────────────────────────────────────────────────


@router.get("/{interview_id}/scorecard")
async def get_scorecard(
    interview_id: uuid.UUID,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """The scorecard for one interview -- staff only.

    Previously unauthenticated beyond "is logged in", which let any user read any
    candidate's scorecard by guessing an interview id, and then scoped to "job
    access *or* I am the candidate", which let the candidate read the hiring
    recommendation and the recruiter's private notes about themselves.

    Both halves are wrong for this resource: a scorecard is the interviewer's
    conclusion, so the subject is refused outright and only staff with access to
    the job may read it. An id the caller cannot reach returns the same 404 as a
    missing one.
    """
    await load_interview_for_staff_read(db, interview_id, current_user)
    scorecard = await service.get_scorecard(interview_id)
    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return scorecard


# ─── Create/Update Scorecard ──────────────────────────────────────


@router.post("/{interview_id}/scorecard")
async def create_scorecard(
    interview_id: uuid.UUID,
    body: ScorecardCreateRequest,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    await load_interview_for_staff_write(db, interview_id, current_user)
    try:
        scorecard = await service.create_scorecard(
            interview_id=interview_id,
            recruiter_id=current_user.id,
            data=body.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return scorecard


# ─── Add Notes ────────────────────────────────────────────────────


@router.post("/{interview_id}/notes")
async def add_notes(
    interview_id: uuid.UUID,
    body: InterviewNotesRequest,
    service: InterviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    await load_interview_for_staff_write(db, interview_id, current_user)
    try:
        await service.add_notes(interview_id, body.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "Notes saved successfully"}


# ─── Coding Assessment ────────────────────────────────────────────


@router.post("/coding/generate")
async def generate_coding_assessment(
    body: CodingAssessmentGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Generate a set of coding problems for an interview.

    The problem generator is stateless, so nothing sensitive is at stake, but the
    response echoes ``interview_id`` as if the problems had been attached to it.
    Left unchecked, a recruiter could name any interview id -- including one from
    another tenant -- and get a response asserting an assignment that does not
    exist. Loading the interview keeps the echo honest.
    """
    await load_interview_for_staff_read(db, body.interview_id, current_user)
    problems = CodingEngine.generate_assessments(
        difficulty=body.difficulty,
        category=body.category,
        count=body.count,
    )
    return {
        "interview_id": str(body.interview_id),
        "assessments": problems,
        "total": len(problems),
    }


@router.post("/coding/submit", response_model=CodingSubmissionResponse)
async def submit_coding_solution(
    body: CodingSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("candidate")),
):
    """Submit a coding solution for an assessment on the caller's own interview.

    The assessment id is untrusted input; it is resolved to its interview and
    checked against the caller before the solution is graded, so one candidate
    cannot overwrite or read back another candidate's coding work.
    """
    from app.db.session import async_session_factory

    try:
        await require_own_coding_assessment(db, body.assessment_id, current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Assessment not found") from exc

    async with async_session_factory() as session:
        assessment = await session.get(CodingAssessment, body.assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        result = CodingEngine.evaluate_submission(
            solution=body.solution,
            test_cases=assessment.test_cases or [],
            category=assessment.category,
        )

        assessment.candidate_solution = body.solution
        assessment.is_correct = result["is_correct"]
        assessment.score = result["score"]
        await session.commit()

    return CodingSubmissionResponse(
        assessment_id=body.assessment_id,
        is_correct=result["is_correct"],
        score=result["score"],
        feedback=result["feedback"],
        expected_approach=result["expected_approach"],
    )


# ══════════════════════════════════════════════════════════════════════
# Phase 11 – application-driven interviews
#
# Declared after the ``/{interview_id}`` routes so the literal ``applications``
# segment can never be captured as an interview id. Every path parameter is
# scoped: the application is authorized for staff, and the interview is always
# looked up *within* that application.
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/applications/{application_id}/interviews",
    response_model=ApplicationInterviewEvidence,
)
async def get_application_interview_evidence(
    application_id: uuid.UUID,
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Phase 11: every interview recorded against one application.

    The recruiter's evidence view: the interviews linked to the application with
    their scorecard aggregate and recommendation, plus a completed-interview
    average. The per-answer evaluations stay on the existing interview detail
    endpoint, so this stays cheap to render in the applicant list.

    Staff access is the same job-owner-or-active-org-staff rule the application
    decision endpoints use, so a recruiter from another organization is refused
    rather than shown an empty list.
    """
    return await service.get_evidence(application_id, current_user)


@router.get(
    "/applications/{application_id}/interviews/options",
    response_model=ApplicationInterviewOptions,
)
async def get_application_interview_options(
    application_id: uuid.UUID,
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Which interview actions this recruiter may take right now, and why not.

    Server-authoritative, derived from the lifecycle transition map, so the UI
    never offers an action the backend would reject and never re-implements a
    lifecycle rule.
    """
    return await service.get_options(application_id, current_user)


@router.post(
    "/applications/{application_id}/interviews",
    response_model=ApplicationInterviewScheduleResult,
    status_code=201,
)
async def schedule_application_interview(
    application_id: uuid.UUID,
    body: ApplicationInterviewScheduleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Phase 11: schedule an interview for an application.

    The job, candidate, recruiter and organization all come from the application
    in the path, so a recruiter cannot schedule an interview against a different
    candidate or another tenant's job. Requires a shortlisted application, and
    refuses when one is already scheduled or in progress, so a retried request
    cannot produce a duplicate.

    Writes the interview and the ``INTERVIEW_SCHEDULED`` transition in this
    request's transaction; the candidate notification is queued afterwards and
    runs in its own session, so a notification failure cannot corrupt the
    schedule.
    """
    result = await service.schedule(application_id, body, current_user)
    await _commit_and_notify(db, background_tasks, application_id, result, "scheduled")
    return result


@router.post(
    "/applications/{application_id}/interviews/{interview_id}/reschedule",
    response_model=ApplicationInterviewScheduleResult,
)
async def reschedule_application_interview(
    application_id: uuid.UUID,
    interview_id: uuid.UUID,
    body: ApplicationInterviewRescheduleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Move a scheduled interview to a new time, keeping its questions and records.

    The application status is deliberately unchanged: an interview was already
    scheduled and still is, so nothing about the candidate's stage has changed.
    """
    result = await service.reschedule(
        application_id, interview_id, body, current_user,
    )
    await _commit_and_notify(
        db, background_tasks, application_id, result, "rescheduled",
    )
    return result


@router.post(
    "/applications/{application_id}/interviews/{interview_id}/cancel",
    response_model=ApplicationInterviewScheduleResult,
)
async def cancel_application_interview(
    application_id: uuid.UUID,
    interview_id: uuid.UUID,
    body: ApplicationInterviewCancelRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Cancel a scheduled interview.

    The application stays at ``INTERVIEW_SCHEDULED``: a cancellation is not a
    decision about the candidate, and no rejection is inferred from it. The
    recruiter reschedules the same interview or takes a separate, explicit
    action. The internal ``reason`` is recorded on the audit trail and is not
    included in the candidate notification.
    """
    result = await service.cancel(application_id, interview_id, body, current_user)
    await _commit_and_notify(
        db, background_tasks, application_id, result, "cancelled",
    )
    return result


@router.post(
    "/applications/{application_id}/interviews/{interview_id}/complete",
    response_model=ApplicationInterviewScheduleResult,
)
async def complete_application_interview(
    application_id: uuid.UUID,
    interview_id: uuid.UUID,
    body: ApplicationInterviewCompleteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Mark an application-linked interview completed.

    Records that the interview happened and advances the application to
    ``INTERVIEWED`` when the lifecycle allows it. No score, evaluation or
    recommendation is read, and none can influence the outcome: selection and
    rejection remain separate, explicit recruiter decisions.
    """
    result = await service.complete(application_id, interview_id, body, current_user)
    await _commit_and_notify(
        db, background_tasks, application_id, result, "completed",
    )
    return result


# ── Phase 15: recruiter feedback + advance/reject from the interview stage ──


@router.post(
    "/applications/{application_id}/interviews/{interview_id}/feedback",
    response_model=ApplicationInterviewFeedback,
)
async def save_application_interview_feedback(
    application_id: uuid.UUID,
    interview_id: uuid.UUID,
    body: ApplicationInterviewFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Record the recruiter's manual technical feedback for an interview.

    Staff-only and scoped to the application in the path: the interview is looked
    up within that application, so a feedback write cannot reach another
    application's interview. The recruiter's ratings, recommendation and notes are
    stored verbatim on the interview's scorecard; nothing here selects, rejects or
    ranks the candidate.
    """
    return await service.save_feedback(
        application_id, interview_id, body, current_user,
    )


@router.get(
    "/applications/{application_id}/interviews/{interview_id}/feedback",
    response_model=ApplicationInterviewFeedback,
)
async def get_application_interview_feedback(
    application_id: uuid.UUID,
    interview_id: uuid.UUID,
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Read the manual feedback recorded for one interview, staff-only.

    The candidate never sees this projection: the scorecard is decision evidence
    for the hiring team, so this route requires staff access to the application's
    job and returns the same 404 for an unknown interview as for one on another
    application.
    """
    return await service.get_feedback(application_id, interview_id, current_user)


@router.post(
    "/applications/{application_id}/advance-to-hr",
    response_model=ApplicationInterviewStageActionResult,
)
async def advance_application_to_hr(
    application_id: uuid.UUID,
    body: ApplicationInterviewAdvanceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Advance a candidate to the HR interview stage.

    Makes the candidate *eligible* for an HR round and records who granted it. It
    changes no application status, invents no HR interview time, creates no room
    and makes no hire/reject decision: the HR interview still has to be scheduled
    explicitly and the final decision still belongs to the decision endpoints.
    """
    result = await service.advance_to_hr(application_id, body, current_user)
    app_row = await db.get(JobApplication, application_id)
    if app_row:
        job = await db.get(Job, app_row.job_id)
        candidate = await db.get(User, app_row.candidate_id)
        candidate_name = candidate.full_name if candidate else "Candidate"
        job_title = job.title if job else "the position"
        hr_interviewers = await service.get_hr_interviewers(application_id, current_user)
        for hr_user in hr_interviewers:
            queue_staff_application_notification(
                background_tasks,
                user_id=uuid.UUID(str(hr_user.id)),
                application_id=application_id,
                event="advanced_to_hr",
                title="Candidate Advanced to HR",
                message=f"{candidate_name} has completed the recruiter round for {job_title} and is eligible for HR interview scheduling.",
                action_link=f"/hr/applications/{application_id}",
            )
    await db.commit()
    return result


@router.post(
    "/applications/{application_id}/reject",
    response_model=ApplicationInterviewStageActionResult,
)
async def reject_application_from_interview(
    application_id: uuid.UUID,
    body: ApplicationInterviewRejectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Reject a candidate from the interview stage.

    Delegates to the Phase 8 decision service, so the status change, the
    structured rejection reason, the immutable history and the candidate-safe
    wording are identical to a rejection from the decision panel. The candidate
    notification is queued after the commit and runs in its own session, so a
    delivery failure cannot corrupt the committed decision.
    """
    result = await service.reject(application_id, body, current_user)
    app_row = await db.get(JobApplication, application_id)
    candidate_id = app_row.candidate_id if app_row else None
    await db.commit()
    if candidate_id is not None and result.candidate_message:
        queue_decision_notification(
            background_tasks,
            application_id=application_id,
            candidate_id=candidate_id,
            status=result.application_status,
            candidate_message=result.candidate_message,
        )
    return result


@router.get(
    "/applications/{application_id}/hr-interviewers",
    response_model=list[HRInterviewerOption],
)
async def get_hr_interviewers_for_application(
    application_id: uuid.UUID,
    service: ApplicationInterviewIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    """List eligible HR managers in the candidate's organization for HR interview assignment."""
    return await service.get_hr_interviewers(application_id, current_user)


async def _commit_and_notify(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    application_id: uuid.UUID,
    result: ApplicationInterviewScheduleResult,
    event: str,
) -> None:
    """Commit the interview change, then queue candidate and staff notifications.

    The candidate and interviewer identities and approved wording are resolved
    before the commit, while the session still holds the rows. Notifications
    are only queued once the business transaction has committed, and they run
    in their own sessions.
    """
    app_row = await db.get(JobApplication, application_id)
    candidate_id = app_row.candidate_id if app_row else None
    interview_row = await db.get(Interview, result.interview_id)
    recruiter_id = interview_row.recruiter_id if interview_row else None
    is_hr_stage = bool(interview_row and interview_row.stage == "hr")
    job = await db.get(Job, app_row.job_id) if app_row else None
    candidate_user = await db.get(User, candidate_id) if candidate_id else None
    candidate_name = candidate_user.full_name if candidate_user else "The candidate"
    job_title = job.title if job else "the position"
    message = await _candidate_stage_message(db, application_id, event)
    await db.commit()
    if candidate_id is not None:
        queue_interview_notification(
            background_tasks,
            interview_id=result.interview_id,
            candidate_id=candidate_id,
            event=event,  # type: ignore[arg-type]
            candidate_message=message,
        )
    if recruiter_id is not None and is_hr_stage:
        queue_staff_interview_notification(
            background_tasks,
            user_id=recruiter_id,
            interview_id=result.interview_id,
            event=event,
            title=f"HR Interview {event.capitalize()}",
            message=f"HR interview for {candidate_name} ({job_title}) has been {event}.",
            action_link=f"/interviews/{result.interview_id}/room",
        )


async def _candidate_stage_message(
    db: AsyncSession, application_id: uuid.UUID, event: str,
) -> str:
    """Approved candidate wording for an interview event.

    Built from the application status using the same reviewed projection the
    tracking and decision views use, so the notification, the tracking timeline
    and the decision response can never disagree. Recruiter prose is never used,
    and an internal cancellation reason never reaches this function.
    """
    from app.domain.application_decision_schemas import candidate_status_message
    from app.domain.enums import ApplicationStatus

    app_row = await db.get(JobApplication, application_id)
    if app_row is None:
        return "Your interview has been updated."
    job = await db.get(Job, app_row.job_id)
    job_title = job.title if job else "this role"
    status = ApplicationStatus.from_value(app_row.status) or ApplicationStatus.APPLIED

    if event == "cancelled":
        return (
            f"Your interview for {job_title} has been cancelled. The hiring team "
            "will contact you about next steps."
        )
    if event == "rescheduled":
        return (
            f"Your interview for {job_title} has been rescheduled. Please check "
            "your application for the updated time."
        )
    if event == "completed":
        return (
            candidate_status_message(status, job_title, None)
            or "Your interview has been completed. The hiring team will be in touch."
        )
    return candidate_status_message(
        ApplicationStatus.INTERVIEW_SCHEDULED, job_title, None,
    ) or "An interview has been scheduled for your application."
