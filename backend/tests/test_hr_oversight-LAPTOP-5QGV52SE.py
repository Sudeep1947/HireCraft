"""Tests for the Revised Phase 14 HR organization-level oversight surface.

Contract under test:
- HR reads the *same* ``JobApplication`` rows as the recruiter and candidate;
  there is no separate HR application model or status.
- Every figure is a real aggregate over the jobs the caller is entitled to
  read. No hardcoded distribution, no platform-wide fallback for a tenant user.
- The tenant comes from the caller's memberships, never from the request, so
  a cross-tenant HR user cannot read, list or drill into another org's data.
- The overview deliberately reports ``is_platform_scope`` so the UI cannot
  present a cross-tenant number as an org number (or vice versa).
- HR is read-only: no endpoint here can transition, decide, schedule or assign.
- The drill-down reuses the existing explainability / fairness / interview /
  assessment projections, so HR sees no more than an entitled recruiter, and
  candidate-private fields stay out of the oversight payload.
- The timeline is composed only from records that already exist; missing
  sections come back absent, never invented.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    AuditEventType,
    EmploymentType,
    JobStatus,
    MembershipStatus,
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
    ScreeningResult,
    User,
)
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
)

PASSWORD = "HRoversight@12345"

OVERVIEW = "/api/v1/hr/overview"
JOBS = "/api/v1/hr/jobs"


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
    session: AsyncSession, name: str, email: str, role: str,
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
    await _assign_role(session, user.id, role)
    return user


async def _add_membership(
    session: AsyncSession, user: User, org: Organization, role: str,
) -> None:
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


async def _create_org(session: AsyncSession, suffix: str) -> Organization:
    org = Organization(
        name=f"Org {suffix}",
        slug=f"org-hr-{suffix}",
        description=f"Org {suffix}",
        status="active",
    )
    session.add(org)
    await session.flush()
    return org


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
        required_skills=["Python"],
        status=JobStatus.PUBLISHED.value,
    )
    session.add(job)
    await session.flush()
    return job


async def _apply(
    session: AsyncSession, job: Job, candidate: User,
    status: ApplicationStatus = ApplicationStatus.APPLIED,
) -> JobApplication:
    application = JobApplication(
        job_id=job.id, candidate_id=candidate.id, status=status.value,
    )
    session.add(application)
    await session.flush()
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.record_creation(application, actor=candidate)
    if status is not ApplicationStatus.APPLIED:
        await lifecycle.transition_application(
            application.id, status.value, await _job_owner(session, job),
        )
    await session.refresh(application)
    return application


async def _job_owner(session: AsyncSession, job: Job) -> User:
    """The job's recruiter, who is the actor allowed to drive a transition."""
    return await session.get(User, job.recruiter_id)


async def _another_candidate(session: AsyncSession, suffix: str) -> User:
    """A fresh candidate.

    ``job_applications`` is unique on (job_id, candidate_id), so any test that
    needs several applications on one job must use a different person per
    application rather than re-applying the same candidate.
    """
    return await _create_user(
        session, f"Extra {suffix}", f"extra-{suffix}@test.com",
        RoleName.CANDIDATE.value,
    )


async def _tenant(
    session: AsyncSession, suffix: str,
) -> dict:
    """One organization with a recruiter, an HR user, a candidate and a job."""
    org = await _create_org(session, suffix)
    recruiter = await _create_user(
        session, f"Recruiter {suffix}", f"rec{suffix}@test.com",
        RoleName.RECRUITER.value,
    )
    hr = await _create_user(
        session, f"HR {suffix}", f"hr{suffix}@test.com", "hr",
    )
    candidate = await _create_user(
        session, f"Candidate {suffix}", f"cand{suffix}@test.com",
        RoleName.CANDIDATE.value,
    )
    await _add_membership(session, recruiter, org, RoleName.RECRUITER.value)
    await _add_membership(session, hr, org, "hr")
    job = await _create_job(session, recruiter, org, "Backend Engineer")
    application = await _apply(session, job, candidate)
    return {
        "org": org,
        "recruiter": recruiter,
        "hr": hr,
        "candidate": candidate,
        "job": job,
        "app": application,
    }


# ----------------------------------------------------------------------
# Overview: real, org-scoped numbers
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_overview_counts_only_the_callers_organization(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "a")
    other = await _tenant(session, "b")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(OVERVIEW, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["is_platform_scope"] is False
    assert body["organization_ids"] == [str(mine["org"].id)]
    counts = body["counts"]
    # Exactly our own single published job / single application.
    assert counts["open_positions"] == 1
    assert counts["total_applications"] == 1
    assert counts["distinct_candidates"] == 1
    assert counts["distinct_recruiters"] == 1
    assert body["applications_by_status"] == {"applied": 1}
    # The other tenant must not appear anywhere in the payload.
    assert str(other["org"].id) not in resp.text
    assert other["candidate"].full_name not in resp.text
    assert other["job"].title not in resp.text


@pytest.mark.asyncio
async def test_overview_reports_the_funnel_from_real_statuses(
    client: AsyncClient, session: AsyncSession,
):
    tenant = await _tenant(session, "funnel")
    job = tenant["job"]
    candidates = [
        await _create_user(
            session, f"Cand {i}", f"c{i}@funnel.test.com",
            RoleName.CANDIDATE.value,
        )
        for i in range(3)
    ]
    await _apply(session, job, candidates[0], ApplicationStatus.SELECTED)
    await _apply(session, job, candidates[1], ApplicationStatus.REJECTED)
    await _apply(session, job, candidates[2], ApplicationStatus.HIRED)

    token = await _login(client, tenant["hr"].email)
    resp = await client.get(OVERVIEW, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    counts = resp.json()["counts"]
    # 1 seeded + 3 extra = 4 applications.
    assert counts["total_applications"] == 4
    assert counts["selected"] == 1
    assert counts["rejected"] == 1
    assert counts["hired"] == 1
    assert resp.json()["applications_by_status"]["hired"] == 1


@pytest.mark.asyncio
async def test_overview_decision_counters_are_exact_status_counts(
    client: AsyncClient, session: AsyncSession,
):
    """Regression: an offers figure must not be a disguised terminal sum.

    ``offered`` counts the canonical ``offered`` status and nothing else. Even
    though there are no applications in the offered status here, hired +
    rejected + withdrawn (a terminal sum) is reported separately as a plain
    number and is not labelled "offers", so the two signals cannot be conflated.
    """
    tenant = await _tenant(session, "offers")
    candidates = [
        await _create_user(
            session, f"Term {i}", f"term{i}@offers.test.com",
            RoleName.CANDIDATE.value,
        )
        for i in range(2)
    ]
    await _apply(session, tenant["job"], candidates[0], ApplicationStatus.HIRED)
    await _apply(session, tenant["job"], candidates[1], ApplicationStatus.REJECTED)

    token = await _login(client, tenant["hr"].email)
    resp = await client.get(OVERVIEW, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    counts = resp.json()["counts"]
    assert counts["offered"] == 0
    assert counts["hired"] == 1
    assert counts["rejected"] == 1
    assert counts["withdrawn"] == 0


@pytest.mark.asyncio
async def test_overview_assessment_counters_distinguish_assigned_from_all(
    client: AsyncClient, session: AsyncSession,
):
    """``assessments_assigned`` is the in-funnel ``assigned`` count only.

    The overview must not present every attempt (including completed and
    expired ones) as "assigned". The all-status total lives in
    ``assessment_attempts``; the full status breakdown stays in
    ``assessments_by_status`` so nothing is summed away.
    """
    from app.domain.enums import AttemptStatus
    from app.domain.models import Assessment, CandidateAssessment

    tenant = await _tenant(session, "attempts")
    job = tenant["job"]

    assessment = Assessment(
        title="HR attempts",
        description="Attempts counting test.",
        job_id=job.id,
        created_by=tenant["recruiter"].id,
    )
    session.add(assessment)
    await session.flush()

    def _mk_attempt(status: str, number: int) -> CandidateAssessment:
        return CandidateAssessment(
            application_id=tenant["app"].id,
            assessment_id=assessment.id,
            candidate_id=tenant["candidate"].id,
            attempt_number=number,
            status=status,
            assigned_by=tenant["recruiter"].id,
        )

    session.add_all(
        [
            _mk_attempt(AttemptStatus.ASSIGNED.value, 1),
            _mk_attempt(AttemptStatus.ASSIGNED.value, 2),
            _mk_attempt(AttemptStatus.COMPLETED.value, 3),
            _mk_attempt(AttemptStatus.EXPIRED.value, 4),
        ]
    )
    await session.commit()

    token = await _login(client, tenant["hr"].email)
    resp = await client.get(OVERVIEW, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Only the two still-assigned attempts count as "assigned".
    assert body["counts"]["assessments_assigned"] == 2
    assert body["counts"]["assessment_attempts"] == 4
    assert body["assessments_by_status"]["assigned"] == 2
    assert body["assessments_by_status"]["completed"] == 1
    assert body["assessments_by_status"]["expired"] == 1


@pytest.mark.asyncio
async def test_overview_counts_no_hardcoded_workforce_distributions(
    client: AsyncClient, session: AsyncSession,
):
    """Regression: the old /analytics/hr returned invented numbers.

    The oversight overview must expose only what it actually counted. No
    department distribution, gender distribution, named recruiter scores, or
    a fabricated time-to-hire may appear in the payload.
    """
    await _tenant(session, "nofake")
    token = await _login(client, "hrnofake@test.com")
    resp = await client.get(OVERVIEW, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for fabricated in (
        "department_distribution", "gender_distribution", "diversity_index",
        "turnover_rate", "avg_time_to_hire", "recruiter_performance",
        "Recruiter A", "Recruiter B", "Recruiter C", "Non-binary",
    ):
        assert fabricated not in resp.text, f"fabricated field leaked: {fabricated}"
    assert "acceptance_rate" not in body["counts"]


@pytest.mark.asyncio
async def test_overview_for_a_user_with_no_organization_is_empty_not_global(
    client: AsyncClient, session: AsyncSession,
):
    """An HR user outside every org must see an empty scope, not the platform."""
    outsider = await _create_user(
        session, "No Org HR", "orphanhr@test.com", "hr",
    )
    await _tenant(session, "elsewhere")
    await session.commit()
    token = await _login(client, outsider.email)
    resp = await client.get(OVERVIEW, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_platform_scope"] is False
    assert body["organization_ids"] == []
    assert body["counts"]["total_applications"] == 0
    assert body["counts"]["open_positions"] == 0


# ----------------------------------------------------------------------
# Jobs + drill-down
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_list_is_org_scoped_with_real_funnel(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "own")
    other = await _tenant(session, "notmine")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(JOBS, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["is_platform_scope"] is False
    assert body["total"] == 1
    job = body["jobs"][0]
    assert job["id"] == str(mine["job"].id)
    assert job["title"] == "Backend Engineer"
    assert job["recruiter_id"] == str(mine["recruiter"].id)
    assert job["recruiter_name"] == mine["recruiter"].full_name
    assert job["application_count"] == 1
    assert job["applications_by_status"] == {"applied": 1}
    assert job["open_application_count"] == 1
    assert job["hired_count"] == 0
    assert str(other["job"].id) not in resp.text


@pytest.mark.asyncio
async def test_job_application_list_is_authorized_by_job_access(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "list")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(
        f"{JOBS}/{mine['job'].id}/applications", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_id"] == str(mine["job"].id)
    assert body["total"] == 1
    summary = body["applications"][0]
    assert summary["id"] == str(mine["app"].id)
    assert summary["candidate_id"] == str(mine["candidate"].id)
    assert summary["status"] == "applied"
    assert summary["recruiter_id"] == str(mine["recruiter"].id)
    assert summary["has_interview"] is False
    assert summary["has_assessment"] is False


@pytest.mark.asyncio
async def test_job_application_list_refuses_a_cross_tenant_job(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "guard")
    other = await _tenant(session, "victim")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(
        f"{JOBS}/{other['job'].id}/applications", headers=_auth(token),
    )
    assert resp.status_code in (403, 404), resp.text
    assert str(other["app"].id) not in resp.text


# ----------------------------------------------------------------------
# Application detail
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_application_detail_is_the_same_application_the_recruiter_decided(
    client: AsyncClient, session: AsyncSession,
):
    tenant = await _tenant(session, "detail")
    # Move it through the authoritative path so history/decision exist.
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.transition_application(
        tenant["app"].id, ApplicationStatus.SHORTLISTED.value, tenant["recruiter"],
    )
    token = await _login(client, tenant["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{tenant['app'].id}", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["id"] == str(tenant["app"].id)
    assert body["job"]["id"] == str(tenant["job"].id)
    assert body["job"]["recruiter_id"] == str(tenant["recruiter"].id)
    assert body["candidate"]["id"] == str(tenant["candidate"].id)
    # Status matches the recruiter's transition exactly - one SSOT.
    assert body["status"] == "shortlisted"
    assert body["decision"]["status"] == "shortlisted"
    assert body["decision"]["decided_by"] == str(tenant["recruiter"].id)
    assert body["decision"]["decided_by_name"] == tenant["recruiter"].full_name
    assert body["is_terminal"] is False
    # Creation + shortlist events are composed from real history rows.
    statuses = [e["to_status"] for e in body["timeline"]]
    assert "applied" in statuses
    assert "shortlisted" in statuses


@pytest.mark.asyncio
async def test_application_detail_excludes_candidate_private_and_bulk_fields(
    client: AsyncClient, session: AsyncSession,
):
    tenant = await _tenant(session, "privacy")
    token = await _login(client, tenant["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{tenant['app'].id}", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    candidate = body["candidate"]
    # Identity only: no roles, memberships, password or token surface.
    assert set(candidate.keys()) == {
        "id", "full_name", "email", "is_active", "account_status", "has_resume",
    }
    # The raw cover letter is not dumped into the oversight payload.
    assert "cover_letter" not in body
    assert body["cover_letter_available"] is False
    # No free-text recruiter note leaks either.
    assert "recruiter_notes" not in body
    assert "decision_comment" in body["decision"]  # present, but null here
    assert body["decision"]["decision_comment"] is None


@pytest.mark.asyncio
async def test_application_detail_refuses_a_cross_tenant_application(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "idor")
    other = await _tenant(session, "idor-other")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{other['app'].id}", headers=_auth(token),
    )
    assert resp.status_code in (403, 404), resp.text


@pytest.mark.asyncio
async def test_application_detail_of_an_unknown_id_is_404(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "missing")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{uuid.uuid4()}", headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_candidate_cannot_read_the_hr_oversight_surface(
    client: AsyncClient, session: AsyncSession,
):
    tenant = await _tenant(session, "canddeny")
    token = await _login(client, tenant["candidate"].email)
    for path in (OVERVIEW, JOBS, f"/api/v1/hr/applications/{tenant['app'].id}"):
        resp = await client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_hr_cannot_write_hiring_state_through_the_oversight_surface(
    client: AsyncClient, session: AsyncSession,
):
    """HR oversight is read-only; writes stay with the recruiter."""
    tenant = await _tenant(session, "readonly")
    token = await _login(client, tenant["hr"].email)
    for method, path in (
        ("post", f"/api/v1/hr/applications/{tenant['app'].id}"),
        ("post", f"/api/v1/hr/jobs/{tenant['job'].id}/applications"),
        ("patch", f"/api/v1/hr/applications/{tenant['app'].id}"),
    ):
        resp = await getattr(client, method)(path, headers=_auth(token), json={})
        assert resp.status_code in (403, 404, 405), f"{method} {path} -> {resp.status_code}"
    resp = await client.delete(
        f"/api/v1/hr/applications/{tenant['app'].id}", headers=_auth(token),
    )
    assert resp.status_code in (403, 404, 405)


# ----------------------------------------------------------------------
# Audit
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hr_application_read_is_audited(
    client: AsyncClient, session: AsyncSession,
):
    tenant = await _tenant(session, "audited")
    token = await _login(client, tenant["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{tenant['app'].id}", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    await session.commit()

    events = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.HR_APPLICATION_VIEWED.value,
            )
        )
    ).scalars().all()
    matching = [e for e in events if e.resource_id == str(tenant["app"].id)]
    assert len(matching) == 1
    event = matching[0]
    assert event.user_id == tenant["hr"].id
    assert event.organization_id == tenant["org"].id
    assert event.resource_type == "job_application"


@pytest.mark.asyncio
async def test_hr_detail_reports_real_interview_and_assessment_presence(
    client: AsyncClient, session: AsyncSession,
):
    """Phase 11/12 links must surface in the HR drill-down as reused data.

    The interview and assessment blocks are the existing integration services'
    own staff projections, so this asserts the linkage is visible to HR rather
    than asserting a new HR-side record was created.
    """
    from app.domain.application_interview_schemas import (
        ApplicationInterviewScheduleRequest,
    )
    from app.services.interview.application_interview_service import (
        ApplicationInterviewIntegrationService,
    )

    tenant = await _tenant(session, "evidence")
    job, recruiter, candidate = tenant["job"], tenant["recruiter"], tenant["candidate"]
    lifecycle = ApplicationLifecycleService(session)
    await lifecycle.transition_application(
        tenant["app"].id, ApplicationStatus.SHORTLISTED.value, recruiter,
    )

    interview_service = ApplicationInterviewIntegrationService(session)
    await interview_service.schedule(
        tenant["app"].id,
        ApplicationInterviewScheduleRequest(
            scheduled_at=datetime.now(timezone.utc).replace(microsecond=0),
        ),
        recruiter,
    )
    await session.commit()

    token = await _login(client, tenant["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{tenant['app'].id}", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The interview really is linked and really is reported.
    assert body["interview"] is not None
    assert body["status"] == "interview_scheduled"
    # And it appears in the composed timeline as an interview-sourced event.
    sources = {e["source"] for e in body["timeline"]}
    assert "interview" in sources
    assert "status_history" in sources
    # The assessment block is the Phase 12 integration's own projection for
    # this application. With no attempt made it reports an empty attempt list
    # rather than None, which is the honest answer - and it must agree with the
    # application's real status, proving it is the reused service's output.
    assert body["assessment"] is not None
    assert body["assessment"]["application_id"] == str(tenant["app"].id)
    assert body["assessment"]["application_status"] == body["status"]
    assert body["assessment"]["attempt_count"] == 0
    assert body["assessment"]["attempts"] == []


@pytest.mark.asyncio
async def test_refused_hr_read_writes_no_oversight_audit_event(
    client: AsyncClient, session: AsyncSession,
):
    mine = await _tenant(session, "auditdeny")
    other = await _tenant(session, "auditdeny-other")
    token = await _login(client, mine["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{other['app'].id}", headers=_auth(token),
    )
    assert resp.status_code in (403, 404)
    await session.commit()
    events = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.HR_APPLICATION_VIEWED.value,
                AuditLog.resource_id == str(other["app"].id),
            )
        )
    ).scalars().all()
    assert events == []


@pytest.mark.asyncio
async def test_hr_read_does_not_alter_the_application(
    client: AsyncClient, session: AsyncSession,
):
    """Oversight must be observationally read-only."""
    tenant = await _tenant(session, "nostate")
    before = tenant["app"].status
    history_before = len(
        (
            await session.execute(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == tenant["app"].id,
                )
            )
        ).scalars().all()
    )
    token = await _login(client, tenant["hr"].email)
    resp = await client.get(
        f"/api/v1/hr/applications/{tenant['app'].id}", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    await session.refresh(tenant["app"])
    assert tenant["app"].status == before
    history_after = len(
        (
            await session.execute(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == tenant["app"].id,
                )
            )
        ).scalars().all()
    )
    assert history_after == history_before

# ----------------------------------------------------------------------
# Recruiter (employer) monitoring
# ----------------------------------------------------------------------
RECRUITERS = "/api/v1/hr/recruiters"
ATTENTION = "/api/v1/hr/attention"
QUALITY = "/api/v1/hr/quality"
PIPELINE = "/api/v1/hr/pipeline"


# ----------------------------------------------------------------------
# Funnel-stage drill-down (makes the overview pipeline clickable)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stage_drilldown_groups_a_stage_by_job(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "pa")
    other = await _create_job(
        session, tenant["recruiter"], tenant["org"], "Data Engineer",
    )
    for index in range(2):
        await _apply(
            session, other, await _another_candidate(session, f"pa{index}"),
        )
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(f"{PIPELINE}/applied", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "applied"
    assert body["total"] == 3
    # Busiest job first, so the drill-down answers "where is this stage?".
    counts = {j["job_title"]: j["count"] for j in body["jobs"]}
    assert counts == {"Data Engineer": 2, "Backend Engineer": 1}
    assert all(j["job_id"] for j in body["jobs"])
    # Every row carries the recruiter, so the list is readable without a second call.
    assert all(j["recruiter_id"] == str(tenant["recruiter"].id) for j in body["jobs"])


@pytest.mark.asyncio
async def test_stage_drilldown_only_counts_the_requested_stage(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "pb")
    await _apply(
        session, tenant["job"], await _another_candidate(session, "pb"),
        status=ApplicationStatus.SHORTLISTED,
    )
    token = await _login(client, tenant["hr"].email)

    body = (await client.get(f"{PIPELINE}/shortlisted", headers=_auth(token))).json()
    assert body["total"] == 1
    assert [j["count"] for j in body["jobs"]] == [1]

    # The stage that holds the other application must not appear here.
    body = (await client.get(f"{PIPELINE}/applied", headers=_auth(token))).json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_an_unknown_stage_drilldown_returns_nothing(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "pc")
    token = await _login(client, tenant["hr"].email)

    body = (await client.get(f"{PIPELINE}/not_a_stage", headers=_auth(token))).json()
    # A hand-edited link must not silently render the whole pipeline.
    assert body["total"] == 0
    assert body["jobs"] == []


@pytest.mark.asyncio
async def test_stage_drilldown_never_reaches_another_organization(
    client: AsyncClient, session: AsyncSession,
) -> None:
    mine = await _tenant(session, "pd")
    await _tenant(session, "pe")
    token = await _login(client, mine["hr"].email)

    body = (await client.get(f"{PIPELINE}/applied", headers=_auth(token))).json()
    assert body["total"] == 1
    assert [j["job_title"] for j in body["jobs"]] == ["Backend Engineer"]


@pytest.mark.asyncio
async def test_candidate_cannot_read_the_stage_drilldown(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "pf")
    token = await _login(client, tenant["candidate"].email)
    resp = await client.get(f"{PIPELINE}/applied", headers=_auth(token))
    assert resp.status_code == 403, resp.text



@pytest.mark.asyncio
async def test_recruiter_list_rolls_up_the_callers_organization_funnel(
    client: AsyncClient, session: AsyncSession,
) -> None:
    mine = await _tenant(session, "ra")
    theirs = await _tenant(session, "rb")
    token = await _login(client, mine["hr"].email)

    resp = await client.get(RECRUITERS, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["is_platform_scope"] is False
    names = {r["id"] for r in body["recruiters"]}
    assert str(mine["recruiter"].id) in names
    # The other tenant's recruiter has no job in scope, so it must be absent
    # rather than present with zeroes -- otherwise this list enumerates users.
    assert str(theirs["recruiter"].id) not in names

    row = next(r for r in body["recruiters"] if r["id"] == str(mine["recruiter"].id))
    assert row["application_count"] == 1
    assert row["applications_by_status"] == {"applied": 1}
    assert row["open_job_count"] == 1
    assert row["total_job_count"] == 1
    # A brand new application has not been advanced yet: 0.0, not None.
    assert row["advancement_rate"] == 0.0
    assert row["hired_count"] == 0


@pytest.mark.asyncio
async def test_recruiter_advancement_rate_counts_recorded_decisions(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "rc")
    for index, status in enumerate(
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED)
    ):
        await _apply(
            session, tenant["job"],
            await _another_candidate(session, f"rc{index}"), status=status,
        )
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(RECRUITERS, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    row = resp.json()["recruiters"][0]
    # 3 applications: applied (not advanced), shortlisted and rejected (both
    # advanced, because the recruiter reached a decision on them).
    assert row["application_count"] == 3
    assert row["advancement_rate"] == round(2 / 3, 4)


@pytest.mark.asyncio
async def test_recruiter_detail_returns_the_jobs_behind_the_aggregate(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "rd")
    second = await _create_job(
        session, tenant["recruiter"], tenant["org"], "Platform Engineer",
    )
    await _apply(session, second, tenant["candidate"])
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(
        f"{RECRUITERS}/{tenant['recruiter'].id}", headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recruiter"]["id"] == str(tenant["recruiter"].id)
    assert {j["title"] for j in body["jobs"]} == {
        "Backend Engineer", "Platform Engineer",
    }
    # The aggregate equals the sum of the rows, never a second source of truth.
    assert body["recruiter"]["application_count"] == sum(
        j["application_count"] for j in body["jobs"]
    )


@pytest.mark.asyncio
async def test_recruiter_detail_of_a_cross_tenant_recruiter_is_404(
    client: AsyncClient, session: AsyncSession,
) -> None:
    mine = await _tenant(session, "re")
    theirs = await _tenant(session, "rf")
    token = await _login(client, mine["hr"].email)

    resp = await client.get(
        f"{RECRUITERS}/{theirs['recruiter'].id}", headers=_auth(token),
    )
    # 404, not 403: an out-of-scope recruiter must be indistinguishable from an
    # unknown id so this route cannot confirm that a user id exists elsewhere.
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_recruiter_detail_of_an_unknown_id_is_404(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "rg")
    token = await _login(client, tenant["hr"].email)
    resp = await client.get(f"{RECRUITERS}/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# ----------------------------------------------------------------------
# Attention center
# ----------------------------------------------------------------------
async def _backdate(session: AsyncSession, application: JobApplication, days: int) -> None:
    """Age an application and its status history so staleness is measurable."""
    when = datetime.now(timezone.utc) - timedelta(days=days)
    application.created_at = when
    rows = (
        await session.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == application.id,
            )
        )
    ).scalars().all()
    for row in rows:
        row.changed_at = when
    await session.flush()


@pytest.mark.asyncio
async def test_attention_is_empty_when_nothing_crosses_a_threshold(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "ha")
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(ATTENTION, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["total_flagged"] == 0
    assert body["truncated"] is False
    assert body["is_platform_scope"] is False
    # The screen must be able to explain its own numbers.
    assert body["thresholds"]["stale_application_days"] == 7
    assert body["thresholds"]["fairness_gap"] == 0.8


@pytest.mark.asyncio
async def test_attention_flags_a_stale_open_application_with_the_measured_age(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "hb")
    await _backdate(session, tenant["app"], 30)
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(ATTENTION, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    items = [i for i in resp.json()["items"] if i["rule"] == "stale_application"]
    assert len(items) == 1
    item = items[0]
    assert item["application_id"] == str(tenant["app"].id)
    assert item["job_id"] == str(tenant["job"].id)
    assert item["recruiter_id"] == str(tenant["recruiter"].id)
    assert item["severity"] == "warning"
    # The measured age is reported next to the threshold that it crossed.
    assert item["measured_value"] == 30
    assert item["threshold_value"] == 7
    assert "applied" in item["reason"]


@pytest.mark.asyncio
async def test_attention_honours_a_configured_threshold_instead_of_a_hardcoded_one(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured threshold must actually change what fires.

    A 5-day-old application is a non-event at the 7-day default and an event at
    a 3-day setting. Pinning the default only would let a hardcoded 7 pass this
    suite while ignoring configuration entirely.
    """
    tenant = await _tenant(session, "hcfg")
    await _backdate(session, tenant["app"], 5)
    token = await _login(client, tenant["hr"].email)

    default = await client.get(ATTENTION, headers=_auth(token))
    assert not [
        i for i in default.json()["items"] if i["rule"] == "stale_application"
    ], "5 days must not trip the 7-day default"

    settings = get_settings()
    monkeypatch.setattr(settings, "hr_attention_stale_application_days", 3)

    tightened = await client.get(ATTENTION, headers=_auth(token))
    assert tightened.status_code == 200, tightened.text
    body = tightened.json()
    stale = [i for i in body["items"] if i["rule"] == "stale_application"]
    assert len(stale) == 1
    assert stale[0]["threshold_value"] == 3
    # The response echoes the thresholds actually applied, so the UI can never
    # show a stale number next to a fresh rule.
    assert body["thresholds"]["stale_application_days"] == 3


@pytest.mark.asyncio
async def test_attention_does_not_flag_a_closed_application_as_stale(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "hc")
    await session.get(JobApplication, tenant["app"].id)
    tenant["app"].status = ApplicationStatus.REJECTED.value
    tenant["app"].decided_at = datetime.now(timezone.utc)
    await session.flush()
    await _backdate(session, tenant["app"], 60)
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(ATTENTION, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    # A rejected application is finished, not stalled, however old it is.
    assert [i for i in resp.json()["items"] if i["rule"] == "stale_application"] == []


@pytest.mark.asyncio
async def test_attention_flags_a_failed_screening_as_critical(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "hd")
    await session.get(JobApplication, tenant["app"].id)
    tenant["app"].screening_status = ScreeningStatus.FAILED.value
    await session.flush()
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(ATTENTION, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    items = [i for i in resp.json()["items"] if i["rule"] == "screening_failed"]
    assert len(items) == 1
    assert items[0]["severity"] == "critical"
    assert items[0]["application_id"] == str(tenant["app"].id)


@pytest.mark.asyncio
async def test_attention_is_deterministic_across_repeated_requests(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "he")
    await _backdate(session, tenant["app"], 20)
    await session.get(JobApplication, tenant["app"].id)
    tenant["app"].screening_status = ScreeningStatus.FAILED.value
    await session.flush()
    token = await _login(client, tenant["hr"].email)

    first = (await client.get(ATTENTION, headers=_auth(token))).json()
    second = (await client.get(ATTENTION, headers=_auth(token))).json()
    # A screen that reshuffles itself between refreshes cannot be acted on.
    assert first["items"] == second["items"]
    # A critical item outranks a warning one.
    rank = {"critical": 0, "warning": 1, "info": 2}
    assert [i["severity"] for i in first["items"]] == sorted(
        (i["severity"] for i in first["items"]), key=lambda s: rank[s],
    )


@pytest.mark.asyncio
async def test_attention_never_reaches_another_organization(
    client: AsyncClient, session: AsyncSession,
) -> None:
    mine = await _tenant(session, "hf")
    theirs = await _tenant(session, "hg")
    await _backdate(session, theirs["app"], 90)
    token = await _login(client, mine["hr"].email)

    body = (await client.get(ATTENTION, headers=_auth(token))).json()
    assert body["items"] == []
    assert body["total_flagged"] == 0


@pytest.mark.asyncio
async def test_attention_exposes_no_write_method(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "hh")
    token = await _login(client, tenant["hr"].email)
    for method in ("post", "put", "patch", "delete"):
        kwargs = {} if method == "delete" else {"json": {}}
        resp = await getattr(client, method)(ATTENTION, headers=_auth(token), **kwargs)
        assert resp.status_code == 405, f"{method} {ATTENTION} -> {resp.status_code}"


# ----------------------------------------------------------------------
# Hiring quality
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_quality_reports_null_rates_when_there_are_no_applications(
    client: AsyncClient, session: AsyncSession,
) -> None:
    org = await _create_org(session, "qa")
    hr = await _create_user(session, "HR qa", "hrqa@test.com", "hr")
    await _add_membership(session, hr, org, "hr")
    token = await _login(client, hr.email)

    resp = await client.get(QUALITY, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    coverage = resp.json()["coverage"]
    assert coverage["total_applications"] == 0
    # "No data" must never be rendered as a 0% conversion rate.
    for key in ("screening_rate", "interview_rate", "decision_rate", "hire_rate"):
        assert coverage[key] is None, key


@pytest.mark.asyncio
async def test_quality_coverage_is_computed_from_real_statuses(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "qb")
    for index, status in enumerate(
        (ApplicationStatus.INTERVIEWED, ApplicationStatus.HIRED)
    ):
        await _apply(
            session, tenant["job"],
            await _another_candidate(session, f"qb{index}"), status=status,
        )
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(QUALITY, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    coverage = body["coverage"]
    assert coverage["total_applications"] == 3
    assert coverage["interview_rate"] == round(2 / 3, 4)
    assert coverage["hire_rate"] == round(1 / 3, 4)
    assert coverage["decision_rate"] == round(1 / 3, 4)
    assert body["fairness_gap_threshold"] == 0.8
    assert body["is_platform_scope"] is False


@pytest.mark.asyncio
async def test_quality_reports_no_fairness_verdict_without_screening_data(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "qc")
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(QUALITY, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    # Nothing was screened, so there is no ratio to judge; claiming a fair or a
    # biased organization here would be fabricating a compliance verdict.
    assert resp.json()["fairness_alerts"] == []


@pytest.mark.asyncio
async def test_quality_surfaces_a_real_fairness_gap_with_its_numbers(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """When real screening data produces a low parity ratio, say so.

    Only the "no data" branch was covered, which would also pass if the alert
    were never emitted at all. These scores are the shape the fairness engine
    reads: the >=60 cohort clears the 70 pass mark and the <60 cohort does not,
    so the selection-parity ratio is 0.0 -- genuinely below the 0.8 floor.
    """
    tenant = await _tenant(session, "qfair")
    for index, score in enumerate((80, 75, 20, 10)):
        candidate = await _another_candidate(session, f"qf{index}")
        session.add(
            ScreeningResult(
                job_id=tenant["job"].id,
                candidate_id=candidate.id,
                overall_match_score=score,
            ),
        )
    await session.commit()
    token = await _login(client, tenant["hr"].email)

    body = (await client.get(QUALITY, headers=_auth(token))).json()
    alerts = body["fairness_alerts"]
    assert len(alerts) == 1, body
    alert = alerts[0]
    assert alert["metric"] == "disparate_impact_ratio"
    assert alert["observed_value"] == 0.0
    assert alert["threshold_value"] == 0.8
    assert alert["detail"]
    # A fairness reading is a request for review, not a verdict on a person.
    assert "below" in alert["detail"].lower()


@pytest.mark.asyncio
async def test_quality_is_org_scoped(
    client: AsyncClient, session: AsyncSession,
) -> None:
    mine = await _tenant(session, "qd")
    await _tenant(session, "qe")
    token = await _login(client, mine["hr"].email)

    body = (await client.get(QUALITY, headers=_auth(token))).json()
    assert body["coverage"]["total_applications"] == 1


@pytest.mark.asyncio
async def test_reported_scope_comes_from_memberships_not_the_job_organization_column(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A job with no ``organization_id`` must not empty the reported scope.

    ``Job.organization_id`` is nullable and the production job-creation path
    never sets it, so deriving the *reported* scope from that column would make
    the screens say "your organizations" while listing none. The active
    membership is the authoritative source. The ``_tenant`` helper sets both,
    so this test clears the column to reproduce the real production shape.

    The HR user owns the job here, which is the documented way a job with no
    organization is reached (``authorized_job_ids`` matches on ``recruiter_id``).
    This test is about the reported scope *label*, not about who may read what.
    """
    tenant = await _tenant(session, "qnull")
    tenant["job"].organization_id = None
    tenant["job"].recruiter_id = tenant["hr"].id
    await session.commit()
    token = await _login(client, tenant["hr"].email)

    body = (await client.get(QUALITY, headers=_auth(token))).json()
    assert body["is_platform_scope"] is False
    assert body["organization_ids"] == [str(tenant["org"].id)]
    # The job is still authorized and counted -- only the label was at risk.
    assert body["coverage"]["total_applications"] == 1

    overview_body = (await client.get(OVERVIEW, headers=_auth(token))).json()
    assert overview_body["organization_ids"] == [str(tenant["org"].id)]


# ----------------------------------------------------------------------
# Per-stage drill-down for the clickable pipeline
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_applications_can_be_filtered_to_one_funnel_stage(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "ra2")
    await _apply(
        session, tenant["job"], await _another_candidate(session, "ra2"),
        status=ApplicationStatus.SHORTLISTED,
    )
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(
        f"{JOBS}/{tenant['job'].id}/applications?status=shortlisted",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status_filter"] == "shortlisted"
    assert [a["status"] for a in body["applications"]] == ["shortlisted"]
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_an_unknown_stage_filter_matches_nothing_rather_than_everything(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "rb2")
    token = await _login(client, tenant["hr"].email)

    resp = await client.get(
        f"{JOBS}/{tenant['job'].id}/applications?status=not_a_status",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # A stale link must never widen back to the whole job pipeline.
    assert body["applications"] == []
    assert body["total"] == 0
    assert body["status_filter"] == "not_a_status"


@pytest.mark.asyncio
async def test_a_stage_filter_cannot_bypass_the_job_access_check(
    client: AsyncClient, session: AsyncSession,
) -> None:
    mine = await _tenant(session, "rc2")
    theirs = await _tenant(session, "rd2")
    token = await _login(client, mine["hr"].email)

    resp = await client.get(
        f"{JOBS}/{theirs['job'].id}/applications?status=applied",
        headers=_auth(token),
    )
    assert resp.status_code in (403, 404), resp.text


# ----------------------------------------------------------------------
# Role gate shared by every new route
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_candidate_cannot_read_the_new_oversight_routes(
    client: AsyncClient, session: AsyncSession,
) -> None:
    tenant = await _tenant(session, "ra3")
    token = await _login(client, tenant["candidate"].email)
    for path in (
        RECRUITERS,
        f"{RECRUITERS}/{tenant['recruiter'].id}",
        ATTENTION,
        QUALITY,
    ):
        resp = await client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_an_anonymous_caller_cannot_read_the_new_oversight_routes(
    client: AsyncClient, session: AsyncSession,
) -> None:
    await _tenant(session, "rb3")
    for path in (RECRUITERS, ATTENTION, QUALITY):
        resp = await client.get(path)
        # Refused either way. The exact code is platform-wide ``require_role``
        # behaviour -- it declares a required Authorization header, so FastAPI
        # answers 422 rather than 401 -- and is not something this phase
        # changes; what matters is that no oversight data is returned.
        assert resp.status_code in (401, 422), f"{path} -> {resp.status_code}"
        assert "recruiters" not in resp.text
        assert "items" not in resp.text
