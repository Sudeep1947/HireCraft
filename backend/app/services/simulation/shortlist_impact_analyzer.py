"""ShortlistImpactAnalyzer — Phase 6 Shortlist Impact Analysis Engine.

Consumes persisted Phase 3 results (SimulationResult, SimulationExecution)
and configuration snapshots to compute what-if projections when the shortlist
size changes.

Architecture:
    Phase 3: Candidate Pool -> Baseline Evaluation -> Simulation Evaluation
             -> Persist Candidate Results (with ranks and shortlist status)
    Phase 6: Persisted Candidate Results + Config Snapshots -> Shortlist
             Impact Analyzer -> Shortlist Impact Metrics -> Frontend Dashboard

This service is READ-ONLY with respect to production hiring data.
It never modifies JobDescription, CandidateRanking, Candidate, or Resume rows.

All calculations are deterministic and derived from actual simulation results.
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
    ShortlistBoundaryCandidate,
    ShortlistImpactResponse,
    ShortlistInsight,
    ShortlistSensitivityPoint,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)

logger = get_logger(__name__)

# Default boundary range for shortlist analysis (ranks)
DEFAULT_BOUNDARY_RANGE = 5

# Default sensitivity sizes to analyze
DEFAULT_SENSITIVITY_SIZES = [5, 10, 15, 20, 25, 30]


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _safe_percentage(part: int, total: int) -> float:
    """Safe percentage calculation."""
    return round(_safe_divide(part, total) * 100, 1)


class ShortlistImpactAnalyzer:
    """Analyzes shortlist impact from persisted Phase 3 simulation results.

    This is a READ-ONLY analyzer. It consumes SimulationResult rows
    produced by Phase 3 and computes shortlist impact metrics by
    re-projecting shortlist membership at different sizes.
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
    ) -> ShortlistImpactResponse:
        """Run the full shortlist impact analysis for a simulation execution.

        Args:
            simulation_id: The simulation scenario ID.
            execution_id: Optional specific execution ID. If None, uses
                         the latest completed execution.
            boundary_range: Ranks around boundary to consider boundary candidates.

        Returns:
            Complete shortlist impact analysis response.

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

        baseline_shortlist_size = int(baseline_config.get("shortlist_size", 10))
        simulation_shortlist_size = int(simulation_config.get("shortlist_size", 10))
        total = len(results)

        # Compute actual shortlisted counts
        # Shortlisted = rank <= shortlist_size AND candidate is qualified
        # (following the project semantics where shortlisting requires qualification)
        baseline_threshold = int(baseline_config.get("threshold", 70))
        simulation_threshold = int(simulation_config.get("threshold", 70))

        actual_baseline = sum(
            1 for r in results
            if r.baseline_shortlisted
        )
        actual_simulation = sum(
            1 for r in results
            if r.simulation_shortlisted
        )

        # Compute composition changes using candidate IDs
        baseline_shortlisted_ids = {r.candidate_id for r in results if r.baseline_shortlisted}
        simulation_shortlisted_ids = {r.candidate_id for r in results if r.simulation_shortlisted}

        retained_ids = baseline_shortlisted_ids & simulation_shortlisted_ids
        entered_ids = simulation_shortlisted_ids - baseline_shortlisted_ids
        exited_ids = baseline_shortlisted_ids - simulation_shortlisted_ids

        retained_count = len(retained_ids)
        entered_count = len(entered_ids)
        exited_count = len(exited_ids)

        # Overlap metrics (Jaccard similarity)
        union_count = len(baseline_shortlisted_ids | simulation_shortlisted_ids)
        overlap_count = retained_count
        jaccard = _safe_divide(overlap_count, union_count, 0.0)
        retention_rate = _safe_divide(retained_count, actual_baseline, 0.0)
        turnover_rate = _safe_divide(
            entered_count + exited_count,
            actual_baseline if actual_baseline > 0 else 1,
            0.0,
        )

        # Shortlist change
        shortlist_change = simulation_shortlist_size - baseline_shortlist_size

        # Boundary candidates
        boundary_candidates = self._compute_boundary_candidates(
            results, baseline_shortlist_size, simulation_shortlist_size, boundary_range,
        )

        # Sensitivity analysis
        sensitivity_data = self._compute_sensitivity(
            results, baseline_shortlist_size,
        )

        # Generate insights
        insights = self._generate_insights(
            baseline_shortlist_size,
            simulation_shortlist_size,
            actual_baseline,
            actual_simulation,
            retained_count,
            entered_count,
            exited_count,
            total,
        )

        return ShortlistImpactResponse(
            simulation_id=simulation_id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            baseline_shortlist_size=baseline_shortlist_size,
            simulation_shortlist_size=simulation_shortlist_size,
            shortlist_change=shortlist_change,
            actual_baseline_shortlisted=actual_baseline,
            actual_simulation_shortlisted=actual_simulation,
            retained_count=retained_count,
            entered_count=entered_count,
            exited_count=exited_count,
            overlap_count=overlap_count,
            overlap_union_count=union_count,
            jaccard_similarity=round(jaccard, 4),
            retention_rate=round(retention_rate, 4),
            turnover_rate=round(turnover_rate, 4),
            boundary_range=boundary_range,
            boundary_candidates=boundary_candidates,
            sensitivity_data=sensitivity_data,
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
    ) -> ShortlistImpactResponse:
        """Return a valid but empty analysis when no results exist."""
        return ShortlistImpactResponse(
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
            boundary_range=DEFAULT_BOUNDARY_RANGE,
            boundary_candidates=[],
            sensitivity_data=[],
            total_candidates=0,
            insights=[],
        )

    def _compute_boundary_candidates(
        self,
        results: list[SimulationResult],
        baseline_shortlist_size: int,
        simulation_shortlist_size: int,
        boundary_range: int,
    ) -> list[ShortlistBoundaryCandidate]:
        """Identify candidates near the shortlist boundary."""
        candidates: list[ShortlistBoundaryCandidate] = []

        # Determine the boundary window
        min_boundary = min(baseline_shortlist_size, simulation_shortlist_size)
        max_boundary = max(baseline_shortlist_size, simulation_shortlist_size)

        for r in results:
            # Check if candidate is within the boundary range
            rank = r.simulation_rank
            # Consider candidates near either baseline or simulation boundary
            near_baseline = abs(rank - baseline_shortlist_size) <= boundary_range
            near_simulation = abs(rank - simulation_shortlist_size) <= boundary_range

            if near_baseline or near_simulation:
                # Determine shortlist change
                if r.baseline_shortlisted and r.simulation_shortlisted:
                    change = "retained"
                elif not r.baseline_shortlisted and r.simulation_shortlisted:
                    change = "entered"
                elif r.baseline_shortlisted and not r.simulation_shortlisted:
                    change = "exited"
                else:
                    change = "unchanged"

                # Distance from the closer boundary
                dist_baseline = abs(rank - baseline_shortlist_size)
                dist_simulation = abs(rank - simulation_shortlist_size)
                distance = min(dist_baseline, dist_simulation)

                candidates.append(ShortlistBoundaryCandidate(
                    candidate_id=r.candidate_id,
                    candidate_name=r.candidate_name,
                    rank=rank,
                    score=r.simulation_score,
                    baseline_shortlisted=r.baseline_shortlisted,
                    simulation_shortlisted=r.simulation_shortlisted,
                    shortlist_change=change,
                    distance_from_boundary=distance,
                ))

        # Sort by distance from boundary (closest first), then rank
        candidates.sort(key=lambda c: (c.distance_from_boundary, c.rank, c.candidate_name))
        return candidates

    def _compute_sensitivity(
        self,
        results: list[SimulationResult],
        baseline_shortlist_size: int,
    ) -> list[ShortlistSensitivityPoint]:
        """Compute shortlist composition across different sizes."""
        # Sort candidates by simulation rank
        sorted_results = sorted(results, key=lambda r: (r.simulation_rank, r.candidate_name))
        baseline_shortlisted_ids = {r.candidate_id for r in results if r.baseline_shortlisted}

        data: list[ShortlistSensitivityPoint] = []

        # Generate shortlist sizes to analyze
        sizes = set(DEFAULT_SENSITIVITY_SIZES)
        # Add baseline size and simulation-related sizes
        sizes.add(baseline_shortlist_size)
        # Add sizes around the baseline
        for offset in range(-10, 15, 5):
            candidate_size = baseline_shortlist_size + offset
            if 1 <= candidate_size <= len(results):
                sizes.add(candidate_size)

        for size in sorted(sizes):
            if size < 1:
                continue
            # Get top-N candidates by rank
            top_n_ids = {r.candidate_id for r in sorted_results[:size]}
            overlap = len(top_n_ids & baseline_shortlisted_ids)
            newly_included = len(top_n_ids - baseline_shortlisted_ids)

            data.append(ShortlistSensitivityPoint(
                shortlist_size=size,
                actual_shortlisted=min(size, len(results)),
                overlap_with_baseline=overlap,
                newly_included=newly_included,
                overlap_percentage=_safe_percentage(overlap, baseline_shortlist_size if baseline_shortlist_size > 0 else 1),
            ))

        return data

    def _generate_insights(
        self,
        baseline_shortlist_size: int,
        simulation_shortlist_size: int,
        actual_baseline: int,
        actual_simulation: int,
        retained_count: int,
        entered_count: int,
        exited_count: int,
        total: int,
    ) -> list[ShortlistInsight]:
        """Generate deterministic factual insights."""
        insights: list[ShortlistInsight] = []
        change = simulation_shortlist_size - baseline_shortlist_size

        # Shortlist size change
        if change != 0:
            direction = "increased" if change > 0 else "decreased"
            insights.append(ShortlistInsight(
                type="shortlist_change",
                message=f"The simulated shortlist size {direction} by {abs(change)} ({baseline_shortlist_size} -> {simulation_shortlist_size}).",
                metric_value=change,
                metric_unit="positions",
            ))

        # Retained candidates
        if retained_count > 0:
            insights.append(ShortlistInsight(
                type="composition",
                message=f"{retained_count} candidate(s) from the baseline shortlist remained in the simulated shortlist.",
                metric_value=retained_count,
                metric_unit="candidates",
            ))

        # Entered candidates
        if entered_count > 0:
            insights.append(ShortlistInsight(
                type="composition",
                message=f"{entered_count} candidate(s) entered the simulated shortlist.",
                metric_value=entered_count,
                metric_unit="candidates",
            ))

        # Exited candidates
        if exited_count > 0:
            insights.append(ShortlistInsight(
                type="composition",
                message=f"{exited_count} candidate(s) left the simulated shortlist.",
                metric_value=exited_count,
                metric_unit="candidates",
            ))

        # Shortlist expansion
        if change > 0:
            insights.append(ShortlistInsight(
                type="shortlist_change",
                message=f"The simulated shortlist contains {change} additional position(s).",
                metric_value=change,
                metric_unit="positions",
            ))
        elif change < 0:
            insights.append(ShortlistInsight(
                type="shortlist_change",
                message=f"The simulated shortlist has {abs(change)} fewer position(s).",
                metric_value=abs(change),
                metric_unit="positions",
            ))

        # Turnover rate
        if actual_baseline > 0:
            turnover = _safe_divide(
                entered_count + exited_count, actual_baseline,
            ) * 100
            if turnover > 0:
                insights.append(ShortlistInsight(
                    type="composition",
                    message=f"Shortlist turnover rate: {turnover:.1f}%.",
                    metric_value=turnover,
                    metric_unit="percent",
                ))

        return insights
