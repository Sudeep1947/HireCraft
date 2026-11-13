"""Phase 4 — HR / Admin Invitation System tests.

Covers:
- Invitation creation (authorized admin only)
- Role escalation protection
- Mass assignment protection
- Email normalization
- Token security
- Invitation lifecycle (pending → accepted/expired/revoked)
- Acceptance flow (new user + existing user)
- Email matching enforcement
- Duplicate membership prevention
- Revoke and resend
- Cross-organization protection
- Security: malicious payloads
"""

import uuid
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import decode_token, hash_password
from app.domain.models import Invitation, Organization, OrganizationMembership, Role, User, UserRole
from app.domain.enums import InvitationStatus, MembershipStatus
from app.services.invitation_service import InvitationService, VALID_INVITABLE_ROLES


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════


async def _create_org_via_api(client: AsyncClient, token: str, name: str = "Test Org", slug: str = "test-org") -> dict:
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": name, "slug": slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Org creation failed: {resp.text}"
    return resp.json()


async def _register_and_login(client: AsyncClient, email: str, password: str = "SecureP@ss1", name: str = "Test User") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": password},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp.json()["access_token"]


async def _create_user_with_role_in_db(session, email: str, name: str, role_name: str, password: str = "SecureP@ss1") -> User:
    user = User(
        id=uuid.uuid4(),
        full_name=name,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    result = await session.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one_or_none()
    if role:
        ur = UserRole(user_id=user.id, role_id=role.id)
        session.add(ur)
        await session.flush()
    await session.refresh(user)
    return user


async def _create_org_membership(session, user_id: uuid.UUID, org_id: uuid.UUID, role: str = "organization_admin") -> OrganizationMembership:
    membership = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user_id,
        organization_id=org_id,
        role=role,
        status=MembershipStatus.ACTIVE.value,
        joined_at=datetime.now(timezone.utc),
    )
    session.add(membership)
    await session.flush()
    return membership


async def _get_org_admin_token(client: AsyncClient, session, org_id: uuid.UUID) -> str:
    """Create a user with admin role, assign org membership, login, return token."""
    user = await _create_user_with_role_in_db(
        session, f"admin_{uuid.uuid4().hex[:8]}@test.com", "Org Admin", "admin"
    )
    await _create_org_membership(session, user.id, org_id, "organization_admin")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecureP@ss1"},
    )
    return resp.json()["access_token"]


async def _login(client: AsyncClient, email: str, password: str = "SecureP@ss1") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


# ═══════════════════════════════════════════════════════════════════
# 1. INVITATION CREATION — Authorization
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_org_admin_can_create_hr_invitation(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_invite@test.com", "Admin", "admin")
    token = await _login(client, user.email)
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Invite Org", "slug": f"invite-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    org_id = org_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new_hr@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new_hr@test.com"
    assert data["role"] == "hr_manager"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_org_admin_can_create_org_admin_invitation(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_invite2@test.com", "Admin2", "admin")
    token = await _login(client, user.email)
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Invite Org 2", "slug": f"invite-org2-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    org_id = org_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "new_admin@test.com", "role": "organization_admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "organization_admin"

# ═══════════════════════════════════════════════════════════════════
# 2. INVITATION CREATION — Authorization Failures
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_candidate_cannot_create_invitation(client: AsyncClient, auth_service):
    await auth_service.register("Cand", "cand_invite@test.com", "SecureP@ss1")
    token = await _login(client, "cand_invite@test.com")
    org_id = str(uuid.uuid4())

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "victim@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_invitation(client: AsyncClient):
    org_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "victim@test.com", "role": "hr_manager"},
    )
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_non_member_cannot_create_invitation(client: AsyncClient, session):
    # Organization creation is platform-admin-only, so seed the tenant directly
    # and keep this test focused on the invitation authorization boundary.
    org = Organization(
        id=uuid.uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    session.add(org)
    await session.flush()
    org_id = str(org.id)

    await _create_user_with_role_in_db(session, "outsider@test.com", "Outsider", "candidate")
    other_token = await _login(client, "outsider@test.com")

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "target@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 3. ROLE ESCALATION PROTECTION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_recruiter_role_accepted_for_invitation(client: AsyncClient, session):
    """Phase 5: recruiter became an invitable role (was rejected in Phase 4)."""
    user = await _create_user_with_role_in_db(session, "admin_rec@test.com", "Admin Rec", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Rec Org", "slug": f"rec-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    with patch("app.notifications.email_tasks.queue_invitation_email") as mock_queue:
        mock_queue.return_value = {"status": "queued", "task_id": "rec"}
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/invitations",
            json={"email": "rec@test.com", "role": "recruiter"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201
    assert resp.json()["role"] == "recruiter"


@pytest.mark.asyncio
async def test_candidate_role_rejected_for_invitation(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_cand@test.com", "Admin Cand", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Cand Org", "slug": f"cand-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "cand@test.com", "role": "candidate"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_super_admin_role_rejected_for_invitation(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_super@test.com", "Admin Super", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Super Org", "slug": f"super-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "super@test.com", "role": "super_admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_platform_admin_role_rejected_for_invitation(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_plat@test.com", "Admin Plat", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Plat Org", "slug": f"plat-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "plat@test.com", "role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 4. MASS ASSIGNMENT PROTECTION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_organization_id_injection_ignored(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_mass@test.com", "Admin Mass", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Mass Org", "slug": f"mass-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    other_org_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={
            "email": "mass@test.com",
            "role": "hr_manager",
            "organization_id": other_org_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["organization_id"] == org_id


@pytest.mark.asyncio
async def test_invited_by_injection_ignored(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_inviter@test.com", "Admin Inviter", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Inviter Org", "slug": f"inviter-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    fake_inviter = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={
            "email": "inviter@test.com",
            "role": "hr_manager",
            "invited_by_user_id": fake_inviter,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_permissions_injection_ignored(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_perms@test.com", "Admin Perms", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Perms Org", "slug": f"perms-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={
            "email": "perms@test.com",
            "role": "hr_manager",
            "permissions": ["admin:all"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


# ═══════════════════════════════════════════════════════════════════
# 5. EMAIL NORMALIZATION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invitation_email_normalized_to_lowercase(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_norm@test.com", "Admin Norm", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Norm Org", "slug": f"norm-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "  NORMALIZED@TEST.COM  ", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "normalized@test.com"


@pytest.mark.asyncio
async def test_duplicate_pending_invitation_rejected(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_dupe@test.com", "Admin Dupe", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Dupe Org", "slug": f"dupe-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp1 = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "dupe@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "dupe@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 409


# ═══════════════════════════════════════════════════════════════════
# 6. TOKEN SECURITY
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invitation_token_not_stored_raw(client: AsyncClient, session):
    from sqlalchemy import text

    user = await _create_user_with_role_in_db(session, "admin_token@test.com", "Admin Token", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Token Org", "slug": f"token-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "token@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    result = await session.execute(text("SELECT token_hash FROM invitations"))
    token_hashes = [row[0] for row in result.fetchall()]
    for th in token_hashes:
        assert len(th) == 64


@pytest.mark.asyncio
async def test_invitation_token_has_high_entropy(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    tokens = []
    for i in range(3):
        raw = InvModel.generate_token()
        tokens.append(raw)

    for t in tokens:
        assert len(t) >= 40

    assert len(set(tokens)) == 3


# ═══════════════════════════════════════════════════════════════════
# 7. INVITATION ACCEPTANCE — New User
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_new_user_can_accept_invitation(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_accept@test.com", "Admin Accept", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Accept Org", "slug": f"accept-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="newuser@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "New HR User",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 200
    assert "successfully" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_new_user_gets_correct_role_on_acceptance(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_role@test.com", "Admin Role", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Role Org", "slug": f"role-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="roleuser@test.com",
        role="organization_admin",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "New Org Admin",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 200

    from sqlalchemy import select as sa_select
    result = await session.execute(
        sa_select(OrganizationMembership).where(
            OrganizationMembership.organization_id == uuid.UUID(org_id),
        )
    )
    members = result.scalars().all()
    org_admin_members = [m for m in members if m.role == "organization_admin" and m.user_id != user.id]
    assert len(org_admin_members) == 1


# ═══════════════════════════════════════════════════════════════════
# 8. INVITATION ACCEPTANCE — Existing User
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_existing_user_can_accept_invitation(client: AsyncClient, session, auth_service):
    from app.domain.models import Invitation as InvModel

    existing_user = await _create_user_with_role_in_db(
        session, "existing_accept@test.com", "Existing Accept", "candidate"
    )

    admin_user = await _create_user_with_role_in_db(
        session, "admin_existing@test.com", "Admin Existing", "admin"
    )
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Existing Org", "slug": f"existing-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, admin_user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=admin_user.id,
        email=existing_user.email,
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    # Validate should reveal this is an existing-user invitation
    vresp = await client.get(f"/api/v1/invitations/validate/{raw_token}")
    assert vresp.status_code == 200
    assert vresp.json()["existing_user"] is True

    # Existing users must sign in — backend enforces identity via JWT
    user_token = await _login(client, existing_user.email)
    resp = await client.post(
        "/api/v1/invitations/accept-signed-in",
        json={"token": raw_token},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200

    from sqlalchemy import select as sa_select
    result = await session.execute(
        sa_select(OrganizationMembership).where(
            OrganizationMembership.user_id == existing_user.id,
            OrganizationMembership.organization_id == uuid.UUID(org_id),
        )
    )
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "hr_manager"


# ═══════════════════════════════════════════════════════════════════
# 9. EMAIL MATCHING
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_validate_invitation_returns_correct_info(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_validate@test.com", "Admin Validate", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Validate Org", "slug": f"validate-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="validate@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.get(f"/api/v1/invitations/validate/{raw_token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["email"] == "validate@test.com"
    assert data["role"] == "hr_manager"
    assert data["organization_name"] == "Validate Org"


# ═══════════════════════════════════════════════════════════════════
# 10. INVITATION LIFECYCLE — Expired
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_expired_invitation_cannot_be_accepted(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_exp@test.com", "Admin Exp", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Exp Org", "slug": f"exp-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="expired@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Expired User",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_expired_invitation_validate_shows_invalid(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_expv@test.com", "Admin ExpV", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "ExpV Org", "slug": f"expv-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="expiredv@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.get(f"/api/v1/invitations/validate/{raw_token}")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ═══════════════════════════════════════════════════════════════════
# 11. INVITATION LIFECYCLE — Revoked
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_revoked_invitation_cannot_be_accepted(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_rev@test.com", "Admin Rev", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Rev Org", "slug": f"rev-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="revoked@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.REVOKED.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Revoked User",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_revoke_invitation(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_revoke@test.com", "Admin Revoke", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Revoke Org", "slug": f"revoke-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="revoke_target@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations/{invitation.id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    await session.refresh(invitation)
    assert invitation.status == InvitationStatus.REVOKED.value


# ═══════════════════════════════════════════════════════════════════
# 12. DUPLICATE MEMBERSHIP PREVENTION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cannot_invite_existing_member(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_dupe_member@test.com", "Admin Dupe Member", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "DupeMember Org", "slug": f"dupe-member-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    existing_member = await _create_user_with_role_in_db(
        session, "already_member@test.com", "Already Member", "candidate"
    )
    await _create_org_membership(session, existing_member.id, uuid.UUID(org_id), "hr_manager")

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "already_member@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════════════
# 13. CROSS-ORGANIZATION PROTECTION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_non_member_cannot_invite_to_org(client: AsyncClient, session):
    admin = await _create_user_with_role_in_db(session, "admin_cross@test.com", "Admin Cross", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Cross Org", "slug": f"cross-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, admin.email)}"},
    )
    org_id = org_resp.json()["id"]

    outsider = await _create_user_with_role_in_db(session, "outsider_cross@test.com", "Outsider", "candidate")
    outsider_token = await _login(client, outsider.email)

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "target@test.com", "role": "hr_manager"},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 14. SINGLE-USE PROTECTION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_accepted_invitation_cannot_be_reused(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_reuse@test.com", "Admin Reuse", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Reuse Org", "slug": f"reuse-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="reuse@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.ACCEPTED.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        accepted_at=datetime.now(timezone.utc),
        accepted_by_id=user.id,
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Reuse User",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 15. INVALID TOKEN
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": "completely-fake-token-value",
            "full_name": "Fake User",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_invalid_token_returns_invalid(client: AsyncClient):
    resp = await client.get("/api/v1/invitations/validate/fake-token")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ═══════════════════════════════════════════════════════════════════
# 16. PASSWORD VALIDATION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_weak_password_rejected_on_acceptance(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_weak@test.com", "Admin Weak", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Weak Org", "slug": f"weak-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="weak@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Weak User",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_password_mismatch_rejected_on_acceptance(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_mismatch@test.com", "Admin Mismatch", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Mismatch Org", "slug": f"mismatch-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="mismatch@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Mismatch User",
            "password": "SecureP@ss1",
            "confirm_password": "DifferentP@ss1",
        },
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 17. LIST INVITATIONS
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_invitations(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_list@test.com", "Admin List", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "List Org", "slug": f"list-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    for i in range(3):
        raw_token = InvModel.generate_token()
        token_hash = InvModel.hash_token(raw_token)
        invitation = Invitation(
            organization_id=uuid.UUID(org_id),
            invited_by_id=user.id,
            email=f"list{i}@test.com",
            role="hr_manager",
            token_hash=token_hash,
            status=InvitationStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(invitation)
    await session.flush()

    resp = await client.get(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3


# ═══════════════════════════════════════════════════════════════════
# 18. RESEND INVITATION
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_resend_pending_invitation(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_resend@test.com", "Admin Resend", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Resend Org", "slug": f"resend-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="resend@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    inv_id = invitation.id

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations/{inv_id}/resend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["email"] == "resend@test.com"


@pytest.mark.asyncio
async def test_resend_expired_invitation(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    user = await _create_user_with_role_in_db(session, "admin_resend_exp@test.com", "Admin Resend Exp", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "ResendExp Org", "slug": f"resend-exp-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    org_id = org_resp.json()["id"]
    token = await _login(client, user.email)

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=user.id,
        email="resend_exp@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(invitation)
    await session.flush()
    inv_id = invitation.id

    resp = await client.post(
        f"/api/v1/organizations/{org_id}/invitations/{inv_id}/resend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


# ═══════════════════════════════════════════════════════════════════
# 19. BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_candidate_registration_still_works(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Phase4 Cand",
            "email": "phase4_cand@test.com",
            "password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_existing_login_still_works(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("Existing Login", "existing_login_p4@test.com", "SecureP@ss1", "recruiter")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "existing_login_p4@test.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_existing_dashboards_still_work(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("Dash P4", "dash_p4@test.com", "SecureP@ss1", "recruiter")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "dash_p4@test.com", "password": "SecureP@ss1"},
    )
    token = resp.json()["access_token"]
    dash_resp = await client.get(
        "/api/v1/dashboard/recruiter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dash_resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 20. EXISTING-USER IDENTITY ENFORCEMENT (signed-in flow)
# ═══════════════════════════════════════════════════════════════════


async def _seed_pending_invitation(session, org_id, inviter_id, email) -> tuple[Invitation, str]:
    raw_token = Invitation.generate_token()
    invitation = Invitation(
        organization_id=uuid.UUID(org_id) if isinstance(org_id, str) else org_id,
        invited_by_id=inviter_id,
        email=email,
        role="hr_manager",
        token_hash=Invitation.hash_token(raw_token),
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    return invitation, raw_token


@pytest.mark.asyncio
async def test_existing_user_cannot_accept_via_public_new_user_endpoint(client: AsyncClient, session):
    """An existing account must never be re-created or hijacked via /accept."""
    existing_user = await _create_user_with_role_in_db(
        session, "identity@test.com", "Identity User", "candidate"
    )
    admin = await _create_user_with_role_in_db(session, "admin_identity@test.com", "Admin Identity", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Identity Org", "slug": f"identity-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, admin.email)}"},
    )
    _, raw_token = await _seed_pending_invitation(session, org_resp.json()["id"], admin.id, existing_user.email)

    resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Attacker Chosen Name",
            "password": "SecureP@ss1",
            "confirm_password": "SecureP@ss1",
        },
    )
    assert resp.status_code == 422
    assert "already exists" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_email_mismatch_rejected_on_signed_in_accept(client: AsyncClient, session):
    """Authenticated user with a different email cannot steal an invitation."""
    invited_user = await _create_user_with_role_in_db(
        session, "invited_match@test.com", "Invited Match", "candidate"
    )
    other_user = await _create_user_with_role_in_db(
        session, "other_mismatch@test.com", "Other Mismatch", "candidate"
    )
    admin = await _create_user_with_role_in_db(session, "admin_mismatch2@test.com", "Admin Mismatch2", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Mismatch Org 2", "slug": f"mismatch2-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, admin.email)}"},
    )
    _, raw_token = await _seed_pending_invitation(session, org_resp.json()["id"], admin.id, invited_user.email)

    other_token = await _login(client, other_user.email)
    resp = await client.post(
        "/api/v1/invitations/accept-signed-in",
        json={"token": raw_token},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403

    # Invitation must remain pending and unconsumed
    result = await session.execute(
        select(Invitation).where(Invitation.token_hash == Invitation.hash_token(raw_token))
    )
    stored = result.scalar_one()
    await session.refresh(stored)
    assert stored.status == InvitationStatus.PENDING.value


@pytest.mark.asyncio
async def test_signed_in_accept_requires_authentication(client: AsyncClient, session):
    admin = await _create_user_with_role_in_db(session, "admin_signin_req@test.com", "Admin SignInReq", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "SignInReq Org", "slug": f"signinreq-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, admin.email)}"},
    )
    _, raw_token = await _seed_pending_invitation(session, org_resp.json()["id"], admin.id, "someone@test.com")

    resp = await client.post("/api/v1/invitations/accept-signed-in", json={"token": raw_token})
    # Missing/invalid credentials are rejected (422 = absent header, per FastAPI Header(...) validation)
    assert resp.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════════════
# 21. CONCURRENT ACCEPTANCE PROTECTION (single-use guarantee)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invitation_cannot_be_consumed_twice(session):
    """The conditional UPDATE guarantees only one consumer wins."""
    from app.repositories.invitation import InvitationRepository

    inviter = await _create_user_with_role_in_db(session, "race_admin@test.com", "Race Admin", "admin")
    invitee_a = await _create_user_with_role_in_db(session, "race_a@test.com", "Race A", "candidate")
    invitee_b = await _create_user_with_role_in_db(session, "race_b@test.com", "Race B", "candidate")
    org = Organization(name=f"Race Org {uuid.uuid4().hex[:6]}", slug=f"race-org-{uuid.uuid4().hex[:6]}")
    session.add(org)
    await session.flush()

    invitation, raw_token = await _seed_pending_invitation(session, org.id, inviter.id, "race_target@test.com")
    repo = InvitationRepository(session)

    first = await repo.mark_accepted_if_pending(invitation.id, invitee_a.id)
    second = await repo.mark_accepted_if_pending(invitation.id, invitee_b.id)

    assert first is True
    assert second is False
    await session.refresh(invitation)
    assert invitation.accepted_by_id == invitee_a.id


@pytest.mark.asyncio
async def test_second_api_accept_after_success_rejected(client: AsyncClient, session):
    user = await _create_user_with_role_in_db(session, "admin_double@test.com", "Admin Double", "admin")
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Double Org", "slug": f"double-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {await _login(client, user.email)}"},
    )
    _, raw_token = await _seed_pending_invitation(session, org_resp.json()["id"], user.id, "double@test.com")

    payload = {
        "token": raw_token,
        "full_name": "Double User",
        "password": "SecureP@ss1",
        "confirm_password": "SecureP@ss1",
    }
    first = await client.post("/api/v1/invitations/accept", json=payload)
    second = await client.post("/api/v1/invitations/accept", json=payload)

    assert first.status_code == 200
    assert second.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 22. EXPIRATION CONFIGURATION
# ═══════════════════════════════════════════════════════════════════


def test_expiration_uses_configured_hours():
    from unittest.mock import MagicMock

    svc = InvitationService.__new__(InvitationService)
    svc._settings = MagicMock(invitation_expiration_hours=72)
    expires_at = svc._expiry_from_now()

    expected = datetime.now(timezone.utc) + timedelta(hours=72)
    delta = abs((expires_at - expected).total_seconds())
    assert delta < 60


def test_expiration_default_is_72_hours():
    settings = get_settings()
    assert settings.invitation_expiration_hours == 72
