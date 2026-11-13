"""Phase 2: Organization / Tenant Foundation Tests.

Covers: organization CRUD, slug handling, membership integrity,
multi-org coexistence, and tenant isolation basics.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import AccountStatus, MembershipStatus, RoleName
from app.domain.models import (
    Organization,
    OrganizationMembership,
    User,
    UserRole,
)
from app.repositories.membership import OrganizationMembershipRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository


# ── Helpers ────────────────────────────────────────────────────────────


async def _create_user_with_role(session: AsyncSession, email: str, role_name: str):
    repo = UserRepository(session)
    user = await repo.create(
        full_name=f"User {email.split('@')[0]}",
        email=email,
        password_hash=hash_password("SecureP@ss1"),
        is_active=True,
        is_verified=True,
        account_status=AccountStatus.ACTIVE.value,
    )
    role = await repo.find_role_by_name(role_name)
    if role:
        await repo.assign_role(user.id, role.id)
    return user


async def _create_org(session: AsyncSession, name: str, slug: str) -> Organization:
    org = Organization(name=name, slug=slug, status="active")
    session.add(org)
    await session.flush()
    return org


async def _create_membership(
    session: AsyncSession, user_id, org_id, role: str
) -> OrganizationMembership:
    m = OrganizationMembership(
        user_id=user_id,
        organization_id=org_id,
        role=role,
        status=MembershipStatus.ACTIVE.value,
    )
    session.add(m)
    await session.flush()
    return m


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss1"},
    )
    return resp.json()["access_token"]


# ── Organization CRUD Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_organization(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "org_create@test.com", "admin")
    await session.commit()
    token = await _login(client, "org_create@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={
            "name": "Test Corp",
            "slug": "test-corp",
            "description": "A test org",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Corp"
    assert data["slug"] == "test-corp"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_organization_duplicate_slug(
    client: AsyncClient, session: AsyncSession
):
    user = await _create_user_with_role(session, "dup_slug@test.com", "admin")
    org = await _create_org(session, "Existing Org", "dup-slug")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()
    token = await _login(client, "dup_slug@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Dup Slug Org", "slug": "dup-slug"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_organization(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "get_org@test.com", "admin")
    org = await _create_org(session, "Get Org", "get-org")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()
    token = await _login(client, "get_org@test.com")

    resp = await client.get(
        f"/api/v1/organizations/{org.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Org"


@pytest.mark.asyncio
async def test_get_organization_not_found(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "not_found_org@test.com", "admin")
    await session.commit()
    token = await _login(client, "not_found_org@test.com")

    resp = await client.get(
        f"/api/v1/organizations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (404, 403)


@pytest.mark.asyncio
async def test_update_organization(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "upd_org@test.com", "admin")
    org = await _create_org(session, "Update Org", "upd-org")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()
    token = await _login(client, "upd_org@test.com")

    resp = await client.put(
        f"/api/v1/organizations/{org.id}",
        json={"name": "Updated Org", "description": "New description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Org"
    assert resp.json()["description"] == "New description"


@pytest.mark.asyncio
async def test_list_my_organizations(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "my_orgs@test.com", "admin")
    org1 = await _create_org(session, "Org One", "org-one")
    org2 = await _create_org(session, "Org Two", "org-two")
    await _create_membership(session, user.id, org1.id, "organization_admin")
    await _create_membership(session, user.id, org2.id, "recruiter")
    await session.commit()
    token = await _login(client, "my_orgs@test.com")

    resp = await client.get(
        "/api/v1/organizations/me/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    orgs = resp.json()
    assert len(orgs) == 2
    slugs = {o["slug"] for o in orgs}
    assert "org-one" in slugs
    assert "org-two" in slugs


@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_org(client: AsyncClient):
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "No Auth Org", "slug": "no-auth-org"},
    )
    assert resp.status_code == 401


# ── Slug Handling Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_slug_format_valid(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "slug_valid@test.com", "admin")
    await session.commit()
    token = await _login(client, "slug_valid@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Slug Valid", "slug": "my-org-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_slug_rejects_uppercase(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "slug_upper@test.com", "admin")
    await session.commit()
    token = await _login(client, "slug_upper@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Upper Slug", "slug": "InvalidSlug"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_slug_rejects_underscores(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "slug_under@test.com", "admin")
    await session.commit()
    token = await _login(client, "slug_under@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Under Slug", "slug": "invalid_slug"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_slug_rejects_spaces(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "slug_space@test.com", "admin")
    await session.commit()
    token = await _login(client, "slug_space@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Space Slug", "slug": "invalid slug"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_slug_rejects_leading_hyphen(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "slug_hyph@test.com", "admin")
    await session.commit()
    token = await _login(client, "slug_hyph@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Hyphen Slug", "slug": "-invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_slug_all_lowercase(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "slug_lower@test.com", "admin")
    await session.commit()
    token = await _login(client, "slug_lower@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Lower Slug", "slug": "all-lowercase"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


# ── Membership Integrity Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_creator_becomes_org_admin(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "creator@test.com", "admin")
    await session.commit()
    token = await _login(client, "creator@test.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Creator Org", "slug": "creator-org"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    org_id = resp.json()["id"]

    membership_repo = OrganizationMembershipRepository(session)
    membership = await membership_repo.get_active_membership(user.id, uuid.UUID(org_id))
    assert membership is not None
    assert membership.role == "organization_admin"


@pytest.mark.asyncio
async def test_non_member_cannot_see_members(client: AsyncClient, session: AsyncSession):
    user_a = await _create_user_with_role(session, "mbr_a@test.com", "admin")
    user_b = await _create_user_with_role(session, "mbr_b@test.com", "candidate")
    org = await _create_org(session, "Mbr Org", "mbr-org")
    await _create_membership(session, user_a.id, org.id, "organization_admin")
    await session.commit()
    token_b = await _login(client, "mbr_b@test.com")

    resp = await client.get(
        f"/api/v1/organizations/{org.id}/members",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_candidate_cannot_update_org(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "cand_upd@test.com", "candidate")
    org = await _create_org(session, "Cand Org", "cand-org")
    await session.commit()
    token = await _login(client, "cand_upd@test.com")

    resp = await client.put(
        f"/api/v1/organizations/{org.id}",
        json={"name": "Hacked Org"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_invite(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "rec_inv@test.com", "recruiter")
    org = await _create_org(session, "Rec Org", "rec-inv-org")
    await _create_membership(session, user.id, org.id, "recruiter")
    await session.commit()
    token = await _login(client, "rec_inv@test.com")

    resp = await client.post(
        f"/api/v1/organizations/{org.id}/invitations",
        json={"email": "new@test.com", "role": "recruiter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_hr_manager_can_list_members(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "hr_list@test.com", "admin")
    hr_user = await _create_user_with_role(session, "hr_member@test.com", "hr")
    org = await _create_org(session, "HR Org", "hr-list-org")
    await _create_membership(session, user.id, org.id, "hr_manager")
    await _create_membership(session, hr_user.id, org.id, "recruiter")
    await session.commit()
    token = await _login(client, "hr_list@test.com")

    resp = await client.get(
        f"/api/v1/organizations/{org.id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


# ── Multi-Organization Coexistence Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_user_can_belong_to_two_orgs(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "multi_org@test.com", "admin")
    org_a = await _create_org(session, "Org Alpha", "org-alpha")
    org_b = await _create_org(session, "Org Beta", "org-beta")
    await _create_membership(session, user.id, org_a.id, "organization_admin")
    await _create_membership(session, user.id, org_b.id, "recruiter")
    await session.commit()
    token = await _login(client, "multi_org@test.com")

    resp_a = await client.get(
        f"/api/v1/organizations/{org_a.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp_b = await client.get(
        f"/api/v1/organizations/{org_b.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["name"] == "Org Alpha"
    assert resp_b.json()["name"] == "Org Beta"


@pytest.mark.asyncio
async def test_orgs_have_separate_members(client: AsyncClient, session: AsyncSession):
    user_a = await _create_user_with_role(session, "sepa@test.com", "admin")
    user_b = await _create_user_with_role(session, "sepb@test.com", "admin")
    org_a = await _create_org(session, "Sep Org A", "sep-org-a")
    org_b = await _create_org(session, "Sep Org B", "sep-org-b")
    await _create_membership(session, user_a.id, org_a.id, "organization_admin")
    await _create_membership(session, user_b.id, org_b.id, "organization_admin")
    await session.commit()
    token_a = await _login(client, "sepa@test.com")

    resp = await client.get(
        f"/api/v1/organizations/{org_a.id}/members",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    members = [m["user_id"] for m in resp.json()["items"]]
    assert str(user_a.id) in members
    assert str(user_b.id) not in members


@pytest.mark.asyncio
async def test_list_my_organizations_empty(client: AsyncClient, session: AsyncSession):
    await _create_user_with_role(session, "empty_orgs@test.com", "candidate")
    await session.commit()
    token = await _login(client, "empty_orgs@test.com")

    resp = await client.get(
        "/api/v1/organizations/me/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_cannot_access_other_orgs_data(
    client: AsyncClient, session: AsyncSession
):
    user = await _create_user_with_role(session, "cross_org@test.com", "admin")
    org = await _create_org(session, "Private Org", "private-cross-org")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()
    token = await _login(client, "cross_org@test.com")

    other_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/organizations/{other_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (403, 404)


# ── Repository-Level Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_org_repo_get_by_slug(session: AsyncSession):
    org = await _create_org(session, "Repo Org", "repo-slug-test")
    await session.commit()
    repo = OrganizationRepository(session)
    found = await repo.get_by_slug("repo-slug-test")
    assert found is not None
    assert found.name == "Repo Org"


@pytest.mark.asyncio
async def test_org_repo_get_by_slug_not_found(session: AsyncSession):
    repo = OrganizationRepository(session)
    found = await repo.get_by_slug("nonexistent-slug")
    assert found is None


@pytest.mark.asyncio
async def test_membership_repo_active_membership(session: AsyncSession):
    user = await _create_user_with_role(session, "mbr_repo@test.com", "admin")
    org = await _create_org(session, "Mbr Repo Org", "mbr-repo-org")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()

    repo = OrganizationMembershipRepository(session)
    membership = await repo.get_active_membership(user.id, org.id)
    assert membership is not None
    assert membership.role == "organization_admin"


@pytest.mark.asyncio
async def test_membership_repo_count(session: AsyncSession):
    user_a = await _create_user_with_role(session, "cnt_a@test.com", "admin")
    user_b = await _create_user_with_role(session, "cnt_b@test.com", "recruiter")
    org = await _create_org(session, "Count Org", "count-org")
    await _create_membership(session, user_a.id, org.id, "organization_admin")
    await _create_membership(session, user_b.id, org.id, "recruiter")
    await session.commit()

    repo = OrganizationMembershipRepository(session)
    count = await repo.count_org_members(org.id)
    assert count == 2


# ── Database Constraint Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_org_slug_unique_constraint(session: AsyncSession):
    org1 = Organization(name="Org 1", slug="unique-slug", status="active")
    org2 = Organization(name="Org 2", slug="unique-slug", status="active")
    session.add(org1)
    await session.flush()
    session.add(org2)
    with pytest.raises(Exception):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_membership_status_values(session: AsyncSession):
    user = await _create_user_with_role(session, "status_val@test.com", "admin")
    org = await _create_org(session, "Status Org", "status-org")
    membership = await _create_membership(
        session, user.id, org.id, "organization_admin"
    )
    assert membership.status in [
        "active",
        "suspended",
        "revoked",
        "invited",
        "pending",
    ]


@pytest.mark.asyncio
async def test_org_uuid_primary_key(session: AsyncSession):
    org = await _create_org(session, "UUID Org", "uuid-pk-org")
    assert isinstance(org.id, uuid.UUID)


@pytest.mark.asyncio
async def test_org_status_active_by_default(session: AsyncSession):
    org = await _create_org(session, "Status Default", "status-default-org")
    assert org.status == "active"


# ── Invitation Lifecycle Tests (org-scoped) ───────────────────────────


@pytest.mark.asyncio
async def test_admin_can_create_invitation(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "inv_admin@test.com", "admin")
    org = await _create_org(session, "Inv Org", "inv-admin-org")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()
    token = await _login(client, "inv_admin@test.com")

    resp = await client.post(
        f"/api/v1/organizations/{org.id}/invitations",
        json={"email": "newhire@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "newhire@test.com"
    assert resp.json()["role"] == "hr_manager"
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_list_invitations(client: AsyncClient, session: AsyncSession):
    user = await _create_user_with_role(session, "inv_list@test.com", "admin")
    org = await _create_org(session, "Inv List Org", "inv-list-org")
    await _create_membership(session, user.id, org.id, "organization_admin")
    await session.commit()
    token = await _login(client, "inv_list@test.com")

    await client.post(
        f"/api/v1/organizations/{org.id}/invitations",
        json={"email": "list@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/v1/organizations/{org.id}/invitations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
