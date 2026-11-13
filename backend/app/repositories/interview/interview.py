import uuid
from collections.abc import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import (
    CodingAssessment,
    Interview,
    InterviewAnswer,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewScorecard,
)
from app.repositories.base import BaseRepository


class InterviewRepository(BaseRepository[Interview]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Interview)

    async def get_with_questions(self, interview_id: uuid.UUID) -> Interview | None:
        stmt = (
            select(Interview)
            .options(selectinload(Interview.questions).selectinload(InterviewQuestion.answer).selectinload(InterviewAnswer.evaluation))
            .options(selectinload(Interview.scorecard))
            .where(Interview.id == interview_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_candidate(self, candidate_id: uuid.UUID) -> list[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.candidate_id == candidate_id)
            .order_by(Interview.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_recruiter(self, recruiter_id: uuid.UUID) -> list[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.recruiter_id == recruiter_id)
            .order_by(Interview.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_job(self, job_id: uuid.UUID) -> list[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.job_id == job_id)
            .order_by(Interview.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_jobs(
        self, job_ids: Sequence[uuid.UUID],
    ) -> list[Interview]:
        """Every interview belonging to any of the given jobs.

        The tenant boundary for aggregate reporting: the caller resolves which
        jobs it may read with ``authorized_job_ids`` and the filter is applied in
        the query, so an organization-wide report can never reach another
        tenant's interviews.

        An empty list returns nothing rather than an unbounded query, so a caller
        with no visible jobs gets an empty report instead of everyone's.
        """
        if not job_ids:
            return []
        stmt = (
            select(Interview)
            .where(Interview.job_id.in_(list(job_ids)))
            .order_by(Interview.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Phase 11: application-linked lookups ───────────────────────
    #
    # These deliberately do NOT eager-load questions, answers, evaluations or
    # the scorecard. The application evidence panels render one row per
    # interview and the detail/scorecard endpoints already load the heavy graph
    # on demand, so selectinloading it here would multiply the row count of
    # every application list view by the size of every interview.

    async def list_by_application(
        self, application_id: uuid.UUID,
    ) -> list[Interview]:
        """Every interview linked to one application, oldest first.

        Ordering by ``scheduled_at`` keeps a rescheduled interview in the
        position a recruiter expects rather than reordering the list on each
        change, with ``created_at`` as a stable tiebreaker for interviews that
        have no scheduled time yet.
        """
        stmt = (
            select(Interview)
            .options(selectinload(Interview.recruiter))
            .where(Interview.application_id == application_id)
            .order_by(
                Interview.scheduled_at.asc().nulls_last(),
                Interview.created_at.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_application(
        self, application_id: uuid.UUID, interview_id: uuid.UUID,
    ) -> Interview | None:
        """Fetch one interview *scoped to* its application.

        The application id is part of the predicate rather than checked after
        the load, so an interview belonging to a different application can never
        be returned and then filtered: there is no window in which a row for
        another application is loaded at all.
        """
        stmt = (
            select(Interview)
            .options(selectinload(Interview.recruiter))
            .where(
                Interview.id == interview_id,
                Interview.application_id == application_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_application(
        self, application_id: uuid.UUID,
    ) -> Interview | None:
        """The first still-open interview for an application, if any.

        Used to keep a retried schedule request from creating a second live
        interview for the same application. "Open" means scheduled or in
        progress; a cancelled or completed interview no longer blocks a new one.
        """
        stmt = (
            select(Interview)
            .options(selectinload(Interview.recruiter))
            .where(
                Interview.application_id == application_id,
                Interview.status.in_(["scheduled", "in_progress"]),
            )
            .order_by(Interview.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_upcoming_by_candidate(self, candidate_id: uuid.UUID) -> list[Interview]:
        from datetime import datetime, timezone
        stmt = (
            select(Interview)
            .where(
                Interview.candidate_id == candidate_id,
                Interview.status.in_(["scheduled", "in_progress"]),
                Interview.scheduled_at >= datetime.now(timezone.utc),
            )
            .order_by(Interview.scheduled_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_upcoming_by_recruiter(self, recruiter_id: uuid.UUID) -> list[Interview]:
        from datetime import datetime, timezone
        stmt = (
            select(Interview)
            .where(
                Interview.recruiter_id == recruiter_id,
                Interview.status.in_(["scheduled", "in_progress"]),
                Interview.scheduled_at >= datetime.now(timezone.utc),
            )
            .order_by(Interview.scheduled_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_completed(self, candidate_id: uuid.UUID | None = None, recruiter_id: uuid.UUID | None = None) -> int:
        stmt = select(func.count(Interview.id)).where(Interview.status == "completed")
        if candidate_id:
            stmt = stmt.where(Interview.candidate_id == candidate_id)
        if recruiter_id:
            stmt = stmt.where(Interview.recruiter_id == recruiter_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def avg_score(
        self,
        candidate_id: uuid.UUID | None = None,
        recruiter_id: uuid.UUID | None = None,
    ) -> float:
        """Mean scorecard score across completed interviews.

        Both scopes are honoured. A caller that passes neither aggregates every
        completed interview on the platform, so the recruiter dashboard used to
        report a cross-tenant average sitting next to correctly scoped totals
        and completed counts on the same screen.
        """
        stmt = (
            select(func.avg(InterviewScorecard.overall_score))
            .join(Interview, InterviewScorecard.interview_id == Interview.id)
            .where(Interview.status == "completed")
        )
        if candidate_id:
            stmt = stmt.where(Interview.candidate_id == candidate_id)
        if recruiter_id:
            stmt = stmt.where(Interview.recruiter_id == recruiter_id)
        result = await self._session.execute(stmt)
        avg = result.scalar_one()
        return float(avg) if avg else 0.0

    async def count_total(self, candidate_id: uuid.UUID | None = None, recruiter_id: uuid.UUID | None = None) -> int:
        stmt = select(func.count(Interview.id))
        if candidate_id:
            stmt = stmt.where(Interview.candidate_id == candidate_id)
        if recruiter_id:
            stmt = stmt.where(Interview.recruiter_id == recruiter_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()


class InterviewQuestionRepository(BaseRepository[InterviewQuestion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InterviewQuestion)

    async def list_by_interview(self, interview_id: uuid.UUID) -> list[InterviewQuestion]:
        stmt = (
            select(InterviewQuestion)
            .where(InterviewQuestion.interview_id == interview_id)
            .order_by(InterviewQuestion.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_unanswered(self, interview_id: uuid.UUID) -> InterviewQuestion | None:
        stmt = (
            select(InterviewQuestion)
            .outerjoin(InterviewAnswer, InterviewQuestion.id == InterviewAnswer.question_id)
            .where(
                InterviewQuestion.interview_id == interview_id,
                InterviewAnswer.id.is_(None),
            )
            .order_by(InterviewQuestion.order_index)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class InterviewAnswerRepository(BaseRepository[InterviewAnswer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InterviewAnswer)

    async def get_by_question(self, question_id: uuid.UUID) -> InterviewAnswer | None:
        stmt = select(InterviewAnswer).where(InterviewAnswer.question_id == question_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_interview(self, interview_id: uuid.UUID) -> list[InterviewAnswer]:
        stmt = (
            select(InterviewAnswer)
            .join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)
            .where(InterviewQuestion.interview_id == interview_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class InterviewEvaluationRepository(BaseRepository[InterviewEvaluation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InterviewEvaluation)

    async def get_by_answer(self, answer_id: uuid.UUID) -> InterviewEvaluation | None:
        stmt = select(InterviewEvaluation).where(InterviewEvaluation.answer_id == answer_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_interview(self, interview_id: uuid.UUID) -> list[InterviewEvaluation]:
        stmt = (
            select(InterviewEvaluation)
            .join(InterviewAnswer, InterviewEvaluation.answer_id == InterviewAnswer.id)
            .join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)
            .where(InterviewQuestion.interview_id == interview_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class InterviewScorecardRepository(BaseRepository[InterviewScorecard]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InterviewScorecard)

    async def get_by_interview(self, interview_id: uuid.UUID) -> InterviewScorecard | None:
        stmt = select(InterviewScorecard).where(InterviewScorecard.interview_id == interview_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_candidate(self, candidate_id: uuid.UUID) -> list[InterviewScorecard]:
        stmt = (
            select(InterviewScorecard)
            .join(Interview, InterviewScorecard.interview_id == Interview.id)
            .where(Interview.candidate_id == candidate_id)
            .order_by(InterviewScorecard.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CodingAssessmentRepository(BaseRepository[CodingAssessment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CodingAssessment)

    async def list_by_interview(self, interview_id: uuid.UUID) -> list[CodingAssessment]:
        stmt = (
            select(CodingAssessment)
            .where(CodingAssessment.interview_id == interview_id)
            .order_by(CodingAssessment.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
