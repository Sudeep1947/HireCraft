"""Comprehensive authentication tests for Phase 4.5A.

Covers: password strength, JWT claims, refresh token lifecycle,
session management, role enforcement, error messages, and
regression tests for existing auth flows.
"""

import pytest
from httpx import AsyncClient

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


# ═══════════════════════════════════════════════════════════════════
# STEP 12.1 – Password Strength Validation (unit)
# ═══════════════════════════════════════════════════════════════════


class TestPasswordStrength:
    def test_strong_password(self):
        assert validate_password_strength("SecureP@ss1") == []

    def test_too_short(self):
        issues = validate_password_strength("Ab1!")
        assert "at least 8 characters" in issues

    def test_no_uppercase(self):
        issues = validate_password_strength("lowercase1")
        assert "an uppercase letter" in issues

    def test_no_lowercase(self):
        issues = validate_password_strength("UPPERCASE1")
        assert "a lowercase letter" in issues

    def test_no_digit(self):
        issues = validate_password_strength("NoDigitHere!")
        assert "a digit" in issues

    def test_weak_password_multiple_issues(self):
        issues = validate_password_strength("short")
        assert len(issues) >= 3

    def test_accepts_long_complex(self):
        assert validate_password_strength("MyC0mpl3x!P@ssw0rd") == []


# ═══════════════════════════════════════════════════════════════════
# STEP 12.2 – Password Hashing
# ═══════════════════════════════════════════════════════════════════


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "SecureP@ss1"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("SecureP@ss1")
        assert not verify_password("WrongP@ss1", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("SecureP@ss1")
        h2 = hash_password("SecureP@ss1")
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════════
# STEP 12.3 – JWT Claims & Payload
# ═══════════════════════════════════════════════════════════════════


class TestJWTClaims:
    def test_access_token_contains_roles(self):
        token = create_access_token("user-123", ["admin", "hr"])
        payload = decode_token(token)
        assert "admin" in payload["roles"]
        assert "hr" in payload["roles"]
        assert payload["type"] == "access"

    def test_access_token_contains_email_and_name(self):
        token = create_access_token(
            "user-123", ["candidate"], email="test@example.com", full_name="Test User",
        )
        payload = decode_token(token)
        assert payload["email"] == "test@example.com"
        assert payload["full_name"] == "Test User"

    def test_access_token_has_token_id(self):
        token = create_access_token("user-123", ["candidate"])
        payload = decode_token(token)
        assert "token_id" in payload
        assert len(payload["token_id"]) > 0

    def test_refresh_token_has_type(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-123"

    def test_refresh_token_has_token_id(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert "token_id" in payload

    def test_refresh_token_remember_me_extends_expiry(self):
        token_normal = create_refresh_token("user-123", remember_me=False)
        token_remember = create_refresh_token("user-123", remember_me=True)
        p_normal = decode_token(token_normal)
        p_remember = decode_token(token_remember)
        assert p_remember["exp"] > p_normal["exp"]

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError):
            decode_token("invalid.token.value")


# ═══════════════════════════════════════════════════════════════════
# STEP 12.4 – Registration (API)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_returns_user_with_role(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Reg Test",
            "email": "reg_test@example.com",
            "password": "SecureP@ss1",
            "role": "candidate",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "reg_test@example.com"
    assert "candidate" in data["roles"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_recruiter_forced_to_candidate(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Recruiter",
            "email": "rec_reg_auth@example.com",
            "password": "SecureP@ss1",
            "role": "recruiter",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_hr_forced_to_candidate(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "HR Person",
            "email": "hr_reg_auth@example.com",
            "password": "SecureP@ss1",
            "role": "hr",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_default_role_is_candidate(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Default Role",
            "email": "default_role@example.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_admin_forced_to_candidate(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake Admin",
            "email": "fake_admin_auth@example.com",
            "password": "SecureP@ss1",
            "role": "admin",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_duplicate_email_409(client: AsyncClient, auth_service):
    await auth_service.register("Dupe", "dupe_auth@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dupe",
            "email": "dupe_auth@example.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_register_weak_password_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Weak PW",
            "email": "weak_pw@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_uppercase_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "No Upper",
            "email": "no_upper@example.com",
            "password": "lowercase1",
        },
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# STEP 12.5 – Login (API)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_returns_tokens(client: AsyncClient, auth_service):
    await auth_service.register("Login Test", "login_test@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_test@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, auth_service):
    await auth_service.register("Wrong PW", "wrong_pw@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong_pw@example.com", "password": "WrongP@ss1"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_login_contains_roles_in_jwt(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("JWT Roles", "jwt_roles@example.com", "SecureP@ss1", "recruiter")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "jwt_roles@example.com", "password": "SecureP@ss1"},
    )
    payload = decode_token(resp.json()["access_token"])
    assert "recruiter" in payload["roles"]
    assert payload["email"] == "jwt_roles@example.com"
    assert payload["full_name"] == "JWT Roles"


@pytest.mark.asyncio
async def test_login_remember_me(client: AsyncClient, auth_service):
    await auth_service.register("Remember Me", "remember_me@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "remember_me@example.com", "password": "SecureP@ss1", "remember_me": True},
    )
    assert resp.status_code == 200
    refresh_payload = decode_token(resp.json()["refresh_token"])
    normal_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "remember_me@example.com", "password": "SecureP@ss1", "remember_me": False},
    )
    normal_payload = decode_token(normal_resp.json()["refresh_token"])
    assert refresh_payload["exp"] > normal_payload["exp"]


# ═══════════════════════════════════════════════════════════════════
# STEP 12.6 – Refresh Token Lifecycle
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient, auth_service):
    await auth_service.register("Refresh", "refresh_test@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_test@example.com", "password": "SecureP@ss1"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["access_token"] != login_resp.json()["access_token"]


@pytest.mark.asyncio
async def test_refresh_invalid_token_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_revokes_old_token(client: AsyncClient, auth_service):
    await auth_service.register("Revoke", "revoke_test@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "revoke_test@example.com", "password": "SecureP@ss1"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    resp1 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp1.status_code == 200
    resp2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(client: AsyncClient, auth_service):
    await auth_service.register("Wrong Type", "wrong_type@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong_type@example.com", "password": "SecureP@ss1"},
    )
    access_token = login_resp.json()["access_token"]
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# STEP 12.7 – Current User API
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_me_returns_user_with_roles(client: AsyncClient, auth_service):
    await auth_service.register("Me Test", "me_auth@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "me_auth@example.com", "password": "SecureP@ss1"},
    )
    token = login_resp.json()["access_token"]
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me_auth@example.com"
    assert "candidate" in data["roles"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_me_invalid_token_401(client: AsyncClient):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_refresh_token_rejected(client: AsyncClient, auth_service):
    await auth_service.register("Refresh Me", "refresh_me@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_me@example.com", "password": "SecureP@ss1"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# STEP 12.8 – Logout
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, auth_service):
    await auth_service.register("Logout", "logout_auth@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout_auth@example.com", "password": "SecureP@ss1"},
    )
    token = login_resp.json()["access_token"]
    refresh = login_resp.json()["refresh_token"]
    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient, auth_service):
    await auth_service.register("Logout Revoke", "logout_revoke@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout_revoke@example.com", "password": "SecureP@ss1"},
    )
    token = login_resp.json()["access_token"]
    refresh = login_resp.json()["refresh_token"]
    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code in (401, 422)


# ═══════════════════════════════════════════════════════════════════
# STEP 12.9 – Roles API
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_roles_endpoint_returns_all_roles(client: AsyncClient):
    resp = await client.get("/api/v1/auth/roles")
    assert resp.status_code == 200
    data = resp.json()
    names = {r["name"] for r in data}
    assert {"admin", "hr", "recruiter", "candidate"}.issubset(names)


# ═══════════════════════════════════════════════════════════════════
# STEP 12.10 – Session Persistence (end-to-end)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_session_lifecycle(client: AsyncClient, auth_service):
    """Simulate: register -> login -> access -> refresh -> access -> logout -> refresh fails."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Lifecycle",
            "email": "lifecycle@example.com",
            "password": "SecureP@ss1",
            "role": "candidate",
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "lifecycle@example.com", "password": "SecureP@ss1"},
    )
    assert login.status_code == 200
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "lifecycle@example.com"

    ref = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert ref.status_code == 200
    new_access = ref.json()["access_token"]
    new_refresh = ref.json()["refresh_token"]

    me2 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me2.status_code == 200

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh},
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert logout.status_code == 200

    old_refresh_fail = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert old_refresh_fail.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# STEP 12.11 – Error Message Quality
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_error_message_not_generic(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401
    detail = resp.json()["error"]["message"]
    assert "500" not in detail
    assert "Internal" not in detail


@pytest.mark.asyncio
async def test_register_error_message_for_duplicate(client: AsyncClient, auth_service):
    await auth_service.register("Dupe Msg", "dupe_msg@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dupe Msg",
            "email": "dupe_msg@example.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_register_weak_password_error_includes_requirements(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Weak",
            "email": "weak_msg@example.com",
            "password": "alllowercase",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    msg = body["error"].get("message", "")
    assert "Password" in msg or "password" in msg


# ═══════════════════════════════════════════════════════════════════
# STEP 12.12 – Authorization Middleware
# ═══════════════════════════════════════════════════════════════════


async def _login(client, email, password):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_candidate_cannot_access_admin_dashboard(client: AsyncClient, auth_service):
    await auth_service.register("Cand NoAdmin 2", "cand_na2@example.com", "SecureP@ss1")
    token = await _login(client, "cand_na2@example.com", "SecureP@ss1")
    resp = await client.get("/api/v1/dashboard/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recruiter_cannot_access_candidate_dashboard(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("Rec NoCand", "rec_nc_auth@example.com", "SecureP@ss1", "recruiter")
    token = await _login(client, "rec_nc_auth@example.com", "SecureP@ss1")
    resp = await client.get("/api/v1/dashboard/candidate", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_hr_can_access_recruiter_dashboard(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("HR Rec 2", "hr_rec2_auth@example.com", "SecureP@ss1", "hr")
    token = await _login(client, "hr_rec2_auth@example.com", "SecureP@ss1")
    resp = await client.get("/api/v1/dashboard/recruiter", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_any_dashboard(client: AsyncClient):
    for path in ["/api/v1/dashboard/candidate", "/api/v1/dashboard/recruiter", "/api/v1/dashboard/hr", "/api/v1/dashboard/admin"]:
        resp = await client.get(path)
        assert resp.status_code in (401, 422), f"{path} should require auth"


# ═══════════════════════════════════════════════════════════════════
# STEP 12.13 – Login Response includes User Info
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_returns_user_info(client: AsyncClient, auth_service):
    await auth_service.register("UserInfo Test", "userinfo_test@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "userinfo_test@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "user" in data
    user = data["user"]
    assert user["email"] == "userinfo_test@example.com"
    assert user["full_name"] == "UserInfo Test"
    assert "candidate" in user["roles"]
    assert user["is_active"] is True
    assert "id" in user
    assert "created_at" in user
    assert "updated_at" in user


@pytest.mark.asyncio
async def test_login_recruiter_returns_recruiter_roles(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("Rec Login", "rec_login_auth@example.com", "SecureP@ss1", "recruiter")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "rec_login_auth@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    user = data["user"]
    assert "recruiter" in user["roles"]
    assert user["email"] == "rec_login_auth@example.com"


@pytest.mark.asyncio
async def test_login_hr_returns_hr_roles(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("HR Login", "hr_login_auth@example.com", "SecureP@ss1", "hr")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "hr_login_auth@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    user = data["user"]
    assert "hr" in user["roles"]


@pytest.mark.asyncio
async def test_refresh_returns_user_info(client: AsyncClient, auth_service):
    await auth_service.register("Refresh Info", "refresh_info@example.com", "SecureP@ss1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_info@example.com", "password": "SecureP@ss1"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "user" in data
    user = data["user"]
    assert user["email"] == "refresh_info@example.com"
    assert "candidate" in user["roles"]


@pytest.mark.asyncio
async def test_admin_login_returns_admin_roles(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("Admin Login", "admin_login@example.com", "SecureP@ss1", "admin")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin_login@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    user = data["user"]
    assert "admin" in user["roles"]
