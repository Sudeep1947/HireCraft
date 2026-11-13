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
    CandidateProfile,
    Job,
    JobApplication,
    Organization,
    OrganizationMembership,
    ParsedResumeData,
    Resume,
    Role,
    ScreeningResult,
)
from app.repositories.user import UserRepository

DETAIL_PATH = "/api/v1/recruiter/jobs/applications/{application_id}/screening-detail"


async def _register_user(
    client: AsyncClient,
    session,
    full_name: str,
    email: str,
    role_name: str | None = None,
):
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
            "company": "Screening Detail Co",
            "employment_type": "full_time",
            "location": "Remote",
            "description": "Screening detail test",
            "required_skills": ["Python"],
            "preferred_skills": ["Docker"],
            "status": "published",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def _screening_result(
    job_id, candidate_id, application_id, overall: int, resume_id=None,
) -> ScreeningResult:
    return ScreeningResult(
        job_id=job_id,
        candidate_id=candidate_id,
        application_id=application_id,
        resume_id=resume_id,
        overall_match_score=overall,
        skill_match_score=92,
        experience_match_score=84,
        education_match_score=90,
        project_match_score=81,
        certification_match_score=70,
        location_match_score=100,
        employment_type_match_score=95,
        semantic_match_score=88,
        matched_skills=["Python", "FastAPI"],
        missing_required_skills=["Kubernetes"],
        missing_preferred_skills=["Terraform"],
        strengths=["Strong backend Python"],
        weaknesses=["No Kubernetes evidence"],
        recommendation=HiringRecommendation.RECOMMEND,
        strength_level=StrengthLevel.GOOD,
    )


def _skill(name: str, category: str = "Other") -> dict:
    return {
        "name": name,
        "category": category,
        "matched_on": name.lower(),
        "inferred": False,
        "source_section": "Skills",
        "source_text": None,
    }


def _profile_json(skills: list[dict], experience_months: int = 40) -> dict:
    return {
        "schema_version": "1",
        "summary": "Backend engineer.",
        "personal_info": None,
        "skills": skills,
        "experience": [
            {
                "company": "ABC Technologies",
                "job_title": "Backend Engineer",
                "title": None,
                "location": None,
                "employment_type": None,
                "start_date": "2022-01",
                "end_date": None,
                "original_start_date": None,
                "original_end_date": None,
                "is_current": True,
                "dates_uncertain": False,
                "duration_months": experience_months,
                "duration_label": "~3 years 4 months",
                "description": ["Developed asynchronous APIs using Python and FastAPI."],
                "responsibilities": [],
                "achievements": [],
                "technologies": ["Python", "FastAPI"],
                "source_section": "Experience",
                "source_text": None,
            }
        ],
        "education": [],
        "projects": [],
        "certifications": [],
        "languages": [],
        "metadata": {
            "parser_version": "rie-1.0.0",
            "processed_at": "2026-08-24T00:00:00Z",
            "language": None,
            "detected_sections": [],
            "warnings": [],
        },
    }


async def _attach_resume(session, candidate_id, profile_json, raw_text) -> Resume:
    profile = CandidateProfile(user_id=candidate_id, current_role="Engineer")
    session.add(profile)
    await session.flush()
    resume = Resume(
        user_id=candidate_id,
        profile_id=profile.id,
        original_filename=f"{candidate_id}.pdf",
        storage_path=f"/tmp/{candidate_id}.pdf",
        file_size=1024,
        file_type="pdf",
        mime_type="application/pdf",
        file_hash=uuid.uuid4().hex,
        status="parsed",
        is_primary=True,
        version=1,
    )
    session.add(resume)
    await session.flush()
    session.add(
        ParsedResumeData(
            resume_id=resume.id, raw_text=raw_text, parsed_json={"resume_profile": profile_json},
        )
    )
    await session.flush()
    return resume


def _block_embeddings(monkeypatch) -> None:
    from app.rag import embeddings as emb_module

    monkeypatch.setattr(
        emb_module.embedding_service, "embed_query", lambda *a, **k: [], raising=False,
    )


@pytest.mark.asyncio
async def test_screening_detail_returns_stored_result_and_breakdown(client: AsyncClient, session):
    recruiter_headers, _ = await _register_user(
        client, session, "Detail Recruiter", "detail-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Detail Candidate", "detail-candidate@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Detail Job")
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.UNDER_REVIEW,
        screening_status=ScreeningStatus.COMPLETED.value,
    )
    session.add(application)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 87))
    await session.flush()

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["application"]["id"] == str(application_id)
    assert body["application"]["job_id"] == str(job_id)
    assert body["application"]["status"] == "under_review"
    assert body["application"]["screening"]["effective_status"] == "completed"
    assert body["candidate"]["id"] == str(candidate_id)
    assert body["candidate"]["name"] == "Detail Candidate"
    assert body["job"]["id"] == str(job_id)
    assert body["job"]["required_skills"] == ["Python"]

    screening = body["screening_result"]
    assert screening["overall_match_score"] == 87
    assert screening["recommendation"] == "recommend"
    assert screening["matched_skills"] == ["Python", "FastAPI"]
    assert screening["missing_required_skills"] == ["Kubernetes"]

    breakdown = {item["key"]: item for item in body["match_breakdown"]}
    assert breakdown["skills"]["score"] == 92
    assert breakdown["skills"]["source_column"] == "skill_match_score"
    assert breakdown["semantic"]["score"] == 88
    assert len(breakdown) == 8
    assert body["freshness"]["screened_at"] is not None
    assert body["freshness"]["engine_version"] is None


@pytest.mark.asyncio
async def test_screening_detail_reports_pending_without_a_score(client: AsyncClient, session):
    recruiter_headers, _ = await _register_user(
        client, session, "Pending Recruiter", "pending-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Pending Candidate", "pending-candidate@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Pending Job")
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.APPLIED,
        screening_status=ScreeningStatus.QUEUED.value,
        screening_attempts=1,
    )
    session.add(application)
    await session.flush()
    application_id = application.id

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["screening_result"] is None
    assert body["match_breakdown"] == []
    assert body["application"]["screening"]["effective_status"] == "queued"
    assert body["application"]["screening"]["attempts"] == 1
    assert body["candidate"]["name"] == "Pending Candidate"
    assert body["freshness"]["screened_at"] is None


@pytest.mark.asyncio
async def test_screening_detail_reports_failed_state_without_fake_score(client: AsyncClient, session):
    recruiter_headers, _ = await _register_user(
        client, session, "Failed Recruiter", "failed-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Failed Candidate", "failed-candidate@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Failed Job")
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.APPLIED,
        screening_status=ScreeningStatus.FAILED.value,
        screening_error="Matching engine timed out",
        screening_attempts=2,
    )
    session.add(application)
    await session.flush()
    application_id = application.id

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["screening_result"] is None
    assert body["match_breakdown"] == []
    assert body["application"]["screening"]["effective_status"] == "failed"
    assert body["application"]["screening"]["error"] == "Matching engine timed out"
    assert body["application"]["status"] == "applied"


@pytest.mark.asyncio
async def test_screening_detail_is_scoped_to_the_application_not_the_candidate(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Multi Job Recruiter", "multi-job-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Multi Job Candidate", "multi-job-candidate@test.com",
    )
    first_job_id = await _create_job(client, recruiter_headers, "Multi Job A")
    second_job_id = await _create_job(client, recruiter_headers, "Multi Job B")
    first_application = JobApplication(
        job_id=first_job_id, candidate_id=candidate_id, status=ApplicationStatus.APPLIED,
    )
    second_application = JobApplication(
        job_id=second_job_id, candidate_id=candidate_id, status=ApplicationStatus.APPLIED,
    )
    session.add_all([first_application, second_application])
    await session.flush()
    first_application_id = first_application.id
    second_application_id = second_application.id
    session.add_all(
        [
            _screening_result(first_job_id, candidate_id, first_application_id, 91),
            _screening_result(second_job_id, candidate_id, second_application_id, 63),
        ]
    )
    await session.flush()

    first_response = await client.get(
        DETAIL_PATH.format(application_id=first_application_id), headers=recruiter_headers,
    )
    second_response = await client.get(
        DETAIL_PATH.format(application_id=second_application_id), headers=recruiter_headers,
    )
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_body = first_response.json()
    second_body = second_response.json()
    assert first_body["screening_result"]["overall_match_score"] == 91
    assert first_body["application"]["job_id"] == str(first_job_id)
    assert first_body["job"]["title"] == "Multi Job A"
    assert second_body["screening_result"]["overall_match_score"] == 63
    assert second_body["application"]["job_id"] == str(second_job_id)
    assert second_body["job"]["title"] == "Multi Job B"


@pytest.mark.asyncio
async def test_screening_detail_blocks_unauthorized_and_cross_tenant_access(
    client: AsyncClient, session,
):
    owner_headers, owner_id = await _register_user(
        client, session, "Detail Owner", "detail-owner@test.com", "hr",
    )
    job_id = await _create_job(client, owner_headers, "Protected Job")
    organization = Organization(
        name="Detail Organization",
        slug=f"detail-org-{uuid.uuid4().hex}",
    )
    session.add(organization)
    await session.flush()
    organization_id = organization.id
    job = await session.get(Job, job_id)
    job.organization_id = organization_id

    outsider_headers, _ = await _register_user(
        client, session, "Other Org Recruiter", "other-org-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Protected Candidate", "protected-candidate@test.com",
    )
    active_headers, active_id = await _register_user(
        client, session, "Same Org Recruiter", "same-org-recruiter@test.com", "hr",
    )
    application = JobApplication(
        job_id=job_id, candidate_id=candidate_id, status=ApplicationStatus.APPLIED,
    )
    session.add(application)
    await session.flush()
    application_id = application.id
    session.add(OrganizationMembership(
        user_id=active_id,
        organization_id=organization_id,
        role="recruiter",
        status=MembershipStatus.ACTIVE.value,
    ))
    await session.flush()

    owner_response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=owner_headers,
    )
    assert owner_response.status_code == 200

    active_response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=active_headers,
    )
    assert active_response.status_code == 200

    outsider_response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=outsider_headers,
    )
    assert outsider_response.status_code == 403
    assert "screening_result" not in outsider_response.json()

    assert owner_id != candidate_id

    missing_response = await client.get(
        DETAIL_PATH.format(application_id=uuid.uuid4()), headers=owner_headers,
    )
    assert missing_response.status_code == 404

    anonymous_response = await client.get(
        DETAIL_PATH.format(application_id=application_id),
    )
    assert anonymous_response.status_code == 422
    assert "screening_result" not in anonymous_response.json()


@pytest.mark.asyncio
async def test_candidate_role_cannot_read_recruiter_screening_detail(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Candidate Guard Recruiter", "candidate-guard-recruiter@test.com", "hr",
    )
    job_id = await _create_job(client, recruiter_headers, "Guarded Job")
    candidate_headers, candidate_id = await _register_user(
        client, session, "Guarded Candidate", "guarded-candidate@test.com",
    )
    application = JobApplication(
        job_id=job_id, candidate_id=candidate_id, status=ApplicationStatus.APPLIED,
    )
    session.add(application)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 77))
    await session.flush()

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=candidate_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_screening_detail_survives_missing_optional_intelligence(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Sparse Recruiter", "sparse-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Sparse Candidate", "sparse-candidate@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Sparse Job")
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.APPLIED,
        screening_status=ScreeningStatus.NOT_STARTED.value,
    )
    session.add(application)
    await session.flush()
    application_id = application.id

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["screening_result"] is None
    assert body["application"]["screening"]["effective_status"] == "not_started"
    assert body["candidate"]["has_resume"] is False
    assert body["candidate"]["resume_id"] is None
    assert body["freshness"]["resume_matches_application"] is None
    assert body["limitations"]
    assert "evidence_intelligence_section" in body
    assert "fit_section" in body


@pytest.mark.asyncio
async def test_screening_detail_composes_real_fit_and_evidence_sections(
    client: AsyncClient, session, monkeypatch,
):
    """The detail endpoint must reuse the existing engines, not re-derive data."""
    _block_embeddings(monkeypatch)
    recruiter_headers, _ = await _register_user(
        client, session, "Composed Recruiter", "composed-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Composed Candidate", "composed-candidate@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Composed Job")
    resume = await _attach_resume(
        session,
        candidate_id,
        _profile_json(skills=[_skill("Python", "Programming Language"),
                              _skill("FastAPI", "Framework")]),
        "Built asynchronous APIs with Python and FastAPI at ABC Technologies.",
    )
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.UNDER_REVIEW,
        screening_status=ScreeningStatus.COMPLETED.value,
    )
    session.add(application)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 84, resume.id))
    await session.flush()

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["fit_section"]["available"] is True
    assert body["fit_section"]["reason"] is None
    assert body["fit"] is not None
    assert body["fit"]["candidate_id"] == str(candidate_id)
    assert body["fit"]["job_id"] == str(job_id)
    assert body["fit"]["requirements"] is not None
    assert "skill_gaps" in body["fit"]
    assert body["freshness"]["fit_engine_version"]
    assert body["freshness"]["screening_resume_id"] == str(resume.id)
    assert body["freshness"]["resume_matches_application"] is True

    assert body["evidence_intelligence_section"]["available"] is (
        body["evidence_intelligence"] is not None
    )
    if body["evidence_intelligence"] is not None:
        assert body["evidence_intelligence"]["candidate_id"] == str(candidate_id)
        assert body["evidence_intelligence"]["candidate_name"] == "Composed Candidate"
    assert body["job_context_section"]["available"] is (
        body["job_context"] is not None
    )
    if body["job_context"] is not None:
        assert body["job_context"]["job_id"] == str(job_id)
        assert body["job_context"]["summary"]["text"]

    assert body["candidate"]["has_resume"] is True
    assert body["candidate"]["resume_id"] == str(resume.id)


@pytest.mark.asyncio
async def test_screening_detail_flags_resume_changed_after_screening(
    client: AsyncClient, session, monkeypatch,
):
    """A newer primary resume must be reported, never silently re-scored."""
    _block_embeddings(monkeypatch)
    recruiter_headers, _ = await _register_user(
        client, session, "Stale Recruiter", "stale-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Stale Candidate", "stale-candidate@test.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Stale Job")
    stale_resume = await _attach_resume(
        session,
        candidate_id,
        _profile_json(skills=[_skill("Python", "Programming Language")]),
        "Older resume.",
    )
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.UNDER_REVIEW,
        screening_status=ScreeningStatus.COMPLETED.value,
    )
    session.add(application)
    await session.flush()
    application_id = application.id
    session.add(
        _screening_result(job_id, candidate_id, application_id, 88, stale_resume.id)
    )
    await session.flush()

    newer_profile = await session.get(CandidateProfile, stale_resume.profile_id)
    stale_resume.is_primary = False
    session.add(
        Resume(
            user_id=candidate_id,
            profile_id=newer_profile.id,
            original_filename="newer.pdf",
            storage_path="/tmp/newer.pdf",
            file_size=2048,
            file_type="pdf",
            mime_type="application/pdf",
            file_hash=uuid.uuid4().hex,
            status="parsed",
            is_primary=True,
            version=2,
        )
    )
    await session.flush()

    response = await client.get(
        DETAIL_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["freshness"]["screening_resume_id"] == str(stale_resume.id)
    assert body["candidate"]["resume_id"] != str(stale_resume.id)
    assert body["freshness"]["resume_matches_application"] is False
    assert body["screening_result"]["overall_match_score"] == 88
