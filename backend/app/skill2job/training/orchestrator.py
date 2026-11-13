"""Phase 8 + LLM: LangGraph orchestration for the Skill2Job pipeline.

The graph wires the independent agents (perception -> profile -> jobs -> match ->
gap -> training) with conditional branching and records an execution trace for
auditability. Each node is a thin wrapper around an existing agent protocol
method; the graph adds orchestration and deterministic summaries, never extra
intelligence.

Conditional routing:
- If profile is incomplete (<2 skills), skip matching and gap analysis
- If no jobs found, skip match/gap/plan
- If no matches found (score=0), skip gap analysis
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.skill2job_models import Skill2JobExecutionTrace

logger = logging.getLogger(__name__)

ORCHESTRATION_VERSION = "skill2job-orchestration-9.0.0"


class PipelineState(TypedDict, total=False):
    user_id: str
    dossier_summary: dict
    jobs_count: int
    matched_count: int
    gap_count: int
    plan_count: int
    trace: dict
    profile_complete: bool
    jobs_available: bool
    has_matches: bool
    llm_enhanced: bool


class _GraphRuntime:
    """Holds the async session the graph nodes close over."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.steps: list[dict] = []
        self.user_id: str | None = None

    def _record(self, node: str, status: str, summary: dict, elapsed_ms: int) -> None:
        self.steps.append(
            {
                "node": node,
                "status": status,
                "summary": summary,
                "elapsed_ms": elapsed_ms,
            }
        )

    async def node_gather(self, state: PipelineState) -> PipelineState:
        from app.skill2job.adapters.candidate_adapter import CandidateAdapter

        started = time.monotonic()
        self.user_id = state.get("user_id")
        uid = uuid.UUID(self.user_id)
        try:
            profile = await CandidateAdapter(self.session).get_profile(uid)
            summary = {"connected": bool(profile)}
            state["profile_complete"] = bool(profile)
        except Exception as exc:
            summary = {"connected": False, "error": str(exc)}
            state["profile_complete"] = False
        self._record("gather", "ok", summary, int((time.monotonic() - started) * 1000))
        return state

    async def node_profile(self, state: PipelineState) -> PipelineState:
        from app.skill2job.adapters.candidate_adapter import CandidateAdapter
        from app.skill2job.profile.agent import ProfileAgent

        started = time.monotonic()
        uid = uuid.UUID(self.user_id)
        try:
            dossier = await ProfileAgent(self.session, CandidateAdapter(self.session)).build_dossier(uid)
            skill_count = dossier.skill_count
            completeness = getattr(
                dossier.completeness,
                "overall_percentage",
                getattr(dossier.completeness, "score", 0),
            )
            summary = {
                "skill_count": skill_count,
                "completeness": completeness,
            }
            state["dossier_summary"] = summary
            state["profile_complete"] = skill_count >= 2
            self._record("profile", "ok", summary, int((time.monotonic() - started) * 1000))
        except Exception as exc:
            state["profile_complete"] = False
            self._record("profile", "error", {"error": str(exc)}, int((time.monotonic() - started) * 1000))
        return state

    async def node_jobs(self, state: PipelineState) -> PipelineState:
        from app.skill2job.jobs.agent import LocalJobAgent

        started = time.monotonic()
        try:
            jobs = await LocalJobAgent(self.session).fetch_jobs()
            state["jobs_count"] = len(jobs)
            state["jobs_available"] = len(jobs) > 0
            self._record("jobs", "ok", {"fetched": len(jobs)}, int((time.monotonic() - started) * 1000))
        except Exception as exc:
            state["jobs_available"] = False
            self._record("jobs", "error", {"error": str(exc)}, int((time.monotonic() - started) * 1000))
        return state

    async def node_match(self, state: PipelineState) -> PipelineState:
        from app.skill2job.matching.agent import JobMatchingAgent

        started = time.monotonic()
        uid = uuid.UUID(self.user_id)
        try:
            entries = await JobMatchingAgent(self.session).run_match(uid, limit=10)
            state["matched_count"] = len(entries)
            state["has_matches"] = len(entries) > 0
            top = entries[0] if entries else None
            self._record(
                "match",
                "ok",
                {"matched": len(entries), "top_score": top.overall_score if top else None},
                int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:
            state["has_matches"] = False
            self._record("match", "error", {"error": str(exc)}, int((time.monotonic() - started) * 1000))
        return state

    async def node_gap(self, state: PipelineState) -> PipelineState:
        from app.skill2job.gap.agent import SkillGapAgent

        started = time.monotonic()
        uid = uuid.UUID(self.user_id)
        try:
            analyses = await SkillGapAgent(self.session).analyze_profile(uid, limit=3)
            state["gap_count"] = len(analyses)
            self._record("gap", "ok", {"analyses": len(analyses)}, int((time.monotonic() - started) * 1000))
        except Exception as exc:
            self._record("gap", "error", {"error": str(exc)}, int((time.monotonic() - started) * 1000))
        return state

    async def node_plan(self, state: PipelineState) -> PipelineState:
        from app.skill2job.training.agent import TrainingAgent

        started = time.monotonic()
        uid = uuid.UUID(self.user_id)
        try:
            plan = await TrainingAgent(self.session).plan_training(uid)
            state["plan_count"] = plan.total_modules
            state["llm_enhanced"] = plan.llm_plan_summary is not None
            self._record("plan", "ok", {
                "modules": plan.total_modules,
                "llm_enhanced": plan.llm_plan_summary is not None,
            }, int((time.monotonic() - started) * 1000))
        except Exception as exc:
            self._record("plan", "error", {"error": str(exc)}, int((time.monotonic() - started) * 1000))
        return state

    def should_run_match(self, state: PipelineState) -> str:
        if not state.get("profile_complete", False):
            return "skip"
        return "match"

    def should_run_gap(self, state: PipelineState) -> str:
        if not state.get("jobs_available", False):
            return "skip"
        if not state.get("has_matches", False):
            return "skip"
        return "gap"

    def should_run_plan(self, state: PipelineState) -> str:
        if state.get("gap_count", 0) == 0:
            return "skip"
        return "plan"


def build_graph(runtime: _GraphRuntime):
    try:
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(PipelineState)

        graph.add_node("gather", runtime.node_gather)
        graph.add_node("profile", runtime.node_profile)
        graph.add_node("jobs", runtime.node_jobs)
        graph.add_node("match", runtime.node_match)
        graph.add_node("gap", runtime.node_gap)
        graph.add_node("plan", runtime.node_plan)

        graph.add_edge(START, "gather")
        graph.add_edge("gather", "profile")
        graph.add_edge("profile", "jobs")

        graph.add_conditional_edges(
            "jobs",
            runtime.should_run_match,
            {
                "match": "match",
                "skip": END,
            },
        )

        graph.add_conditional_edges(
            "match",
            runtime.should_run_gap,
            {
                "gap": "gap",
                "skip": END,
            },
        )

        graph.add_conditional_edges(
            "gap",
            runtime.should_run_plan,
            {
                "plan": "plan",
                "skip": END,
            },
        )

        graph.add_edge("plan", END)
        return graph.compile()
    except ImportError:
        class _CompiledGraphFallback:
            def __init__(self, r: _GraphRuntime) -> None:
                self.runtime = r

            async def ainvoke(self, state: PipelineState) -> PipelineState:
                state = await self.runtime.node_gather(state)
                state = await self.runtime.node_profile(state)
                state = await self.runtime.node_jobs(state)
                if self.runtime.should_run_match(state) == "skip":
                    return state
                state = await self.runtime.node_match(state)
                if self.runtime.should_run_gap(state) == "skip":
                    return state
                state = await self.runtime.node_gap(state)
                if self.runtime.should_run_plan(state) == "skip":
                    return state
                state = await self.runtime.node_plan(state)
                return state

        return _CompiledGraphFallback(runtime)


class PipelineOrchestrator:
    """Run the full Skill2Job pipeline via LangGraph and record the trace."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, user_id: uuid.UUID) -> dict:
        runtime = _GraphRuntime(self.session)
        app = build_graph(runtime)
        final = await app.ainvoke({"user_id": str(user_id)})
        run_id = uuid.uuid4().hex
        trace = {
            "version": ORCHESTRATION_VERSION,
            "user_id": str(user_id),
            "steps": runtime.steps,
            "final": {
                "dossier_summary": final.get("dossier_summary"),
                "jobs_count": final.get("jobs_count"),
                "matched_count": final.get("matched_count"),
                "gap_count": final.get("gap_count"),
                "plan_count": final.get("plan_count"),
                "profile_complete": final.get("profile_complete"),
                "jobs_available": final.get("jobs_available"),
                "has_matches": final.get("has_matches"),
                "llm_enhanced": final.get("llm_enhanced"),
            },
        }
        self.session.add(
            Skill2JobExecutionTrace(
                user_id=user_id,
                run_id=run_id,
                trace=trace,
            )
        )
        await self.session.flush()
        return {
            "run_id": run_id,
            "status": "completed",
            "steps": runtime.steps,
            "final": trace["final"],
        }

    async def get_trace(self, user_id: uuid.UUID, run_id: str, is_admin: bool = False) -> dict | None:
        from sqlalchemy import select

        stmt = select(Skill2JobExecutionTrace).where(Skill2JobExecutionTrace.run_id == run_id)
        if not is_admin:
            stmt = stmt.where(Skill2JobExecutionTrace.user_id == user_id)

        row = (
            await self.session.execute(stmt)
        ).scalars().first()
        if row is None:
            return None
        return {
            "run_id": row.run_id,
            "trace": row.trace,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def list_traces(self, user_id: uuid.UUID, limit: int = 10, is_admin: bool = False) -> dict:
        from sqlalchemy import select

        stmt = select(Skill2JobExecutionTrace)
        if not is_admin:
            stmt = stmt.where(Skill2JobExecutionTrace.user_id == user_id)
        stmt = stmt.order_by(Skill2JobExecutionTrace.created_at.desc()).limit(limit)

        rows = (
            await self.session.execute(stmt)
        ).scalars().all()
        return {
            "items": [
                {
                    "run_id": r.run_id,
                    "steps": len((r.trace or {}).get("steps", [])),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            "total": len(rows),
        }
