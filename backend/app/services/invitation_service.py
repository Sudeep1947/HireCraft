"""Invitation service for secure team onboarding."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationError
from app.core.logging import get_logger
from app.core.security import hash_password, validate_password_strength
from app.domain.enums import InvitationStatus, MembershipStatus, OrganizationStatus, RoleName
from app.domain.models import Invitation, OrganizationMembership, UserRole
from app.repositories.invitation import InvitationRepository
from app.repositories.user import UserRepository

logger = get_logger(__name__)

# Phase 4/5: roles that may appear on organization invitations.
# Candidate is excluded (public self-registration, Phase 3).
# Platform roles (admin/super_admin) are never invitable via organizations.
VALID_INVITABLE_ROLES = {
    RoleName.HR_MANAGER.value,
    RoleName.ORG_ADMIN.value,
    RoleName.RECRUITER.value,
}

# Phase 5 minimum authorization rule (formalized in Phase 9):
# Only organization admins may create/resend/revoke invitations, regardless
# of target role. HR managers cannot invite recruiters unless explicitly
# granted in a later phase.


class InvitationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._invitation_repo = InvitationRepository(session)
        self._user_repo = UserRepository(session)
        self._settings = get_settings()

    def _expiry_from_now(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            hours=self._settings.invitation_expiration_hours
        )

    @staticmethod
    def _as_aware_utc(value: datetime) -> datetime:
        """SQLite drops tzinfo on storage; treat naive timestamps as UTC."""
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    async def create_invitation(
        self,
        organization_id: uuid.UUID,
        invited_by_id: uuid.UUID,
        email: str,
        role: str,
    ) -> tuple[Invitation, str]:
        email = email.strip().lower()

        if role not in VALID_INVITABLE_ROLES:
            raise ValidationError(
                detail=f"Cannot invite for role '{role}'. Valid roles: {', '.join(VALID_INVITABLE_ROLES)}"
            )

        existing_invite = await self._invitation_repo.get_pending_by_email_and_org(email, organization_id)
        if existing_invite:
            if self._as_aware_utc(existing_invite.expires_at) < datetime.now(timezone.utc):
                existing_invite.status = InvitationStatus.EXPIRED.value
                await self._session.flush()
            else:
                raise ConflictError(detail="An active invitation already exists for this email in this organization. You can resend or revoke it from the Pending Invitations list below.")

        existing_user = await self._user_repo.get_by_email(email)
        if existing_user:
            from app.repositories.membership import OrganizationMembershipRepository
            membership_repo = OrganizationMembershipRepository(self._session)
            existing_membership = await membership_repo.get_active_membership(existing_user.id, organization_id)
            if existing_membership:
                raise ConflictError(detail="User is already a member of this organization")

        raw_token = Invitation.generate_token()
        token_hash = Invitation.hash_token(raw_token)
        expires_at = self._expiry_from_now()

        invitation = Invitation(
            organization_id=organization_id,
            invited_by_id=invited_by_id,
            email=email,
            role=role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING.value,
            expires_at=expires_at,
        )
        self._session.add(invitation)
        await self._session.flush()

        logger.info(
            "Invitation created: org=%s email=%s role=%s by=%s",
            organization_id, email, role, invited_by_id,
        )
        return invitation, raw_token

    async def validate_invitation(self, token: str) -> Invitation:
        token_hash = Invitation.hash_token(token)
        invitation = await self._invitation_repo.get_by_token_hash(token_hash)

        if not invitation:
            raise NotFoundError(detail="Invalid invitation token")

        if invitation.status == InvitationStatus.ACCEPTED.value:
            raise ValidationError(detail="This invitation has already been accepted")

        if invitation.status == InvitationStatus.REVOKED.value:
            raise ValidationError(detail="This invitation has been revoked")

        if self._as_aware_utc(invitation.expires_at) < datetime.now(timezone.utc):
            invitation.status = InvitationStatus.EXPIRED.value
            await self._session.flush()
            raise ValidationError(detail="This invitation has expired")

        return invitation

    async def _consume_invitation(self, invitation: Invitation, user) -> OrganizationMembership:
        """Create membership and atomically mark invitation accepted (race-safe)."""
        from app.repositories.membership import OrganizationMembershipRepository

        membership_repo = OrganizationMembershipRepository(self._session)

        existing_membership = await membership_repo.get_active_membership(
            user.id, invitation.organization_id
        )
        if existing_membership:
            raise ConflictError(detail="You are already a member of this organization")

        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=invitation.organization_id,
            role=invitation.role,
            status=MembershipStatus.ACTIVE.value,
            invited_by_id=invitation.invited_by_id,
            joined_at=datetime.now(timezone.utc),
        )
        self._session.add(membership)

        # Grant the invited global role so dashboards/RBAC recognize the user.
        role_obj = await self._user_repo.find_role_by_name(invitation.role)
        if role_obj is not None:
            from sqlalchemy import select

            already_has = (
                await self._session.execute(
                    select(UserRole).where(
                        UserRole.user_id == user.id, UserRole.role_id == role_obj.id
                    )
                )
            ).scalar_one_or_none()
            if already_has is None:
                await self._user_repo.assign_role(user.id, role_obj.id)

        consumed = await self._invitation_repo.mark_accepted_if_pending(invitation.id, user.id)
        if not consumed:
            raise ConflictError(detail="This invitation has already been used")
        try:
            await self._session.flush()
        except IntegrityError:
            raise ConflictError(detail="You are already a member of this organization")

        logger.info(
            "Invitation accepted: user=%s org=%s role=%s",
            user.id, invitation.organization_id, invitation.role,
        )
        return membership

    async def accept_invitation(
        self,
        token: str,
        full_name: str,
        password: str,
        confirm_password: str,
    ) -> OrganizationMembership:
        """Acceptance for NEW users: creates the account bound to the invited email."""
        if password != confirm_password:
            raise ValidationError(detail="Passwords do not match")

        violations = validate_password_strength(password)
        if violations:
            raise ValidationError(
                detail="Password does not meet security requirements",
                extra={"requirements": violations},
            )

        invitation = await self.validate_invitation(token)

        existing_user = await self._user_repo.get_by_email(invitation.email)
        if existing_user:
            # An account exists for this email — it must not be re-created here.
            # The invitee must sign in so identity can be verified server-side.
            raise ValidationError(detail="An account already exists for this email. Please sign in to accept this invitation.")

        user = await self._user_repo.create(
            full_name=full_name,
            email=invitation.email,
            password_hash=hash_password(password),
            is_active=True,
            is_verified=True,
        )
        return await self._consume_invitation(invitation, user)

    async def accept_invitation_signed_in(self, token: str, current_user) -> OrganizationMembership:
        """Acceptance for EXISTING users: authenticated; email must match invitee."""
        invitation = await self.validate_invitation(token)

        if current_user.email.strip().lower() != invitation.email:
            logger.warning(
                "Invitation email mismatch: user=%s expected_email_domain_match_failed org=%s",
                current_user.id, invitation.organization_id,
            )
            raise ForbiddenError(detail="This invitation was sent to a different email address")

        return await self._consume_invitation(invitation, current_user)

    async def revoke_invitation(
        self, invitation_id: uuid.UUID, actor_id: uuid.UUID
    ) -> bool:
        invitation = await self._invitation_repo.get(invitation_id)
        if not invitation:
            raise NotFoundError(detail="Invitation not found")

        if invitation.invited_by_id != actor_id:
            raise ForbiddenError(detail="You can only revoke invitations you created")

        result = await self._invitation_repo.revoke(invitation_id)
        if result:
            logger.info("Invitation revoked: id=%s by=%s", invitation_id, actor_id)
        return result

    async def resend_invitation(
        self, invitation_id: uuid.UUID, actor_id: uuid.UUID
    ) -> tuple[Invitation, str]:
        invitation = await self._invitation_repo.get(invitation_id)
        if not invitation:
            raise NotFoundError(detail="Invitation not found")

        if invitation.invited_by_id != actor_id:
            raise ForbiddenError(detail="You can only resend invitations you created")

        if invitation.status not in (
            InvitationStatus.PENDING.value,
            InvitationStatus.EXPIRED.value,
        ):
            raise ValidationError(
                detail=f"Cannot resend invitation with status '{invitation.status}'"
            )

        raw_token = Invitation.generate_token()
        token_hash = Invitation.hash_token(raw_token)
        expires_at = self._expiry_from_now()

        invitation.token_hash = token_hash
        invitation.expires_at = expires_at
        invitation.status = InvitationStatus.PENDING.value
        await self._session.flush()

        logger.info(
            "Invitation resent: id=%s org=%s email=%s by=%s",
            invitation_id, invitation.organization_id, invitation.email, actor_id,
        )
        return invitation, raw_token

    async def list_organization_invitations(
        self, organization_id: uuid.UUID, include_expired: bool = False
    ) -> list[Invitation]:
        return await self._invitation_repo.get_org_invitations(organization_id, include_expired)
