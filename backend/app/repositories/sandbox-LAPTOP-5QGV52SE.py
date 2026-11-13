"""Repository for Hiring Strategy Sandbox persistence."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.hiring_strategy_sandbox_models import (
    HiringStrategySandbox,
    SandboxStrategy,
)
from app.repositories.base import BaseRepository


class SandboxRepository(BaseRepository[HiringStrategySandbox]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HiringStrategySandbox)

    async def get_with_details(self, sandbox_id: uuid.UUID) -> HiringStrategySandbox | None:
        stmt = (
            select(HiringStrategySandbox)
            .options(
                selectinload(HiringStrategySandbox.job),
                selectinload(HiringStrategySandbox.creator),
                selectinload(HiringStrategySandbox.organization),
                selectinload(HiringStrategySandbox.strategies).selectinload(SandboxStrategy.scenario),
            )
            .where(HiringStrategySandbox.id == sandbox_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_visible(
        self, user_id: uuid.UUID, organization_ids: list[uuid.UUID],
    ) -> list[HiringStrategySandbox]:
        stmt = (
            select(HiringStrategySandbox)
            .options(
                selectinload(HiringStrategySandbox.job),
                selectinload(HiringStrategySandbox.creator),
            )
            .where(
                (HiringStrategySandbox.created_by == user_id)
                | (
                    HiringStrategySandbox.organization_id.is_not(None)
                    & HiringStrategySandbox.organization_id.in_(organization_ids)
                )
            )
            .order_by(HiringStrategySandbox.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_strategies(self, sandbox_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(SandboxStrategy).where(
            SandboxStrategy.sandbox_id == sandbox_id
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_completed_strategies(self, sandbox_id: uuid.UUID) -> int:
        from app.domain.simulation_models import SimulationScenario
        stmt = (
            select(func.count())
            .select_from(SandboxStrategy)
            .join(SimulationScenario, SandboxStrategy.scenario_id == SimulationScenario.id)
            .where(
                SandboxStrategy.sandbox_id == sandbox_id,
                SimulationScenario.status == "completed",
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0


class SandboxStrategyRepository(BaseRepository[SandboxStrategy]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SandboxStrategy)

    async def get_with_scenario(self, strategy_id: uuid.UUID) -> SandboxStrategy | None:
        stmt = (
            select(SandboxStrategy)
            .options(
                selectinload(SandboxStrategy.scenario),
                selectinload(SandboxStrategy.parent_strategy),
            )
            .where(SandboxStrategy.id == strategy_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxStrategy]:
        stmt = (
            select(SandboxStrategy)
            .options(
                selectinload(SandboxStrategy.scenario),
                selectinload(SandboxStrategy.parent_strategy),
            )
            .where(SandboxStrategy.sandbox_id == sandbox_id)
            .order_by(SandboxStrategy.sort_order, SandboxStrategy.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_scenario(self, scenario_id: uuid.UUID) -> SandboxStrategy | None:
        stmt = select(SandboxStrategy).where(SandboxStrategy.scenario_id == scenario_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
