"""Tests for the employee access request flow.

Tests cover: create request, verify email, admin approve/reject, activate account.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.domain.enums import AccessRequestStatus, AccountStatus, MembershipStatus, OrganizationStatus, RoleName
from app.domain.models import (
    AccessRequest,
    Organization,
    OrganizationMembership,
    Role,
    User,
    UserRole,
)

pytestmark = [pytest.mark.anyio, pytest.mark.asyncio]


async def _create_org(session, org_id=None, slug="testorg", domain="test.com"):
    org = Organization(
        id=org_id or uuid.uuid4(),
        name="Test Corp",
        slug=slug,
        domain=domain,
        status=OrganizationStatus.ACTIVE.value,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_role(session, name="recruiter"):
    result = await session.execute(select(Role).where(Role.name == name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    role = Role(name=name, description=f"{name} role")
    session.add(role)
    await session.flush()
    return role


async def _create_user(session, email="existing@test.com", full_name="Existing User"):
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=full_name,
        password_hash=hash_password("TestPass123!"),
        is_active=True,
        is_verified=True,
        account_status=AccountStatus.ACTIVE.value,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_user_with_role(session, email="admin@test.com", role_name="organization_admin", full_name="Admin User"):
    user = await _create_user(session, email=email, full_name=full_name)
    role = await _create_role(session, role_name)
    ur = UserRole(user_id=user.id, role_id=role.id)
    session.add(ur)
    await session.flush()
    # Eagerly load roles so _get_token can access them outside greenlet context
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user.id)
    )
    return result.scalar_one()


def _get_token(user: User) -> str:
    """Generate a valid JWT access token for a user."""
    role_names = [ur.role.name for ur in (user.roles or [])]
    return create_access_token(str(user.id), role_names)


async def _create_membership(session, user_id, org_id, role="recruiter"):
    m = OrganizationMembership(
        user_id=user_id,
        organization_id=org_id,
        role=role,
        status=MembershipStatus.ACTIVE.value,
    )
    session.add(m)
    await session.flush()
    return m


# ── Create Access Request ────────────────────────────────────────────


class TestCreateAccessRequest:
    async def test_create_request_success(self, client: AsyncClient, session):
        org = await _create_org(session)
        await session.commit()

        resp = await client.post("/api/v1/access-requests", json={
            "full_name": "Jane Smith",
            "email": "jane@company.com",
            "organization_slug": "testorg",
            "requested_role": "recruiter",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending_email_verification"
        assert "verification" in data["message"].lower()

    async def test_create_request_duplicate(self, client: AsyncClient, session):
        org = await _create_org(session)
        # Create existing pending request
        existing = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
            verification_token_hash=AccessRequest.hash_token("oldtoken"),
            verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(existing)
        await session.commit()

        resp = await client.post("/api/v1/access-requests", json={
            "full_name": "Jane Smith",
            "email": "jane@test.com",
            "organization_slug": "testorg",
        })
        assert resp.status_code == 409
        assert "active access request" in resp.json()["error"]["message"].lower()

    async def test_create_request_existing_membership(self, client: AsyncClient, session):
        org = await _create_org(session)
        user = await _create_user(session, "jane@test.com")
        await _create_membership(session, user.id, org.id)
        await session.commit()

        resp = await client.post("/api/v1/access-requests", json={
            "full_name": "Jane Smith",
            "email": "jane@test.com",
            "organization_slug": "testorg",
        })
        assert resp.status_code == 409

    async def test_create_request_org_not_found(self, client: AsyncClient):
        resp = await client.post("/api/v1/access-requests", json={
            "full_name": "Jane",
            "email": "jane@test.com",
            "organization_slug": "nonexistent",
        })
        assert resp.status_code == 404

    async def test_create_request_invalid_role(self, client: AsyncClient, session):
        org = await _create_org(session)
        await session.commit()

        resp = await client.post("/api/v1/access-requests", json={
            "full_name": "Jane",
            "email": "jane@test.com",
            "organization_slug": "testorg",
            "requested_role": "super_admin",
        })
        assert resp.status_code == 422

    async def test_create_request_no_role(self, client: AsyncClient, session):
        org = await _create_org(session)
        await session.commit()

        resp = await client.post("/api/v1/access-requests", json={
            "full_name": "Jane",
            "email": "jane@test.com",
            "organization_slug": "testorg",
        })
        assert resp.status_code == 201


# ── Verify Email ─────────────────────────────────────────────────────


class TestVerifyEmail:
    async def test_verify_email_success(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "test_verification_token_abc123"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
            verification_token_hash=AccessRequest.hash_token(raw_token),
            verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(f"/api/v1/access-requests/{request.id}/verify-email?token={raw_token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_admin_approval"

    async def test_verify_email_invalid_token(self, client: AsyncClient, session):
        org = await _create_org(session)
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
            verification_token_hash=AccessRequest.hash_token("real_token"),
            verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(f"/api/v1/access-requests/{request.id}/verify-email?token=wrongtoken")
        assert resp.status_code == 422

    async def test_verify_email_already_verified(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "already_verified_token"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.EMAIL_VERIFIED.value,
            verification_token_hash=AccessRequest.hash_token(raw_token),
            verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(f"/api/v1/access-requests/{request.id}/verify-email?token={raw_token}")
        assert resp.status_code == 422

    async def test_verify_email_expired(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "expired_token"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
            verification_token_hash=AccessRequest.hash_token(raw_token),
            verification_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(f"/api/v1/access-requests/{request.id}/verify-email?token={raw_token}")
        assert resp.status_code == 422
        assert "expired" in resp.json()["error"]["message"].lower()


# ── Admin Approve ────────────────────────────────────────────────────


class TestAdminApprove:
    async def _setup_admin_with_request(self, session):
        """Create org, admin user, and a pending admin approval request."""
        org = await _create_org(session)
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")

        role = await _create_role(session, "recruiter")

        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane Smith",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            email_verified_at=datetime.now(timezone.utc),
            requested_role="recruiter",
        )
        session.add(request)
        await session.commit()
        return org, admin, request

    async def test_approve_success(self, client: AsyncClient, session):
        org, admin, request = await self._setup_admin_with_request(session)

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/approve",
            json={"approved_role": "recruiter"},
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    async def test_approve_invalid_role(self, client: AsyncClient, session):
        org, admin, request = await self._setup_admin_with_request(session)

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/approve",
            json={"approved_role": "super_admin"},
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 422

    async def test_approve_not_pending(self, client: AsyncClient, session):
        org, admin, request = await self._setup_admin_with_request(session)
        request.status = AccessRequestStatus.REJECTED.value
        await session.commit()

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/approve",
            json={"approved_role": "recruiter"},
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        # Admin endpoint wraps service errors → returns 404 not found
        assert resp.status_code == 404

    async def test_approve_no_auth(self, client: AsyncClient, session):
        org, admin, request = await self._setup_admin_with_request(session)

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/approve",
            json={"approved_role": "recruiter"},
        )
        assert resp.status_code == 422

    async def test_approve_wrong_org(self, client: AsyncClient, session):
        """Admin from org A cannot approve requests belonging to org B."""
        # Admin belongs to org A
        org = await _create_org(session, slug="orga", domain="orga.com")
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")

        # Request belongs to org B
        other_org = await _create_org(session, slug="orgb", domain="orgb.com")
        request = AccessRequest(
            organization_id=other_org.id,
            full_name="Jane Smith",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            email_verified_at=datetime.now(timezone.utc),
            requested_role="recruiter",
        )
        session.add(request)
        await session.commit()

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/approve",
            json={"approved_role": "recruiter"},
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 404


# ── Admin Reject ─────────────────────────────────────────────────────


class TestAdminReject:
    async def test_reject_success(self, client: AsyncClient, session):
        org = await _create_org(session)
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")

        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            email_verified_at=datetime.now(timezone.utc),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/reject",
            json={"reason": "Not a current employee"},
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    async def test_reject_no_reason(self, client: AsyncClient, session):
        org = await _create_org(session)
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")

        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            email_verified_at=datetime.now(timezone.utc),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(
            f"/api/v1/access-requests/{request.id}/reject",
            json={},
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 200


# ── Activate Account ─────────────────────────────────────────────────


class TestActivateAccount:
    async def test_activate_success(self, client: AsyncClient, session):
        org = await _create_org(session)
        role = await _create_role(session, "recruiter")

        raw_token = "activation_token_xyz"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane Smith",
            email="jane@test.com",
            status=AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
            approved_role="recruiter",
            activation_token_hash=AccessRequest.hash_token(raw_token),
            activation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(request)
        await session.commit()

        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": raw_token,
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "activated"

    async def test_activate_password_mismatch(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "activation_tokenMismatch"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
            approved_role="recruiter",
            activation_token_hash=AccessRequest.hash_token(raw_token),
            activation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(request)
        await session.commit()

        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": raw_token,
            "password": "SecurePass123!",
            "confirm_password": "DifferentPass456!",
        })
        assert resp.status_code == 422

    async def test_activate_weak_password(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "activation_tokenWeak"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
            approved_role="recruiter",
            activation_token_hash=AccessRequest.hash_token(raw_token),
            activation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(request)
        await session.commit()

        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": raw_token,
            "password": "123",
            "confirm_password": "123",
        })
        assert resp.status_code == 422

    async def test_activate_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": "nonexistent_token",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        })
        assert resp.status_code == 422

    async def test_activate_expired_token(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "expired_activation_token"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
            approved_role="recruiter",
            activation_token_hash=AccessRequest.hash_token(raw_token),
            activation_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add(request)
        await session.commit()

        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": raw_token,
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        })
        assert resp.status_code == 422
        assert "expired" in resp.json()["error"]["message"].lower()

    async def test_activate_already_used(self, client: AsyncClient, session):
        org = await _create_org(session)
        raw_token = "used_activation_token"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.ACTIVATED.value,
            approved_role="recruiter",
            activation_token_hash=AccessRequest.hash_token(raw_token),
            activation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(request)
        await session.commit()

        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": raw_token,
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        })
        assert resp.status_code == 422

    async def test_activate_existing_user(self, client: AsyncClient, session):
        """Activation with existing user should assign membership, not create new user."""
        org = await _create_org(session)
        role = await _create_role(session, "recruiter")
        existing_user = await _create_user(session, "jane@test.com")

        raw_token = "activate_existing_user"
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane Smith",
            email="jane@test.com",
            status=AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
            approved_role="recruiter",
            activation_token_hash=AccessRequest.hash_token(raw_token),
            activation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(request)
        await session.commit()

        resp = await client.post("/api/v1/access-requests/activate", json={
            "token": raw_token,
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        })
        assert resp.status_code == 200

        # Verify membership was created
        from sqlalchemy import select
        result = await session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == existing_user.id,
                OrganizationMembership.organization_id == org.id,
            )
        )
        membership = result.scalar_one_or_none()
        assert membership is not None
        assert membership.role == "recruiter"


# ── Admin List Requests ──────────────────────────────────────────────


class TestAdminListRequests:
    async def test_list_empty(self, client: AsyncClient, session):
        org = await _create_org(session)
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")
        await session.commit()

        resp = await client.get(
            "/api/v1/access-requests",
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    async def test_list_with_requests(self, client: AsyncClient, session):
        org = await _create_org(session)
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")

        for i in range(3):
            req = AccessRequest(
                organization_id=org.id,
                full_name=f"User {i}",
                email=f"user{i}@test.com",
                status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
                email_verified_at=datetime.now(timezone.utc),
            )
            session.add(req)
        await session.commit()

        resp = await client.get(
            "/api/v1/access-requests",
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    async def test_list_filter_by_status(self, client: AsyncClient, session):
        org = await _create_org(session)
        admin = await _create_user_with_role(session, email="admin@test.com", role_name="organization_admin")
        await _create_membership(session, admin.id, org.id, role="organization_admin")

        req1 = AccessRequest(
            organization_id=org.id, full_name="Pending User", email="pending@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            email_verified_at=datetime.now(timezone.utc),
        )
        req2 = AccessRequest(
            organization_id=org.id, full_name="Approved User", email="approved@test.com",
            status=AccessRequestStatus.APPROVED.value,
            email_verified_at=datetime.now(timezone.utc),
            reviewed_at=datetime.now(timezone.utc),
        )
        session.add_all([req1, req2])
        await session.commit()

        resp = await client.get(
            "/api/v1/access-requests?status=pending_admin_approval",
            headers={"Authorization": f"Bearer {_get_token(admin)}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["requests"][0]["email"] == "pending@test.com"

    async def test_list_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/access-requests")
        assert resp.status_code == 422


# ── Get Request Status ───────────────────────────────────────────────


class TestGetRequestStatus:
    async def test_get_status_success(self, client: AsyncClient, session):
        org = await _create_org(session)
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            email_verified_at=datetime.now(timezone.utc),
        )
        session.add(request)
        await session.commit()

        resp = await client.get(f"/api/v1/access-requests/{request.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Jane"
        assert data["status"] == "pending_admin_approval"

    async def test_get_status_not_found(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/access-requests/{fake_id}")
        assert resp.status_code == 404


# ── Resend Verification ─────────────────────────────────────────────


class TestResendVerification:
    async def test_resend_success(self, client: AsyncClient, session):
        org = await _create_org(session)
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
            verification_token_hash=AccessRequest.hash_token("old_token"),
            verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(f"/api/v1/access-requests/{request.id}/resend-verification")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_email_verification"

    async def test_resend_not_pending(self, client: AsyncClient, session):
        org = await _create_org(session)
        request = AccessRequest(
            organization_id=org.id,
            full_name="Jane",
            email="jane@test.com",
            status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            verification_token_hash=AccessRequest.hash_token("old_token"),
        )
        session.add(request)
        await session.commit()

        resp = await client.post(f"/api/v1/access-requests/{request.id}/resend-verification")
        assert resp.status_code == 422
