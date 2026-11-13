"""Repository for SimulationReport persistence."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.simulation_models import SimulationReport
from app.repositories.base import BaseRepository


class SimulationReportRepository(BaseRepository[SimulationReport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SimulationReport)

    async def get_with_details(self, report_id: uuid.UUID) -> SimulationReport | None:
        stmt = (
            select(SimulationReport)
            .options(
                selectinload(SimulationReport.scenario),
                selectinload(SimulationReport.execution),
                selectinload(SimulationReport.sandbox),
                selectinload(SimulationReport.job),
                selectinload(SimulationReport.creator),
                selectinload(SimulationReport.organization),
            )
            .where(SimulationReport.id == report_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        organization_ids: list[uuid.UUID],
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SimulationReport], int]:
        base_filter = (
            (SimulationReport.created_by == user_id)
            | (
                SimulationReport.organization_id.is_not(None)
                & SimulationReport.organization_id.in_(organization_ids)
            )
        )

        count_stmt = select(func.count()).select_from(SimulationReport).where(base_filter)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(SimulationReport)
            .options(
                selectinload(SimulationReport.scenario),
                selectinload(SimulationReport.job),
                selectinload(SimulationReport.sandbox),
                selectinload(SimulationReport.creator),
            )
            .where(base_filter)
            .order_by(SimulationReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_by_scenario(
        self, scenario_id: uuid.UUID,
    ) -> list[SimulationReport]:
        stmt = (
            select(SimulationReport)
            .where(SimulationReport.scenario_id == scenario_id)
            .order_by(SimulationReport.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_sandbox(
        self, sandbox_id: uuid.UUID,
    ) -> list[SimulationReport]:
        stmt = (
            select(SimulationReport)
            .where(SimulationReport.sandbox_id == sandbox_id)
            .order_by(SimulationReport.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_existing(
        self,
        scenario_id: uuid.UUID | None,
        execution_id: uuid.UUID | None,
        report_type: str,
        report_format: str,
    ) -> SimulationReport | None:
        """Find an existing completed report for the same scenario/execution/type/format."""
        filters = [
            SimulationReport.status == "completed",
            SimulationReport.report_type == report_type,
            SimulationReport.format == report_format,
        ]
        if scenario_id:
            filters.append(SimulationReport.scenario_id == scenario_id)
        if execution_id:
            filters.append(SimulationReport.execution_id == execution_id)

        stmt = select(SimulationReport).where(*filters).order_by(
            SimulationReport.created_at.desc(),
        ).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
