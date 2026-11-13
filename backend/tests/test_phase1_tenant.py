"""Phase 1 Tenant Isolation Tests.

Verifies that cross-organization data access is prevented.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import AccountStatus, MembershipStatus
from app.domain.models import (
    Organization,
    OrganizationMembership,
)
from app.repositories.user import UserRepository


async def _create_user_with_role(session: AsyncSession, email: str, role_name: str):
    """Create a user directly in the DB with a role."""
    repo = UserRepository(session)
    user = await repo.create(
        full_name=f"User {email}",
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


@pytest.mark.asyncio
async def test_org_a_cannot_see_org_b_members(client: AsyncClient, session: AsyncSession):
    """Organization A's admin should not see Organization B's members."""
    user_a = await _create_user_with_role(session, "admin_a@tenant.com", "admin")
    user_b = await _create_user_with_role(session, "admin_b@tenant.com", "admin")
    org_a = await _create_org(session, "Org A", "org-a-tenant")
    org_b = await _create_org(session, "Org B", "org-b-tenant")
    await _create_membership(session, user_a.id, org_a.id, "organization_admin")
    await _create_membership(session, user_b.id, org_b.id, "organization_admin")
    await session.commit()

    token_a = await _login(client, "admin_a@tenant.com")

    resp = await client.get(
        f"/api/v1/organizations/{org_b.id}/members",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_a_cannot_invite_to_org_b(client: AsyncClient, session: AsyncSession):
    """Organization A's admin should not invite to Organization B."""
    user_a = await _create_user_with_role(session, "invader@tenant.com", "admin")
    org_a = await _create_org(session, "Org A2", "org-a2-tenant")
    org_b = await _create_org(session, "Org B2", "org-b2-tenant")
    await _create_membership(session, user_a.id, org_a.id, "organization_admin")
    await session.commit()

    token_a = await _login(client, "invader@tenant.com")

    resp = await client.post(
        f"/api/v1/organizations/{org_b.id}/invitations",
        json={"email": "sneaky@evil.com", "role": "recruiter"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_access_org(client: AsyncClient, session: AsyncSession):
    """A user not belonging to an org should not access its data."""
    user = await _create_user_with_role(session, "outsider@tenant.com", "candidate")
    org = await _create_org(session, "Private Org", "private-org")
    await session.commit()

    token = await _login(client, "outsider@tenant.com")

    resp = await client.get(
        f"/api/v1/organizations/{org.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_member_can_access_own_org(client: AsyncClient, session: AsyncSession):
    """Organization members should access their own org."""
    user = await _create_user_with_role(session, "member@tenant.com", "recruiter")
    org = await _create_org(session, "My Org", "my-org-tenant")
    await _create_membership(session, user.id, org.id, "recruiter")
    await session.commit()

    token = await _login(client, "member@tenant.com")

    resp = await client.get(
        f"/api/v1/organizations/{org.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_candidate_cannot_create_organization(client: AsyncClient, auth_service):
    """Candidates should not be able to create organizations."""
    await auth_service.register("Cand Create", "cand_create@tenant.com", "SecureP@ss1")
    token = await _login(client, "cand_create@tenant.com")

    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Hacker Org", "slug": "hacker-org"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recruiter_cannot_manage_members(client: AsyncClient, session: AsyncSession):
    """Recruiters should not be able to manage team members."""
    user = await _create_user_with_role(session, "rec_m@tenant.com", "recruiter")
    org = await _create_org(session, "Rec Org", "rec-org-tenant")
    await _create_membership(session, user.id, org.id, "recruiter")
    await session.commit()

    token = await _login(client, "rec_m@tenant.com")

    resp = await client.get(
        f"/api/v1/organizations/{org.id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
