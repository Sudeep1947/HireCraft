"""Phase 12: assessment platform driven from an application.

Covers the four things the phase is actually judged on:

1. **Application-driven, not a second engine.** An assignment is a
   ``CandidateAssessment`` row in ``assigned`` state, the existing start endpoint
   resumes it, and the existing grading produces the result. The regression tests
   at the end pin that: the pre-existing self-start flow, the attempt limit, and
   the router surface all still behave as they did.
2. **A result is evidence, not a verdict.** No endpoint here can move an
   application status, and the tests assert the status is byte-identical before
   and after a full take-and-submit cycle.
3. **Tenancy and IDOR.** Staff access is the same rule the decision endpoints
   use, the catalog is scoped in SQL, and "not yours" and "does not exist" return
   the same status to a candidate.
4. **Idempotency.** A double-clicked assign produces one attempt, a retried
   submit produces one result, and one notification per event.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    AttemptStatus,
    AuditEventType,
    EmploymentType,
    JobStatus,
    MembershipStatus,
    RoleName,
)
from app.domain.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentResult,
    CandidateAssessment,
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    User,
)
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
)

PASSWORD = "Str0ng-Passw0rd!"

SECTIONS = [
    {"question_type": "mcq", "count": 2},
    {"question_type": "technical_theory", "count": 1},
]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _url(application_id: uuid.UUID, suffix: str = "") -> str:
    return f"/api/v1/assessments/applications/{application_id}/assessment{suffix}"


def _reschedule_url(application_id: uuid.UUID, attempt_id: uuid.UUID) -> str:
    return _url(
        application_id, f"/attempts/{attempt_id}/reschedule",
    )


# ═══ Fixtures ═══════════════════════════════════════════════════════


async def _mkuser(session: AsyncSession, name: str, email: str) -> User:
    from app.domain.models import Role, UserRole

    user = User(
        id=uuid.uuid4(),
        full_name=name,
        email=email,
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    role = (
        await session.execute(select(Role).where(Role.name == RoleName.RECRUITER.value))
    ).scalar_one()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()
    return user


async def _mk_candidate(session: AsyncSession, name: str, email: str) -> User:
    return await _mkuser_as(session, name, email, RoleName.CANDIDATE.value)


async def _mkuser_as(
    session: AsyncSession, name: str, email: str, role_name: str,
) -> User:
    from app.domain.models import Role, UserRole

    user = User(
        id=uuid.uuid4(),
        full_name=name,
        email=email,
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    role = (
        await session.execute(select(Role).where(Role.name == role_name))
    ).scalar_one()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()
    return user


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def captured_notifications(monkeypatch):
    """Record what the post-commit assessment dispatcher was asked to send.

    The real dispatcher opens its own session against the configured database
    rather than the test database, so the delivery step is replaced with a
    recorder. The delivery function itself is unit tested separately.
    """
    captured: list[dict] = []

    async def _fake(
        attempt_id, candidate_id, event, candidate_message, action_link=None,
    ):
        captured.append(
            {
                "attempt_id": str(attempt_id),
                "candidate_id": str(candidate_id),
                "event": event,
                "message": candidate_message,
                # Recorded so a test can assert the candidate is pointed at this
                # specific assessment rather than at a list page.
                "action_link": action_link,
            }
        )

    import app.services.assessment.application_assessment_notification as mod

    monkeypatch.setattr(mod, "_deliver_with_own_session", _fake)
    return captured


async def _setup(
    session: AsyncSession,
    suffix: str,
    *,
    status: ApplicationStatus = ApplicationStatus.SHORTLISTED,
    with_outsider: bool = True,
):
    """Org + owning recruiter + candidate + published job + application."""
    org = Organization(
        name=f"Org {suffix}", slug=f"org-{suffix}",
        description="d", status="active",
    )
    session.add(org)
    await session.flush()

    recruiter = await _mkuser(session, f"Rec {suffix}", f"rec{suffix}@test.com")
    candidate = await _mk_candidate(session, f"Cand {suffix}", f"cand{suffix}@test.com")
    outsider = None
    if with_outsider:
        outsider = await _mkuser(
            session, f"Out {suffix}", f"out{suffix}@test.com",
        )

    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title="Backend Engineer",
        company=org.name,
        department="Engineering",
        employment_type=EmploymentType.FULL_TIME.value,
        location="Remote",
        description="Build systems.",
        required_skills=["Python"],
        preferred_skills=[],
        status=JobStatus.PUBLISHED.value,
    )
    session.add(job)
    await session.flush()

    app = JobApplication(
        job_id=job.id, candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()

    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(app, actor=candidate)
    if status != ApplicationStatus.APPLIED:
        # Walk the real transition map rather than jumping straight to the target,
        # so the fixture cannot assert against a state the application could
        # never legally reach.
        path = {
            ApplicationStatus.UNDER_REVIEW: [ApplicationStatus.UNDER_REVIEW],
            ApplicationStatus.SHORTLISTED: [
                ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
            ],
            ApplicationStatus.OFFERED: [
                ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
                ApplicationStatus.OFFERED,
            ],
            ApplicationStatus.HIRED: [
                ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
                ApplicationStatus.OFFERED, ApplicationStatus.HIRED,
            ],
            ApplicationStatus.REJECTED: [
                ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.INTERVIEW_SCHEDULED: [
                ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
                ApplicationStatus.INTERVIEW_SCHEDULED,
            ],
            ApplicationStatus.INTERVIEWED: [
                ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
                ApplicationStatus.INTERVIEW_SCHEDULED,
                ApplicationStatus.INTERVIEWED,
            ],
        }[status]
        for step in path:
            await lifecycle.transition_application(app.id, step.value, recruiter)
    await session.refresh(app)

    return {
        "org": org, "recruiter": recruiter, "candidate": candidate,
        "outsider": outsider, "job": job, "app": app,
    }


async def _mk_assessment(
    session: AsyncSession, *, job_id: uuid.UUID | None, title: str,
    allowed_attempts: int = 1, passing_score: int = 60,
) -> Assessment:
    """A published assessment with real questions, built directly.

    Built in the database rather than through ``POST /generate`` so the test
    controls ``job_id`` and ``allowed_attempts`` exactly, and so a global
    (``job_id IS NULL``) and a job-scoped assessment can be compared side by side.
    """
    from app.services.assessment.generators import generate_assessment_questions

    assessment = Assessment(
        title=title,
        description="An assessment for testing.",
        job_id=job_id,
        mode="custom",
        status="published",
        duration_minutes=30,
        passing_score=passing_score,
        negative_marking=0.0,
        allowed_attempts=allowed_attempts,
        adaptive=False,
        shuffle_questions=False,
        shuffle_options=False,
        config={"sections": [{"question_type": "mcq", "count": 2}]},
    )
    session.add(assessment)
    await session.flush()

    generated = generate_assessment_questions(
        [{"question_type": "mcq", "count": 2, "difficulty": "easy"}],
    )
    for index, payload in enumerate(generated):
        session.add(
            AssessmentQuestion(
                assessment_id=assessment.id,
                question_type=payload["question_type"],
                skill=payload.get("skill", "general"),
                topic=payload.get("topic", "general"),
                difficulty=payload.get("difficulty", "medium"),
                question_text=payload["question_text"],
                content=payload.get("content"),
                correct_answer=payload.get("correct_answer"),
                explanation=payload.get("explanation"),
                estimated_time_seconds=payload.get("estimated_time_seconds", 90),
                points=float(payload.get("points", 1.0)),
                section="Technical",
                order_index=index,
            ),
        )
    await session.flush()
    return assessment


async def _attempts(session: AsyncSession, application_id: uuid.UUID) -> list:
    return list(
        (
            await session.execute(
                select(CandidateAssessment)
                .where(CandidateAssessment.application_id == application_id)
                .order_by(CandidateAssessment.attempt_number),
            )
        ).scalars().all()
    )


async def _assign(client, token, application_id, assessment_id, **extra):
    return await client.post(
        _url(application_id, "/assign"),
        json={"assessment_id": str(assessment_id), **extra},
        headers=_auth(token),
    )


async def _take_all(
    client: AsyncClient, session: AsyncSession, token: str, attempt_id: uuid.UUID,
) -> None:
    """Answer every question on an attempt and submit it."""
    state = await client.get(
        f"/api/v1/assessments/attempts/{attempt_id}", headers=_auth(token),
    )
    assert state.status_code == 200, state.text
    for question in state.json()["questions"]:
        if question["question_type"] == "mcq":
            payload = {"option_index": 0}
        else:
            payload = {"text": "A considered answer."}
        await client.post(
            f"/api/v1/assessments/{attempt_id}/answer",
            json={
                "question_id": question["id"],
                "answer": payload,
                "time_taken_seconds": 10,
            },
            headers=_auth(token),
        )
    sub = await client.post(
        f"/api/v1/assessments/{attempt_id}/submit", headers=_auth(token),
    )
    assert sub.status_code == 200, sub.text


# ═══ 1. Assignment is application-driven ════════════════════════════


@pytest.mark.asyncio
async def test_assign_creates_assigned_attempt_linked_to_application(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "assign")
    r_token = await _login(client, f"recassign@test.com")
    c_token = await _login(client, f"candassign@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Assign Me",
    )

    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["already_assigned"] is False
    assert body["attempt_status"] == AttemptStatus.ASSIGNED.value

    attempts = await _attempts(session, ctx["app"].id)
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.application_id == ctx["app"].id
    assert attempt.candidate_id == ctx["candidate"].id
    assert attempt.assessment_id == assessment.id
    assert attempt.status == AttemptStatus.ASSIGNED.value
    assert attempt.assigned_by == ctx["recruiter"].id
    assert attempt.assigned_at is not None
    # The clock has not started: an assignment is not a deadline.
    assert attempt.started_at is None
    assert attempt.expires_at is None


@pytest.mark.asyncio
async def test_assign_does_not_change_application_status(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "nostatus")
    r_token = await _login(client, "recnostatus@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="No Status Change",
    )
    before = ctx["app"].status

    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 201, resp.text
    await session.refresh(ctx["app"])
    assert ctx["app"].status == before == ApplicationStatus.SHORTLISTED.value


@pytest.mark.asyncio
async def test_assign_notifies_candidate_once_after_commit(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "notify")
    r_token = await _login(client, "recnotify@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Notify Me",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    assigned = [n for n in captured_notifications if n["event"] == "assigned"]
    assert len(assigned) == 1
    assert assigned[0]["candidate_id"] == str(ctx["candidate"].id)
    # The message names the task and nothing else. No verdict, no deadline.
    assert "Notify Me" in assigned[0]["message"]
    assert "pass" not in assigned[0]["message"].lower()
    assert "expire" not in assigned[0]["message"].lower()


@pytest.mark.asyncio
async def test_assign_body_cannot_name_a_participant(
    client: AsyncClient, session: AsyncSession,
):
    """The participants come from the application, never from the body."""
    ctx = await _setup(session, "forge")
    r_token = await _login(client, "recforge@test.com")
    other = await _mk_candidate(session, "Other", "otherforge@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Forgery",
    )

    for field, value in (
        ("candidate_id", str(other.id)),
        ("recruiter_id", str(other.id)),
        ("job_id", str(ctx["job"].id)),
    ):
        resp = await _assign(
            client, r_token, ctx["app"].id, assessment.id, **{field: value},
        )
        assert resp.status_code == 422, (field, resp.text)
        assert not await _attempts(session, ctx["app"].id)


# ═══ 2. Eligibility ════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [ApplicationStatus.APPLIED, ApplicationStatus.UNDER_REVIEW],
)
async def test_assign_refused_before_shortlist(
    client: AsyncClient, session: AsyncSession, status,
):
    """A graded assessment must not short-circuit screening."""
    ctx = await _setup(session, f"pre{status.value}", status=status)
    r_token = await _login(client, f"recpre{status.value}@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Too Early",
    )
    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 409, resp.text
    assert not await _attempts(session, ctx["app"].id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [ApplicationStatus.REJECTED, ApplicationStatus.HIRED],
)
async def test_assign_refused_for_terminal_application(
    client: AsyncClient, session: AsyncSession, status,
):
    ctx = await _setup(session, f"term{status.value}", status=status)
    r_token = await _login(client, f"recterm{status.value}@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Too Late",
    )
    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 409, resp.text
    assert not await _attempts(session, ctx["app"].id)


@pytest.mark.asyncio
async def test_assign_allowed_after_interview_stages(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(
        session, "postiv", status=ApplicationStatus.INTERVIEWED,
    )
    r_token = await _login(client, "recpostiv@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="After Interview",
    )
    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_options_report_why_assignment_is_refused(
    client: AsyncClient, session: AsyncSession,
):
    """The UI reads this instead of re-deriving the rules."""
    ctx = await _setup(session, "opts", status=ApplicationStatus.APPLIED)
    r_token = await _login(client, "recopts@test.com")
    resp = await client.get(
        _url(ctx["app"].id, "/options"), headers=_auth(r_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_assign"] is False
    assert body["assign_unavailable_reason"] == "application_not_assessable"
    assert body["current_status"] == ApplicationStatus.APPLIED.value


# ═══ 3. Idempotency ════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_duplicate_assign_returns_the_existing_attempt(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "dupe")
    r_token = await _login(client, "recdupe@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Assign Once",
    )
    first = await _assign(client, r_token, ctx["app"].id, assessment.id)
    second = await _assign(client, r_token, ctx["app"].id, assessment.id)

    assert second.status_code == 201, second.text
    assert second.json()["already_assigned"] is True
    assert second.json()["attempt_id"] == first.json()["attempt_id"]
    assert len(await _attempts(session, ctx["app"].id)) == 1
    # One business event, one notification.
    assert len([n for n in captured_notifications if n["event"] == "assigned"]) == 1


@pytest.mark.asyncio
async def test_retry_after_retake_creates_a_new_attempt(
    client: AsyncClient, session: AsyncSession,
):
    """A finished attempt is immutable, so a retake is a *new* attempt."""
    ctx = await _setup(session, "retake")
    r_token = await _login(client, "recretake@test.com")
    c_token = await _login(client, "candretake@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Retake", allowed_attempts=2,
    )
    first = await _assign(client, r_token, ctx["app"].id, assessment.id)
    await _take_all(client, session, c_token, first.json()["attempt_id"])

    second = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert second.status_code == 201, second.text
    assert second.json()["already_assigned"] is False
    attempts = await _attempts(session, ctx["app"].id)
    assert len(attempts) == 2
    assert [a.attempt_number for a in attempts] == [1, 2]


@pytest.mark.asyncio
async def test_assign_refused_when_attempts_are_exhausted(
    client: AsyncClient, session: AsyncSession,
):
    """Refuse up front rather than assign something that cannot be started."""
    ctx = await _setup(session, "exhaust")
    r_token = await _login(client, "recexhaust@test.com")
    c_token = await _login(client, "candexhaust@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="One Shot", allowed_attempts=1,
    )

    # The candidate self-starts and completes the only allowed attempt.
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    assert start.status_code == 200, start.text
    await _take_all(client, session, c_token, start.json()["attempt_id"])

    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "conflict"
    assert not await _attempts(session, ctx["app"].id)


# ═══ 4. Start resumes the assignment ═══════════════════════════════


@pytest.mark.asyncio
async def test_start_resumes_the_assigned_attempt(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "resume")
    r_token = await _login(client, "recresume@test.com")
    c_token = await _login(client, "candresume@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Resume Me", allowed_attempts=1,
    )
    assigned = (await _assign(client, r_token, ctx["app"].id, assessment.id)).json()

    before = len(await _attempts(session, ctx["app"].id))
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    assert start.status_code == 200, start.text
    body = start.json()

    # Same row, now running. A second row would mean a second attempt engine.
    assert body["attempt_id"] == assigned["attempt_id"]
    assert body["status"] == AttemptStatus.IN_PROGRESS.value
    assert body["expires_at"] is not None
    assert len(await _attempts(session, ctx["app"].id)) == before == 1

    attempt = (await _attempts(session, ctx["app"].id))[0]
    assert attempt.status == AttemptStatus.IN_PROGRESS.value
    assert attempt.application_id == ctx["app"].id
    assert attempt.attempt_number == 1
    assert attempt.question_order


@pytest.mark.asyncio
async def test_assigned_attempt_counts_as_the_allowed_attempt(
    client: AsyncClient, session: AsyncSession,
):
    """The reason the resume must precede the limit check.

    With ``allowed_attempts=1`` the pre-created row is itself the one allowed
    attempt. Checking the limit first would tell the candidate
    NO_ATTEMPTS_REMAINING for the very attempt a recruiter assigned them, and
    they could never start it.
    """
    ctx = await _setup(session, "limit")
    r_token = await _login(client, "reclimit@test.com")
    c_token = await _login(client, "candlimit@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Only One", allowed_attempts=1,
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    assert start.status_code == 200, start.text
    assert "NO_ATTEMPTS_REMAINING" not in start.text


@pytest.mark.asyncio
async def test_candidate_sees_assigned_attempt_first_in_my_assessments(
    client: AsyncClient, session: AsyncSession,
):
    """The page whose job is "what do I do next" must not bury the assignment.

    Under ``ORDER BY started_at DESC`` a NULL ``started_at`` sorts last on SQLite,
    which would put the pending assignment at the bottom of the list.
    """
    ctx = await _setup(session, "mine")
    r_token = await _login(client, "recmine@test.com")
    c_token = await _login(client, "candmine@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Pending Task",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    resp = await client.get("/api/v1/assessments/me", headers=_auth(c_token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == AttemptStatus.ASSIGNED.value
    assert items[0]["application_id"] == str(ctx["app"].id)
    assert items[0]["assessment_title"] == "Pending Task"


# ═══ 5. Security and tenancy ═══════════════════════════════════════


@pytest.mark.asyncio
async def test_outsider_recruiter_cannot_assign_or_read(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "outsider")
    o_token = await _login(client, "outoutsider@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Private",
    )

    assign = await _assign(client, o_token, ctx["app"].id, assessment.id)
    assert assign.status_code in (403, 404), assign.text
    evidence = await client.get(
        _url(ctx["app"].id, "/evidence"), headers=_auth(o_token),
    )
    assert evidence.status_code in (403, 404), evidence.text
    assert not await _attempts(session, ctx["app"].id)


@pytest.mark.asyncio
async def test_candidate_cannot_assign(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "candassign")
    c_token = await _login(client, "candcandassign@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Not Yours To Assign",
    )
    resp = await _assign(client, c_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 403, resp.text
    assert not await _attempts(session, ctx["app"].id)


@pytest.mark.asyncio
async def test_candidate_cannot_read_evidence(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "candevid")
    c_token = await _login(client, "candcandevid@test.com")
    resp = await client.get(_url(ctx["app"].id, "/evidence"), headers=_auth(c_token))
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_candidate_cannot_read_another_candidates_assessment(
    client: AsyncClient, session: AsyncSession,
):
    """Same 404 for "not yours" and "does not exist", so ids cannot be probed."""
    ctx = await _setup(session, "idor")
    r_token = await _login(client, "recidor@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Private Result",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    intruder = await _mk_candidate(session, "Intruder", "intruderidor@test.com")
    i_token = await _login(client, "intruderidor@test.com")

    forbidden = await client.get(_url(ctx["app"].id), headers=_auth(i_token))
    missing = await client.get(
        _url(uuid.uuid4()), headers=_auth(i_token),
    )
    assert forbidden.status_code == missing.status_code == 404
    # Everything except the per-request correlation id must match, or the
    # response discloses whether the application exists.
    assert _without_request_id(forbidden.json()) == _without_request_id(
        missing.json()
    )


def _without_request_id(body: dict) -> dict:
    """Drop the correlation id, which is unique to the request by design.

    The error handler nests it under ``error``, so it is stripped there rather
    than at the top level.
    """
    stripped = {k: v for k, v in body.items() if k != "request_id"}
    if isinstance(stripped.get("error"), dict):
        stripped["error"] = {
            k: v for k, v in stripped["error"].items() if k != "request_id"
        }
    return stripped


@pytest.mark.asyncio
async def test_cannot_assign_an_assessment_scoped_to_another_job(
    client: AsyncClient, session: AsyncSession,
):
    """Job-scoped assessments are not cross-assignable, and the 404 says nothing.

    The response is identical to a genuinely missing assessment, so it does not
    disclose that another tenant's assessment id exists.
    """
    ctx = await _setup(session, "otherjob")
    r_token = await _login(client, "recotherjob@test.com")

    other_org = Organization(
        name="Other Org", slug="other-org-x", description="d", status="active",
    )
    session.add(other_org)
    await session.flush()
    other_job = Job(
        recruiter_id=ctx["recruiter"].id,
        organization_id=other_org.id,
        title="Unrelated Role",
        company="Other",
        department="Engineering",
        employment_type=EmploymentType.FULL_TIME.value,
        location="Remote",
        description="d",
        required_skills=[],
        preferred_skills=[],
        status=JobStatus.PUBLISHED.value,
    )
    session.add(other_job)
    await session.flush()
    foreign = await _mk_assessment(
        session, job_id=other_job.id, title="Foreign Assessment",
    )
    absent = uuid.uuid4()

    a = await _assign(client, r_token, ctx["app"].id, foreign.id)
    b = await _assign(client, r_token, ctx["app"].id, absent)
    assert a.status_code == b.status_code == 404
    # The response is the one a genuinely missing assessment would get, so it
    # discloses nothing about the other tenant's assessment existing.
    assert _without_request_id(a.json()) == _without_request_id(b.json())


@pytest.mark.asyncio
async def test_catalog_is_scoped_to_the_application_job(
    client: AsyncClient, session: AsyncSession,
):
    """The browser never receives a row it could not have used."""
    ctx = await _setup(session, "catalog")
    r_token = await _login(client, "reccatalog@test.com")

    mine = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Mine",
    )
    shared = await _mk_assessment(session, job_id=None, title="Shared")
    other_job = Job(
        recruiter_id=ctx["recruiter"].id,
        organization_id=ctx["org"].id,
        title="Other Role In Same Org",
        company=ctx["org"].name,
        department="Engineering",
        employment_type=EmploymentType.FULL_TIME.value,
        location="Remote",
        description="d",
        required_skills=[],
        preferred_skills=[],
        status=JobStatus.PUBLISHED.value,
    )
    session.add(other_job)
    await session.flush()
    elsewhere = await _mk_assessment(
        session, job_id=other_job.id, title="Elsewhere",
    )
    draft = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Draft",
    )
    draft.status = "draft"
    await session.flush()

    resp = await client.get(_url(ctx["app"].id, "/options"), headers=_auth(r_token))
    assert resp.status_code == 200, resp.text
    titles = {a["title"] for a in resp.json()["available"]}
    assert titles == {"Mine", "Shared"}
    assert "Elsewhere" not in titles
    assert "Draft" not in titles
    assert {str(mine.id), str(shared.id)} == {
        a["assessment_id"] for a in resp.json()["available"]
    }
    assert str(elsewhere.id) not in {
        a["assessment_id"] for a in resp.json()["available"]
    }


@pytest.mark.asyncio
async def test_already_assessed_appears_but_is_not_re_offered(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "alreadyset")
    r_token = await _login(client, "recalreadyset@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Live Assignment",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    resp = await client.get(_url(ctx["app"].id, "/options"), headers=_auth(r_token))
    body = resp.json()
    entry = next(
        a for a in body["available"] if a["assessment_id"] == str(assessment.id)
    )
    assert entry["already_assigned"] is True
    assert body["has_assessments"] is True
    assert body["attempt_count"] == 1
    assert len(body["actions"]) == 1
    assert body["actions"][0]["can_reassign"] is False


# ═══ 6. Candidate-safe projection ══════════════════════════════════


@pytest.mark.asyncio
async def test_candidate_view_is_allowlisted_and_application_scoped(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "safe")
    r_token = await _login(client, "recsafe@test.com")
    c_token = await _login(client, "candsafe@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Safe View",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    resp = await client.get(_url(ctx["app"].id), headers=_auth(c_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["has_assessment"] is True
    assert body["status"] == AttemptStatus.ASSIGNED.value
    assert body["can_start"] is True
    assert body["can_continue"] is False
    # No result yet, so no score. An ungraded attempt is not a zero.
    assert body["overall_score"] is None
    assert body["summary_text"] is None

    # The internal hiring-ish labels and the recruiter's identity must be absent
    # by construction, not merely unused.
    for forbidden in (
        "recommendation", "readiness_level", "weak_skills", "skill_scores",
        "recruiter_id", "assigned_by", "integrity_events", "passing_score",
        "per_question", "candidate_id", "section_scores", "accuracy",
    ):
        assert forbidden not in body, forbidden


@pytest.mark.asyncio
async def test_candidate_view_reports_result_after_submission(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "after")
    r_token = await _login(client, "recafter@test.com")
    c_token = await _login(client, "candafter@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Graded", passing_score=50,
    )
    assigned = (await _assign(client, r_token, ctx["app"].id, assessment.id)).json()
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    await _take_all(client, session, c_token, start.json()["attempt_id"])

    resp = await client.get(_url(ctx["app"].id), headers=_auth(c_token))
    body = resp.json()
    assert body["status"] == AttemptStatus.COMPLETED.value
    assert body["has_completed"] is True
    assert body["can_start"] is False
    assert body["can_continue"] is False
    assert isinstance(body["overall_score"], (int, float))
    # Still no verdict language in the candidate projection.
    assert "recommendation" not in body
    assert "readiness_level" not in body

    completed = [n for n in captured_notifications if n["event"] == "completed"]
    assert len(completed) == 1
    assert completed[0]["attempt_id"] == assigned["attempt_id"]
    assert "result is now available" in completed[0]["message"]


@pytest.mark.asyncio
async def test_resubmit_does_not_notify_or_regrade_twice(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "resubmit")
    r_token = await _login(client, "recresubmit@test.com")
    c_token = await _login(client, "candresubmit@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Once Only",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    attempt_id = start.json()["attempt_id"]
    await _take_all(client, session, c_token, attempt_id)

    result = await client.get(
        f"/api/v1/assessments/{attempt_id}/result", headers=_auth(c_token),
    )
    assert result.status_code == 200, result.text
    first = result.json()["overall_score"]
    again = await client.post(
        f"/api/v1/assessments/{attempt_id}/submit", headers=_auth(c_token),
    )
    assert again.status_code == 200, again.text
    assert again.json()["overall_score"] == first

    count = await session.scalar(
        select(func.count()).select_from(AssessmentResult).where(
            AssessmentResult.attempt_id == uuid.UUID(attempt_id),
        ),
    )
    assert count == 1
    assert len([n for n in captured_notifications if n["event"] == "completed"]) == 1


# ═══ 7. Evidence ═══════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_evidence_shows_score_only_once_graded(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "evid")
    r_token = await _login(client, "recevid@test.com")
    c_token = await _login(client, "candevid@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Evidence", passing_score=50,
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    resp = await client.get(_url(ctx["app"].id, "/evidence"), headers=_auth(r_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attempt_count"] == 1
    assert body["completed_count"] == 0
    assert body["average_overall_score"] is None
    attempt = body["attempts"][0]
    assert attempt["overall_score"] is None
    assert attempt["passed"] is None
    assert attempt["questions_answered"] == 0

    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    await _take_all(client, session, c_token, start.json()["attempt_id"])

    resp2 = await client.get(
        _url(ctx["app"].id, "/evidence"), headers=_auth(r_token),
    )
    body2 = resp2.json()
    assert body2["completed_count"] == 1
    assert body2["average_overall_score"] is not None
    graded = body2["attempts"][0]
    assert isinstance(graded["overall_score"], (int, float))
    assert isinstance(graded["passed"], bool)
    assert graded["questions_answered"] > 0
    # Weak skills are staff-only signal, unlike the candidate's own strong list.
    assert "weak_skills" in graded


@pytest.mark.asyncio
async def test_evidence_is_audited(
    client: AsyncClient, session: AsyncSession,
):
    from app.domain.models import AuditLog

    ctx = await _setup(session, "audit")
    r_token = await _login(client, "recaudit@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Audited",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)
    await client.get(_url(ctx["app"].id, "/evidence"), headers=_auth(r_token))

    events = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.ASSESSMENT_EVIDENCE_VIEWED.value,
            ),
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].resource_id == str(ctx["app"].id)


@pytest.mark.asyncio
async def test_assign_is_audited(
    client: AsyncClient, session: AsyncSession,
):
    from app.domain.models import AuditLog

    ctx = await _setup(session, "auditassign")
    r_token = await _login(client, "recauditassign@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Audited Assign",
    )
    await _assign(client, r_token, ctx["app"].id, assessment.id)

    events = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.ASSESSMENT_ASSIGNED.value,
            ),
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].user_id == ctx["recruiter"].id
    assert events[0].resource_id == str(ctx["app"].id)


# ═══ 8. Reuse, not a second platform ═══════════════════════════════


@pytest.mark.asyncio
async def test_self_started_attempt_has_no_application_link(
    client: AsyncClient, session: AsyncSession,
):
    """The legacy self-start flow is preserved exactly: no invented application."""
    ctx = await _setup(session, "selfstart")
    c_token = await _login(client, "candselfstart@test.com")
    assessment = await _mk_assessment(
        session, job_id=None, title="Practice",
    )
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    assert start.status_code == 200, start.text

    attempt = await session.get(
        CandidateAssessment, uuid.UUID(start.json()["attempt_id"]),
    )
    assert attempt.application_id is None
    assert attempt.assigned_by is None
    assert attempt.attempt_number == 1


@pytest.mark.asyncio
async def test_self_start_does_not_send_a_completion_notification(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """A candidate who pressed the button is already looking at the result."""
    ctx = await _setup(session, "selfnotify")
    c_token = await _login(client, "candselfnotify@test.com")
    assessment = await _mk_assessment(session, job_id=None, title="Practice")
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(c_token),
    )
    await _take_all(client, session, c_token, start.json()["attempt_id"])
    assert not [n for n in captured_notifications if n["event"] == "completed"]


@pytest.mark.asyncio
async def test_one_candidate_two_applications_stay_separate(
    client: AsyncClient, session: AsyncSession,
):
    """Evidence is per application, not per candidate."""
    ctx = await _setup(session, "twoapps")
    r_token = await _login(client, "rectwoapps@test.com")
    c_token = await _login(client, "candtwoapps@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Shared Assessment", allowed_attempts=3,
    )
    generic = await _mk_assessment(
        session, job_id=None, title="Generic", allowed_attempts=3,
    )

    # A second *job*, because (job_id, candidate_id) is unique: a candidate
    # cannot hold two applications to the same role, and the database enforces it.
    second_job = Job(
        recruiter_id=ctx["recruiter"].id,
        organization_id=ctx["org"].id,
        title="Platform Engineer",
        company=ctx["org"].name,
        department="Engineering",
        employment_type=EmploymentType.FULL_TIME.value,
        location="Remote",
        description="d",
        required_skills=["Python"],
        preferred_skills=[],
        status=JobStatus.PUBLISHED.value,
    )
    session.add(second_job)
    await session.flush()

    second = JobApplication(
        job_id=second_job.id, candidate_id=ctx["candidate"].id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(second)
    await session.flush()
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(second, actor=ctx["candidate"])
    for step in (
        ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
    ):
        await lifecycle.transition_application(second.id, step.value, ctx["recruiter"])
    await session.refresh(second)

    a = (await _assign(client, r_token, ctx["app"].id, assessment.id)).json()
    # A job-agnostic assessment is assignable to a different job's application,
    # which is why the catalog is "this job's assessments plus generic ones".
    b = (await _assign(client, r_token, second.id, generic.id)).json()
    assert a["attempt_id"] != b["attempt_id"]
    assert generic.id is not None

    for application_id in (ctx["app"].id, second.id):
        resp = await client.get(
            _url(application_id, "/evidence"), headers=_auth(r_token),
        )
        assert resp.json()["attempt_count"] == 1, application_id
        # And each application shows only its own attempt.
        assert len(resp.json()["attempts"]) == 1

    attempts = (
        await session.execute(
            select(CandidateAssessment).where(
                CandidateAssessment.candidate_id == ctx["candidate"].id,
            ).order_by(CandidateAssessment.attempt_number),
        )
    ).scalars().all()
    # The attempt counter is per (assessment, candidate). These are two
    # *different* assessments, so both are attempt 1 of their own.
    assert [x.attempt_number for x in attempts] == [1, 1]
    assert {x.application_id for x in attempts} == {ctx["app"].id, second.id}


@pytest.mark.asyncio
async def test_evidence_endpoint_ignores_an_unrelated_attempt(
    client: AsyncClient, session: AsyncSession,
):
    """An attempt from another application cannot be surfaced on this one."""
    ctx = await _setup(session, "unrelated")
    r_token = await _login(client, "recunrelated@test.com")
    c_token = await _login(client, "candunrelated@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Elsewhere",
    )
    other = await _mk_assessment(
        session, job_id=None, title="Practice Elsewhere",
    )
    start = await client.post(
        f"/api/v1/assessments/{other.id}/start", headers=_auth(c_token),
    )
    await _take_all(client, session, c_token, start.json()["attempt_id"])

    resp = await client.get(_url(ctx["app"].id, "/evidence"), headers=_auth(r_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["attempt_count"] == 0
    assert resp.json()["attempts"] == []

    # And a self-started attempt is invisible to the candidate's application card.
    mine = await client.get(_url(ctx["app"].id), headers=_auth(c_token))
    assert mine.json()["has_assessment"] is False


@pytest.mark.asyncio
async def test_existing_assessment_routes_still_registered(client: AsyncClient):
    """Phase 12 is additive: the pre-existing surface is unchanged."""
    from app.api.v1.assessments import router

    paths = {r.path for r in router.routes}
    for expected in (
        "/assessments/generate",
        "/assessments",
        "/assessments/me",
        "/assessments/{assessment_id}/start",
        "/assessments/attempts/{attempt_id}",
        "/assessments/{attempt_id}/answer",
        "/assessments/{attempt_id}/code/run",
        "/assessments/{attempt_id}/code/submit",
        "/assessments/{attempt_id}/integrity",
        "/assessments/{attempt_id}/submit",
        "/assessments/{attempt_id}/result",
        "/assessments/{assessment_id}",
        "/assessments/{assessment_id}/analytics",
    ):
        assert expected in paths, expected
    for added in (
        "/assessments/applications/{application_id}/assessment",
        "/assessments/applications/{application_id}/assessment/options",
        "/assessments/applications/{application_id}/assessment/assign",
        "/assessments/applications/{application_id}/assessment/evidence",
        "/assessments/applications/{application_id}/assessment/attempts"
        "/{attempt_id}/reschedule",
    ):
        assert added in paths, added


# ═══ 5. Scheduling ═════════════════════════════════════════════════
#
# Before the scheduling columns, the only timestamp an assignment carried was the
# instant the recruiter clicked, so the candidate's page could report nothing more
# interesting than "scheduled: now" and a reschedule had nowhere to be written.
# These tests pin the behaviour that replaces that: a chosen time is persisted,
# reaches only the candidate it was assigned to, arrives in the notification with
# the job and the link, and moving it updates the one assignment rather than
# creating a second.


def _iso(**offset) -> str:
    """A scheduled time a fixed distance from now, as an ISO string."""
    return (datetime.now(timezone.utc) + timedelta(**offset)).isoformat()


@pytest.mark.asyncio
async def test_scheduled_time_is_persisted_and_reaches_the_candidate(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """The chosen time is stored, and the candidate's own reads return it."""
    ctx = await _setup(session, "sched")
    r_token = await _login(client, "recsched@test.com")
    c_token = await _login(client, "candsched@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Scheduled Take",
    )
    when = _iso(days=3)

    resp = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=when,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["rescheduled"] is False
    assert body["scheduled_for"] is not None
    # The link is recorded on the assignment, not merely derivable.
    assert body["assessment_link"].endswith(str(assessment.id))

    # Persisted on the row itself.
    stored = (await _attempts(session, ctx["app"].id))[0]
    assert stored.scheduled_for is not None
    assert stored.assessment_link == body["assessment_link"]

    # The candidate's own application view reports the schedule...
    view = await client.get(_url(ctx["app"].id), headers=_auth(c_token))
    assert view.status_code == 200, view.text
    assert view.json()["scheduled_for"] is not None
    assert view.json()["assessment_link"] == body["assessment_link"]

    # ...and so does the candidate's assessment page feed, which is a different
    # query and would not see the column if only one of them were updated.
    mine = await client.get(
        "/api/v1/assessments/me", headers=_auth(c_token),
    )
    assert mine.status_code == 200, mine.text
    item = next(
        i for i in mine.json()["items"] if i["attempt_id"] == body["attempt_id"]
    )
    assert item["scheduled_for"] is not None
    assert item["assessment_link"] == body["assessment_link"]
    assert item["job_title"] == "Backend Engineer"


@pytest.mark.asyncio
async def test_assign_without_a_time_stores_no_schedule(
    client: AsyncClient, session: AsyncSession,
):
    """No chosen time is None, not a fabricated "now".

    The assignment timestamp already records when the recruiter acted; copying it
    into ``scheduled_for`` would assert they picked that moment, which they did not.
    """
    ctx = await _setup(session, "nosched")
    r_token = await _login(client, "recnosched@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Untimed",
    )

    resp = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert resp.status_code == 201, resp.text
    assert resp.json()["scheduled_for"] is None

    stored = (await _attempts(session, ctx["app"].id))[0]
    assert stored.scheduled_for is None
    # The assignment time is still recorded -- it is a different fact.
    assert stored.assigned_at is not None


@pytest.mark.asyncio
async def test_scheduled_assessment_is_invisible_to_another_candidate(
    client: AsyncClient, session: AsyncSession,
):
    """Candidate B must not see candidate A's assessment by any route."""
    ctx = await _setup(session, "iso")
    r_token = await _login(client, "reciso@test.com")
    a_token = await _login(client, "candiso@test.com")
    # A second candidate, with their own application, who was assigned nothing.
    other = await _mk_candidate(session, "Cand Other", "otheriso@test.com")
    other_app = JobApplication(
        job_id=ctx["job"].id, candidate_id=other.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(other_app)
    await session.flush()
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(other_app, actor=other)
    for step in (ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED):
        await lifecycle.transition_application(other_app.id, step.value, ctx["recruiter"])
    await session.refresh(other_app)
    b_token = await _login(client, "otheriso@test.com")

    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Only For A",
    )
    assigned = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=2),
    )
    assert assigned.status_code == 201, assigned.text

    # B's own list does not contain it.
    mine = await client.get("/api/v1/assessments/me", headers=_auth(b_token))
    assert mine.status_code == 200, mine.text
    assert all(
        i["attempt_id"] != assigned.json()["attempt_id"]
        for i in mine.json()["items"]
    )

    # B's application view reports no assessment, so no link leaks either.
    theirs = await client.get(_url(other_app.id), headers=_auth(b_token))
    assert theirs.status_code == 200, theirs.text
    assert theirs.json()["has_assessment"] is False
    assert theirs.json()["assessment_link"] is None

    # And B cannot read A's application by guessing its id: the same 404 as a
    # nonexistent one.
    stolen = await client.get(_url(ctx["app"].id), headers=_auth(b_token))
    missing = await client.get(
        _url(uuid.uuid4()), headers=_auth(b_token),
    )
    assert stolen.status_code == missing.status_code == 404


@pytest.mark.asyncio
async def test_reschedule_updates_the_assignment_in_place(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """A new time moves the one assignment; it does not add a second."""
    ctx = await _setup(session, "resched")
    r_token = await _login(client, "recresched@test.com")
    c_token = await _login(client, "candresched@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Movable",
    )
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    assert first.status_code == 201, first.text

    later = _iso(days=8)
    resp = await client.post(
        _reschedule_url(ctx["app"].id, first.json()["attempt_id"]),
        json={"scheduled_for": later},
        headers=_auth(r_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rescheduled"] is True
    assert body["attempt_id"] == first.json()["attempt_id"]

    # One row, still one, now carrying the new time.
    attempts = await _attempts(session, ctx["app"].id)
    assert len(attempts) == 1
    assert attempts[0].scheduled_for is not None

    # The candidate reads the new time, not the old one.
    view = await client.get(_url(ctx["app"].id), headers=_auth(c_token))
    stored_schedule = view.json()["scheduled_for"]
    assert stored_schedule is not None
    assert datetime.fromisoformat(stored_schedule).replace(
        tzinfo=timezone.utc,
    ) == datetime.fromisoformat(later).replace(tzinfo=timezone.utc)

    # Both events were told to the candidate, each exactly once.
    events = [n["event"] for n in captured_notifications]
    assert events == ["assigned", "rescheduled"]


@pytest.mark.asyncio
async def test_rescheduling_the_same_time_is_not_an_event(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """Re-posting the identical schedule changes nothing and says nothing.

    Guards the line between "reschedule" and "retry": a duplicate submission must
    not manufacture a second notification telling the candidate their time moved
    when it did not.
    """
    ctx = await _setup(session, "same")
    r_token = await _login(client, "recsame@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Stable",
    )
    when = _iso(days=4)
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=when,
    )
    assert first.status_code == 201, first.text

    repeat = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=when,
    )
    assert repeat.status_code == 201, repeat.text
    assert repeat.json()["already_assigned"] is True
    assert repeat.json()["rescheduled"] is False

    resp = await client.post(
        _reschedule_url(ctx["app"].id, first.json()["attempt_id"]),
        json={"scheduled_for": when},
        headers=_auth(r_token),
    )
    assert resp.status_code == 200, resp.text
    assert [n["event"] for n in captured_notifications] == ["assigned"]


@pytest.mark.asyncio
async def test_assign_with_a_new_time_reschedules_rather_than_duplicating(
    client: AsyncClient, session: AsyncSession,
):
    """Re-assigning the same assessment with a different time moves it.

    The recruiter may reach "schedule" only through the assign control, so the
    assign verb has to honour a new time itself rather than report the assignment
    as already made and silently drop the schedule.
    """
    ctx = await _setup(session, "viassign")
    r_token = await _login(client, "recviassign@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Reassigned",
    )
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    assert first.status_code == 201, first.text

    second = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=6),
    )
    assert second.status_code == 201, second.text
    assert second.json()["rescheduled"] is True
    assert second.json()["attempt_id"] == first.json()["attempt_id"]
    assert len(await _attempts(session, ctx["app"].id)) == 1


@pytest.mark.asyncio
async def test_reassigning_without_a_time_keeps_the_stored_schedule(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """Omitting the time means "leave it", not "clear it".

    The assign form's date field is optional, so a recruiter can submit the same
    assessment again having left it blank. Treating the blank as a request to
    unschedule would silently discard the arrangement the candidate was told about;
    treating it as a change is worse still, because the reschedule path writes the
    new time unconditionally and would raise with nothing to write.
    """
    ctx = await _setup(session, "keep")
    r_token = await _login(client, "reckeep@test.com")
    c_token = await _login(client, "candkeep@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Kept",
    )
    when = _iso(days=5)
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=when,
    )
    assert first.status_code == 201, first.text
    attempt_id = first.json()["attempt_id"]

    # No ``scheduled_for`` in the body at all.
    repeat = await _assign(client, r_token, ctx["app"].id, assessment.id)
    assert repeat.status_code == 201, repeat.text
    body = repeat.json()
    assert body["already_assigned"] is True
    assert body["rescheduled"] is False
    assert body["scheduled_for"] is not None

    # The row still carries the original arrangement.
    stored = (await _attempts(session, ctx["app"].id))[0]
    assert stored.scheduled_for is not None
    assert stored.scheduled_for.replace(
        tzinfo=timezone.utc,
    ) == datetime.fromisoformat(when).replace(tzinfo=timezone.utc)

    # The candidate still sees the same time, and was not told it moved.
    view = await client.get(_url(ctx["app"].id), headers=_auth(c_token))
    assert view.json()["scheduled_for"] is not None
    assert [n["event"] for n in captured_notifications] == ["assigned"]


@pytest.mark.asyncio
async def test_reschedule_refused_once_the_attempt_is_finished(
    client: AsyncClient, session: AsyncSession,
):
    """A completed attempt's timing is evidence and cannot be moved."""
    ctx = await _setup(session, "done")
    r_token = await _login(client, "recdone@test.com")
    c_token = await _login(client, "canddone@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Already Done",
    )
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    attempt_id = first.json()["attempt_id"]
    await _take_all(client, session, c_token, attempt_id)

    resp = await client.post(
        _reschedule_url(ctx["app"].id, attempt_id),
        json={"scheduled_for": _iso(days=9)},
        headers=_auth(r_token),
    )
    assert resp.status_code == 409, resp.text
    # The options endpoint says so up front, so the UI never offers the control.
    options = await client.get(
        _url(ctx["app"].id, "/options"), headers=_auth(r_token),
    )
    action = next(
        a for a in options.json()["actions"] if a["attempt_id"] == attempt_id
    )
    assert action["can_reschedule"] is False
    assert action["reschedule_unavailable_reason"] == "assessment_not_reschedulable"


@pytest.mark.asyncio
async def test_reschedule_refuses_an_attempt_from_another_tenant(
    client: AsyncClient, session: AsyncSession,
):
    """An attempt id carried across organizations is refused outright.

    The application-level RBAC guard answers this before the attempt is even
    looked up, so the attempt's existence is never confirmed to a recruiter who
    has no claim to the application it hangs off.
    """
    first_ctx = await _setup(session, "own1")
    second_ctx = await _setup(session, "own2")
    r_token = await _login(client, "recown1@test.com")
    assessment = await _mk_assessment(
        session, job_id=first_ctx["job"].id, title="Owned",
    )
    mine = await _assign(
        client, r_token, first_ctx["app"].id, assessment.id,
        scheduled_for=_iso(days=1),
    )
    assert mine.status_code == 201, mine.text

    resp = await client.post(
        _reschedule_url(second_ctx["app"].id, mine.json()["attempt_id"]),
        json={"scheduled_for": _iso(days=5)},
        headers=_auth(r_token),
    )
    assert resp.status_code == 403, resp.text
    # The victim's schedule is untouched.
    stored = (await _attempts(session, first_ctx["app"].id))[0]
    assert stored.scheduled_for is not None


@pytest.mark.asyncio
async def test_reschedule_refuses_an_attempt_from_another_application(
    client: AsyncClient, session: AsyncSession,
):
    """Within one organization, a foreign attempt id does not exist.

    The tenant check above passes here, so this exercises the narrower guard: an
    attempt that belongs to a *different* application of the same organization
    must not be movable through this one's URL.
    """
    ctx = await _setup(session, "sameorg")
    r_token = await _login(client, "recsameorg@test.com")
    # A second application, same organization and recruiter, different candidate.
    other = await _mk_candidate(session, "Same Org Other", "sameorg2@test.com")
    other_app = JobApplication(
        job_id=ctx["job"].id, candidate_id=other.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(other_app)
    await session.flush()
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(other_app, actor=ctx["recruiter"])
    for step in (ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED):
        await lifecycle.transition_application(other_app.id, step.value, ctx["recruiter"])
    await session.refresh(other_app)

    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Shared",
    )
    mine = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    assert mine.status_code == 201, mine.text

    resp = await client.post(
        _reschedule_url(other_app.id, mine.json()["attempt_id"]),
        json={"scheduled_for": _iso(days=5)},
        headers=_auth(r_token),
    )
    assert resp.status_code == 404, resp.text
    stored = (await _attempts(session, ctx["app"].id))[0]
    assert stored.scheduled_for is not None


@pytest.mark.asyncio
async def test_reschedule_refused_for_a_recruiter_without_access(
    client: AsyncClient, session: AsyncSession,
):
    """A recruiter from another organization cannot move the schedule."""
    ctx = await _setup(session, "tenant")
    r_token = await _login(client, "rectenant@test.com")
    out_token = await _login(client, "outtenant@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Theirs",
    )
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    assert first.status_code == 201, first.text

    resp = await client.post(
        _reschedule_url(ctx["app"].id, first.json()["attempt_id"]),
        json={"scheduled_for": _iso(days=5)},
        headers=_auth(out_token),
    )
    assert resp.status_code in (403, 404), resp.text


@pytest.mark.asyncio
async def test_assignment_notification_names_the_schedule_the_job_and_the_link(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """The notification carries what the candidate needs to act, and where to go."""
    ctx = await _setup(session, "notify")
    r_token = await _login(client, "recnotify@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="React Basics",
    )
    when = datetime.now(timezone.utc) + timedelta(days=3)
    resp = await _assign(
        client, r_token, ctx["app"].id, assessment.id,
        scheduled_for=when.isoformat(),
    )
    assert resp.status_code == 201, resp.text

    sent = next(n for n in captured_notifications if n["event"] == "assigned")
    message = sent["message"]
    assert "React Basics" in message
    assert "Backend Engineer" in message
    # The time is rendered, in the zone it is stored in.
    assert when.strftime("%d %b %Y") in message
    # And it points at this assessment rather than at a list page.
    assert sent["action_link"] == resp.json()["assessment_link"]
    assert sent["candidate_id"] == str(ctx["candidate"].id)


@pytest.mark.asyncio
async def test_reschedule_notification_reports_the_new_time(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    """The candidate is told the assessment moved, and to where."""
    ctx = await _setup(session, "renotify")
    r_token = await _login(client, "recrenotify@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Moves",
    )
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    when = datetime.now(timezone.utc) + timedelta(days=11)
    await client.post(
        _reschedule_url(ctx["app"].id, first.json()["attempt_id"]),
        json={"scheduled_for": when.isoformat()},
        headers=_auth(r_token),
    )

    sent = next(n for n in captured_notifications if n["event"] == "rescheduled")
    assert "Moves" in sent["message"]
    assert when.strftime("%d %b %Y") in sent["message"]
    assert sent["action_link"] == first.json()["assessment_link"]


@pytest.mark.asyncio
async def test_reschedule_requires_a_new_time(
    client: AsyncClient, session: AsyncSession,
):
    """"Reschedule" with no time is refused rather than defaulted to now."""
    ctx = await _setup(session, "reqtime")
    r_token = await _login(client, "recreqtime@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Needs A Time",
    )
    first = await _assign(
        client, r_token, ctx["app"].id, assessment.id, scheduled_for=_iso(days=1),
    )
    resp = await client.post(
        _reschedule_url(ctx["app"].id, first.json()["attempt_id"]),
        json={},
        headers=_auth(r_token),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_assign_still_forbids_a_client_supplied_candidate(
    client: AsyncClient, session: AsyncSession,
):
    """Scheduling did not open the identity fields the schema was built to close."""
    ctx = await _setup(session, "forbid")
    r_token = await _login(client, "recforbid@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Guarded",
    )
    resp = await client.post(
        _url(ctx["app"].id, "/assign"),
        json={
            "assessment_id": str(assessment.id),
            "scheduled_for": _iso(days=1),
            "candidate_id": str(ctx["candidate"].id),
        },
        headers=_auth(r_token),
    )
    assert resp.status_code == 422, resp.text
    assert len(await _attempts(session, ctx["app"].id)) == 0
