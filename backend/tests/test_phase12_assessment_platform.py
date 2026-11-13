"""Phase 12 – Assessment Platform test suite.

Covers: question generation (MCQ/aptitude/coding/SQL/debugging/output),
validation QC, grading (objective/subjective/debugging/code), sandboxed
execution, SQL execution grading, scoring, adaptive difficulty, timer
expiry, attempt limits, full API flow, RBAC and regression sanity.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.models import (
    AssessmentQuestion,
    CandidateAnswer,
    CandidateAssessment,
    CodingSubmission,
)
from app.services.assessment.adaptive import next_difficulty, pick_next_question, starting_difficulty
from app.services.assessment.assessment_service import AssessmentService
from app.services.assessment.code_sandbox import CodeSandbox, SqlGrader, estimate_complexity
from app.services.assessment.generators import generate_assessment_questions
from app.services.assessment.graders import (
    grade_coding_from_run,
    grade_debugging,
    grade_objective,
    grade_subjective,
)
from app.services.assessment.question_banks import CODING_PROBLEMS, QUANT_GENERATORS, SQL_SCHEMA_STATEMENTS
from app.services.assessment.scoring import compute_result
from app.services.assessment.validator import sanitize_batch, validate_question

PASSWORD = "Test@12345"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _mkuser(session, email: str, role: str) -> User:
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.domain.models import Role, User, UserRole

    user = User(id=uuid.uuid4(), full_name=f"U {email[:6]}", email=email,
                password_hash=hash_password(PASSWORD))
    session.add(user)
    await session.flush()
    role_row = (await session.execute(select(Role).where(Role.name == role))).scalar_one()
    session.add(UserRole(user_id=user.id, role_id=role_row.id))
    await session.flush()
    return user


async def _login(client, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


FULL_SECTIONS = [
    {"question_type": "mcq", "count": 3, "skills": ["python"], "difficulty": "mixed"},
    {"question_type": "aptitude_quantitative", "count": 2, "difficulty": "mixed"},
    {"question_type": "aptitude_logical", "count": 2},
    {"question_type": "aptitude_verbal", "count": 1},
    {"question_type": "technical_theory", "count": 1},
    {"question_type": "code_output", "count": 1},
    {"question_type": "debugging", "count": 1},
    {"question_type": "sql_mcq", "count": 1},
    {"question_type": "sql_query", "count": 2, "difficulty": "mixed"},
    {"question_type": "coding", "count": 1, "difficulty": "easy"},
    {"question_type": "system_design", "count": 1},
    {"question_type": "behavioral", "count": 1},
]


# ═══════════════ Generation & validation ════════════════════════


class TestGeneration:
    def test_full_paper_generation(self):
        qs = generate_assessment_questions(FULL_SECTIONS, seed=11)
        types = {q["question_type"] for q in qs}
        expected = {"mcq", "aptitude_quantitative", "aptitude_logical", "aptitude_verbal",
                    "technical_theory", "code_output", "debugging", "sql_mcq",
                    "sql_query", "coding", "system_design", "behavioral"}
        assert expected.issubset(types)
        for q in qs:
            if q["question_type"] in {"mcq", "aptitude_quantitative", "aptitude_logical",
                                      "aptitude_verbal", "technical_theory", "sql_mcq"}:
                assert len(q["content"]["options"]) >= 3
                assert isinstance(q["correct_answer"]["option_index"], int)

    def test_deterministic_generation_with_seed(self):
        a = generate_assessment_questions(FULL_SECTIONS, seed=99)
        b = generate_assessment_questions(FULL_SECTIONS, seed=99)
        assert [q["question_text"] for q in a] == [q["question_text"] for q in b]

    def test_all_quant_generators_produce_valid_mcqs(self):
        import random
        for name, gen in QUANT_GENERATORS.items():
            for draw in range(12):
                q = gen(random.Random(draw))
                ok, reason = validate_question(q)
                assert ok, f"{name} (draw {draw}): {reason}"

    def test_reference_solutions_pass_own_tests(self):
        for _diff, probs in CODING_PROBLEMS.items():
            for p in probs:
                ns: dict = {}
                exec(p["reference_solution"], ns)
                fn_name = p["reference_solution"].split("def ")[1].split("(")[0]
                fn = ns[fn_name]
                for tc in p["test_cases"]:
                    assert fn(*tc["args"]) == tc["expected"], p["title"]

    def test_validator_rejects_bad_questions(self):
        good_mcq = {
            "question_type": "mcq", "skill": "X", "topic": "t", "difficulty": "easy",
            "question_text": "Which option is correct here?",
            "content": {"options": ["a", "b", "c"]},
            "correct_answer": {"option_index": 0}, "explanation": "because",
        }
        dup = {**good_mcq, "content": {"options": ["a", "a", "b"]}}
        bad_idx = {**good_mcq, "correct_answer": {"option_index": 9}}
        no_expl = {**good_mcq, "explanation": ""}
        short = {**good_mcq, "question_text": "hi?"}
        assert validate_question(good_mcq)[0] is True
        assert validate_question(dup)[0] is False
        assert validate_question(bad_idx)[0] is False
        assert validate_question(no_expl)[0] is False
        assert validate_question(short)[0] is False

    def test_sanitize_dedupes_and_drops_invalid(self):
        base = {
            "question_type": "mcq", "skill": "X", "topic": "t", "difficulty": "easy",
            "content": {"options": ["a", "b", "c"]},
            "correct_answer": {"option_index": 1}, "explanation": "e",
        }
        q1 = {**base, "question_text": "What does the first unique question ask?"}
        q2 = {**base, "question_text": "what does the FIRST  unique question ask?"}
        invalid = {**base, "question_text": "no options here?", "content": {}}
        clean = sanitize_batch([q1, q2, invalid])
        assert len(clean) == 1


# ═══════════════ Grading ════════════════════════════════════════


class TestGraders:
    def test_mcq_right_and_wrong(self):
        q = {"question_type": "mcq", "correct_answer": {"option_index": 2}, "content": {}}
        assert grade_objective(q, {"option_index": 2})["is_correct"] is True
        wrong = grade_objective(q, {"option_index": 0})
        assert wrong["is_correct"] is False and wrong["score"] == 0.0

    def test_code_output_exact_and_partial(self):
        q = {"question_type": "code_output", "correct_answer": {"output": "[0, 1, 4, 9]"}, "content": {}}
        assert grade_objective(q, {"text": "[0, 1, 4, 9]"})["score"] == 1.0
        partial = grade_objective(q, {"text": "[0, 1, 4,"})
        assert 0 < partial["score"] < 1
        assert grade_objective(q, {"text": "garbage"})["score"] == 0.0

    def test_subjective_rubric_coverage(self):
        q = {"question_type": "system_design",
             "correct_answer": {"rubric": ["cache", "database", "queue", "scale"]}}
        rich = grade_subjective(q, "We add a redis cache in front of the database, "
                                   "use a queue for writes, and shard to scale reads. " * 3)
        assert rich["score"] > 0.6
        empty = grade_subjective(q, "")
        assert empty["score"] == 0.0

    def test_debugging_grading(self):
        q = {"question_type": "debugging",
             "correct_answer": {"keywords": ["total = n", "+=", "sum("]}}
        good = grade_debugging(q, "The bug is `total = n` overwrites the accumulator; "
                                  "fixed code uses total += n or sum(numbers).")
        assert good["score"] >= 0.7
        bad = grade_debugging(q, "looks fine to me")
        assert bad["score"] < 0.5

    def test_coding_grading_from_run(self):
        run = {"passed_count": 3, "total_count": 4, "ok": False, "stderr": "", "timed_out": False}
        g = grade_coding_from_run(run)
        assert g["score"] == 0.75 and g["is_correct"] is False
        perfect = grade_coding_from_run({"passed_count": 4, "total_count": 4, "ok": True})
        assert perfect["is_correct"] is True and perfect["score"] == 1.0


# ═══════════════ Sandbox & SQL ══════════════════════════════════


class TestSandbox:
    def setup_method(self):
        self.sandbox = CodeSandbox()

    def test_correct_solution_passes(self):
        two_sum = next(p for p in CODING_PROBLEMS["easy"] if p["title"] == "Two Sum")
        result = self.sandbox.run_tests(two_sum["reference_solution"],
                                        two_sum["test_cases"], "two_sum")
        assert result["ok"] is True
        assert result["passed_count"] == result["total_count"] == 4
        assert result["timed_out"] is False
        assert all(t["passed"] for t in result["test_results"])

    def test_wrong_solution_fails(self):
        two_sum = next(p for p in CODING_PROBLEMS["easy"] if p["title"] == "Two Sum")
        bad = "def two_sum(nums, target):\n    return [0, 1]\n"
        result = self.sandbox.run_tests(bad, two_sum["test_cases"], "two_sum")
        assert result["ok"] is False
        assert result["passed_count"] < result["total_count"]

    def test_runtime_error_reported(self):
        tests = [{"args": [[1]], "expected": 1}]
        result = self.sandbox.run_tests("def solve(nums):\n    return 1 / 0\n", tests, "solve")
        assert result["ok"] is False
        assert result["total_count"] == 1

    def test_infinite_loop_times_out(self):
        tests = [{"args": [1], "expected": 1}]
        result = self.sandbox.run_tests(
            "def solve(n):\n    while True:\n        n += 1\n    return n\n",
            tests, "solve", timeout_seconds=3,
        )
        assert result["timed_out"] is True or result["ok"] is False

    def test_complexity_heuristics(self):
        assert "O(1)" in estimate_complexity("x = 1\n")["time"]
        assert "O(n" in estimate_complexity("for i in range(10):\n    print(i)\n")["time"]
        nested = "".join(f"{'    ' * d}for i{d} in range(10):\n" for d in range(3)) + "    pass"
        est = estimate_complexity(nested)
        assert "O(n^" in est["time"] or "O(2^n)" in est["time"]

    def test_sql_grader_correct_vs_wrong_vs_forbidden(self):
        grader = SqlGrader()
        ref = "SELECT name FROM employees WHERE department_id = 1 ORDER BY name"
        good = grader.grade(SQL_SCHEMA_STATEMENTS, ref, ref)
        assert good["is_correct"] is True and good["score"] == 100

        wrong = grader.grade(SQL_SCHEMA_STATEMENTS,
                             "SELECT name FROM employees WHERE salary > 999999", ref)
        assert wrong["is_correct"] is False

        evil = grader.grade(SQL_SCHEMA_STATEMENTS,
                            "ATTACH DATABASE 'x.db' AS x; SELECT 1", ref)
        assert evil["is_correct"] is False and evil["score"] == 0


# ═══════════════ Scoring engine ═════════════════════════════════


def _score_questions():
    return [
        {"id": "q1", "question_type": "mcq", "skill": "python", "topic": "loops",
         "section": "Technical MCQ", "difficulty": "easy", "points": 2,
         "estimated_time_seconds": 60},
        {"id": "q2", "question_type": "coding", "skill": "algorithms", "topic": "arrays",
         "section": "Coding", "difficulty": "medium", "points": 3,
         "estimated_time_seconds": 600},
    ]


class TestScoring:
    def test_perfect_score_is_strong_hire(self):
        qs = _score_questions()
        answers = [
            {"question_id": "q1", "score_fraction": 1.0, "is_correct": True,
             "time_taken_seconds": 30},
            {"question_id": "q2", "score_fraction": 1.0, "is_correct": True,
             "time_taken_seconds": 300},
        ]
        out = compute_result(qs, answers)
        assert out["overall_score"] == 100.0
        assert out["recommendation"] == "strong_hire"
        assert out["readiness_level"] == "interview_ready"
        assert set(out["skill_scores"]) == {"python", "algorithms"}
        assert out["accuracy"] == 100.0

    def test_recommendation_thresholds(self):
        qs = _score_questions()

        def frac(f: float):
            return [
                {"question_id": "q1", "score_fraction": f, "is_correct": f >= 0.5,
                 "time_taken_seconds": 60},
                {"question_id": "q2", "score_fraction": f, "is_correct": None,
                 "time_taken_seconds": 600},
            ]

        assert compute_result(qs, frac(0.8))["recommendation"] == "hire"
        assert compute_result(qs, frac(0.65))["recommendation"] == "consider"
        assert compute_result(qs, frac(0.10))["recommendation"] == "reject"

    def test_negative_marking_penalises_wrong_objective_only(self):
        qs = _score_questions()
        answers = [
            {"question_id": "q1", "score_fraction": 0.0, "is_correct": False,
             "time_taken_seconds": 60},
            {"question_id": "q2", "score_fraction": 0.5, "is_correct": None,
             "time_taken_seconds": 600},
        ]
        clean = compute_result(qs, answers)
        marked = compute_result(qs, answers, negative_marking=0.25)
        assert marked["overall_score"] < clean["overall_score"]
        # a wrong CODING question is never penalised
        only_coding = [{"question_id": "q2", "score_fraction": 0.0,
                        "is_correct": False, "time_taken_seconds": 100}]
        assert (compute_result([qs[1]], only_coding, negative_marking=0.25)["overall_score"]
                == compute_result([qs[1]], only_coding)["overall_score"])

    def test_weak_topics_and_skills_flagged(self):
        qs = _score_questions()
        answers = [
            {"question_id": "q1", "score_fraction": 0.0, "is_correct": False,
             "time_taken_seconds": 60},
            {"question_id": "q2", "score_fraction": 1.0, "is_correct": True,
             "time_taken_seconds": 600},
        ]
        out = compute_result(qs, answers)
        assert "Loops" in out["recommended_topics"]
        assert "python" in out["weak_skills"]
        assert "algorithms" in out["strong_skills"]


# ═══════════════ Adaptive engine ════════════════════════════════


class TestAdaptive:
    def test_ladder_up_on_streak_down_on_wrong(self):
        assert next_difficulty("easy", True, 2) == "medium"
        assert next_difficulty("medium", True, 1) == "medium"
        assert next_difficulty("medium", True, 3) == "hard"
        assert next_difficulty("hard", True, 5) == "expert"
        assert next_difficulty("expert", True, 9) == "expert"
        assert next_difficulty("hard", False, 0) == "medium"
        assert next_difficulty("easy", False, 0) == "easy"
        assert next_difficulty("weird", False, 0) == "easy"

    def test_starting_difficulty_prefers_easiest_available(self):
        pool = [{"difficulty": d} for d in ("medium", "easy", "hard")]
        assert starting_difficulty(pool) == "easy"
        assert starting_difficulty([{"difficulty": "hard"}, {"difficulty": "expert"}]) == "hard"

    def test_pick_next_question_modes(self):
        pool = [
            {"id": "e", "difficulty": "easy", "order_index": 0},
            {"id": "m", "difficulty": "medium", "order_index": 1},
            {"id": "h", "difficulty": "hard", "order_index": 2},
        ]
        assert pick_next_question(pool, set(), "medium", None, 0, adaptive=False)["id"] == "e"
        assert pick_next_question(pool, {"e"}, "easy", True, 2, adaptive=False)["id"] == "m"
        assert pick_next_question(pool, {"e"}, "easy", True, 2, adaptive=True)["id"] == "m"
        assert pick_next_question(pool, {"e", "m"}, "medium", True, 2, adaptive=True)["id"] == "h"
        assert pick_next_question(
            pool, {"e", "m", "h"}, "medium", True, 4, adaptive=True) is None


# ═══════════════ Service + API end-to-end ═══════════════════════


FLOW_SECTIONS = [
    {"question_type": "mcq", "count": 2},
    {"question_type": "coding", "count": 1, "difficulty": "easy"},
    {"question_type": "sql_query", "count": 1},
    {"question_type": "system_design", "count": 1},
]


@pytest.mark.asyncio
class TestAssessmentFlow:
    async def _recruiter_and_assessment(self, client, session, title="Phase12 Flow"):
        email = f"{uuid.uuid4().hex[:8]}@t.dev"
        await _mkuser(session, email, "recruiter")
        token = await _login(client, email)
        resp = await client.post(
            "/api/v1/assessments/generate",
            json={"title": title, "duration_minutes": 30, "sections": FLOW_SECTIONS},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        return token, resp.json()

    async def _candidate(self, client, session) -> str:
        email = f"{uuid.uuid4().hex[:8]}@t.dev"
        await _mkuser(session, email, "candidate")
        return await _login(client, email)

    async def test_full_lifecycle(self, client, session):
        r_token, assessment = await self._recruiter_and_assessment(client, session)
        assert assessment["status"] == "published"
        assert assessment["question_count"] >= 4

        c_token = await self._candidate(client, session)
        start = await client.post(f"/api/v1/assessments/{assessment['id']}/start",
                                  headers=_auth(c_token))
        assert start.status_code == 200, start.text
        attempt_id = start.json()["attempt_id"]
        assert start.json()["total_questions"] == assessment["question_count"]
        assert len(start.json()["instructions"]) >= 3

        state = await client.get(f"/api/v1/assessments/attempts/{attempt_id}",
                                 headers=_auth(c_token))
        assert state.status_code == 200
        questions = state.json()["questions"]
        for q in questions:
            assert "correct_answer" not in q and "explanation" not in q
        by_type = {q["question_type"]: q for q in questions}
        assert by_type["coding"]["starter_code"]
        assert by_type["sql_query"]["schema_sql"]

        mcq_q = next(q for q in questions if q["question_type"] == "mcq")
        ans = await client.post(
            f"/api/v1/assessments/{attempt_id}/answer",
            json={"question_id": mcq_q["id"], "answer": {"option_index": 0},
                  "time_taken_seconds": 20},
            headers=_auth(c_token),
        )
        assert ans.status_code == 200, ans.text
        body = ans.json()
        assert 0 <= body["evaluation"]["score"] <= 100
        assert body["correct_answer_revealed"] is True
        assert body["explanation"]

        dup = await client.post(
            f"/api/v1/assessments/{attempt_id}/answer",
            json={"question_id": mcq_q["id"], "answer": {"option_index": 1}},
            headers=_auth(c_token),
        )
        assert dup.status_code == 409
        assert dup.json()["error"]["message"] == "ALREADY_ANSWERED"

        aq = (await session.execute(
            select(AssessmentQuestion).where(
                AssessmentQuestion.assessment_id == uuid.UUID(assessment["id"]),
                AssessmentQuestion.question_type == "coding",
            ))).scalar_one()
        ref_code = aq.correct_answer["reference_solution"]

        run = await client.post(
            f"/api/v1/assessments/{attempt_id}/code/run",
            json={"question_id": str(aq.id), "language": "python", "code": ref_code},
            headers=_auth(c_token),
        )
        assert run.status_code == 200, run.text
        run_body = run.json()
        assert run_body["ok"] is True
        assert run_body["passed_count"] == run_body["total_count"] > 0

        sub = await client.post(
            f"/api/v1/assessments/{attempt_id}/code/submit",
            json={"question_id": str(aq.id), "language": "python", "code": ref_code},
            headers=_auth(c_token),
        )
        assert sub.status_code == 200, sub.text
        assert sub.json()["evaluation"]["score"] == 100.0
        subs = (await session.execute(select(CodingSubmission))).scalars().all()
        assert any(s.passed_count == s.total_count for s in subs)

        sq = (await session.execute(
            select(AssessmentQuestion).where(
                AssessmentQuestion.assessment_id == uuid.UUID(assessment["id"]),
                AssessmentQuestion.question_type == "sql_query",
            ))).scalar_one()
        sql_ans = await client.post(
            f"/api/v1/assessments/{attempt_id}/answer",
            json={"question_id": str(sq.id),
                  "answer": {"sql": sq.correct_answer["reference_query"]}},
            headers=_auth(c_token),
        )
        assert sql_ans.status_code == 200, sql_ans.text
        assert sql_ans.json()["evaluation"]["score"] == 100.0

        sd_row = (await session.execute(
            select(AssessmentQuestion).where(
                AssessmentQuestion.assessment_id == uuid.UUID(assessment["id"]),
                AssessmentQuestion.question_type == "system_design",
            ))).scalar_one()
        rubric = (sd_row.correct_answer or {}).get("rubric") or []
        sd_ans = await client.post(
            f"/api/v1/assessments/{attempt_id}/answer",
            json={"question_id": str(sd_row.id), "answer": {
                "text": "First cover: " + ", ".join(rubric) +
                        ". Then discuss trade-offs, bottlenecks and scaling limits "
                        "with concrete numbers, capacity estimates and a step by "
                        "step rollout plan."}},
            headers=_auth(c_token),
        )
        assert sd_ans.status_code == 200
        assert sd_ans.json()["evaluation"]["score"] > 50

        integrity = await client.post(
            f"/api/v1/assessments/{attempt_id}/integrity",
            json={"event_type": "tab_switch", "detail": "candidate left tab"},
            headers=_auth(c_token),
        )
        assert integrity.status_code == 200

        fin = await client.post(f"/api/v1/assessments/{attempt_id}/submit",
                                headers=_auth(c_token))
        assert fin.status_code == 200, fin.text
        result = fin.json()
        assert result["status"] == "completed"
        assert result["overall_score"] > 0
        assert result["section_scores"] and result["skill_scores"]
        assert result["recommendation"] in {"strong_hire", "hire", "consider", "reject"}
        assert result["integrity_flags"] == 1
        assert result["per_question"]

        again = await client.get(f"/api/v1/assessments/{attempt_id}/result",
                                 headers=_auth(c_token))
        assert again.status_code == 200
        assert again.json()["overall_score"] == result["overall_score"]

        staff_view = await client.get(f"/api/v1/assessments/{attempt_id}/result",
                                      headers=_auth(r_token))
        assert staff_view.status_code == 200

        analytics = await client.get(
            f"/api/v1/assessments/{assessment['id']}/analytics", headers=_auth(r_token))
        assert analytics.status_code == 200, analytics.text
        an = analytics.json()
        assert an["completed"] >= 1
        assert an["average_score"] > 0
        assert an["candidates"]
        assert an["candidates"][0]["best_score"] >= an["candidates"][0]["latest_score"]
        assert an["skill_performance"]
        assert an["coding_success_rate"] == 100.0

        mine = await client.get("/api/v1/assessments/me", headers=_auth(c_token))
        assert mine.status_code == 200
        assert mine.json()["total"] >= 1
        assert mine.json()["items"][0]["overall_score"] is not None

    async def test_timer_expiry_auto_submits_then_blocks_answers(self, client, session):
        _, assessment = await self._recruiter_and_assessment(client, session, "Phase12 Expiry")
        c_token = await self._candidate(client, session)
        start = await client.post(f"/api/v1/assessments/{assessment['id']}/start",
                                  headers=_auth(c_token))
        attempt_id = start.json()["attempt_id"]

        row = await session.get(CandidateAssessment, uuid.UUID(attempt_id))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        await session.flush()

        state = await client.get(f"/api/v1/assessments/attempts/{attempt_id}",
                                 headers=_auth(c_token))
        assert state.status_code == 200
        assert state.json()["status"] == "expired"

        ans = await client.post(
            f"/api/v1/assessments/{attempt_id}/answer",
            json={"question_id": state.json()["questions"][0]["id"],
                  "answer": {"option_index": 0}},
            headers=_auth(c_token),
        )
        assert ans.status_code == 409

        res = await client.get(f"/api/v1/assessments/{attempt_id}/result",
                               headers=_auth(c_token))
        assert res.status_code == 200
        assert res.json()["status"] == "expired"
        assert res.json()["overall_score"] == 0.0

    async def test_attempt_limit_enforced(self, client, session):
        _, assessment = await self._recruiter_and_assessment(client, session, "Phase12 Limit")
        token = await self._candidate(client, session)
        first = await client.post(f"/api/v1/assessments/{assessment['id']}/start",
                                  headers=_auth(token))
        assert first.status_code == 200
        second = await client.post(f"/api/v1/assessments/{assessment['id']}/start",
                                   headers=_auth(token))
        assert second.status_code == 409
        assert second.json()["error"]["message"] == "NO_ATTEMPTS_REMAINING"

    async def test_rbac_matrix(self, client, session):
        c_token = await self._candidate(client, session)
        gen = await client.post("/api/v1/assessments/generate",
                                json={"title": "Nope", "sections": FLOW_SECTIONS[:1]},
                                headers=_auth(c_token))
        assert gen.status_code == 403

        anon_list = await client.get("/api/v1/assessments")
        assert anon_list.status_code == 422

        r_email = f"{uuid.uuid4().hex[:8]}@t.dev"
        await _mkuser(session, r_email, "recruiter")
        r_token = await _login(client, r_email)
        created = await client.post(
            "/api/v1/assessments/generate",
            json={"title": "RBAC Probe", "sections": FLOW_SECTIONS[:1]},
            headers=_auth(r_token))
        assert created.status_code == 200
        aid = created.json()["id"]

        assert (await client.post(f"/api/v1/assessments/{aid}/start",
                                  headers=_auth(r_token))).status_code == 403
        assert (await client.get(f"/api/v1/assessments/{aid}",
                                 headers=_auth(c_token))).status_code == 403
        assert (await client.get(f"/api/v1/assessments/{aid}/analytics",
                                 headers=_auth(c_token))).status_code == 403

        mine = await client.get("/api/v1/assessments/me", headers=_auth(c_token))
        assert mine.status_code == 200 and mine.json()["total"] == 0

    async def test_result_visibility_between_candidates(self, client, session):
        _, assessment = await self._recruiter_and_assessment(
            client, session, "Phase12 Visibility")
        ta = await self._candidate(client, session)
        tb = await self._candidate(client, session)
        start = await client.post(f"/api/v1/assessments/{assessment['id']}/start",
                                  headers=_auth(ta))
        attempt_id = start.json()["attempt_id"]

        other_state = await client.get(f"/api/v1/assessments/attempts/{attempt_id}",
                                       headers=_auth(tb))
        assert other_state.status_code == 403

        other_ans = await client.post(
            f"/api/v1/assessments/{attempt_id}/integrity",
            json={"event_type": "copy"},
            headers=_auth(tb))
        assert other_ans.status_code == 403

        other_result = await client.get(f"/api/v1/assessments/{attempt_id}/result",
                                        headers=_auth(tb))
        assert other_result.status_code == 403


@pytest.mark.asyncio
async def test_regression_existing_routers_still_registered(client):
    openapi = (await client.get("/openapi.json")).json()
    paths = openapi["paths"]
    assert "/api/v1/auth/login" in paths
    assert any("/interview" in p for p in paths), sorted(paths)[:30]
    assert sum(p.startswith("/api/v1/assessments") for p in paths) >= 10
