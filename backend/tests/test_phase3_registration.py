"""Phase 3 – Candidate Self-Registration security and behavior tests.

Covers:
- Email normalization (case-insensitive, whitespace trimming)
- Mass assignment protection (role, organization_id, is_admin, permissions, etc.)
- Candidate-only enforcement
- Password never leaked in responses
- Account status for new registrations
- Backward compatibility with existing auth flows
"""

import pytest
from httpx import AsyncClient

from app.core.security import decode_token, hash_password, verify_password
from app.domain.models import Role, User, UserRole
from app.domain.schemas import RegisterRequest, LoginRequest
from app.services.auth import AuthService


# ═══════════════════════════════════════════════════════════════════
# 1. Schema-Level Email Normalization
# ═══════════════════════════════════════════════════════════════════


class TestSchemaEmailNormalization:
    def test_register_request_lowercases_email(self):
        req = RegisterRequest(full_name="Test User", email="Test@Example.COM", password="SecureP@ss1")
        assert req.email == "test@example.com"

    def test_register_request_strips_whitespace_from_email(self):
        req = RegisterRequest(full_name="Test User", email="  test@example.com  ", password="SecureP@ss1")
        assert req.email == "test@example.com"

    def test_register_request_strips_whitespace_from_full_name(self):
        req = RegisterRequest(full_name="  Test User  ", email="test@example.com", password="SecureP@ss1")
        assert req.full_name == "Test User"

    def test_register_request_combined_normalize(self):
        req = RegisterRequest(full_name="  John Doe  ", email="  John@DOE.com  ", password="SecureP@ss1")
        assert req.email == "john@doe.com"
        assert req.full_name == "John Doe"

    def test_login_request_lowercases_email(self):
        req = LoginRequest(email="Test@Example.COM", password="pass1234")
        assert req.email == "test@example.com"

    def test_login_request_strips_whitespace(self):
        req = LoginRequest(email="  test@example.com  ", password="pass1234")
        assert req.email == "test@example.com"

    def test_already_lowercase_email_unchanged(self):
        req = RegisterRequest(full_name="User", email="user@example.com", password="SecureP@ss1")
        assert req.email == "user@example.com"


# ═══════════════════════════════════════════════════════════════════
# 2. Email Normalization in Registration (API)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_normalizes_email_to_lowercase(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Case Test", "email": "CaseTest@Example.COM", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "casetest@example.com"


@pytest.mark.asyncio
async def test_register_strips_whitespace_from_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Space Test", "email": "  space_test@example.com  ", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "space_test@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email_case_insensitive(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Dupe1", "dupe_ci@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Dupe2", "email": "DUPE_CI@EXAMPLE.COM", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_register_duplicate_email_whitespace_insensitive(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Space1", "space_dup@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Space2", "email": "  space_dup@example.com  ", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════════════
# 3. Email Normalization in Login (API)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_with_uppercase_email(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Login Norm", "login_norm@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN_NORM@EXAMPLE.COM", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_with_whitespace_email(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Login WS", "login_ws@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "  login_ws@example.com  ", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_case_insensitive_wrong_password_still_401(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Login Fail CI", "login_fail_ci@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN_FAIL_CI@EXAMPLE.COM", "password": "WrongP@ss1"},
    )
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# 4. Mass Assignment Protection
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_role_field_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MA Test",
            "email": "ma_role@example.com",
            "password": "SecureP@ss1",
            "role": "admin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "candidate" in data["roles"]
    assert "admin" not in data["roles"]


@pytest.mark.asyncio
async def test_register_organization_id_ignored(client: AsyncClient):
    import uuid
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MA Org",
            "email": "ma_org@example.com",
            "password": "SecureP@ss1",
            "organization_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "candidate" in data["roles"]


@pytest.mark.asyncio
async def test_register_is_admin_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MA Admin",
            "email": "ma_admin@example.com",
            "password": "SecureP@ss1",
            "is_admin": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "candidate" in data["roles"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_permissions_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MA Perms",
            "email": "ma_perms@example.com",
            "password": "SecureP@ss1",
            "permissions": ["admin:all"],
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_is_superuser_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MA Super",
            "email": "ma_super@example.com",
            "password": "SecureP@ss1",
            "is_superuser": True,
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_is_staff_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MA Staff",
            "email": "ma_staff@example.com",
            "password": "SecureP@ss1",
            "is_staff": True,
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_super_admin_role_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake SuperAdmin",
            "email": "ma_superadmin@example.com",
            "password": "SecureP@ss1",
            "role": "super_admin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "candidate" in data["roles"]
    assert "super_admin" not in data["roles"]


@pytest.mark.asyncio
async def test_register_organization_admin_role_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake OrgAdmin",
            "email": "ma_orgadmin@example.com",
            "password": "SecureP@ss1",
            "role": "organization_admin",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_register_hr_manager_role_ignored(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Fake HRManager",
            "email": "ma_hrmanager@example.com",
            "password": "SecureP@ss1",
            "role": "hr_manager",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


# ═══════════════════════════════════════════════════════════════════
# 5. Candidate-Only Enforcement
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_always_assigns_candidate_role(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Always Cand", "email": "always_cand@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert resp.json()["roles"] == ["candidate"]


@pytest.mark.asyncio
async def test_register_no_role_field_also_candidate(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Role", "email": "no_role_field@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


# ═══════════════════════════════════════════════════════════════════
# 6. Password Never Leaked in Responses
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_response_no_password_hash(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "PW Leak", "email": "pw_leak@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_login_response_no_password_hash(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Login PW", "login_pw@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_pw@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "password" not in data
    assert "password_hash" not in data
    if "user" in data and data["user"]:
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]


@pytest.mark.asyncio
async def test_me_response_no_password_hash(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Me PW", "me_pw@example.com", "SecureP@ss1")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "me_pw@example.com", "password": "SecureP@ss1"},
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "password" not in data
    assert "password_hash" not in data


# ═══════════════════════════════════════════════════════════════════
# 7. Account Status for New Registrations
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_new_account_is_active(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Active Test", "email": "active_test@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_new_account_is_not_verified(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Verify Test", "email": "verify_test@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert resp.json()["is_verified"] is False


# ═══════════════════════════════════════════════════════════════════
# 8. Password Validation
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_weak_password_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Weak", "email": "weak_p3@example.com", "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_no_uppercase_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Upper", "email": "no_upper3@example.com", "password": "lowercase1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_no_digit_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Digit", "email": "no_digit3@example.com", "password": "NoDigitHere!"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_empty_password_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Empty PW", "email": "empty_pw3@example.com", "password": ""},
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 9. Backward Compatibility – Existing Auth Flows
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_auth_flow_after_email_normalization(client: AsyncClient, auth_service: AuthService):
    """Register → login → me → refresh → me → logout — all with normalized emails."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Flow Norm", "email": "  FlowNorm@Test.COM  ", "password": "SecureP@ss1"},
    )
    assert reg.status_code == 201
    assert reg.json()["email"] == "flownorm@test.com"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": " flownorm@test.com ", "password": "SecureP@ss1"},
    )
    assert login.status_code == 200
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "flownorm@test.com"

    ref = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert ref.status_code == 200

    me2 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {ref.json()['access_token']}"},
    )
    assert me2.status_code == 200

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": ref.json()["refresh_token"]},
        headers={"Authorization": f"Bearer {ref.json()['access_token']}"},
    )
    assert logout.status_code == 200


@pytest.mark.asyncio
async def test_existing_user_login_unchanged(client: AsyncClient, _create_user_with_role):
    """Existing non-normalized email user can still log in."""
    await _create_user_with_role("Existing User", "existing_user@example.com", "SecureP@ss1", "recruiter")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "existing_user@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    payload = decode_token(resp.json()["access_token"])
    assert "recruiter" in payload["roles"]


@pytest.mark.asyncio
async def test_existing_user_login_with_uppercase(client: AsyncClient, _create_user_with_role):
    """Existing user can log in with uppercase email variant."""
    await _create_user_with_role("Upper Login", "upper_login@example.com", "SecureP@ss1", "hr")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "UPPER_LOGIN@EXAMPLE.COM", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_candidate_dashboard_still_works(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Dash Test", "dash_test@example.com", "SecureP@ss1")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dash_test@example.com", "password": "SecureP@ss1"},
    )
    token = login.json()["access_token"]
    resp = await client.get(
        "/api/v1/dashboard/candidate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 10. Input Validation
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_invalid_email_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Bad Email", "email": "not-an-email", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_empty_full_name_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "", "email": "empty_name@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_fields_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_full_name_too_long_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "A" * 256,
            "email": "long_name@example.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 11. Error Message Quality
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_duplicate_email_error_message(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Err Test", "err_dup@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Err Test 2", "email": "err_dup@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_login_invalid_credentials_error_message(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost3@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["error"]["message"]


# ═══════════════════════════════════════════════════════════════════
# 12. Response Format
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_response_has_required_fields(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Format Test", "email": "format_test@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "full_name" in data
    assert "email" in data
    assert "is_active" in data
    assert "is_verified" in data
    assert "roles" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_login_response_has_user_info(client: AsyncClient, auth_service: AuthService):
    await auth_service.register("Login Format", "login_format@example.com", "SecureP@ss1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_format@example.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    user = data["user"]
    assert "id" in user
    assert "email" in user
    assert "roles" in user
    assert "candidate" in user["roles"]
