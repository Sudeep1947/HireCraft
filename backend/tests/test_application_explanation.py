"""Phase 6: application-specific Explainable AI.

Covers the two guarantees that matter most:

1. **One authoritative explanation.** The recruiter and candidate endpoints are
   projections of the same stored ``ScreeningResult``, so they can never
   disagree about the score, and neither recomputes it.
2. **The candidate view is genuinely safe.** It is an allowlist, so the tests
   assert on the absence of internal fields rather than trusting the shape.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.domain.enums import (
    ApplicationStatus,
    HiringRecommendation,
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
    ParsedResumeData,
    Resume,
    Role,
    ScreeningResult,
    UserRole,
)
from app.repositories.user import UserRepository
from app.services.screening.application_explanation_service import (
    CANDIDATE_FORBIDDEN_KEY_TOKENS,
)

RECRUITER_PATH = "/api/v1/recruiter/jobs/applications/{application_id}/explanation"
CANDIDATE_PATH = "/api/v1/candidate/jobs/applications/{application_id}/explanation"


async def _register_user(
    client: AsyncClient,
    session,
    full_name: str,
    email: str,
    role_name: str | None = None,
):
    """Register and log in. Registration already grants the candidate role."""
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
        existing = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role.id,
            )
        )
        if existing.scalar_one_or_none() is None:
            await repository.assign_role(user_id, role.id)
            await session.commit()
        session.expire_all()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user_id


async def _strip_candidate_role(session, user_id) -> None:
    """Remove the default candidate role so a recruiter is not also a candidate."""
    repository = UserRepository(session)
    role = await repository.find_role_by_name("candidate")
    if role is not None:
        await repository.remove_role(user_id, role.id)
        await session.commit()
        session.expire_all()


async def _create_job(client: AsyncClient, headers: dict[str, str], title: str) -> uuid.UUID:
    response = await client.post(
        "/api/v1/recruiter/jobs",
        json={
            "title": title,
            "company": "Explainability Co",
            "employment_type": "full_time",
            "location": "Remote",
            "description": "Application explanation test",
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
            resume_id=resume.id,
            raw_text=raw_text,
            parsed_json={"resume_profile": profile_json},
        )
    )
    await session.flush()
    return resume


def _block_embeddings(monkeypatch) -> None:
    from app.rag import embeddings as emb_module

    monkeypatch.setattr(
        emb_module.embedding_service, "embed_query", lambda *a, **k: [], raising=False,
    )


def _application(session, job_id, candidate_id, status=ApplicationStatus.UNDER_REVIEW):
    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        status=status,
        screening_status=ScreeningStatus.COMPLETED.value,
    )
    session.add(application)
    return application


def _keys(payload) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.add(str(key))
            found |= _keys(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= _keys(item)
    return found


# ─── Recruiter view ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recruiter_explanation_explains_the_stored_score(client: AsyncClient, session):
    recruiter_headers, _ = await _register_user(
        client, session, "Explain Recruiter", "explain-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Explain Candidate", "explain-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Explained Job")
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 87))
    await session.flush()

    response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # The score is the stored screening result, not a recomputation.
    assert body["score"]["overall_score"] == 87
    assert body["score"]["source"] == "screening_result"
    assert body["screening_state"]["effective_status"] == "completed"
    assert body["screening_state"]["screened"] is True
    assert body["application"]["candidate_id"] == str(candidate_id)

    breakdown = {item["key"]: item["score"] for item in body["match_breakdown"]}
    assert breakdown["skills"] == 92
    assert breakdown["semantic"] == 88
    assert len(breakdown) == 8

    assert body["feature_importance"], "expected explainability dimensions"
    assert all("weight" in item for item in body["feature_importance"])
    assert body["positive_factors"], "expected positive factors"
    assert body["negative_factors"], "expected negative factors"
    assert body["reasoning_summary"]
    assert body["confidence"] is not None
    assert body["skill_alignment"]["matched_skills"] == ["Python", "FastAPI"]
    assert body["skill_alignment"]["missing_required_skills"] == ["Kubernetes"]
    assert body["freshness"]["screened_at"] is not None
    assert body["freshness"]["explainability_method"] == "rule_based"
    assert body["disclaimer"]
    assert body["limitations"]

    # Internal-only material stays on this side of the boundary.
    assert body["score"]["recommendation"] == "recommend"
    assert body["score"]["strength_level"] == "good"
    assert "review_flags" in body
    assert "screening_questions" in body
    assert "fit_formula" in body


@pytest.mark.asyncio
async def test_recruiter_explanation_reports_pending_without_inventing_a_score(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Pending Explain Recruiter", "pending-explain-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Pending Explain Candidate", "pending-explain-candidate@test.com",
        "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Pending Explained Job")
    application = _application(
        session, job_id, candidate_id, status=ApplicationStatus.APPLIED,
    )
    application.screening_status = ScreeningStatus.QUEUED.value
    await session.flush()
    application_id = application.id

    response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["score"]["overall_score"] is None
    assert body["score"]["source"] == "unavailable"
    assert body["screening_state"]["effective_status"] == "queued"
    assert body["screening_state"]["screened"] is False
    assert "prepared" in body["screening_state"]["message"]
    assert body["match_breakdown"] == []
    assert body["feature_importance"] == []
    assert body["positive_factors"] == []
    assert body["confidence"] is None
    assert body["explainability"]["available"] is False
    assert body["explainability"]["reason"]


@pytest.mark.asyncio
async def test_recruiter_explanation_reports_failure_without_a_fake_score(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Failed Explain Recruiter", "failed-explain-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Failed Explain Candidate", "failed-explain-candidate@test.com",
        "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Failed Explained Job")
    application = _application(session, job_id, candidate_id, status=ApplicationStatus.APPLIED)
    application.screening_status = ScreeningStatus.FAILED.value
    application.screening_error = "Matching engine timed out"
    await session.flush()
    application_id = application.id

    response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["score"]["overall_score"] is None
    assert body["screening_state"]["effective_status"] == "failed"
    assert body["application"]["screening_error"] == "Matching engine timed out"
    # The raw engine error is internal; only a human-readable message is shared.
    assert "timed out" not in body["screening_state"]["message"]


# ─── Candidate view ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_explanation_shows_the_same_score_without_internal_fields(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Shared Recruiter", "shared-recruiter@test.com", "hr",
    )
    candidate_headers, candidate_id = await _register_user(
        client, session, "Shared Candidate", "shared-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Shared Job")
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 87))
    await session.flush()

    recruiter_response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    candidate_response = await client.get(
        CANDIDATE_PATH.format(application_id=application_id), headers=candidate_headers,
    )
    assert recruiter_response.status_code == 200, recruiter_response.text
    assert candidate_response.status_code == 200, candidate_response.text

    recruiter_body = recruiter_response.json()
    body = candidate_response.json()

    # Same authoritative score, same state, same dimensions.
    assert body["score"]["overall_score"] == recruiter_body["score"]["overall_score"] == 87
    assert body["screening_state"] == recruiter_body["screening_state"]
    assert [f["label"] for f in body["feature_importance"]] == [
        f["label"] for f in recruiter_body["feature_importance"]
    ]
    assert body["application"]["id"] == str(application_id)
    assert body["application"]["status"] == "under_review"

    # Candidate-safe naming, and no internal verdicts.
    assert "recommendation" not in body["score"]
    assert "strength_level" not in body["score"]
    assert body["matched_skills"] == ["Python", "FastAPI"]
    assert "Kubernetes" in body["areas_with_limited_evidence"]
    assert body["aligned_areas"]
    assert body["limited_areas"]
    assert body["screening_notice"]

    keys = _keys(body)
    assert {
        "review_flags",
        "screening_questions",
        "fit_formula",
        "fit_weights",
        "recruiter_note",
        "screening_error",
    } & keys == set()
    for token in CANDIDATE_FORBIDDEN_KEY_TOKENS:
        assert not any(token in key.lower() for key in keys), token


@pytest.mark.asyncio
async def test_candidate_explanation_never_exposes_another_candidates_data(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Isolation Recruiter", "isolation-recruiter@test.com", "hr",
    )
    first_headers, first_id = await _register_user(
        client, session, "First Candidate", "first-candidate@test.com", "candidate",
    )
    _, second_id = await _register_user(
        client, session, "Second Candidate", "second-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Isolation Job")
    first = _application(session, job_id, first_id)
    second = _application(session, job_id, second_id)
    await session.flush()
    first_id_app, second_id_app = first.id, second.id
    session.add(_screening_result(job_id, first_id, first_id_app, 95))
    session.add(_screening_result(job_id, second_id, second_id_app, 41))
    await session.flush()

    own = await client.get(
        CANDIDATE_PATH.format(application_id=first_id_app), headers=first_headers,
    )
    assert own.status_code == 200, own.text
    body = own.json()
    assert body["score"]["overall_score"] == 95
    assert str(second_id) not in str(body)

    # Somebody else's application is indistinguishable from a missing one.
    stolen = await client.get(
        CANDIDATE_PATH.format(application_id=second_id_app), headers=first_headers,
    )
    missing = await client.get(
        CANDIDATE_PATH.format(application_id=uuid.uuid4()), headers=first_headers,
    )
    assert stolen.status_code == 404
    assert missing.status_code == 404
    assert stolen.json()["error"]["message"] == missing.json()["error"]["message"]
    assert stolen.json()["error"]["code"] == missing.json()["error"]["code"]

    anonymous = await client.get(CANDIDATE_PATH.format(application_id=first_id_app))
    assert anonymous.status_code == 422


@pytest.mark.asyncio
async def test_roles_cannot_cross_the_explanation_boundary(client: AsyncClient, session):
    recruiter_headers, recruiter_id = await _register_user(
        client, session, "Boundary Recruiter", "boundary-recruiter@test.com", "hr",
    )
    # Registration grants the candidate role; a pure recruiter must not keep it,
    # otherwise the candidate route's role gate would legitimately admit them.
    await _strip_candidate_role(session, recruiter_id)
    candidate_headers, candidate_id = await _register_user(
        client, session, "Boundary Candidate", "boundary-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Boundary Job")
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 80))
    await session.flush()

    as_candidate = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=candidate_headers,
    )
    assert as_candidate.status_code == 403

    as_recruiter = await client.get(
        CANDIDATE_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert as_recruiter.status_code == 403


@pytest.mark.asyncio
async def test_explanation_is_scoped_to_one_application_of_many(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Multi Recruiter", "multi-explain-recruiter@test.com", "hr",
    )
    candidate_headers, candidate_id = await _register_user(
        client, session, "Multi Candidate", "multi-candidate@test.com", "candidate",
    )
    first_job = await _create_job(client, recruiter_headers, "Multi Explained A")
    second_job = await _create_job(client, recruiter_headers, "Multi Explained B")
    first = _application(session, first_job, candidate_id)
    second = _application(session, second_job, candidate_id)
    await session.flush()
    first_app_id, second_app_id = first.id, second.id
    session.add(_screening_result(first_job, candidate_id, first_app_id, 91))
    session.add(_screening_result(second_job, candidate_id, second_app_id, 63))
    await session.flush()

    first_response = await client.get(
        CANDIDATE_PATH.format(application_id=first_app_id), headers=candidate_headers,
    )
    second_response = await client.get(
        CANDIDATE_PATH.format(application_id=second_app_id), headers=candidate_headers,
    )
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text

    first_body, second_body = first_response.json(), second_response.json()
    assert first_body["score"]["overall_score"] == 91
    assert first_body["job"]["id"] == str(first_job)
    assert first_body["job"]["title"] == "Multi Explained A"
    assert second_body["score"]["overall_score"] == 63
    assert second_body["job"]["id"] == str(second_job)
    assert second_body["job"]["title"] == "Multi Explained B"


@pytest.mark.asyncio
async def test_explanation_blocks_cross_tenant_recruiters(client: AsyncClient, session):
    owner_headers, _ = await _register_user(
        client, session, "Tenant Owner", "tenant-owner@test.com", "hr",
    )
    job_id = await _create_job(client, owner_headers, "Tenant Job")
    organization = Organization(name="Explanation Org", slug=f"explain-org-{uuid.uuid4().hex}")
    session.add(organization)
    await session.flush()
    organization_id = organization.id
    job = await session.get(Job, job_id)
    job.organization_id = organization_id

    outsider_headers, _ = await _register_user(
        client, session, "Outsider Recruiter", "outsider-recruiter@test.com", "hr",
    )
    same_org_headers, same_org_id = await _register_user(
        client, session, "Same Org Recruiter", "same-org-recruiter@test.com", "hr",
    )
    _, candidate_id = await _register_user(
        client, session, "Tenant Candidate", "tenant-candidate@test.com", "candidate",
    )
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(OrganizationMembership(
        user_id=same_org_id,
        organization_id=organization_id,
        role="recruiter",
        status=MembershipStatus.ACTIVE.value,
    ))
    session.add(_screening_result(job_id, candidate_id, application_id, 75))
    await session.flush()

    assert (await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=owner_headers,
    )).status_code == 200
    assert (await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=same_org_headers,
    )).status_code == 200

    denied = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=outsider_headers,
    )
    assert denied.status_code == 403
    assert "positive_factors" not in denied.text

    assert (await client.get(
        RECRUITER_PATH.format(application_id=uuid.uuid4()), headers=owner_headers,
    )).status_code == 404


# ─── Evidence grounding and freshness ──────────────────────────────


def test_factor_evidence_is_attached_only_when_it_really_matches():
    """Unit-level guard on the evidence lookup used by every factor."""
    from app.services.screening.application_explanation_service import (
        ApplicationExplanationService,
    )

    lookup = ApplicationExplanationService._lookup_evidence
    index = {
        "python": [{"source": "experience", "quote": "Built APIs in Python", "context": None, "section": None}],
        "go": [{"source": "project", "quote": "Wrote a Go service", "context": None, "section": None}],
    }

    # Exact category match.
    assert lookup(None, "python", index) == index["python"]
    # Skill named inside the factor's own reason text.
    assert lookup("Matched Skills", "Successfully matched 2 skills: Python, Docker", index) == index["python"]
    # Word boundaries: "Go" must not match "Google".
    assert lookup("Experience", "Used Google Cloud", index) == []
    assert lookup("Experience", "Wrote a Go service", index) == index["go"]
    # Nothing located -> no evidence, rather than the closest thing available.
    assert lookup("Location", "Location is a strong match", index) == []
    assert lookup("Location", "", index) == []


@pytest.mark.asyncio
async def test_explanation_grounds_factors_in_real_resume_evidence(
    client: AsyncClient, session, monkeypatch,
):
    _block_embeddings(monkeypatch)
    recruiter_headers, _ = await _register_user(
        client, session, "Grounded Recruiter", "grounded-recruiter@test.com", "hr",
    )
    candidate_headers, candidate_id = await _register_user(
        client, session, "Grounded Candidate", "grounded-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Grounded Job")
    resume = await _attach_resume(
        session,
        candidate_id,
        _profile_json(skills=[_skill("Python", "Programming Language")]),
        "Developed asynchronous APIs using Python at ABC Technologies.",
    )
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 86, resume.id))
    await session.flush()

    recruiter_response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    candidate_response = await client.get(
        CANDIDATE_PATH.format(application_id=application_id), headers=candidate_headers,
    )
    assert recruiter_response.status_code == 200, recruiter_response.text
    assert candidate_response.status_code == 200, candidate_response.text

    recruiter_body = recruiter_response.json()
    body = candidate_response.json()

    # The real Phase 2/3 engines ran; the explanation composes their output.
    assert recruiter_body["fit"]["available"] is True
    assert recruiter_body["evidence_intelligence"]["available"] is True
    assert recruiter_body["requirements"], "expected requirement-level results"
    assert body["requirements"]
    assert body["resume_evidence"], "expected quotes from the candidate's own resume"
    for item in body["resume_evidence"]:
        assert item["quote"].strip()
        assert set(item) <= {"source", "quote", "context", "section"}

    # Requirement evidence is grounded in a real quote from this resume.
    python = next(
        item for item in body["requirements"] if item["requirement"] == "Python"
    )
    assert python["evidence"], "a matched requirement must cite resume evidence"
    assert any("Python" in item["quote"] for item in python["evidence"])

    # A factor never claims evidence it does not have.
    for factor in (*body["aligned_areas"], *body["limited_areas"]):
        assert factor["evidence_available"] == bool(factor["evidence"])

    assert body["freshness"]["screening_resume_id"] == str(resume.id)
    assert body["freshness"]["primary_resume_id"] == str(resume.id)
    assert recruiter_body["freshness"]["fit_engine_version"]


@pytest.mark.asyncio
async def test_explanation_flags_a_newer_resume_instead_of_rescoring(
    client: AsyncClient, session, monkeypatch,
):
    _block_embeddings(monkeypatch)
    recruiter_headers, _ = await _register_user(
        client, session, "Drift Recruiter", "drift-recruiter@test.com", "hr",
    )
    candidate_headers, candidate_id = await _register_user(
        client, session, "Drift Candidate", "drift-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Drift Job")
    stale = await _attach_resume(
        session,
        candidate_id,
        _profile_json(skills=[_skill("Python", "Programming Language")]),
        "Older resume.",
    )
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 88, stale.id))
    await session.flush()

    profile = await session.get(CandidateProfile, stale.profile_id)
    stale.is_primary = False
    session.add(Resume(
        user_id=candidate_id,
        profile_id=profile.id,
        original_filename="newer.pdf",
        storage_path="/tmp/newer.pdf",
        file_size=2048,
        file_type="pdf",
        mime_type="application/pdf",
        file_hash=uuid.uuid4().hex,
        status="parsed",
        is_primary=True,
        version=2,
    ))
    await session.flush()

    response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["score"]["overall_score"] == 88
    assert body["freshness"]["screening_resume_id"] == str(stale.id)
    assert body["freshness"]["primary_resume_id"] != str(stale.id)
    assert body["freshness"]["screening_resume_is_current_primary"] is False
    assert any("newer primary resume" in item for item in body["limitations"])

    candidate_response = await client.get(
        CANDIDATE_PATH.format(application_id=application_id), headers=candidate_headers,
    )
    assert candidate_response.status_code == 200, candidate_response.text
    candidate_body = candidate_response.json()
    assert candidate_body["freshness"]["screening_resume_is_current_primary"] is False
    assert any("newer primary resume" in item for item in candidate_body["limitations"])


@pytest.mark.asyncio
async def test_explanation_survives_missing_optional_intelligence(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_user(
        client, session, "Sparse Recruiter", "sparse-explain-recruiter@test.com", "hr",
    )
    candidate_headers, candidate_id = await _register_user(
        client, session, "Sparse Candidate", "sparse-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Sparse Job")
    application = _application(session, job_id, candidate_id, status=ApplicationStatus.APPLIED)
    application.screening_status = ScreeningStatus.NOT_STARTED.value
    await session.flush()
    application_id = application.id

    recruiter_response = await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )
    candidate_response = await client.get(
        CANDIDATE_PATH.format(application_id=application_id), headers=candidate_headers,
    )
    assert recruiter_response.status_code == 200, recruiter_response.text
    assert candidate_response.status_code == 200, candidate_response.text

    recruiter_body = recruiter_response.json()
    body = candidate_response.json()

    assert recruiter_body["score"]["overall_score"] is None
    assert recruiter_body["screening_state"]["effective_status"] == "not_started"
    assert recruiter_body["requirements"] == []
    assert recruiter_body["evidence_gaps"] == []
    assert recruiter_body["fit"]["available"] is False
    assert recruiter_body["fit"]["reason"]
    assert recruiter_body["evidence_intelligence"]["available"] is False
    assert recruiter_body["evidence_intelligence"]["reason"]

    assert body["score"]["overall_score"] is None
    assert body["requirements"] == []
    assert body["resume_evidence"] == []
    assert body["fit"]["available"] is False
    assert body["fit"]["reason"]
    # Internal engine provenance is not the candidate's business.
    assert all("engine version" not in item for item in body["limitations"])


# ─── Audit ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explanation_views_are_audited_without_content(
    client: AsyncClient, session,
):
    recruiter_headers, recruiter_id = await _register_user(
        client, session, "Audited Recruiter", "audited-recruiter@test.com", "hr",
    )
    candidate_headers, candidate_id = await _register_user(
        client, session, "Audited Candidate", "audited-candidate@test.com", "candidate",
    )
    job_id = await _create_job(client, recruiter_headers, "Audited Job")
    application = _application(session, job_id, candidate_id)
    await session.flush()
    application_id = application.id
    session.add(_screening_result(job_id, candidate_id, application_id, 83))
    await session.flush()

    assert (await client.get(
        RECRUITER_PATH.format(application_id=application_id), headers=recruiter_headers,
    )).status_code == 200
    assert (await client.get(
        CANDIDATE_PATH.format(application_id=application_id), headers=candidate_headers,
    )).status_code == 200

    result = await session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == str(application_id),
        )
    )
    rows = result.scalars().all()
    actions = {row.action for row in rows}
    assert "application_explanation_viewed" in actions
    assert "candidate_explanation_viewed" in actions

    by_user = {row.user_id: row for row in rows}
    assert by_user[recruiter_id].event_type == "application_explanation_viewed"
    assert by_user[candidate_id].event_type == "candidate_explanation_viewed"
    for row in rows:
        # Identifiers only: no score, no evidence, no resume content.
        assert set(row.details) == {
            "job_id", "candidate_id", "screening_result_id", "screened",
        }
        assert all(isinstance(value, (str, bool, type(None))) for value in row.details.values())
        assert row.resource_type == "job_application"
