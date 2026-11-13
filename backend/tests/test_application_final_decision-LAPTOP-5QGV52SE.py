"""Tests for the Phase 13 final selection decision.

Contract under test:
- Selection is an explicit, human decision recorded through the decision
  endpoint. No screening score, AI recommendation, interview result or
  assessment result can produce one.
- ``select`` is a distinct outcome from being hired: it moves the application
  to ``selected``, never to ``hired`` or ``offered``.
- ``selected`` is non-terminal. The recruiter can still extend the offer or the
  process can still fall through, so selection never implies a job.
- The deciding actor and time are recorded, the immutable history gains a row,
  and a dedicated ``application_selected`` audit event is written.
- The candidate-facing projection states the selection without claiming a hire
  and never leaks the private recruiter note.
- The notification is delivered after commit in its own session and is
  de-duplicated, and a notification failure cannot corrupt the decision.
- Authorization is server-side and a repeated selection is rejected with 409.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    AuditEventType,
    EmploymentType,
    JobStatus,
    MembershipStatus,
    RejectionReason,
    RoleName,
    ScreeningStatus,
)
from app.domain.models import (
    ApplicationStatusHistory,
    AuditLog,
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    Role,
    User,
    UserRole,
)
from app.repositories.jobs.job import JobApplicationRepository
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
)

PASSWORD = "Passw0rd!"

# A legal route to each status a final selection can be made from. Selection is
# never offered from APPLIED or UNDER_REVIEW: those are pre-review states, and
# a positive final decision out of them would bypass reviewing entirely.
PATHS: dict[ApplicationStatus, list[ApplicationStatus]] = {
    ApplicationStatus.UNDER_REVIEW: [ApplicationStatus.UNDER_REVIEW],
    ApplicationStatus.SHORTLISTED: [ApplicationStatus.SHORTLISTED],
    ApplicationStatus.INTERVIEW_SCHEDULED: [
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED,
    ],
    ApplicationStatus.INTERVIEWED: [
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.INTERVIEWED,
    ],
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _assign_role(session: AsyncSession, user_id, role: str) -> None:
    role_row = (
        await session.execute(select(Role).where(Role.name == role))
    ).scalar_one_or_none()
    if role_row is None:
        role_row = Role(id=uuid.uuid4(), name=role, description=role)
        session.add(role_row)
        await session.flush()
    existing = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_row.id,
            ),
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(UserRole(user_id=user_id, role_id=role_row.id))
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


async def _setup(
    session: AsyncSession,
    suffix: str,
    *,
    status: ApplicationStatus = ApplicationStatus.INTERVIEWED,
    job_title: str = "Backend Engineer",
):
    """Org + owning recruiter + candidate + published job + application."""
    org = Organization(
        name=f"Org {suffix}", slug=f"org-{suffix}",
        description="demo", status="active",
    )
    session.add(org)
    await session.flush()

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
    await _add_membership(session, recruiter, org.id, "recruiter")
    # The outsider is a recruiter too, but of a different organization.
    await _add_membership(session, outsider, uuid.uuid4(), "recruiter")

    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title=job_title,
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

    app = JobApplication(
        job_id=job.id, candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()

    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(app, actor=candidate)
    for step in PATHS.get(status, []):
        await lifecycle.transition_application(app.id, step.value, recruiter)
    await session.refresh(app)
    assert app.status == status.value
    return {
        "org": org,
        "recruiter": recruiter,
        "candidate": candidate,
        "outsider": outsider,
        "job": job,
        "app": app,
    }


def _decision_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/recruiter/jobs/applications/{app_id}/decision"


def _options_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/recruiter/jobs/applications/{app_id}/decision-options"


def _history_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/recruiter/jobs/applications/{app_id}/decision-history"


def _candidate_decision_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/candidate/jobs/applications/{app_id}/decision"


def _candidate_track_url(app_id: uuid.UUID) -> str:
    return f"/api/v1/candidate/jobs/applications/{app_id}"


def _candidate_decisions_url() -> str:
    return "/api/v1/candidate/jobs/applications/decisions"


@pytest.fixture
def captured_notifications(monkeypatch):
    """Capture what the post-commit dispatcher was asked to send.

    The real dispatcher opens its own session against the configured database,
    not the in-memory test database, so it is replaced with a recorder.
    """
    captured: list[dict] = []

    async def _fake(application_id, candidate_id, status, candidate_message):
        captured.append(
            {
                "application_id": application_id,
                "candidate_id": candidate_id,
                "status": status,
                "candidate_message": candidate_message,
            }
        )

    import app.services.applications.application_decision_notification as mod

    monkeypatch.setattr(mod, "_deliver_with_own_session", _fake)
    return captured


# ── The positive decision ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_select_moves_status_and_records_the_decider(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "p1", job_title="Platform Engineer")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select", "internal_note": "Best evidence set"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "selected"
    assert body["previous_status"] == "interviewed"
    assert body["changed_status"] is True
    # A selection is a positive decision and needs no rejection reason.
    assert body["rejection_reason"] is None
    assert body["candidate_status_label"] == "Selected"

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.SELECTED.value
    # Who chose, and when, is the point of the decision.
    assert app.decided_by == ctx["recruiter"].id
    assert app.decided_at is not None
    assert app.decision_reason_code is None

    assert len(captured_notifications) == 1
    assert captured_notifications[0]["status"] is ApplicationStatus.SELECTED
    assert "selected" in captured_notifications[0]["candidate_message"].lower()


@pytest.mark.asyncio
async def test_select_is_not_hired_and_not_offered(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Selection must never be silently collapsed into being hired."""
    ctx = await _setup(session, "p2")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "selected"
    assert body["status"] not in {"hired", "offered"}


@pytest.mark.asyncio
async def test_select_writes_history_and_a_dedicated_audit_event(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p3")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    records = (
        await session.execute(
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id == ctx["app"].id)
            .order_by(ApplicationStatusHistory.changed_at),
        )
    ).scalars().all()
    latest = records[-1]
    assert latest.from_status == ApplicationStatus.INTERVIEWED.value
    assert latest.to_status == ApplicationStatus.SELECTED.value
    assert (latest.metadata_json or {}).get("decision") == "select"

    events = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.APPLICATION_SELECTED.value,
                AuditLog.resource_id == str(ctx["app"].id),
            ),
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].user_id == ctx["recruiter"].id
    assert events[0].details["decision"] == "select"
    assert events[0].details["status"] == "selected"
    # The private note must not be copied into audit details.
    assert "Best evidence" not in str(events[0].details)


@pytest.mark.asyncio
async def test_selection_is_available_from_the_evidence_stages(
    client: AsyncClient, session: AsyncSession,
) -> None:
    for suffix, status in (
        ("short", ApplicationStatus.SHORTLISTED),
        ("sched", ApplicationStatus.INTERVIEW_SCHEDULED),
        ("done", ApplicationStatus.INTERVIEWED),
    ):
        ctx = await _setup(session, f"o{suffix}", status=status)
        token = await _login(client, ctx["recruiter"].email)
        resp = await client.get(
            _options_url(ctx["app"].id), headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        options = {
            o["decision"]: o
            for o in resp.json()["options"]
        }
        assert "select" in options, resp.text
        assert options["select"]["available"] is True, (status, resp.text)
        assert options["select"]["target_status"] == "selected"


@pytest.mark.asyncio
async def test_selection_is_refused_before_review_starts(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A positive final decision cannot be made from a pre-review status."""
    for suffix, status in (
        ("a", ApplicationStatus.APPLIED),
        ("u", ApplicationStatus.UNDER_REVIEW),
    ):
        ctx = await _setup(session, f"p{suffix}", status=status)
        token = await _login(client, ctx["recruiter"].email)
        resp = await client.get(
            _options_url(ctx["app"].id), headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        options = {
            o["decision"]: o
            for o in resp.json()["options"]
        }
        assert options["select"]["available"] is False, (status, resp.text)
        # The server explains itself rather than silently hiding the option.
        assert options["select"]["unavailable_reason"]

        # And posting it anyway is refused.
        post = await client.post(
            _decision_url(ctx["app"].id),
            json={"decision": "select"}, headers=_auth(token),
        )
        assert post.status_code == 409, (status, post.text)


@pytest.mark.asyncio
async def test_rejection_reason_is_refused_on_a_selection(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p4")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select", "rejection_reason": "low_job_match"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value


# ── Human control, authorization, idempotency ───────────────────────────

@pytest.mark.asyncio
async def test_completed_screening_never_selects_a_candidate(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    """The automated screening path must not reach the positive decision.

    The screening worker writes ``screening_status``/``screening_completed_at``
    and a score. None of that may move the application, so the state is set
    exactly as the worker would leave it and the lifecycle is then checked.
    """
    ctx = await _setup(session, "p5")
    lifecycle = ApplicationLifecycleService(session)
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    app.screening_status = ScreeningStatus.COMPLETED.value
    app.screening_completed_at = datetime.now(timezone.utc)
    await session.flush()

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    # A completed screening is decision support, never a decision.
    assert app.screening_status == ScreeningStatus.COMPLETED.value
    assert app.status == ApplicationStatus.INTERVIEWED.value
    assert captured_notifications == []

    selected_audit = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.APPLICATION_SELECTED.value,
            ),
        )
    ).scalars().all()
    assert selected_audit == []

    # Selection still requires an explicit, separately authorized call.
    token = await _login(client, ctx["recruiter"].email)
    options = await client.get(
        _options_url(ctx["app"].id), headers=_auth(token),
    )
    assert options.status_code == 200, options.text
    assert app.status != ApplicationStatus.SELECTED.value
    assert lifecycle is not None


@pytest.mark.asyncio
async def test_reaching_interviewed_never_selects_a_candidate(
    session: AsyncSession,
) -> None:
    """INTERVIEWED is a factual stage; it records no selection."""
    ctx = await _setup(session, "p6")
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value

    selected_audit = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.APPLICATION_SELECTED.value,
                AuditLog.resource_id == str(ctx["app"].id),
            ),
        )
    ).scalars().all()
    assert selected_audit == []


@pytest.mark.asyncio
async def test_candidate_cannot_select_themselves(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p7")
    token = await _login(client, ctx["candidate"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert resp.status_code in (401, 403), resp.text
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value


@pytest.mark.asyncio
async def test_recruiter_from_another_org_cannot_select(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p8")
    token = await _login(client, ctx["outsider"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.INTERVIEWED.value


@pytest.mark.asyncio
async def test_repeated_selection_is_409_and_writes_one_outcome(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "p9")
    token = await _login(client, ctx["recruiter"].email)

    first = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert second.status_code == 409, second.text

    selections = (
        await session.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == ctx["app"].id,
                ApplicationStatusHistory.to_status
                == ApplicationStatus.SELECTED.value,
            ),
        )
    ).scalars().all()
    assert len(selections) == 1
    assert len(captured_notifications) == 1


@pytest.mark.asyncio
async def test_selection_survives_a_failing_notification(
    client: AsyncClient, session: AsyncSession, monkeypatch,
) -> None:
    """A broken dispatcher must not undo a committed selection."""
    ctx = await _setup(session, "p10")
    token = await _login(client, ctx["recruiter"].email)

    async def _boom(*args, **kwargs):
        raise RuntimeError("notification backend is down")

    import app.services.applications.application_decision_notification as mod

    monkeypatch.setattr(mod, "_deliver_with_own_session", _boom)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.SELECTED.value
    assert app.decided_by == ctx["recruiter"].id


# ── Selected is a real, non-terminal stage ─────────────────────────────

@pytest.mark.asyncio
async def test_selected_still_allows_an_offer_or_a_fallback_rejection(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Selection is not final: the process can still move on from it."""
    ctx = await _setup(session, "p11")
    token = await _login(client, ctx["recruiter"].email)
    selected = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert selected.status_code == 200, selected.text

    options = await client.get(
        _options_url(ctx["app"].id), headers=_auth(token),
    )
    assert options.status_code == 200, options.text
    body = options.json()
    # Not final: the recruiter may still act.
    assert body["status_is_final"] is False

    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.transition_application(
        ctx["app"].id, ApplicationStatus.OFFERED.value, ctx["recruiter"],
    )
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.OFFERED.value


@pytest.mark.asyncio
async def test_selected_falls_through_to_rejected_with_a_reason(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A selection can still be withdrawn by a real rejection decision."""
    ctx = await _setup(session, "p12")
    token = await _login(client, ctx["recruiter"].email)
    selected = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert selected.status_code == 200, selected.text

    rejected = await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": RejectionReason.POSITION_FILLED.value,
        },
        headers=_auth(token),
    )
    assert rejected.status_code == 200, rejected.text

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.REJECTED.value
    assert app.decision_reason_code == RejectionReason.POSITION_FILLED.value


@pytest.mark.asyncio
async def test_candidate_can_still_withdraw_after_being_selected(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p13")
    token = await _login(client, ctx["recruiter"].email)
    selected = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(token),
    )
    assert selected.status_code == 200, selected.text

    cand_token = await _login(client, ctx["candidate"].email)
    track = await client.get(
        _candidate_track_url(ctx["app"].id), headers=_auth(cand_token),
    )
    assert track.status_code == 200, track.text
    assert track.json()["can_withdraw"] is True


# ── Candidate-safe projection ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_candidate_sees_selected_without_claiming_a_hire(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p14", job_title="Platform Engineer")
    rec_token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select", "internal_note": "SECRET NOTE"},
        headers=_auth(rec_token),
    )

    cand_token = await _login(client, ctx["candidate"].email)
    resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(cand_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "selected"
    assert body["status_label"] == "Selected"
    assert body["decision_outcome"] == "selected"
    # Selected is not final and is not a hire.
    assert body["is_decision_final"] is False
    assert "hired" not in body["candidate_message"].lower()
    assert "offer" not in body["candidate_message"].lower()
    assert "Platform Engineer" in body["candidate_message"]
    # The private note never reaches the candidate.
    assert "SECRET NOTE" not in resp.text
    assert "internal_note" not in body


@pytest.mark.asyncio
async def test_internal_note_absent_from_every_candidate_surface(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p15")
    rec_token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select", "internal_note": "DO NOT LEAK"},
        headers=_auth(rec_token),
    )

    cand_token = await _login(client, ctx["candidate"].email)
    for url in (
        _candidate_decision_url(ctx["app"].id),
        _candidate_track_url(ctx["app"].id),
        _candidate_decisions_url(),
    ):
        resp = await client.get(url, headers=_auth(cand_token))
        assert resp.status_code == 200, (url, resp.text)
        assert "DO NOT LEAK" not in resp.text, url
        assert "internal_note" not in resp.text, url


@pytest.mark.asyncio
async def test_candidate_cannot_read_another_candidates_selection(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p16")
    other = await _setup(session, "p16b")
    rec_token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(rec_token),
    )

    # The other candidate must not be able to read this decision by id.
    other_token = await _login(client, other["candidate"].email)
    resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(other_token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_tracking_progress_includes_selection(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p17")
    rec_token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select"}, headers=_auth(rec_token),
    )

    cand_token = await _login(client, ctx["candidate"].email)
    resp = await client.get(
        _candidate_track_url(ctx["app"].id), headers=_auth(cand_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    statuses = [s["status"] for s in body["stages"]]
    assert "selected" in statuses
    assert body["status"] == "selected"
    # It is not the final stage: the offer and hire steps are still ahead.
    assert body["stages"][-1]["status"] == "selected"
    assert "selected" not in {
        e["status"] for e in body["timeline"][:-1]
    }


# ── Staff history ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decision_history_shows_the_selection_to_staff_only(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p18")
    rec_token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "select", "internal_note": "Chose on evidence"},
        headers=_auth(rec_token),
    )

    resp = await client.get(
        _history_url(ctx["app"].id), headers=_auth(rec_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "selected"
    entry = body["history"][-1]
    assert entry["decision"] == "select"
    assert entry["to_status"] == "selected"
    # Staff see the note; the candidate never does.
    assert entry["internal_note"] == "Chose on evidence"

    cand_token = await _login(client, ctx["candidate"].email)
    forbidden = await client.get(
        _history_url(ctx["app"].id), headers=_auth(cand_token),
    )
    assert forbidden.status_code in (401, 403, 404), forbidden.text
