"""Employee Access Request Service.

Handles the full flow: employee requests access -> email verified -> admin approves -> account activated.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import AccessRequestRole, AccessRequestStatus, AuditEventType, MembershipStatus, RoleName
from app.domain.models import AccessRequest, Organization, OrganizationMembership, Role, User, UserRole
from app.repositories.access_request import AccessRequestRepository
from app.repositories.membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository

logger = get_logger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")
settings = get_settings()

ACCESS_REQUEST_VERIFICATION_HOURS = 24
ACCESS_REQUEST_ACTIVATION_DAYS = 7


class AccessRequestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AccessRequestRepository(session)
        self.user_repo = UserRepository(session)
        self.membership_repo = OrganizationMembershipRepository(session)

    # ── Employee: Create Access Request ─────────────────────────────

    async def create_request(
        self,
        full_name: str,
        email: str,
        organization_slug: str,
        requested_role: str | None = None,
    ) -> tuple[AccessRequest, str]:
        """Create an access request and return (request, raw_verification_token)."""
        email = email.lower().strip()
        full_name = full_name.strip()

        # Resolve organization by slug or domain
        org = await self._resolve_organization(organization_slug)
        if not org:
            raise NotFoundError(detail="Organization not found")

        # Validate requested role if provided
        if requested_role and requested_role not in {r.value for r in AccessRequestRole}:
            raise ValidationError(detail="Invalid requested role. Must be 'hr_manager' or 'recruiter'.")

        # Check for existing active request
        existing = await self.repo.get_active_by_email_and_org(email, org.id)
        if existing:
            raise ConflictError(
                detail="An active access request already exists for this email and organization.",
                extra={"request_id": str(existing.id), "status": existing.status},
            )

        # Check if user already has an active membership in this org
        existing_membership = await self.membership_repo.get_active_membership_by_email(email, org.id)
        if existing_membership:
            raise ConflictError(
                detail="An account with this email already has an active role in this organization.",
            )

        # Generate verification token
        raw_token = AccessRequest.generate_token()
        token_hash = AccessRequest.hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ACCESS_REQUEST_VERIFICATION_HOURS)

        # Create request
        request = AccessRequest(
            organization_id=org.id,
            full_name=full_name,
            email=email,
            requested_role=requested_role,
            verification_token_hash=token_hash,
            verification_expires_at=expires_at,
            status=AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
        )
        self.session.add(request)
        await self.session.flush()

        AUDIT_LOGGER.info(
            "ACCESS_REQUEST_CREATED org=%s email=%s request_id=%s",
            org.slug, email, request.id,
        )

        return request, raw_token

    # ── Employee: Verify Email ──────────────────────────────────────

    async def verify_email(self, token: str) -> AccessRequest:
        """Verify the employee's company email via the verification token."""
        token_hash = AccessRequest.hash_token(token)
        request = await self.repo.get_by_verification_token_hash(token_hash)

        if not request:
            raise ValidationError(detail="Invalid verification link.")

        if request.status != AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value:
            raise ValidationError(detail="This verification link has already been used.")

        if request.verification_expires_at and request.verification_expires_at < datetime.now(timezone.utc):
            await self.repo.update_status(request.id, AccessRequestStatus.EXPIRED)
            raise ValidationError(detail="This verification link has expired. Please request a new one.")

        # Mark as verified, transition to EMAIL_VERIFIED then PENDING_ADMIN_APPROVAL
        await self.repo.set_verified(request.id)
        # Immediately transition to pending admin approval
        from sqlalchemy import update
        await self.session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.id == request.id,
                AccessRequest.status == AccessRequestStatus.EMAIL_VERIFIED.value,
            )
            .values(status=AccessRequestStatus.PENDING_ADMIN_APPROVAL.value)
        )

        AUDIT_LOGGER.info(
            "ACCESS_EMAIL_VERIFIED request_id=%s email=%s",
            request.id, request.email,
        )

        request.status = AccessRequestStatus.PENDING_ADMIN_APPROVAL.value
        return request

    # ── Employee: Resend Verification ───────────────────────────────

    async def resend_verification(self, request_id: uuid.UUID) -> tuple[AccessRequest, str]:
        """Resend verification email for a pending request."""
        request = await self.repo.get(request_id)
        if not request:
            raise NotFoundError(detail="Access request not found.")

        if request.status != AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value:
            raise ValidationError(detail="This request is no longer awaiting email verification.")

        raw_token = AccessRequest.generate_token()
        token_hash = AccessRequest.hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ACCESS_REQUEST_VERIFICATION_HOURS)

        from sqlalchemy import update
        await self.session.execute(
            update(AccessRequest)
            .where(AccessRequest.id == request.id)
            .values(
                verification_token_hash=token_hash,
                verification_expires_at=expires_at,
            )
        )

        return request, raw_token

    # ── Admin: List Requests ────────────────────────────────────────

    async def list_requests(
        self,
        organization_id: uuid.UUID,
        status: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[AccessRequest], int]:
        return await self.repo.list_by_org(organization_id, status=status, offset=offset, limit=limit)

    # ── Admin: Get Request Detail ───────────────────────────────────

    async def get_request(self, request_id: uuid.UUID, organization_id: uuid.UUID) -> AccessRequest:
        request = await self.repo.get_by_id_and_org(request_id, organization_id)
        if not request:
            raise NotFoundError(detail="Access request not found.")
        return request

    # ── Admin: Approve Request ──────────────────────────────────────

    async def approve_request(
        self,
        request_id: uuid.UUID,
        organization_id: uuid.UUID,
        approved_role: str,
        reviewed_by_id: uuid.UUID,
    ) -> AccessRequest:
        """Admin approves an access request. Creates activation token."""
        # Validate role
        valid_roles = {AccessRequestRole.HR_MANAGER.value, AccessRequestRole.RECRUITER.value}
        if approved_role not in valid_roles:
            raise ValidationError(detail="Approved role must be 'hr_manager' or 'recruiter'.")

        request = await self.repo.get_by_id_and_org(request_id, organization_id)
        if not request:
            raise NotFoundError(detail="Access request not found.")

        if request.status != AccessRequestStatus.PENDING_ADMIN_APPROVAL.value:
            raise ValidationError(
                detail=f"Cannot approve a request with status '{request.status}'.",
                extra={"current_status": request.status},
            )

        # Check if a user with this email already exists
        existing_user = await self.user_repo.get_by_email(request.email)

        # Set approved status
        success = await self.repo.set_approved(request.id, approved_role, reviewed_by_id)
        if not success:
            raise ValidationError(detail="Failed to approve request. It may have been processed already.")

        # Generate activation token
        raw_activation_token = AccessRequest.generate_token()
        activation_hash = AccessRequest.hash_token(raw_activation_token)
        activation_expires = datetime.now(timezone.utc) + timedelta(days=ACCESS_REQUEST_ACTIVATION_DAYS)

        await self.repo.set_activation_pending(request.id, activation_hash, activation_expires)

        AUDIT_LOGGER.info(
            "ACCESS_REQUEST_APPROVED request_id=%s approved_role=%s reviewed_by=%s email=%s",
            request.id, approved_role, reviewed_by_id, request.email,
        )

        # Refresh to get updated status
        await self.session.refresh(request)
        request._raw_activation_token = raw_activation_token  # type: ignore[attr-defined]
        return request

    # ── Admin: Reject Request ───────────────────────────────────────

    async def reject_request(
        self,
        request_id: uuid.UUID,
        organization_id: uuid.UUID,
        reviewed_by_id: uuid.UUID,
        reason: str | None = None,
    ) -> AccessRequest:
        request = await self.repo.get_by_id_and_org(request_id, organization_id)
        if not request:
            raise NotFoundError(detail="Access request not found.")

        if request.status != AccessRequestStatus.PENDING_ADMIN_APPROVAL.value:
            raise ValidationError(
                detail=f"Cannot reject a request with status '{request.status}'.",
            )

        success = await self.repo.set_rejected(request.id, reviewed_by_id, reason)
        if not success:
            raise ValidationError(detail="Failed to reject request.")

        AUDIT_LOGGER.info(
            "ACCESS_REQUEST_REJECTED request_id=%s reviewed_by=%s email=%s reason=%s",
            request.id, reviewed_by_id, request.email, reason or "(none)",
        )

        await self.session.refresh(request)
        return request

    # ── Employee: Activate Account ──────────────────────────────────

    async def activate_account(self, token: str, password: str) -> User:
        """Activate account after admin approval. Creates user if needed, assigns role."""
        from app.core.security import hash_password, validate_password_strength

        token_hash = AccessRequest.hash_token(token)
        request = await self.repo.get_by_activation_token_hash(token_hash)

        if not request:
            raise ValidationError(detail="Invalid activation link.")

        if request.status != AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value:
            raise ValidationError(detail="This activation link has already been used.")

        if request.activation_expires_at and request.activation_expires_at < datetime.now(timezone.utc):
            await self.repo.update_status(request.id, AccessRequestStatus.EXPIRED)
            raise ValidationError(detail="This activation link has expired. Please contact your administrator.")

        # Validate password
        errors = validate_password_strength(password)
        if errors:
            raise ValidationError(
                detail="Password does not meet security requirements.",
                extra={"requirements": errors},
            )

        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(request.email)

        if existing_user:
            # Check if they already have membership in this org
            existing_membership = await self.membership_repo.get_active_membership(existing_user.id, request.organization_id)
            if existing_membership:
                raise ConflictError(detail="An account with this email already has an active role in this organization.")
            user = existing_user
        else:
            # Create new user
            user = await self.user_repo.create(
                full_name=request.full_name,
                email=request.email,
                password_hash=hash_password(password),
                is_active=True,
                is_verified=True,
                account_status="active",
            )

        # Assign organization membership
        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=request.organization_id,
            role=request.approved_role,
            status=MembershipStatus.ACTIVE.value,
            joined_at=datetime.now(timezone.utc),
        )
        self.session.add(membership)

        # Assign global role
        role_result = await self.session.execute(
            select(Role).where(Role.name == request.approved_role)
        )
        role = role_result.scalar_one_or_none()
        if role:
            # Check if role already assigned
            existing_ur = await self.session.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            )
            if not existing_ur.scalar_one_or_none():
                self.session.add(UserRole(user_id=user.id, role_id=role.id))

        # Mark as activated
        await self.repo.set_activated(request.id, user.id)

        AUDIT_LOGGER.info(
            "ACCOUNT_ACTIVATED request_id=%s user_id=%s role=%s email=%s",
            request.id, user.id, request.approved_role, request.email,
        )

        await self.session.flush()
        return user

    # ── Helpers ─────────────────────────────────────────────────────

    async def _resolve_organization(self, slug_or_domain: str) -> Organization | None:
        """Resolve organization by slug, domain, or name."""
        slug_or_domain = slug_or_domain.strip().lower()

        # Try slug first
        result = await self.session.execute(
            select(Organization).where(Organization.slug == slug_or_domain)
        )
        org = result.scalar_one_or_none()
        if org:
            return org

        # Try domain (strip @ if present)
        domain = slug_or_domain.lstrip("@")
        result = await self.session.execute(
            select(Organization).where(Organization.domain == domain)
        )
        org = result.scalar_one_or_none()
        if org:
            return org

        # Try name (case-insensitive partial match)
        result = await self.session.execute(
            select(Organization).where(Organization.name.ilike(f"%{slug_or_domain}%"))
        )
        return result.scalars().first()
