"""Tests for the OPTIONAL manual shortlist action (Simulation Intelligence).

Contract under test:
- Viewing / running a simulation never touches live data; only an explicit
  Apply Shortlist request may update the live job applications.
- The shortlist mutation reuses the EXISTING application-status workflow
  (``RecruiterJobService.update_application_status``) — no second shortlist
  engine.
- The simulation itself stays immutable (status stays ``completed``).
- The operation is made explicit and confirmable (HTTP POST carrying the
  exact candidate ids), idempotent, and validated server-side for
  authorization, tenant isolation, execution completion, candidate/job
  relationship, and current live state.
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
    SimulationStatus,
)
from app.domain.models import AuditLog, Job, JobApplication, Notification, Organization, User
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationResult,
    SimulationScenario,
)

PASSWORD = "Shortlist@12345"


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
    session: AsyncSession, user: User, org: Organization, role: str,
) -> None:
    from app.domain.models import OrganizationMembership
    session.add(
        OrganizationMembership(
            user_id=user.id,
            organization_id=org.id,
            role=role,
            status=MembershipStatus.ACTIVE.value,
            joined_at=datetime.now(timezone.utc),
        ),
    )
    await session.flush()


async def _assign_role(session: AsyncSession, user: User, role_name: str) -> None:
    from app.domain.models import Role, UserRole
    role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    assert role, f"Role {role_name!r} must exist"
    session.add(UserRole(user_id=user.id, role_id=role.id))
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


async def _setup_recruiter(
    session: AsyncSession, org: Organization,
) -> User:
    user = await _create_user(
        session, "Shortlist Recruiter", f"recruiter_{uuid.uuid4().hex[:6]}@test.com",
    )
    await _assign_role(session, user, "recruiter")
    await _add_membership(session, user, org, "recruiter")
    return user


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
        experience_required="3 years",
        education_required="Bachelor's degree",
        status=JobStatus.PUBLISHED.value,
    )
    session.add(job)
    await session.flush()
    return job


async def _create_application(
    session: AsyncSession, job: Job, candidate: User, status: str = "applied",
) -> JobApplication:
    app = JobApplication(
        id=uuid.uuid4(),
        job_id=job.id,
        candidate_id=candidate.id,
        status=status,
    )
    session.add(app)
    await session.flush()
    return app


async def _create_scenario(
    session: AsyncSession, job: Job, user: User, org: Organization,
) -> SimulationScenario:
    scenario = SimulationScenario(
        id=uuid.uuid4(),
        organization_id=org.id,
        job_id=job.id,
        created_by=user.id,
        name="Shortlist Scenario",
        description="Test scenario for optional shortlist",
        status=SimulationStatus.COMPLETED.value,
        baseline_config={
            "scoring_weights": {"skills": 0.4, "experience": 0.25, "education": 0.15, "projects": 0.2},
            "threshold": 70,
            "shortlist_size": 10,
        },
        simulation_config={
            "scoring_weights": {"skills": 0.3, "experience": 0.4, "education": 0.1, "projects": 0.2},
            "threshold": 75,
            "shortlist_size": 15,
        },
    )
    session.add(scenario)
    await session.flush()
    return scenario


async def _create_execution(
    session: AsyncSession, scenario: SimulationScenario, job: Job, user: User,
    status: str = SimulationStatus.COMPLETED.value,
) -> SimulationExecution:
    execution = SimulationExecution(
        id=uuid.uuid4(),
        scenario_id=scenario.id,
        organization_id=scenario.organization_id,
        job_id=job.id,
        created_by=user.id,
        status=status,
        progress=100,
        total_candidates=3,
        processed_candidates=3,
        engine_version="test-v1",
        configuration_snapshot={
            "snapshot_version": "test-v1",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "job": {"id": str(job.id), "title": job.title},
            "candidate_ids": [],
        },
        summary={"candidate_count": 3},
        completed_at=datetime.now(timezone.utc) if status == SimulationStatus.COMPLETED.value else None,
    )
    session.add(execution)
    await session.flush()
    return execution


async def _create_results(
    session: AsyncSession,
    execution: SimulationExecution,
    scenario: SimulationScenario,
    candidate_ids: list[uuid.UUID],
    names: list[str],
) -> None:
    for idx, (cid, name) in enumerate(zip(candidate_ids, names), start=1):
        session.add(
            SimulationResult(
                id=uuid.uuid4(),
                execution_id=execution.id,
                scenario_id=scenario.id,
                candidate_id=cid,
                candidate_name=name,
                baseline_score=80.0 - idx,
                simulation_score=85.0 - idx,
                score_change=5.0,
                baseline_rank=idx,
                simulation_rank=idx,
                rank_change=0,
                baseline_status="qualified",
                simulation_status="qualified",
                baseline_shortlisted=True,
                simulation_shortlisted=True,
            ),
        )
    await session.flush()


async def _build_full_scenario(
    session: AsyncSession,
) -> dict:
    """Recruiter-owned org + job + 2 candidates with applications + completed
    simulation (scenario, execution, results). Returns identifiers + token."""
    org = await _create_org(session, "ShortlistOrg", "shortlist-org")
    recruiter = await _setup_recruiter(session, org)
    job = await _create_job(session, recruiter, org)
    scenario = await _create_scenario(session, job, recruiter, org)
    execution = await _create_execution(session, scenario, job, recruiter)

    alice = await _create_user(session, "Alice", f"alice_{uuid.uuid4().hex[:6]}@test.com")
    bob = await _create_user(session, "Bob", f"bob_{uuid.uuid4().hex[:6]}@test.com")
    app_alice = await _create_application(session, job, alice, "applied")
    app_bob = await _create_application(session, job, bob, "under_review")
    await _create_results(
        session, execution, scenario, [alice.id, bob.id], ["Alice", "Bob"],
    )
    await session.commit()

    return {
        "org": org,
        "recruiter": recruiter,
        "job": job,
        "scenario": scenario,
        "execution": execution,
        "alice": alice,
        "bob": bob,
        "app_alice_id": app_alice.id,
        "app_bob_id": app_bob.id,
    }


# ─────────────────────────────────────────────────────────────────────
# No live-data change without an explicit, confirmed Apply Shortlist
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_live_change_after_simulation_runs(
    client: AsyncClient, session: AsyncSession,
):
    """Test 6: running a simulation / viewing results must never touch live
    job data; applications stay untouched until an explicit apply."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.get(
        f"/api/v1/simulations/{ctx['scenario'].id}/results",
        headers=_auth(token),
    )
    assert resp.status_code == 200

    apps = (await session.execute(select(JobApplication))).scalars().all()
    assert {a.status for a in apps} == {"applied", "under_review"}

    scenario = await session.get(SimulationScenario, ctx["scenario"].id)
    assert scenario.status == SimulationStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_cancelled_or_empty_request_never_mutates(
    client: AsyncClient, session: AsyncSession,
):
    """Empty selection is rejected outright by schema validation (a cancelled
    checkbox flow simply never reaches the API)."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": []},
        headers=_auth(token),
    )
    assert resp.status_code == 422

    apps = (await session.execute(select(JobApplication))).scalars().all()
    assert {a.status for a in apps} == {"applied", "under_review"}


# ─────────────────────────────────────────────────────────────────────
# Apply Shortlist (happy path) — reuses the existing shortlist workflow
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_shortlist_updates_live_applications(
    client: AsyncClient, session: AsyncSession,
):
    """Test 2: explicit apply moves chosen candidates onto the live shortlist
    through the existing application-status workflow, without rerunning a
    ranking engine."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(ctx["alice"].id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["simulation_id"] == str(ctx["scenario"].id)
    assert data["execution_id"] == str(ctx["execution"].id)
    assert data["job_id"] == str(ctx["job"].id)
    assert data["scenario_status"] == SimulationStatus.COMPLETED.value  # simulation immutable
    assert data["shortlist_status"] == "applied"
    assert data["applied"] is True
    assert len(data["updated"]) == 1
    updated = data["updated"][0]
    assert updated["candidate_name"] == "Alice"
    assert updated["previous_status"] == "applied"
    assert updated["new_status"] == "shortlisted"
    assert updated["updated"] is True
    assert data["skipped"] == []

    app = await session.get(JobApplication, ctx["app_alice_id"])
    assert app.status == ApplicationStatus.SHORTLISTED.value

    # The existing workflow also notifies the candidate.
    notifs = (
        await session.execute(
            select(Notification).where(Notification.user_id == ctx["alice"].id),
        )
    ).scalars().all()
    assert len(notifs) == 1

    # An audit record captures which human applied it and when.
    audit = (
        await session.execute(
            select(AuditLog).where(AuditLog.event_type == "simulation_shortlist_applied"),
        )
    ).scalars().all()
    assert len(audit) == 1
    assert audit[0].user_id == ctx["recruiter"].id
    assert audit[0].resource_id == str(ctx["execution"].id)

    # Simulation is still COMPLETED — hypothesis was never overwritten.
    scenario = await session.get(SimulationScenario, ctx["scenario"].id)
    assert scenario.status == SimulationStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_apply_shortlist_multiple_candidates(
    client: AsyncClient, session: AsyncSession,
):
    """Both eligible candidates (applied + under_review) can be shortlisted in
    one confirmed request."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(ctx["alice"].id), str(ctx["bob"].id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["updated"]) == 2

    apps = (await session.execute(select(JobApplication))).scalars().all()
    assert {a.status for a in apps} == {ApplicationStatus.SHORTLISTED.value}


# ─────────────────────────────────────────────────────────────────────
# Idempotency + stale/conflict protection
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_shortlist_is_idempotent(
    client: AsyncClient, session: AsyncSession,
):
    """Test 10: re-requesting the same selection is safe — already-shortlisted
    candidates are reported as skipped and no duplicate notifications fire."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)
    url = f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist"
    payload = {"candidate_ids": [str(ctx["alice"].id)]}

    first = await client.post(url, json=payload, headers=_auth(token))
    assert first.status_code == 200
    assert len(first.json()["updated"]) == 1

    second = await client.post(url, json=payload, headers=_auth(token))
    assert second.status_code == 200
    data = second.json()
    assert data["updated"] == []
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["candidate_id"] == str(ctx["alice"].id)
    assert data["skipped"][0]["new_status"] == "shortlisted"
    assert data["skipped"][0]["updated"] is False

    notifs = (
        await session.execute(
            select(Notification).where(Notification.user_id == ctx["alice"].id),
        )
    ).scalars().all()
    assert len(notifs) == 1  # no duplicate notification on the retry


@pytest.mark.asyncio
async def test_apply_shortlist_conflict_on_stale_live_state(
    client: AsyncClient, session: AsyncSession,
):
    """Test 11: if the live application already moved forward (e.g. the
    candidate withdrew), the whole apply request fails with 409 and NO other
    candidate is shortlisted — nothing is silently half-applied."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)

    bob_app = await session.get(JobApplication, ctx["app_bob_id"])
    bob_app.status = ApplicationStatus.WITHDRAWN.value
    await session.flush()

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(ctx["alice"].id), str(ctx["bob"].id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 409, resp.text

    alice_app = await session.get(JobApplication, ctx["app_alice_id"])
    assert alice_app.status == ApplicationStatus.APPLIED.value  # untouched
    bob_app = await session.get(JobApplication, ctx["app_bob_id"])
    assert bob_app.status == ApplicationStatus.WITHDRAWN.value  # untouched


@pytest.mark.asyncio
async def test_apply_shortlist_rejects_candidate_not_in_simulation_pool(
    client: AsyncClient, session: AsyncSession,
):
    """The frontend checkbox list only offers simulated candidates, but a
    forged payload with a candidate outside the simulation's pool must be
    rejected (422)."""
    ctx = await _build_full_scenario(session)
    token = await _login(client, ctx["recruiter"].email)
    outsider = await _create_user(session, "Outsider", "outsider@test.com")

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(outsider.id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# ─────────────────────────────────────────────────────────────────────
# Permission & tenant isolation
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_shortlist_requires_admin_hr_or_recruiter(
    client: AsyncClient, session: AsyncSession,
):
    """Role gate: a candidate cannot trigger a shortlist action."""
    ctx = await _build_full_scenario(session)
    candidate_user = ctx["alice"]
    await _assign_role(session, candidate_user, "candidate")
    await session.commit()
    token = await _login(client, candidate_user.email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(ctx["alice"].id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_apply_shortlist_forbidden_for_non_owner_recruiter(
    client: AsyncClient, session: AsyncSession,
):
    """Test 8: a recruiter who can VIEW the simulation (same org, active
    membership) but does not own the job may not apply the shortlist."""
    ctx = await _build_full_scenario(session)
    other = await _setup_recruiter(session, ctx["org"])
    await session.commit()
    token = await _login(client, other.email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(ctx["alice"].id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_apply_shortlist_forbidden_across_tenants(
    client: AsyncClient, session: AsyncSession,
):
    """Test 9: recruiters from another organization cannot even access the
    simulation, let alone apply a shortlist."""
    ctx = await _build_full_scenario(session)
    org_b = await _create_org(session, "AnotherOrg", "another-org")
    outsider = await _setup_recruiter(session, org_b)
    await session.commit()
    token = await _login(client, outsider.email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={"candidate_ids": [str(ctx["alice"].id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


# ─────────────────────────────────────────────────────────────────────
# Execution gating
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_shortlist_requires_completed_execution(
    client: AsyncClient, session: AsyncSession,
):
    """Cannot apply from an execution that is still running or failed."""
    ctx = await _build_full_scenario(session)
    pending = await _create_execution(
        session, ctx["scenario"], ctx["job"], ctx["recruiter"],
        status=SimulationStatus.RUNNING.value,
    )
    await session.commit()
    token = await _login(client, ctx["recruiter"].email)

    resp = await client.post(
        f"/api/v1/simulations/{ctx['scenario'].id}/apply-shortlist",
        json={
            "candidate_ids": [str(ctx["alice"].id)],
            "execution_id": str(pending.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 409, resp.text