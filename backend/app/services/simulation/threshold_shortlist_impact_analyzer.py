"""ThresholdShortlistImpactAnalyzer — Phase 6 Combined Analysis Coordinator.

Coordinates threshold and shortlist impact analysis to produce a unified
view of how changing both decision boundaries affects qualification and
shortlist composition.

Architecture:
    Phase 3: Candidate Pool -> Baseline Evaluation -> Simulation Evaluation
             -> Persist Candidate Results
    Phase 6: Persisted Candidate Results + Config Snapshots -> Threshold
             Analyzer + Shortlist Analyzer -> Combined Impact -> Frontend

This service is READ-ONLY with respect to production hiring data.
It never modifies JobDescription, CandidateRanking, Candidate, or Resume rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationResult,
    SimulationScenario,
)
from app.domain.threshold_shortlist_schemas import (
    CandidateThresholdShortlistImpact,
    CombinedImpactMatrix,
    CombinedThresholdShortlistResponse,
    ThresholdImpactResponse,
    ThresholdInsight,
    ShortlistImpactResponse,
    ShortlistInsight,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)
from app.services.simulation.threshold_impact_analyzer import ThresholdImpactAnalyzer
from app.services.simulation.shortlist_impact_analyzer import ShortlistImpactAnalyzer

logger = get_logger(__name__)


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


class ThresholdShortlistImpactAnalyzer:
    """Coordinates threshold and shortlist analysis for combined impact view.

    This is a READ-ONLY coordinator. It delegates to ThresholdImpactAnalyzer
    and ShortlistImpactAnalyzer, then combines their results into a unified
    response with per-candidate impact details.
    """

    def __init__(
        self,
        session: AsyncSession,
        execution_repo: SimulationExecutionRepository | None = None,
        result_repo: SimulationResultRepository | None = None,
        scenario_repo: SimulationRepository | None = None,
    ) -> None:
        self._session = session
        self._exec_repo = execution_repo or SimulationExecutionRepository(session)
        self._result_repo = result_repo or SimulationResultRepository(session)
        self._scenario_repo = scenario_repo or SimulationRepository(session)
        self._threshold_analyzer = ThresholdImpactAnalyzer(
            session, self._exec_repo, self._result_repo, self._scenario_repo,
        )
        self._shortlist_analyzer = ShortlistImpactAnalyzer(
            session, self._exec_repo, self._result_repo, self._scenario_repo,
        )

    async def analyze(
        self,
        simulation_id: uuid.UUID,
        execution_id: uuid.UUID | None = None,
        boundary_range: int = 5,
    ) -> CombinedThresholdShortlistResponse:
        """Run combined threshold + shortlist impact analysis."""
        scenario = await self._scenario_repo.get(simulation_id)
        if not scenario:
            raise NotFoundError("Simulation not found")

        execution = await self._resolve_execution(scenario, execution_id)
        results = await self._result_repo.list_by_execution(execution.id)
        if not results:
            return self._empty_response(scenario, execution)

        threshold_impact = await self._threshold_analyzer.analyze(
            simulation_id, execution_id=execution.id, boundary_range=boundary_range,
        )
        shortlist_impact = await self._shortlist_analyzer.analyze(
            simulation_id, execution_id=execution.id, boundary_range=boundary_range,
        )

        combined_matrix = self._compute_combined_matrix(results)
        candidate_impacts = self._compute_candidate_impacts(
            results, threshold_impact, shortlist_impact,
        )
        insights: list[ThresholdInsight | ShortlistInsight] = (
            threshold_impact.insights + shortlist_impact.insights
        )

        return CombinedThresholdShortlistResponse(
            simulation_id=simulation_id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            completed_at=execution.completed_at,
            threshold_impact=threshold_impact,
            shortlist_impact=shortlist_impact,
            combined_matrix=combined_matrix,
            total_affected_candidates=len(candidate_impacts),
            candidate_impacts=candidate_impacts,
            insights=insights,
        )

    async def _resolve_execution(
        self,
        scenario: SimulationScenario,
        execution_id: uuid.UUID | None,
    ) -> SimulationExecution:
        """Resolve execution: explicit ID or latest completed."""
        if execution_id is not None:
            execution = await self._exec_repo.get_for_scenario(scenario.id, execution_id)
            if not execution:
                raise NotFoundError("Execution not found")
            return execution
        execution = await self._exec_repo.latest_completed(scenario.id)
        if not execution:
            raise ValidationError(
                "No completed execution found. Run the simulation first.",
            )
        return execution

    def _empty_response(
        self,
        scenario: SimulationScenario,
        execution: SimulationExecution,
    ) -> CombinedThresholdShortlistResponse:
        """Return a valid but empty analysis when no results exist."""
        threshold_empty = ThresholdImpactResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            baseline_threshold=70,
            simulation_threshold=70,
            threshold_change=0,
            baseline_qualified_count=0,
            simulation_qualified_count=0,
            qualified_change=0,
            percentage_qualified_before=0.0,
            percentage_qualified_after=0.0,
            newly_qualified_count=0,
            newly_disqualified_count=0,
            remained_qualified_count=0,
            remained_unqualified_count=0,
            qualification_retention_rate=None,
            qualification_turnover_rate=0.0,
            boundary_range=5,
            boundary_candidates=[],
            sensitivity_data=[],
            score_distribution=[],
            total_candidates=0,
            insights=[],
        )
        shortlist_empty = ShortlistImpactResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            baseline_shortlist_size=10,
            simulation_shortlist_size=10,
            shortlist_change=0,
            actual_baseline_shortlisted=0,
            actual_simulation_shortlisted=0,
            retained_count=0,
            entered_count=0,
            exited_count=0,
            overlap_count=0,
            overlap_union_count=0,
            jaccard_similarity=0.0,
            retention_rate=0.0,
            turnover_rate=0.0,
            boundary_range=5,
            boundary_candidates=[],
            sensitivity_data=[],
            total_candidates=0,
            insights=[],
        )
        return CombinedThresholdShortlistResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            completed_at=execution.completed_at,
            threshold_impact=threshold_empty,
            shortlist_impact=shortlist_empty,
            combined_matrix=CombinedImpactMatrix(
                retained=0, entered=0, exited=0, remained_outside=0,
            ),
            total_affected_candidates=0,
            candidate_impacts=[],
            insights=[],
        )

    def _compute_combined_matrix(
        self,
        results: list[SimulationResult],
    ) -> CombinedImpactMatrix:
        """Compute the combined baseline vs simulation shortlist matrix."""
        baseline_shortlisted = {r.candidate_id for r in results if r.baseline_shortlisted}
        simulation_shortlisted = {r.candidate_id for r in results if r.simulation_shortlisted}

        retained = len(baseline_shortlisted & simulation_shortlisted)
        entered = len(simulation_shortlisted - baseline_shortlisted)
        exited = len(baseline_shortlisted - simulation_shortlisted)
        remained_outside = len(results) - retained - entered - exited

        return CombinedImpactMatrix(
            retained=retained,
            entered=entered,
            exited=exited,
            remained_outside=remained_outside,
        )

    def _compute_candidate_impacts(
        self,
        results: list[SimulationResult],
        threshold_impact: ThresholdImpactResponse,
        shortlist_impact: ShortlistImpactResponse,
    ) -> list[CandidateThresholdShortlistImpact]:
        """Compute per-candidate impact for affected candidates."""
        impacts: list[CandidateThresholdShortlistImpact] = []
        baseline_threshold = threshold_impact.baseline_threshold
        simulation_threshold = threshold_impact.simulation_threshold

        for r in results:
            base_qualified = r.baseline_score >= baseline_threshold
            sim_qualified = r.simulation_score >= simulation_threshold

            if base_qualified and sim_qualified:
                qual_change = "remained_qualified"
            elif not base_qualified and sim_qualified:
                qual_change = "newly_qualified"
            elif base_qualified and not sim_qualified:
                qual_change = "newly_disqualified"
            else:
                qual_change = "remained_unqualified"

            if r.baseline_shortlisted and r.simulation_shortlisted:
                short_change = "retained"
            elif not r.baseline_shortlisted and r.simulation_shortlisted:
                short_change = "entered"
            elif r.baseline_shortlisted and not r.simulation_shortlisted:
                short_change = "exited"
            else:
                short_change = "unchanged"

            is_affected = qual_change in ("newly_qualified", "newly_disqualified") or short_change in ("entered", "exited")
            if not is_affected:
                continue

            explanation = self._build_explanation(
                r, qual_change, short_change, baseline_threshold, simulation_threshold,
            )

            impacts.append(CandidateThresholdShortlistImpact(
                candidate_id=r.candidate_id,
                candidate_name=r.candidate_name,
                baseline_score=r.baseline_score,
                baseline_rank=r.baseline_rank,
                baseline_threshold=baseline_threshold,
                baseline_qualified=base_qualified,
                baseline_shortlisted=r.baseline_shortlisted,
                simulation_score=r.simulation_score,
                simulation_rank=r.simulation_rank,
                simulation_threshold=simulation_threshold,
                simulation_qualified=sim_qualified,
                simulation_shortlisted=r.simulation_shortlisted,
                qualification_change=qual_change,
                shortlist_change=short_change,
                score_change=r.score_change,
                rank_change=r.rank_change,
                explanation=explanation,
            ))

        impacts.sort(key=lambda c: (c.candidate_name,))
        return impacts

    @staticmethod
    def _build_explanation(
        r: SimulationResult,
        qual_change: str,
        short_change: str,
        baseline_threshold: int,
        simulation_threshold: int,
    ) -> str:
        """Build a factual explanation for a candidate's combined impact."""
        parts: list[str] = []

        if qual_change == "newly_disqualified":
            parts.append(
                f"Candidate score ({r.simulation_score}) no longer meets the simulated threshold "
                f"(changed from {baseline_threshold} to {simulation_threshold})."
            )
        elif qual_change == "newly_qualified":
            parts.append(
                f"Candidate score ({r.simulation_score}) now meets the simulated threshold "
                f"(changed from {baseline_threshold} to {simulation_threshold})."
            )

        if short_change == "entered":
            parts.append("Candidate entered the simulated shortlist.")
        elif short_change == "exited":
            parts.append("Candidate left the simulated shortlist.")

        return " ".join(parts)
