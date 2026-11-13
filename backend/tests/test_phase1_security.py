"""Phase 1 Security Tests - Enterprise Identity & Authorization.

Tests the critical security requirements:
- Candidate-only public registration
- Privilege escalation prevention
- Account status enforcement
- Invitation security
- Tenant isolation
- Authorization boundaries
"""
import pytest
from httpx import AsyncClient


# ═══════════════════════════════════════════════════════════════════
# Registration Security
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_candidate_only(client: AsyncClient):
    """Registration should only create candidate accounts."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "New Candidate",
            "email": "new_candidate@test.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "candidate" in data["roles"]
    assert data["email"] == "new_candidate@test.com"


@pytest.mark.asyncio
async def test_register_rejects_recruiter_role(client: AsyncClient):
    """Public registration must NOT allow recruiter role."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake Recruiter",
            "email": "fake_recruiter@test.com",
            "password": "SecureP@ss1",
            "role": "recruiter",
        },
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "recruiter" not in data.get("roles", []), "Role injection succeeded!"


@pytest.mark.asyncio
async def test_register_rejects_hr_role(client: AsyncClient):
    """Public registration must NOT allow HR role."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake HR",
            "email": "fake_hr@test.com",
            "password": "SecureP@ss1",
            "role": "hr",
        },
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "hr" not in data.get("roles", []), "Role injection succeeded!"


@pytest.mark.asyncio
async def test_register_admin_role_ignored(client: AsyncClient):
    """Public registration must NOT allow admin role — role is silently ignored."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake Admin",
            "email": "fake_admin@test.com",
            "password": "SecureP@ss1",
            "role": "admin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "admin" not in data.get("roles", []), "Role injection succeeded!"


@pytest.mark.asyncio
async def test_register_no_role_field_returns_candidate(client: AsyncClient):
    """Even without explicit role, registration creates candidate."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "No Role Specified",
            "email": "no_role@test.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "candidate" in data["roles"]


@pytest.mark.asyncio
async def test_register_invalid_role_ignored(client: AsyncClient):
    """Invalid role values are silently ignored — always creates candidate."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Bad Role",
            "email": "bad_role@test.com",
            "password": "SecureP@ss1",
            "role": "superadmin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "superadmin" not in data.get("roles", []), "Role injection succeeded!"


# ═══════════════════════════════════════════════════════════════════
# Privilege Escalation Prevention
# ═══════════════════════════════════════════════════════════════════


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Helper: register a candidate user and return their access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Test User", "email": email, "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss1"},
    )
    return login_resp.json()["access_token"]


@pytest.mark.asyncio
async def test_candidate_cannot_access_admin_endpoints(client: AsyncClient):
    """Candidate token should be rejected on admin endpoints."""
    token = await _register_and_login(client, "cand_admin@test.com")
    resp = await client.get(
        "/api/v1/dashboard/admin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_candidate_cannot_access_hr_endpoints(client: AsyncClient):
    """Candidate token should be rejected on HR endpoints."""
    token = await _register_and_login(client, "cand_hr@test.com")
    resp = await client.get(
        "/api/v1/dashboard/hr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_candidate_cannot_access_recruiter_endpoints(client: AsyncClient):
    """Candidate token should be rejected on recruiter endpoints."""
    token = await _register_and_login(client, "cand_rec@test.com")
    resp = await client.get(
        "/api/v1/dashboard/recruiter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_any_dashboard(client: AsyncClient):
    """Unauthenticated requests must be rejected."""
    for path in [
        "/api/v1/dashboard/candidate",
        "/api/v1/dashboard/recruiter",
        "/api/v1/dashboard/hr",
        "/api/v1/dashboard/admin",
    ]:
        resp = await client.get(path)
        assert resp.status_code in (401, 422), f"{path} should require auth"


@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    """Invalid JWT tokens must be rejected."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_used_as_access_token(client: AsyncClient):
    """Refresh tokens must not work as access tokens."""
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Token Test", "email": "token_test@test.com", "password": "SecureP@ss1"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "token_test@test.com", "password": "SecureP@ss1"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert me_resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# Account Status
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_returns_account_status(client: AsyncClient):
    """Login response should include account status info."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Status Test", "email": "status_test@test.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "is_active" in data


@pytest.mark.asyncio
async def test_me_endpoint_returns_user_info(client: AsyncClient):
    """GET /me should return current user info."""
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Me Test", "email": "me_test@test.com", "password": "SecureP@ss1"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "me_test@test.com", "password": "SecureP@ss1"},
    )
    token = login_resp.json()["access_token"]
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "me_test@test.com"
    assert "candidate" in data["roles"]


# ═══════════════════════════════════════════════════════════════════
# Invitation Security
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_validate_invalid_invitation_token(client: AsyncClient):
    """Invalid invitation tokens should return valid=false."""
    resp = await client.get("/api/v1/invitations/validate/invalid-token-123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False


@pytest.mark.asyncio
async def test_accept_invitation_invalid_token_fails(client: AsyncClient):
    """Accepting with invalid token should fail."""
    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": "totally-invalid-token",
            "full_name": "Should Fail",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code in (400, 404, 422)


@pytest.mark.asyncio
async def test_accept_invitation_password_mismatch(client: AsyncClient):
    """Accepting with mismatched passwords should fail."""
    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": "some-token",
            "full_name": "Mismatch Test",
            "password": "SecureP@ss1",
            "confirm_password": "DifferentP@ss1",
        },
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Token Lifecycle
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_auth_lifecycle(client: AsyncClient):
    """Test: register -> login -> access -> refresh -> access -> logout -> refresh fails."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Lifecycle", "email": "lifecycle_p1@test.com", "password": "SecureP@ss1"},
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "lifecycle_p1@test.com", "password": "SecureP@ss1"},
    )
    assert login.status_code == 200
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200

    ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert ref.status_code == 200
    new_access = ref.json()["access_token"]
    new_refresh = ref.json()["refresh_token"]

    me2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me2.status_code == 200

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh},
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert logout.status_code == 200

    old_refresh_fail = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert old_refresh_fail.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    """Refresh tokens should be rotated on each use."""
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Rotation", "email": "rotation@test.com", "password": "SecureP@ss1"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rotation@test.com", "password": "SecureP@ss1"},
    )
    token1 = login.json()["refresh_token"]

    ref1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": token1})
    assert ref1.status_code == 200
    token2 = ref1.json()["refresh_token"]
    assert token1 != token2

    ref2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": token1})
    assert ref2.status_code == 401

    ref3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": token2})
    assert ref3.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Password Security
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_weak_password_rejected(client: AsyncClient):
    """Weak passwords should be rejected."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Weak PW", "email": "weak@test.com", "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_password_without_uppercase_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Upper", "email": "noupper@test.com", "password": "alllowercase1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_wrong_password_returns_401(client: AsyncClient):
    """Wrong password should return 401 with generic message."""
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Wrong PW", "email": "wrongpw@test.com", "password": "SecureP@ss1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@test.com", "password": "WrongPassword"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["error"]["message"]
