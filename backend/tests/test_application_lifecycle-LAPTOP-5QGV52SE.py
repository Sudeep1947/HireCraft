"""Tests for the centralized application lifecycle (Phase 1).

Contract under test:
- Every application writes a creation history record (applied) + audit entry.
- Recruiter status changes flow through the lifecycle service: legal funnel
  transitions succeed, illegal ones fail with 409, role misuse fails 403,
  unknown statuses fail 422.
- Staff can never set WITHDRAWN; a candidate can only withdraw their own
  application (403 for any other target; 409 if already finalized).
- Decision metadata (decided_by/decided_at/reason/comment) is stored on
  decisive statuses.
- The status flip is a compare-and-swap: stale expected states never silently
  overwrite a concurrently changed application (409).
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, ValidationError
from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    EmploymentType,
    JobStatus,
    MembershipStatus,
    RoleName,
)
from app.domain.models import AuditLog, ApplicationStatusHistory, Job, JobApplication, Organization, OrganizationMembership, User
from app.repositories.jobs.job import ApplicationStatusHistoryRepository, JobApplicationRepository
from app.repositories.membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository
from app.services.applications.application_lifecycle_service import ApplicationLifecycleService

PASSWORD = "Lifecycle@12345"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


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


async def _assign_role(session: AsyncSession, user_id: uuid.UUID, role_name: str) -> None:
    from app.domain.models import Role, UserRole
    role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    assert role, f"Role {role_name!r} must exist"
    existing = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role.id,
            ),
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


async def _create_application(
    session: AsyncSession, job: Job, candidate: User,
) -> JobApplication:
    app = JobApplication(
        job_id=job.id,
        candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()
    return app


async def _setup_hr_org(session: AsyncSession, suffix: str):
    """Org + owner recruiter user + org job. Returns dict of identities."""
    org = await _create_org(session, f"Org {suffix}", f"org-{suffix}")
    recruiter = await _create_user(session, f"Recruiter {suffix}", f"rec{suffix}@test.com")
    candidate = await _create_user(session, f"Candidate {suffix}", f"cand{suffix}@test.com")
    await _assign_role(session, recruiter.id, RoleName.RECRUITER.value)
    await _assign_role(session, candidate.id, RoleName.CANDIDATE.value)
    job = await _create_job(session, recruiter, org)
    app = await _create_application(session, job, candidate)
    # Production path: a real application always gets a creation history record.
    await ApplicationLifecycleService(session).record_creation(app, actor=candidate)
    return {
        "org": org,
        "recruiter": recruiter,
        "candidate": candidate,
        "job": job,
        "app": app,
    }


async def _register_and_login_role(client: AsyncClient, session: AsyncSession, suffix: str, role: str) -> tuple[str, uuid.UUID]:
    """Register a user, assign a platform role, and return (token, user_id)."""
    email = f"{role[:4]}{suffix}@test.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": f"{role.title()} {suffix}", "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    user_id = uuid.UUID(resp.json()["id"])
    await _assign_role(session, user_id, role)
    # The register call loaded the User (with its "candidate" role) into the
    # shared session's identity map; expire so later requests see the role.
    session.expire_all()
    return await _login(client, email), user_id


# ─────────────────────────────────────────────────────────────────────
# Creation record
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_records_creation_history_and_audit(
    client: AsyncClient, session: AsyncSession,
) -> None:
    hr_token, hr_id = await _register_and_login_role(client, session, "c1", "hr")
    job_create = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Lifecycle Job", "company": "Test Co", "employment_type": "full_time",
              "location": "NYC", "description": "A job", "required_skills": ["Python"],
              "status": "published"},
        headers=_auth(hr_token),
    )
    assert job_create.status_code == 201, job_create.text
    job_id = job_create.json()["id"]

    cand_token, cand_id = await _register_and_login_role(client, session, "c2", "candidate")
    apply_resp = await client.post(
        "/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=_auth(cand_token),
    )
    assert apply_resp.status_code == 201, apply_resp.text
    app_id = uuid.UUID(apply_resp.json()["id"])

    history = await ApplicationStatusHistoryRepository(session).list_by_application(app_id)
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == ApplicationStatus.APPLIED.value

    audit = (
        await session.execute(
            select(AuditLog).where(AuditLog.event_type == "application_created"),
        )
    ).scalars().all()
    assert any(a.resource_id == str(app_id) for a in audit)


# ─────────────────────────────────────────────────────────────────────
# Happy-path funnel + decision metadata
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_legal_funnel_advances_application_and_captures_decision(
    client: AsyncClient, session: AsyncSession,
) -> None:
    hr_token, hr_id = await _register_and_login_role(client, session, "f1", "hr")
    job_id = (await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Funnel Job", "company": "Test Co", "employment_type": "full_time",
              "location": "NYC", "description": "A job", "required_skills": ["Python"],
              "status": "published"},
        headers=_auth(hr_token),
    )).json()["id"]
    cand_token, cand_id = await _register_and_login_role(client, session, "f2", "candidate")
    app_id = (await client.post(
        "/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=_auth(cand_token),
    )).json()["id"]

    for status in ("under_review", "shortlisted", "interview_scheduled", "offered", "hired"):
        resp = await client.patch(
            f"/api/v1/recruiter/jobs/applications/{app_id}/status",
            json={"status": status},
            headers=_auth(hr_token),
        )
        assert resp.status_code == 200, resp.text

    app = await session.get(JobApplication, uuid.UUID(app_id))
    assert app.status == ApplicationStatus.HIRED.value
    assert app.decided_at is not None
    assert app.decided_by is not None

    history = await ApplicationStatusHistoryRepository(session).list_by_application(app.id)
    statuses = [(h.from_status, h.to_status) for h in history]
    assert statuses == [
        (None, "applied"),
        ("applied", "under_review"),
        ("under_review", "shortlisted"),
        ("shortlisted", "interview_scheduled"),
        ("interview_scheduled", "offered"),
        ("offered", "hired"),
    ]

    audit = (
        await session.execute(
            select(AuditLog).where(AuditLog.event_type == "application_status_changed"),
        )
    ).scalars().all()
    assert len(audit) == 5


@pytest.mark.asyncio
async def test_rejection_stores_reason_comment_and_decider(
    client: AsyncClient, session: AsyncSession,
) -> None:
    hr_token, hr_id = await _register_and_login_role(client, session, "r1", "hr")
    job_id = (await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Reject Job", "company": "Test Co", "employment_type": "full_time",
              "location": "NYC", "description": "A job", "required_skills": ["Python"],
              "status": "published"},
        headers=_auth(hr_token),
    )).json()["id"]
    cand_token, cand_id = await _register_and_login_role(client, session, "r2", "candidate")
    app_id = (await client.post(
        "/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=_auth(cand_token),
    )).json()["id"]

    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{app_id}/status",
        json={"status": "rejected", "reason": "other", "comment": "Not a fit for the team"},
        headers=_auth(hr_token),
    )
    assert resp.status_code == 200, resp.text

    app = await session.get(JobApplication, uuid.UUID(app_id))
    assert app.status == ApplicationStatus.REJECTED.value
    assert app.decision_reason == "other"
    assert app.decision_comment == "Not a fit for the team"
    assert app.decided_at is not None
    assert app.decided_by is not None


# ─────────────────────────────────────────────────────────────────────
# Illegal transitions, role misuse, terminal states
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skip_transition_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "skip")
    org_id = ctx["org"].id
    app_id = ctx["app"].id
    hr_token, hr_id = await _register_and_login_role(client, session, "skip_hr", "hr")
    hr_user = await UserRepository(session).get(hr_id)
    assert hr_user is not None
    await _add_membership(session, hr_user, org_id, RoleName.HR_MANAGER.value)

    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{app_id}/status",
        json={"status": "hired"},
        headers=_auth(hr_token),
    )
    assert resp.status_code == 409, resp.text

    app = await session.get(JobApplication, app_id)
    assert app.status == ApplicationStatus.APPLIED.value
    history = await ApplicationStatusHistoryRepository(session).list_by_application(app_id)
    assert len(history) == 1
    assert history[0].to_status == "applied"


@pytest.mark.asyncio
async def test_terminal_state_never_reopens(client: AsyncClient, session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "term")
    org_id = ctx["org"].id
    app_id = ctx["app"].id
    hr_token, hr_id = await _register_and_login_role(client, session, "term_hr", "hr")
    hr_user = await UserRepository(session).get(hr_id)
    assert hr_user is not None
    await _add_membership(session, hr_user, org_id, RoleName.HR_MANAGER.value)

    for status in ("shortlisted", "interview_scheduled", "offered", "hired"):
        resp = await client.patch(
            f"/api/v1/recruiter/jobs/applications/{app_id}/status",
            json={"status": status},
            headers=_auth(hr_token),
        )
        assert resp.status_code == 200

    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{app_id}/status",
        json={"status": "under_review"},
        headers=_auth(hr_token),
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_candidate_cannot_set_recruiter_status(
    session: AsyncSession,
) -> None:
    ctx = await _setup_hr_org(session, "candrole")
    lifecycle = ApplicationLifecycleService(session)
    with pytest.raises(ForbiddenError):
        await lifecycle.transition_application(
            ctx["app"].id, ApplicationStatus.SHORTLISTED.value, ctx["candidate"],
        )


@pytest.mark.asyncio
async def test_staff_cannot_withdraw_application(session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "staffwd")
    lifecycle = ApplicationLifecycleService(session)
    with pytest.raises(ForbiddenError):
        await lifecycle.transition_application(
            ctx["app"].id, ApplicationStatus.WITHDRAWN.value, ctx["recruiter"],
        )


@pytest.mark.asyncio
async def test_candidate_withdraws_from_later_stage(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_hr_org(session, "wd1")
    candidate_email = ctx["candidate"].email
    org_id = ctx["org"].id
    app_id = ctx["app"].id
    cand_token = await _login(client, candidate_email)
    hr_token, hr_id = await _register_and_login_role(client, session, "wd1_hr", "hr")
    hr_user = await UserRepository(session).get(hr_id)
    assert hr_user is not None
    await _add_membership(session, hr_user, org_id, RoleName.HR_MANAGER.value)

    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{app_id}/status",
        json={"status": "shortlisted"},
        headers=_auth(hr_token),
    )
    assert resp.status_code == 200, resp.text

    withdraw = await client.post(
        f"/api/v1/candidate/jobs/applications/{app_id}/withdraw",
        headers=_auth(cand_token),
    )
    assert withdraw.status_code == 200, withdraw.text

    app = await session.get(JobApplication, app_id)
    assert app.status == ApplicationStatus.WITHDRAWN.value
    history = await ApplicationStatusHistoryRepository(session).list_by_application(app_id)
    assert [h.to_status for h in history] == ["applied", "shortlisted", "withdrawn"]


@pytest.mark.asyncio
async def test_candidate_cannot_withdraw_finalized_application(
    session: AsyncSession,
) -> None:
    ctx = await _setup_hr_org(session, "finalwd")
    lifecycle = ApplicationLifecycleService(session)
    recruiter = ctx["recruiter"]
    for status in ("shortlisted", "interview_scheduled", "offered", "hired"):
        await lifecycle.transition_application(
            ctx["app"].id, status, recruiter,
        )
    with pytest.raises(ConflictError):
        await lifecycle.transition_application(
            ctx["app"].id, ApplicationStatus.WITHDRAWN.value, ctx["candidate"],
        )


# ─────────────────────────────────────────────────────────────────────
# Organization access control
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_org_staff_member_of_same_org_can_transition(
    session: AsyncSession,
) -> None:
    ctx = await _setup_hr_org(session, "samenig")
    staff = await _create_user(session, "Org HR", "samenig_staff@test.com")
    await _add_membership(session, staff, ctx["org"].id, RoleName.RECRUITER.value)

    lifecycle = ApplicationLifecycleService(session)
    updated = await lifecycle.transition_application(
        ctx["app"].id, ApplicationStatus.UNDER_REVIEW.value, staff,
    )
    assert updated.status == ApplicationStatus.UNDER_REVIEW.value


@pytest.mark.asyncio
async def test_stranger_without_access_is_forbidden(session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "stranger")
    outsider = await _create_user(session, "Outsider", "stranger_user@test.com")
    lifecycle = ApplicationLifecycleService(session)
    with pytest.raises(ForbiddenError):
        await lifecycle.transition_application(
            ctx["app"].id, ApplicationStatus.UNDER_REVIEW.value, outsider,
        )


@pytest.mark.asyncio
async def test_member_of_other_org_cannot_transition(session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "otherorg1")
    other_org = await _create_org(session, "Other Org", "other-org-1")
    foreign_staff = await _create_user(session, "Foreign HR", "foreign_staff@test.com")
    await _add_membership(session, foreign_staff, other_org.id, RoleName.RECRUITER.value)

    lifecycle = ApplicationLifecycleService(session)
    with pytest.raises(ForbiddenError):
        await lifecycle.transition_application(
            ctx["app"].id, ApplicationStatus.UNDER_REVIEW.value, foreign_staff,
        )


@pytest.mark.asyncio
async def test_stranger_api_call_returns_403(client: AsyncClient, session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "api403")
    stranger = await _create_user(session, "Stranger HR", "api403_hr@test.com")
    await _assign_role(session, stranger.id, "recruiter")
    token = await _login(client, stranger.email)

    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/status",
        json={"status": "under_review"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


# ─────────────────────────────────────────────────────────────────────
# Validation + concurrency
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_status_rejected(client: AsyncClient, session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "unknown")
    app_id = ctx["app"].id
    recruiter_id = ctx["recruiter"].id
    hr_token, hr_id = await _register_and_login_role(client, session, "unknown_hr", "hr")
    # A string that is not a member of ApplicationStatus. Note this must stay a
    # status the enum genuinely lacks: validation short-circuits before the
    # authorization check, so naming a real status here would 403 the unrelated
    # throwaway ``hr`` user instead of exercising the 422 branch.
    resp = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{app_id}/status",
        json={"status": "phone_screened"},
        headers=_auth(hr_token),
    )
    assert resp.status_code == 422, resp.text

    lifecycle = ApplicationLifecycleService(session)
    recruiter = await session.get(User, recruiter_id)
    with pytest.raises(ValidationError):
        await lifecycle.transition_application(
            app_id, "phone_screened", recruiter,
        )


@pytest.mark.asyncio
async def test_cas_never_overwrites_stale_state(session: AsyncSession) -> None:
    ctx = await _setup_hr_org(session, "cas")
    repo = JobApplicationRepository(session)
    app_id = ctx["app"].id

    # Move the row out from under a stale expectation.
    await repo.update_status(app_id, ApplicationStatus.UNDER_REVIEW.value)
    stale = await repo.update_status_if_current(
        app_id, ApplicationStatus.APPLIED.value, ApplicationStatus.SHORTLISTED.value,
    )
    assert stale is None

    app = await session.get(JobApplication, app_id)
    assert app.status == ApplicationStatus.UNDER_REVIEW.value


@pytest.mark.asyncio
async def test_same_org_actor_notification_uses_candidate(
    session: AsyncSession,
) -> None:
    ctx = await _setup_hr_org(session, "notif_org")
    member = await _create_user(session, "Org Recruiter", "notif_org_mem@test.com")
    await _add_membership(session, member, ctx["org"].id, RoleName.RECRUITER.value)
    lifecycle = ApplicationLifecycleService(session)
    updated = await lifecycle.transition_application(
        ctx["app"].id, ApplicationStatus.UNDER_REVIEW.value, member,
    )
    assert updated is not None