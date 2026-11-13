import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_candidate_dashboard(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Candidate User", "email": "candidate@test.com", "password": "SecureP@ss123"},
    )
    assert register_resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "candidate@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.get("/api/v1/candidates/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "profile" in data
    assert data["full_name"] == "Candidate User"
    assert data["email"] == "candidate@test.com"


@pytest.mark.asyncio
async def test_candidate_profile_crud(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Profile Test", "email": "profile@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "profile@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    get_resp = await client.get("/api/v1/candidates/profile", headers=headers)
    assert get_resp.status_code == 200

    update_resp = await client.put(
        "/api/v1/candidates/profile",
        json={"bio": "Experienced developer", "current_role": "Software Engineer", "location": "New York"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["bio"] == "Experienced developer"
    assert data["current_role"] == "Software Engineer"


@pytest.mark.asyncio
async def test_profile_completion(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Complete Test", "email": "complete@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "complete@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.get("/api/v1/candidates/profile/completion", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "completion_percentage" in data
    assert "sections" in data
    assert "missing_sections" in data
    assert "recommendations" in data


@pytest.mark.asyncio
async def test_education_crud(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Edu Test", "email": "edu@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "edu@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/candidates/education",
        json={"institution": "MIT", "degree": "B.Sc. Computer Science", "cgpa": 3.8},
        headers=headers,
    )
    assert create_resp.status_code == 201
    edu_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/candidates/education", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = await client.put(
        f"/api/v1/candidates/education/{edu_id}",
        json={"cgpa": 3.9},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["cgpa"] == 3.9

    delete_resp = await client.delete(f"/api/v1/candidates/education/{edu_id}", headers=headers)
    assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_experience_crud(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Exp Test", "email": "exp@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "exp@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/candidates/experience",
        json={"company": "Google", "job_title": "Software Engineer", "employment_type": "full_time"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    exp_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/candidates/experience", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = await client.delete(f"/api/v1/candidates/experience/{exp_id}", headers=headers)
    assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/candidates/dashboard")
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_notifications(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Notif Test", "email": "notif@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "notif@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    list_resp = await client.get("/api/v1/candidates/notifications", headers=headers)
    assert list_resp.status_code == 200

    unread_resp = await client.get("/api/v1/candidates/notifications/unread-count", headers=headers)
    assert unread_resp.status_code == 200


@pytest.mark.asyncio
async def test_candidate_avatar_lifecycle(client: AsyncClient) -> None:
    # 1. Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Avatar User", "email": "avatar@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "avatar@test.com", "password": "SecureP@ss123"},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 2. Check initial profile has no avatar
    prof_resp = await client.get("/api/v1/candidates/profile", headers=headers)
    assert prof_resp.status_code == 200
    assert prof_resp.json()["avatar_url"] is None

    # 3. Upload valid avatar
    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    files = {"file": ("avatar.png", image_bytes, "image/png")}
    upload_resp = await client.post("/api/v1/candidates/avatar", headers=headers, files=files)
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert upload_data["avatar_url"] is not None
    assert upload_data["avatar_url"].startswith("/uploads/avatars/")

    # 4. Fetch profile to confirm persistence
    prof_resp2 = await client.get("/api/v1/candidates/profile", headers=headers)
    assert prof_resp2.status_code == 200
    assert prof_resp2.json()["avatar_url"] == upload_data["avatar_url"]

    # 5. Fetch avatar via static files endpoint
    avatar_path = upload_data["avatar_url"]
    static_resp = await client.get(avatar_path)
    assert static_resp.status_code == 200

    # 6. Remove avatar
    delete_resp = await client.delete("/api/v1/candidates/avatar", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["avatar_url"] is None

    # 7. Confirm profile now has null avatar
    prof_resp3 = await client.get("/api/v1/candidates/profile", headers=headers)
    assert prof_resp3.status_code == 200
    assert prof_resp3.json()["avatar_url"] is None


@pytest.mark.asyncio
async def test_candidate_avatar_validation(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Val User", "email": "avatarval@test.com", "password": "SecureP@ss123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "avatarval@test.com", "password": "SecureP@ss123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Reject invalid file extension (.txt or .pdf)
    files = {"file": ("document.txt", b"plain text", "text/plain")}
    resp = await client.post("/api/v1/candidates/avatar", headers=headers, files=files)
    assert resp.status_code == 400
    assert "invalid file type" in resp.json()["detail"].lower()

    # Reject file exceeding 5 MB
    huge_bytes = b"0" * (5 * 1024 * 1024 + 10)
    files_huge = {"file": ("big.jpg", huge_bytes, "image/jpeg")}
    resp_huge = await client.post("/api/v1/candidates/avatar", headers=headers, files=files_huge)
    assert resp_huge.status_code == 400
    assert "exceeds" in resp_huge.json()["detail"].lower()


@pytest.mark.asyncio
async def test_candidate_avatar_isolation(client: AsyncClient) -> None:
    # Candidate A
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "User Alpha", "email": "alpha@test.com", "password": "SecureP@ss123"},
    )
    tok_a = (await client.post("/api/v1/auth/login", json={"email": "alpha@test.com", "password": "SecureP@ss123"})).json()
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}

    # Candidate B
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "User Beta", "email": "beta@test.com", "password": "SecureP@ss123"},
    )
    tok_b = (await client.post("/api/v1/auth/login", json={"email": "beta@test.com", "password": "SecureP@ss123"})).json()
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}

    # Upload Photo A
    img_a = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4alpha"
    resp_a = await client.post("/api/v1/candidates/avatar", headers=headers_a, files={"file": ("alpha.png", img_a, "image/png")})
    assert resp_a.status_code == 200
    url_a = resp_a.json()["avatar_url"]

    # Upload Photo B
    img_b = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4beta"
    resp_b = await client.post("/api/v1/candidates/avatar", headers=headers_b, files={"file": ("beta.png", img_b, "image/png")})
    assert resp_b.status_code == 200
    url_b = resp_b.json()["avatar_url"]

    # URLs must be distinct and specific to each user ID
    assert url_a != url_b

    # Verify Candidate A sees Photo A
    prof_a = (await client.get("/api/v1/candidates/profile", headers=headers_a)).json()
    assert prof_a["avatar_url"] == url_a

    # Verify Candidate B sees Photo B
    prof_b = (await client.get("/api/v1/candidates/profile", headers=headers_b)).json()
    assert prof_b["avatar_url"] == url_b

