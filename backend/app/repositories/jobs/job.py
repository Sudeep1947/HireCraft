import uuid
from datetime import datetime

from sqlalchemy import and_, asc, case, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, attributes, selectinload

from app.domain.enums import ScreeningStatus
from app.domain.models import (
    ApplicationStatusHistory,
    Job,
    JobApplication,
    SavedJob,
    ScreeningResult,
    User,
)
from app.repositories.base import BaseRepository


APPLICANT_SORT_ALIASES = {
    "newest": "newest",
    "-created_at": "newest",
    "oldest": "oldest",
    "created_at": "oldest",
    "score_high": "score_high",
    "-overall_match_score": "score_high",
    "score_low": "score_low",
    "overall_match_score": "score_low",
    "name_asc": "name_asc",
    "candidate_name": "name_asc",
    "name_desc": "name_desc",
    "-candidate_name": "name_desc",
    "status": "status_asc",
    "-status": "status_desc",
}


class JobRepository(BaseRepository[Job]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Job)

    async def list_by_recruiter(self, recruiter_id: uuid.UUID) -> list[Job]:
        stmt = select(Job).where(Job.recruiter_id == recruiter_id).order_by(Job.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_recruiter(self, job_id: uuid.UUID, recruiter_id: uuid.UUID) -> Job | None:
        stmt = select(Job).where(Job.id == job_id, Job.recruiter_id == recruiter_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        q: str | None = None,
        employment_type: str | None = None,
        location: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        skills: list[str] | None = None,
        status: str | None = "published",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        conditions = [Job.is_archived == False]
        if status:
            conditions.append(Job.status == status)
        else:
            conditions.append(Job.status.in_(["published", "closed"]))
        if q:
            conditions.append(
                or_(
                    Job.title.ilike(f"%{q}%"),
                    Job.company.ilike(f"%{q}%"),
                    Job.description.ilike(f"%{q}%"),
                    Job.location.ilike(f"%{q}%"),
                )
            )
        if employment_type:
            conditions.append(Job.employment_type == employment_type)
        if location:
            conditions.append(Job.location.ilike(f"%{location}%"))
        if salary_min is not None:
            conditions.append(
                or_(Job.salary_max >= salary_min, Job.salary_min >= salary_min)
            )
        if salary_max is not None:
            conditions.append(
                or_(Job.salary_min <= salary_max, Job.salary_max <= salary_max)
            )
        if skills:
            for skill in skills:
                conditions.append(Job.required_skills.any(skill))

        stmt_count = select(func.count()).select_from(Job).where(*conditions)
        total_result = await self._session.execute(stmt_count)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = select(Job).where(*conditions).order_by(Job.created_at.desc()).offset(offset).limit(page_size)
        result = await self._session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def increment_version(self, job_id: uuid.UUID) -> Job | None:
        stmt = (
            update(Job).where(Job.id == job_id).values(version=Job.version + 1).returning(Job)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()


class JobApplicationRepository(BaseRepository[JobApplication]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, JobApplication)

    async def list_by_job(self, job_id: uuid.UUID) -> list[JobApplication]:
        stmt = (
            select(JobApplication)
            .options(selectinload(JobApplication.recruiter_notes))
            .where(JobApplication.job_id == job_id)
            .order_by(JobApplication.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _applicant_search_pattern(query: str) -> str:
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def _build_applicant_query(
        self,
        job_id: uuid.UUID,
        *,
        q: str | None = None,
        application_status: str | None = None,
        screening_status: str | None = None,
        recommendation: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
    ):
        candidate_user = aliased(User)
        screening = aliased(ScreeningResult)
        conditions = [JobApplication.job_id == job_id]

        if q:
            pattern = self._applicant_search_pattern(q)
            conditions.append(
                or_(
                    candidate_user.full_name.ilike(pattern, escape="\\"),
                    candidate_user.email.ilike(pattern, escape="\\"),
                )
            )
        if application_status:
            conditions.append(JobApplication.status == application_status)
        if screening_status:
            effective_status = case(
                (screening.id.is_not(None), ScreeningStatus.COMPLETED.value),
                else_=JobApplication.screening_status,
            )
            conditions.append(effective_status == screening_status)
        if recommendation:
            conditions.append(screening.recommendation == recommendation)
        if min_score is not None:
            conditions.append(screening.overall_match_score >= min_score)
        if max_score is not None:
            conditions.append(screening.overall_match_score <= max_score)

        query = (
            select(JobApplication, screening)
            .outerjoin(
                screening,
                and_(
                    screening.job_id == JobApplication.job_id,
                    screening.candidate_id == JobApplication.candidate_id,
                ),
            )
            .outerjoin(candidate_user, candidate_user.id == JobApplication.candidate_id)
            .where(*conditions)
        )
        return query, conditions, candidate_user, screening

    def _applicant_options(self):
        return (
            selectinload(JobApplication.candidate),
            selectinload(JobApplication.job),
            selectinload(JobApplication.recruiter_notes),
        )

    def _materialize_applicants(self, result) -> list[JobApplication]:
        applications: list[JobApplication] = []
        for application, screening in result.unique().all():
            attributes.set_committed_value(
                application,
                "screening_result",
                [screening] if screening is not None else [],
            )
            applications.append(application)
        return applications

    async def list_filtered_by_job(
        self,
        job_id: uuid.UUID,
        *,
        q: str | None = None,
        application_status: str | None = None,
        screening_status: str | None = None,
        recommendation: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        sort_by: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobApplication], int]:
        q = q.strip() if q else None
        sort_by = APPLICANT_SORT_ALIASES.get(sort_by, sort_by)
        query, conditions, candidate_user, screening = self._build_applicant_query(
            job_id,
            q=q,
            application_status=application_status,
            screening_status=screening_status,
            recommendation=recommendation,
            min_score=min_score,
            max_score=max_score,
        )

        count_stmt = (
            select(func.count(func.distinct(JobApplication.id)))
            .select_from(JobApplication)
            .outerjoin(
                screening,
                and_(
                    screening.job_id == JobApplication.job_id,
                    screening.candidate_id == JobApplication.candidate_id,
                ),
            )
            .outerjoin(candidate_user, candidate_user.id == JobApplication.candidate_id)
            .where(*conditions)
        )
        total = (await self._session.execute(count_stmt)).scalar() or 0

        if sort_by == "oldest":
            order_by = (asc(JobApplication.created_at), asc(JobApplication.id))
        elif sort_by == "score_high":
            order_by = (
                asc(case((screening.overall_match_score.is_(None), 1), else_=0)),
                desc(screening.overall_match_score),
                desc(JobApplication.created_at),
                asc(JobApplication.id),
            )
        elif sort_by == "score_low":
            order_by = (
                asc(case((screening.overall_match_score.is_(None), 1), else_=0)),
                asc(screening.overall_match_score),
                desc(JobApplication.created_at),
                asc(JobApplication.id),
            )
        elif sort_by == "name_asc":
            order_by = (asc(candidate_user.full_name), asc(JobApplication.id))
        elif sort_by == "name_desc":
            order_by = (desc(candidate_user.full_name), asc(JobApplication.id))
        elif sort_by == "status_asc":
            order_by = (asc(JobApplication.status), asc(JobApplication.id))
        elif sort_by == "status_desc":
            order_by = (desc(JobApplication.status), asc(JobApplication.id))
        else:
            order_by = (desc(JobApplication.created_at), asc(JobApplication.id))

        stmt = (
            query.options(*self._applicant_options())
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return self._materialize_applicants(result), int(total)

    async def list_all_with_screening_by_job(
        self, job_id: uuid.UUID,
    ) -> list[JobApplication]:
        query, _, _, _ = self._build_applicant_query(job_id)
        stmt = query.options(*self._applicant_options()).order_by(
            asc(JobApplication.created_at), asc(JobApplication.id),
        )
        result = await self._session.execute(stmt)
        return self._materialize_applicants(result)

    @staticmethod
    def _dashboard_value(value) -> str:
        if value is None:
            return ""
        return value.value if hasattr(value, "value") else str(value)

    async def get_dashboard_summary(self, job_id: uuid.UUID) -> dict:
        screening = aliased(ScreeningResult)
        screening_join = and_(
            screening.job_id == JobApplication.job_id,
            screening.candidate_id == JobApplication.candidate_id,
        )
        aggregate_stmt = (
            select(
                func.count(func.distinct(JobApplication.id)).label("total_applicants"),
                func.count(func.distinct(screening.id)).label("total_screened"),
                func.avg(screening.overall_match_score).label("average_score"),
                func.coalesce(
                    func.sum(
                        case(
                            (screening.overall_match_score >= 80, 1),
                            else_=0,
                        ),
                    ),
                    0,
                ).label("high_match_count"),
            )
            .select_from(JobApplication)
            .outerjoin(screening, screening_join)
            .where(JobApplication.job_id == job_id)
        )
        aggregate = (await self._session.execute(aggregate_stmt)).one()

        status_rows = (
            await self._session.execute(
                select(JobApplication.status, func.count(JobApplication.id))
                .where(JobApplication.job_id == job_id)
                .group_by(JobApplication.status),
            )
        ).all()
        status_breakdown = {
            self._dashboard_value(status): int(count)
            for status, count in status_rows
        }

        screening_rows = (
            await self._session.execute(
                select(
                    JobApplication.screening_status,
                    func.count(JobApplication.id),
                    func.count(screening.id),
                )
                .outerjoin(screening, screening_join)
                .where(JobApplication.job_id == job_id)
                .group_by(JobApplication.screening_status),
            )
        ).all()
        screening_breakdown = {
            status.value: 0 for status in ScreeningStatus
        }
        for raw_status, total_count, result_count in screening_rows:
            status_value = self._dashboard_value(raw_status) or ScreeningStatus.NOT_STARTED.value
            total_count = int(total_count or 0)
            result_count = int(result_count or 0)
            if status_value == ScreeningStatus.COMPLETED.value:
                screening_breakdown[ScreeningStatus.COMPLETED.value] += total_count
                continue
            screening_breakdown[ScreeningStatus.COMPLETED.value] += result_count
            remaining_count = total_count - result_count
            if remaining_count:
                screening_breakdown.setdefault(status_value, 0)
                screening_breakdown[status_value] += remaining_count

        recommendation_rows = (
            await self._session.execute(
                select(screening.recommendation, func.count(screening.id))
                .select_from(JobApplication)
                .outerjoin(screening, screening_join)
                .where(JobApplication.job_id == job_id, screening.id.is_not(None))
                .group_by(screening.recommendation),
            )
        ).all()
        strength_rows = (
            await self._session.execute(
                select(screening.strength_level, func.count(screening.id))
                .select_from(JobApplication)
                .outerjoin(screening, screening_join)
                .where(JobApplication.job_id == job_id, screening.id.is_not(None))
                .group_by(screening.strength_level),
            )
        ).all()
        average_score = aggregate.average_score
        return {
            "job_id": job_id,
            "total_applicants": int(aggregate.total_applicants or 0),
            "total_screened": int(aggregate.total_screened or 0),
            "not_screened": screening_breakdown.get(ScreeningStatus.NOT_STARTED.value, 0),
            "queued": screening_breakdown.get(ScreeningStatus.QUEUED.value, 0),
            "running": screening_breakdown.get(ScreeningStatus.RUNNING.value, 0),
            "failed": screening_breakdown.get(ScreeningStatus.FAILED.value, 0),
            "skipped": screening_breakdown.get(ScreeningStatus.SKIPPED.value, 0),
            "average_score": float(average_score) if average_score is not None else None,
            "high_match_count": int(aggregate.high_match_count or 0),
            "status_breakdown": status_breakdown,
            "application_status_breakdown": status_breakdown,
            "screening_status_breakdown": screening_breakdown,
            "recommendation_breakdown": {
                self._dashboard_value(recommendation): int(count)
                for recommendation, count in recommendation_rows
            },
            "strength_level_breakdown": {
                self._dashboard_value(strength): int(count)
                for strength, count in strength_rows
            },
        }

    async def list_by_candidate(self, candidate_id: uuid.UUID) -> list[JobApplication]:
        stmt = select(JobApplication).where(JobApplication.candidate_id == candidate_id).order_by(JobApplication.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_job_and_candidate(self, job_id: uuid.UUID, candidate_id: uuid.UUID) -> JobApplication | None:
        stmt = select(JobApplication).where(
            JobApplication.job_id == job_id,
            JobApplication.candidate_id == candidate_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_job(self, job_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(JobApplication).where(JobApplication.job_id == job_id)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def update_status(self, application_id: uuid.UUID, status: str) -> JobApplication | None:
        stmt = (
            update(JobApplication)
            .where(JobApplication.id == application_id)
            .values(status=status)
            .returning(JobApplication)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def update_status_if_current(
        self,
        application_id: uuid.UUID,
        expected_status: str,
        new_status: str,
        **extra: object,
    ) -> JobApplication | None:
        """Compare-and-swap status update.

        Only flips the row when its status still equals ``expected_status``.
        Returns the updated application on success, ``None`` when a concurrent
        change made ``expected_status`` stale.
        """
        stmt = (
            update(JobApplication)
            .where(
                JobApplication.id == application_id,
                JobApplication.status == expected_status,
            )
            .values(status=new_status, **extra)
            .returning(JobApplication)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def set_screening_queued(
        self, application_id: uuid.UUID, task_id: str | None = None,
    ) -> JobApplication | None:
        stmt = (
            update(JobApplication)
            .where(JobApplication.id == application_id)
            .values(
                screening_status=ScreeningStatus.QUEUED.value,
                screening_task_id=task_id,
            )
            .returning(JobApplication)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def claim_screening(
        self,
        application_id: uuid.UUID,
        expected_statuses: list[str],
        started_at: datetime,
        task_id: str | None = None,
    ) -> JobApplication | None:
        """Atomically move an application's screening into RUNNING.

        Only claims rows whose ``screening_status`` is still one of
        ``expected_statuses``; returns ``None`` when another worker already
        claimed or finished it. ``screening_attempts`` is incremented on every
        successful claim.
        """
        stmt = (
            update(JobApplication)
            .where(
                JobApplication.id == application_id,
                JobApplication.screening_status.in_(expected_statuses),
            )
            .values(
                screening_status=ScreeningStatus.RUNNING.value,
                screening_attempts=JobApplication.screening_attempts + 1,
                screening_started_at=started_at,
                screening_completed_at=None,
                screening_error=None,
                screening_task_id=task_id,
            )
            .returning(JobApplication)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def finish_screening(
        self,
        application_id: uuid.UUID,
        status: ScreeningStatus,
        completed_at: datetime,
        error: str | None = None,
    ) -> JobApplication | None:
        stmt = (
            update(JobApplication)
            .where(JobApplication.id == application_id)
            .values(
                screening_status=status.value,
                screening_completed_at=completed_at,
                screening_error=error,
            )
            .returning(JobApplication)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()


class ApplicationStatusHistoryRepository(BaseRepository[ApplicationStatusHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ApplicationStatusHistory)

    async def list_by_application(
        self, application_id: uuid.UUID, limit: int = 100,
    ) -> list[ApplicationStatusHistory]:
        stmt = (
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id == application_id)
            .order_by(ApplicationStatusHistory.changed_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class SavedJobRepository(BaseRepository[SavedJob]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SavedJob)

    async def list_by_candidate(self, candidate_id: uuid.UUID) -> list[SavedJob]:
        stmt = select(SavedJob).where(SavedJob.candidate_id == candidate_id).order_by(SavedJob.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def is_saved(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        stmt = select(SavedJob).where(
            SavedJob.candidate_id == candidate_id,
            SavedJob.job_id == job_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def remove(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        stmt = select(SavedJob).where(
            SavedJob.candidate_id == candidate_id,
            SavedJob.job_id == job_id,
        )
        result = await self._session.execute(stmt)
        saved = result.scalar_one_or_none()
        if saved:
            await self._session.delete(saved)
            await self._session.flush()
            return True
        return False
