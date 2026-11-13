import uuid

import pytest
from httpx import AsyncClient

from app.domain.models import Role, UserRole


async def _ensure_role(session, name, description):
    """Get or create a Role by name."""
    from app.repositories.user import UserRepository
    repo = UserRepository(session)
    role = await repo.find_role_by_name(name)
    if not role:
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()
    return role


async def _setup_hr(client, session, email_suffix):
    """Create HR role + user and return (headers, hr_role_obj)."""
    hr_role = await _ensure_role(session, "hr", "HR user")
    await _ensure_role(session, "candidate", "Job applicant")
    await session.flush()

    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": f"HR {email_suffix}", "email": f"hr{email_suffix}@test.com", "password": "SecureP@ss123"},
    )
    user_id = uuid.UUID(resp.json()["id"])

    from app.repositories.user import UserRepository
    repo = UserRepository(session)
    await repo.assign_role(user_id, hr_role.id)
    session.expire_all()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"hr{email_suffix}@test.com", "password": "SecureP@ss123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return headers, hr_role


async def _setup_candidate(client, session, email_suffix):
    """Register candidate (role auto-assigned) and return headers."""
    await _ensure_role(session, "candidate", "Job applicant")
    await session.flush()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": f"Candidate {email_suffix}", "email": f"cand{email_suffix}@test.com", "password": "SecureP@ss123"},
    )
    assert resp.status_code == 201
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"cand{email_suffix}@test.com", "password": "SecureP@ss123"},
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


async def _create_published_job(client, headers, title):
    resp = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": title, "company": "Test Co", "employment_type": "full_time", "location": "NYC", "description": "A job", "required_skills": ["Python"], "status": "published"},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_recruiter_create_job(client: AsyncClient, session) -> None:
    headers, _ = await _setup_hr(client, session, "1")

    create_resp = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Software Engineer", "company": "Tech Corp", "employment_type": "full_time", "location": "New York", "description": "Build amazing software", "required_skills": ["Python", "React"]},
        headers=headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["title"] == "Software Engineer"
    assert data["company"] == "Tech Corp"
    assert data["status"] == "draft"
    assert data["required_skills"] == ["Python", "React"]


@pytest.mark.asyncio
async def test_recruiter_list_jobs(client: AsyncClient, session) -> None:
    headers, _ = await _setup_hr(client, session, "2")

    for i in range(2):
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": f"Job {i}", "company": "C", "employment_type": "full_time", "location": "NYC", "description": "Desc", "required_skills": ["Python"]},
            headers=headers,
        )

    list_resp = await client.get("/api/v1/recruiter/jobs", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2


@pytest.mark.asyncio
async def test_recruiter_job_crud(client: AsyncClient, session) -> None:
    headers, _ = await _setup_hr(client, session, "3")

    create_resp = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Backend Engineer", "company": "Acme Inc", "employment_type": "full_time", "location": "Remote", "description": "Backend role", "required_skills": ["Python", "FastAPI"]},
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/recruiter/jobs/{job_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Backend Engineer"

    update_resp = await client.put(f"/api/v1/recruiter/jobs/{job_id}", json={"title": "Senior Backend Engineer", "salary_min": 100000}, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Senior Backend Engineer"

    status_resp = await client.patch(f"/api/v1/recruiter/jobs/{job_id}/status?status=published", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "published"

    delete_resp = await client.delete(f"/api/v1/recruiter/jobs/{job_id}", headers=headers)
    assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_candidate_job_portal(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "4")
    job_id = await _create_published_job(client, hr_headers, "Public Job")
    cand_headers = await _setup_candidate(client, session, "1")

    search_resp = await client.get("/api/v1/candidate/jobs/search", headers=cand_headers)
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] >= 1

    detail_resp = await client.get(f"/api/v1/candidate/jobs/{job_id}", headers=cand_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Public Job"


@pytest.mark.asyncio
async def test_candidate_apply_and_save(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "5")
    job_id = await _create_published_job(client, hr_headers, "Apply Test Job")
    cand_headers = await _setup_candidate(client, session, "2")

    apply_resp = await client.post(
        "/api/v1/candidate/jobs/apply",
        json={"job_id": job_id, "cover_letter": "I am a great fit"},
        headers=cand_headers,
    )
    assert apply_resp.status_code == 201
    assert apply_resp.json()["status"] == "applied"

    duplicate_resp = await client.post("/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=cand_headers)
    assert duplicate_resp.status_code == 400

    apps_resp = await client.get("/api/v1/candidate/jobs/applications", headers=cand_headers)
    assert apps_resp.status_code == 200
    assert len(apps_resp.json()) == 1

    save_resp = await client.post(f"/api/v1/candidate/jobs/saved?job_id={job_id}", headers=cand_headers)
    assert save_resp.status_code == 201

    saved_resp = await client.get("/api/v1/candidate/jobs/saved", headers=cand_headers)
    assert saved_resp.status_code == 200
    assert len(saved_resp.json()) == 1


@pytest.mark.asyncio
async def test_recruiter_dashboard_and_applications(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "6")
    job_id = await _create_published_job(client, hr_headers, "Dashboard Test Job")
    cand_headers = await _setup_candidate(client, session, "3")

    await client.post("/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=cand_headers)

    dash_resp = await client.get("/api/v1/recruiter/jobs/dashboard", headers=hr_headers)
    assert dash_resp.status_code == 200
    d = dash_resp.json()
    assert d["total_jobs"] >= 1
    assert d["published_jobs"] >= 1
    assert d["total_applications"] >= 1

    apps_resp = await client.get(f"/api/v1/recruiter/jobs/{job_id}/applications", headers=hr_headers)
    assert apps_resp.status_code == 200
    apps = apps_resp.json()
    assert len(apps) == 1

    app_id = apps[0]["id"]
    status_resp = await client.patch(f"/api/v1/recruiter/jobs/applications/{app_id}/status", json={"status": "under_review"}, headers=hr_headers)
    assert status_resp.status_code == 200

    note_resp = await client.post(f"/api/v1/recruiter/jobs/applications/{app_id}/notes", json={"note": "Strong candidate"}, headers=hr_headers)
    assert note_resp.status_code == 201
    assert note_resp.json()["note"] == "Strong candidate"


@pytest.mark.asyncio
async def test_candidate_withdraw(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "7")
    job_id = await _create_published_job(client, hr_headers, "Withdraw Test")
    cand_headers = await _setup_candidate(client, session, "4")

    apply_resp = await client.post("/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=cand_headers)
    app_id = apply_resp.json()["id"]

    withdraw_resp = await client.post(f"/api/v1/candidate/jobs/applications/{app_id}/withdraw", headers=cand_headers)
    assert withdraw_resp.status_code == 200


@pytest.mark.asyncio
async def test_application_sends_notification_to_recruiter(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "notif1")
    job_id = await _create_published_job(client, hr_headers, "Notif Test Job")
    cand_headers = await _setup_candidate(client, session, "notif_cand1")

    await client.post("/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=cand_headers)

    notif_resp = await client.get("/api/v1/notifications", headers=hr_headers)
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()
    assert any("applied" in n["message"].lower() for n in notifs)


@pytest.mark.asyncio
async def test_notifications_crud(client: AsyncClient, session) -> None:
    cand_headers = await _setup_candidate(client, session, "notif_cand2")

    notif_resp = await client.get("/api/v1/notifications", headers=cand_headers)
    assert notif_resp.status_code == 200

    count_resp = await client.get("/api/v1/notifications/unread-count", headers=cand_headers)
    assert count_resp.status_code == 200
    assert "count" in count_resp.json()

    mark_all_resp = await client.put("/api/v1/notifications/read-all", headers=cand_headers)
    assert mark_all_resp.status_code == 200


@pytest.mark.asyncio
async def test_recruiter_note_edit_delete(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "note1")
    job_id = await _create_published_job(client, hr_headers, "Note Test Job")
    cand_headers = await _setup_candidate(client, session, "note_cand1")

    await client.post("/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=cand_headers)

    apps_resp = await client.get(f"/api/v1/recruiter/jobs/{job_id}/applications", headers=hr_headers)
    app_id = apps_resp.json()[0]["id"]

    note_resp = await client.post(f"/api/v1/recruiter/jobs/applications/{app_id}/notes", json={"note": "Original note"}, headers=hr_headers)
    assert note_resp.status_code == 201
    note_id = note_resp.json()["id"]

    update_resp = await client.put(f"/api/v1/recruiter/jobs/applications/{app_id}/notes/{note_id}", json={"note": "Updated note"}, headers=hr_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["note"] == "Updated note"

    delete_resp = await client.delete(f"/api/v1/recruiter/jobs/applications/{app_id}/notes/{note_id}", headers=hr_headers)
    assert delete_resp.status_code == 200

    apps_resp2 = await client.get(f"/api/v1/recruiter/jobs/{job_id}/applications", headers=hr_headers)
    assert len(apps_resp2.json()[0]["recruiter_notes"]) == 0


@pytest.mark.asyncio
async def test_withdraw_finalized_application(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "withdraw1")
    job_id = await _create_published_job(client, hr_headers, "Withdraw Finalized")
    cand_headers = await _setup_candidate(client, session, "withdraw_cand1")

    apply_resp = await client.post("/api/v1/candidate/jobs/apply", json={"job_id": job_id}, headers=cand_headers)
    app_id = apply_resp.json()["id"]

    # Advance to HIRED through the legal lifecycle funnel.
    for status in ("shortlisted", "interview_scheduled", "offered", "hired"):
        status_resp = await client.patch(
            f"/api/v1/recruiter/jobs/applications/{app_id}/status",
            json={"status": status},
            headers=hr_headers,
        )
        assert status_resp.status_code == 200, status_resp.text

    withdraw_resp = await client.post(f"/api/v1/candidate/jobs/applications/{app_id}/withdraw", headers=cand_headers)
    assert withdraw_resp.status_code == 409


@pytest.mark.asyncio
async def test_unsave_job(client: AsyncClient, session) -> None:
    hr_headers, _ = await _setup_hr(client, session, "unsave1")
    job_id = await _create_published_job(client, hr_headers, "Unsave Test")
    cand_headers = await _setup_candidate(client, session, "unsave_cand1")

    save_resp = await client.post(f"/api/v1/candidate/jobs/saved?job_id={job_id}", headers=cand_headers)
    assert save_resp.status_code == 201

    saved_resp = await client.get("/api/v1/candidate/jobs/saved", headers=cand_headers)
    assert len(saved_resp.json()) == 1

    unsave_resp = await client.delete(f"/api/v1/candidate/jobs/saved/{job_id}", headers=cand_headers)
    assert unsave_resp.status_code == 200

    saved_resp2 = await client.get("/api/v1/candidate/jobs/saved", headers=cand_headers)
    assert len(saved_resp2.json()) == 0
