"""Phase 7: Fairness & Bias Intelligence in the screening workflow.

The assertions are deliberately about *honesty of reporting* and *containment*,
not just happy-path values:

* Group metrics are checked against hand-computed rates, and every
  insufficient-data case must degrade to a stated status rather than a
  convenient number.
* Protected attributes are never inferred, and an analysis with no demographic
  coverage must say so instead of implying parity.
* Authorization is verified on the new endpoint *and* on the pre-existing
  unscoped ``/fairness/*`` routes, which are the real cross-tenant risk.
* The candidate-facing surface must be provably free of fairness data.
* Fetching fairness must not mutate a single field, and must not start an
  adversarial run.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.domain.enums import (
    ApplicationStatus,
    EmploymentType,
    HiringRecommendation,
    JobStatus,
    MembershipStatus,
    ScreeningStatus,
    StrengthLevel,
)
from app.domain.models import (
    AuditLog,
    CandidateProfile,
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    Role,
    ScreeningResult,
    User,
    UserRole,
)
from app.services.fairness.fairness_engine import POSITIVE_OUTCOME_THRESHOLD

FAIRNESS_PATH = "/api/v1/recruiter/jobs/applications/{application_id}/fairness-context"
CANDIDATE_EXPLANATION_PATH = (
    "/api/v1/candidate/jobs/applications/{application_id}/explanation"
)
PASSWORD = "SecureP@ss123"


# ── Builders ───────────────────────────────────────────────────────


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _recruiter(session, make_user, email: str) -> User:
    user, _ = await make_user("Recruiter", email, PASSWORD, "recruiter")
    return user


async def _organization(session, owner: User, name: str) -> Organization:
    organization = Organization(name=name, slug=uuid.uuid4().hex[:12])
    session.add(organization)
    await session.flush()
    session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=owner.id,
            role="recruiter",
            status=MembershipStatus.ACTIVE.value,
        )
    )
    await session.commit()
    return organization


async def _job(
    session, recruiter: User, organization: Organization, title: str,
    description: str = "Backend engineer role.",
) -> Job:
    job = Job(
        organization_id=organization.id,
        recruiter_id=recruiter.id,
        title=title,
        company="Northwind",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
        description=description,
        required_skills=["Python"],
        status=JobStatus.PUBLISHED,
    )
    session.add(job)
    await session.commit()
    return job


async def _screened_candidate(
    session, job: Job, gender: str | None, score: int, index: int,
) -> JobApplication:
    """A candidate with a self-reported gender, an application and a screening.

    ``gender=None`` means the candidate supplied nothing, which must be
    reported as missing coverage rather than inferred into a group.
    """
    user = User(
        id=uuid.uuid4(),
        full_name=f"Candidate {index}",
        email=f"cand{index}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password(PASSWORD),
    )
    session.add(user)
    await session.flush()
    session.add(
        CandidateProfile(user_id=user.id, current_role="Engineer", gender=gender)
    )
    # Grant the candidate role so the candidate-facing safety tests can
    # authenticate as the person whose data is being read.
    role = (
        await session.execute(select(Role).where(Role.name == "candidate"))
    ).scalar_one_or_none()
    if role is not None:
        session.add(UserRole(user_id=user.id, role_id=role.id))
    application = JobApplication(
        job_id=job.id,
        candidate_id=user.id,
        status=ApplicationStatus.UNDER_REVIEW,
        screening_status=ScreeningStatus.COMPLETED,
    )
    session.add(application)
    await session.flush()
    session.add(
        ScreeningResult(
            job_id=job.id,
            candidate_id=user.id,
            application_id=application.id,
            overall_match_score=score,
            skill_match_score=score,
            recommendation=HiringRecommendation.RECOMMEND,
            strength_level=StrengthLevel.GOOD,
        )
    )
    await session.commit()
    return application


async def _context(client: AsyncClient, headers, application_id, **params):
    return await client.get(
        FAIRNESS_PATH.format(application_id=application_id),
        headers=headers,
        params=params or None,
    )


def _metric(analysis: dict, name: str) -> dict:
    for metric in analysis["cross_group_metrics"]:
        if metric["metric_name"] == name:
            return metric
    raise AssertionError(f"metric {name} not present")


def _group(analysis: dict, value: str) -> dict:
    for entry in analysis["group_outcomes"]:
        if entry["group_value"] == value:
            return entry
    raise AssertionError(f"group {value} not present")


# ── Group metric correctness ───────────────────────────────────────


@pytest.mark.asyncio
async def test_group_metrics_match_hand_computed_rates(
    client: AsyncClient, session, _create_user_with_role,
):
    """SPD and DI come from real self-reported group rates."""
    recruiter = await _recruiter(session, _create_user_with_role, "r1@example.com")
    organization = await _organization(session, recruiter, "Org One")
    job = await _job(session, recruiter, organization, "Fairness Role")

    # 8 male candidates all above the positive-outcome threshold, 6 female with
    # 3 above it: rates 1.0 and 0.5, so SPD 0.5 and DI 0.5.
    for i in range(7):
        await _screened_candidate(session, job, "male", 90, i)
    for i in range(6):
        await _screened_candidate(
            session, job, "female", 80 if i < 3 else 40, 100 + i,
        )
    subject = await _screened_candidate(session, job, "male", 95, 999)

    headers = await _login(client, "r1@example.com")
    response = await _context(client, headers, subject.id)
    assert response.status_code == 200, response.text
    analysis = response.json()["group_analysis"]

    assert analysis["metric_status"] == "available"
    assert analysis["reference_group"] == "male"
    assert _group(analysis, "male")["sample_size"] == 8
    assert _group(analysis, "male")["positive_outcome_rate"] == 1.0
    assert _group(analysis, "female")["sample_size"] == 6
    assert _group(analysis, "female")["positive_outcome_rate"] == 0.5

    spd = _metric(analysis, "statistical_parity_difference")
    di = _metric(analysis, "disparate_impact_ratio")
    assert spd["value"] == pytest.approx(0.5)
    assert spd["reference_group"] == "male"
    assert sorted(spd["groups_compared"]) == ["female", "male"]
    assert di["value"] == pytest.approx(0.5)
    assert di["status_reason"] is None


@pytest.mark.asyncio
async def test_no_group_is_inferred_when_gender_is_missing(
    client: AsyncClient, session, _create_user_with_role,
):
    """A candidate with no gender is missing coverage, never an assigned group."""
    recruiter = await _recruiter(session, _create_user_with_role, "r2@example.com")
    organization = await _organization(session, recruiter, "Org Two")
    job = await _job(session, recruiter, organization, "No Inference Role")

    subject = await _screened_candidate(session, job, None, 90, 0)
    for i in range(5):
        await _screened_candidate(session, job, None, 90, 10 + i)

    headers = await _login(client, "r2@example.com")
    analysis = (await _context(client, headers, subject.id)).json()["group_analysis"]

    assert analysis["metric_status"] == "no_demographic_data"
    assert analysis["reference_group"] is None
    # The metrics are present but explicitly unvalued, so a consumer cannot
    # mistake their absence for parity.
    assert analysis["cross_group_metrics"], "metrics should be reported as unavailable"
    for metric in analysis["cross_group_metrics"]:
        assert metric["value"] is None
        assert metric["metric_status"] == "no_reference_group"
    unknown = _group(analysis, "unknown")
    assert unknown["metric_status"] == "no_demographic_data"
    assert unknown["positive_outcome_rate"] is None

    coverage = analysis["coverage"]
    assert coverage["attributes_inferred"] is False
    assert coverage["candidates_missing_demographic"] == 6
    assert coverage["demographic_coverage_pct"] == 0.0


@pytest.mark.asyncio
async def test_group_below_minimum_size_reports_insufficient(
    client: AsyncClient, session, _create_user_with_role,
):
    """A small group yields a stated status, not a rate."""
    recruiter = await _recruiter(session, _create_user_with_role, "r3@example.com")
    organization = await _organization(session, recruiter, "Org Three")
    job = await _job(session, recruiter, organization, "Small Group Role")

    subject = await _screened_candidate(session, job, "male", 90, 0)
    for i in range(5):
        await _screened_candidate(session, job, "male", 90, 10 + i)
    for i in range(2):
        await _screened_candidate(session, job, "female", 30, 30 + i)

    headers = await _login(client, "r3@example.com")
    analysis = (await _context(client, headers, subject.id)).json()["group_analysis"]

    assert analysis["metric_status"] == "insufficient_data"
    female = _group(analysis, "female")
    assert female["sample_size"] == 2
    assert female["metric_status"] == "insufficient_sample"
    assert female["positive_outcome_rate"] is None
    assert "below" in female["status_reason"]
    # No value is invented for a cross-group comparison that cannot be made.
    assert all(m["value"] is None for m in analysis["cross_group_metrics"])


@pytest.mark.asyncio
async def test_minimum_group_size_is_configurable_and_respected(
    client: AsyncClient, session, _create_user_with_role,
):
    """Lowering the minimum must actually admit the group, not just relabel it."""
    recruiter = await _recruiter(session, _create_user_with_role, "r4@example.com")
    organization = await _organization(session, recruiter, "Org Four")
    job = await _job(session, recruiter, organization, "Tunable Role")

    subject = await _screened_candidate(session, job, "male", 90, 0)
    for i in range(4):
        await _screened_candidate(session, job, "male", 90, 10 + i)
    for i in range(2):
        await _screened_candidate(session, job, "female", 30, 30 + i)

    headers = await _login(client, "r4@example.com")
    strict = (await _context(client, headers, subject.id)).json()
    assert strict["group_analysis"]["metric_status"] == "insufficient_data"

    relaxed = (
        await _context(client, headers, subject.id, minimum_group_size=2)
    ).json()
    assert relaxed["group_analysis"]["metric_status"] == "available"
    spd = _metric(relaxed["group_analysis"], "statistical_parity_difference")
    assert spd["value"] == 1.0
    assert relaxed["group_analysis"]["coverage"]["minimum_group_size"] == 2


@pytest.mark.asyncio
async def test_unscreened_job_reports_no_screening_data(
    client: AsyncClient, session, _create_user_with_role,
):
    """An unscreened application returns a complete payload, not a 500."""
    recruiter = await _recruiter(session, _create_user_with_role, "r5@example.com")
    organization = await _organization(session, recruiter, "Org Five")
    job = await _job(session, recruiter, organization, "UnScreened Role")

    candidate = User(
        id=uuid.uuid4(),
        full_name="Pending",
        email=f"pending-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password(PASSWORD),
    )
    session.add(candidate)
    await session.flush()
    application = JobApplication(
        job_id=job.id,
        candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED,
        screening_status=ScreeningStatus.QUEUED,
    )
    session.add(application)
    await session.commit()

    headers = await _login(client, "r5@example.com")
    response = await _context(client, headers, application.id)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["screening_state"]["screened"] is False
    assert body["screening_state"]["effective_status"] == ScreeningStatus.QUEUED.value
    assert body["population"]["application_screening_included"] is False
    assert body["population"]["screened"] == 0
    assert body["group_analysis"]["metric_status"] == "no_screening_data"
    assert all(
        m["value"] is None for m in body["group_analysis"]["cross_group_metrics"]
    )
    assert body["score_distribution"] is None
    assert any("no screening results" in item for item in body["limitations"])


@pytest.mark.asyncio
async def test_unrecognised_gender_value_is_not_treated_as_a_group(
    client: AsyncClient, session, _create_user_with_role,
):
    """An out-of-vocabulary gender must not become its own comparison group."""
    recruiter = await _recruiter(session, _create_user_with_role, "r6@example.com")
    organization = await _organization(session, recruiter, "Org Six")
    job = await _job(session, recruiter, organization, "Vocabulary Role")

    subject = await _screened_candidate(session, job, "male", 90, 0)
    for i in range(4):
        await _screened_candidate(session, job, "male", 90, 10 + i)
    for i in range(6):
        await _screened_candidate(session, job, "not-a-gender", 10, 30 + i)

    headers = await _login(client, "r6@example.com")
    analysis = (await _context(client, headers, subject.id)).json()["group_analysis"]

    values = {g["group_value"] for g in analysis["group_outcomes"]}
    assert "not-a-gender" not in values
    assert "unknown" in values
    assert analysis["metric_status"] == "insufficient_data"


# ── Response contract ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fairness_is_population_scoped_and_never_merged_with_score(
    client: AsyncClient, session, _create_user_with_role,
):
    """No per-candidate fairness score, and methodology ships with the metrics."""
    recruiter = await _recruiter(session, _create_user_with_role, "r7@example.com")
    organization = await _organization(session, recruiter, "Org Seven")
    job = await _job(session, recruiter, organization, "Contract Role")
    subject = await _screened_candidate(session, job, "male", 91, 0)
    for i in range(5):
        await _screened_candidate(session, job, "male", 91, 10 + i)
    for i in range(5):
        await _screened_candidate(session, job, "female", 30, 30 + i)

    headers = await _login(client, "r7@example.com")
    body = (await _context(client, headers, subject.id)).json()

    serialized = repr(body).lower()
    for forbidden in (
        "fairness_score", "composite_fairness_score", "candidate_fairness_score",
        "fairness_adjustment", "adjusted_score",
    ):
        assert forbidden not in serialized, forbidden

    assert body["population"]["application_screening_included"] is True
    assert "not a property of the individual" in body["population"]["note"]
    assert body["group_analysis"]["methodology"]
    assert body["group_analysis"]["grouping_note"]
    assert body["disclaimer"]
    assert (
        body["score_distribution"]["positive_outcome_threshold"]
        == POSITIVE_OUTCOME_THRESHOLD
    )
    assert "not a comparison between candidate groups" in body["score_distribution"]["note"]


@pytest.mark.asyncio
async def test_job_description_bias_is_reported_from_real_job_text(
    client: AsyncClient, session, _create_user_with_role,
):
    recruiter = await _recruiter(session, _create_user_with_role, "r8@example.com")
    organization = await _organization(session, recruiter, "Org Eight")
    job = await _job(
        session, recruiter, organization, "Aggressive Sales Ninja",
        description="We want a young, aggressive salesman. He must be a rockstar ninja.",
    )
    subject = await _screened_candidate(session, job, "male", 70, 0)

    headers = await _login(client, "r8@example.com")
    body = (await _context(client, headers, subject.id)).json()

    jd = body["job_description_bias"]
    assert jd is not None
    assert jd["job_id"] == str(job.id)
    assert jd["total_issues"] >= 1
    assert sum(jd["issue_counts"].values()) == jd["total_issues"]
    # It describes the posting, not the candidate.
    assert "every applicant" in jd["note"]
    assert body["sections"]["job_description_bias"]["status"] == "available"


@pytest.mark.asyncio
async def test_adversarial_is_never_executed_by_viewing_a_screening(
    client: AsyncClient, session, _create_user_with_role, monkeypatch,
):
    """Opening a screening must not launch a perturbation run."""
    from app.services.fairness import fairness_engine as engine_module

    def _fail(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("adversarial test executed during a fairness read")

    monkeypatch.setattr(
        engine_module.FairnessEngine, "run_adversarial_test", _fail,
    )

    recruiter = await _recruiter(session, _create_user_with_role, "r9@example.com")
    organization = await _organization(session, recruiter, "Org Nine")
    job = await _job(session, recruiter, organization, "Adversarial Role")
    subject = await _screened_candidate(session, job, "male", 75, 0)

    headers = await _login(client, "r9@example.com")
    body = (await _context(client, headers, subject.id)).json()

    adversarial = body["adversarial"]
    assert adversarial["tested"] is False
    assert adversarial["stability_score"] is None
    assert adversarial["status"] == "no_stored_result"
    assert adversarial["reason"]
    assert adversarial["run_on_demand_endpoint"]
    assert body["sections"]["adversarial"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_limitations_reflect_the_observed_population(
    client: AsyncClient, session, _create_user_with_role,
):
    """Limitations describe this response, not generic boilerplate."""
    recruiter = await _recruiter(session, _create_user_with_role, "r10@example.com")
    organization = await _organization(session, recruiter, "Org Ten")
    job = await _job(session, recruiter, organization, "Limitation Role")
    subject = await _screened_candidate(session, job, None, 80, 0)
    for i in range(3):
        await _screened_candidate(session, job, None, 80, 10 + i)

    headers = await _login(client, "r10@example.com")
    body = (await _context(client, headers, subject.id)).json()

    joined = " ".join(body["limitations"])
    assert "have not supplied a self-reported gender" in joined
    assert "Fewer than two demographic groups" in joined
    assert "No hiring decision" in joined


# ── Security ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recruiter_cannot_read_fairness_context_across_organizations(
    client: AsyncClient, session, _create_user_with_role,
):
    """A recruiter is scoped to their own organization."""
    owner = await _recruiter(session, _create_user_with_role, "ownera@example.com")
    intruder = await _recruiter(session, _create_user_with_role, "intruder@example.com")
    organization = await _organization(session, owner, "Tenant A")
    job = await _job(session, owner, organization, "Tenant A Role")
    application = await _screened_candidate(session, job, "male", 80, 0)

    headers = await _login(client, "intruder@example.com")
    response = await _context(client, headers, application.id)
    assert response.status_code in (403, 404)
    assert "tenant a role" not in response.text.lower()


@pytest.mark.asyncio
async def test_candidate_cannot_read_fairness_context(
    client: AsyncClient, session, _create_user_with_role,
):
    """The fairness context endpoint is recruiter/HR only."""
    recruiter = await _recruiter(session, _create_user_with_role, "r11@example.com")
    organization = await _organization(session, recruiter, "Org Eleven")
    job = await _job(session, recruiter, organization, "Candidate Probe")
    application = await _screened_candidate(session, job, "male", 80, 0)

    candidate = await session.get(User, application.candidate_id)
    headers = await _login(client, candidate.email)
    response = await _context(client, headers, application.id)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_legacy_fairness_routes_are_scoped(
    client: AsyncClient, session, _create_user_with_role,
):
    """The pre-existing /fairness/* routes must not leak across tenants.

    This is the pre-existing cross-tenant surface Phase 7 was asked to fix, so it
    is asserted explicitly rather than assumed.
    """
    owner = await _recruiter(session, _create_user_with_role, "ownerb@example.com")
    outsider = await _recruiter(session, _create_user_with_role, "outsider@example.com")
    organization = await _organization(session, owner, "Tenant B")
    job = await _job(session, owner, organization, "Tenant B Confidential")
    application = await _screened_candidate(session, job, "male", 80, 0)

    headers = await _login(client, "outsider@example.com")
    job_id = str(job.id)
    candidate_id = str(application.candidate_id)

    attempts = [
        ("get", "/api/v1/fairness/report/{job_id}", f"/api/v1/fairness/report/{job_id}", None),
        (
            "get", "/api/v1/fairness/bias-detection/{job_id}",
            f"/api/v1/fairness/bias-detection/{job_id}", None,
        ),
        (
            "get", "/api/v1/fairness/jd-analysis/{job_id}",
            f"/api/v1/fairness/jd-analysis/{job_id}", None,
        ),
        (
            "post", "/api/v1/fairness/analyze", "/api/v1/fairness/analyze",
            {"job_id": job_id},
        ),
        (
            "post", "/api/v1/fairness/adversarial-test",
            "/api/v1/fairness/adversarial-test",
            {"job_id": job_id, "candidate_id": candidate_id},
        ),
        (
            "get", "/api/v1/fairness/candidate/{candidate_id}",
            f"/api/v1/fairness/candidate/{candidate_id}", None,
        ),
    ]
    for method, path, url, params in attempts:
        response = await client.request(method, url, headers=headers, params=params)
        assert response.status_code in (403, 404), f"{method.upper()} {path} -> {response.status_code}"
        assert "confidential" not in response.text.lower(), path


@pytest.mark.asyncio
async def test_legacy_platform_wide_routes_return_empty_for_a_user_with_no_jobs(
    client: AsyncClient, session, _create_user_with_role,
):
    """A recruiter with no accessible jobs sees nothing, not the whole platform."""
    owner = await _recruiter(session, _create_user_with_role, "ownerc@example.com")
    loner = await _recruiter(session, _create_user_with_role, "loner@example.com")
    organization = await _organization(session, owner, "Tenant C")
    job = await _job(session, owner, organization, "Tenant C Hidden")
    for i in range(6):
        await _screened_candidate(
            session, job, "male" if i < 3 else "female", 80, i,
        )

    headers = await _login(client, "loner@example.com")

    overview = await client.get("/api/v1/fairness/overview", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["total_jobs"] == 0
    assert overview.json()["total_screened"] == 0
    assert overview.json()["total_candidates"] == 0
    assert overview.json()["bias_alerts"] == []

    metrics = await client.get("/api/v1/fairness/metrics", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["data_points"] == 0

    alerts = await client.get("/api/v1/fairness/bias-alerts", headers=headers)
    assert alerts.status_code == 200
    assert alerts.json() == []


# ── Read-only guarantees ───────────────────────────────────────────


def _enum_value(value) -> str:
    """Enum columns may come back as the enum or its raw string."""
    return getattr(value, "value", value)


@pytest.mark.asyncio
async def test_viewing_fairness_changes_nothing(
    client: AsyncClient, session, _create_user_with_role,
):
    """Scores, recommendation, strength, status and screening state are untouched."""
    recruiter = await _recruiter(session, _create_user_with_role, "r12@example.com")
    organization = await _organization(session, recruiter, "Org Twelve")
    job = await _job(session, recruiter, organization, "Immutable Role")
    subject = await _screened_candidate(session, job, "male", 84, 0)
    for i in range(5):
        await _screened_candidate(session, job, "male", 84, 10 + i)
    for i in range(5):
        await _screened_candidate(session, job, "female", 20, 30 + i)

    screening = await session.execute(
        select(ScreeningResult).where(ScreeningResult.application_id == subject.id)
    )
    screening_id = screening.scalar_one().id
    before = await session.get(ScreeningResult, screening_id)
    before_values = {
        "score": before.overall_match_score,
        "recommendation": _enum_value(before.recommendation),
        "strength_level": _enum_value(before.strength_level),
        "application_status": _enum_value(subject.status),
        "screening_status": _enum_value(subject.screening_status),
    }

    headers = await _login(client, "r12@example.com")
    assert (await _context(client, headers, subject.id)).status_code == 200

    await session.refresh(subject)
    after = await session.get(ScreeningResult, screening_id)
    assert after.overall_match_score == before_values["score"]
    assert _enum_value(after.recommendation) == before_values["recommendation"]
    assert _enum_value(after.strength_level) == before_values["strength_level"]
    assert _enum_value(subject.status) == before_values["application_status"]
    assert _enum_value(subject.screening_status) == before_values["screening_status"]


@pytest.mark.asyncio
async def test_audit_records_the_view_without_protected_attributes(
    client: AsyncClient, session, _create_user_with_role,
):
    """The audit trail must not become a second copy of the fairness data."""
    recruiter = await _recruiter(session, _create_user_with_role, "r13@example.com")
    organization = await _organization(session, recruiter, "Org Thirteen")
    job = await _job(session, recruiter, organization, "Audited Role")
    subject = await _screened_candidate(session, job, "male", 80, 0)
    for i in range(5):
        await _screened_candidate(session, job, "female", 20, 10 + i)

    headers = await _login(client, "r13@example.com")
    assert (await _context(client, headers, subject.id)).status_code == 200

    entries = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.action == "application_fairness_context_viewed",
            )
        )
    ).scalars().all()
    assert entries, "expected a fairness context audit entry"
    details = str(entries[-1].details).lower()
    for leaked in ("male", "female", "gender", "positive_outcome_rate"):
        assert leaked not in details, f"{leaked} leaked into audit details"
    assert "group_analysis_status" in details


# ── Candidate safety ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_explanation_contains_no_fairness_data(
    client: AsyncClient, session, _create_user_with_role,
):
    """The Phase 6 candidate surface stays free of Phase 7 fairness content."""
    recruiter = await _recruiter(session, _create_user_with_role, "r14@example.com")
    organization = await _organization(session, recruiter, "Org Fourteen")
    job = await _job(session, recruiter, organization, "Safety Role")
    subject = await _screened_candidate(session, job, "male", 80, 0)
    for i in range(5):
        await _screened_candidate(session, job, "female", 20, 10 + i)

    candidate = await session.get(User, subject.candidate_id)
    headers = await _login(client, candidate.email)
    response = await client.get(
        CANDIDATE_EXPLANATION_PATH.format(application_id=subject.id),
        headers=headers,
    )
    assert response.status_code == 200, response.text

    payload = response.json()

    # Structural check: no fairness-related key may exist anywhere in the tree.
    # This is the check that actually matters -- a value hidden under an
    # innocuous key would still be caught, and a job title containing the word
    # "fairness" cannot produce a false pass.
    forbidden_keys = {
        "fairness", "fairness_score", "group_fairness", "bias", "bias_alerts",
        "statistical_parity_difference", "disparate_impact_ratio",
        "equal_opportunity_difference", "group_outcomes", "group_metrics",
        "cross_group_metrics", "coverage", "demographic", "demographic_coverage_pct",
        "adversarial", "protected_attributes", "protected_attribute", "gender",
        "gendered_language", "minimum_group_size", "reference_group",
        "application_fairness_context", "fairness_context", "spd", "di",
    }

    def _keys(node) -> set[str]:
        if isinstance(node, dict):
            found = {str(k).lower() for k in node}
            for value in node.values():
                found |= _keys(value)
            return found
        if isinstance(node, list):
            found: set[str] = set()
            for item in node:
                found |= _keys(item)
            return found
        return set()

    leaked = _keys(payload) & forbidden_keys
    assert not leaked, f"fairness keys leaked to candidate: {sorted(leaked)}"

    # And no fairness *values* in the serialized text either.
    text = response.text.lower()
    for token in (
        "statistical parity", "disparate impact", "group fairness",
        "protected attribute", "demographic coverage", "adversarial",
        "bias alert", "self-reported gender",
    ):
        assert token not in text, token
