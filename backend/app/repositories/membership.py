"""Organization membership repository."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import OrganizationMembership, User
from app.domain.enums import MembershipStatus
from app.repositories.base import BaseRepository


class OrganizationMembershipRepository(BaseRepository[OrganizationMembership]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrganizationMembership)

    async def get_by_user_and_org(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMembership | None:
        stmt = select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_membership(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMembership | None:
        stmt = select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_membership_by_email(
        self, email: str, organization_id: uuid.UUID
    ) -> OrganizationMembership | None:
        """Check if a user with this email has an active membership in the org."""
        from app.domain.models import User

        stmt = (
            select(OrganizationMembership)
            .join(User, OrganizationMembership.user_id == User.id)
            .where(
                User.email == email.lower().strip(),
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE.value,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_organizations(self, user_id: uuid.UUID) -> list[OrganizationMembership]:
        stmt = (
            select(OrganizationMembership)
            .options(selectinload(OrganizationMembership.organization))
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE.value,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_org_members(
        self, organization_id: uuid.UUID, include_inactive: bool = False
    ) -> list[OrganizationMembership]:
        stmt = select(OrganizationMembership).options(
            selectinload(OrganizationMembership.user)
        ).where(OrganizationMembership.organization_id == organization_id)
        if not include_inactive:
            stmt = stmt.where(
                OrganizationMembership.status.in_([
                    MembershipStatus.ACTIVE.value,
                    MembershipStatus.SUSPENDED.value,
                ])
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_org_members(self, organization_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def update_status(
        self, membership_id: uuid.UUID, status: str
    ) -> OrganizationMembership | None:
        membership = await self.get(membership_id)
        if membership:
            membership.status = status
            if status == MembershipStatus.ACTIVE.value and not membership.joined_at:
                membership.joined_at = datetime.now(timezone.utc)
            await self._session.flush()
        return membership
