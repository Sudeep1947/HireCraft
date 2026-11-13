"""Phase 1: job-specific, candidate-specific bulk assessment assignment.

The feature is "recruiter opens one job, sees its applicants, ticks several and
assigns one assessment to all of them". These tests pin the four things it is
judged on:

1. **Batch, not N calls.** Two or more applicants can be assigned in one request,
   and each gets its own attempt row; a single-candidate batch behaves exactly
   like the per-application endpoint.
2. **Only this job's applicants.** An application id that does not belong to the
   job is reported, never assigned, and does not fail the rest of the batch.
3. **The existing rules.** The same pre-shortlist gate applies per candidate, the
   same catalog is offered, the same duplicate protection holds, and no
   assignment moves an application status.
4. **Staff only.** A recruiter from another organization and a candidate are both
   refused, and the whole batch is one transaction.
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
    EmploymentType,
    JobStatus,
    RoleName,
)
from app.domain.models import (
    Assessment,
    AssessmentQuestion,
    CandidateAssessment,
    Job,
    JobApplication,
    Organization,
    User,
)
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
)

PASSWORD = "Str0ng-Passw0rd!"


# ═══ Helpers ════════════════════════════════════════════════════════


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bulk_url(job_id: uuid.UUID, suffix: str = "/assign") -> str:
    return f"/api/v1/recruiter/jobs/{job_id}/assessments{suffix}"


def _options_url(job_id: uuid.UUID) -> str:
    return f"/api/v1/recruiter/jobs/{job_id}/assessment-options"


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


async def _mk_recruiter(session: AsyncSession, name: str, email: str) -> User:
    return await _mkuser_as(session, name, email, RoleName.RECRUITER.value)


async def _mk_candidate(session: AsyncSession, name: str, email: str) -> User:
    return await _mkuser_as(session, name, email, RoleName.CANDIDATE.value)


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# Legal transition paths, so a fixture never asserts from a state the
# application could not legally reach.
_PATH: dict[ApplicationStatus, list[ApplicationStatus]] = {
    ApplicationStatus.UNDER_REVIEW: [ApplicationStatus.UNDER_REVIEW],
    ApplicationStatus.SHORTLISTED: [
        ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
    ],
    ApplicationStatus.INTERVIEW_SCHEDULED: [
        ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED,
    ],
    ApplicationStatus.INTERVIEWED: [
        ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED, ApplicationStatus.INTERVIEWED,
    ],
    ApplicationStatus.REJECTED: [
        ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
        ApplicationStatus.REJECTED,
    ],
    ApplicationStatus.HIRED: [
        ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED,
        ApplicationStatus.OFFERED, ApplicationStatus.HIRED,
    ],
}


async def _mk_job(session: AsyncSession, recruiter: User, org: Organization, title: str) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title=title,
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
    return job


async def _mk_application(
    session: AsyncSession,
    job: Job,
    candidate: User,
    status: ApplicationStatus,
    actor: User,
) -> JobApplication:
    lifecycle = ApplicationLifecycleService(session)
    app = JobApplication(
        job_id=job.id, candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()
    await lifecycle.record_creation(app, actor=candidate)
    if status != ApplicationStatus.APPLIED:
        for step in _PATH[status]:
            await lifecycle.transition_application(app.id, step.value, actor)
    await session.refresh(app)
    return app


async def _setup(
    session: AsyncSession,
    suffix: str,
    applicant_statuses: list[ApplicationStatus],
    *,
    with_outsider: bool = True,
):
    """Org + owning recruiter + N candidates/applications at given statuses."""
    org = Organization(
        name=f"Org {suffix}", slug=f"org-{suffix}",
        description="d", status="active",
    )
    session.add(org)
    await session.flush()

    recruiter = await _mk_recruiter(session, f"Rec {suffix}", f"rec{suffix}@test.com")
    outsider = None
    if with_outsider:
        outsider = await _mk_recruiter(
            session, f"Out {suffix}", f"out{suffix}@test.com",
        )

    job = await _mk_job(session, recruiter, org, "Backend Engineer")

    applications = []
    candidates = []
    for index, status in enumerate(applicant_statuses):
        candidate = await _mk_candidate(
            session, f"Cand {suffix} {index}", f"cand{suffix}{index}@test.com",
        )
        candidates.append(candidate)
        app = await _mk_application(session, job, candidate, status, recruiter)
        applications.append(app)

    return {
        "org": org, "recruiter": recruiter, "outsider": outsider,
        "job": job, "applications": applications, "candidates": candidates,
    }


async def _mk_assessment(
    session: AsyncSession, *, job_id: uuid.UUID | None, title: str,
    allowed_attempts: int = 1, status: str = "published",
) -> Assessment:
    from app.services.assessment.generators import generate_assessment_questions

    assessment = Assessment(
        title=title,
        description="An assessment for testing.",
        job_id=job_id,
        mode="custom",
        status=status,
        duration_minutes=30,
        passing_score=60,
        negative_marking=0.0,
        allowed_attempts=allowed_attempts,
        adaptive=False,
        shuffle_questions=False,
        shuffle_options=False,
        config={"sections": [{"question_type": "mcq", "count": 2}]},
    )
    session.add(assessment)
    await session.flush()

    for index, payload in enumerate(
        generate_assessment_questions(
            [{"question_type": "mcq", "count": 2, "difficulty": "easy"}],
        )
    ):
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


@pytest.fixture
def captured_notifications(monkeypatch):
    """Record what the post-commit assessment dispatcher was asked to send."""
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
                "action_link": action_link,
            }
        )

    import app.services.assessment.application_assessment_notification as mod

    monkeypatch.setattr(mod, "_deliver_with_own_session", _fake)
    return captured


# ═══ 1. Single and multi candidate ══════════════════════════════════


@pytest.mark.asyncio
async def test_bulk_assign_to_one_candidate(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "bulk1", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recbulk1@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="One at a time",
    )
    app = ctx["applications"][0]

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(app.id)],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned_count"] == 1
    assert body["requested_count"] == 1
    assert body["skipped_count"] == 0
    assert body["items"][0]["outcome"] == "assigned"
    assert body["items"][0]["candidate_id"] == str(ctx["candidates"][0].id)

    attempts = await _attempts(session, app.id)
    assert len(attempts) == 1
    assert attempts[0].status == AttemptStatus.ASSIGNED.value
    assert attempts[0].assigned_by == ctx["recruiter"].id
    assert attempts[0].candidate_id == ctx["candidates"][0].id

    assigned = [n for n in captured_notifications if n["event"] == "assigned"]
    assert len(assigned) == 1
    assert assigned[0]["candidate_id"] == str(ctx["candidates"][0].id)
    assert "One at a time" in assigned[0]["message"]


@pytest.mark.asyncio
async def test_bulk_assign_to_many_candidates(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(
        session,
        "bulk3",
        [
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.INTERVIEW_SCHEDULED,
            ApplicationStatus.INTERVIEWED,
        ],
    )
    token = await _login(client, "recbulk3@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Everyone", allowed_attempts=2,
    )

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(a.id) for a in ctx["applications"]],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned_count"] == 3
    assert body["skipped_count"] == 0
    assert all(item["outcome"] == "assigned" for item in body["items"])

    for app in ctx["applications"]:
        attempts = await _attempts(session, app.id)
        assert len(attempts) == 1
        assert attempts[0].assessment_id == assessment.id
        assert attempts[0].status == AttemptStatus.ASSIGNED.value

    # One notification per newly assigned candidate.
    assert len([n for n in captured_notifications if n["event"] == "assigned"]) == 3


@pytest.mark.asyncio
async def test_bulk_assign_does_not_change_application_status(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(
        session, "bulknostatus",
        [ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_SCHEDULED],
    )
    token = await _login(client, "recbulknostatus@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="No status change",
    )
    before = [a.status for a in ctx["applications"]]

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(a.id) for a in ctx["applications"]],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    for app, was in zip(ctx["applications"], before):
        await session.refresh(app)
        assert app.status == was


# ═══ 2. Only this job's applicants ══════════════════════════════════


@pytest.mark.asyncio
async def test_non_applicant_is_reported_not_assigned(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "nonapp", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recnonapp@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Scoped",
    )
    valid = ctx["applications"][0]

    # An application belonging to a *different* job of the same org, and a
    # genuinely unknown id: both must be reported the same way.
    other_job = await _mk_job(session, ctx["recruiter"], ctx["org"], "Other Role")
    other_candidate = await _mk_candidate(session, "Elsewhere", "elsewhere@test.com")
    other_app = await _mk_application(
        session, other_job, other_candidate, ApplicationStatus.SHORTLISTED,
        ctx["recruiter"],
    )
    unknown = uuid.uuid4()

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(valid.id), str(other_app.id), str(unknown)],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned_count"] == 1
    assert body["skipped_count"] == 2

    outcomes = {item["application_id"]: item for item in body["items"]}
    assert outcomes[str(valid.id)]["outcome"] == "assigned"
    for foreign in (other_app.id, unknown):
        assert outcomes[str(foreign)]["outcome"] == "skipped"
        assert outcomes[str(foreign)]["reason"] == "not_an_applicant"
        assert outcomes[str(foreign)]["candidate_id"] is None

    # The foreign application was not touched.
    assert not await _attempts(session, other_app.id)


# ═══ 3. The existing per-candidate rules ════════════════════════════


@pytest.mark.asyncio
async def test_ineligible_candidate_is_skipped_but_rest_are_assigned(
    client: AsyncClient, session: AsyncSession,
):
    """A graded assessment must not short-circuit screening, even in a batch."""
    ctx = await _setup(
        session, "mixed",
        [ApplicationStatus.APPLIED, ApplicationStatus.SHORTLISTED],
    )
    token = await _login(client, "recmixed@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Partial",
    )

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(a.id) for a in ctx["applications"]],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned_count"] == 1
    assert body["skipped_count"] == 1

    applied_app, shortlisted_app = ctx["applications"]
    outcomes = {item["application_id"]: item for item in body["items"]}
    skipped = outcomes[str(applied_app.id)]
    assert skipped["outcome"] == "skipped"
    assert skipped["reason"] == "application_not_assessable"
    assert not await _attempts(session, applied_app.id)

    assert outcomes[str(shortlisted_app.id)]["outcome"] == "assigned"
    assert len(await _attempts(session, shortlisted_app.id)) == 1


@pytest.mark.asyncio
async def test_terminal_candidate_is_skipped(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(
        session, "terminal",
        [ApplicationStatus.REJECTED, ApplicationStatus.SHORTLISTED],
    )
    token = await _login(client, "recterminal@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Final",
    )

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(a.id) for a in ctx["applications"]],
        },
        headers=_auth(token),
    )
    body = resp.json()
    rejected_app = ctx["applications"][0]
    outcomes = {item["application_id"]: item for item in body["items"]}
    assert outcomes[str(rejected_app.id)]["reason"] == "application_is_final"
    assert body["assigned_count"] == 1
    assert not await _attempts(session, rejected_app.id)


@pytest.mark.asyncio
async def test_candidate_out_of_attempts_is_skipped(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "exhaust", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recexhaust@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="One shot", allowed_attempts=1,
    )
    app = ctx["applications"][0]

    # A self-started, completed attempt consumes the only allowed attempt.
    candidate_token = await _login(client, "candexhaust0@test.com")
    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start", headers=_auth(candidate_token),
    )
    assert start.status_code == 200, start.text
    state = await client.get(
        f"/api/v1/assessments/attempts/{start.json()['attempt_id']}",
        headers=_auth(candidate_token),
    )
    for question in state.json()["questions"]:
        await client.post(
            f"/api/v1/assessments/{start.json()['attempt_id']}/answer",
            json={
                "question_id": question["id"],
                "answer": {"option_index": 0},
                "time_taken_seconds": 10,
            },
            headers=_auth(candidate_token),
        )
    await client.post(
        f"/api/v1/assessments/{start.json()['attempt_id']}/submit",
        headers=_auth(candidate_token),
    )

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(app.id)],
        },
        headers=_auth(token),
    )
    body = resp.json()
    assert body["assigned_count"] == 0
    assert body["skipped_count"] == 1
    assert body["items"][0]["reason"] == "no_attempts_remaining"
    assert not await _attempts(session, app.id)


@pytest.mark.asyncio
async def test_bulk_assign_is_idempotent(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(session, "dupe", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recdupe@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Assign once",
    )
    app = ctx["applications"][0]
    payload = {
        "assessment_id": str(assessment.id),
        "application_ids": [str(app.id)],
    }

    first = await client.post(_bulk_url(ctx["job"].id), json=payload, headers=_auth(token))
    second = await client.post(_bulk_url(ctx["job"].id), json=payload, headers=_auth(token))

    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["assigned_count"] == 0
    assert second.json()["already_assigned_count"] == 1
    assert second.json()["items"][0]["outcome"] == "already_assigned"
    assert len(await _attempts(session, app.id)) == 1
    assert len([n for n in captured_notifications if n["event"] == "assigned"]) == 1


@pytest.mark.asyncio
async def test_repeated_application_id_is_one_attempt(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "dedupe", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recdedupe@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Once",
    )
    app = ctx["applications"][0]

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(app.id), str(app.id), str(app.id)],
        },
        headers=_auth(token),
    )
    body = resp.json()
    assert body["requested_count"] == 1
    assert body["assigned_count"] == 1
    assert len(await _attempts(session, app.id)) == 1


# ═══ 4. Authorization and tenancy ═══════════════════════════════════


@pytest.mark.asyncio
async def test_outsider_recruiter_cannot_bulk_assign(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "outsider", [ApplicationStatus.SHORTLISTED])
    outsider_token = await _login(client, "outoutsider@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Private",
    )
    app = ctx["applications"][0]

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(app.id)],
        },
        headers=_auth(outsider_token),
    )
    assert resp.status_code in (403, 404), resp.text
    assert not await _attempts(session, app.id)


@pytest.mark.asyncio
async def test_candidate_cannot_bulk_assign(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "candassign", [ApplicationStatus.SHORTLISTED])
    candidate_token = await _login(client, "candcandassign0@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Not yours",
    )
    app = ctx["applications"][0]

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(app.id)],
        },
        headers=_auth(candidate_token),
    )
    assert resp.status_code == 403, resp.text
    assert not await _attempts(session, app.id)


@pytest.mark.asyncio
async def test_unknown_job_is_404(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "unknownjob", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recunknownjob@test.com")
    assessment = await _mk_assessment(session, job_id=None, title="Generic")

    resp = await client.post(
        _bulk_url(uuid.uuid4()),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(ctx["applications"][0].id)],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_bulk_assign_rejects_assessment_of_another_job(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "otherjob", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recotherjob@test.com")
    other_job = await _mk_job(session, ctx["recruiter"], ctx["org"], "Unrelated")
    foreign = await _mk_assessment(
        session, job_id=other_job.id, title="Foreign",
    )
    app = ctx["applications"][0]

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(foreign.id),
            "application_ids": [str(app.id)],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text
    assert not await _attempts(session, app.id)


@pytest.mark.asyncio
async def test_bulk_assign_body_cannot_name_a_participant(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "forge", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recforge@test.com")
    other = await _mk_candidate(session, "Other", "otherforge@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Forgery",
    )
    app = ctx["applications"][0]

    for field in ("candidate_id", "recruiter_id", "job_id"):
        resp = await client.post(
            _bulk_url(ctx["job"].id),
            json={
                "assessment_id": str(assessment.id),
                "application_ids": [str(app.id)],
                field: str(other.id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422, (field, resp.text)
    assert not await _attempts(session, app.id)


@pytest.mark.asyncio
async def test_bulk_assign_requires_at_least_one_application(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "empty", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recempty@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Empty list",
    )
    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={"assessment_id": str(assessment.id), "application_ids": []},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# ═══ 5. Catalog and create-and-assign ═══════════════════════════════


@pytest.mark.asyncio
async def test_job_options_catalog_is_scoped_to_the_job(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "opts", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recopts@test.com")

    mine = await _mk_assessment(session, job_id=ctx["job"].id, title="Mine")
    shared = await _mk_assessment(session, job_id=None, title="Shared")
    other_job = await _mk_job(session, ctx["recruiter"], ctx["org"], "Other")
    elsewhere = await _mk_assessment(
        session, job_id=other_job.id, title="Elsewhere",
    )
    draft = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Draft", status="draft",
    )

    resp = await client.get(_options_url(ctx["job"].id), headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    titles = {a["title"] for a in body["available"]}
    assert titles == {"Mine", "Shared"}
    assert body["job_id"] == str(ctx["job"].id)
    for absent in ("Elsewhere", "Draft"):
        assert absent not in titles
    assert draft.id and elsewhere.id


@pytest.mark.asyncio
async def test_job_options_for_outsider_is_refused(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "optsout", [ApplicationStatus.SHORTLISTED])
    outsider_token = await _login(client, "outoptsout@test.com")
    resp = await client.get(
        _options_url(ctx["job"].id), headers=_auth(outsider_token),
    )
    assert resp.status_code in (403, 404), resp.text


@pytest.mark.asyncio
async def test_bulk_create_and_assign(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(
        session, "create",
        [ApplicationStatus.SHORTLISTED, ApplicationStatus.SHORTLISTED],
    )
    token = await _login(client, "reccreate@test.com")

    resp = await client.post(
        _bulk_url(ctx["job"].id, "/create-and-assign"),
        json={
            "title": "Authored For The Batch",
            "sections": [{"question_type": "mcq", "count": 2}],
            "application_ids": [str(a.id) for a in ctx["applications"]],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created_new_assessment"] is True
    assert body["assigned_count"] == 2
    assert body["assessment_title"] == "Authored For The Batch"

    assessment = await session.get(Assessment, uuid.UUID(body["assessment_id"]))
    # Server-derived scope: the authored assessment belongs to this job.
    assert assessment.job_id == ctx["job"].id

    for app in ctx["applications"]:
        attempts = await _attempts(session, app.id)
        assert len(attempts) == 1
        assert attempts[0].assessment_id == assessment.id


@pytest.mark.asyncio
async def test_bulk_create_and_assign_cannot_name_a_job(
    client: AsyncClient, session: AsyncSession,
):
    ctx = await _setup(session, "createforge", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "reccreateforge@test.com")
    resp = await client.post(
        _bulk_url(ctx["job"].id, "/create-and-assign"),
        json={
            "title": "Authored",
            "sections": [{"question_type": "mcq", "count": 2}],
            "application_ids": [str(ctx["applications"][0].id)],
            "job_id": str(uuid.uuid4()),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# ═══ 6. Reuse, not a second engine ══════════════════════════════════


@pytest.mark.asyncio
async def test_bulk_assign_writes_audit_per_candidate(
    client: AsyncClient, session: AsyncSession,
):
    from app.domain.enums import AuditEventType
    from app.domain.models import AuditLog

    ctx = await _setup(
        session, "audit",
        [ApplicationStatus.SHORTLISTED, ApplicationStatus.SHORTLISTED],
    )
    token = await _login(client, "recaudit@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Audited batch",
    )

    await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(a.id) for a in ctx["applications"]],
        },
        headers=_auth(token),
    )

    events = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.ASSESSMENT_ASSIGNED.value,
                AuditLog.action == "bulk_assign_assessment",
            ),
        )
    ).scalars().all()
    assert len(events) == 2
    assert {e.resource_id for e in events} == {str(a.id) for a in ctx["applications"]}


@pytest.mark.asyncio
async def test_bulk_assigned_attempt_resumes_via_existing_start(
    client: AsyncClient, session: AsyncSession,
):
    """The batch creates ordinary assignments: the candidate start path resumes them."""
    ctx = await _setup(session, "resume", [ApplicationStatus.SHORTLISTED])
    token = await _login(client, "recresume@test.com")
    candidate_token = await _login(client, "candresume0@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Resume me",
    )
    app = ctx["applications"][0]

    assigned = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(app.id)],
        },
        headers=_auth(token),
    )
    attempt_id = assigned.json()["items"][0]["attempt_id"]

    start = await client.post(
        f"/api/v1/assessments/{assessment.id}/start",
        headers=_auth(candidate_token),
    )
    assert start.status_code == 200, start.text
    assert start.json()["attempt_id"] == attempt_id
    assert start.json()["status"] == AttemptStatus.IN_PROGRESS.value

    count = await session.scalar(
        select(func.count()).select_from(CandidateAssessment).where(
            CandidateAssessment.application_id == app.id,
        ),
    )
    assert count == 1


@pytest.mark.asyncio
async def test_bulk_routes_are_registered(client: AsyncClient):
    """Additive: the job-scoped bulk surface is present."""
    from app.api.v1.recruiter_jobs import router

    paths = {r.path for r in router.routes}
    for expected in (
        "/recruiter/jobs/{job_id}/assessment-options",
        "/recruiter/jobs/{job_id}/assessments/assign",
        "/recruiter/jobs/{job_id}/assessments/create-and-assign",
    ):
        assert expected in paths, expected


@pytest.mark.asyncio
async def test_scheduled_time_is_applied_to_every_assignment(
    client: AsyncClient, session: AsyncSession, captured_notifications,
):
    ctx = await _setup(
        session, "sched",
        [ApplicationStatus.SHORTLISTED, ApplicationStatus.SHORTLISTED],
    )
    token = await _login(client, "recsched@test.com")
    assessment = await _mk_assessment(
        session, job_id=ctx["job"].id, title="Scheduled batch",
    )
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    resp = await client.post(
        _bulk_url(ctx["job"].id),
        json={
            "assessment_id": str(assessment.id),
            "application_ids": [str(a.id) for a in ctx["applications"]],
            "scheduled_for": when,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    for item in resp.json()["items"]:
        assert item["scheduled_for"] is not None

    for app in ctx["applications"]:
        attempts = await _attempts(session, app.id)
        assert attempts[0].scheduled_for is not None

    assigned = [n for n in captured_notifications if n["event"] == "assigned"]
    assert len(assigned) == 2
    assert all("Scheduled for" in n["message"] for n in assigned)
