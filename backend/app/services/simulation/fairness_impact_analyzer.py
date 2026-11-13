"""FairnessImpactAnalyzer — Phase 7 Fairness Impact Simulation Engine.

Consumes persisted Phase 3 results (SimulationResult, SimulationExecution)
and self-reported candidate demographic data to compute fairness impact
metrics when the hiring configuration changes.

Architecture:
    Phase 3: Candidate Pool -> Baseline Evaluation -> Simulation Evaluation
             -> Persist Candidate Results
    Phase 7: Persisted Candidate Results + Candidate Demographics
             -> Fairness Impact Analyzer -> Group-Level Metrics
             -> Cross-Group Metrics -> Fairness Impact Report -> Frontend

This service is READ-ONLY with respect to production hiring data.
It never modifies JobDescription, Candidate, CandidateRanking, or any
live hiring records.

All calculations are deterministic and derived from actual simulation
results and self-reported demographic data.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import Gender
from app.domain.models import CandidateProfile
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationResult,
    SimulationScenario,
)
from app.domain.threshold_shortlist_schemas import ShortlistInsight
from app.domain.fairness_impact_schemas import (
    FairnessCrossGroupMetric,
    FairnessGroupMetric,
    FairnessImpactResponse,
    FairnessInsight,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)

logger = get_logger(__name__)

# Default minimum group size for statistical reliability
DEFAULT_MINIMUM_GROUP_SIZE = 5

# Valid gender values that count as "known demographic"
_KNOWN_GENDER_VALUES = {
    Gender.MALE.value,
    Gender.FEMALE.value,
    Gender.OTHER.value,
}


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _safe_percentage(part: int, total: int) -> float:
    """Safe percentage calculation."""
    return round(_safe_divide(part, total) * 100, 2)


class FairnessImpactAnalyzer:
    """Analyzes fairness impact from persisted Phase 3 simulation results
    and self-reported candidate demographic data.

    This is a READ-ONLY analyzer. It consumes SimulationResult rows
    produced by Phase 3 and CandidateProfile demographic data to compute
    fairness metrics across demographic groups. It never writes to live
    hiring tables.
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
        minimum_group_size: int = DEFAULT_MINIMUM_GROUP_SIZE,
    ) -> FairnessImpactResponse:
        """Run the full fairness impact analysis for a simulation execution.

        Args:
            simulation_id: The simulation scenario ID.
            execution_id: Optional specific execution ID. If None, uses
                         the latest completed execution.
            minimum_group_size: Minimum candidates in a group for metric
                               calculation. Groups below this threshold
                               are marked as insufficient_sample.

        Returns:
            Complete fairness impact analysis response.

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
            return self._empty_response(scenario, execution, minimum_group_size)

        # Load demographic data for all candidates in results
        demographics = await self._load_demographics(results)
        total_candidates = len(results)
        candidates_with_demo = sum(
            1 for r in results if r.candidate_id in demographics
        )
        candidates_missing_demo = total_candidates - candidates_with_demo

        # Group candidates by gender
        groups = self._group_by_gender(results, demographics)

        # Determine reference group (largest known-gender group)
        reference_group = self._determine_reference_group(groups)

        # Compute per-group metrics
        group_metrics = self._compute_group_metrics(
            groups, reference_group, minimum_group_size,
        )

        # Compute cross-group metrics
        cross_group_metrics = self._compute_cross_group_metrics(
            groups, reference_group, minimum_group_size,
        )

        # Generate insights
        insights = self._generate_insights(
            group_metrics, cross_group_metrics, reference_group,
            total_candidates, candidates_with_demo, candidates_missing_demo,
        )

        return FairnessImpactResponse(
            simulation_id=simulation_id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            group_dimension="gender",
            reference_group=reference_group,
            total_candidates=total_candidates,
            candidates_with_demographic=candidates_with_demo,
            candidates_missing_demographic=candidates_missing_demo,
            minimum_group_size=minimum_group_size,
            group_metrics=group_metrics,
            cross_group_metrics=cross_group_metrics,
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

    async def _load_demographics(
        self,
        results: list[SimulationResult],
    ) -> dict[uuid.UUID, str | None]:
        """Load gender demographics for all candidates in results.

        Returns a dict mapping candidate_id (user_id) to gender value string,
        or None if no profile/gender found.
        """
        candidate_ids = list({r.candidate_id for r in results})
        if not candidate_ids:
            return {}

        stmt = select(
            CandidateProfile.user_id,
            CandidateProfile.gender,
        ).where(CandidateProfile.user_id.in_(candidate_ids))

        rows = (await self._session.execute(stmt)).all()
        return {row.user_id: row.gender for row in rows}

    def _group_by_gender(
        self,
        results: list[SimulationResult],
        demographics: dict[uuid.UUID, str | None],
    ) -> dict[str, list[SimulationResult]]:
        """Group simulation results by gender demographic."""
        groups: dict[str, list[SimulationResult]] = defaultdict(list)

        for r in results:
            gender = demographics.get(r.candidate_id)
            if gender and gender in _KNOWN_GENDER_VALUES:
                groups[gender].append(r)
            else:
                groups["unknown"].append(r)

        return dict(groups)

    def _determine_reference_group(
        self,
        groups: dict[str, list[SimulationResult]],
    ) -> str | None:
        """Determine the reference group (largest known-gender group)."""
        known_groups = {
            k: v for k, v in groups.items() if k != "unknown"
        }
        if not known_groups:
            return None
        return max(known_groups, key=lambda k: len(known_groups[k]))

    def _compute_group_metrics(
        self,
        groups: dict[str, list[SimulationResult]],
        reference_group: str | None,
        minimum_group_size: int,
    ) -> list[FairnessGroupMetric]:
        """Compute fairness metrics for each demographic group."""
        metrics: list[FairnessGroupMetric] = []

        for group_value, group_results in sorted(groups.items()):
            sample_size = len(group_results)

            # Check if we have enough data
            if group_value == "unknown":
                metrics.append(FairnessGroupMetric(
                    group_dimension="gender",
                    group_value=group_value,
                    sample_size=sample_size,
                    eligible_count=sample_size,
                    baseline_selected_count=0,
                    simulation_selected_count=0,
                    entered_selection=0,
                    exited_selection=0,
                    retained_selection=0,
                    metric_status="no_demographic_data",
                    status_reason="Candidates in this group have no self-reported gender data.",
                ))
                continue

            if sample_size < minimum_group_size:
                metrics.append(FairnessGroupMetric(
                    group_dimension="gender",
                    group_value=group_value,
                    sample_size=sample_size,
                    eligible_count=sample_size,
                    baseline_selected_count=0,
                    simulation_selected_count=0,
                    entered_selection=0,
                    exited_selection=0,
                    retained_selection=0,
                    metric_status="insufficient_sample",
                    status_reason=(
                        f"Group has {sample_size} candidate(s), below the "
                        f"minimum threshold of {minimum_group_size}."
                    ),
                ))
                continue

            # Compute selection counts
            baseline_selected = sum(1 for r in group_results if r.baseline_shortlisted)
            simulation_selected = sum(1 for r in group_results if r.simulation_shortlisted)

            # Compute transitions
            retained = sum(
                1 for r in group_results
                if r.baseline_shortlisted and r.simulation_shortlisted
            )
            entered = sum(
                1 for r in group_results
                if not r.baseline_shortlisted and r.simulation_shortlisted
            )
            exited = sum(
                1 for r in group_results
                if r.baseline_shortlisted and not r.simulation_shortlisted
            )

            # Compute selection rates
            baseline_rate = _safe_divide(baseline_selected, sample_size)
            simulation_rate = _safe_divide(simulation_selected, sample_size)
            rate_change = simulation_rate - baseline_rate

            metrics.append(FairnessGroupMetric(
                group_dimension="gender",
                group_value=group_value,
                sample_size=sample_size,
                eligible_count=sample_size,
                baseline_selected_count=baseline_selected,
                simulation_selected_count=simulation_selected,
                baseline_selection_rate=round(baseline_rate, 4),
                simulation_selection_rate=round(simulation_rate, 4),
                selection_rate_change=round(rate_change, 4),
                entered_selection=entered,
                exited_selection=exited,
                retained_selection=retained,
                metric_status="available",
            ))

        return metrics

    def _compute_cross_group_metrics(
        self,
        groups: dict[str, list[SimulationResult]],
        reference_group: str | None,
        minimum_group_size: int,
    ) -> list[FairnessCrossGroupMetric]:
        """Compute cross-group fairness metrics (SPD, DI)."""
        metrics: list[FairnessCrossGroupMetric] = []

        if not reference_group or reference_group not in groups:
            metrics.append(FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                metric_status="no_reference_group",
                status_reason="No valid reference group available for cross-group comparison.",
            ))
            metrics.append(FairnessCrossGroupMetric(
                metric_name="disparate_impact_ratio",
                metric_label="Disparate Impact Ratio",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                metric_status="no_reference_group",
                status_reason="No valid reference group available for cross-group comparison.",
            ))
            return metrics

        ref_results = groups[reference_group]
        ref_size = len(ref_results)
        if ref_size < minimum_group_size:
            metrics.append(FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                metric_status="insufficient_data",
                status_reason=(
                    f"Reference group '{reference_group}' has {ref_size} candidate(s), "
                    f"below the minimum threshold of {minimum_group_size}."
                ),
            ))
            metrics.append(FairnessCrossGroupMetric(
                metric_name="disparate_impact_ratio",
                metric_label="Disparate Impact Ratio",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                metric_status="insufficient_data",
                status_reason=(
                    f"Reference group '{reference_group}' has {ref_size} candidate(s), "
                    f"below the minimum threshold of {minimum_group_size}."
                ),
            ))
            return metrics

        # Reference group selection rates
        ref_baseline_selected = sum(1 for r in ref_results if r.baseline_shortlisted)
        ref_simulation_selected = sum(1 for r in ref_results if r.simulation_shortlisted)
        ref_baseline_rate = _safe_divide(ref_baseline_selected, ref_size)
        ref_simulation_rate = _safe_divide(ref_simulation_selected, ref_size)

        # Compute SPD and DI across all known groups
        known_groups = {
            k: v for k, v in groups.items()
            if k != "unknown" and len(v) >= minimum_group_size
        }

        if len(known_groups) < 2:
            metrics.append(FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                groups_compared=list(known_groups.keys()),
                metric_status="insufficient_data",
                status_reason="Fewer than 2 groups meet the minimum size threshold.",
            ))
            metrics.append(FairnessCrossGroupMetric(
                metric_name="disparate_impact_ratio",
                metric_label="Disparate Impact Ratio",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                groups_compared=list(known_groups.keys()),
                metric_status="insufficient_data",
                status_reason="Fewer than 2 groups meet the minimum size threshold.",
            ))
            return metrics

        # Compute aggregate SPD: max absolute difference from reference
        baseline_spds: list[float] = []
        simulation_spds: list[float] = []

        for gv, gresults in known_groups.items():
            if gv == reference_group:
                continue
            g_size = len(gresults)
            g_baseline_selected = sum(1 for r in gresults if r.baseline_shortlisted)
            g_simulation_selected = sum(1 for r in gresults if r.simulation_shortlisted)
            g_baseline_rate = _safe_divide(g_baseline_selected, g_size)
            g_simulation_rate = _safe_divide(g_simulation_selected, g_size)

            baseline_spds.append(abs(g_baseline_rate - ref_baseline_rate))
            simulation_spds.append(abs(g_simulation_rate - ref_simulation_rate))

        if baseline_spds and simulation_spds:
            baseline_spd = max(baseline_spds)
            simulation_spd = max(simulation_spds)
            spd_change = simulation_spd - baseline_spd
            spd_relative = _safe_divide(spd_change, abs(baseline_spd)) if baseline_spd != 0 else None

            metrics.append(FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=round(baseline_spd, 4),
                simulation_value=round(simulation_spd, 4),
                absolute_change=round(spd_change, 4),
                relative_change=round(spd_relative, 4) if spd_relative is not None else None,
                reference_group=reference_group,
                groups_compared=list(known_groups.keys()),
                metric_status="available",
            ))

            # DI: ratio of min selection rate to max selection rate
            all_baseline_rates = []
            all_simulation_rates = []
            for gv, gresults in known_groups.items():
                g_size = len(gresults)
                g_b_sel = sum(1 for r in gresults if r.baseline_shortlisted)
                g_s_sel = sum(1 for r in gresults if r.simulation_shortlisted)
                all_baseline_rates.append(_safe_divide(g_b_sel, g_size))
                all_simulation_rates.append(_safe_divide(g_s_sel, g_size))

            min_baseline = min(all_baseline_rates)
            max_baseline = max(all_baseline_rates)
            min_simulation = min(all_simulation_rates)
            max_simulation = max(all_simulation_rates)

            baseline_di = _safe_divide(min_baseline, max_baseline, 1.0)
            simulation_di = _safe_divide(min_simulation, max_simulation, 1.0)
            di_change = simulation_di - baseline_di
            di_relative = _safe_divide(di_change, abs(baseline_di)) if baseline_di != 0 else None

            # Check if rates are identical
            if min_baseline == max_baseline and min_simulation == max_simulation:
                di_status = "identical_rates"
                di_reason = "All groups have identical selection rates."
            else:
                di_status = "available"
                di_reason = None

            metrics.append(FairnessCrossGroupMetric(
                metric_name="disparate_impact_ratio",
                metric_label="Disparate Impact Ratio",
                baseline_value=round(baseline_di, 4),
                simulation_value=round(simulation_di, 4),
                absolute_change=round(di_change, 4),
                relative_change=round(di_relative, 4) if di_relative is not None else None,
                reference_group=reference_group,
                groups_compared=list(known_groups.keys()),
                metric_status=di_status,
                status_reason=di_reason,
            ))
        else:
            metrics.append(FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                groups_compared=list(known_groups.keys()),
                metric_status="insufficient_data",
                status_reason="Could not compute SPD: no valid comparisons.",
            ))
            metrics.append(FairnessCrossGroupMetric(
                metric_name="disparate_impact_ratio",
                metric_label="Disparate Impact Ratio",
                baseline_value=None,
                simulation_value=None,
                absolute_change=None,
                reference_group=reference_group,
                groups_compared=list(known_groups.keys()),
                metric_status="insufficient_data",
                status_reason="Could not compute DI: no valid comparisons.",
            ))

        return metrics

    def _generate_insights(
        self,
        group_metrics: list[FairnessGroupMetric],
        cross_group_metrics: list[FairnessCrossGroupMetric],
        reference_group: str | None,
        total_candidates: int,
        candidates_with_demo: int,
        candidates_missing_demo: int,
    ) -> list[FairnessInsight]:
        """Generate deterministic factual insights."""
        insights: list[FairnessInsight] = []

        # Demographic coverage
        if candidates_missing_demo > 0:
            pct = _safe_percentage(candidates_missing_demo, total_candidates)
            insights.append(FairnessInsight(
                type="demographic_coverage",
                message=(
                    f"{candidates_missing_demo} of {total_candidates} candidates "
                    f"({pct}%) have no self-reported gender data."
                ),
                metric_value=candidates_missing_demo,
                metric_unit="candidates",
            ))

        # Reference group
        if reference_group:
            insights.append(FairnessInsight(
                type="reference_group",
                message=f"Reference group for cross-group comparisons: {reference_group}.",
            ))

        # Per-group selection rate changes
        available_groups = [
            m for m in group_metrics if m.metric_status == "available"
        ]
        for gm in available_groups:
            if gm.selection_rate_change is not None and gm.selection_rate_change != 0:
                direction = "increased" if gm.selection_rate_change > 0 else "decreased"
                abs_change = round(abs(gm.selection_rate_change) * 100, 1)
                insights.append(FairnessInsight(
                    type="selection_rate_change",
                    message=(
                        f"Selection rate for {gm.group_value} {direction} by "
                        f"{abs_change} percentage points "
                        f"(from {round(gm.baseline_selection_rate * 100, 1)}% to "
                        f"{round(gm.simulation_selection_rate * 100, 1)}%)."
                    ),
                    metric_value=gm.selection_rate_change,
                    metric_unit="rate",
                ))

        # Candidate transitions
        for gm in available_groups:
            if gm.entered_selection > 0:
                insights.append(FairnessInsight(
                    type="candidate_transition",
                    message=(
                        f"{gm.entered_selection} candidate(s) from group "
                        f"'{gm.group_value}' entered the simulated shortlist."
                    ),
                    metric_value=gm.entered_selection,
                    metric_unit="candidates",
                ))
            if gm.exited_selection > 0:
                insights.append(FairnessInsight(
                    type="candidate_transition",
                    message=(
                        f"{gm.exited_selection} candidate(s) from group "
                        f"'{gm.group_value}' exited the simulated shortlist."
                    ),
                    metric_value=gm.exited_selection,
                    metric_unit="candidates",
                ))

        # Cross-group metric changes
        for cm in cross_group_metrics:
            if cm.metric_status == "available" and cm.absolute_change is not None:
                if cm.absolute_change != 0:
                    direction = "increased" if cm.absolute_change > 0 else "decreased"
                    insights.append(FairnessInsight(
                        type="cross_group_metric",
                        message=(
                            f"{cm.metric_label} {direction} from "
                            f"{cm.baseline_value} to {cm.simulation_value}."
                        ),
                        metric_value=cm.absolute_change,
                        metric_unit="points",
                    ))
                else:
                    insights.append(FairnessInsight(
                        type="cross_group_metric",
                        message=(
                            f"{cm.metric_label} remained unchanged at "
                            f"{cm.baseline_value}."
                        ),
                        metric_value=0,
                        metric_unit="points",
                    ))
            elif cm.metric_status == "insufficient_data":
                if cm.status_reason:
                    insights.append(FairnessInsight(
                        type="data_limitation",
                        message=f"{cm.metric_label}: {cm.status_reason}",
                    ))

        # Insufficient sample groups
        insufficient_groups = [
            m for m in group_metrics if m.metric_status == "insufficient_sample"
        ]
        if insufficient_groups:
            group_names = ", ".join(m.group_value for m in insufficient_groups)
            insights.append(FairnessInsight(
                type="insufficient_sample",
                message=(
                    f"Fairness metrics are not reported for group(s) "
                    f"[{group_names}] because the available sample size is "
                    f"below the configured analysis threshold."
                ),
                metric_value=len(insufficient_groups),
                metric_unit="groups",
            ))

        return insights

    def _empty_response(
        self,
        scenario: SimulationScenario,
        execution: SimulationExecution,
        minimum_group_size: int,
    ) -> FairnessImpactResponse:
        """Return a valid but empty analysis when no results exist."""
        return FairnessImpactResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            group_dimension="gender",
            reference_group=None,
            total_candidates=0,
            candidates_with_demographic=0,
            candidates_missing_demographic=0,
            minimum_group_size=minimum_group_size,
            group_metrics=[],
            cross_group_metrics=[],
            insights=[],
        )
