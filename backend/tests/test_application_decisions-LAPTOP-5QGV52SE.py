"""Tests for the Phase 8 recruiter decision workflow.

Contract under test:
- Decisions are explicit and human: keep under review, shortlist, reject. No
  screening score, AI recommendation or fairness metric can produce one.
- Rejection requires a controlled ``RejectionReason``; a reason on a
  non-rejection decision is rejected.
- The candidate-facing reason is a fixed projection of the reason code. The
  internal recruiter note never reaches a candidate on any endpoint.
- Status, decision history and audit are written together; the candidate
  notification is delivered afterwards in its own session and is de-duplicated.
- Authorization is server-side: job owner or active org staff only, a candidate
  can never decide, and a candidate can never read another candidate's
  decision.
- Illegal and repeated decisions fail with 409 and write nothing twice.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
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
)
from app.domain.models import (
    ApplicationStatusHistory,
    AuditLog,
    Job,
    JobApplication,
    Notification,
    Organization,
    OrganizationMembership,
    User,
)
from app.repositories.jobs.job import (
    ApplicationStatusHistoryRepository,
    JobApplicationRepository,
)
from app.repositories.user import UserRepository
from app.services.applications.application_decision_notification import (
    decision_dedupe_key,
    deliver_decision_notification,
)
from app.services.applications.application_decision_service import (
    ApplicationDecisionService,
)
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
)
from app.domain.application_decision_schemas import (
    ApplicationDecisionCreate,
    candidate_status_message,
)

PASSWORD = "Decision@12345"
INTERNAL_NOTE = "INTERNAL-ONLY-9f2c private recruiter note"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
    existing = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(UserRole(user_id=user_id, role_id=role.id))
        await session.flush()


async def _create_user(
    session: AsyncSession, name: str, email: str,
) -> User:
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


async def _create_org(session: AsyncSession, name: str, slug: str) -> Organization:
    org = Organization(name=name, slug=slug, description=f"{name} demo", status="active")
    session.add(org)
    await session.flush()
    return org


async def _create_job(
    session: AsyncSession, recruiter: User, org: Organization | None,
    title: str = "Backend Engineer",
) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id if org else None,
        title=title,
        company=org.name if org else "Test Co",
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
    status: ApplicationStatus = ApplicationStatus.APPLIED,
    job_title: str = "Backend Engineer",
):
    """Org + owning recruiter + candidate + published job + application."""
    org = await _create_org(session, f"Org {suffix}", f"org-{suffix}")
    recruiter = await _create_user(
        session, f"Recruiter {suffix}", f"rec{suffix}@test.com",
    )
    candidate = await _create_user(
        session, f"Candidate {suffix}", f"cand{suffix}@test.com",
    )
    other_recruiter = await _create_user(
        session, f"Outsider {suffix}", f"out{suffix}@test.com",
    )
    await _assign_role(session, recruiter.id, RoleName.RECRUITER.value)
    await _assign_role(session, candidate.id, RoleName.CANDIDATE.value)
    await _assign_role(session, other_recruiter.id, RoleName.RECRUITER.value)
    job = await _create_job(session, recruiter, org, title=job_title)
    app = JobApplication(
        job_id=job.id,
        candidate_id=candidate.id,
        status=status.value,
    )
    session.add(app)
    await session.flush()
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(app, actor=candidate)
    if status != ApplicationStatus.APPLIED:
        # Reach the requested starting status through the authoritative path.
        await lifecycle.transition_application(
            app.id, status.value, recruiter,
        )
    await session.refresh(app)
    return {
        "org": org,
        "recruiter": recruiter,
        "candidate": candidate,
        "other_recruiter": other_recruiter,
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


@pytest.fixture
def captured_notifications(monkeypatch):
    """Capture what the post-commit dispatcher was asked to send.

    The real dispatcher opens its own session against the configured database,
    which is not the in-memory test database, so it is replaced with a recorder
    here. The delivery function itself is unit tested separately below.
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


# ─────────────────────────────────────────────────────────────────────
# Rejection requires a structured reason
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_without_reason_is_rejected(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "r1")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text
    assert "reason" in resp.text.lower()

    # Nothing was written: status, history and notifications are untouched.
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.APPLIED.value
    assert app.decision_reason_code is None
    assert captured_notifications == []


@pytest.mark.asyncio
async def test_unknown_decision_value_is_rejected(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "r2")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "auto_reject"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_reason_on_non_rejection_decision_is_rejected(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "r3")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist", "rejection_reason": "low_job_match"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# ─────────────────────────────────────────────────────────────────────
# Rejection records a structured decision, history and audit
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_records_reason_code_history_and_audit(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "r4", job_title="Platform Engineer")
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": "insufficient_experience",
            "internal_note": INTERNAL_NOTE,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["previous_status"] == "applied"
    assert body["changed_status"] is True
    assert body["rejection_reason"] == "insufficient_experience"
    assert body["decided_by"] == str(ctx["recruiter"].id)

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.REJECTED.value
    # The controlled code is stored separately from any free text.
    assert app.decision_reason_code == RejectionReason.INSUFFICIENT_EXPERIENCE.value
    assert app.decided_by == ctx["recruiter"].id
    assert app.decided_at is not None
    # The private note is stored for staff only.
    assert app.decision_comment == INTERNAL_NOTE

    history = await ApplicationStatusHistoryRepository(session).list_by_application(
        ctx["app"].id,
    )
    rejection_records = [
        r for r in history if r.to_status == ApplicationStatus.REJECTED.value
    ]
    assert len(rejection_records) == 1
    record = rejection_records[0]
    assert record.changed_by == ctx["recruiter"].id
    assert (record.metadata_json or {}).get("reason_code") == "insufficient_experience"
    assert (record.metadata_json or {}).get("decision") == "reject"
    assert record.comment == INTERNAL_NOTE

    events = set(
        (
            await session.execute(
                select(AuditLog.event_type).where(
                    AuditLog.resource_id == str(ctx["app"].id),
                )
            )
        ).scalars().all()
    )
    assert AuditEventType.APPLICATION_STATUS_CHANGED.value in events
    assert AuditEventType.APPLICATION_DECISION_RECORDED.value in events
    assert AuditEventType.APPLICATION_REJECTED.value in events

    # One notification is queued, and only after the decision.
    assert len(captured_notifications) == 1
    assert captured_notifications[0]["status"] is ApplicationStatus.REJECTED
    assert captured_notifications[0]["candidate_id"] == ctx["candidate"].id


@pytest.mark.asyncio
async def test_audit_details_do_not_duplicate_the_internal_note(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "r5")
    token = await _login(client, ctx["recruiter"].email)

    await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": "position_filled",
            "internal_note": INTERNAL_NOTE,
        },
        headers=_auth(token),
    )

    rows = (
        await session.execute(
            select(AuditLog.details).where(
                AuditLog.resource_id == str(ctx["app"].id),
                AuditLog.event_type == AuditEventType.APPLICATION_DECISION_RECORDED.value,
            )
        )
    ).scalars().all()
    assert rows, "decision audit entry must exist"
    assert all(INTERNAL_NOTE not in str(row) for row in rows)


# ─────────────────────────────────────────────────────────────────────
# Shortlist and keep-under-review
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shortlist_moves_status_and_records_decision(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(
        session, "s1", status=ApplicationStatus.UNDER_REVIEW,
    )
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist", "internal_note": "Strong Python depth"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "shortlisted"
    assert body["changed_status"] is True

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    # A shortlist is a real decision, so it records who decided and when.
    assert app.status == ApplicationStatus.SHORTLISTED.value
    assert app.decided_by == ctx["recruiter"].id
    assert app.decided_at is not None
    # A shortlist carries no rejection reason.
    assert app.decision_reason_code is None

    assert len(captured_notifications) == 1
    assert captured_notifications[0]["status"] is ApplicationStatus.SHORTLISTED
    # The queued message is the approved shortlist projection, not a
    # locally recomposed string.
    assert "shortlisted" in captured_notifications[0]["candidate_message"].lower()


@pytest.mark.asyncio
async def test_keep_under_review_records_decision_without_status_change(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(
        session, "k1", status=ApplicationStatus.UNDER_REVIEW,
    )
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "keep_under_review", "internal_note": "Waiting on refs"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "under_review"
    assert body["changed_status"] is False

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.UNDER_REVIEW.value

    # The decision is still recorded in the immutable history.
    history = await ApplicationStatusHistoryRepository(session).list_by_application(
        ctx["app"].id,
    )
    keep_records = [
        r for r in history
        if (r.metadata_json or {}).get("decision") == "keep_under_review"
    ]
    assert len(keep_records) == 1
    assert keep_records[0].from_status == "under_review"
    assert keep_records[0].to_status == "under_review"
    assert keep_records[0].changed_by == ctx["recruiter"].id

    # A non-final decision does not tell the candidate anything new.
    assert captured_notifications == []


@pytest.mark.asyncio
async def test_keep_under_review_rejected_outside_under_review(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "k2")  # status: applied
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "keep_under_review"},
        headers=_auth(token),
    )
    assert resp.status_code == 409, resp.text


# ─────────────────────────────────────────────────────────────────────
# Server-authoritative options
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_options_reflect_the_lifecycle_rules(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(
        session, "o1", status=ApplicationStatus.UNDER_REVIEW,
    )
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.get(_options_url(ctx["app"].id), headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["current_status"] == "under_review"
    assert body["status_is_final"] is False

    options = {o["decision"]: o for o in body["options"]}
    assert options["keep_under_review"]["available"] is True
    assert options["shortlist"]["available"] is True
    assert options["reject"]["available"] is True
    assert options["reject"]["requires_rejection_reason"] is True
    assert options["shortlist"]["target_status"] == "shortlisted"

    # Every reason the recruiter may pick, with the exact candidate wording.
    reasons = body["rejection_reasons"]
    assert {r["value"] for r in reasons} == {r.value for r in RejectionReason}
    assert all("Backend Engineer" in r["candidate_message"] for r in reasons)


@pytest.mark.asyncio
async def test_decision_options_block_terminal_statuses(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "o2", status=ApplicationStatus.APPLIED)
    token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject", "rejection_reason": "other"},
        headers=_auth(token),
    )

    resp = await client.get(_options_url(ctx["app"].id), headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status_is_final"] is True
    assert all(o["available"] is False for o in body["options"])
    assert all(o["unavailable_reason"] for o in body["options"])


@pytest.mark.asyncio
async def test_decision_options_after_shortlist_allow_interview_only(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(
        session, "o3", status=ApplicationStatus.UNDER_REVIEW,
    )
    token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )

    resp = await client.get(_options_url(ctx["app"].id), headers=_auth(token))
    options = {o["decision"]: o for o in resp.json()["options"]}
    assert options["shortlist"]["available"] is False
    assert options["keep_under_review"]["available"] is False
    assert options["reject"]["available"] is True


# ─────────────────────────────────────────────────────────────────────
# Terminal states, duplicates, concurrency
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_decision_after_a_final_status(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "t1", status=ApplicationStatus.APPLIED)
    token = await _login(client, ctx["recruiter"].email)
    reject = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject", "rejection_reason": "other"},
        headers=_auth(token),
    )
    assert reject.status_code == 200, reject.text

    again = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject", "rejection_reason": "other"},
        headers=_auth(token),
    )
    assert again.status_code == 409, again.text

    shortlist = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )
    assert shortlist.status_code == 409, shortlist.text

    # Exactly one decision history record and one queued notification.
    history = await ApplicationStatusHistoryRepository(session).list_by_application(
        ctx["app"].id,
    )
    assert len([r for r in history if r.to_status == "rejected"]) == 1
    assert len(captured_notifications) == 1


@pytest.mark.asyncio
async def test_duplicate_decision_submissions_produce_one_outcome(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    """A retried submission must not double-decide or double-notify.

    Two identical submissions are sent in sequence rather than gathered: the
    shared test session is not safe for concurrent use. The underlying
    compare-and-swap that makes a genuinely concurrent second writer lose is
    covered by the Phase 1 lifecycle tests; here the guard is the service-level
    conflict check, which must hold for a plain retry.
    """
    ctx = await _setup(
        session, "t2", status=ApplicationStatus.UNDER_REVIEW,
    )
    token = await _login(client, ctx["recruiter"].email)

    first = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )
    assert second.status_code == 409, second.text

    history = await ApplicationStatusHistoryRepository(session).list_by_application(
        ctx["app"].id,
    )
    assert len([r for r in history if r.to_status == "shortlisted"]) == 1
    assert len(captured_notifications) == 1


# ─────────────────────────────────────────────────────────────────────
# Authorization
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recruiter_from_another_org_cannot_decide(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "a1")
    other_org = await _create_org(session, "Org Other A1", "org-other-a1")
    outsider = ctx["other_recruiter"]
    await _add_membership(session, outsider, other_org.id, "recruiter")
    token = await _login(client, outsider.email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject", "rejection_reason": "other"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text

    options = await client.get(_options_url(ctx["app"].id), headers=_auth(token))
    assert options.status_code == 403, options.text
    history = await client.get(_history_url(ctx["app"].id), headers=_auth(token))
    assert history.status_code == 403, history.text


@pytest.mark.asyncio
async def test_candidate_cannot_decide_on_their_own_application(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "a2")
    token = await _login(client, ctx["candidate"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject", "rejection_reason": "other"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.APPLIED.value


@pytest.mark.asyncio
async def test_org_hr_member_can_decide_without_being_job_owner(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "a3")
    # The platform role is the legacy "hr" name; membership role is "hr" too.
    hr_user = await _create_user(session, "HR A3", "hra3@test.com")
    await _assign_role(session, hr_user.id, "hr")
    await _add_membership(session, hr_user, ctx["org"].id, "hr")
    token = await _login(client, hr_user.email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "shortlisted"


# ─────────────────────────────────────────────────────────────────────
# Candidate-facing communication and privacy
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_sees_approved_reason_and_no_internal_note(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "p1", job_title="Platform Engineer")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)

    await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": "missing_required_skill",
            "internal_note": INTERNAL_NOTE,
        },
        headers=_auth(recruiter_token),
    )

    resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(candidate_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    # The candidate-facing label is softened but the stored status is truthful.
    assert body["status_label"] == "Not Selected"
    assert body["decision_outcome"] == "not_selected"
    assert body["rejection_reason"] == "missing_required_skill"
    assert "Platform Engineer" in body["candidate_message"]
    assert body["is_decision_final"] is True
    assert body["decided_at"] is not None

    # Allowlist: no internal note, no recruiter identity, no score, no history.
    assert INTERNAL_NOTE not in resp.text
    assert "internal_note" not in resp.text
    assert "decided_by" not in resp.text
    assert "recruiter" not in resp.text.lower()
    assert "match_score" not in resp.text
    assert "history" not in resp.text


@pytest.mark.asyncio
async def test_queued_notification_message_matches_candidate_projection(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    """One projection, two consumers: no separate notification wording."""
    ctx = await _setup(session, "p1b", job_title="Platform Engineer")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": "missing_required_skill",
            "internal_note": INTERNAL_NOTE,
        },
        headers=_auth(recruiter_token),
    )
    assert resp.status_code == 200, resp.text

    candidate_resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(candidate_token),
    )
    assert candidate_resp.status_code == 200, candidate_resp.text

    assert len(captured_notifications) == 1
    assert (
        captured_notifications[0]["candidate_message"]
        == candidate_resp.json()["candidate_message"]
        == resp.json()["candidate_message"]
    )
    assert "Platform Engineer" in captured_notifications[0]["candidate_message"]


@pytest.mark.asyncio
async def test_internal_note_absent_from_every_candidate_endpoint(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "p2", job_title="Data Engineer")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)

    await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": "education_requirement",
            "internal_note": INTERNAL_NOTE,
        },
        headers=_auth(recruiter_token),
    )

    payloads = {
        "applications": await client.get(
            "/api/v1/candidate/jobs/applications", headers=_auth(candidate_token),
        ),
        "decision": await client.get(
            _candidate_decision_url(ctx["app"].id), headers=_auth(candidate_token),
        ),
        "explanation": await client.get(
            f"/api/v1/candidate/jobs/applications/{ctx['app'].id}/explanation",
            headers=_auth(candidate_token),
        ),
    }
    for name, resp in payloads.items():
        assert resp.status_code == 200, (name, resp.text)
        assert INTERNAL_NOTE not in resp.text, f"internal note leaked via {name}"


@pytest.mark.asyncio
async def test_candidate_cannot_read_another_candidates_decision(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p3")
    other = await _create_user(session, "Other P3", "otherp3@test.com")
    await _assign_role(session, other.id, RoleName.CANDIDATE.value)
    token = await _login(client, other.email)

    resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(token),
    )
    # Same 404 as a missing id: existence is not leaked.
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_candidate_view_of_unknown_application_is_404(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "p4")
    token = await _login(client, ctx["candidate"].email)
    resp = await client.get(
        _candidate_decision_url(uuid.uuid4()), headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_candidate_sees_shortlist_message(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(
        session, "p5", status=ApplicationStatus.UNDER_REVIEW, job_title="SRE",
    )
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)

    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist", "internal_note": INTERNAL_NOTE},
        headers=_auth(recruiter_token),
    )
    resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(candidate_token),
    )
    body = resp.json()
    assert body["status"] == "shortlisted"
    assert body["status_label"] == "Shortlisted"
    assert "shortlisted" in body["candidate_message"]
    assert INTERNAL_NOTE not in resp.text


@pytest.mark.asyncio
async def test_legacy_rejection_without_reason_code_gives_no_fabricated_reason(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A rejection made through the legacy endpoint has no controlled code.

    The candidate must not receive an invented explanation.
    """
    ctx = await _setup(session, "p6", job_title="Mobile Engineer")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)

    legacy = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/status",
        json={"status": "rejected", "reason": "legacy free text"},
        headers=_auth(recruiter_token),
    )
    assert legacy.status_code == 200, legacy.text

    resp = await client.get(
        _candidate_decision_url(ctx["app"].id), headers=_auth(candidate_token),
    )
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] is None
    assert "No further detail" in body["candidate_message"]
    assert "legacy free text" not in resp.text


@pytest.mark.asyncio
async def test_candidate_decision_list_is_scoped_and_safe(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(session, "p7", job_title="Security Engineer")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    other = await _create_user(session, "Other P7", "otherp7@test.com")
    await _assign_role(session, other.id, RoleName.CANDIDATE.value)

    await client.post(
        _decision_url(ctx["app"].id),
        json={
            "decision": "reject",
            "rejection_reason": "failed_interview",
            "internal_note": INTERNAL_NOTE,
        },
        headers=_auth(recruiter_token),
    )

    resp = await client.get(
        "/api/v1/candidate/jobs/applications/decisions", headers=_auth(candidate_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["application_id"] == str(ctx["app"].id)
    assert entry["job_title"] == "Security Engineer"
    assert entry["status"] == "rejected"
    assert entry["status_label"] == "Not Selected"
    assert entry["rejection_reason"] == "failed_interview"
    assert INTERNAL_NOTE not in resp.text

    # Another candidate sees only their own (empty) list.
    other_token = await _login(client, other.email)
    other_resp = await client.get(
        "/api/v1/candidate/jobs/applications/decisions",
        headers=_auth(other_token),
    )
    assert other_resp.status_code == 200, other_resp.text
    assert other_resp.json() == []


# ─────────────────────────────────────────────────────────────────────
# Decision history (staff)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_history_is_staff_only_and_complete(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(
        session, "h1", status=ApplicationStatus.UNDER_REVIEW,
    )
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)

    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "keep_under_review", "internal_note": "checking refs"},
        headers=_auth(recruiter_token),
    )
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(recruiter_token),
    )

    resp = await client.get(_history_url(ctx["app"].id), headers=_auth(recruiter_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    decisions = [h["decision"] for h in body["history"] if h["decision"]]
    assert decisions == ["keep_under_review", "shortlist"]
    assert body["status"] == "shortlisted"
    # The review note lives on the review history record. The application-level
    # note tracks the most recent status-changing decision, which had none.
    review_record = next(
        h for h in body["history"] if h["decision"] == "keep_under_review"
    )
    assert review_record["internal_note"] == "checking refs"
    assert any(
        h["changed_by_name"] == ctx["recruiter"].full_name for h in body["history"]
    )

    # A candidate may not read the staff trail.
    denied = await client.get(
        _history_url(ctx["app"].id), headers=_auth(candidate_token),
    )
    assert denied.status_code == 403, denied.text


# ─────────────────────────────────────────────────────────────────────
# Notifications: after commit, isolated, de-duplicated
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_survives_a_failing_notification(
    client: AsyncClient, session: AsyncSession, monkeypatch,
) -> None:
    """A notification failure must not corrupt or fail the decision."""
    ctx = await _setup(session, "n1")
    token = await _login(client, ctx["recruiter"].email)

    import app.services.applications.application_decision_notification as mod

    async def _boom(*args, **kwargs):
        raise RuntimeError("notification backend is down")

    monkeypatch.setattr(mod, "_deliver_with_own_session", _boom)

    resp = await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "reject", "rejection_reason": "other"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.REJECTED.value
    assert app.decision_reason_code == RejectionReason.OTHER.value
    history = await ApplicationStatusHistoryRepository(session).list_by_application(
        ctx["app"].id,
    )
    assert len([r for r in history if r.to_status == "rejected"]) == 1


@pytest.mark.asyncio
async def test_notification_is_written_once_per_decision(
    session: AsyncSession,
) -> None:
    ctx = await _setup(session, "n2")
    app_id, candidate_id = ctx["app"].id, ctx["candidate"].id
    approved_message = candidate_status_message(
        ApplicationStatus.REJECTED, ctx["job"].title, RejectionReason.POSITION_FILLED,
    )

    created = await deliver_decision_notification(
        session,
        application_id=app_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.REJECTED,
        candidate_message=approved_message,
    )
    assert created is True

    # A duplicate delivery (retry or replayed task) is suppressed, not raised.
    duplicate = await deliver_decision_notification(
        session,
        application_id=app_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.REJECTED,
        candidate_message=approved_message,
    )
    assert duplicate is False

    count = (
        await session.execute(
            select(func.count(Notification.id)).where(
                Notification.dedupe_key
                == decision_dedupe_key(app_id, ApplicationStatus.REJECTED),
            )
        )
    ).scalar_one()
    assert count == 1

    row = (
        await session.execute(
            select(Notification).where(
                Notification.dedupe_key
                == decision_dedupe_key(app_id, ApplicationStatus.REJECTED),
            )
        )
    ).scalar_one()
    assert row.user_id == candidate_id
    assert INTERNAL_NOTE not in row.message
    # The stored message is the approved projection verbatim.
    assert row.message == approved_message
    # A different decision on the same application is a different key.
    assert decision_dedupe_key(
        app_id, ApplicationStatus.SHORTLISTED,
    ) != decision_dedupe_key(app_id, ApplicationStatus.REJECTED)


# ─────────────────────────────────────────────────────────────────────
# AI and fairness never decide
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_high_screening_score_does_not_shortlist_or_reject(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    """A perfect score is decision support only: nothing moves on its own."""
    ctx = await _setup(session, "x1", status=ApplicationStatus.UNDER_REVIEW)
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    app.overall_match_score = 100
    app.recommendation = "strongly_recommend"
    app.strength_level = "excellent"
    app.screening_status = "completed"
    await session.flush()

    token = await _login(client, ctx["recruiter"].email)
    options = await client.get(_options_url(ctx["app"].id), headers=_auth(token))
    assert options.status_code == 200

    refreshed = await JobApplicationRepository(session).get(ctx["app"].id)
    assert refreshed.status == ApplicationStatus.UNDER_REVIEW.value
    assert refreshed.decided_by is None

    history = await ApplicationStatusHistoryRepository(session).list_by_application(
        ctx["app"].id,
    )
    assert all(r.to_status != "shortlisted" for r in history)
    assert all(r.to_status != "rejected" for r in history)
    assert captured_notifications == []


@pytest.mark.asyncio
async def test_decision_does_not_touch_screening_fields(
    client: AsyncClient, session: AsyncSession, captured_notifications,
) -> None:
    ctx = await _setup(
        session, "x2", status=ApplicationStatus.UNDER_REVIEW,
    )
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    app.overall_match_score = 82
    app.screening_status = "completed"
    app.screening_attempts = 1
    await session.flush()

    token = await _login(client, ctx["recruiter"].email)
    await client.post(
        _decision_url(ctx["app"].id),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )

    refreshed = await JobApplicationRepository(session).get(ctx["app"].id)
    assert refreshed.status == ApplicationStatus.SHORTLISTED.value
    assert refreshed.overall_match_score == 82
    assert refreshed.screening_status == "completed"
    assert refreshed.screening_attempts == 1


# ─────────────────────────────────────────────────────────────────────
# Service level and regressions
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_service_rejects_unknown_application(
    session: AsyncSession,
) -> None:
    ctx = await _setup(session, "u1")
    service = ApplicationDecisionService(session)
    with pytest.raises(Exception) as exc:
        await service.record_decision(
            uuid.uuid4(),
            ApplicationDecisionCreate(decision="shortlist"),
            ctx["recruiter"],
        )
    assert "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_candidate_withdraw_still_works(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "u2", status=ApplicationStatus.UNDER_REVIEW)
    token = await _login(client, ctx["candidate"].email)
    resp = await client.post(
        f"/api/v1/candidate/jobs/applications/{ctx['app'].id}/withdraw",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.WITHDRAWN.value


@pytest.mark.asyncio
async def test_legacy_status_endpoint_still_works(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The Phase 1 contract is preserved for the simulation/demo callers."""
    ctx = await _setup(session, "u3")
    token = await _login(client, ctx["recruiter"].email)
    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/status",
        json={"status": "under_review"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    app = await JobApplicationRepository(session).get(ctx["app"].id)
    assert app.status == ApplicationStatus.UNDER_REVIEW.value


@pytest.mark.asyncio
async def test_decision_on_unknown_application_is_404(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "u4")
    token = await _login(client, ctx["recruiter"].email)
    resp = await client.post(
        _decision_url(uuid.uuid4()),
        json={"decision": "shortlist"},
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text
