"""Phase 1 – Secure organization creation.

Organization creation is a platform-administration operation. These tests pin
down the authorization boundary, input normalization/validation, duplicate
handling, creator membership integrity, audit trail, and tenant isolation.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import AccountStatus, AuditEventType, MembershipStatus, RoleName
from app.domain.models import AuditLog, Organization, OrganizationMembership
from app.repositories.membership import OrganizationMembershipRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository

PASSWORD = "SecureP@ss1"


async def _create_user_with_role(session: AsyncSession, email: str, role_name: str):
    repo = UserRepository(session)
    user = await repo.create(
        full_name=f"User {email.split('@')[0]}",
        email=email,
        password_hash=hash_password(PASSWORD),
        is_active=True,
        is_verified=True,
        account_status=AccountStatus.ACTIVE.value,
    )
    role = await repo.find_role_by_name(role_name)
    if role:
        await repo.assign_role(user.id, role.id)
    return user


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_org(
    client: AsyncClient,
    token: str,
    payload: dict,
    *,
    request_id: str | None = None,
):
    headers = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["X-Request-ID"] = request_id
        headers["User-Agent"] = "pytest-agent"
    return await client.post("/api/v1/organizations", json=payload, headers=headers)


# ── Authorization matrix ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_super_admin_can_create_organization(
    client: AsyncClient, session: AsyncSession
):
    user = await _create_user_with_role(session, "super_creator@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "super_creator@test.com")

    resp = await _create_org(
        client,
        token,
        {"name": "Secure Corp", "slug": "secure-corp"},
        request_id="req-secure-org-1",
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["slug"] == "secure-corp"
    assert data["status"] == "active"

    membership_repo = OrganizationMembershipRepository(session)
    membership = await membership_repo.get_active_membership(
        user.id, uuid.UUID(data["id"])
    )
    assert membership is not None
    assert membership.role == RoleName.ORG_ADMIN.value
    assert membership.status == MembershipStatus.ACTIVE.value

    # The creator keeps their platform role; membership never grants one.
    assert {ur.role.name for ur in user.roles} == {"super_admin"}


@pytest.mark.asyncio
async def test_legacy_platform_admin_can_create_organization(
    client: AsyncClient, session: AsyncSession
):
    """Legacy ``admin`` is a platform-admin alias in the existing RBAC model."""
    await _create_user_with_role(session, "legacy_admin@test.com", "admin")
    await session.commit()
    token = await _login(client, "legacy_admin@test.com")

    resp = await _create_org(
        client, token, {"name": "Legacy Corp", "slug": "legacy-corp"}
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name",
    ["organization_admin", "hr_manager", "recruiter", "candidate"],
)
async def test_non_platform_roles_cannot_create_organization(
    client: AsyncClient, session: AsyncSession, role_name: str
):
    user = await _create_user_with_role(
        session, f"denied_{role_name}@test.com", role_name
    )
    if role_name == "organization_admin":
        # Having an org-admin membership somewhere must not confer the ability
        # to create a new tenant.
        existing = Organization(
            name="Existing Tenant", slug=f"existing-{uuid.uuid4().hex[:8]}", status="active"
        )
        session.add(existing)
        await session.flush()
        session.add(
            OrganizationMembership(
                user_id=user.id,
                organization_id=existing.id,
                role=RoleName.ORG_ADMIN.value,
                status=MembershipStatus.ACTIVE.value,
            )
        )
    await session.commit()
    token = await _login(client, f"denied_{role_name}@test.com")

    slug = f"denied-org-{role_name.replace('_', '-')}"
    resp = await _create_org(
        client, token, {"name": "Denied Org", "slug": slug}
    )
    assert resp.status_code == 403, resp.text

    org_repo = OrganizationRepository(session)
    assert await org_repo.get_by_slug(slug) is None


@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_organization(client: AsyncClient):
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Anonymous Org", "slug": "anonymous-org"},
    )
    assert resp.status_code == 401
    assert "request_id" in resp.json()["error"]


# ── Input normalization and validation ─────────────────────────────────


@pytest.mark.asyncio
async def test_name_and_slug_are_trimmed(
    client: AsyncClient, session: AsyncSession
):
    await _create_user_with_role(session, "trim_admin@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "trim_admin@test.com")

    resp = await _create_org(
        client,
        token,
        {"name": "  Trimmed Corp  ", "slug": "  trimmed-corp  "},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Trimmed Corp"
    assert resp.json()["slug"] == "trimmed-corp"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "slug": "empty-name"},
        {"name": "Valid Name", "slug": "   "},
        {"name": "Valid Name", "slug": "Bad-Slug"},
        {"name": "Valid Name", "slug": "bad_slug"},
        {"name": "Valid Name", "slug": "-leading"},
        {"name": "Valid Name", "slug": "trailing-"},
        {"name": "Valid Name", "slug": "double--hyphen"},
        {"name": "Valid Name", "slug": "has space"},
    ],
)
async def test_invalid_name_or_slug_is_rejected(
    client: AsyncClient, session: AsyncSession, payload: dict
):
    email = f"invalid_{uuid.uuid4().hex[:8]}@test.com"
    await _create_user_with_role(session, email, "super_admin")
    await session.commit()
    token = await _login(client, email)

    resp = await _create_org(client, token, payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "protected_field",
    [
        {"id": str(uuid.uuid4())},
        {"status": "suspended"},
        {"role": "super_admin"},
        {"created_by": str(uuid.uuid4())},
        {"user_id": str(uuid.uuid4())},
        {"is_active": False},
    ],
)
async def test_protected_fields_are_rejected(
    client: AsyncClient, session: AsyncSession, protected_field: dict
):
    email = f"mass_{uuid.uuid4().hex[:8]}@test.com"
    await _create_user_with_role(session, email, "super_admin")
    await session.commit()
    token = await _login(client, email)

    payload = {
        "name": "Mass Assignment Corp",
        "slug": f"mass-assignment-{uuid.uuid4().hex[:6]}",
        **protected_field,
    }
    resp = await _create_org(client, token, payload)
    assert resp.status_code == 422, resp.text


# ── Duplicate handling ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_slug_returns_conflict_without_duplicate_membership(
    client: AsyncClient, session: AsyncSession
):
    user = await _create_user_with_role(session, "dup_admin@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "dup_admin@test.com")

    first = await _create_org(
        client, token, {"name": "First Org", "slug": "duplicate-slug"}
    )
    assert first.status_code == 201, first.text

    second = await _create_org(
        client, token, {"name": "Second Org", "slug": "duplicate-slug"}
    )
    assert second.status_code == 409, second.text
    assert "already exists" in second.json()["error"]["message"]

    org_repo = OrganizationRepository(session)
    org = await org_repo.get_by_slug("duplicate-slug")
    assert org is not None
    assert org.name == "First Org"

    count = await session.execute(
        select(func.count())
        .select_from(OrganizationMembership)
        .where(OrganizationMembership.user_id == user.id)
    )
    assert count.scalar_one() == 1


# ── Audit trail ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_successful_creation_is_audited(
    client: AsyncClient, session: AsyncSession
):
    user = await _create_user_with_role(session, "audit_admin@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "audit_admin@test.com")

    resp = await _create_org(
        client,
        token,
        {"name": "Audited Corp", "slug": "audited-corp"},
        request_id="req-audit-42",
    )
    assert resp.status_code == 201, resp.text
    org_id = uuid.UUID(resp.json()["id"])

    audit = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.ORGANIZATION_CREATED.value
            )
        )
    ).scalar_one()
    assert audit.user_id == user.id
    assert audit.organization_id == org_id
    assert audit.action == "organization_create"
    assert audit.resource_type == "organization"
    assert audit.resource_id == str(org_id)
    assert audit.success is True
    assert audit.ip_address
    assert audit.user_agent == "pytest-agent"
    assert audit.details["request_id"] == "req-audit-42"
    assert audit.details["organization_slug"] == "audited-corp"
    assert audit.details["organization_name"] == "Audited Corp"
    # No credential material is written to the audit trail.
    serialized = str(audit.details).lower()
    for secret in ("password", "token", "secret", "authorization"):
        assert secret not in serialized


# ── Tenant isolation ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_creator_membership_does_not_expose_org_to_other_admins(
    client: AsyncClient, session: AsyncSession
):
    creator = await _create_user_with_role(session, "tenant_creator@test.com", "super_admin")
    other = await _create_user_with_role(session, "tenant_other@test.com", "super_admin")
    await session.commit()
    creator_token = await _login(client, "tenant_creator@test.com")
    other_token = await _login(client, "tenant_other@test.com")

    resp = await _create_org(
        client, creator_token, {"name": "Private Tenant", "slug": "private-tenant"}
    )
    assert resp.status_code == 201, resp.text
    org_id = resp.json()["id"]

    # Another platform admin is not implicitly a member of the new tenant.
    memberships = await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == other.id
        )
    )
    assert memberships.scalars().all() == []

    listed = await client.get(
        "/api/v1/organizations/me/list",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert listed.status_code == 200
    assert listed.json() == []

    denied = await client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert denied.status_code == 403

    creator_memberships = await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == creator.id,
            OrganizationMembership.organization_id == uuid.UUID(org_id),
        )
    )
    assert len(creator_memberships.scalars().all()) == 1



# ── Metadata, Logo Upload & Admin Organization Features ─────────────────


@pytest.mark.asyncio
async def test_create_organization_with_full_metadata(
    client: AsyncClient, session: AsyncSession
):
    user = await _create_user_with_role(session, "full_meta_admin@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "full_meta_admin@test.com")

    payload = {
        "name": "Infosys Technologies",
        "industry": "Information Technology",
        "website": "https://www.infosys.com",
        "description": "Global leader in next-generation digital services and consulting.",
        "location": "Bangalore, India",
        "status": "active",
        "logo_url": "/uploads/organizations/infosys.png",
    }

    resp = await _create_org(client, token, payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Infosys Technologies"
    assert data["slug"] == "infosys-technologies"
    assert data["industry"] == "Information Technology"
    assert data["website"] == "https://www.infosys.com"
    assert data["location"] == "Bangalore, India"
    assert data["status"] == "active"
    assert data["logo_url"] == "/uploads/organizations/infosys.png"


@pytest.mark.asyncio
async def test_duplicate_organization_name_returns_conflict(
    client: AsyncClient, session: AsyncSession
):
    await _create_user_with_role(session, "dup_name_admin@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "dup_name_admin@test.com")

    resp1 = await _create_org(
        client, token, {"name": "Amazon", "slug": "amazon-prime"}
    )
    assert resp1.status_code == 201, resp1.text

    resp2 = await _create_org(
        client, token, {"name": "  amazon  ", "slug": "amazon-web-services"}
    )
    assert resp2.status_code == 409, resp2.text
    assert "already exists" in resp2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_invalid_website_url_is_rejected(
    client: AsyncClient, session: AsyncSession
):
    await _create_user_with_role(session, "url_admin@test.com", "super_admin")
    await session.commit()
    token = await _login(client, "url_admin@test.com")

    resp = await _create_org(
        client,
        token,
        {"name": "Bad URL Corp", "website": "not-a-valid-url"},
    )
    assert resp.status_code == 422, resp.text

    resp2 = await _create_org(
        client,
        token,
        {"name": "JS URL Corp", "website": "javascript:alert(1)"},
    )
    assert resp2.status_code == 422, resp2.text


@pytest.mark.asyncio
async def test_logo_upload_security(
    client: AsyncClient, session: AsyncSession
):
    await _create_user_with_role(session, "logo_admin@test.com", "super_admin")
    await _create_user_with_role(session, "logo_recruiter@test.com", "recruiter")
    await session.commit()
    admin_token = await _login(client, "logo_admin@test.com")
    recruiter_token = await _login(client, "logo_recruiter@test.com")

    # 1. Valid image upload by admin
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    files = {"file": ("logo.png", fake_png, "image/png")}
    resp = await client.post(
        "/api/v1/organizations/logo",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "logo_url" in data
    assert data["logo_url"].startswith("/uploads/organizations/")

    # 2. Reject executable / invalid extension
    exe_files = {"file": ("malicious.exe", b"MZ\x90\x00\x03", "application/x-msdownload")}
    resp_exe = await client.post(
        "/api/v1/organizations/logo",
        files=exe_files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_exe.status_code == 400

    # 3. Reject executable content masked as png
    masked_files = {"file": ("fake.png", b"MZ\x90ThisIsAnExecutable", "image/png")}
    resp_masked = await client.post(
        "/api/v1/organizations/logo",
        files=masked_files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_masked.status_code == 400

    # 4. Non-admin forbidden
    resp_recruiter = await client.post(
        "/api/v1/organizations/logo",
        files={"file": ("logo.png", fake_png, "image/png")},
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert resp_recruiter.status_code == 403

    # 5. Unauthenticated
    resp_anon = await client.post(
        "/api/v1/organizations/logo",
        files={"file": ("logo.png", fake_png, "image/png")},
    )
    assert resp_anon.status_code == 401


@pytest.mark.asyncio
async def test_list_all_organizations_endpoint(
    client: AsyncClient, session: AsyncSession
):
    await _create_user_with_role(session, "list_admin@test.com", "super_admin")
    await _create_user_with_role(session, "list_candidate@test.com", "candidate")
    await session.commit()
    admin_token = await _login(client, "list_admin@test.com")
    cand_token = await _login(client, "list_candidate@test.com")

    # Admin can list
    resp = await client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Candidate forbidden
    resp_cand = await client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {cand_token}"},
    )
    assert resp_cand.status_code == 403
