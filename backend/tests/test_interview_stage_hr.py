"""Tests for Phase 15: recruiter interview stage, feedback, HR advancement.

Contract under test:

- An interview carries a **stage** (``recruiter`` / ``hr``) separate from its
  status and from the application status. Scheduling defaults to the recruiter
  round, so every existing caller and row keeps its meaning.
- The shared room shows a server-derived **display state** (upcoming /
  ready_to_join / in_progress / completed / cancelled / rescheduled / expired).
  The window closing yields ``expired`` and **never** completes the interview or
  moves the application: only the recruiter's explicit action does.
- Rescheduling records ``rescheduled_at`` and the room reports ``rescheduled``
  while it waits for the new time.
- A recruiter can record **manual technical feedback** on a real interview; it is
  stored on the interview scorecard, readable by staff only, and reaches no
  candidate surface.
- **Advance to HR** makes the candidate eligible for an HR round. It requires a
  completed recruiter interview, changes no application status, invents no HR
  time, creates no room and makes no decision. HR scheduling is only offered once
  the candidate is advanced.
- **Reject** delegates to the Phase 8 decision service, so the status change,
  the structured reason and the candidate-safe wording match the decision panel.
- All of it is staff-only and application-scoped: a candidate or another tenant's
  recruiter is refused.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    InterviewStage,
    InterviewStatus,
    JobStatus,
    MembershipStatus,
    RejectionReason,
    RoleName,
)
from app.domain.models import (
    Interview,
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    User,
)
from app.repositories.interview.interview import InterviewRepository
from app.repositories.jobs.job import JobApplicationRepository
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
)

PASSWORD = "Interview@12345"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _interviews_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/interview/applications/{app_id}/interviews"


def _room_url(interview_id: uuid.UUID) -> str:
    return f"/api/v1/interview/{interview_id}/room"


def _join_url(interview_id: uuid.UUID) -> str:
    return f"/api/v1/interview/{interview_id}/join"


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _assign_role(session: AsyncSession, user_id: uuid.UUID, role_name: str) -> None:
    from app.domain.models import Role, UserRole

    role = (
        await session.execute(select(Role).where(Role.name == role_name))
    ).scalar_one_or_none()
    assert role, f"Role {role_name!r} must exist"
    session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.flush()


async def _create_user(session: AsyncSession, name: str, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        full_name=name,
        email=email,
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_org(session: AsyncSession, name: str, slug: str) -> Organization:
    org = Organization(name=name, slug=slug, description=f"{name} demo", status="active")
    session.add(org)
    await session.flush()
    return org


async def _create_job(session: AsyncSession, recruiter: User, org: Organization, title: str) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title=title,
        company=org.name,
        department="Engineering",
        employment_type="full_time",
        location="Remote",
        description="Build production systems.",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL"],
        status=JobStatus.PUBLISHED.value,
    )
    session.add(job)
    await session.flush()
    return job


async def _setup(
    session: AsyncSession,
    suffix: str,
    *,
    status: ApplicationStatus = ApplicationStatus.SHORTLISTED,
):
    org = await _create_org(session, f"Org {suffix}", f"org-{suffix}")
    recruiter = await _create_user(session, f"Recruiter {suffix}", f"rec{suffix}@test.com")
    candidate = await _create_user(session, f"Candidate {suffix}", f"cand{suffix}@test.com")
    outsider = await _create_user(session, f"Outsider {suffix}", f"out{suffix}@test.com")
    await _assign_role(session, recruiter.id, RoleName.RECRUITER.value)
    await _assign_role(session, candidate.id, RoleName.CANDIDATE.value)
    await _assign_role(session, outsider.id, RoleName.RECRUITER.value)

    job = await _create_job(session, recruiter, org, f"Backend Engineer {suffix}")
    app = JobApplication(
        job_id=job.id,
        candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()

    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(app, actor=candidate)
    if status != ApplicationStatus.APPLIED:
        await lifecycle.transition_application(
            app.id, ApplicationStatus.UNDER_REVIEW.value, recruiter,
        )
        if status != ApplicationStatus.UNDER_REVIEW:
            await lifecycle.transition_application(app.id, status.value, recruiter)
    await session.refresh(app)
    return {
        "org": org,
        "recruiter": recruiter,
        "candidate": candidate,
        "outsider": outsider,
        "job": job,
        "app": app,
    }


def _schedule_body(**overrides) -> dict:
    when = datetime.now(timezone.utc) + timedelta(days=3)
    body = {
        "scheduled_at": when.isoformat(),
        "duration_minutes": 60,
        "categories": ["technical", "behavioral"],
        "difficulty": "medium",
        "question_count": 4,
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def capture_notifications(monkeypatch):
    """Never let the post-commit dispatchers open a real session."""
    captured: list[dict] = []

    async def _fake(*args, **kwargs):
        captured.append({"args": args, "kwargs": kwargs})

    import app.services.interview.application_interview_notification as interview_mod
    import app.services.applications.application_decision_notification as decision_mod

    monkeypatch.setattr(interview_mod, "_deliver_with_own_session", _fake)
    monkeypatch.setattr(interview_mod, "_deliver_staff_with_own_session", _fake)
    monkeypatch.setattr(decision_mod, "_deliver_with_own_session", _fake)
    return captured


async def _schedule(client: AsyncClient, ctx, token: str, **overrides):
    return await client.post(
        _interviews_url(ctx["app"].id),
        json=_schedule_body(**overrides),
        headers=_auth(token),
    )


async def _complete(client: AsyncClient, app_id: uuid.UUID, interview_id: str, token: str):
    return await client.post(
        f"{_interviews_url(app_id)}/{interview_id}/complete",
        json={},
        headers=_auth(token),
    )


# ═════════════════════════════════════════════════════════════════════
# 1. Stage
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scheduled_interview_defaults_to_recruiter_stage(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "st1")
    token = await _login(client, ctx["recruiter"].email)

    resp = await _schedule(client, ctx, token)
    assert resp.status_code == 201, resp.text
    interview_id = resp.json()["interview_id"]

    interview = await InterviewRepository(session).get(uuid.UUID(interview_id))
    assert interview.stage == InterviewStage.RECRUITER.value

    evidence = await client.get(
        _interviews_url(ctx["app"].id), headers=_auth(token),
    )
    assert evidence.status_code == 200, evidence.text
    summary = evidence.json()["interviews"][0]
    assert summary["stage"] == InterviewStage.RECRUITER.value
    assert evidence.json()["hr_eligible"] is False


# ═════════════════════════════════════════════════════════════════════
# 2. Room display states
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_room_state_is_upcoming_before_the_window(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "rs1")
    token = await _login(client, ctx["candidate"].email)
    create = await _schedule(
        client, ctx, await _login(client, ctx["recruiter"].email),
    )
    interview_id = create.json()["interview_id"]

    room = await client.get(_room_url(uuid.UUID(interview_id)), headers=_auth(token))
    assert room.status_code == 200, room.text
    body = room.json()
    assert body["state"] == "upcoming"
    assert body["status"] == InterviewStatus.SCHEDULED.value
    assert body["can_join"] is False
    assert body["rescheduled_at"] is None


@pytest.mark.asyncio
async def test_room_state_ready_then_in_progress_on_join(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "rs2")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    within_window = datetime.now(timezone.utc) + timedelta(minutes=5)
    create = await _schedule(
        client, ctx, recruiter_token, scheduled_at=within_window.isoformat(),
    )
    interview_id = create.json()["interview_id"]

    room = await client.get(_room_url(uuid.UUID(interview_id)), headers=_auth(candidate_token))
    assert room.json()["state"] == "ready_to_join"
    assert room.json()["can_join"] is True

    joined = await client.post(_join_url(uuid.UUID(interview_id)), headers=_auth(candidate_token))
    assert joined.status_code == 200, joined.text
    assert joined.json()["state"] == "in_progress"
    assert joined.json()["status"] == InterviewStatus.IN_PROGRESS.value
    assert joined.json()["you_joined"] is True

    interview = await InterviewRepository(session).get(uuid.UUID(interview_id))
    assert interview.status == InterviewStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_room_state_expired_does_not_complete_or_advance(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "rs3")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    long_ago = datetime.now(timezone.utc) - timedelta(hours=3)
    create = await _schedule(
        client, ctx, recruiter_token, scheduled_at=long_ago.isoformat(),
    )
    interview_id = create.json()["interview_id"]

    room = await client.get(_room_url(uuid.UUID(interview_id)), headers=_auth(candidate_token))
    assert room.json()["state"] == "expired"
    assert room.json()["can_join"] is False

    # The window closing is not the interview ending: nothing was written.
    interview = await InterviewRepository(session).get(uuid.UUID(interview_id))
    assert interview.status == InterviewStatus.SCHEDULED.value
    assert interview.completed_at is None
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value


@pytest.mark.asyncio
async def test_reschedule_marks_the_room_rescheduled(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "rs4")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    create = await _schedule(client, ctx, recruiter_token)
    interview_id = create.json()["interview_id"]

    moved = datetime.now(timezone.utc) + timedelta(days=6)
    resp = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{interview_id}/reschedule",
        json={"scheduled_at": moved.isoformat(), "duration_minutes": 45},
        headers=_auth(recruiter_token),
    )
    assert resp.status_code == 200, resp.text

    room = await client.get(_room_url(uuid.UUID(interview_id)), headers=_auth(candidate_token))
    body = room.json()
    assert body["state"] == "rescheduled"
    assert body["rescheduled_at"] is not None

    # The status is untouched: a reschedule is not a completion.
    interview = await InterviewRepository(session).get(uuid.UUID(interview_id))
    assert interview.status == InterviewStatus.SCHEDULED.value


# ═════════════════════════════════════════════════════════════════════
# 3. Feedback
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_feedback_round_trip_is_staff_only(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "fb1")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    create = await _schedule(client, ctx, recruiter_token)
    interview_id = create.json()["interview_id"]
    feedback_url = f"{_interviews_url(ctx['app'].id)}/{interview_id}/feedback"

    payload = {
        "technical_skills": 80,
        "communication": 70,
        "problem_solving": 90,
        "hiring_confidence": 65,
        "recommendation": "recommend",
        "recruiter_notes": "Strong systems thinking.",
    }
    saved = await client.post(feedback_url, json=payload, headers=_auth(recruiter_token))
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["technical_skills"] == 80
    assert body["overall_score"] == 80  # average of 80/70/90
    assert body["recommendation"] == "recommend"

    fetched = await client.get(feedback_url, headers=_auth(recruiter_token))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["recruiter_notes"] == "Strong systems thinking."

    # Candidate and another tenant's recruiter are refused.
    candidate_token = await _login(client, ctx["candidate"].email)
    outsider_token = await _login(client, ctx["outsider"].email)
    assert (await client.get(feedback_url, headers=_auth(candidate_token))).status_code == 403
    assert (await client.get(feedback_url, headers=_auth(outsider_token))).status_code == 403


# ═════════════════════════════════════════════════════════════════════
# 4. Advance to HR
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_advance_requires_a_completed_recruiter_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "adv1")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    create = await _schedule(client, ctx, recruiter_token)
    interview_id = create.json()["interview_id"]
    advance_url = f"/api/v1/interview/applications/{ctx['app'].id}/advance-to-hr"

    options = await client.get(
        f"{_interviews_url(ctx['app'].id)}/options", headers=_auth(recruiter_token),
    )
    assert options.json()["can_advance"] is False
    assert options.json()["advance_unavailable_reason"] == "recruiter_interview_not_completed"

    early = await client.post(advance_url, json={}, headers=_auth(recruiter_token))
    assert early.status_code == 409, early.text

    done = await _complete(client, ctx["app"].id, interview_id, recruiter_token)
    assert done.status_code == 200, done.text
    assert done.json()["application_status"] == ApplicationStatus.INTERVIEWED.value

    advanced = await client.post(advance_url, json={"note": "ok"}, headers=_auth(recruiter_token))
    assert advanced.status_code == 200, advanced.text
    result = advanced.json()
    assert result["hr_eligible"] is True
    # Advancing is not a status change and creates no interview.
    assert result["application_status"] == ApplicationStatus.INTERVIEWED.value
    assert result["application_status_changed"] is False

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value

    assert app.advanced_to_hr_at is not None
    assert app.advanced_to_hr_by == ctx["recruiter"].id
    assert len(await InterviewRepository(session).list_by_application(ctx["app"].id)) == 1


@pytest.mark.asyncio
async def test_hr_scheduling_requires_advancement_and_keeps_status(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "adv2")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    create = await _schedule(client, ctx, recruiter_token)
    interview_id = create.json()["interview_id"]

    # HR scheduling is refused before the candidate is advanced.
    blocked = await _schedule(client, ctx, recruiter_token, stage="hr")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "conflict"

    await _complete(client, ctx["app"].id, interview_id, recruiter_token)
    advance_url = f"/api/v1/interview/applications/{ctx['app'].id}/advance-to-hr"
    assert (await client.post(advance_url, json={}, headers=_auth(recruiter_token))).status_code == 200

    options = await client.get(
        f"{_interviews_url(ctx['app'].id)}/options", headers=_auth(recruiter_token),
    )
    assert options.json()["can_schedule_hr"] is True
    assert options.json()["can_advance"] is False
    assert options.json()["advance_unavailable_reason"] == "candidate_already_advanced_to_hr"

    hr = await _schedule(client, ctx, recruiter_token, stage="hr")
    assert hr.status_code == 201, hr.text
    assert hr.json()["application_status_changed"] is False
    assert hr.json()["application_status"] == ApplicationStatus.INTERVIEWED.value

    hr_id = hr.json()["interview_id"]
    interview = await InterviewRepository(session).get(uuid.UUID(hr_id))
    assert interview.stage == InterviewStage.HR.value

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value

    # Verifying the exact frontend workflow: ApplicationInterviewPanel calls
    # GET /applications/{id}/interviews immediately after scheduling.
    # Must succeed with 200 and return loaded recruiter_name without MissingGreenlet 500 error.
    evidence_resp = await client.get(
        _interviews_url(ctx["app"].id), headers=_auth(recruiter_token),
    )
    assert evidence_resp.status_code == 200, evidence_resp.text
    evidence = evidence_resp.json()
    assert evidence["interview_count"] == 2
    hr_iv = next(iv for iv in evidence["interviews"] if iv["id"] == hr_id)
    assert hr_iv["stage"] == "hr"
    assert hr_iv["status"] == "scheduled"
    assert hr_iv["recruiter_name"] == ctx["recruiter"].full_name


# ═════════════════════════════════════════════════════════════════════
# 5. Reject from the interview stage
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reject_from_interview_stage_records_reason(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "rj1")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    create = await _schedule(client, ctx, recruiter_token)
    interview_id = create.json()["interview_id"]
    await _complete(client, ctx["app"].id, interview_id, recruiter_token)

    reject_url = f"/api/v1/interview/applications/{ctx['app'].id}/reject"
    resp = await client.post(
        reject_url,
        json={
            "rejection_reason": RejectionReason.FAILED_INTERVIEW.value,
            "internal_note": "interview did not go well",
        },
        headers=_auth(recruiter_token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["application_status"] == ApplicationStatus.REJECTED.value
    assert result["application_status_changed"] is True
    assert result["candidate_message"]

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.REJECTED.value
    assert app.decision_reason_code == RejectionReason.FAILED_INTERVIEW.value


@pytest.mark.asyncio
async def test_stage_actions_are_staff_only(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "perm1")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    create = await _schedule(client, ctx, recruiter_token)
    interview_id = create.json()["interview_id"]
    await _complete(client, ctx["app"].id, interview_id, recruiter_token)

    candidate_token = await _login(client, ctx["candidate"].email)
    outsider_token = await _login(client, ctx["outsider"].email)
    advance_url = f"/api/v1/interview/applications/{ctx['app'].id}/advance-to-hr"
    reject_url = f"/api/v1/interview/applications/{ctx['app'].id}/reject"

    assert (
        await client.post(advance_url, json={}, headers=_auth(candidate_token))
    ).status_code == 403
    assert (
        await client.post(advance_url, json={}, headers=_auth(outsider_token))
    ).status_code == 403
    assert (
        await client.post(
            reject_url,
            json={"rejection_reason": RejectionReason.FAILED_INTERVIEW.value},
            headers=_auth(outsider_token),
        )
    ).status_code == 403
