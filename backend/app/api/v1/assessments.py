"""Phase 12 – Assessment Platform API endpoints.

Every endpoint is protected by the platform RBAC layer:
* hr / recruiter   – build, browse and analyze assessments
* candidate        – take assessments, run code, view own results
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.domain.application_assessment_schemas import (
    ApplicationAssessmentAssignRequest,
    ApplicationAssessmentAssignResult,
    ApplicationAssessmentCreateRequest,
    ApplicationAssessmentCreateResult,
    ApplicationAssessmentEvidence,
    ApplicationAssessmentOptionsWithAttempts,
    ApplicationAssessmentRescheduleRequest,
    CandidateApplicationAssessmentView,
)
from app.domain.assessment_schemas import (
    AnalyticsResponse,
    AnswerResultResponse,
    AnswerSubmitRequest,
    AssessmentCreateRequest,
    AssessmentListResponse,
    AssessmentResponse,
    AttemptListItem,
    AttemptListResponse,
    AttemptStartResponse,
    CodeRunRequest,
    CodeRunResponse,
    IntegrityEventRequest,
    ResultResponse,
    TestResultOut,
)
from app.domain.enums import AttemptStatus, AuditEventType
from app.domain.models import CandidateAssessment, Job, JobApplication, User
from app.services.assessment.application_assessment_notification import (
    queue_assessment_notification,
)
from app.services.assessment.application_assessment_service import (
    ApplicationAssessmentIntegrationService,
)
from app.services.assessment.assessment_service import AssessmentService
from app.services.screening.access import ApplicationAccessDeniedError

router = APIRouter(prefix="/assessments", tags=["assessments"])

# Reviewed candidate wording for an assignment. It states the task and nothing
# more: no due date is invented (the attempt has no deadline until the candidate
# starts it, when the duration clock begins), and no hiring language appears,
# because an assignment is not a decision.
#
# The schedule sentence is included only when the recruiter actually chose one.
# "Scheduled for <time>" is omitted rather than defaulted when there is no
# ``scheduled_for``, because the alternative is telling the candidate a time
# nobody picked.
CANDIDATE_ASSIGNED_MESSAGE = (
    "{title} has been scheduled for you.{schedule}{job} "
    "Open it from your assessments to begin."
)
# Reports that the time moved. Says the new time and nothing about why, and names
# no verdict: a reschedule is a change of plan, not a change of opinion about the
# candidate.
CANDIDATE_RESCHEDULED_MESSAGE = (
    "{title} has been rescheduled.{schedule}{job} "
    "Open it from your assessments to begin."
)
# Reports that the result is available and nothing more. Deliberately does not
# say passed or failed: the assessment's own threshold is the candidate's to see
# on the result page, and a notification is the wrong place to frame it as an
# outcome, because it is not one.
CANDIDATE_COMPLETED_MESSAGE = (
    "Your assessment has been submitted and your result is now available."
)


def _schedule_sentence(scheduled_for: datetime | None) -> str:
    """The "Scheduled for ..." clause, or empty when no time was chosen.

    The time is rendered server-side rather than sent as a preformatted string so
    the notification and the candidate's page quote the same moment, and the
    timezone is stated because the value is stored in UTC and the candidate may
    be reading it from anywhere.
    """
    if scheduled_for is None:
        return ""
    moment = scheduled_for.astimezone(timezone.utc)
    return f" Scheduled for {moment.strftime('%d %b %Y, %H:%M UTC')}."


def _job_sentence(job_title: str | None) -> str:
    """The "For <job>" clause, or empty when the application has no job title."""
    return f" For {job_title}." if job_title else ""


def _get_service(db: AsyncSession = Depends(get_db)) -> AssessmentService:
    return AssessmentService(db)


def _get_application_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationAssessmentIntegrationService:
    return ApplicationAssessmentIntegrationService(db)


def _map_error(e: ValueError) -> HTTPException:
    msg = str(e)
    status = {
        "NO_ATTEMPTS_REMAINING": 409,
        "ALREADY_ANSWERED": 409,
    }.get(msg, None)
    if msg.startswith("ATTEMPT_"):
        status = 409
    elif msg in {"Assessment not found", "Attempt not found", "Question not found", "Job not found"}:
        status = 404
    return HTTPException(status_code=status or 400, detail=msg)


# ═══ Recruiter: build & browse ══════════════════════════════════


@router.post("/generate", response_model=AssessmentResponse)
async def generate_assessment(
    body: AssessmentCreateRequest,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    try:
        assessment = await service.create_assessment(current_user.id, body)
    except ValueError as e:
        raise _map_error(e)
    items, total = await service.list_assessments()
    out = next(a for a in items if a["id"] == assessment.id)
    return AssessmentResponse(**out)


@router.get("", response_model=AssessmentListResponse)
async def list_assessments(
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    items, total = await service.list_assessments()
    return AssessmentListResponse(items=[AssessmentResponse(**a) for a in items], total=total)


@router.get("/me", response_model=AttemptListResponse)
async def my_attempts(
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    data = await service.my_attempts(current_user.id)
    return AttemptListResponse(items=[AttemptListItem(**i) for i in data["items"]], total=data["total"])


# ═══ Phase 12: run an assessment from an application ══════════════
#
# Registered before every parameter-prefixed route below. These paths all begin
# with the literal segment ``applications``, so they cannot be captured by
# ``/{assessment_id}`` or ``/{attempt_id}`` -- but putting them first means that
# stays true by construction rather than by counting path segments, which is the
# kind of thing that breaks silently when a route is added later.
#
# The application in the path is the only identity input. Job, candidate and
# organization are derived from the authorized application server-side, so a
# recruiter cannot post an assessment against a different candidate or another
# tenant's job, and a candidate cannot read another candidate's result.


@router.get(
    "/applications/{application_id}/assessment",
    response_model=CandidateApplicationAssessmentView,
)
async def get_my_application_assessment(
    application_id: uuid.UUID,
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("candidate")),
):
    """The assessment on one of my applications, as the candidate may see it.

    An explicit allowlist: no recruiter identity, no notes, no protected
    attributes, and none of the platform's internal ``recommendation`` or
    ``readiness_level`` labels, which read as a hiring verdict and belong to the
    recruiter.

    "No such application" and "not your application" both return 404, so
    application ids cannot be probed for existence.
    """
    try:
        return await service.get_candidate_view(application_id, current_user.id)
    except (ApplicationAccessDeniedError, NotFoundError) as exc:
        # One indistinguishable 404 for both, per the IDOR contract.
        raise HTTPException(status_code=404, detail="Application not found") from exc


@router.get(
    "/applications/{application_id}/assessment/options",
    response_model=ApplicationAssessmentOptionsWithAttempts,
)
async def get_application_assessment_options(
    application_id: uuid.UUID,
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Which assessments this recruiter may assign here, and whether at all.

    Server-authoritative, so the UI never offers an action the backend would
    reject and never re-implements the eligibility rules. The catalog is filtered
    in SQL to this application's job plus job-agnostic assessments, so a row the
    browser could not have used is never sent in the first place.
    """
    return await service.get_options(application_id, current_user)


@router.post(
    "/applications/{application_id}/assessment/assign",
    response_model=ApplicationAssessmentAssignResult,
    status_code=201,
)
async def assign_application_assessment(
    application_id: uuid.UUID,
    body: ApplicationAssessmentAssignRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Assign -- or schedule -- an assessment to an application.

    The job, candidate and organization all come from the application in the
    path, and the body carries an ``assessment_id`` and a ``scheduled_for`` and
    nothing else (``extra="forbid"``), so participants cannot be forged.
    Requires a shortlisted, interview-scheduled or interviewed application.

    Idempotent for a repeat: while an attempt for the same assessment is still
    live, a second request that names no time -- or the time already stored --
    re-reads it and reports ``already_assigned`` rather than creating a second
    open attempt, so a double-click or a retry is harmless.

    A repeat that names a **different** time is a reschedule, and updates that one
    existing assignment rather than creating a second. Two live attempts at one
    assessment would leave the candidate holding two of something they asked to
    move, so the update is the only outcome that keeps the invariant.

    The application status is deliberately unchanged. An assessment is evidence
    the recruiter reads before deciding, so a passing score must not shortlist
    and a failing one must not reject; the decision stays an explicit recruiter
    action.
    """
    result = await service.assign(application_id, body, current_user)
    # The candidate id, the job title and the approved wording are resolved before
    # the commit, while the session still holds the rows. The notification is
    # queued only after the business transaction commits, and runs in its own
    # session, so a delivery failure can neither roll back nor appear to fail the
    # assignment.
    candidate_id = await _attempt_candidate_id(db, result.attempt_id)
    job_title = await _application_job_title(db, application_id)
    await db.commit()
    # Exactly one notification per business event. A reschedule is a different
    # event from the original assignment and has its own dedupe key, so the
    # candidate is told about the new time; a no-op repeat is not an event at all
    # and is skipped.
    if candidate_id is not None and result.rescheduled:
        _queue_scheduled_notification(
            background_tasks,
            attempt_id=result.attempt_id,
            candidate_id=candidate_id,
            event="rescheduled",
            title=result.assessment_title,
            scheduled_for=result.scheduled_for,
            job_title=job_title,
            action_link=result.assessment_link,
        )
    elif candidate_id is not None and not result.already_assigned:
        _queue_scheduled_notification(
            background_tasks,
            attempt_id=result.attempt_id,
            candidate_id=candidate_id,
            event="assigned",
            title=result.assessment_title,
            scheduled_for=result.scheduled_for,
            job_title=job_title,
            action_link=result.assessment_link,
        )
    return result


@router.post(
    "/applications/{application_id}/assessment/create-and-assign",
    response_model=ApplicationAssessmentCreateResult,
    status_code=201,
)
async def create_and_assign_application_assessment(
    application_id: uuid.UUID,
    body: ApplicationAssessmentCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Create a candidate-specific assessment and assign it in one action."""
    result = await service.create_and_assign(application_id, body, current_user)

    candidate_id = await _attempt_candidate_id(db, result.assignment.attempt_id)
    job_title = await _application_job_title(db, application_id)
    await db.commit()

    if candidate_id is not None and not result.assignment.already_assigned:
        _queue_scheduled_notification(
            background_tasks,
            attempt_id=result.assignment.attempt_id,
            candidate_id=candidate_id,
            event="assigned",
            title=result.assignment.assessment_title,
            scheduled_for=result.assignment.scheduled_for,
            job_title=job_title,
            action_link=result.assignment.assessment_link,
        )

    return result


@router.post(
    "/applications/{application_id}/assessment/attempts/{attempt_id}/reschedule",
    response_model=ApplicationAssessmentAssignResult,
)
async def reschedule_application_assessment(
    application_id: uuid.UUID,
    attempt_id: uuid.UUID,
    body: ApplicationAssessmentRescheduleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Move an existing assignment to a new date and time.

    Updates the attempt rather than creating one. Rescheduling something a
    candidate already holds is a change to a plan, not a new task, and minting a
    second attempt would reset their attempt counter and leave two open attempts
    at one assessment.

    Both ids are verified: the attempt must belong to the application in the path,
    and the application to the actor. A mismatched attempt answers 404 rather than
    403, so an attempt id cannot be probed for existence across applications or
    tenants.

    A finished attempt is refused. Its timing is part of the evidence it produced
    and its duration clock has usually already run, so the way to give a candidate
    another go at the same assessment is a new attempt, not a moved one.
    """
    result = await service.reschedule(
        application_id, attempt_id, body, current_user,
    )
    candidate_id = await _attempt_candidate_id(db, result.attempt_id)
    job_title = await _application_job_title(db, application_id)
    await db.commit()
    # Guarded the same way the assign route is. The service reports a re-post of
    # the time already stored as ``rescheduled=False`` rather than inventing a
    # change, and telling the candidate their assessment had moved when it had not
    # is worse than saying nothing.
    if candidate_id is not None and result.rescheduled:
        _queue_scheduled_notification(
            background_tasks,
            attempt_id=result.attempt_id,
            candidate_id=candidate_id,
            event="rescheduled",
            title=result.assessment_title,
            scheduled_for=result.scheduled_for,
            job_title=job_title,
            action_link=result.assessment_link,
        )
    return result


@router.get(
    "/applications/{application_id}/assessment/evidence",
    response_model=ApplicationAssessmentEvidence,
)
async def get_application_assessment_evidence(
    application_id: uuid.UUID,
    service: ApplicationAssessmentIntegrationService = Depends(
        _get_application_service,
    ),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    """Every assessment attempt recorded against one application, staff-only.

    Staff access uses the same job-owner-or-active-org-staff rule as the
    application decision endpoints, so a recruiter from another organization is
    refused rather than shown an empty list. Scores are ``None`` until an attempt
    is actually graded: an ungraded attempt and a scored zero are different
    facts and must not look alike.
    """
    result = await service.get_evidence(application_id, current_user)
    await _audit_evidence_view(
        service.session, current_user, application_id, result,
    )
    return result


async def _attempt_candidate_id(
    db: AsyncSession, attempt_id: uuid.UUID,
) -> uuid.UUID | None:
    """The candidate who owns an attempt, or ``None`` if it is already gone."""
    attempt = await db.get(CandidateAssessment, attempt_id)
    return attempt.candidate_id if attempt else None


async def _application_job_title(
    db: AsyncSession, application_id: uuid.UUID,
) -> str | None:
    """The job title behind an application, for the candidate's notification.

    Resolved from the application rather than accepted from the client, so the
    notification cannot be made to mention a job the candidate did not apply to.
    ``None`` is a real answer: the application may have no job, or the job row may
    be gone, and the clause is then omitted rather than filled with a blank.
    """
    title = await db.scalar(
        select(Job.title)
        .join(JobApplication, JobApplication.job_id == Job.id)
        .where(JobApplication.id == application_id)
    )
    return title


def _queue_scheduled_notification(
    background_tasks: BackgroundTasks,
    *,
    attempt_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: str,
    title: str,
    scheduled_for: datetime | None,
    job_title: str | None,
    action_link: str | None,
) -> None:
    """Build the approved candidate wording and queue it.

    One place builds the message for both the assign and the reschedule route, so
    the two cannot drift into telling the candidate different things about the
    same schedule.

    ``action_link`` is the link stored on the notification row, which is what lets
    the candidate's notification page open *this* assessment rather than guessing a
    destination from the notification type.
    """
    template = (
        CANDIDATE_RESCHEDULED_MESSAGE
        if event == "rescheduled"
        else CANDIDATE_ASSIGNED_MESSAGE
    )
    queue_assessment_notification(
        background_tasks,
        attempt_id=attempt_id,
        candidate_id=candidate_id,
        event=event,
        candidate_message=template.format(
            title=title,
            schedule=_schedule_sentence(scheduled_for),
            job=_job_sentence(job_title),
        ),
        action_link=action_link,
    )


def queue_assignment_notification(
    background_tasks: BackgroundTasks,
    *,
    attempt_id: uuid.UUID,
    candidate_id: uuid.UUID,
    title: str,
    scheduled_for: datetime | None,
    job_title: str | None,
    action_link: str | None,
) -> None:
    """Queue the approved "assessment assigned" notification for one candidate.

    Public entry point for the job-scoped bulk assignment route, so a batch queues
    the exact same message the single-application route queues -- from the same
    templates -- instead of a second implementation that could drift.
    """
    _queue_scheduled_notification(
        background_tasks,
        attempt_id=attempt_id,
        candidate_id=candidate_id,
        event="assigned",
        title=title,
        scheduled_for=scheduled_for,
        job_title=job_title,
        action_link=action_link,
    )


async def _audit_evidence_view(
    db: AsyncSession,
    actor: User,
    application_id: uuid.UUID,
    evidence: ApplicationAssessmentEvidence,
) -> None:
    """Record that staff opened the detailed assessment evidence.

    A read, but a sensitive one: it is how "who reviewed this candidate's
    assessment" becomes answerable. Uses the shared :class:`AuditService` and the
    Phase 12 event type, and never records a score -- the point is the access,
    not the data.
    """
    if not evidence.attempts:
        return
    from app.services.audit_service import AuditService

    await AuditService(db).log(
        AuditEventType.ASSESSMENT_EVIDENCE_VIEWED,
        action="view_assessment_evidence",
        user_id=actor.id,
        resource_type="job_application",
        resource_id=str(application_id),
        details={
            "attempt_count": evidence.attempt_count,
            "completed_count": evidence.completed_count,
            "candidate_id": str(evidence.candidate_id),
        },
    )


async def _audit_start(
    db: AsyncSession,
    actor: User,
    attempt_id: uuid.UUID,
    assessment_id: uuid.UUID,
) -> None:
    """Record that a candidate started an attempt.

    Logs the application link when there is one, so the trail shows which
    application the work was for. No scores, no answers.
    """
    from app.services.audit_service import AuditService

    attempt = await db.get(CandidateAssessment, attempt_id)
    await AuditService(db).log(
        AuditEventType.ASSESSMENT_STARTED,
        action="start_assessment",
        user_id=actor.id,
        resource_type="candidate_assessment",
        resource_id=str(attempt_id),
        details={
            "assessment_id": str(assessment_id),
            "application_id": str(attempt.application_id) if attempt and attempt.application_id else None,
            "resumed_assignment": bool(attempt and attempt.assigned_by),
        },
    )


# ═══ Candidate: take ════════════════════════════════════════════


@router.post("/{assessment_id}/start", response_model=AttemptStartResponse)
async def start_attempt(
    assessment_id: uuid.UUID,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    """Begin (or resume) an attempt.

    Phase 12 makes this dual-purpose by design: it starts a fresh self-chosen
    attempt *and* resumes an attempt a recruiter assigned to one of the
    candidate's applications, because the assignment is the same row in
    ``assigned`` state. The candidate's UI therefore has one Start button either
    way, and no new take-assessment screen or API is introduced.

    The start is audited because for an application-linked attempt it is the
    moment a recruiter-assigned task began -- the fact an expiry dispute turns
    on. The duration clock starts here, not at assignment.
    """
    try:
        payload = await service.start_attempt(assessment_id, current_user.id)
    except ValueError as e:
        raise _map_error(e)
    await _audit_start(
        service.session, current_user, payload["attempt_id"], assessment_id,
    )
    return AttemptStartResponse(**payload)


@router.get("/attempts/{attempt_id}", response_model=dict)
async def attempt_state(
    attempt_id: uuid.UUID,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        return await service.get_attempt_state(attempt_id, current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your attempt")
    except ValueError as e:
        raise _map_error(e)


@router.post("/{attempt_id}/answer", response_model=AnswerResultResponse)
async def submit_answer(
    attempt_id: uuid.UUID,
    body: AnswerSubmitRequest,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        data = await service.submit_answer(
            attempt_id, current_user.id, body.question_id, body.answer, body.time_taken_seconds,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your attempt")
    except ValueError as e:
        raise _map_error(e)
    from app.domain.assessment_schemas import EvaluationOut, QuestionPublic
    return AnswerResultResponse(
        answer_id=data["answer_id"],
        evaluation=EvaluationOut(**data["evaluation"]),
        correct_answer_revealed=data["correct_answer_revealed"],
        explanation=data["explanation"],
        next_question=QuestionPublic(**data["next_question"]) if data["next_question"] else None,
        questions_remaining=data["questions_remaining"],
        progress=data["progress"],
    )


@router.post("/{attempt_id}/code/run", response_model=CodeRunResponse)
async def run_code(
    attempt_id: uuid.UUID,
    body: CodeRunRequest,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        run = await service.run_code(attempt_id, current_user.id, body.question_id, body.language, body.code)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your attempt")
    except ValueError as e:
        raise _map_error(e)
    return CodeRunResponse(
        ok=run.get("ok", False),
        stdout=str(run.get("stdout", "")),
        stderr=str(run.get("stderr", "")),
        execution_time_ms=int(run.get("execution_time_ms", 0)),
        passed_count=int(run.get("passed_count", 0)),
        total_count=int(run.get("total_count", 0)),
        test_results=[TestResultOut(**t) for t in run.get("test_results", [])],
        timed_out=bool(run.get("timed_out")),
        sandbox_mode=str(run.get("sandbox_mode", "local")),
    )


@router.post("/{attempt_id}/code/submit", response_model=AnswerResultResponse)
async def submit_code(
    attempt_id: uuid.UUID,
    body: CodeRunRequest,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        data = await service.submit_answer(
            attempt_id, current_user.id, body.question_id,
            {"code": body.code, "language": body.language}, None,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your attempt")
    except ValueError as e:
        raise _map_error(e)
    from app.domain.assessment_schemas import EvaluationOut, QuestionPublic
    return AnswerResultResponse(
        answer_id=data["answer_id"],
        evaluation=EvaluationOut(**data["evaluation"]),
        correct_answer_revealed=False,
        explanation=None,
        next_question=QuestionPublic(**data["next_question"]) if data["next_question"] else None,
        questions_remaining=data["questions_remaining"],
        progress=data["progress"],
    )


@router.post("/{attempt_id}/integrity", response_model=dict)
async def integrity_event(
    attempt_id: uuid.UUID,
    body: IntegrityEventRequest,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        await service.record_integrity_event(attempt_id, current_user.id, body.event_type, body.detail)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your attempt")
    except ValueError as e:
        raise _map_error(e)
    return {"message": "Event recorded"}


async def _audit_submit(
    db: AsyncSession,
    actor: User,
    attempt_id: uuid.UUID,
    result: dict,
    application_id: uuid.UUID | None,
) -> None:
    """Record a submission.

    ``SUBMITTED`` for every attempt, since the submission is the auditable fact;
    ``COMPLETED`` only when a result was actually produced, so a resumed submit of
    an already-closed attempt is not logged as a second completion. The score is
    recorded, because the trail is meant to answer "what was submitted, by whom,
    for which application" and a score with no context is not much use. No
    answers, no free text.
    """
    from app.services.audit_service import AuditService

    audit = AuditService(db)
    attempt = await db.get(CandidateAssessment, attempt_id)
    details = {
        "assessment_id": str(attempt.assessment_id) if attempt else None,
        "application_id": str(application_id) if application_id else None,
        "status": result.get("status"),
        "overall_score": result.get("overall_score"),
    }
    await audit.log(
        AuditEventType.ASSESSMENT_SUBMITTED,
        action="submit_assessment",
        user_id=actor.id,
        resource_type="candidate_assessment",
        resource_id=str(attempt_id),
        details=details,
    )
    if result.get("status") == AttemptStatus.COMPLETED.value:
        await audit.log(
            AuditEventType.ASSESSMENT_COMPLETED,
            action="complete_assessment",
            user_id=actor.id,
            resource_type="candidate_assessment",
            resource_id=str(attempt_id),
            details=details,
        )


@router.post("/{attempt_id}/submit", response_model=ResultResponse)
async def finalize_attempt(
    attempt_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    """Grade and close an attempt.

    Grading is unchanged and still idempotent: ``finalize`` returns the existing
    result when the attempt is already closed, so a double submit cannot produce
    two results.

    Phase 12 adds the completion notification, for an application-linked attempt
    only. A self-started practice attempt gets none: the candidate pressed the
    button and is already looking at the result, so a notification would be
    noise. An assigned attempt is different -- it was work someone asked them to
    do, and the candidate may be on another page. Wording reports that the result
    is available and stops there; it names no verdict, because the recruiter's
    decision is the only verdict and this is not it.
    """
    try:
        # Ownership check without grading side effects.
        attempt = await service._own_attempt(attempt_id, current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your attempt")
    except ValueError as e:
        raise _map_error(e)

    was_open = attempt.status not in AttemptStatus.finished()
    result = await service.finalize(attempt_id)

    application_id = attempt.application_id
    await _audit_submit(
        service.session, current_user, attempt_id, result, application_id,
    )
    if application_id is not None and was_open:
        queue_assessment_notification(
            background_tasks,
            attempt_id=attempt_id,
            candidate_id=current_user.id,
            event="completed",
            candidate_message=CANDIDATE_COMPLETED_MESSAGE,
            # Straight to the result for this attempt, which is what the message
            # tells the candidate is available.
            action_link=f"/candidate/assessments/results/{attempt_id}",
        )
    return ResultResponse(**result)


@router.get("/{attempt_id}/result", response_model=ResultResponse)
async def get_result(
    attempt_id: uuid.UUID,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate", "hr", "recruiter")),
):
    result = await service.get_result(attempt_id)
    user_roles = {ur.role.name for ur in current_user.roles}
    if str(result["candidate_id"]) != str(current_user.id) and not (user_roles & {"hr_manager", "recruiter", "admin", "super_admin", "organization_admin"}):
        raise HTTPException(status_code=403, detail="Not your result")
    return ResultResponse(**result)


# ═══ Staff: detail & analytics ══════════════════════════════════


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    items, _total = await service.list_assessments()
    match = next((a for a in items if a["id"] == assessment_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return AssessmentResponse(**match)


@router.get("/{assessment_id}/analytics", response_model=AnalyticsResponse)
async def assessment_analytics(
    assessment_id: uuid.UUID,
    service: AssessmentService = Depends(_get_service),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    try:
        return AnalyticsResponse(**await service.analytics(assessment_id))
    except ValueError as e:
        raise _map_error(e)
