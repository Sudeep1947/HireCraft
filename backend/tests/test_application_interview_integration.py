"""Tests for Phase 11: application-driven Interview Intelligence integration.

Contract under test:

- An interview is scheduled **from an application**. The job, candidate,
  recruiter and organization are derived from the ``application_id`` in the path;
  the request body carries no participant identity at all, so a recruiter cannot
  schedule an interview against a different candidate or another tenant's job.
- The application lifecycle stays authoritative: scheduling drives
  ``SHORTLISTED -> INTERVIEW_SCHEDULED`` and completion drives
  ``INTERVIEW_SCHEDULED -> INTERVIEWED`` through the lifecycle service, which
  owns the transition table, the compare-and-swap update, the immutable history
  row and the status audit event.
- **No automated hiring decision.** An interview score, evaluation or scorecard
  recommendation never selects, rejects or ranks a candidate, and cancelling an
  interview never rejects the application.
- No duplicate interview from a retried request, and an already-open interview
  blocks a new one.
- Reschedule keeps the same interview record and its questions; the application
  status does not move. Cancel is idempotent. Complete is idempotent.
- Audit records the interview event alongside the application it belongs to,
  and the candidate notification is delivered after commit and de-duplicated.
- Tenant isolation: another organization's recruiter is refused; a candidate can
  never schedule, and can never read another candidate's interview evidence.
- The candidate view is an allowlist. No scorecard, no evaluation, no
  recommendation, no recruiter identity or notes on any candidate endpoint.
- The pre-existing interview endpoints enforce authorization: an interview or
  scorecard id from another tenant is indistinguishable from a missing one.
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
    AuditEventType,
    EmploymentType,
    InterviewStatus,
    JobStatus,
    MembershipStatus,
    RoleName,
)
from app.domain.models import (
    ApplicationStatusHistory,
    AuditLog,
    Interview,
    Job,
    JobApplication,
    Notification,
    Organization,
    OrganizationMembership,
    User,
)
from app.repositories.interview.interview import InterviewRepository
from app.repositories.jobs.job import JobApplicationRepository
from app.services.applications.application_lifecycle_service import (
    DECISION_STATUSES,
    ApplicationLifecycleService,
)
from app.services.interview.application_interview_notification import (
    interview_dedupe_key,
)

PASSWORD = "Interview@12345"
INTERNAL_NOTE = "INTERNAL-ONLY-4a71 private recruiter note"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _interviews_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/interview/applications/{app_id}/interviews"


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _assign_role(
    session: AsyncSession, user_id: uuid.UUID, role_name: str,
) -> None:
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


async def _add_membership(
    session: AsyncSession, user: User, org_id: uuid.UUID, role: str,
) -> None:
    session.add(
        OrganizationMembership(
            user_id=user.id,
            organization_id=org_id,
            role=role,
            status=MembershipStatus.ACTIVE.value,
            joined_at=datetime.now(timezone.utc),
        ),
    )
    await session.flush()


async def _create_job(
    session: AsyncSession, recruiter: User, org: Organization, title: str,
) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title=title,
        company=org.name,
        department="Engineering",
        employment_type=EmploymentType.FULL_TIME.value,
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
    job_title: str = "Backend Engineer",
):
    """Org + owning recruiter + candidate + published job + application.

    Defaults to a SHORTLISTED application, because that is the state an
    application-driven interview is designed to start from.
    """
    org = await _create_org(session, f"Org {suffix}", f"org-{suffix}")
    recruiter = await _create_user(
        session, f"Recruiter {suffix}", f"rec{suffix}@test.com",
    )
    candidate = await _create_user(
        session, f"Candidate {suffix}", f"cand{suffix}@test.com",
    )
    outsider = await _create_user(
        session, f"Outsider {suffix}", f"out{suffix}@test.com",
    )
    await _assign_role(session, recruiter.id, RoleName.RECRUITER.value)
    await _assign_role(session, candidate.id, RoleName.CANDIDATE.value)
    await _assign_role(session, outsider.id, RoleName.RECRUITER.value)

    job = await _create_job(session, recruiter, org, job_title)
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
        # Reach the starting status through the authoritative transition path.
        await lifecycle.transition_application(
            app.id,
            ApplicationStatus.UNDER_REVIEW.value,
            recruiter,
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


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


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


@pytest.fixture
def captured_notifications(monkeypatch):
    """Capture what the post-commit interview dispatcher was asked to send.

    The real dispatcher opens its own session against the configured database,
    not the in-memory test database, so it is replaced with a recorder. The
    delivery function itself is unit tested below.
    """
    captured: list[dict] = []

    async def _fake(interview_id, candidate_id, event, candidate_message):
        captured.append(
            {
                "interview_id": interview_id,
                "candidate_id": candidate_id,
                "event": event,
                "candidate_message": candidate_message,
            }
        )

    import app.services.interview.application_interview_notification as mod

    monkeypatch.setattr(mod, "_deliver_with_own_session", _fake)
    return captured


async def _count_questions(session: AsyncSession, interview_id: uuid.UUID) -> int:
    """Count an interview's questions with an explicit query.

    Not ``len(interview.questions)``: that lazy-loads, which is an implicit IO
    call that async SQLAlchemy refuses outside a greenlet context.
    """
    from app.domain.models import InterviewQuestion

    return len(
        (
            await session.execute(
                select(InterviewQuestion).where(
                    InterviewQuestion.interview_id == interview_id,
                )
            )
        ).scalars().all()
    )


async def _schedule(
    client: AsyncClient, session: AsyncSession, ctx, token: str,
) -> tuple:
    resp = await client.post(
        _interviews_url(ctx["app"].id),
        json=_schedule_body(),
        headers=_auth(token),
    )
    return resp


# ═════════════════════════════════════════════════════════════════════
# 1. Scheduling is application-driven
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_schedule_links_interview_and_advances_application(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "s1")
    token = await _login(client, ctx["recruiter"].email)

    resp = await _schedule(client, session, ctx, token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["application_status"] == ApplicationStatus.INTERVIEW_SCHEDULED.value
    assert body["interview_status"] == InterviewStatus.SCHEDULED.value

    interview = await InterviewRepository(session).get(
        uuid.UUID(body["interview_id"])
    )
    assert interview is not None
    # The link, and the participants derived from the application rather than
    # the request.
    assert interview.application_id == ctx["app"].id
    assert interview.job_id == ctx["job"].id
    assert interview.candidate_id == ctx["candidate"].id
    assert interview.recruiter_id == ctx["recruiter"].id
    # A real question set was generated through the existing generator.
    assert interview.total_questions == 4
    assert await _count_questions(session, interview.id) == 4

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value

    # The lifecycle history recorded the transition, not a direct status write.
    rows = (
        await session.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == ctx["app"].id,
                ApplicationStatusHistory.to_status
                == ApplicationStatus.INTERVIEW_SCHEDULED.value,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].from_status == ApplicationStatus.SHORTLISTED.value
    assert rows[0].metadata_json["interview_id"] == body["interview_id"]


@pytest.mark.asyncio
async def test_schedule_request_cannot_name_a_different_candidate(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A participant in the body is not a participant in the request.

    The Phase 11 request schema has no ``candidate_id`` field at all, so trying
    to point the workflow at another person is a 422 -- the extra key cannot
    even reach the service.
    """
    ctx = await _setup(session, "s2")
    token = await _login(client, ctx["recruiter"].email)

    other = await _create_user(session, "Someone Else", "someone-else@test.com")
    resp = await client.post(
        _interviews_url(ctx["app"].id),
        json=_schedule_body(candidate_id=str(other.id)),
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text

    interviews = await InterviewRepository(session).find(
        application_id=ctx["app"].id,
    )
    assert interviews == []


@pytest.mark.asyncio
async def test_schedule_requires_shortlisted(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "s3", status=ApplicationStatus.UNDER_REVIEW)
    token = await _login(client, ctx["recruiter"].email)

    resp = await _schedule(client, session, ctx, token)
    assert resp.status_code == 409, resp.text

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.UNDER_REVIEW.value
    assert await InterviewRepository(session).find(
        application_id=ctx["app"].id,
    ) == []


@pytest.mark.asyncio
async def test_schedule_refused_for_terminal_application(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "s4", status=ApplicationStatus.REJECTED)
    token = await _login(client, ctx["recruiter"].email)

    resp = await _schedule(client, session, ctx, token)
    assert resp.status_code == 409, resp.text
    assert await InterviewRepository(session).find(
        application_id=ctx["app"].id,
    ) == []


@pytest.mark.asyncio
async def test_duplicate_schedule_is_refused(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A retried request must not create a second live interview."""
    ctx = await _setup(session, "s5")
    token = await _login(client, ctx["recruiter"].email)

    first = await _schedule(client, session, ctx, token)
    assert first.status_code == 201, first.text

    second = await _schedule(client, session, ctx, token)
    assert second.status_code == 409, second.text
    assert "already has an interview" in second.json()["error"]["message"]

    interviews = await InterviewRepository(session).find(
        application_id=ctx["app"].id,
    )
    assert len(interviews) == 1


# ═════════════════════════════════════════════════════════════════════
# 2. Reschedule / cancel / complete
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reschedule_keeps_the_same_interview_and_status(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "r1")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = created["interview_id"]

    later = datetime.now(timezone.utc) + timedelta(days=9)
    resp = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{interview_id}/reschedule",
        json={"scheduled_at": later.isoformat(), "duration_minutes": 90},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["interview_id"] == interview_id
    assert body["application_status_changed"] is False
    assert body["application_status"] == ApplicationStatus.INTERVIEW_SCHEDULED.value

    interview = await InterviewRepository(session).get(uuid.UUID(interview_id))
    assert interview.duration_minutes == 90
    # Same row, and its generated questions survived the move.
    assert await _count_questions(session, interview.id) == 4
    assert len(
        await InterviewRepository(session).find(application_id=ctx["app"].id),
    ) == 1


@pytest.mark.asyncio
async def test_cancel_leaves_application_where_it_was(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Cancelling is not a decision about the candidate."""
    ctx = await _setup(session, "c1")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    resp = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/cancel",
        json={"reason": INTERNAL_NOTE},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["interview_status"] == InterviewStatus.CANCELLED.value
    assert resp.json()["application_status_changed"] is False

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value
    # And specifically not a rejection.
    assert app.status != ApplicationStatus.REJECTED.value
    assert app.decision_reason_code is None


@pytest.mark.asyncio
async def test_cancel_is_idempotent(client: AsyncClient, session: AsyncSession) -> None:
    ctx = await _setup(session, "c2")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    url = f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/cancel"

    assert (await client.post(url, json={}, headers=_auth(token))).status_code == 200
    again = await client.post(url, json={}, headers=_auth(token))
    assert again.status_code == 200, again.text
    assert again.json()["interview_status"] == InterviewStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_completed_interview_cannot_be_cancelled(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "c3")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = created["interview_id"]

    done = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{interview_id}/complete",
        json={},
        headers=_auth(token),
    )
    assert done.status_code == 200, done.text

    cancelled = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{interview_id}/cancel",
        json={},
        headers=_auth(token),
    )
    assert cancelled.status_code == 409, cancelled.text


@pytest.mark.asyncio
async def test_complete_records_interviewed_stage(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "k1")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    # The shortlist already recorded a decision, so compare against it: what
    # matters is that *completing the interview* adds no decision of its own.
    before = await JobApplicationRepository(session).get(ctx["app"].id)
    decided_by_before, decided_at_before = before.decided_by, before.decided_at

    resp = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["interview_status"] == InterviewStatus.COMPLETED.value
    assert body["application_status"] == ApplicationStatus.INTERVIEWED.value
    assert body["application_status_changed"] is True

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value
    # A factual stage, not a decision: the completing actor did not decide, and
    # nothing was selected, offered or rejected.
    assert app.decided_by == decided_by_before
    assert app.decided_at == decided_at_before
    assert app.decision_reason_code is None
    assert app.status not in (
        ApplicationStatus.HIRED.value,
        ApplicationStatus.OFFERED.value,
        ApplicationStatus.REJECTED.value,
    )
    assert ApplicationStatus.INTERVIEWED not in DECISION_STATUSES

    rows = (
        await session.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == ctx["app"].id,
                ApplicationStatusHistory.to_status
                == ApplicationStatus.INTERVIEWED.value,
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_complete_is_idempotent(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "k2")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    url = f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete"

    assert (await client.post(url, json={}, headers=_auth(token))).status_code == 200
    again = await client.post(url, json={}, headers=_auth(token))
    assert again.status_code == 200, again.text
    assert again.json()["application_status_changed"] is False

    rows = (
        await session.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == ctx["app"].id,
                ApplicationStatusHistory.to_status
                == ApplicationStatus.INTERVIEWED.value,
            )
        )
    ).scalars().all()
    # Exactly one INTERVIEWED row, so a retried completion cannot duplicate the
    # stage in the candidate's timeline.
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_complete_does_not_regress_a_later_decision(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A completion must not drag an application backwards.

    If the recruiter already offered the candidate, a late interview-completion
    call records the interview but leaves ``offered`` alone.
    """
    ctx = await _setup(session, "k3")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.transition_application(
        ctx["app"].id, ApplicationStatus.OFFERED.value, ctx["recruiter"],
    )

    resp = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["interview_status"] == InterviewStatus.COMPLETED.value
    assert body["application_status_changed"] is False
    assert body["application_status"] == ApplicationStatus.OFFERED.value


# ═════════════════════════════════════════════════════════════════════
# 3. Authorization / tenant isolation
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_outsider_recruiter_cannot_schedule(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A recruiter from another organization is refused, not silently ignored."""
    ctx = await _setup(session, "a1")
    token = await _login(client, ctx["outsider"].email)

    resp = await _schedule(client, session, ctx, token)
    assert resp.status_code == 403, resp.text
    assert await InterviewRepository(session).find(
        application_id=ctx["app"].id,
    ) == []


@pytest.mark.asyncio
async def test_outsider_cannot_read_interview_evidence(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "a2")
    owner_token = await _login(client, ctx["recruiter"].email)
    await _schedule(client, session, ctx, owner_token)

    outsider_token = await _login(client, ctx["outsider"].email)
    resp = await client.get(
        _interviews_url(ctx["app"].id), headers=_auth(outsider_token),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_candidate_cannot_schedule_or_see_evidence(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "a3")
    token = await _login(client, ctx["candidate"].email)

    assert (
        await client.post(
            _interviews_url(ctx["app"].id), json=_schedule_body(), headers=_auth(token),
        )
    ).status_code == 403
    assert (
        await client.get(_interviews_url(ctx["app"].id), headers=_auth(token))
    ).status_code == 403


@pytest.mark.asyncio
async def test_interview_from_another_application_is_not_reachable(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """An interview id from application B cannot be used against application A.

    This is the cross-application IDOR: without scoping the interview lookup to
    the application in the path, a recruiter could read or cancel an interview
    belonging to an application they are looking at.
    """
    first = await _setup(session, "a4")
    second = await _setup(session, "a5")
    token = await _login(client, first["recruiter"].email)

    created = (await _schedule(client, session, first, token)).json()
    other_interview_id = created["interview_id"]

    for suffix, method, body in (
        ("cancel", "post", {}),
        ("complete", "post", {}),
        ("reschedule", "post", {"scheduled_at": _schedule_body()["scheduled_at"]}),
    ):
        resp = await getattr(client, method)(
            f"{_interviews_url(second['app'].id)}/{other_interview_id}/{suffix}",
            json=body,
            headers=_auth(token),
        )
        # The recruiter has no access to ``second`` at all, so the 403 comes
        # from the application authorization, not the interview.
        assert resp.status_code == 403, (suffix, resp.text)

    # And with access to the second application, the interview is still not
    # reachable through it.
    second_token = await _login(client, second["recruiter"].email)
    resp = await client.post(
        f"{_interviews_url(second['app'].id)}/{other_interview_id}/cancel",
        json={},
        headers=_auth(second_token),
    )
    assert resp.status_code == 404, resp.text

    interview = await InterviewRepository(session).get(
        uuid.UUID(other_interview_id)
    )
    assert interview.status == InterviewStatus.SCHEDULED.value


@pytest.mark.asyncio
async def test_candidate_cannot_read_another_candidates_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "a6")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    other_candidate = await _create_user(
        session, "Nosy Candidate", "nosy@test.com",
    )
    await _assign_role(session, other_candidate.id, RoleName.CANDIDATE.value)
    other_token = await _login(client, other_candidate.email)

    resp = await client.get(
        f"/api/v1/interview/{created['interview_id']}", headers=_auth(other_token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_candidate_cannot_read_scorecard_by_id(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Regression: the scorecard endpoint had no authorization at all.

    Any authenticated user could read any interview's scorecard -- including the
    recruiter notes and hiring recommendation -- by supplying an interview id.

    Both audiences are now refused: a candidate who has nothing to do with the
    interview, and the candidate the interview is *about*. The second case is the
    one that matters most -- a scorecard is the interviewer's conclusion, so
    being the subject of the interview cannot be permission to read it.
    """
    from app.domain.models import InterviewScorecard

    ctx = await _setup(session, "a7")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = created["interview_id"]
    url = f"/api/v1/interview/{interview_id}/scorecard"

    # A real scorecard with the private fields that must never escape.
    session.add(
        InterviewScorecard(
            interview_id=uuid.UUID(interview_id),
            overall_score=91,
            technical_skills=90,
            recommendation="strong_hire",
            recruiter_notes="Exceptional depth; private note.",
            ai_summary="Strong hire.",
        )
    )
    await session.flush()

    # Staff who own the job can read it, so the fixture is proven to work and
    # the refusals below are not passing because the scorecard is missing.
    allowed = await client.get(url, headers=_auth(token))
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["recruiter_notes"] == "Exceptional depth; private note."

    other_candidate = await _create_user(
        session, "Other Candidate", "other-candidate@test.com",
    )
    await _assign_role(session, other_candidate.id, RoleName.CANDIDATE.value)
    other_token = await _login(client, other_candidate.email)

    # Someone with no relationship to the interview.
    unrelated = await client.get(url, headers=_auth(other_token))
    assert unrelated.status_code == 403, unrelated.text

    # The candidate it is about. Refused for being the subject, not for their id.
    subject_token = await _login(client, ctx["candidate"].email)
    subject = await client.get(url, headers=_auth(subject_token))
    assert subject.status_code == 403, subject.text
    assert "recruiter_notes" not in subject.text
    assert "strong_hire" not in subject.text

    # And the same candidate reading the interview detail gets no scorecard
    # either -- ownership must not become a back door to the same data.
    detail = await client.get(
        f"/api/v1/interview/{interview_id}", headers=_auth(subject_token),
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["scorecard"] is None
    assert "recruiter_notes" not in detail.text
    assert "strong_hire" not in detail.text
    # The interviewer is not part of the candidate's own record.
    assert body["recruiter_id"] is None
    assert body["recruiter_name"] is None
    # Their own questions and answers are still theirs to see.
    assert body["questions"]

    # Staff still see everything on the same endpoint.
    staff_detail = (await client.get(
        f"/api/v1/interview/{interview_id}", headers=_auth(token),
    )).json()
    assert staff_detail["scorecard"]["recommendation"] == "strong_hire"
    assert staff_detail["recruiter_id"] == str(ctx["recruiter"].id)


@pytest.mark.asyncio
async def test_candidate_scorecard_list_is_tenant_scoped(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Regression: any recruiter could read any candidate's scorecards."""
    ctx = await _setup(session, "a8")
    token = await _login(client, ctx["recruiter"].email)
    await _schedule(client, session, ctx, token)

    outsider_token = await _login(client, ctx["outsider"].email)
    resp = await client.get(
        f"/api/v1/interview/scorecard/{ctx['candidate'].id}",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_legacy_schedule_is_tenant_checked(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Regression: the job+candidate endpoint took any job id.

    It cannot validate the candidate against an application, but it must still
    refuse a job from another tenant.
    """
    ctx = await _setup(session, "a9")
    token = await _login(client, ctx["outsider"].email)

    resp = await client.post(
        "/api/v1/interview/schedule",
        json={
            "job_id": str(ctx["job"].id),
            "candidate_id": str(ctx["candidate"].id),
            "scheduled_at": (
                datetime.now(timezone.utc) + timedelta(days=2)
            ).isoformat(),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


# ═════════════════════════════════════════════════════════════════════
# 4. Candidate view (allowlist)
# ═════════════════════════════════════════════════════════════════════


def _track_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/candidate/jobs/applications/{app_id}"


@pytest.mark.asyncio
async def test_candidate_tracking_reflects_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "v1")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    cand_token = await _login(client, ctx["candidate"].email)
    body = (
        await client.get(_track_url(ctx["app"].id), headers=_auth(cand_token))
    ).json()

    assert body["status"] == ApplicationStatus.INTERVIEW_SCHEDULED.value
    assert body["status_label"] == "Interview Scheduled"

    interview = body["interview"]
    assert interview is not None
    assert interview["interview_id"] == created["interview_id"]
    assert interview["status"] == InterviewStatus.SCHEDULED.value
    assert interview["interview_count"] == 1
    assert interview["has_completed"] is False
    assert interview["scheduled_at"] is not None


@pytest.mark.asyncio
async def test_candidate_tracking_shows_interview_completed_stage(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "v2")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete",
        json={},
        headers=_auth(token),
    )

    cand_token = await _login(client, ctx["candidate"].email)
    body = (
        await client.get(_track_url(ctx["app"].id), headers=_auth(cand_token))
    ).json()

    assert body["status"] == ApplicationStatus.INTERVIEWED.value
    assert body["status_label"] == "Interview Completed"
    assert body["interview"]["has_completed"] is True

    # The progress view gained a distinct "Interview Completed" step, and it is
    # only shown because a history row records it.
    stages = [s["status"] for s in body["stages"]]
    assert ApplicationStatus.INTERVIEWED.value in stages
    assert body["stages"][-1]["is_current"] is True


@pytest.mark.asyncio
async def test_candidate_view_never_exposes_intelligence(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The candidate payload is an allowlist, checked key by key.

    Give the interview a scorecard with a recommendation and private recruiter
    notes, then assert none of it can appear on any candidate endpoint.
    """
    from app.domain.models import HiringRecommendation, InterviewScorecard

    ctx = await _setup(session, "v3", job_title="Platform Engineer")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = uuid.UUID(created["interview_id"])

    session.add(
        InterviewScorecard(
            interview_id=interview_id,
            technical_skills=91,
            communication=88,
            overall_score=90,
            recommendation=HiringRecommendation.STRONGLY_RECOMMEND.value,
            hiring_confidence=95,
            recruiter_notes=INTERNAL_NOTE,
            ai_summary="Exceptional systems thinking.",
        )
    )
    await session.flush()

    cand_token = await _login(client, ctx["candidate"].email)
    track = (
        await client.get(_track_url(ctx["app"].id), headers=_auth(cand_token))
    )
    assert track.status_code == 200, track.text
    raw = track.text

    for forbidden in (
        "overall_score",
        "recommendation",
        "hiring_confidence",
        "recruiter_notes",
        "ai_summary",
        "technical_skills",
        "hiring_confidence",
        "scorecard",
        "evaluation",
        INTERNAL_NOTE,
        "Exceptional systems thinking",
        "strongly_recommend",
    ):
        assert forbidden not in raw, forbidden

    # And the interview sub-object is exactly the allowlist.
    assert set(track.json()["interview"].keys()) == {
        "application_id",
        "interview_id",
        "status",
        "scheduled_at",
        "duration_minutes",
        "completed_at",
        "next_upcoming_at",
        "has_completed",
        "interview_count",
        "message",
    }


@pytest.mark.asyncio
async def test_candidate_tracking_for_other_application_is_indistinguishable(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Another candidate's application id must not be probeable."""
    ctx = await _setup(session, "v4")

    other = await _create_user(session, "Other", "other-v4@test.com")
    await _assign_role(session, other.id, RoleName.CANDIDATE.value)
    token = await _login(client, other.email)

    forbidden = await client.get(_track_url(ctx["app"].id), headers=_auth(token))
    missing = await client.get(
        _track_url(uuid.uuid4()), headers=_auth(token),
    )
    assert forbidden.status_code == missing.status_code == 404
    assert forbidden.json()["error"]["message"] == missing.json()["error"]["message"]


# ═════════════════════════════════════════════════════════════════════
# 5. Evidence, options, audit and notifications
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_evidence_lists_interviews_and_aggregates_scores(
    client: AsyncClient, session: AsyncSession,
) -> None:
    from app.domain.models import InterviewScorecard

    ctx = await _setup(session, "e1")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = uuid.UUID(created["interview_id"])

    session.add(
        InterviewScorecard(
            interview_id=interview_id, overall_score=80, technical_skills=80,
        )
    )
    await session.flush()

    body = (
        await client.get(_interviews_url(ctx["app"].id), headers=_auth(token))
    ).json()

    assert body["interview_count"] == 1
    assert body["completed_count"] == 0
    assert body["job_title"] == "Backend Engineer"

    row = body["interviews"][0]
    assert row["id"] == created["interview_id"]
    assert row["has_scorecard"] is True
    # The scorecard itself is still reported on its own row, so staff can see
    # that one exists and what it says.
    assert row["overall_score"] == 80
    assert row["status"] == InterviewStatus.SCHEDULED.value

    # But the aggregate is over completed interviews only, so a scorecard filed
    # against an interview nobody has taken cannot move the average.
    assert body["average_overall_score"] is None

    # Once the interview is completed the same score counts.
    completed = await client.post(
        f"{_interviews_url(ctx['app'].id)}/{interview_id}/complete",
        json={},
        headers=_auth(token),
    )
    assert completed.status_code == 200, completed.text

    body = (
        await client.get(_interviews_url(ctx["app"].id), headers=_auth(token))
    ).json()
    assert body["completed_count"] == 1
    assert body["average_overall_score"] == 80.0


@pytest.mark.asyncio
async def test_options_reflect_server_side_rules(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "e2")
    token = await _login(client, ctx["recruiter"].email)

    before = (
        await client.get(
            f"{_interviews_url(ctx['app'].id)}/options", headers=_auth(token),
        )
    ).json()
    assert before["can_schedule"] is True
    assert before["schedule_unavailable_reason"] is None
    assert before["has_interviews"] is False
    assert before["current_status"] == ApplicationStatus.SHORTLISTED.value

    created = (await _schedule(client, session, ctx, token)).json()
    after = (
        await client.get(
            f"{_interviews_url(ctx['app'].id)}/options", headers=_auth(token),
        )
    ).json()
    assert after["can_schedule"] is False
    assert after["schedule_unavailable_reason"] == "interview_already_scheduled"
    assert after["active_interview_id"] == created["interview_id"]

    option = after["options"][0]
    assert option["can_reschedule"] is True
    assert option["can_cancel"] is True
    assert option["can_complete"] is True

    # Once completed, only the read-only states remain.
    await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete",
        json={},
        headers=_auth(token),
    )
    done = (
        await client.get(
            f"{_interviews_url(ctx['app'].id)}/options", headers=_auth(token),
        )
    ).json()
    finished = done["options"][0]
    assert finished["can_reschedule"] is False
    assert finished["can_cancel"] is False
    assert finished["can_complete"] is False
    assert finished["reschedule_unavailable_reason"] == "interview_already_finished"


@pytest.mark.asyncio
async def test_options_and_enforcement_agree_in_every_interview_state(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """What the UI offers is exactly what the API will do.

    The affordance projection and the mutating endpoints read the same table, so
    this walks each interview state and checks that every advertised action
    succeeds and that every closed one is refused. A drift between the two would
    show up here as either a 4xx on an offered button or a working action the UI
    hides.
    """
    ctx = await _setup(session, "e2b")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = uuid.UUID(created["interview_id"])
    base = _interviews_url(ctx["app"].id)

    async def _option() -> dict:
        resp = await client.get(f"{base}/options", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        return resp.json()["options"][0]

    async def _move(method: str, suffix: str = "", **body) -> int:
        return (
            await client.request(
                method,
                f"{base}/{interview_id}/{suffix}",
                json=body,
                headers=_auth(token),
            )
        ).status_code

    # An interview that was started is completable; it is the normal end of a
    # real one, and refusing here would strand the application.
    interview = await InterviewRepository(session).get(interview_id)
    interview.status = InterviewStatus.IN_PROGRESS.value
    await session.flush()

    running = await _option()
    assert running["can_complete"] is True
    assert running["complete_unavailable_reason"] is None
    assert running["can_cancel"] is True
    assert await _move("POST", "complete") == 200
    assert (
        await InterviewRepository(session).get(interview_id)
    ).status == InterviewStatus.COMPLETED.value

    # A completed interview is evidence and every mutation is closed, each with
    # the controlled reason the UI needs to explain itself.
    finished = await _option()
    assert (finished["can_reschedule"], finished["can_cancel"], finished["can_complete"]) == (
        False, False, False,
    )
    assert finished["cancel_unavailable_reason"] == "interview_already_finished"
    assert finished["complete_unavailable_reason"] == "interview_already_finished"
    assert await _move("POST", "complete") == 200  # idempotent
    assert await _move("POST", "cancel") == 409
    assert await _move(
        "POST", "reschedule", scheduled_at=_iso(days=9),
    ) == 409


@pytest.mark.asyncio
async def test_rescheduling_a_cancelled_interview_reopens_the_same_row(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A cancellation is reversible, because it is not a decision.

    Reopening keeps the original interview and its questions instead of forcing
    the recruiter to create a second interview for the same application, and the
    application never left INTERVIEW_SCHEDULED.
    """
    ctx = await _setup(session, "e2c")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    interview_id = uuid.UUID(created["interview_id"])
    base = _interviews_url(ctx["app"].id)

    cancelled = await client.post(
        f"{base}/{interview_id}/cancel",
        json={"reason": "interviewer unavailable"},
        headers=_auth(token),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["interview_status"] == InterviewStatus.CANCELLED.value

    options = (
        await client.get(f"{base}/options", headers=_auth(token))
    ).json()["options"][0]
    # Reopening is offered; cancelling again and completing are not.
    assert options["can_reschedule"] is True
    assert options["can_cancel"] is False
    assert options["can_complete"] is False

    # The closed actions are refused, not merely hidden.
    assert (
        await client.post(
            f"{base}/{interview_id}/complete", json={}, headers=_auth(token),
        )
    ).status_code == 409
    # Cancelling again is idempotent rather than an error, so a retry is safe.
    assert (
        await client.post(
            f"{base}/{interview_id}/cancel", json={}, headers=_auth(token),
        )
    ).status_code == 200

    # And the application stays where it was: a cancellation moved no stage.
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value

    reopened = await client.post(
        f"{base}/{interview_id}/reschedule",
        json={"scheduled_at": _iso(days=10)},
        headers=_auth(token),
    )
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["interview_id"] == created["interview_id"]
    assert body["interview_status"] == InterviewStatus.SCHEDULED.value
    assert body["application_status_changed"] is False

    interview = await InterviewRepository(session).get(interview_id)
    assert interview.status == InterviewStatus.SCHEDULED.value
    # One interview, still carrying its original questions.
    assert len(
        await InterviewRepository(session).find(application_id=ctx["app"].id),
    ) == 1
    assert await _count_questions(session, interview.id) == 4

    # The reopen is auditable, including the status it came from.
    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.INTERVIEW_RESCHEDULED.value,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].details["previous_interview_status"] == (
        InterviewStatus.CANCELLED.value
    )
    assert rows[0].details["reopened_from_cancelled"] is True


@pytest.mark.asyncio
async def test_audit_records_interview_events_with_application_link(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "e3")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()
    await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete",
        json={},
        headers=_auth(token),
    )

    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.INTERVIEW_SCHEDULED.value,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.organization_id == ctx["org"].id
    assert row.resource_type == "interview"
    assert row.resource_id == created["interview_id"]
    # The trail links the interview to the application it belongs to.
    assert row.details["application_id"] == str(ctx["app"].id)
    assert row.details["job_id"] == str(ctx["job"].id)

    completed = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.INTERVIEW_COMPLETED.value,
            )
        )
    ).scalars().all()
    assert len(completed) == 1

    # And the status change itself is audited by the lifecycle service, so the
    # application trail is unchanged by Phase 11. Filtered in Python because a
    # JSON containment predicate is not portable across the test's SQLite build.
    all_status_changes = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type
                == AuditEventType.APPLICATION_STATUS_CHANGED.value,
            )
        )
    ).scalars().all()
    assert any(
        row.details["to"] == ApplicationStatus.INTERVIEWED.value
        and row.resource_id == str(ctx["app"].id)
        for row in all_status_changes
    )


@pytest.mark.asyncio
async def test_notifications_are_queued_after_commit(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "e4", job_title="Platform Engineer")
    token = await _login(client, ctx["recruiter"].email)

    created = (await _schedule(client, session, ctx, token)).json()
    assert len(captured_notifications) == 1
    sent = captured_notifications[0]
    assert str(sent["interview_id"]) == created["interview_id"]
    assert sent["candidate_id"] == ctx["candidate"].id
    assert sent["event"] == "scheduled"
    assert "Platform Engineer" in sent["candidate_message"]

    await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/complete",
        json={},
        headers=_auth(token),
    )
    assert [n["event"] for n in captured_notifications] == ["scheduled", "completed"]


@pytest.mark.asyncio
async def test_cancellation_reason_never_reaches_the_candidate(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "e5")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    await client.post(
        f"{_interviews_url(ctx['app'].id)}/{created['interview_id']}/cancel",
        json={"reason": INTERNAL_NOTE},
        headers=_auth(token),
    )

    assert len(captured_notifications) == 2
    message = captured_notifications[1]["candidate_message"]
    assert INTERNAL_NOTE not in message
    assert "cancel" in message.lower()

    cand_token = await _login(client, ctx["candidate"].email)
    track = await client.get(_track_url(ctx["app"].id), headers=_auth(cand_token))
    assert INTERNAL_NOTE not in track.text


@pytest.mark.asyncio
async def test_notification_delivery_is_deduplicated(session: AsyncSession) -> None:
    """Two dispatchers for the same interview event collapse onto one row."""
    from app.services.interview.application_interview_notification import (
        deliver_interview_notification,
    )

    candidate = await _create_user(session, "Notif", "notif-dedupe@test.com")
    interview_id = uuid.uuid4()

    first = await deliver_interview_notification(
        session,
        interview_id=interview_id,
        candidate_id=candidate.id,
        event="scheduled",
        candidate_message="An interview has been scheduled.",
    )
    second = await deliver_interview_notification(
        session,
        interview_id=interview_id,
        candidate_id=candidate.id,
        event="scheduled",
        candidate_message="An interview has been scheduled.",
    )
    assert first is True
    assert second is False

    rows = (
        await session.execute(
            select(Notification).where(
                Notification.dedupe_key
                == interview_dedupe_key(interview_id, "scheduled"),
            )
        )
    ).scalars().all()
    assert len(rows) == 1

    # A different event on the same interview is a different notification.
    assert (
        await deliver_interview_notification(
            session,
            interview_id=interview_id,
            candidate_id=candidate.id,
            event="completed",
            candidate_message="Your interview has been completed.",
        )
        is True
    )


@pytest.mark.asyncio
async def test_schedule_commits_once_so_the_two_writes_are_atomic(
    client: AsyncClient, session: AsyncSession, monkeypatch,
) -> None:
    """The interview row and the status flip are one unit of work.

    Both land in the same transaction, so a failure anywhere in the request
    cannot leave a scheduled interview attached to an application still marked
    shortlisted. Atomicity here is the *absence of an intermediate commit*, so
    that is what is measured: the request must flush all of its work -- the
    interview, the application status, the status history and the audit rows --
    and commit exactly once at the end.

    A session-level rollback cannot be used to demonstrate this. The whole test
    suite shares one connection under an outer transaction, so rolling the
    session back would discard this test's setup along with the request and
    prove nothing about the request itself.
    """
    ctx = await _setup(session, "e6")
    token = await _login(client, ctx["recruiter"].email)

    commits: list[None] = []
    real_commit = session.commit

    async def _counting_commit() -> None:
        commits.append(None)
        await real_commit()

    monkeypatch.setattr(session, "commit", _counting_commit)

    resp = await client.post(
        _interviews_url(ctx["app"].id),
        json=_schedule_body(),
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    assert len(commits) == 1, "the schedule must not commit before it is done"

    monkeypatch.undo()
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value
    assert len(
        await InterviewRepository(session).find(application_id=ctx["app"].id),
    ) == 1


@pytest.mark.asyncio
async def test_interview_without_application_is_preserved(
    session: AsyncSession,
) -> None:
    """A practice/mock interview keeps a NULL application.

    ``application_id`` is nullable on purpose, so adding the link cannot break
    the mock interview flow.
    """
    ctx = await _setup(session, "e7")
    mock = Interview(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        recruiter_id=None,
        interview_type="mock",
        status=InterviewStatus.SCHEDULED.value,
        total_questions=0,
        questions_answered=0,
    )
    session.add(mock)
    await session.flush()
    await session.refresh(mock)

    assert mock.application_id is None
    # And it is invisible to the application evidence view.
    assert await InterviewRepository(session).list_by_application(
        ctx["app"].id
    ) == []


@pytest.mark.asyncio
async def test_candidate_keeps_their_own_mock_feedback_but_not_a_real_evaluation(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The narrowing is by interview type, not a blanket hide.

    A mock interview is a practice product: reading the AI feedback on their own
    answers is the entire point, so withholding it would break the feature. A
    recruiter-scheduled interview is real hiring, and its evaluations are the
    interviewer's assessment of the candidate rather than the candidate's own
    work. The scorecard is withheld in both cases.
    """
    from app.domain.enums import InterviewType
    from app.domain.models import (
        InterviewAnswer,
        InterviewEvaluation,
        InterviewQuestion,
    )

    ctx = await _setup(session, "s1")
    candidate_token = await _login(client, ctx["candidate"].email)
    recruiter_token = await _login(client, ctx["recruiter"].email)

    real = (await _schedule(client, session, ctx, recruiter_token)).json()
    real_id = uuid.UUID(real["interview_id"])
    mock = Interview(
        id=uuid.uuid4(),
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        recruiter_id=None,
        interview_type=InterviewType.MOCK.value,
        status=InterviewStatus.COMPLETED.value,
        duration_minutes=60,
        total_questions=1,
        questions_answered=1,
    )
    session.add(mock)
    await session.flush()
    question = InterviewQuestion(
        id=uuid.uuid4(),
        interview_id=mock.id,
        question_text="Explain a race condition.",
        category="technical",
        difficulty="medium",
        order_index=0,
    )
    session.add(question)
    await session.flush()
    answer = InterviewAnswer(
        id=uuid.uuid4(),
        question_id=question.id,
        answer_text="Two threads touching shared state.",
        time_taken_seconds=90,
    )
    session.add(answer)
    await session.flush()
    session.add(
        InterviewEvaluation(
            id=uuid.uuid4(),
            answer_id=answer.id,
            overall_score=70,
            technical_accuracy=70,
            feedback="Reasonable but shallow.",
        )
    )
    await session.flush()
    await session.refresh(mock)

    mock_detail = (
        await client.get(
            f"/api/v1/interview/{mock.id}", headers=_auth(candidate_token),
        )
    ).json()
    # The candidate keeps their own practice feedback...
    assert mock_detail["questions"][0]["answer"]["evaluation"]["feedback"] == (
        "Reasonable but shallow."
    )
    # ...but still no scorecard and still no interviewer.
    assert mock_detail["scorecard"] is None
    assert mock_detail["recruiter_name"] is None

    # Now the same shape on a real interview: the candidate keeps the question and
    # their own answer, and loses the interviewer's evaluation of it.
    real_question = await session.execute(
        select(InterviewQuestion).where(InterviewQuestion.interview_id == real_id)
    )
    real_q = real_question.scalars().first()
    real_answer = InterviewAnswer(
        id=uuid.uuid4(),
        question_id=real_q.id,
        answer_text="A real hiring answer.",
        time_taken_seconds=60,
    )
    session.add(real_answer)
    await session.flush()
    session.add(
        InterviewEvaluation(
            id=uuid.uuid4(),
            answer_id=real_answer.id,
            overall_score=40,
            technical_accuracy=40,
            feedback="Weak; would not progress.",
        )
    )
    await session.flush()

    candidate_view = (
        await client.get(
            f"/api/v1/interview/{real_id}", headers=_auth(candidate_token),
        )
    ).json()
    answer_payload = next(
        q["answer"] for q in candidate_view["questions"] if q["answer"]
    )
    assert answer_payload["answer_text"] == "A real hiring answer."
    assert answer_payload["evaluation"] is None
    assert "would not progress" not in str(candidate_view)

    # The same evaluation is still there for staff, so nothing was destroyed.
    staff_view = (
        await client.get(
            f"/api/v1/interview/{real_id}", headers=_auth(recruiter_token),
        )
    ).json()
    staff_answers = [q["answer"] for q in staff_view["questions"] if q["answer"]]
    assert any(
        a["evaluation"] and a["evaluation"]["overall_score"] == 40
        for a in staff_answers
    )


@pytest.mark.asyncio
async def test_interview_analytics_is_scoped_to_the_caller(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Aggregate reporting must not cross a tenant boundary.

    ``/interview/analytics`` previously passed ``recruiter_id=None`` for HR, and
    the analytics engine's fallback for that case called ``uuid.UUID(int())`` with
    no argument -- so an HR caller got a 500. Removing the filter instead would
    have handed one tenant every other tenant's interview scores and
    recommendations, so the scope is now resolved from the jobs the caller may read.
    """
    ctx = await _setup(session, "s2")
    await _schedule(client, session, ctx, await _login(client, ctx["recruiter"].email))

    recruiter_token = await _login(client, ctx["recruiter"].email)
    own = await client.get("/api/v1/interview/analytics", headers=_auth(recruiter_token))
    assert own.status_code == 200, own.text
    assert own.json()["total_interviews"] == 1

    # An HR user in the same organization sees the same report, resolved through
    # job access rather than by accident. "hr" is a seeded role that predates the
    # RoleName enum, and it is the non-recruiter branch this test needs.
    hr = await _create_user(session, "Org HR", "org-hr@test.com")
    await _assign_role(session, hr.id, "hr")
    session.add(
        OrganizationMembership(
            user_id=hr.id,
            organization_id=ctx["org"].id,
            role="hr",
            status=MembershipStatus.ACTIVE.value,
        )
    )
    await session.flush()
    hr_token = await _login(client, hr.email)

    hr_report = await client.get("/api/v1/interview/analytics", headers=_auth(hr_token))
    assert hr_report.status_code == 200, hr_report.text
    assert hr_report.json()["total_interviews"] == 1

    # An HR user from a different organization sees none of it. The endpoint must
    # answer with an empty report rather than an error or, worse, the other
    # tenant's numbers.
    outsider_hr = await _create_user(session, "Outsider HR", "outsider-hr@test.com")
    await _assign_role(session, outsider_hr.id, "hr")
    other_org = await _create_org(session, "Other Co", "other-co")
    session.add(
        OrganizationMembership(
            user_id=outsider_hr.id,
            organization_id=other_org.id,
            role="hr",
            status=MembershipStatus.ACTIVE.value,
        )
    )
    await session.flush()
    outsider_token = await _login(client, outsider_hr.email)

    outsider_report = await client.get(
        "/api/v1/interview/analytics", headers=_auth(outsider_token),
    )
    assert outsider_report.status_code == 200, outsider_report.text
    assert outsider_report.json()["total_interviews"] == 0


@pytest.mark.asyncio
async def test_interview_analytics_aggregates_a_completed_answered_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A completed interview with evaluated answers must aggregate, not 500.

    The analytics engine used to walk the ``question.answer.evaluation``
    relationship chain off freshly selected questions. That chain is lazily
    loaded, and a lazy load raises MissingGreenlet in an async session -- so
    any recruiter with a single completed, answered interview got a 500 from
    ``/interview/analytics``, and the Interview Analytics page showed only its
    generic "Failed to load analytics" error. The empty report still worked,
    which is why the breakage stayed invisible until real interviews existed.

    The categories are now selected with an explicit join; this test pins both
    that the endpoint survives a completed, evaluated interview and the
    numbers it reports for one.
    """
    from app.domain.models import (
        InterviewAnswer,
        InterviewEvaluation,
        InterviewQuestion,
        InterviewScorecard,
    )

    ctx = await _setup(session, "s2-analytics")
    token = await _login(client, ctx["recruiter"].email)
    resp = await _schedule(client, session, ctx, token)
    assert resp.status_code == 201, resp.text
    interview_id = uuid.UUID(resp.json()["interview_id"])

    interview = await session.get(Interview, interview_id)
    assert interview is not None
    interview.status = InterviewStatus.COMPLETED.value
    interview.completed_at = datetime.now(timezone.utc)

    question = InterviewQuestion(
        interview_id=interview_id,
        question_text="Tell me about caching.",
        category="technical",
        difficulty="medium",
        order_index=0,
    )
    session.add(question)
    await session.flush()
    answer = InterviewAnswer(question_id=question.id, answer_text="Cache-aside.")
    session.add(answer)
    await session.flush()
    session.add(InterviewEvaluation(
        answer_id=answer.id,
        technical_accuracy=80, completeness=80, communication=80,
        problem_solving=80, confidence=80, relevance=80, overall_score=82,
    ))
    session.add(InterviewScorecard(
        interview_id=interview_id,
        technical_skills=80, communication=80, teamwork=80, leadership=80,
        problem_solving=80, culture_fit=80, learning_ability=80,
        overall_score=82, recommendation="recommend", hiring_confidence=70,
    ))
    await session.flush()
    # A production request always reads from the database: nothing about the
    # interview graph may be served from this test's identity map.
    session.expire_all()

    report = await client.get("/api/v1/interview/analytics", headers=_auth(token))
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["total_interviews"] == 1
    assert body["completion_rate"] == 100.0
    assert body["average_score"] == 82
    assert body["category_averages"] == {"technical": 82.0}
    assert body["recommendation_breakdown"]["recommend"] == 1


# --- The application link is exposed on interview reads -----------
#
# The interview detail and list payloads now carry `application_id`. Without it a
# recruiter looking at an interview has an interview id but nothing tying it to
# the application it came from, which is the id they would have to quote to
# support. The column was already on the row; this only makes it readable.


@pytest.mark.asyncio
async def test_interview_detail_reports_its_application(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "i1")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    resp = await client.get(
        f"/api/v1/interview/{created['interview_id']}", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["application_id"] == str(ctx["app"].id)
    # The rest of the link is unchanged, and still agrees with the application.
    assert body["job_id"] == str(ctx["job"].id)
    assert body["candidate_id"] == str(ctx["candidate"].id)


@pytest.mark.asyncio
async def test_candidate_sees_the_application_id_on_their_own_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The candidate's narrowed view still carries the reference.

    It is their own application, and it is the number they are told to quote, so
    withholding it here would leave them with the interview id and nothing else.
    """
    ctx = await _setup(session, "i2")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    candidate_token = await _login(client, ctx["candidate"].email)
    resp = await client.get(
        f"/api/v1/interview/{created['interview_id']}",
        headers=_auth(candidate_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["application_id"] == str(ctx["app"].id)


@pytest.mark.asyncio
async def test_application_id_is_null_for_an_interview_with_no_application(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A practice interview reports null rather than omitting the key.

    The field is nullable by design, and the schema has to say so: a client
    branching on whether the key is present would get the wrong answer here.
    """
    ctx = await _setup(session, "i3")
    mock = Interview(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        recruiter_id=None,
        interview_type="mock",
        status=InterviewStatus.SCHEDULED.value,
        total_questions=0,
        questions_answered=0,
    )
    session.add(mock)
    await session.flush()
    await session.refresh(mock)

    token = await _login(client, ctx["recruiter"].email)
    resp = await client.get(
        f"/api/v1/interview/{mock.id}", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    assert "application_id" in resp.json()
    assert resp.json()["application_id"] is None


@pytest.mark.asyncio
async def test_interview_list_carries_the_application_id(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "i4")
    token = await _login(client, ctx["recruiter"].email)
    created = (await _schedule(client, session, ctx, token)).json()

    resp = await client.get("/api/v1/interview/list", headers=_auth(token))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["items"], "the scheduled interview should be listed"
    assert body["total"] == len(body["items"])
    row = next(r for r in body["items"] if r["id"] == created["interview_id"])
    assert row["application_id"] == str(ctx["app"].id)


@pytest.mark.asyncio
async def test_listing_an_interview_does_not_widen_tenant_visibility(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """`application_id` came from the row, so it must not become a leak.

    The added field is derived from an interview the caller is already allowed to
    see. A recruiter from another organization must still see an empty list, and
    must not be able to learn an application id by reading one.
    """
    ctx = await _setup(session, "i5")
    token = await _login(client, ctx["recruiter"].email)
    await _schedule(client, session, ctx, token)

    outsider = await _create_user(session, "Outsider", "outsider-list@test.com")
    await _assign_role(session, outsider.id, "recruiter")
    session.add(
        OrganizationMembership(
            user_id=outsider.id,
            organization_id=(await _create_org(session, "Elsewhere", "elsewhere")).id,
            role="recruiter",
            status=MembershipStatus.ACTIVE.value,
        )
    )
    await session.flush()
    outsider_token = await _login(client, outsider.email)

    resp = await client.get("/api/v1/interview/list", headers=_auth(outsider_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
