import uuid

import pytest
from httpx import AsyncClient

from app.domain.enums import (
    ApplicationStatus,
    HiringRecommendation,
    MembershipStatus,
    ScreeningStatus,
    StrengthLevel,
)
from app.domain.models import (
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    Role,
    ScreeningResult,
)
from app.repositories.user import UserRepository


async def _register_user(client: AsyncClient, session, full_name: str, email: str, role_name: str | None = None):
    response = await client.post(
        "/api/v1/auth/register",
        json={"full_name": full_name, "email": email, "password": "SecureP@ss123"},
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    if role_name:
        repository = UserRepository(session)
        role = await repository.find_role_by_name(role_name)
        if role is None:
            role = Role(name=role_name, description=role_name)
            session.add(role)
            await session.flush()
        await repository.assign_role(user_id, role.id)
        await session.commit()
        session.expire_all()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user_id


async def _create_job(client: AsyncClient, headers: dict[str, str], title: str) -> uuid.UUID:
    response = await client.post(
        "/api/v1/recruiter/jobs",
        json={
            "title": title,
            "company": "Applicant Test Co",
            "employment_type": "full_time",
            "location": "Remote",
            "description": "Applicant dashboard test",
            "required_skills": ["Python"],
            "status": "published",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_applicant_filters_summary_and_legacy_screening(client: AsyncClient, session):
    recruiter_headers, _ = await _register_user(
        client, session, "Recruiter Filter", "recruiter-filter@test.com", "hr",
    )
    _, first_candidate_id = await _register_user(
        client, session, "Alice Applicant", "alice-applicant@test.com",
    )
    _, second_candidate_id = await _register_user(
        client, session, "Bob Applicant", "bob-applicant@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Filtered Applicants")

    first_application = JobApplication(
        job_id=job_id,
        candidate_id=first_candidate_id,
        status=ApplicationStatus.UNDER_REVIEW,
        screening_status=ScreeningStatus.FAILED.value,
        screening_attempts=2,
    )
    second_application = JobApplication(
        job_id=job_id,
        candidate_id=second_candidate_id,
        status=ApplicationStatus.APPLIED,
        screening_status=ScreeningStatus.QUEUED.value,
    )
    session.add_all([first_application, second_application])
    await session.flush()
    session.add(
        ScreeningResult(
            job_id=job_id,
            candidate_id=first_candidate_id,
            overall_match_score=91,
            skill_match_score=90,
            experience_match_score=92,
            education_match_score=90,
            project_match_score=89,
            certification_match_score=88,
            location_match_score=95,
            employment_type_match_score=90,
            semantic_match_score=93,
            matched_skills=["Python"],
            missing_required_skills=[],
            missing_preferred_skills=[],
            strengths=["Python"],
            weaknesses=[],
            recommendation=HiringRecommendation.STRONGLY_RECOMMEND,
            strength_level=StrengthLevel.EXCELLENT,
        )
    )
    await session.flush()

    response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants",
        params={"q": "alice", "recommendation": "strongly_recommend", "min_score": 80, "sort_by": "score_high"},
        headers=recruiter_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["total_pages"] == 1
    assert body["summary"]["total_applicants"] == 2
    assert body["summary"]["total_screened"] == 1
    assert body["summary"]["queued"] == 1
    assert body["summary"]["failed"] == 0
    assert body["summary"]["average_score"] == 91
    assert body["summary"]["high_match_count"] == 1
    assert body["summary"]["recommendation_breakdown"] == {"strongly_recommend": 1}
    item = body["items"][0]
    assert item["candidate_name"] == "Alice Applicant"
    assert item["screening_status"] == "completed"
    assert item["score"] == 91
    assert item["overall_match_score"] == 91
    assert item["recommendation"] == "strongly_recommend"
    assert item["strength_level"] == "excellent"
    assert item["screening_attempts"] == 2
    assert item["screening_result"]["application_id"] is None

    page_response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants",
        params={"page": 1, "page_size": 1, "sort_by": "name_asc"},
        headers=recruiter_headers,
    )
    assert page_response.status_code == 200
    page_body = page_response.json()
    assert page_body["total"] == 2
    assert page_body["total_pages"] == 2
    assert len(page_body["items"]) == 1
    assert page_body["items"][0]["candidate_name"] == "Alice Applicant"

    summary_response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants/summary",
        headers=recruiter_headers,
    )
    assert summary_response.status_code == 200
    assert summary_response.json()["total_applicants"] == 2
    assert summary_response.json()["status_breakdown"] == {"under_review": 1, "applied": 1}

    invalid_response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants",
        params={"sort_by": "unsupported"},
        headers=recruiter_headers,
    )
    assert invalid_response.status_code == 422


@pytest.mark.asyncio
async def test_applicant_access_requires_active_organization_membership(client: AsyncClient, session):
    owner_headers, _ = await _register_user(
        client, session, "Owner Active", "owner-active@test.com", "hr",
    )
    job_id = await _create_job(client, owner_headers, "Organization Applicants")
    organization = Organization(
        name="Applicant Test Organization",
        slug=f"applicant-org-{uuid.uuid4().hex}",
    )
    session.add(organization)
    await session.flush()
    organization_id = organization.id
    job = await session.get(Job, job_id)
    job.organization_id = organization_id

    active_headers, active_id = await _register_user(
        client, session, "Active Staff", "active-staff@test.com", "recruiter",
    )
    inactive_headers, inactive_id = await _register_user(
        client, session, "Inactive Staff", "inactive-staff@test.com", "recruiter",
    )
    session.add_all(
        [
            OrganizationMembership(
                user_id=active_id,
                organization_id=organization_id,
                role="recruiter",
                status=MembershipStatus.ACTIVE.value,
            ),
            OrganizationMembership(
                user_id=inactive_id,
                organization_id=organization_id,
                role="recruiter",
                status=MembershipStatus.SUSPENDED.value,
            ),
        ]
    )
    await session.flush()

    active_response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants",
        headers=active_headers,
    )
    assert active_response.status_code == 200

    inactive_response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants",
        headers=inactive_headers,
    )
    assert inactive_response.status_code == 403


@pytest.mark.asyncio
async def test_summary_screening_breakdown_counts_each_application_once(client: AsyncClient, session):
    recruiter_headers, _ = await _register_user(
        client, session, "Recruiter Breakdown", "recruiter-breakdown@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Completed Applicant", "completed-applicant@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Breakdown Applicants")

    session.add(
        JobApplication(
            job_id=job_id,
            candidate_id=candidate_id,
            status=ApplicationStatus.APPLIED,
            screening_status=ScreeningStatus.COMPLETED.value,
        )
    )
    await session.flush()

    response = await client.get(
        f"/api/v1/recruiter/jobs/{job_id}/applicants/summary",
        headers=recruiter_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_applicants"] == 1
    assert body["screening_status_breakdown"]["completed"] == 1
    assert sum(body["screening_status_breakdown"].values()) == body["total_applicants"]


@pytest.mark.asyncio
async def test_recruiter_notes_follow_job_access_and_application_scope(client: AsyncClient, session):
    owner_headers, _ = await _register_user(
        client, session, "Owner Notes", "owner-notes@test.com", "hr",
    )
    job_id = await _create_job(client, owner_headers, "Note Applicants")
    organization = Organization(
        name="Note Test Organization",
        slug=f"note-org-{uuid.uuid4().hex}",
    )
    session.add(organization)
    await session.flush()
    job = await session.get(Job, job_id)
    job.organization_id = organization.id
    organization_id = organization.id

    active_headers, active_id = await _register_user(
        client, session, "Active Note Staff", "active-note-staff@test.com", "recruiter",
    )
    inactive_headers, inactive_id = await _register_user(
        client, session, "Inactive Note Staff", "inactive-note-staff@test.com", "recruiter",
    )
    session.add_all(
        [
            OrganizationMembership(
                user_id=active_id,
                organization_id=organization_id,
                role="recruiter",
                status=MembershipStatus.ACTIVE.value,
            ),
            OrganizationMembership(
                user_id=inactive_id,
                organization_id=organization_id,
                role="recruiter",
                status=MembershipStatus.SUSPENDED.value,
            ),
        ]
    )
    _, first_candidate_id = await _register_user(
        client, session, "Note Applicant One", "note-applicant-one@test.com",
    )
    _, second_candidate_id = await _register_user(
        client, session, "Note Applicant Two", "note-applicant-two@test.com",
    )
    first_application = JobApplication(
        job_id=job_id,
        candidate_id=first_candidate_id,
        status=ApplicationStatus.APPLIED,
    )
    second_application = JobApplication(
        job_id=job_id,
        candidate_id=second_candidate_id,
        status=ApplicationStatus.APPLIED,
    )
    session.add_all([first_application, second_application])
    await session.flush()
    first_application_id = first_application.id
    second_application_id = second_application.id

    created = await client.post(
        f"/api/v1/recruiter/jobs/applications/{first_application_id}/notes",
        json={"note": "Reviewed portfolio"},
        headers=active_headers,
    )
    assert created.status_code == 201
    note_id = uuid.UUID(created.json()["id"])

    forbidden = await client.post(
        f"/api/v1/recruiter/jobs/applications/{first_application_id}/notes",
        json={"note": "Suspended staff note"},
        headers=inactive_headers,
    )
    assert forbidden.status_code == 403

    cross_application = await client.put(
        f"/api/v1/recruiter/jobs/applications/{second_application_id}/notes/{note_id}",
        json={"note": "Rewritten against another application"},
        headers=active_headers,
    )
    assert cross_application.status_code == 404

    updated = await client.put(
        f"/api/v1/recruiter/jobs/applications/{first_application_id}/notes/{note_id}",
        json={"note": "Reviewed portfolio thoroughly"},
        headers=active_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["note"] == "Reviewed portfolio thoroughly"

    deleted = await client.delete(
        f"/api/v1/recruiter/jobs/applications/{first_application_id}/notes/{note_id}",
        headers=active_headers,
    )
    assert deleted.status_code == 200
