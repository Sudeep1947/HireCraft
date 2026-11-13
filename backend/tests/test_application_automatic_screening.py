"""Tests for automatic application screening (Phase 3).

Contract under test:
- Applying to a published job triggers screening automatically (inline when no
  broker is reachable, as in the test suite) using the SAME request session.
- Successful screening persists a ``ScreeningResult`` linked to the application,
  writes a system ``application_screened`` audit (``user_id=None``,
  ``actor=system``, ``trigger=automatic``) and refreshes job rankings.
- Screening never changes the application lifecycle status.
- A candidate without a profile does not block the application: the response is
  still 201, the run records ``FAILED`` with the reason and a
  ``application_screening_failed`` audit.
- Runs are idempotent: a completed run is never re-claimed (one screening
  result, ``screening_attempts == 1``).
- ``FAILED`` runs are re-claimable so a bounded retry can succeed later.
- Finalized applications are ``SKIPPED`` instead of raising.
- Unexpected engine failures are recorded as ``FAILED`` and never propagate to
  the caller.
- When a broker is reachable the application is marked ``QUEUED`` and no inline
  run happens.
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
    ScreeningStatus,
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
from app.services.applications.application_lifecycle_service import ApplicationLifecycleService
from app.services.applications.automatic_screening_service import AutomaticScreeningService
from app.services.applications.screening_scheduler import dispatch_automatic_screening

PASSWORD = "AutoScreen@12345"


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


async def _create_job(session: AsyncSession, recruiter: User, org: Organization) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title="Backend Engineer",
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


async def _setup(
    session: AsyncSession,
    suffix: str,
    with_profile: bool = True,
    skills: tuple[str, ...] = ("Python", "FastAPI", "PostgreSQL"),
):
    org = await _create_org(session, f"AutoScr Org {suffix}", f"autoscr-org-{suffix}")
    recruiter = await _create_user(session, f"AutoScr Rec {suffix}", f"autoscrrec{suffix}@test.com")
    candidate = await _create_user(session, f"AutoScr Cand {suffix}", f"autoscrcand{suffix}@test.com")
    await _assign_role(session, recruiter.id, RoleName.RECRUITER.value)
    await _assign_role(session, candidate.id, RoleName.CANDIDATE.value)
    job = await _create_job(session, recruiter, org)
    if with_profile:
        await _create_profile_with_skills(session, candidate.id, list(skills))
    return {
        "org": org,
        "recruiter": recruiter,
        "candidate": candidate,
        "job": job,
    }


# ─────────────────────────────────────────────────────────────────────
# Automatic screening on apply (inline path, no broker in tests)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_triggers_inline_screening_and_persists_result(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "happy")
    token = await _login(client, ctx["candidate"].email)
    job_id = ctx["job"].id
    candidate_id = ctx["candidate"].id

    resp = await client.post(
        "/api/v1/candidate/jobs/apply",
        json={"job_id": str(job_id), "cover_letter": "Great fit"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == ApplicationStatus.APPLIED.value
    assert body["screening_status"] == ScreeningStatus.COMPLETED.value
    assert body["screening_error"] is None
    assert body["screening_completed_at"] is not None
    app_id = uuid.UUID(body["id"])

    screening = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalar_one_or_none()
    assert screening is not None
    assert screening.job_id == job_id
    assert screening.candidate_id == candidate_id
    assert 0 <= screening.overall_match_score <= 100

    app = await session.get(JobApplication, app_id)
    assert app.status == ApplicationStatus.APPLIED.value
    assert app.screening_status == ScreeningStatus.COMPLETED.value
    assert app.screening_attempts == 1

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "application_screened",
                AuditLog.resource_id == str(app_id),
            ),
        )
    ).scalars().all()
    assert len(audits) == 1
    entry = audits[0]
    assert entry.user_id is None
    details = entry.details or {}
    assert details.get("actor") == "system"
    assert details.get("trigger") == "automatic"

    ranking = (
        await session.execute(
            select(CandidateRanking).where(
                CandidateRanking.job_id == job_id,
                CandidateRanking.candidate_id == candidate_id,
            ),
        )
    ).scalar_one_or_none()
    assert ranking is not None
    assert ranking.rank == 1


@pytest.mark.asyncio
async def test_apply_without_profile_still_201_and_tracks_failure(
    client: AsyncClient, session: AsyncSession,
) -> None:
    ctx = await _setup(session, "noprofile", with_profile=False)
    token = await _login(client, ctx["candidate"].email)

    resp = await client.post(
        "/api/v1/candidate/jobs/apply",
        json={"job_id": str(ctx["job"].id)},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == ApplicationStatus.APPLIED.value
    assert body["screening_status"] == ScreeningStatus.FAILED.value
    assert body["screening_error"] and "profile" in body["screening_error"].lower()
    app_id = uuid.UUID(body["id"])

    screening = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalar_one_or_none()
    assert screening is None

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "application_screening_failed",
                AuditLog.resource_id == str(app_id),
            ),
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].user_id is None
    assert audits[0].success is False


# ─────────────────────────────────────────────────────────────────────
# Idempotency and retry
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_completed_screening_is_idempotent(session: AsyncSession) -> None:
    ctx = await _setup(session, "idem")
    app = JobApplication(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()
    await ApplicationLifecycleService(session).record_creation(app, actor=ctx["candidate"])
    app_id = app.id

    svc = AutomaticScreeningService(session)
    first = await svc.process(app_id)
    assert first == ScreeningStatus.COMPLETED.value

    second = await svc.process(app_id)
    assert second == ScreeningStatus.COMPLETED.value

    app = await session.get(JobApplication, app_id)
    assert app.screening_attempts == 1

    results = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalars().all()
    assert len(results) == 1


@pytest.mark.asyncio
async def test_failed_run_can_be_retried(session: AsyncSession) -> None:
    ctx = await _setup(session, "retry", with_profile=False)
    app = JobApplication(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()
    await ApplicationLifecycleService(session).record_creation(app, actor=ctx["candidate"])
    app_id = app.id

    svc = AutomaticScreeningService(session)
    first = await svc.process(app_id)
    assert first == ScreeningStatus.FAILED.value

    await _create_profile_with_skills(
        session, ctx["candidate"].id, list("Python FastAPI PostgreSQL".split(" ")),
    )
    second = await svc.process(app_id)
    assert second == ScreeningStatus.COMPLETED.value

    app = await session.get(JobApplication, app_id)
    assert app.screening_attempts == 2
    assert app.screening_status == ScreeningStatus.COMPLETED.value

    results = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalars().all()
    assert len(results) == 1


# ─────────────────────────────────────────────────────────────────────
# Finalized applications and unexpected failures
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finalized_application_is_skipped(session: AsyncSession) -> None:
    ctx = await _setup(session, "skip")
    app = JobApplication(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        status=ApplicationStatus.APPLIED.value,
    )
    session.add(app)
    await session.flush()
    await ApplicationLifecycleService(session).record_creation(app, actor=ctx["candidate"])
    app_id = app.id

    for status in ("shortlisted", "interview_scheduled", "offered", "hired"):
        await ApplicationLifecycleService(session).transition_application(
            app_id, status, ctx["recruiter"],
        )

    result = await dispatch_automatic_screening(session, app_id)
    assert result == ScreeningStatus.SKIPPED.value

    app = await session.get(JobApplication, app_id)
    assert app.status == ApplicationStatus.HIRED.value
    assert app.screening_status == ScreeningStatus.SKIPPED.value

    screening = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalar_one_or_none()
    assert screening is None


@pytest.mark.asyncio
async def test_unexpected_engine_failure_is_recorded_not_raised(
    client: AsyncClient, session: AsyncSession, monkeypatch,
) -> None:
    ctx = await _setup(session, "boom")
    token = await _login(client, ctx["candidate"].email)

    async def _boom(*args, **kwargs):
        raise RuntimeError("engine exploded")

    from app.services.applications.application_screening_service import (
        ApplicationScreeningService,
    )
    monkeypatch.setattr(ApplicationScreeningService, "screen_application_system", _boom)

    resp = await client.post(
        "/api/v1/candidate/jobs/apply",
        json={"job_id": str(ctx["job"].id)},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == ApplicationStatus.APPLIED.value
    assert body["screening_status"] == ScreeningStatus.FAILED.value
    assert "engine exploded" in (body["screening_error"] or "")

    audits = (
        await session.execute(
            select(AuditLog).where(AuditLog.event_type == "application_screening_failed"),
        )
    ).scalars().all()
    assert any(a.resource_id == body["id"] for a in audits)
    assert all(a.success is False for a in audits)


# ─────────────────────────────────────────────────────────────────────
# Broker path: QUEUED, no inline run
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_broker_available_marks_queued_and_skips_inline(
    client: AsyncClient, session: AsyncSession, monkeypatch,
) -> None:
    import app.services.applications.screening_scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "_celery_available", lambda: True)
    monkeypatch.setattr(
        sched_mod, "queue_application_screening",
        lambda application_id: {"status": "queued", "task_id": "task-abc123"},
    )

    ctx = await _setup(session, "queued")
    token = await _login(client, ctx["candidate"].email)

    resp = await client.post(
        "/api/v1/candidate/jobs/apply",
        json={"job_id": str(ctx["job"].id)},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["screening_status"] == ScreeningStatus.QUEUED.value
    app_id = uuid.UUID(body["id"])

    app = await session.get(JobApplication, app_id)
    assert app.screening_status == ScreeningStatus.QUEUED.value
    assert app.screening_task_id == "task-abc123"
    assert app.screening_attempts == 0
    assert app.screening_started_at is None

    screening = (
        await session.execute(
            select(ScreeningResult).where(ScreeningResult.application_id == app_id),
        )
    ).scalar_one_or_none()
    assert screening is None