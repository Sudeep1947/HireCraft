"""Interview Analytics Engine."""

from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Interview, InterviewScorecard, Job
from app.repositories.interview.interview import (
    InterviewRepository,
    InterviewScorecardRepository,
)


class InterviewAnalytics:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.interview_repo = InterviewRepository(session)
        self.scorecard_repo = InterviewScorecardRepository(session)

    async def get_analytics(
        self,
        recruiter_id: uuid.UUID | None = None,
        candidate_id: uuid.UUID | None = None,
        job_ids: list[uuid.UUID] | None = None,
    ) -> dict:
        """Aggregate interview outcomes for one audience.

        Exactly one scope is honoured: a candidate's own interviews, a single
        recruiter's, or the set of jobs the caller may read. When no scope is
        given there is nothing to aggregate over, and an empty report is the
        correct answer -- the previous fallback here called ``uuid.UUID(int())``
        with no argument, so an HR caller raised a TypeError, and "fixing" it by
        dropping the filter would have turned the endpoint into a cross-tenant
        read of every interview's scores and recommendations.
        """
        if candidate_id:
            interviews = await self.interview_repo.list_by_candidate(candidate_id)
        elif recruiter_id:
            interviews = await self.interview_repo.list_by_recruiter(recruiter_id)
        elif job_ids is not None:
            interviews = await self.interview_repo.list_by_jobs(job_ids)
        else:
            interviews = []

        total = len(interviews)
        completed = [iv for iv in interviews if iv.status == "completed"]
        completion_rate = (len(completed) / total * 100) if total > 0 else 0

        scores = []
        for iv in completed:
            sc = await self.scorecard_repo.get_by_interview(iv.id)
            if sc:
                scores.append(sc.overall_score)

        avg_score = sum(scores) / len(scores) if scores else 0
        sorted_scores = sorted(scores)
        median_score = (
            sorted_scores[len(sorted_scores) // 2]
            if sorted_scores
            else 0
        )

        score_dist = {"excellent": 0, "good": 0, "average": 0, "below_average": 0}
        for s in scores:
            if s >= 80:
                score_dist["excellent"] += 1
            elif s >= 65:
                score_dist["good"] += 1
            elif s >= 45:
                score_dist["average"] += 1
            else:
                score_dist["below_average"] += 1

        category_perf = await self._category_performance(completed)
        difficulty_dist = self._difficulty_distribution(interviews)
        rec_breakdown = await self._recommendation_breakdown(completed)
        skill_perf = await self._skill_performance(completed)
        trends = await self._compute_trends(completed)

        return {
            "total_interviews": total,
            "completion_rate": round(completion_rate, 1),
            "average_score": round(avg_score, 1),
            "median_score": median_score,
            "score_distribution": score_dist,
            "category_averages": category_perf,
            "difficulty_distribution": difficulty_dist,
            "recommendation_breakdown": rec_breakdown,
            "skill_performance": skill_perf,
            "hiring_prediction": {
                "likely_hire_pct": score_dist["excellent"] + score_dist["good"],
                "needs_review_pct": score_dist["average"],
                "unlikely_hire_pct": score_dist["below_average"],
            },
            "trends": trends,
        }

    async def _category_performance(self, completed: list[Interview]) -> dict:
        """The average evaluated score of each question category.

        One joined query for every completed interview, instead of fetching each
        interview's questions and then reading the ``question.answer.evaluation``
        relationship chain. That chain is lazily loaded, and a lazy load raises
        MissingGreenlet in an async session -- which is what made this endpoint
        answer 500 for any recruiter with a single completed, answered
        interview, and therefore what made the Interview Analytics page show
        only its generic "Failed to load analytics" error. Selecting the two
        columns with explicit joins keeps every read inside the request's own
        await, and as a side effect replaces the per-interview N+1 with one
        query for the whole report.
        """
        if not completed:
            return {}

        from app.domain.models import (
            InterviewAnswer,
            InterviewEvaluation,
            InterviewQuestion,
        )

        stmt = (
            select(InterviewQuestion.category, InterviewEvaluation.overall_score)
            .select_from(InterviewQuestion)
            .join(
                InterviewAnswer,
                InterviewAnswer.question_id == InterviewQuestion.id,
            )
            .join(
                InterviewEvaluation,
                InterviewEvaluation.answer_id == InterviewAnswer.id,
            )
            .where(
                InterviewQuestion.interview_id.in_([iv.id for iv in completed])
            )
        )
        result = await self.session.execute(stmt)

        category_scores: dict[str, list[int]] = {}
        for category, score in result.all():
            category_scores.setdefault(category, []).append(score)

        return {
            cat: round(sum(scores) / len(scores), 1)
            for cat, scores in category_scores.items()
        }

    @staticmethod
    def _difficulty_distribution(interviews: list[Interview]) -> dict:
        from app.repositories.interview.interview import InterviewQuestionRepository
        dist = {"easy": 0, "medium": 0, "hard": 0}
        for iv in interviews:
            if iv.total_questions:
                if iv.interview_type == "mock":
                    dist["medium"] += iv.total_questions
                else:
                    dist["medium"] += iv.total_questions
        return dist

    async def _recommendation_breakdown(self, completed: list[Interview]) -> dict:
        breakdown = {"strongly_recommend": 0, "recommend": 0, "consider": 0, "not_recommended": 0}
        for iv in completed:
            sc = await self.scorecard_repo.get_by_interview(iv.id)
            if sc and sc.recommendation in breakdown:
                breakdown[sc.recommendation] += 1
        return breakdown

    async def _skill_performance(self, completed: list[Interview]) -> dict:
        all_scores: list[int] = []
        for iv in completed:
            sc = await self.scorecard_repo.get_by_interview(iv.id)
            if sc:
                all_scores.append(sc.technical_skills)

        if not all_scores:
            return {}

        return {
            "technical_skills_avg": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
            "total_evaluated": len(all_scores),
        }

    async def _compute_trends(self, completed: list[Interview]) -> list[dict]:
        monthly: dict[str, list[int]] = {}
        for iv in completed:
            if iv.completed_at:
                month_key = iv.completed_at.strftime("%Y-%m")
                sc = await self.scorecard_repo.get_by_interview(iv.id)
                if sc:
                    if month_key not in monthly:
                        monthly[month_key] = []
                    monthly[month_key].append(sc.overall_score)

        trends = []
        for month in sorted(monthly.keys()):
            scores = monthly[month]
            trends.append({
                "month": month,
                "count": len(scores),
                "average_score": round(sum(scores) / len(scores), 1),
            })
        return trends
