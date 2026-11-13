"""Tests for Simulation Reports & Decision Intelligence (Phase 13).

Covers:
- Report schema validation
- Report model creation
- Report API CRUD + RBAC
- Report generation from simulation data
- PDF/CSV export
- Immutability: live data unchanged after report generation
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import (
    EmploymentType,
    JobStatus,
    MembershipStatus,
    SimulationReportFormat,
    SimulationReportStatus,
    SimulationReportType,
    SimulationStatus,
)
from app.domain.models import Job, Organization, OrganizationMembership, User
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationImpact,
    SimulationReport,
    SimulationResult,
    SimulationScenario,
)

PASSWORD = "Report@12345"


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


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
) -> OrganizationMembership:
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role=role,
        status=MembershipStatus.ACTIVE.value,
        joined_at=datetime.now(timezone.utc),
    )
    session.add(membership)
    await session.flush()
    return membership


async def _create_job(
    session: AsyncSession, recruiter: User, org: Organization,
) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        organization_id=org.id,
        title="Senior Python Developer",
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


async def _assign_role(session: AsyncSession, user: User, role_name: str) -> None:
    from app.domain.models import Role, UserRole
    role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    assert role, f"Role {role_name!r} must exist"
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()


async def _setup_recruiter(
    session: AsyncSession, client: AsyncClient, org: Organization,
) -> tuple[User, str]:
    user = User(
        id=uuid.uuid4(),
        full_name="Report Recruiter",
        email=f"report_recruiter_{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await _assign_role(session, user, "recruiter")
    await _add_membership(session, user, org, "recruiter")
    token = await _login(client, user.email)
    return user, token


async def _create_scenario(
    session: AsyncSession,
    job: Job,
    user: User,
    org: Organization,
    name: str = "Test Scenario",
) -> SimulationScenario:
    scenario = SimulationScenario(
        id=uuid.uuid4(),
        organization_id=org.id,
        job_id=job.id,
        created_by=user.id,
        name=name,
        description="Test scenario for reports",
        status=SimulationStatus.COMPLETED.value,
        baseline_config={
            "scoring_weights": {"skills": 0.4, "experience": 0.25, "education": 0.15, "projects": 0.2},
            "threshold": 70,
            "shortlist_size": 10,
            "requirements": {"mandatory_skills": ["Python"], "preferred_skills": ["PostgreSQL"]},
        },
        simulation_config={
            "scoring_weights": {"skills": 0.3, "experience": 0.4, "education": 0.1, "projects": 0.2},
            "threshold": 75,
            "shortlist_size": 15,
            "requirements": {"mandatory_skills": ["Python", "Docker"], "preferred_skills": ["PostgreSQL"]},
        },
    )
    session.add(scenario)
    await session.flush()
    return scenario


async def _create_execution(
    session: AsyncSession,
    scenario: SimulationScenario,
    job: Job,
    user: User,
) -> SimulationExecution:
    execution = SimulationExecution(
        id=uuid.uuid4(),
        scenario_id=scenario.id,
        organization_id=scenario.organization_id,
        job_id=job.id,
        created_by=user.id,
        status=SimulationStatus.COMPLETED.value,
        progress=100,
        total_candidates=5,
        processed_candidates=5,
        engine_version="test-v1",
        configuration_snapshot={
            "snapshot_version": "test-v1",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "job": {"id": str(job.id), "title": job.title, "company": job.company},
            "baseline": scenario.baseline_config,
            "simulation": scenario.simulation_config,
            "candidate_ids": [],
        },
        summary={
            "candidate_count": 5,
            "threshold": {"baseline": 70, "simulation": 75},
            "shortlist": {"baseline": 10, "simulation": 15},
            "qualified": {"baseline": 3, "simulation": 2, "change": -1},
            "shortlisted": {"baseline": 2, "simulation": 3, "change": 1},
            "pool_movement": {"entered_shortlist": 1, "left_shortlist": 0},
            "score_movement": {"improved": 2, "declined": 2, "unchanged": 1},
            "average_score": {"baseline": 72.0, "simulation": 74.5, "change": 2.5},
            "top_candidate_changed": False,
        },
        completed_at=datetime.now(timezone.utc),
    )
    session.add(execution)
    await session.flush()
    return execution


async def _create_results(
    session: AsyncSession,
    execution: SimulationExecution,
    scenario: SimulationScenario,
) -> list[SimulationResult]:
    candidates = [
        ("Alice", 80, 85, 1, 1),
        ("Bob", 75, 70, 2, 3),
        ("Charlie", 70, 78, 3, 2),
        ("Diana", 65, 68, 4, 4),
        ("Eve", 60, 55, 5, 5),
    ]
    results = []
    for name, base_score, sim_score, base_rank, sim_rank in candidates:
        r = SimulationResult(
            id=uuid.uuid4(),
            execution_id=execution.id,
            scenario_id=scenario.id,
            candidate_id=uuid.uuid4(),
            candidate_name=name,
            baseline_score=base_score,
            simulation_score=sim_score,
            score_change=sim_score - base_score,
            baseline_rank=base_rank,
            simulation_rank=sim_rank,
            rank_change=base_rank - sim_rank,
            baseline_status="qualified" if base_score >= 70 else "not_qualified",
            simulation_status="qualified" if sim_score >= 75 else "not_qualified",
            baseline_shortlisted=base_rank <= 10,
            simulation_shortlisted=sim_rank <= 15,
        )
        session.add(r)
        results.append(r)
    await session.flush()
    return results


# ─────────────────────────────────────────────────────────────────────
# Schema Validation Tests
# ─────────────────────────────────────────────────────────────────────


def test_report_type_enum_values():
    """Report type enum has all required types."""
    assert SimulationReportType.SIMULATION.value == "simulation"
    assert SimulationReportType.CANDIDATE_IMPACT.value == "candidate_impact"
    assert SimulationReportType.FAIRNESS_IMPACT.value == "fairness_impact"
    assert SimulationReportType.COMPARISON.value == "comparison"
    assert SimulationReportType.SANDBOX.value == "sandbox"
    assert SimulationReportType.EXECUTIVE.value == "executive"
    assert SimulationReportType.TECHNICAL.value == "technical"


def test_report_status_enum_values():
    """Report status enum has all required statuses."""
    assert SimulationReportStatus.REQUESTED.value == "requested"
    assert SimulationReportStatus.GENERATING.value == "generating"
    assert SimulationReportStatus.COMPLETED.value == "completed"
    assert SimulationReportStatus.FAILED.value == "failed"


def test_report_format_enum_values():
    """Report format enum has all required formats."""
    assert SimulationReportFormat.WEB.value == "web"
    assert SimulationReportFormat.PDF.value == "pdf"
    assert SimulationReportFormat.JSON.value == "json"
    assert SimulationReportFormat.CSV.value == "csv"


def test_report_create_schema_validation():
    """SimulationReportCreate validates correctly."""
    from app.domain.simulation_report_schemas import SimulationReportCreate

    # Valid request
    req = SimulationReportCreate(
        report_type="simulation",
        simulation_id=uuid.uuid4(),
    )
    assert req.report_type == "simulation"
    assert req.format == "web"

    # Title stripping
    req2 = SimulationReportCreate(
        report_type="simulation",
        simulation_id=uuid.uuid4(),
        title="  Test Report  ",
    )
    assert req2.title == "Test Report"


# ─────────────────────────────────────────────────────────────────────
# API Tests
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_report_requires_auth(client: AsyncClient):
    """Unauthenticated users cannot create reports."""
    resp = await client.post(
        "/api/v1/simulation-reports",
        json={"report_type": "simulation", "simulation_id": str(uuid.uuid4())},
    )
    assert resp.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_list_reports_requires_auth(client: AsyncClient):
    """Unauthenticated users cannot list reports."""
    resp = await client.get("/api/v1/simulation-reports")
    assert resp.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_create_and_list_reports(
    client: AsyncClient, session: AsyncSession,
):
    """Full flow: create a simulation with execution, then generate and list reports."""
    org = await _create_org(session, "ReportOrg", "report-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    # Create report
    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
            "title": "Test Simulation Report",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    report = resp.json()
    assert report["status"] == "completed"
    assert report["report_type"] == "simulation"
    assert report["title"] == "Test Simulation Report"
    report_id = report["id"]

    # List reports
    resp = await client.get(
        "/api/v1/simulation-reports",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(r["id"] == report_id for r in data["items"])

    # Get single report
    resp = await client.get(
        f"/api/v1/simulation-reports/{report_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == report_id
    assert resp.json()["report_data"] is not None

    # Get report status
    resp = await client.get(
        f"/api/v1/simulation-reports/{report_id}/status",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Get report JSON
    resp = await client.get(
        f"/api/v1/simulation-reports/{report_id}/json",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    json_data = resp.json()
    assert "header" in json_data
    assert "executive_summary" in json_data
    assert "configuration_diff" in json_data


@pytest.mark.asyncio
async def test_report_contains_configuration_diff(
    client: AsyncClient, session: AsyncSession,
):
    """Report correctly shows baseline vs simulation configuration changes."""
    org = await _create_org(session, "ConfigOrg", "config-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()["report_data"]

    # Verify configuration diff
    config = data["configuration_diff"]
    weights = config["weights"]
    assert len(weights) >= 4  # skills, experience, education, projects

    skills_weight = next(w for w in weights if w["weight_name"] == "skills")
    assert skills_weight["baseline"] == 0.4
    assert skills_weight["simulation"] == 0.3
    assert skills_weight["change"] == -0.1

    exp_weight = next(w for w in weights if w["weight_name"] == "experience")
    assert exp_weight["baseline"] == 0.25
    assert exp_weight["simulation"] == 0.4
    assert exp_weight["change"] == 0.15

    # Verify threshold diff
    threshold = config["threshold"]
    assert threshold is not None
    assert threshold["baseline"] == 70
    assert threshold["simulation"] == 75

    # Verify requirement changes
    req_changes = config["requirement_changes"]
    assert any(rc["skill"] == "Docker" and rc["from_status"] == "not_required" for rc in req_changes)


@pytest.mark.asyncio
async def test_report_contains_candidate_impact(
    client: AsyncClient, session: AsyncSession,
):
    """Report correctly aggregates candidate impact from persisted results."""
    org = await _create_org(session, "CandOrg", "cand-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()["report_data"]

    impact = data["candidate_impact"]
    assert impact["total_candidates"] == 5
    assert impact["largest_score_movement"] > 0
    assert impact["largest_rank_movement"] > 0


@pytest.mark.asyncio
async def test_report_contains_executive_summary(
    client: AsyncClient, session: AsyncSession,
):
    """Report generates a factual executive summary."""
    org = await _create_org(session, "ExecOrg", "exec-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()["report_data"]

    summary = data["executive_summary"]
    assert summary["total_candidates_evaluated"] == 5
    assert len(summary["narrative"]) > 0
    assert "5" in summary["narrative"]  # mentions candidate count


@pytest.mark.asyncio
async def test_report_contains_isolation_notice(
    client: AsyncClient, session: AsyncSession,
):
    """Every report includes the simulation isolation notice."""
    org = await _create_org(session, "IsoOrg", "iso-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()["report_data"]

    limitations = data["limitations"]
    assert "hypothetical simulation" in limitations["simulation_isolation_notice"].lower()


@pytest.mark.asyncio
async def test_delete_report(
    client: AsyncClient, session: AsyncSession,
):
    """Users can delete their own reports."""
    org = await _create_org(session, "DelOrg", "del-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    # Create report
    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    # Delete report
    resp = await client.delete(
        f"/api/v1/simulation-reports/{report_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get(
        f"/api/v1/simulation-reports/{report_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_requires_simulation_for_type(
    client: AsyncClient, session: AsyncSession,
):
    """Simulation report type requires simulation_id."""
    org = await _create_org(session, "ValOrg", "val-org")
    user, token = await _setup_recruiter(session, client, org)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={"report_type": "simulation"},
        headers=_auth(token),
    )
    assert resp.status_code == 422 or resp.status_code == 400


@pytest.mark.asyncio
async def test_report_requires_sandbox_for_sandbox_type(
    client: AsyncClient, session: AsyncSession,
):
    """Sandbox report type requires sandbox_id."""
    org = await _create_org(session, "SbOrg", "sb-org")
    user, token = await _setup_recruiter(session, client, org)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={"report_type": "sandbox"},
        headers=_auth(token),
    )
    assert resp.status_code == 422 or resp.status_code == 400


@pytest.mark.asyncio
async def test_comparison_requires_multiple_scenarios(
    client: AsyncClient, session: AsyncSession,
):
    """Comparison report type requires at least 2 scenario IDs."""
    org = await _create_org(session, "CompOrg", "comp-org")
    user, token = await _setup_recruiter(session, client, org)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "comparison",
            "comparison_scenario_ids": [str(uuid.uuid4())],
        },
        headers=_auth(token),
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_immutability_after_report_generation(
    client: AsyncClient, session: AsyncSession,
):
    """Report generation does not modify live hiring data."""
    org = await _create_org(session, "ImmOrg", "imm-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    results = await _create_results(session, execution, scenario)
    await session.commit()

    # Record original state
    original_job_title = job.title
    original_scenario_status = scenario.status
    original_result_scores = {r.id: r.baseline_score for r in results}

    # Generate report
    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201

    # Verify no changes to live data
    await session.refresh(job)
    await session.refresh(scenario)
    assert job.title == original_job_title
    assert scenario.status == original_scenario_status

    for r in results:
        await session.refresh(r)
        assert r.baseline_score == original_result_scores[r.id]


@pytest.mark.asyncio
async def test_pdf_export(
    client: AsyncClient, session: AsyncSession,
):
    """PDF export returns a valid PDF."""
    org = await _create_org(session, "PdfOrg", "pdf-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/simulation-reports/{report_id}/pdf",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # Verify it starts with PDF header
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_csv_export(
    client: AsyncClient, session: AsyncSession,
):
    """CSV export returns valid CSV content."""
    org = await _create_org(session, "CsvOrg", "csv-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "simulation",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/simulation-reports/{report_id}/csv?section=candidate_impact",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    # Verify CSV has header row
    content = resp.content.decode("utf-8")
    assert "Candidate ID" in content


@pytest.mark.asyncio
async def test_candidate_report_type(
    client: AsyncClient, session: AsyncSession,
):
    """Candidate impact report type works correctly."""
    org = await _create_org(session, "CiOrg", "ci-org")
    user, token = await _setup_recruiter(session, client, org)
    job = await _create_job(session, user, org)
    scenario = await _create_scenario(session, job, user, org)
    execution = await _create_execution(session, scenario, job, user)
    await _create_results(session, execution, scenario)
    await session.commit()

    resp = await client.post(
        "/api/v1/simulation-reports",
        json={
            "report_type": "candidate_impact",
            "simulation_id": str(scenario.id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    report = resp.json()
    assert report["report_type"] == "candidate_impact"
    assert report["status"] == "completed"
    assert report["report_data"]["candidate_impact"]["total_candidates"] == 5
