"""Main Interview Service — orchestrates all interview operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Interview, Job, User
from app.domain.enums import InterviewType
from app.repositories.interview.interview import (
    InterviewAnswerRepository,
    InterviewQuestionRepository,
    InterviewRepository,
    InterviewScorecardRepository,
)
from app.repositories.candidate.profile import CandidateProfileRepository
from app.repositories.jobs.job import JobRepository
from app.services.interview.answer_evaluator import AnswerEvaluator
from app.services.interview.interview_room_service import room_id_for
from app.services.interview.mock_interview import MockInterviewService
from app.services.interview.question_generator import QuestionGenerator
from app.services.interview.scorecard_engine import ScorecardEngine


class InterviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.interview_repo = InterviewRepository(session)
        self.question_repo = InterviewQuestionRepository(session)
        self.answer_repo = InterviewAnswerRepository(session)
        self.scorecard_repo = InterviewScorecardRepository(session)
        self.job_repo = JobRepository(session)
        self.profile_repo = CandidateProfileRepository(session)

    # ─── Generate Questions ───────────────────────────────────────

    async def generate_questions(
        self,
        job_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        categories: list[str] | None = None,
        difficulty: str = "medium",
        count: int = 10,
        candidate_id: uuid.UUID | None = None,
    ) -> dict:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            job = await self.session.get(Job, job_id)
            if not job:
                raise ValueError("Job not found")

        candidate_skills = []
        candidate_projects = []
        candidate_experience = []
        if candidate_id:
            profile = await self.profile_repo.get_by_user_id(candidate_id)
            if profile:
                from sqlalchemy import select
                from app.domain.models import CandidateSkill, Skill, Project, Experience
                skill_stmt = (
                    select(Skill.name)
                    .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
                    .where(CandidateSkill.profile_id == profile.id)
                )
                result = await self.session.execute(skill_stmt)
                candidate_skills = list(result.scalars().all())

                proj_stmt = select(Project.title).where(Project.profile_id == profile.id)
                result = await self.session.execute(proj_stmt)
                candidate_projects = list(result.scalars().all())

                exp_stmt = select(Experience.job_title).where(Experience.profile_id == profile.id)
                result = await self.session.execute(exp_stmt)
                candidate_experience = list(result.scalars().all())

        questions = QuestionGenerator.generate_questions(
            job_title=job.title,
            job_description=job.description or "",
            required_skills=job.required_skills or [],
            preferred_skills=job.preferred_skills or [],
            experience_level=job.experience_required or "",
            categories=categories,
            difficulty=difficulty,
            count=count,
            candidate_skills=candidate_skills,
            candidate_projects=candidate_projects,
            candidate_experience=candidate_experience,
        )

        categories_used = list(set(q["category"] for q in questions))

        return {
            "questions": questions,
            "total_questions": len(questions),
            "categories": categories_used,
            "difficulty": difficulty,
        }

    # ─── Schedule Interview ───────────────────────────────────────

    async def schedule_interview(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        scheduled_at: datetime,
        duration_minutes: int = 60,
        categories: list[str] | None = None,
        difficulty: str = "medium",
        question_count: int = 10,
        application_id: uuid.UUID | None = None,
        stage: str = "recruiter",
    ) -> Interview:
        """Create a scheduled interview with its generated question set.

        ``application_id`` is the Phase 11 link to the ``JobApplication`` this
        interview serves. It is optional because mock/practice interviews and the
        legacy job+candidate scheduling flow have no application. The caller is
        responsible for having authorized the pair: this method only persists.

        ``stage`` (Phase 15) records which hiring round this is -- ``recruiter``
        by default, ``hr`` for a second-round interview -- separately from the
        interview's status.
        """
        job = await self.session.get(Job, job_id)
        if not job:
            raise ValueError("Job not found")

        gen = await self.generate_questions(
            job_id=job_id,
            recruiter_id=recruiter_id,
            categories=categories,
            difficulty=difficulty,
            count=question_count,
            candidate_id=candidate_id,
        )

        interview = await self.interview_repo.create(
            job_id=job_id,
            candidate_id=candidate_id,
            application_id=application_id,
            recruiter_id=recruiter_id,
            interview_type="recruiter_scheduled",
            stage=stage,
            status="scheduled",
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            total_questions=len(gen["questions"]),
            questions_answered=0,
        )

        # Phase 14: the shared room this interview's participants will join.
        # Assigned here, where every scheduled interview is created, so the room
        # exists from the moment it is scheduled rather than waiting for somebody
        # to join. Mock practice sessions are untouched: they have their own
        # self-service flow and their own screen, so they get no room.
        interview.room_id = room_id_for(interview.id)

        for idx, q in enumerate(gen["questions"]):
            await self.question_repo.create(
                interview_id=interview.id,
                question_text=q["question_text"],
                category=q["category"],
                difficulty=q["difficulty"],
                order_index=idx,
                context=q.get("context"),
            )

        await self.session.flush()
        return interview

    # ─── Start Mock Interview ─────────────────────────────────────

    async def start_mock_interview(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        categories: list[str] | None = None,
        difficulty: str = "mixed",
        count: int = 10,
    ) -> dict:
        job = await self.session.get(Job, job_id)
        if not job:
            raise ValueError("Job not found")

        gen = await self.generate_questions(
            job_id=job_id,
            recruiter_id=candidate_id,
            categories=categories,
            difficulty=difficulty,
            count=count,
            candidate_id=candidate_id,
        )

        mock_service = MockInterviewService(self.session)
        interview = await mock_service.start_mock(
            candidate_id=candidate_id,
            job_id=job_id,
            questions=gen["questions"],
        )

        questions = await self.question_repo.list_by_interview(interview.id)
        first_q = questions[0] if questions else None

        return {
            "interview_id": interview.id,
            "job_id": job_id,
            "job_title": job.title,
            "first_question": first_q,
            "total_questions": len(questions),
        }

    # ─── Submit Answer ────────────────────────────────────────────

    async def submit_answer(
        self,
        question_id: uuid.UUID,
        answer_text: str,
        time_taken_seconds: int | None = None,
    ) -> dict:
        mock_service = MockInterviewService(self.session)
        return await mock_service.submit_answer(
            question_id=question_id,
            answer_text=answer_text,
            time_taken_seconds=time_taken_seconds,
        )

    # ─── Complete Interview ───────────────────────────────────────

    async def complete_interview(self, interview_id: uuid.UUID) -> dict:
        mock_service = MockInterviewService(self.session)
        return await mock_service.complete_interview(interview_id)

    # ─── Evaluate Interview (Recruiter) ───────────────────────────

    async def evaluate_interview(self, interview_id: uuid.UUID) -> dict:
        interview = await self.interview_repo.get_with_questions(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        for q in interview.questions:
            if q.answer and not q.answer.evaluation:
                evaluation = AnswerEvaluator.evaluate_answer(
                    question_text=q.question_text,
                    answer_text=q.answer.answer_text,
                    category=q.category,
                    question_context=q.context,
                )
                from app.repositories.interview.interview import InterviewEvaluationRepository
                eval_repo = InterviewEvaluationRepository(self.session)
                await eval_repo.create(answer_id=q.answer.id, **evaluation)

        scorecard_engine = ScorecardEngine(self.session)
        scorecard = await scorecard_engine.generate_scorecard(interview_id)

        await self.session.flush()
        return scorecard

    # ─── Scorecard ────────────────────────────────────────────────

    async def get_scorecard(self, interview_id: uuid.UUID) -> dict | None:
        scorecard = await self.scorecard_repo.get_by_interview(interview_id)
        return scorecard

    async def create_scorecard(
        self,
        interview_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        data: dict,
    ) -> dict:
        interview = await self.session.get(Interview, interview_id)
        if not interview:
            raise ValueError("Interview not found")

        scorecard_engine = ScorecardEngine(self.session)
        scorecard = await scorecard_engine.generate_scorecard(
            interview_id,
            recruiter_notes=data.get("recruiter_notes"),
        )

        if data.get("recruiter_notes"):
            interview_recruiter_notes = data["recruiter_notes"]
            if scorecard.get("id"):
                await self.scorecard_repo.update(
                    scorecard["id"],
                    recruiter_notes=interview_recruiter_notes,
                )

        await self.session.flush()
        return scorecard

    async def add_notes(self, interview_id: uuid.UUID, notes: str) -> None:
        interview = await self.session.get(Interview, interview_id)
        if not interview:
            raise ValueError("Interview not found")

        existing = await self.scorecard_repo.get_by_interview(interview_id)
        if existing:
            await self.scorecard_repo.update(existing.id, recruiter_notes=notes)
        else:
            await self.scorecard_repo.create(
                interview_id=interview_id,
                recruiter_notes=notes,
            )
        await self.session.flush()

    # ─── List Interviews ──────────────────────────────────────────

    async def list_interviews(
        self,
        user_id: uuid.UUID,
        role: str,
    ) -> list[dict]:
        if role == "candidate":
            interviews = await self.interview_repo.list_by_candidate(user_id)
        elif role in ("recruiter", "hr", "hr_manager"):
            interviews = await self.interview_repo.list_by_recruiter(user_id)
            if role in ("hr", "hr_manager"):
                all_interviews = await self.interview_repo.list_by_candidate(user_id)
                interviews = list({i.id: i for i in interviews + all_interviews}.values())
        else:
            interviews = await self.interview_repo.list_by_recruiter(user_id)

        items = []
        for iv in interviews:
            job = await self.session.get(Job, iv.job_id)
            candidate = await self.session.get(User, iv.candidate_id)
            # The interviewer's display name. For the candidate this is the one
            # fact about the other side they are entitled to -- "who signed the
            # job" -- and it is a plain name from the interview's own row, not
            # any account detail, contact or organization internals. For staff
            # it is simply the colleague who owns the interview.
            recruiter = (
                await self.session.get(User, iv.recruiter_id)
                if iv.recruiter_id else None
            )
            scorecard = await self.scorecard_repo.get_by_interview(iv.id)
            items.append({
                "id": iv.id,
                "job_id": iv.job_id,
                "job_title": job.title if job else "",
                "candidate_id": iv.candidate_id,
                "candidate_name": candidate.full_name if candidate else "",
                # Which application this interview was scheduled from, so a
                # reader can tell "an interview with this candidate" apart from
                # "the interview on this candidate's application for this job".
                # None for a practice/mock interview, which has no application.
                "application_id": iv.application_id,
                "interview_type": iv.interview_type,
                "stage": getattr(iv, "stage", "recruiter") or "recruiter",
                "status": iv.status,
                "scheduled_at": iv.scheduled_at,
                "completed_at": iv.completed_at,
                # The scheduled length, so a list row can show "30 minutes"
                # without the client loading the room or the detail payload.
                "duration_minutes": iv.duration_minutes,
                "total_questions": iv.total_questions,
                "questions_answered": iv.questions_answered,
                "overall_score": scorecard.overall_score if scorecard else None,
                "recruiter_name": recruiter.full_name if recruiter else "",
                "created_at": iv.created_at,
            })
        return items

    async def get_interview_detail(
        self, interview_id: uuid.UUID, *, for_candidate: bool = False,
    ) -> dict | None:
        """Full interview detail.

        ``for_candidate`` narrows the payload for the interview's own subject.
        Without it a candidate could read the hiring decision made about them:
        the scorecard carries the recommendation, the hiring confidence and the
        recruiter's private notes, and the per-answer evaluations are the
        interviewer's assessment rather than the candidate's own work.

        What the candidate still sees depends on why the interview exists:

        - A **mock** interview is a practice product. The candidate is meant to
          read the AI feedback on their own answers, so evaluations are kept.
        - A **recruiter-scheduled** interview is real hiring. Its evaluations
          are the interviewer's assessment of the candidate and are withheld.

        The scorecard is withheld either way: it is a staff artifact, and a
        candidate has no route to it.
        """
        interview = await self.interview_repo.get_with_questions(interview_id)
        if not interview:
            return None

        job = await self.session.get(Job, interview.job_id)
        candidate = await self.session.get(User, interview.candidate_id)
        recruiter = await self.session.get(User, interview.recruiter_id) if interview.recruiter_id else None
        scorecard = await self.scorecard_repo.get_by_interview(interview_id)

        # Mock practice feedback is the candidate's own; real-interview
        # evaluations are the interviewer's and stay with staff.
        evaluations_visible = (
            not for_candidate
            or interview.interview_type == InterviewType.MOCK.value
        )

        questions_data = []
        for q in interview.questions:
            q_data = {
                "id": q.id,
                "question_text": q.question_text,
                "category": q.category,
                "difficulty": q.difficulty,
                "order_index": q.order_index,
                "context": q.context,
                "answer": None,
            }
            if q.answer:
                eval_data = None
                if q.answer.evaluation and evaluations_visible:
                    eval_data = {
                        "id": q.answer.evaluation.id,
                        "technical_accuracy": q.answer.evaluation.technical_accuracy,
                        "completeness": q.answer.evaluation.completeness,
                        "communication": q.answer.evaluation.communication,
                        "problem_solving": q.answer.evaluation.problem_solving,
                        "confidence": q.answer.evaluation.confidence,
                        "relevance": q.answer.evaluation.relevance,
                        "overall_score": q.answer.evaluation.overall_score,
                        "feedback": q.answer.evaluation.feedback,
                        "improvement_suggestions": q.answer.evaluation.improvement_suggestions,
                        "follow_up_questions": q.answer.evaluation.follow_up_questions,
                    }
                q_data["answer"] = {
                    "id": q.answer.id,
                    "answer_text": q.answer.answer_text,
                    "time_taken_seconds": q.answer.time_taken_seconds,
                    "evaluation": eval_data,
                }
            questions_data.append(q_data)

        scorecard_data = None
        if scorecard and not for_candidate:
            scorecard_data = {
                "id": scorecard.id,
                "interview_id": scorecard.interview_id,
                "technical_skills": scorecard.technical_skills,
                "communication": scorecard.communication,
                "teamwork": scorecard.teamwork,
                "leadership": scorecard.leadership,
                "problem_solving": scorecard.problem_solving,
                "culture_fit": scorecard.culture_fit,
                "learning_ability": scorecard.learning_ability,
                "overall_score": scorecard.overall_score,
                "recommendation": scorecard.recommendation,
                "hiring_confidence": scorecard.hiring_confidence,
                "recruiter_notes": scorecard.recruiter_notes,
                "ai_summary": scorecard.ai_summary,
                "created_at": scorecard.created_at,
                "updated_at": scorecard.updated_at,
            }

        return {
            "id": interview.id,
            "job_id": interview.job_id,
            "job_title": job.title if job else "",
            "candidate_id": interview.candidate_id,
            "candidate_name": candidate.full_name if candidate else "",
            "candidate_email": candidate.email if candidate else "",
            # The application this interview belongs to, when it came from one.
            # Both roles already hold this id for their own record -- the
            # recruiter navigates the application, the candidate tracks it -- so
            # it names the record without adding any decision data.
            "application_id": interview.application_id,
            # The interviewer's identity is withheld from the candidate: who
            # interviewed you is not part of your own interview record.
            "recruiter_id": None if for_candidate else interview.recruiter_id,
            "recruiter_name": (
                None if for_candidate
                else (recruiter.full_name if recruiter else "")
            ),
            "interview_type": interview.interview_type,
            "stage": getattr(interview, "stage", "recruiter") or "recruiter",
            "status": interview.status,
            "scheduled_at": interview.scheduled_at,
            "started_at": interview.started_at,
            "completed_at": interview.completed_at,
            "duration_minutes": interview.duration_minutes,
            "total_questions": interview.total_questions,
            "questions_answered": interview.questions_answered,
            "questions": questions_data,
            "scorecard": scorecard_data,
            "created_at": interview.created_at,
            "updated_at": interview.updated_at,
        }

    # ─── Dashboard ────────────────────────────────────────────────

    async def get_dashboard(self, user_id: uuid.UUID, role: str) -> dict:
        if role == "candidate":
            return await self._candidate_dashboard(user_id)
        return await self._recruiter_dashboard(user_id)

    async def _candidate_dashboard(self, candidate_id: uuid.UUID) -> dict:
        total = await self.interview_repo.count_total(candidate_id=candidate_id)
        completed = await self.interview_repo.count_completed(candidate_id=candidate_id)
        upcoming = await self.interview_repo.list_upcoming_by_candidate(candidate_id)
        avg_score = await self.interview_repo.avg_score(candidate_id=candidate_id)

        interviews = await self.interview_repo.list_by_candidate(candidate_id)
        recent = []
        for iv in interviews[:5]:
            job = await self.session.get(Job, iv.job_id)
            recent.append({
                "id": iv.id,
                "job_title": job.title if job else "",
                "interview_type": iv.interview_type,
                "stage": getattr(iv, "stage", "recruiter") or "recruiter",
                "status": iv.status,
                "completed_at": iv.completed_at,
                "created_at": iv.created_at,
            })

        return {
            "total_interviews": total,
            "mock_interviews": sum(1 for iv in interviews if iv.interview_type == "mock"),
            "scheduled_interviews": len(upcoming),
            "average_score": round(avg_score, 1),
            "upcoming_interviews": [
                {
                    "id": iv.id,
                    "job_id": iv.job_id,
                    "interview_type": iv.interview_type,
                    "status": iv.status,
                    "scheduled_at": iv.scheduled_at,
                }
                for iv in upcoming
            ],
            "recent_scores": recent,
        }

    async def _recruiter_dashboard(self, recruiter_id: uuid.UUID) -> dict:
        total = await self.interview_repo.count_total(recruiter_id=recruiter_id)
        completed = await self.interview_repo.count_completed(recruiter_id=recruiter_id)
        upcoming = await self.interview_repo.list_upcoming_by_recruiter(recruiter_id)
        avg_score = await self.interview_repo.avg_score(recruiter_id=recruiter_id)

        interviews = await self.interview_repo.list_by_recruiter(recruiter_id)
        score_dist = {"excellent": 0, "good": 0, "average": 0, "below_average": 0}
        for iv in interviews[:50]:
            scorecard = await self.scorecard_repo.get_by_interview(iv.id)
            if scorecard:
                s = scorecard.overall_score
                if s >= 80:
                    score_dist["excellent"] += 1
                elif s >= 65:
                    score_dist["good"] += 1
                elif s >= 45:
                    score_dist["average"] += 1
                else:
                    score_dist["below_average"] += 1

        recent = []
        for iv in interviews[:5]:
            job = await self.session.get(Job, iv.job_id)
            candidate = await self.session.get(User, iv.candidate_id)
            recent.append({
                "id": iv.id,
                "job_title": job.title if job else "",
                "candidate_name": candidate.full_name if candidate else "",
                "interview_type": iv.interview_type,
                "stage": getattr(iv, "stage", "recruiter") or "recruiter",
                "status": iv.status,
                "created_at": iv.created_at,
            })

        return {
            "total_interviews": total,
            "upcoming_interviews": len(upcoming),
            "completed_interviews": completed,
            "average_score": round(avg_score, 1),
            "recent_interviews": recent,
            "score_distribution": score_dist,
        }

    # ─── Candidate Scorecards ─────────────────────────────────────

    async def get_candidate_scorecards(self, candidate_id: uuid.UUID) -> list[dict]:
        scorecards = await self.scorecard_repo.list_for_candidate(candidate_id)
        result = []
        for sc in scorecards:
            interview = await self.session.get(Interview, sc.interview_id)
            job = await self.session.get(Job, interview.job_id) if interview else None
            result.append({
                "id": sc.id,
                "interview_id": sc.interview_id,
                "job_title": job.title if job else "",
                "overall_score": sc.overall_score,
                "recommendation": sc.recommendation,
                "hiring_confidence": sc.hiring_confidence,
                "ai_summary": sc.ai_summary,
                "created_at": sc.created_at,
            })
        return result
