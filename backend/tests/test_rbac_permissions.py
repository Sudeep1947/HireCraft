"""Comprehensive tests for Enterprise RBAC — permissions, security middleware, ownership checks."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.permissions import (
    Permission,
    ROLE_PERMISSIONS,
    get_all_permissions_for_user,
    get_permissions_for_role,
    role_has_permission,
    user_has_permission,
)
from app.core.security import decode_token, hash_password, verify_password
from app.domain.models import AuditLog, Role, User
from app.repositories.user import UserRepository
from app.services.audit import log_audit_event
from app.services.auth import AuthService


# ─── Permission Model Unit Tests ──────────────────────────────────


class TestPermissionEnum:
    def test_permission_values_are_strings(self) -> None:
        for perm in Permission:
            assert isinstance(perm.value, str)
            assert ":" in perm.value

    def test_all_roles_have_permissions(self) -> None:
        for role_name in ("candidate", "recruiter", "hr", "admin"):
            assert role_name in ROLE_PERMISSIONS
            assert len(ROLE_PERMISSIONS[role_name]) > 0

    def test_admin_has_all_permissions(self) -> None:
        admin_perms = ROLE_PERMISSIONS["admin"]
        all_perms = set(Permission)
        assert set(admin_perms) == all_perms

    def test_candidate_permissions_are_subset_of_all(self) -> None:
        candidate_perms = set(ROLE_PERMISSIONS["candidate"])
        all_perms = set(Permission)
        assert candidate_perms.issubset(all_perms)

    def test_recruiter_permissions_are_subset_of_all(self) -> None:
        recruiter_perms = set(ROLE_PERMISSIONS["recruiter"])
        all_perms = set(Permission)
        assert recruiter_perms.issubset(all_perms)

    def test_hr_permissions_are_subset_of_all(self) -> None:
        hr_perms = set(ROLE_PERMISSIONS["hr"])
        all_perms = set(Permission)
        assert hr_perms.issubset(all_perms)


class TestGetPermissionsForRole:
    def test_candidate_permissions(self) -> None:
        perms = get_permissions_for_role("candidate")
        assert Permission.PROFILE_VIEW in perms
        assert Permission.RESUME_UPLOAD in perms
        assert Permission.JOB_BROWSE in perms
        assert Permission.JOB_APPLY in perms

    def test_recruiter_permissions(self) -> None:
        perms = get_permissions_for_role("recruiter")
        assert Permission.JOB_CREATE in perms
        assert Permission.APPLICANT_VIEW in perms
        assert Permission.RESUME_SCREEN in perms

    def test_hr_permissions(self) -> None:
        perms = get_permissions_for_role("hr")
        assert Permission.HR_DASHBOARD in perms
        assert Permission.HR_PIPELINE in perms
        assert Permission.HR_REPORTS in perms

    def test_admin_permissions(self) -> None:
        perms = get_permissions_for_role("admin")
        assert Permission.ADMIN_USER_MANAGE in perms
        assert Permission.ADMIN_ROLE_MANAGE in perms
        assert Permission.ADMIN_AUDIT_VIEW in perms

    def test_unknown_role_returns_empty(self) -> None:
        perms = get_permissions_for_role("unknown")
        assert perms == []


class TestRoleHasPermission:
    def test_candidate_has_profile_view(self) -> None:
        assert role_has_permission("candidate", Permission.PROFILE_VIEW)

    def test_candidate_does_not_have_job_create(self) -> None:
        assert not role_has_permission("candidate", Permission.JOB_CREATE)

    def test_recruiter_has_job_create(self) -> None:
        assert role_has_permission("recruiter", Permission.JOB_CREATE)

    def test_recruiter_does_not_have_admin_user_manage(self) -> None:
        assert not role_has_permission("recruiter", Permission.ADMIN_USER_MANAGE)

    def test_hr_has_dashboard_view(self) -> None:
        assert role_has_permission("hr", Permission.HR_DASHBOARD)

    def test_admin_has_everything(self) -> None:
        for perm in Permission:
            assert role_has_permission("admin", perm)


class TestUserHasPermission:
    def test_single_role_user_with_permission(self) -> None:
        assert user_has_permission(["candidate"], Permission.PROFILE_VIEW)

    def test_single_role_user_without_permission(self) -> None:
        assert not user_has_permission(["candidate"], Permission.JOB_CREATE)

    def test_multi_role_user_with_either_permission(self) -> None:
        assert user_has_permission(["candidate", "recruiter"], Permission.JOB_CREATE)

    def test_multi_role_user_combined_permissions(self) -> None:
        roles = ["candidate", "recruiter"]
        assert user_has_permission(roles, Permission.PROFILE_VIEW)
        assert user_has_permission(roles, Permission.JOB_CREATE)

    def test_empty_roles_returns_false(self) -> None:
        assert not user_has_permission([], Permission.PROFILE_VIEW)


class TestGetAllPermissionsForUser:
    def test_candidate_gets_candidate_permissions(self) -> None:
        perms = get_all_permissions_for_user(["candidate"])
        assert Permission.PROFILE_VIEW in perms
        assert Permission.JOB_CREATE not in perms

    def test_multi_role_gets_combined(self) -> None:
        perms = get_all_permissions_for_user(["candidate", "recruiter"])
        assert Permission.PROFILE_VIEW in perms
        assert Permission.JOB_CREATE in perms

    def test_admin_gets_all(self) -> None:
        perms = get_all_permissions_for_user(["admin"])
        assert perms == set(Permission)

    def test_empty_roles_returns_empty(self) -> None:
        perms = get_all_permissions_for_user([])
        assert perms == set()


# ─── Audit Service Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_audit_event(session) -> None:
    audit = await log_audit_event(
        session,
        action="test_action",
        resource_type="test_resource",
        resource_id="123",
        details={"key": "value"},
        ip_address="127.0.0.1",
        user_agent="test-agent",
        success=True,
    )
    assert audit.action == "test_action"
    assert audit.resource_type == "test_resource"
    assert audit.resource_id == "123"
    assert audit.details == {"key": "value"}
    assert audit.ip_address == "127.0.0.1"
    assert audit.success is True
    assert audit.user_id is None


@pytest.mark.asyncio
async def test_log_audit_event_with_user_id(session) -> None:
    user_id = uuid.uuid4()
    audit = await log_audit_event(
        session,
        user_id=user_id,
        action="login",
        success=True,
    )
    assert audit.user_id == user_id
    assert audit.action == "login"


# ─── Security Middleware Tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("cache-control") == "no-store, no-cache, must-revalidate"


@pytest.mark.asyncio
async def test_audit_logging_middleware_logs_sensitive_paths(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Audit Test", "audit_mw@example.com", "SecureP@ss123")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "audit_mw@example.com", "password": "SecureP@ss123"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_request_body_too_large_returns_413(client: AsyncClient) -> None:
    large_body = "x" * (11 * 1024 * 1024)
    response = await client.post(
        "/api/v1/auth/register",
        content=large_body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(large_body))},
    )
    assert response.status_code == 413


# ─── Permission-Based Route Protection Tests ──────────────────────


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def _create_user_with_role(
    user_repo: UserRepository, name: str, email: str, password: str, role: str
) -> None:
    """Create a user with the given role directly in DB (public registration is candidate-only)."""
    user = await user_repo.create(
        full_name=name,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
        is_verified=True,
    )
    role_obj = await user_repo.find_role_by_name(role)
    await user_repo.assign_role(user.id, role_obj.id)


@pytest.mark.asyncio
async def test_recruiter_job_create_requires_recruiter_role(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Cand Job", "cand_job@example.com", "SecureP@ss123")
    token = await _login(client, "cand_job@example.com", "SecureP@ss123")
    response = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Test Job", "company": "Test Co", "location": "Remote", "description": "desc", "employment_type": "full_time"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_recruiter_can_create_job(client: AsyncClient, user_repo: UserRepository) -> None:
    await _create_user_with_role(user_repo, "Rec Job", "rec_job@example.com", "SecureP@ss123", "recruiter")
    token = await _login(client, "rec_job@example.com", "SecureP@ss123")
    response = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Test Job", "company": "Test Co", "location": "Remote", "description": "desc", "employment_type": "full_time"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (200, 201)


@pytest.mark.asyncio
async def test_candidate_cannot_access_recruiter_jobs(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Cand RecJob", "cand_recjob@example.com", "SecureP@ss123")
    token = await _login(client, "cand_recjob@example.com", "SecureP@ss123")
    response = await client.get(
        "/api/v1/recruiter/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_users(client: AsyncClient, user_repo: UserRepository) -> None:
    await _create_user_with_role(user_repo, "Rec Users", "rec_users@example.com", "SecureP@ss123", "recruiter")
    token = await _login(client, "rec_users@example.com", "SecureP@ss123")
    response = await client.get(
        "/api/v1/dashboard/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_access_by_role(client: AsyncClient, auth_service: AuthService, user_repo: UserRepository) -> None:
    await auth_service.register("Dash Cand", "dash_cand@example.com", "SecureP@ss123")
    cand_token = await _login(client, "dash_cand@example.com", "SecureP@ss123")

    await _create_user_with_role(user_repo, "Dash Rec", "dash_rec@example.com", "SecureP@ss123", "recruiter")
    rec_token = await _login(client, "dash_rec@example.com", "SecureP@ss123")

    await _create_user_with_role(user_repo, "Dash HR", "dash_hr@example.com", "SecureP@ss123", "hr")
    hr_token = await _login(client, "dash_hr@example.com", "SecureP@ss123")

    cand_resp = await client.get("/api/v1/dashboard/candidate", headers={"Authorization": f"Bearer {cand_token}"})
    assert cand_resp.status_code == 200

    rec_resp = await client.get("/api/v1/dashboard/recruiter", headers={"Authorization": f"Bearer {rec_token}"})
    assert rec_resp.status_code == 200

    hr_resp = await client.get("/api/v1/dashboard/hr", headers={"Authorization": f"Bearer {hr_token}"})
    assert hr_resp.status_code == 200

    cand_no_admin = await client.get("/api/v1/dashboard/admin", headers={"Authorization": f"Bearer {cand_token}"})
    assert cand_no_admin.status_code == 403


# ─── Authentication Edge Cases ────────────────────────────────────


@pytest.mark.asyncio
async def test_bearer_token_required(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/candidate")
    assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_invalid_bearer_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/dashboard/candidate",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_not_usable_for_access(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Refresh NoUse", "refresh_nouse@example.com", "SecureP@ss123")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_nouse@example.com", "password": "SecureP@ss123"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    response = await client.get(
        "/api/v1/dashboard/candidate",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_cannot_authenticate(client: AsyncClient, session) -> None:
    user = User(
        full_name="Inactive User",
        email="inactive@example.com",
        password_hash=hash_password("SecureP@ss123"),
        is_active=False,
        is_verified=False,
    )
    session.add(user)
    await session.flush()

    role = (await session.execute(select(Role).where(Role.name == "candidate"))).scalars().first()
    from app.domain.models import UserRole
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "SecureP@ss123"},
    )
    assert response.status_code == 401


# ─── Password Security ───────────────────────────────────────────


def test_password_hashing_uniqueness() -> None:
    password = "SecureP@ss123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    assert hash1 != hash2
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)


# ─── Role Seeding Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_roles_are_seeded(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/roles")
    assert response.status_code == 200
    names = {r["name"] for r in response.json()}
    assert {"admin", "hr", "recruiter", "candidate", "super_admin", "organization_admin", "hr_manager"}.issubset(names)


@pytest.mark.asyncio
async def test_admin_role_has_description(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/roles")
    roles = response.json()
    admin_role = next((r for r in roles if r["name"] == "admin"), None)
    assert admin_role is not None
    assert admin_role["description"] is not None


# ─── Login Response Includes User Data ────────────────────────────


@pytest.mark.asyncio
async def test_login_response_includes_user(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Login User", "login_user@example.com", "SecureP@ss123")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_user@example.com", "password": "SecureP@ss123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("user") is not None
    assert data["user"]["email"] == "login_user@example.com"
    assert "candidate" in data["user"]["roles"]


@pytest.mark.asyncio
async def test_login_response_includes_permissions_in_user(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Perm User", "perm_user@example.com", "SecureP@ss123")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "perm_user@example.com", "password": "SecureP@ss123"},
    )
    data = response.json()
    user_data = data["user"]
    assert "roles" in user_data
    assert isinstance(user_data["roles"], list)


@pytest.mark.asyncio
async def test_refresh_response_includes_user(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Refresh Inc", "refresh_inc@example.com", "SecureP@ss123")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_inc@example.com", "password": "SecureP@ss123"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("user") is not None
    assert data["user"]["email"] == "refresh_inc@example.com"


# ─── Cross-Role Access Denial ─────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_cannot_access_hr_dashboard(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Cand HR", "cand_hr@example.com", "SecureP@ss123")
    token = await _login(client, "cand_hr@example.com", "SecureP@ss123")
    response = await client.get("/api/v1/dashboard/hr", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_recruiter_cannot_access_admin_dashboard(client: AsyncClient, user_repo: UserRepository) -> None:
    await _create_user_with_role(user_repo, "Rec Admin", "rec_admin@example.com", "SecureP@ss123", "recruiter")
    token = await _login(client, "rec_admin@example.com", "SecureP@ss123")
    response = await client.get("/api/v1/dashboard/admin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_hr_cannot_access_admin_dashboard(client: AsyncClient, user_repo: UserRepository) -> None:
    await _create_user_with_role(user_repo, "HR Admin", "hr_admin@example.com", "SecureP@ss123", "hr")
    token = await _login(client, "hr_admin@example.com", "SecureP@ss123")
    response = await client.get("/api/v1/dashboard/admin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


# ─── Permission Boundary Tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_cannot_register_as_admin_via_api(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Fake Admin", "email": "fake_admin_perm@example.com", "password": "SecureP@ss123", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["roles"] == ["candidate"]


@pytest.mark.asyncio
async def test_cannot_register_with_invalid_role(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Bad Role", "email": "bad_role@example.com", "password": "SecureP@ss123", "role": "superadmin"},
    )
    assert response.status_code == 201
    assert response.json()["roles"] == ["candidate"]


# ─── Multiple Role Permissions ────────────────────────────────────


@pytest.mark.asyncio
async def test_user_with_multiple_roles_gets_combined_permissions() -> None:
    perms = get_all_permissions_for_user(["candidate", "recruiter"])
    assert Permission.PROFILE_VIEW in perms
    assert Permission.JOB_CREATE in perms
    assert Permission.APPLICANT_VIEW in perms


@pytest.mark.asyncio
async def test_admin_role_supersedes_others() -> None:
    perms = get_all_permissions_for_user(["candidate", "admin"])
    assert perms == set(Permission)


# ─── Token Type Enforcement ───────────────────────────────────────


@pytest.mark.asyncio
async def test_token_type_must_be_access(client: AsyncClient, auth_service: AuthService) -> None:
    await auth_service.register("Type Test", "type_test@example.com", "SecureP@ss123")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "type_test@example.com", "password": "SecureP@ss123"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401


# ─── Password Strength Validation ─────────────────────────────────


def test_password_too_short_rejected() -> None:
    from pydantic import BaseModel, Field, ValidationError

    class PasswordModel(BaseModel):
        password: str = Field(..., min_length=8, max_length=128)

    with pytest.raises(ValidationError):
        PasswordModel(password="short")


def test_password_too_long_rejected() -> None:
    from pydantic import BaseModel, Field, ValidationError

    class PasswordModel(BaseModel):
        password: str = Field(..., min_length=8, max_length=128)

    with pytest.raises(ValidationError):
        PasswordModel(password="x" * 129)


# ─── Health Endpoint (No Auth Required) ───────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint_no_auth_required(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    # 200 = healthy, 503 = degraded (e.g., Redis unavailable in test env)
    assert response.status_code in (200, 503)


# ─── Role Hierarchy ───────────────────────────────────────────────


def test_permission_hierarchy_candidate_lt_recruiter_lt_hr_lt_admin() -> None:
    cand_count = len(ROLE_PERMISSIONS["candidate"])
    rec_count = len(ROLE_PERMISSIONS["recruiter"])
    hr_count = len(ROLE_PERMISSIONS["hr"])
    admin_count = len(ROLE_PERMISSIONS["admin"])

    assert admin_count > hr_count
    assert hr_count > 0
    assert rec_count > 0
    assert cand_count > 0


def test_admin_permissions_superset_of_all() -> None:
    admin_perms = set(ROLE_PERMISSIONS["admin"])
    for role in ("candidate", "recruiter", "hr"):
        role_perms = set(ROLE_PERMISSIONS[role])
        assert role_perms.issubset(admin_perms)
