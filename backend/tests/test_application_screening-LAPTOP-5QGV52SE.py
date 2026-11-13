"""Tests for application-level screening (Phase 2).

Contract under test:
- Triggering screening on an application reuses the existing matching engine and
  persists a ``ScreeningResult`` explicitly linked to the application.
- The screening result is retrievable by application; 404 before it is run.
- Screening never changes the application status and never makes a hiring
  decision (decision support only).
- Finalized (hired/rejected/withdrawn) applications cannot be screened (409).
- Access is organization-aware: the job owner and active same-org staff may
  screen; strangers and cross-org staff get 403; unknown applications get 404;
  non-staff roles get 403.
- An ``application_screened`` audit event is written and job rankings refresh.
- Screening is deterministic and idempotent per application.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    EmploymentType,
    JobStatus,
    MembershipStatus,
    RoleName,
    SkillCategory,
)
from app.domain.models import (
    AuditLog,
    CandidateProfile,
    CandidateRanking,
    CandidateSkill,
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    Role,
    ScreeningResult,
    Skill,
    User,
    UserRole,
)
from app.repositories.jobs.job import ApplicationStatusHistoryRepository
from app.services.applications.application_lifecycle_service import ApplicationLifecycleService

PASSWORD = "Screening@12345"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


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


async def _assign_role(session: AsyncSession, user_id: uuid.UUID, role_name: str) -> None:
    role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    assert role, f"Role {role_name!r} must exist"
    existing = (
        await session.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id),
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(UserRole(user_id=user_id, role_id=role.id))
        await session.flush()


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


async def _create_job(session: AsyncSession, recruiter: User, org: Organization | None) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id if org else None,
        title="Backend Engineer",
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


async def _create_profile_with_skills(
    session: AsyncSession, user_id: uuid.UUID, skills: list[str],
) -> CandidateProfile:
    profile = CandidateProfile(user_id=user_id, location="Remote", profile_completion=80)
    session.add(profile)
    await session.flush()
    for name in skills:
        skill = (await session.execute(select(Skill).where(Skill.name == name))).scalar_one_or_none()
        if skill is None:
            skill = Skill(name=name, category=SkillCategory.PROGRAMMING_LANGUAGES.value)
            session.add(skill)
            await session.flush()
        session.add(CandidateSkill(profile_id=profile.id, skill_id=skill.id))
    await session.flush()
    return profile


async def _setup_org_application(
    session: AsyncSession,
    suffix: str,
    skills: tuple[str, ...] = ("Python", "FastAPI", "PostgreSQL"),
    with_profile: bool = True,
):
    org = await _create_org(session, f"Scr Org {suffix}", f"scr-org-{suffix}")
    recruiter = await _create_user(session, f"Scr Rec {suffix}", f"scrrec{suffix}@test.com")
    candidate = await _create_user(session, f"Scr Cand {suffix}", f"scrcand{suffix}@test.com")
    await _assign_role(session, recruiter.id, RoleName.RECRUITER.value)
    await _assign_role(session, candidate.id, RoleName.CANDIDATE.value)
    job = await _create_job(session, recruiter, org)
    app = await _create_application(session, job, candidate)
    await ApplicationLifecycleService(session).record_creation(app, actor=candidate)
    if with_profile:
        await _create_profile_with_skills(session, candidate.id, list(skills))
    return {
        "org": org,
        "recruiter": recruiter,
        "candidate": candidate,
        "job": job,
        "app": app,
    }


# ─────────────────────────────────────────────────────────────────────
# Happy path + persistence + audit
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_screen_application_persists_linked_result(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "happy")
    token = await _login(client, ctx["recruiter"].email)
    app_id = ctx["app"].id

    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screen", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["application_id"] == str(app_id)
    assert body["job_id"] == str(ctx["job"].id)
    assert body["candidate_id"] == str(ctx["candidate"].id)
    assert 0 <= body["overall_match_score"] <= 100

    stored = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalar_one_or_none()
    assert stored is not None
    assert stored.job_id == ctx["job"].id
    assert stored.candidate_id == ctx["candidate"].id
    assert stored.overall_match_score == body["overall_match_score"]

    # Screening must not change the lifecycle status.
    app = await session.get(JobApplication, app_id)
    assert app.status == ApplicationStatus.APPLIED.value
    history = await ApplicationStatusHistoryRepository(session).list_by_application(app_id)
    assert [h.to_status for h in history] == ["applied"]


@pytest.mark.asyncio
async def test_get_application_screening_after_trigger(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "get")
    token = await _login(client, ctx["recruiter"].email)
    app_id = ctx["app"].id

    created = await client.post(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screen", headers=_auth(token),
    )
    assert created.status_code == 200, created.text

    fetched = await client.get(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screening", headers=_auth(token),
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == created.json()["id"]
    assert fetched.json()["application_id"] == str(app_id)


@pytest.mark.asyncio
async def test_get_screening_before_trigger_returns_404(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "before")
    token = await _login(client, ctx["recruiter"].email)
    resp = await client.get(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/screening",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_screening_writes_audit_and_ranking(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "audit")
    token = await _login(client, ctx["recruiter"].email)
    app_id = ctx["app"].id

    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screen", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    audit = (
        await session.execute(
            select(AuditLog).where(AuditLog.event_type == "application_screened"),
        )
    ).scalars().all()
    assert any(a.resource_id == str(app_id) for a in audit)

    ranking = (
        await session.execute(
            select(CandidateRanking).where(
                CandidateRanking.job_id == ctx["job"].id,
                CandidateRanking.candidate_id == ctx["candidate"].id,
            ),
        )
    ).scalar_one_or_none()
    assert ranking is not None
    assert ranking.rank == 1


@pytest.mark.asyncio
async def test_screening_is_deterministic_and_idempotent(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "idem")
    token = await _login(client, ctx["recruiter"].email)
    app_id = ctx["app"].id

    first = await client.post(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screen", headers=_auth(token),
    )
    second = await client.post(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screen", headers=_auth(token),
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["overall_match_score"] == second.json()["overall_match_score"]

    results = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalars().all()
    assert len(results) == 1
    rankings = (
        await session.execute(
            select(CandidateRanking).where(
                CandidateRanking.job_id == ctx["job"].id,
                CandidateRanking.candidate_id == ctx["candidate"].id,
            ),
        )
    ).scalars().all()
    assert len(rankings) == 1


# ─────────────────────────────────────────────────────────────────────
# Lifecycle guard
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finalized_application_cannot_be_screened(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "terminal")
    token = await _login(client, ctx["recruiter"].email)
    app_id = ctx["app"].id

    lifecycle = ApplicationLifecycleService(session)
    for status in ("shortlisted", "interview_scheduled", "offered", "hired"):
        await lifecycle.transition_application(app_id, status, ctx["recruiter"])

    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{app_id}/screen", headers=_auth(token),
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_screening_without_profile_returns_422(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "noprofile", with_profile=False)
    token = await _login(client, ctx["recruiter"].email)
    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/screen",
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# ─────────────────────────────────────────────────────────────────────
# Authorization / organization isolation
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_application_returns_404(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "missing")
    token = await _login(client, ctx["recruiter"].email)
    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{uuid.uuid4()}/screen",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_stranger_recruiter_is_forbidden(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "stranger")
    stranger = await _create_user(session, "Stranger", "scr_stranger@test.com")
    await _assign_role(session, stranger.id, RoleName.RECRUITER.value)
    token = await _login(client, stranger.email)

    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/screen",
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_cross_org_staff_is_forbidden(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "crossorg")
    other_org = await _create_org(session, "Other Scr Org", "scr-other-org")
    foreign = await _create_user(session, "Foreign HR", "scr_foreign@test.com")
    await _assign_role(session, foreign.id, RoleName.RECRUITER.value)
    await _add_membership(session, foreign, other_org.id, RoleName.RECRUITER.value)
    token = await _login(client, foreign.email)

    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/screen",
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_same_org_staff_can_screen(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "samenig")
    staff = await _create_user(session, "Org Staff", "scr_org_staff@test.com")
    await _assign_role(session, staff.id, RoleName.RECRUITER.value)
    await _add_membership(session, staff, ctx["org"].id, RoleName.RECRUITER.value)
    token = await _login(client, staff.email)

    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/screen",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_candidate_role_cannot_screen(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup_org_application(session, "candrole")
    token = await _login(client, ctx["candidate"].email)
    resp = await client.post(
        f"/api/v1/recruiter/jobs/applications/{ctx['app'].id}/screen",
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text
