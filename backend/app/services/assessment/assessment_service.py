"""Phase 12 – Assessment Platform orchestration service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.assessment_schemas import AssessmentCreateRequest
from app.domain.enums import AttemptStatus
from app.domain.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentResult,
    CandidateAnswer,
    CandidateAssessment,
    CodingSubmission,
    Job,
    JobApplication,
    TestCase,
    User,
)
from app.services.assessment import adaptive as adaptive_mod
from app.services.assessment import graders, scoring
from app.services.assessment.code_sandbox import CodeSandbox, SqlGrader, estimate_complexity
from app.services.assessment.generators import generate_assessment_questions


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite stores naive datetimes; normalize to UTC-aware for comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def candidate_take_link(assessment_id: uuid.UUID | str) -> str:
    """The one place the candidate's take-assessment route is written.

    Migration 0029 started persisting the issued link on the assignment row, which
    makes it more important than ever that there is a single definition of it: a
    writer that formatted the route itself could record a link that no reader
    would ever produce. Every writer and every fallback reader goes through here,
    so the stored value and the derived value cannot drift apart.
    """
    return f"/candidate/assessments/take/{assessment_id}"


def resolve_take_link(stored: str | None, assessment_id: uuid.UUID | str) -> str:
    """The link to show for an attempt: what was issued, else what is derived.

    Prefers the value recorded on the row so the page shows the link the
    assignment actually issued. Falls back to deriving it for the two cases where
    no link was ever issued: a self-started attempt, which was never handed one,
    and an assignment created before migration 0029.
    """
    return stored or candidate_take_link(assessment_id)


class AssessmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sandbox = CodeSandbox()
        self.sql_grader = SqlGrader()

    # ═══ Recruiter side ══════════════════════════════════════════

    async def create_assessment(
        self,
        recruiter_id: uuid.UUID,
        req: AssessmentCreateRequest,
        seed: int | None = None,
    ) -> Assessment:
        job = None
        if req.job_id:
            job = await self.session.get(Job, req.job_id)
            if not job:
                raise ValueError("Job not found")

        sections = [s.model_dump() for s in req.sections]
        gen_seed = seed if seed is not None else uuid.uuid4().int % (2**31)
        generated = generate_assessment_questions(sections, seed=gen_seed)
        if not generated:
            raise ValueError("Could not generate any valid questions for the requested sections")

        assessment = Assessment(
            title=req.title,
            description=req.description,
            job_id=req.job_id,
            created_by=recruiter_id,
            mode=req.mode,
            status="published",
            duration_minutes=req.duration_minutes,
            passing_score=req.passing_score,
            negative_marking=req.negative_marking,
            allowed_attempts=req.allowed_attempts,
            adaptive=req.adaptive,
            shuffle_questions=req.shuffle_questions,
            shuffle_options=req.shuffle_options,
            config={
                "sections": sections,
                "generation_seed": gen_seed,
                "job_skills": (job.required_skills or []) if job else [],
            },
        )
        self.session.add(assessment)
        await self.session.flush()

        for idx, q in enumerate(generated):
            aq = AssessmentQuestion(
                assessment_id=assessment.id,
                question_type=q["question_type"],
                skill=q.get("skill", "general"),
                topic=q.get("topic", "general"),
                difficulty=q.get("difficulty", "medium"),
                question_text=q["question_text"],
                content=q.get("content"),
                correct_answer=q.get("correct_answer"),
                explanation=q.get("explanation"),
                estimated_time_seconds=q.get("estimated_time_seconds", 90),
                points=float(q.get("points", 1.0)),
                section=self._section_label(q),
                order_index=idx,
            )
            self.session.add(aq)
            await self.session.flush()
            content = q.get("content") or {}
            for t_idx, tc in enumerate(content.get("test_cases") or []):
                self.session.add(TestCase(
                    question_id=aq.id,
                    input_data=str(tc.get("args")),
                    expected_output=str(tc.get("expected")),
                    hidden=t_idx >= 1,
                    order_index=t_idx,
                ))
        await self.session.flush()
        return assessment

    @staticmethod
    def _section_label(q: dict) -> str:
        from app.services.assessment.scoring import SECTION_LABELS
        return SECTION_LABELS.get(q["question_type"], q["question_type"])

    async def list_assessments(self) -> tuple[list[dict], int]:
        rows = (await self.session.execute(
            select(Assessment).order_by(Assessment.created_at.desc())
        )).scalars().all()
        items = []
        for a in rows:
            q_count = await self.session.scalar(
                select(func.count()).select_from(AssessmentQuestion)
                .where(AssessmentQuestion.assessment_id == a.id)
            )
            a_count = await self.session.scalar(
                select(func.count()).select_from(CandidateAssessment)
                .where(CandidateAssessment.assessment_id == a.id)
            )
            items.append(self._assessment_out(a, q_count or 0, a_count or 0))
        return items, len(items)

    def _assessment_out(self, a: Assessment, q_count: int, a_count: int) -> dict:
        return {
            "id": a.id, "title": a.title, "description": a.description,
            "job_id": a.job_id, "job_title": None, "mode": a.mode,
            "status": a.status, "duration_minutes": a.duration_minutes,
            "passing_score": a.passing_score, "negative_marking": a.negative_marking,
            "allowed_attempts": a.allowed_attempts, "adaptive": a.adaptive,
            "shuffle_questions": a.shuffle_questions, "shuffle_options": a.shuffle_options,
            "created_by": a.created_by, "question_count": q_count,
            "attempt_count": a_count, "created_at": a.created_at,
        }

    # ═══ Candidate side ══════════════════════════════════════════

    async def start_attempt(self, assessment_id: uuid.UUID, candidate_id: uuid.UUID) -> dict:
        assessment = await self.session.get(Assessment, assessment_id)
        if not assessment or assessment.status != "published":
            raise ValueError("Assessment not found")

        questions = await self._questions_for(assessment_id)
        if not questions:
            raise ValueError("Assessment has no questions")

        # Phase 12: an attempt assigned to an application by a recruiter is
        # resumed here rather than superseded by a new one.
        #
        # This must happen BEFORE the attempt-limit check, because that check
        # counts every attempt the candidate has for this assessment, and the
        # pre-created ``assigned`` row is one of them. Checking the limit first
        # would let a candidate who is already holding the only allowed attempt
        # be told NO_ATTEMPTS_REMAINING for the very attempt a recruiter assigned
        # them, and there would be no way for them to ever start it.
        assigned = await self.session.scalar(
            select(CandidateAssessment)
            .where(CandidateAssessment.assessment_id == assessment_id)
            .where(CandidateAssessment.candidate_id == candidate_id)
            .where(CandidateAssessment.status == AttemptStatus.ASSIGNED.value)
            .order_by(CandidateAssessment.assigned_at)
            .limit(1)
        )
        if assigned is not None:
            return await self._activate_attempt(assigned, assessment, questions)

        used = await self.session.scalar(
            select(func.count()).select_from(CandidateAssessment)
            .where(CandidateAssessment.assessment_id == assessment_id)
            .where(CandidateAssessment.candidate_id == candidate_id)
        )
        if (used or 0) >= assessment.allowed_attempts:
            raise ValueError("NO_ATTEMPTS_REMAINING")

        now = datetime.now(timezone.utc)
        attempt = CandidateAssessment(
            assessment_id=assessment_id,
            candidate_id=candidate_id,
            attempt_number=(used or 0) + 1,
            status=AttemptStatus.IN_PROGRESS.value,
            started_at=now,
            expires_at=now + timedelta(minutes=assessment.duration_minutes),
            question_order=self._question_order(assessment_id, assessment, questions, candidate_id),
            integrity_events=[],
            current_index=0,
        )
        self.session.add(attempt)
        await self.session.flush()
        await self._auto_expire_guard(attempt)
        return self._started_payload(attempt, assessment, questions)

    async def _activate_attempt(
        self,
        attempt: CandidateAssessment,
        assessment: Assessment,
        questions: list[AssessmentQuestion],
    ) -> dict:
        """Turn a pre-created ``assigned`` attempt into a running one.

        The clock starts here, on the candidate's first real start, rather than at
        assignment time. An assessment assigned on Monday and begun on Friday
        should give the candidate its full duration, not five minutes of it.

        ``question_order`` is generated now, not at assignment, so a question set
        that changed between assignment and start is what the candidate is
        actually served. The shuffle is seeded on ``(assessment, candidate)`` as
        before, so resuming the same assignment reproduces the same order.
        """
        now = datetime.now(timezone.utc)
        attempt.status = AttemptStatus.IN_PROGRESS.value
        attempt.started_at = now
        attempt.expires_at = now + timedelta(minutes=assessment.duration_minutes)
        attempt.question_order = self._question_order(
            attempt.assessment_id, assessment, questions, attempt.candidate_id,
        )
        await self.session.flush()
        await self._auto_expire_guard(attempt)
        return self._started_payload(attempt, assessment, questions)

    def _question_order(
        self,
        assessment_id: uuid.UUID,
        assessment: Assessment,
        questions: list[AssessmentQuestion],
        candidate_id: uuid.UUID,
    ) -> list[dict]:
        """Build the served question order, honouring the shuffle settings."""
        import random as _r
        order = [{"qid": str(q.id), "opts": list(range(len((q.content or {}).get("options") or [])))}
                 for q in questions]
        if assessment.shuffle_questions:
            _r.Random(str(assessment_id) + str(candidate_id)).shuffle(order)
        if assessment.shuffle_options:
            rng = _r.Random(str(assessment_id) + str(candidate_id))
            for entry in order:
                perm = list(entry["opts"])
                rng.shuffle(perm)
                entry["opts"] = perm
        return order

    def _started_payload(
        self,
        attempt: CandidateAssessment,
        assessment: Assessment,
        questions: list[AssessmentQuestion],
    ) -> dict:
        return {
            "attempt_id": attempt.id,
            "assessment_id": assessment.id,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "expires_at": attempt.expires_at,
            "total_questions": len(questions),
            "instructions": self._instructions(assessment),
            "sections": sorted({self._label_of(q) for q in questions}),
        }


    @staticmethod
    def _instructions(a: Assessment) -> list[str]:
        out = [
            f"Total duration: {a.duration_minutes} minutes. The assessment submits automatically when time expires.",
            f"Passing score: {a.passing_score}/100.",
            "Each objective question grades instantly; subjective answers are evaluated on submission.",
        ]
        if a.negative_marking > 0:
            out.append(f"Negative marking: -{a.negative_marking} per wrong objective answer.")
        if a.allowed_attempts > 1:
            out.append(f"You have {a.allowed_attempts} allowed attempts.")
        if a.adaptive:
            out.append("Adaptive mode: difficulty adjusts to your performance.")
        out.append("Integrity notice: tab switches and copy/paste events are logged for recruiter review.")
        return out

    async def get_attempt_state(self, attempt_id: uuid.UUID, candidate_id: uuid.UUID) -> dict:
        attempt = await self._own_attempt(attempt_id, candidate_id)
        await self._auto_expire_guard(attempt)
        assessment = await self.session.get(Assessment, attempt.assessment_id)
        questions = await self._questions_for(attempt.assessment_id)
        by_id = {str(q.id): q for q in questions}
        answers = await self._answers_map(attempt_id)
        order = attempt.question_order or []

        visible = []
        for pos, entry in enumerate(order):
            q = by_id.get(entry.get("qid"))
            if not q:
                continue
            visible.append(self._public_question(q, pos, entry))
        return {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "expires_at": attempt.expires_at,
            "duration_minutes": assessment.duration_minutes,
            "questions": visible,
            "answered": {str(k): v for k, v in answers.items()},
        }

    async def submit_answer(
        self,
        attempt_id: uuid.UUID,
        candidate_id: uuid.UUID,
        question_id: uuid.UUID,
        answer: dict,
        time_taken_seconds: int | None,
    ) -> dict:
        attempt = await self._own_attempt(attempt_id, candidate_id)
        await self._auto_expire_guard(attempt)
        if attempt.status != "in_progress":
            raise ValueError(f"ATTEMPT_{attempt.status.upper()}")

        existing = await self.session.scalar(
            select(CandidateAnswer).where(CandidateAnswer.attempt_id == attempt_id)
            .where(CandidateAnswer.question_id == question_id)
        )
        if existing:
            raise ValueError("ALREADY_ANSWERED")

        q = await self.session.get(AssessmentQuestion, question_id)
        if not q or q.assessment_id != attempt.assessment_id:
            raise ValueError("Question not found")

        qdict = {
            "id": str(q.id), "question_type": q.question_type,
            "correct_answer": q.correct_answer, "content": q.content or {},
            "points": q.points, "difficulty": q.difficulty,
        }
        evaluation = await self._evaluate(qdict, answer)
        frac = float(evaluation.get("score", 0.0))

        ans_row = CandidateAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            answer_data=answer,
            time_taken_seconds=time_taken_seconds,
            is_correct=evaluation.get("is_correct"),
            score_awarded=round(frac * float(q.points or 1.0), 4),
        )
        self.session.add(ans_row)
        await self.session.flush()

        if q.question_type == "coding" and isinstance(answer.get("code"), str):
            run = evaluation.pop("_run", None) or {}
            self.session.add(CodingSubmission(
                answer_id=ans_row.id,
                language=answer.get("language", "python"),
                code=answer["code"],
                stdout=run.get("stdout"),
                stderr=run.get("stderr"),
                passed_count=run.get("passed_count", 0),
                total_count=run.get("total_count", 0),
                execution_time_ms=run.get("execution_time_ms"),
                test_results=run.get("test_results"),
                complexity_estimate=estimate_complexity(answer["code"]),
                ai_feedback=evaluation.get("feedback"),
            ))

        attempt.current_index += 1

        # Adaptive next-question selection.
        questions = await self._questions_for(attempt.assessment_id)
        answers_map = await self._answers_map(attempt_id)
        streak = self._current_streak(answers_map)
        last = list(answers_map.values())[-1] if answers_map else None
        nxt = adaptive_mod.pick_next_question(
            pool=[{"id": qq.id, "difficulty": qq.difficulty, "order_index": qq.order_index} for qq in questions],
            answered_ids=set(answers_map.keys()),
            current_difficulty=q.difficulty,
            last_correct=last,
            streak=streak,
            adaptive=bool((await self.session.get(Assessment, attempt.assessment_id)).adaptive),
        )
        next_row = await self.session.get(AssessmentQuestion, nxt["id"]) if nxt else None

        reveal = q.question_type in {
            "mcq", "aptitude_quantitative", "aptitude_logical", "aptitude_verbal",
            "technical_theory", "code_output", "sql_mcq", "sql_debug",
        }
        remaining = len(questions) - len(answers_map)
        return {
            "answer_id": ans_row.id,
            "evaluation": {
                "score": round(frac * 100, 2),
                "is_correct": evaluation.get("is_correct"),
                "feedback": evaluation.get("feedback"),
                "dimensions": evaluation.get("dimensions"),
            },
            "correct_answer_revealed": reveal,
            "explanation": q.explanation if reveal else None,
            "next_question": self._public_question(next_row, len(answers_map)) if next_row else None,
            "questions_remaining": max(remaining, 0),
            "progress": {"answered": len(answers_map), "total": len(questions)},
        }

    async def run_code(
        self, attempt_id: uuid.UUID, candidate_id: uuid.UUID,
        question_id: uuid.UUID, language: str, code: str,
    ) -> dict:
        attempt = await self._own_attempt(attempt_id, candidate_id)
        await self._auto_expire_guard(attempt)
        q = await self.session.get(AssessmentQuestion, question_id)
        if not q or q.assessment_id != attempt.assessment_id:
            raise ValueError("Question not found")
        content = q.content or {}

        if language == "sql" or q.question_type == "sql_query":
            result = self.sql_grader.grade(
                setup_statements=content.get("schema_statements", []),
                candidate_query=code,
                reference_query=(q.correct_answer or {}).get("reference_query", ""),
            )
            return {
                "ok": bool(result.get("is_correct")),
                "stdout": result.get("feedback", ""),
                "stderr": "", "execution_time_ms": 0,
                "passed_count": 100 if result.get("is_correct") else 0,
                "total_count": 100,
                "test_results": [], "timed_out": False, "sandbox_mode": "sqlite-memory",
            }

        tests = [
            {"args": eval_case(tc.input_data), "expected": eval_case(tc.expected_output)}
            for tc in (await self.session.execute(
                select(TestCase).where(TestCase.question_id == q.id)
                .order_by(TestCase.order_index)
            )).scalars().all()
        ] or content.get("test_cases") or []
        fn_name = content.get("function_name")
        if not fn_name:
            ref = (q.correct_answer or {}).get("reference_solution") or ""
            fn_name = ref.split("def ")[1].split("(")[0].strip() if "def " in ref else None
        run = self.sandbox.run_tests(code, tests, fn_name or "solve")
        run["complexity_estimate"] = estimate_complexity(code)
        return run

    # ── finalize / results ───────────────────────────────────────

    async def finalize(self, attempt_id: uuid.UUID, *, expired: bool = False) -> dict:
        attempt = await self.session.get(CandidateAssessment, attempt_id)
        if not attempt:
            raise ValueError("Attempt not found")
        if attempt.status in {"completed", "expired"}:
            return await self.get_result(attempt_id)

        attempt.status = "expired" if expired else "completed"
        attempt.submitted_at = datetime.now(timezone.utc)

        questions = await self._questions_for(attempt.assessment_id)
        answers = (await self.session.execute(
            select(CandidateAnswer).where(CandidateAnswer.attempt_id == attempt_id)
        )).scalars().all()

        payload = scoring.compute_result(
            questions=[{
                "id": q.id, "question_type": q.question_type, "skill": q.skill,
                "topic": q.topic, "section": q.section, "difficulty": q.difficulty,
                "points": q.points, "estimated_time_seconds": q.estimated_time_seconds,
            } for q in questions],
            answers=[{
                "question_id": a.question_id,
                "score_fraction": (a.score_awarded / float(next(
                    (qq.points for qq in questions if qq.id == a.question_id), 1.0))),
                "is_correct": a.is_correct,
                "time_taken_seconds": a.time_taken_seconds,
            } for a in answers],
            negative_marking=float(
                (await self.session.get(Assessment, attempt.assessment_id)).negative_marking
            ),
            passing_score=int(
                (await self.session.get(Assessment, attempt.assessment_id)).passing_score
            ),
        )

        existing = await self.session.get(AssessmentResult, attempt_id)
        result = existing or AssessmentResult(attempt_id=attempt_id)
        result.overall_score = payload["overall_score"]
        result.accuracy = payload["accuracy"]
        result.time_management = payload["time_management"]
        result.readiness_level = payload["readiness_level"]
        result.recommendation = payload["recommendation"]
        result.ai_summary = payload["ai_summary"]
        result.section_scores = payload["section_scores"]
        result.strong_skills = payload["strong_skills"]
        result.weak_skills = payload["weak_skills"]
        result.recommended_topics = payload["recommended_topics"]
        if not existing:
            self.session.add(result)
        await self.session.flush()
        return await self.get_result(attempt_id)

    async def get_result(self, attempt_id: uuid.UUID) -> dict:
        attempt = await self.session.get(CandidateAssessment, attempt_id)
        if not attempt:
            raise ValueError("Attempt not found")
        result = (await self.session.execute(
            select(AssessmentResult).where(AssessmentResult.attempt_id == attempt_id)
        )).scalar_one_or_none()
        assessment = await self.session.get(Assessment, attempt.assessment_id)
        questions = await self._questions_for(attempt.assessment_id)
        answers = (await self.session.execute(
            select(CandidateAnswer).where(CandidateAnswer.attempt_id == attempt_id)
        )).scalars().all()
        q_by_id = {str(q.id): q for q in questions}

        per_question = []
        for a in answers:
            q = q_by_id.get(str(a.question_id))
            if not q:
                continue
            per_question.append({
                "question_id": str(a.question_id),
                "type": q.question_type,
                "skill": q.skill,
                "difficulty": q.difficulty,
                "score_pct": round((a.score_awarded / float(q.points or 1)) * 100, 1),
                "is_correct": a.is_correct,
                "time_seconds": a.time_taken_seconds,
            })

        integrity = attempt.integrity_events or []
        skill_acc: dict[str, list[float]] = {}
        for entry in per_question:
            skill_acc.setdefault(entry["skill"], []).append(entry["score_pct"])
        skill_scores = {k: round(sum(v) / len(v), 1) for k, v in skill_acc.items()}
        return {
            "attempt_id": attempt.id,
            "assessment_id": attempt.assessment_id,
            "candidate_id": attempt.candidate_id,
            "status": attempt.status,
            "submitted_at": attempt.submitted_at,
            "overall_score": result.overall_score if result else 0.0,
            "passing_score": assessment.passing_score,
            "passed": bool(result and result.overall_score >= assessment.passing_score),
            "section_scores": (result.section_scores or []) if result else [],
            "skill_scores": skill_scores,
            "strong_skills": (result.strong_skills or []) if result else [],
            "weak_skills": (result.weak_skills or []) if result else [],
            "recommended_topics": (result.recommended_topics or []) if result else [],
            "accuracy": result.accuracy if result else 0.0,
            "time_management": result.time_management if result else 0.0,
            "readiness_level": result.readiness_level if result else "not_ready",
            "recommendation": result.recommendation if result else "consider",
            "ai_summary": result.ai_summary if result else None,
            "integrity_flags": len(integrity),
            "per_question": per_question,
        }

    async def my_attempts(self, candidate_id: uuid.UUID) -> dict:
        rows = (await self.session.execute(
            select(CandidateAssessment)
            .where(CandidateAssessment.candidate_id == candidate_id)
            # Phase 12: an ``assigned`` attempt has no ``started_at`` yet, and
            # NULLs sort *last* under DESC on SQLite, so a candidate's pending
            # assignment would be buried at the bottom of their own list -- on the
            # one page whose whole job is telling them what to do next. Ordered
            # explicitly by status first so it does not depend on the database's
            # NULL ordering. ``created_at`` breaks the ``started_at`` ties the
            # previous single-key sort left to the engine.
            .order_by(
                (CandidateAssessment.status == AttemptStatus.ASSIGNED.value).desc(),
                CandidateAssessment.started_at.desc(),
                CandidateAssessment.created_at.desc(),
            )
        )).scalars().all()
        # Job titles for the assignments that came from an application, in one
        # query for the whole list rather than one per row.
        application_ids = {at.application_id for at in rows if at.application_id}
        job_titles: dict[uuid.UUID, str] = {}
        if application_ids:
            job_title_rows = (await self.session.execute(
                select(JobApplication.id, Job.title)
                .join(Job, Job.id == JobApplication.job_id)
                .where(JobApplication.id.in_(application_ids))
            )).all()
            job_titles = {app_id: title for app_id, title in job_title_rows}
        items = []
        for at in rows:
            a = await self.session.get(Assessment, at.assessment_id)
            res = (await self.session.execute(
                select(AssessmentResult).where(AssessmentResult.attempt_id == at.id)
            )).scalar_one_or_none()
            items.append({
                "attempt_id": at.id,
                "assessment_id": at.assessment_id,
                "application_id": at.application_id,
                "assessment_title": a.title if a else "",
                "mode": a.mode if a else "",
                "status": at.status,
                # The schedule the candidate was given: when the recruiter assigned
                # it. None for a self-started attempt, which nobody scheduled.
                "scheduled_at": at.assigned_at,
                # The date and time the recruiter actually chose, which is a
                # different fact from ``scheduled_at`` above and is what the page
                # should label "Scheduled". None is a real answer meaning "no time
                # was chosen", so it is never filled in from ``scheduled_at``.
                "scheduled_for": at.scheduled_for,
                # Returned so the page and any notification point at the same link
                # instead of each rebuilding a route. The stored value is preferred
                # so the link shown is the one the assignment issued.
                "assessment_link": resolve_take_link(at.assessment_link, at.assessment_id),
                "job_title": job_titles.get(at.application_id) if at.application_id else None,
                # Surfaced so the list can say an attempt is on the clock, which
                # is the difference between "you have a task" and "you have a
                # deadline".
                "expires_at": at.expires_at,
                "started_at": at.started_at,
                "submitted_at": at.submitted_at,
                "overall_score": res.overall_score if res else None,
                "passed": bool(res and a and res.overall_score >= a.passing_score),
            })
        return {"items": items, "total": len(items)}

    async def record_integrity_event(
        self, attempt_id: uuid.UUID, candidate_id: uuid.UUID, event_type: str, detail: str | None,
    ) -> None:
        attempt = await self._own_attempt(attempt_id, candidate_id)
        events = list(attempt.integrity_events or [])
        events.append({
            "event": event_type,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        attempt.integrity_events = events
        await self.session.flush()

    # ═══ Analytics ═══════════════════════════════════════════════

    async def analytics(self, assessment_id: uuid.UUID) -> dict:
        assessment = await self.session.get(Assessment, assessment_id)
        if not assessment:
            raise ValueError("Assessment not found")
        attempts = (await self.session.execute(
            select(CandidateAssessment).where(CandidateAssessment.assessment_id == assessment_id)
        )).scalars().all()
        questions = await self._questions_for(assessment_id)

        completed = [a for a in attempts if a.status in {"completed", "expired"}]
        scores: list[float] = []
        times: list[float] = []
        skill_acc: dict[str, list[float]] = {}
        q_stats: dict[str, dict] = {}
        diff_acc: dict[str, list[float]] = {}
        code_pass_total = code_total = 0

        for at in completed:
            res = (await self.session.execute(
                select(AssessmentResult).where(AssessmentResult.attempt_id == at.id)
            )).scalar_one_or_none()
            if res:
                scores.append(res.overall_score)
                times.append((_aware(at.submitted_at) - _aware(at.started_at)).total_seconds() / 60)
            answers = (await self.session.execute(
                select(CandidateAnswer).where(CandidateAnswer.attempt_id == at.id)
            )).scalars().all()
            qmap = {str(q.id): q for q in questions}
            for ans in answers:
                q = qmap.get(str(ans.question_id))
                if not q:
                    continue
                pct = (ans.score_awarded / float(q.points or 1)) * 100
                skill_acc.setdefault(q.skill, []).append(pct)
                diff_acc.setdefault(q.difficulty, []).append(pct)
                st = q_stats.setdefault(str(q.id), {"topic": q.topic, "type": q.question_type, "scores": []})
                st["scores"].append(pct)
            subs = (await self.session.execute(
                select(CodingSubmission).join(
                    CandidateAnswer, CandidateAnswer.id == CodingSubmission.answer_id
                ).where(CandidateAnswer.attempt_id == at.id)
            )).scalars().all()
            for sub in subs:
                code_total += 1
                if sub.total_count and sub.passed_count == sub.total_count:
                    code_pass_total += 1

        # candidate comparison
        by_candidate: dict[uuid.UUID, list[CandidateAssessment]] = {}
        for at in attempts:
            by_candidate.setdefault(at.candidate_id, []).append(at)
        candidates = []
        for cid, c_attempts in by_candidate.items():
            c_scores = []
            rec = "consider"
            for at in sorted(c_attempts, key=lambda x: x.attempt_number):
                res = (await self.session.execute(
                    select(AssessmentResult).where(AssessmentResult.attempt_id == at.id)
                )).scalar_one_or_none()
                if res:
                    c_scores.append(res.overall_score)
                    rec = res.recommendation
            if not c_scores:
                continue
            user = await self.session.get(User, cid)
            candidates.append({
                "candidate_id": cid,
                "candidate_name": user.full_name if user else str(cid)[:8],
                "attempts": len(c_attempts),
                "best_score": max(c_scores),
                "latest_score": c_scores[-1],
                "recommendation": rec,
            })
        candidates.sort(key=lambda c: c["best_score"], reverse=True)

        n_completed = len(completed)
        median_time = sorted(times)[len(times) // 2] if times else 0.0
        return {
            "assessment_id": assessment_id,
            "title": assessment.title,
            "total_assigned": len(attempts),
            "completed": n_completed,
            "in_progress": sum(1 for a in attempts if a.status == "in_progress"),
            "completion_rate": round(n_completed / len(attempts) * 100, 1) if attempts else 0.0,
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "pass_rate": round(
                sum(1 for s in scores if s >= assessment.passing_score) / len(scores) * 100, 1
            ) if scores else 0.0,
            "median_time_minutes": round(median_time, 1),
            "skill_performance": {
                k: round(sum(v) / len(v), 1) for k, v in skill_acc.items() if v
            },
            "question_accuracy": [
                {
                    "question_id": qid,
                    "topic": st["topic"],
                    "type": st["type"],
                    "accuracy": round(sum(st["scores"]) / len(st["scores"]), 1),
                    "responses": len(st["scores"]),
                }
                for qid, st in q_stats.items()
            ],
            "difficulty_performance": {
                d: round(sum(v) / len(v), 1) for d, v in diff_acc.items() if v
            },
            "coding_success_rate": round(code_pass_total / code_total * 100, 1) if code_total else 0.0,
            "candidates": candidates,
        }

    # ═══ internals ═══════════════════════════════════════════════

    async def _questions_for(self, assessment_id: uuid.UUID) -> list[AssessmentQuestion]:
        return list((await self.session.execute(
            select(AssessmentQuestion)
            .where(AssessmentQuestion.assessment_id == assessment_id)
            .order_by(AssessmentQuestion.order_index)
        )).scalars().all())

    async def _answers_map(self, attempt_id: uuid.UUID) -> dict[str, CandidateAnswer]:
        rows = (await self.session.execute(
            select(CandidateAnswer).where(CandidateAnswer.attempt_id == attempt_id)
        )).scalars().all()
        return {str(a.question_id): a for a in rows}

    async def _own_attempt(self, attempt_id: uuid.UUID, candidate_id: uuid.UUID) -> CandidateAssessment:
        attempt = await self.session.get(CandidateAssessment, attempt_id)
        if not attempt:
            raise ValueError("Attempt not found")
        if str(attempt.candidate_id) != str(candidate_id):
            raise PermissionError("Not your attempt")
        return attempt

    async def _auto_expire_guard(self, attempt: CandidateAssessment) -> None:
        if attempt.status != "in_progress":
            return
        exp = _aware(attempt.expires_at)
        if exp and datetime.now(timezone.utc) >= exp:
            await self.finalize(attempt.id, expired=True)

    @staticmethod
    def _current_streak(answers_map: dict[str, CandidateAnswer]) -> int:
        values = list(answers_map.values())
        streak = 0
        for a in reversed(values):
            if a.is_correct:
                streak += 1
            else:
                break
        return streak

    async def _evaluate(self, qdict: dict, answer: dict) -> dict:
        qtype = qdict["question_type"]
        if qtype in {
            "mcq", "aptitude_quantitative", "aptitude_logical", "aptitude_verbal",
            "technical_theory", "code_output", "sql_mcq", "sql_debug",
        }:
            return graders.grade_objective(qdict, answer)
        if qtype == "sql_query":
            result = self.sql_grader.grade(
                setup_statements=qdict["content"].get("schema_statements", []),
                candidate_query=str(answer.get("sql", "")),
                reference_query=(qdict.get("correct_answer") or {}).get("reference_query", ""),
            )
            return {
                "is_correct": result.get("is_correct"),
                "score": result.get("score", 0) / 100.0,
                "feedback": result.get("feedback"),
            }
        if qtype == "coding":
            code = str(answer.get("code", ""))
            tests = qdict["content"].get("test_cases") or []
            fn = qdict["content"].get("function_name")
            run = self.sandbox.run_tests(code, tests, fn or "solve")
            graded = graders.grade_coding_from_run(run)
            graded["_run"] = run
            return graded
        text = str(answer.get("text", ""))
        if qtype == "debugging":
            return graders.grade_debugging(qdict, text)
        return graders.grade_subjective(qdict, text)

    def _public_question(self, q: AssessmentQuestion | None, position: int,
                         entry: dict | None = None) -> dict | None:
        if q is None:
            return None
        content = q.content or {}
        options = list(content.get("options") or [])
        if entry and entry.get("opts") and len(options) == len(entry["opts"]):
            options = [options[i] for i in entry["opts"]]
        return {
            "id": str(q.id),
            "question_type": q.question_type,
            "skill": q.skill,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "question_text": q.question_text,
            "options": options,
            "code_snippet": content.get("snippet") or content.get("buggy_code"),
            "language": content.get("language") or content.get("editor_language"),
            "starter_code": content.get("starter_code"),
            "tables": None,
            "schema_sql": "\n".join(content.get("schema_statements") or []) or None,
            "estimated_time_seconds": q.estimated_time_seconds,
            "points": q.points,
            "section": q.section,
            "order_index": position,
        }

    @staticmethod
    def _label_of(q: AssessmentQuestion) -> str:
        from app.services.assessment.scoring import SECTION_LABELS
        return SECTION_LABELS.get(q.question_type, q.question_type)


def eval_case(raw: str | None):
    """Safely evaluate a stored test-case literal ('[2, 7]' etc.)."""
    if raw is None:
        return None
    try:
        import ast
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw
