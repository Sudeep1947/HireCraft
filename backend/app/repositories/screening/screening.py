import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import CandidateRanking, ScreeningResult, SkillGapAnalysis
from app.repositories.base import BaseRepository


class ScreeningResultRepository(BaseRepository[ScreeningResult]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ScreeningResult)

    async def get_by_job_and_candidate(
        self, job_id: uuid.UUID, candidate_id: uuid.UUID,
    ) -> ScreeningResult | None:
        stmt = select(ScreeningResult).where(
            ScreeningResult.job_id == job_id,
            ScreeningResult.candidate_id == candidate_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_application(
        self, application_id: uuid.UUID,
    ) -> ScreeningResult | None:
        stmt = select(ScreeningResult).where(
            ScreeningResult.application_id == application_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_job(self, job_id: uuid.UUID) -> list[ScreeningResult]:
        stmt = (
            select(ScreeningResult)
            .where(ScreeningResult.job_id == job_id)
            .order_by(ScreeningResult.overall_match_score.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_candidate(self, candidate_id: uuid.UUID) -> list[ScreeningResult]:
        stmt = (
            select(ScreeningResult)
            .where(ScreeningResult.candidate_id == candidate_id)
            .order_by(ScreeningResult.overall_match_score.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_job(self, job_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(ScreeningResult).where(
            ScreeningResult.job_id == job_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0


class CandidateRankingRepository(BaseRepository[CandidateRanking]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CandidateRanking)

    async def get_by_job_and_candidate(
        self, job_id: uuid.UUID, candidate_id: uuid.UUID,
    ) -> CandidateRanking | None:
        stmt = select(CandidateRanking).where(
            CandidateRanking.job_id == job_id,
            CandidateRanking.candidate_id == candidate_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_job(self, job_id: uuid.UUID) -> list[CandidateRanking]:
        stmt = (
            select(CandidateRanking)
            .where(CandidateRanking.job_id == job_id)
            .order_by(CandidateRanking.rank.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_job(self, job_id: uuid.UUID) -> None:
        stmt = select(CandidateRanking).where(CandidateRanking.job_id == job_id)
        result = await self._session.execute(stmt)
        for row in result.scalars().all():
            await self._session.delete(row)
        await self._session.flush()


class SkillGapAnalysisRepository(BaseRepository[SkillGapAnalysis]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SkillGapAnalysis)

    async def get_by_screening_result(
        self, screening_result_id: uuid.UUID,
    ) -> SkillGapAnalysis | None:
        stmt = select(SkillGapAnalysis).where(
            SkillGapAnalysis.screening_result_id == screening_result_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
