"""Phase 7 regression guard for the pre-existing /fairness/* routes.

Blocking an unauthorized caller is only half the job. These tests assert the
other half: an authorized owner must still get working data, and the candidate
self-service view must still span every job the candidate applied to.
"""

import pytest
from sqlalchemy import select

from app.domain.enums import HiringRecommendation, StrengthLevel
from app.domain.models import JobApplication, ScreeningResult, User
from tests.test_fairness_context import (
    _job,
    _login,
    _organization,
    _recruiter,
    _screened_candidate,
)


@pytest.mark.asyncio
async def test_owner_can_still_read_every_legacy_route(
    client, session, _create_user_with_role,
):
    owner = await _recruiter(session, _create_user_with_role, "owner@example.com")
    organization = await _organization(session, owner, "Legacy Org")
    job = await _job(session, owner, organization, "Legacy Role")
    subject = await _screened_candidate(session, job, "male", 80, 0)
    # Two groups that both clear the default minimum of five, so the additive
    # group_fairness block is genuinely reportable rather than "insufficient".
    for i in range(4):
        await _screened_candidate(session, job, "male", 80, 10 + i)
    for i in range(5):
        await _screened_candidate(session, job, "female", 30, 30 + i)

    headers = await _login(client, "owner@example.com")
    job_id = str(job.id)
    candidate_id = str(subject.candidate_id)

    report = await client.get(f"/api/v1/fairness/report/{job_id}", headers=headers)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["total_candidates"] == 10
    # The additive group_fairness block is present on the legacy endpoint too.
    assert body["group_fairness"]["metric_status"] == "available"
    assert body["group_fairness"]["coverage"]["attributes_inferred"] is False

    bias = await client.get(
        f"/api/v1/fairness/bias-detection/{job_id}", headers=headers,
    )
    assert bias.status_code == 200, bias.text
    assert bias.json()["job_id"] == job_id

    jd = await client.get(f"/api/v1/fairness/jd-analysis/{job_id}", headers=headers)
    assert jd.status_code == 200, jd.text

    scoped = await client.post(
        "/api/v1/fairness/analyze", headers=headers, params={"job_id": job_id},
    )
    assert scoped.status_code == 200, scoped.text

    unscoped = await client.post("/api/v1/fairness/analyze", headers=headers)
    assert unscoped.status_code == 200, unscoped.text
    assert unscoped.json()["total_jobs"] == 1

    candidate_view = await client.get(
        f"/api/v1/fairness/candidate/{candidate_id}", headers=headers,
    )
    assert candidate_view.status_code == 200, candidate_view.text
    assert candidate_view.json()["total_evaluations"] == 1

    for path in (
        "/api/v1/fairness/overview",
        "/api/v1/fairness/metrics",
        "/api/v1/fairness/bias-alerts",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, f"{path}: {response.text}"

    overview = (await client.get("/api/v1/fairness/overview", headers=headers)).json()
    assert overview["total_jobs"] == 1
    assert overview["total_screened"] == 10


@pytest.mark.asyncio
async def test_candidate_self_view_is_not_narrowed_by_organization_scope(
    client, session, _create_user_with_role,
):
    """``/my-fairness`` must still cover every job the candidate applied to."""
    owner = await _recruiter(session, _create_user_with_role, "o2@example.com")
    organization = await _organization(session, owner, "Self Org")
    job_a = await _job(session, owner, organization, "Self Role A")
    job_b = await _job(session, owner, organization, "Self Role B")

    first = await _screened_candidate(session, job_a, "male", 80, 0)
    candidate_id = first.candidate_id

    second = JobApplication(job_id=job_b.id, candidate_id=candidate_id)
    session.add(second)
    await session.flush()
    session.add(
        ScreeningResult(
            job_id=job_b.id,
            candidate_id=candidate_id,
            application_id=second.id,
            overall_match_score=60,
            recommendation=HiringRecommendation.CONSIDER,
            strength_level=StrengthLevel.AVERAGE,
        )
    )
    await session.commit()

    candidate = await session.get(User, candidate_id)
    headers = await _login(client, candidate.email)
    response = await client.get("/api/v1/fairness/my-fairness", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total_evaluations"] == 2
