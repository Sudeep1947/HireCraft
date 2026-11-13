"""Organization repository for multi-tenant operations."""
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Organization)

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Organization | None:
        stmt = select(Organization).where(func.lower(Organization.name) == func.lower(name))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_memberships(self, org_id: uuid.UUID) -> Organization | None:
        stmt = (
            select(Organization)
            .options(selectinload(Organization.memberships))
            .where(Organization.id == org_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Organization]:
        stmt = select(Organization).where(Organization.status == "active")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, ids: list[uuid.UUID]) -> list[Organization]:
        if not ids:
            return []
        stmt = select(Organization).where(Organization.id.in_(ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
