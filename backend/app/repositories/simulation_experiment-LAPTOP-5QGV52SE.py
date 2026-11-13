"""Repository for SimulationExperiment CRUD operations."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.simulation_models import (
    SimulationExperiment,
    SimulationExperimentResult,
)
from app.repositories.base import BaseRepository


class SimulationExperimentRepository(BaseRepository[SimulationExperiment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SimulationExperiment)

    async def get_with_details(self, experiment_id: uuid.UUID) -> SimulationExperiment | None:
        stmt = (
            select(SimulationExperiment)
            .options(
                selectinload(SimulationExperiment.base_scenario),
                selectinload(SimulationExperiment.job),
                selectinload(SimulationExperiment.creator),
                selectinload(SimulationExperiment.results),
            )
            .where(SimulationExperiment.id == experiment_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SimulationExperiment], int]:
        base = select(SimulationExperiment).where(
            SimulationExperiment.created_by == user_id,
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            base
            .options(
                selectinload(SimulationExperiment.base_scenario),
                selectinload(SimulationExperiment.job),
            )
            .order_by(SimulationExperiment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_by_org(
        self,
        org_id: uuid.UUID | None,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SimulationExperiment], int]:
        base = select(SimulationExperiment)
        if org_id is not None:
            base = base.where(SimulationExperiment.organization_id == org_id)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            base
            .options(
                selectinload(SimulationExperiment.base_scenario),
                selectinload(SimulationExperiment.job),
                selectinload(SimulationExperiment.creator),
            )
            .order_by(SimulationExperiment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def count_active_by_org(self, org_id: uuid.UUID | None) -> int:
        stmt = select(func.count()).select_from(SimulationExperiment).where(
            SimulationExperiment.organization_id == org_id,
            SimulationExperiment.status.in_(["queued", "running"]),
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0


class SimulationExperimentResultRepository(
    BaseRepository[SimulationExperimentResult],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SimulationExperimentResult)

    async def list_by_experiment(
        self,
        experiment_id: uuid.UUID,
    ) -> list[SimulationExperimentResult]:
        stmt = (
            select(SimulationExperimentResult)
            .where(SimulationExperimentResult.experiment_id == experiment_id)
            .order_by(SimulationExperimentResult.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
