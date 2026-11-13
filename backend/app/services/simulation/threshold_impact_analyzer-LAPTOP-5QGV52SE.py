"""ThresholdImpactAnalyzer — Phase 6 Threshold Impact Analysis Engine.

Consumes persisted Phase 3 results (SimulationResult, SimulationExecution)
and configuration snapshots to compute what-if projections when the minimum
hiring score threshold changes.

Architecture:
    Phase 3: Candidate Pool -> Baseline Evaluation -> Simulation Evaluation
             -> Persist Candidate Results (with scores)
    Phase 6: Persisted Candidate Results + Config Snapshots -> Threshold
             Impact Analyzer -> Threshold Impact Metrics -> Frontend Dashboard

This service is READ-ONLY with respect to production hiring data.
It never modifies JobDescription, CandidateRanking, Candidate, or Resume rows.

All calculations are deterministic and derived from actual simulation results.
"""

from __future__ import annotations

import statistics
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
    ThresholdBoundaryCandidate,
    ThresholdImpactResponse,
    ThresholdInsight,
    ThresholdScoreDistribution,
    ThresholdSensitivityPoint,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)

logger = get_logger(__name__)

_QUALIFIED = "qualified"
_NOT_QUALIFIED = "not_qualified"

# Default boundary range for threshold analysis (points)
DEFAULT_BOUNDARY_RANGE = 5

# Default sensitivity range (points around baseline)
DEFAULT_SENSITIVITY_STEP = 5
DEFAULT_SENSITIVITY_RANGE = 20

# Score band width for distribution
SCORE_BAND_WIDTH = 5


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _safe_percentage(part: int, total: int) -> float:
    """Safe percentage calculation."""
    return round(_safe_divide(part, total) * 100, 1)


def _is_qualified(score: int, threshold: int) -> bool:
    """Determine if a candidate qualifies at a given threshold."""
    return score >= threshold


class ThresholdImpactAnalyzer:
    """Analyzes threshold impact from persisted Phase 3 simulation results.

    This is a READ-ONLY analyzer. It consumes SimulationResult rows
    produced by Phase 3 and computes threshold impact metrics by
    re-projecting qualification status at different threshold values.
    It never writes to live hiring tables.
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

    async def analyze(
        self,
        simulation_id: uuid.UUID,
        execution_id: uuid.UUID | None = None,
        boundary_range: int = DEFAULT_BOUNDARY_RANGE,
    ) -> ThresholdImpactResponse:
        """Run the full threshold impact analysis for a simulation execution.

        Args:
            simulation_id: The simulation scenario ID.
            execution_id: Optional specific execution ID. If None, uses
                         the latest completed execution.
            boundary_range: Points around threshold to consider boundary.

        Returns:
            Complete threshold impact analysis response.

        Raises:
            NotFoundError: If simulation or execution not found.
            ValidationError: If execution is not completed.
        """
        scenario = await self._scenario_repo.get(simulation_id)
        if not scenario:
            raise NotFoundError("Simulation not found")

        execution = await self._resolve_execution(scenario, execution_id)

        results = await self._result_repo.list_by_execution(execution.id)
        if not results:
            return self._empty_response(scenario, execution)

        snapshot = execution.configuration_snapshot or {}
        baseline_config = snapshot.get("baseline") or {}
        simulation_config = snapshot.get("simulation") or {}

        baseline_threshold = int(baseline_config.get("threshold", 70))
        simulation_threshold = int(simulation_config.get("threshold", 70))

        # Core threshold analysis
        threshold_change = simulation_threshold - baseline_threshold
        baseline_qualified = sum(
            1 for r in results if _is_qualified(r.baseline_score, baseline_threshold)
        )
        simulation_qualified = sum(
            1 for r in results if _is_qualified(r.simulation_score, simulation_threshold)
        )
        qualified_change = simulation_qualified - baseline_qualified
        total = len(results)

        # Threshold crossings
        crossings = self._compute_threshold_crossings(
            results, baseline_threshold, simulation_threshold,
        )

        # Qualification retention and turnover
        retention_rate = _safe_divide(
            crossings["remained_qualified"],
            baseline_qualified,
            None,
        )
        turnover_rate = _safe_divide(
            crossings["newly_qualified"] + crossings["newly_disqualified"],
            baseline_qualified if baseline_qualified > 0 else 1,
            0.0,
        )

        # Boundary candidates
        boundary_candidates = self._compute_boundary_candidates(
            results, simulation_threshold, boundary_range,
        )

        # Sensitivity analysis
        sensitivity_data = self._compute_sensitivity(results, baseline_threshold)

        # Score distribution
        score_distribution = self._compute_score_distribution(
            results, simulation_threshold,
        )

        # Generate insights
        insights = self._generate_insights(
            baseline_threshold,
            simulation_threshold,
            baseline_qualified,
            simulation_qualified,
            crossings,
            boundary_candidates,
            total,
        )

        return ThresholdImpactResponse(
            simulation_id=simulation_id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            baseline_threshold=baseline_threshold,
            simulation_threshold=simulation_threshold,
            threshold_change=threshold_change,
            baseline_qualified_count=baseline_qualified,
            simulation_qualified_count=simulation_qualified,
            qualified_change=qualified_change,
            percentage_qualified_before=_safe_percentage(baseline_qualified, total),
            percentage_qualified_after=_safe_percentage(simulation_qualified, total),
            newly_qualified_count=crossings["newly_qualified"],
            newly_disqualified_count=crossings["newly_disqualified"],
            remained_qualified_count=crossings["remained_qualified"],
            remained_unqualified_count=crossings["remained_unqualified"],
            qualification_retention_rate=retention_rate,
            qualification_turnover_rate=turnover_rate,
            boundary_range=boundary_range,
            boundary_candidates=boundary_candidates,
            sensitivity_data=sensitivity_data,
            score_distribution=score_distribution,
            total_candidates=total,
            insights=insights,
        )

    # ─── Private Analysis Methods ───────────────────────────────────

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
    ) -> ThresholdImpactResponse:
        """Return a valid but empty analysis when no results exist."""
        return ThresholdImpactResponse(
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
            boundary_range=DEFAULT_BOUNDARY_RANGE,
            boundary_candidates=[],
            sensitivity_data=[],
            score_distribution=[],
            total_candidates=0,
            insights=[],
        )

    def _compute_threshold_crossings(
        self,
        results: list[SimulationResult],
        baseline_threshold: int,
        simulation_threshold: int,
    ) -> dict[str, int]:
        """Compute qualification crossings between baseline and simulation thresholds."""
        remained_qualified = 0
        remained_unqualified = 0
        newly_qualified = 0
        newly_disqualified = 0

        for r in results:
            base_qualified = _is_qualified(r.baseline_score, baseline_threshold)
            sim_qualified = _is_qualified(r.simulation_score, simulation_threshold)

            if base_qualified and sim_qualified:
                remained_qualified += 1
            elif not base_qualified and sim_qualified:
                newly_qualified += 1
            elif base_qualified and not sim_qualified:
                newly_disqualified += 1
            else:
                remained_unqualified += 1

        return {
            "remained_qualified": remained_qualified,
            "remained_unqualified": remained_unqualified,
            "newly_qualified": newly_qualified,
            "newly_disqualified": newly_disqualified,
        }

    def _compute_boundary_candidates(
        self,
        results: list[SimulationResult],
        threshold: int,
        boundary_range: int,
    ) -> list[ThresholdBoundaryCandidate]:
        """Identify candidates near the threshold boundary."""
        candidates: list[ThresholdBoundaryCandidate] = []

        for r in results:
            distance = abs(r.simulation_score - threshold)
            if distance <= boundary_range:
                base_qualified = _is_qualified(r.baseline_score, threshold)
                sim_qualified = _is_qualified(r.simulation_score, threshold)

                if base_qualified and sim_qualified:
                    change = "remained_qualified"
                elif not base_qualified and sim_qualified:
                    change = "newly_qualified"
                elif base_qualified and not sim_qualified:
                    change = "newly_disqualified"
                else:
                    change = "remained_unqualified"

                candidates.append(ThresholdBoundaryCandidate(
                    candidate_id=r.candidate_id,
                    candidate_name=r.candidate_name,
                    score=r.simulation_score,
                    threshold=threshold,
                    distance_from_threshold=distance,
                    qualified=sim_qualified,
                    baseline_qualified=base_qualified,
                    qualification_change=change,
                    baseline_rank=r.baseline_rank,
                    simulation_rank=r.simulation_rank,
                    rank_change=r.rank_change,
                    baseline_shortlisted=r.baseline_shortlisted,
                    simulation_shortlisted=r.simulation_shortlisted,
                ))

        # Sort by distance from threshold (closest first)
        candidates.sort(key=lambda c: (c.distance_from_threshold, -c.score, c.candidate_name))
        return candidates

    def _compute_sensitivity(
        self,
        results: list[SimulationResult],
        baseline_threshold: int,
    ) -> list[ThresholdSensitivityPoint]:
        """Compute qualified candidate counts across a range of thresholds."""
        scores = [r.simulation_score for r in results]
        total = len(results)

        if not scores:
            return []

        min_score = max(0, min(scores) - 5)
        max_score = min(100, max(scores) + 5)

        # Generate threshold values
        threshold_values: list[int] = []
        start = (min_score // DEFAULT_SENSITIVITY_STEP) * DEFAULT_SENSITIVITY_STEP
        for t in range(start, max_score + 1, DEFAULT_SENSITIVITY_STEP):
            threshold_values.append(t)
        # Ensure we include common thresholds
        for t in [0, 50, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
            if t not in threshold_values and min_score <= t <= max_score:
                threshold_values.append(t)
        threshold_values = sorted(set(threshold_values))

        data: list[ThresholdSensitivityPoint] = []
        for t in threshold_values:
            qualified = sum(1 for s in scores if _is_qualified(s, t))
            data.append(ThresholdSensitivityPoint(
                threshold=t,
                qualified_count=qualified,
                percentage_qualified=_safe_percentage(qualified, total),
            ))

        return data

    def _compute_score_distribution(
        self,
        results: list[SimulationResult],
        threshold: int,
    ) -> list[ThresholdScoreDistribution]:
        """Compute score distribution with threshold band highlighted."""
        scores = [r.simulation_score for r in results]

        if not scores:
            return []

        min_score = max(0, min(scores) - (min(scores) % SCORE_BAND_WIDTH))
        max_score = min(100, max(scores) + (SCORE_BAND_WIDTH - max(scores) % SCORE_BAND_WIDTH))

        bands: list[ThresholdScoreDistribution] = []
        for lower in range(min_score, max_score + 1, SCORE_BAND_WIDTH):
            upper = min(lower + SCORE_BAND_WIDTH - 1, 100)
            count = sum(1 for s in scores if lower <= s <= upper)
            # Check if threshold falls in this band
            is_threshold_band = lower <= threshold <= upper
            label = f"{lower}-{upper}"
            bands.append(ThresholdScoreDistribution(
                label=label,
                lower_bound=lower,
                upper_bound=upper,
                candidate_count=count,
                is_threshold_band=is_threshold_band,
            ))

        return bands

    def _generate_insights(
        self,
        baseline_threshold: int,
        simulation_threshold: int,
        baseline_qualified: int,
        simulation_qualified: int,
        crossings: dict[str, int],
        boundary_candidates: list[ThresholdBoundaryCandidate],
        total: int,
    ) -> list[ThresholdInsight]:
        """Generate deterministic factual insights."""
        insights: list[ThresholdInsight] = []
        change = simulation_threshold - baseline_threshold

        # Threshold change insight
        if change != 0:
            direction = "increased" if change > 0 else "decreased"
            insights.append(ThresholdInsight(
                type="threshold_change",
                message=f"The simulated threshold {direction} by {abs(change)} points ({baseline_threshold} -> {simulation_threshold}).",
                metric_value=change,
                metric_unit="points",
            ))

        # Qualification impact
        qualified_diff = simulation_qualified - baseline_qualified
        if qualified_diff > 0:
            insights.append(ThresholdInsight(
                type="qualification_impact",
                message=f"{qualified_diff} more candidates meet the simulated threshold.",
                metric_value=qualified_diff,
                metric_unit="candidates",
            ))
        elif qualified_diff < 0:
            insights.append(ThresholdInsight(
                type="qualification_impact",
                message=f"{abs(qualified_diff)} fewer candidates meet the simulated threshold.",
                metric_value=abs(qualified_diff),
                metric_unit="candidates",
            ))
        else:
            insights.append(ThresholdInsight(
                type="qualification_impact",
                message="The same number of candidates meet both thresholds.",
            ))

        # Newly disqualified
        if crossings["newly_disqualified"] > 0:
            insights.append(ThresholdInsight(
                type="qualification_impact",
                message=f"{crossings['newly_disqualified']} candidate(s) no longer meet the simulated threshold.",
                metric_value=crossings["newly_disqualified"],
                metric_unit="candidates",
            ))

        # Newly qualified
        if crossings["newly_qualified"] > 0:
            insights.append(ThresholdInsight(
                type="qualification_impact",
                message=f"{crossings['newly_qualified']} candidate(s) now meet the simulated threshold.",
                metric_value=crossings["newly_qualified"],
                metric_unit="candidates",
            ))

        # Boundary candidates
        if boundary_candidates:
            close_count = sum(1 for c in boundary_candidates if c.distance_from_threshold <= 2)
            if close_count > 0:
                insights.append(ThresholdInsight(
                    type="boundary",
                    message=f"{close_count} candidate(s) are within 2 points of the simulated threshold.",
                    metric_value=close_count,
                    metric_unit="candidates",
                ))

        # Retention rate
        if baseline_qualified > 0:
            retention = _safe_divide(crossings["remained_qualified"], baseline_qualified) * 100
            insights.append(ThresholdInsight(
                type="qualification_impact",
                message=f"{retention:.1f}% of baseline qualified candidates remain qualified under the simulated threshold.",
                metric_value=retention,
                metric_unit="percent",
            ))

        return insights
