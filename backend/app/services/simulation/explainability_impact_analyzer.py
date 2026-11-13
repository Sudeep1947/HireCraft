"""ExplainabilityImpactAnalyzer — Phase 8 Explainability Impact Simulation.

Consumes persisted Phase 3 results (SimulationResult, SimulationExecution)
and configuration snapshots to explain why candidate scores and rankings
changed between baseline and simulation configurations.

Architecture:
    Phase 3: Candidate Pool -> Baseline Evaluation -> Simulation Evaluation
             -> Persist Candidate Results (with per-dimension scores)
    Phase 8: Persisted Candidate Results + Config Snapshots
             -> Explainability Impact Analyzer -> Per-Dimension Contribution
             Comparison -> Score/Rank Attribution -> Frontend

This service is READ-ONLY with respect to production hiring data.
It never modifies JobDescription, Candidate, CandidateRanking, or any
live hiring records.

All calculations are deterministic and derived from actual simulation
results and scoring weight configurations.
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
from app.domain.explainability_impact_schemas import (
    CandidateExplainabilityImpact,
    ExplainabilityImpactResponse,
    ExplainabilityImpactSummary,
    ExplainabilityInsight,
    FeatureContributionChange,
    WeightChange,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)

logger = get_logger(__name__)

# Dimension keys -> human-readable labels
_DIMENSION_LABELS: dict[str, str] = {
    "skill": "Skills",
    "experience": "Experience",
    "education": "Education",
    "project": "Projects",
    "certification": "Certifications",
    "location": "Location",
    "employment_type": "Employment Type",
    "semantic": "Semantic Match",
}

# Dimension key -> config weight key
DIMENSION_KEYS: dict[str, str] = {
    "skill": "skills",
    "experience": "experience",
    "education": "education",
    "project": "projects",
    "certification": "certifications",
    "location": "location",
    "employment_type": "employment_type",
    "semantic": "semantic",
}


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


class ExplainabilityImpactAnalyzer:
    """Analyzes explainability impact from persisted Phase 3 simulation results.

    This is a READ-ONLY analyzer. It consumes SimulationResult rows
    produced by Phase 3 (which already contain per-dimension scores in
    baseline_dimensions and simulation_dimensions) and configuration
    snapshots (which contain scoring weights) to compute per-dimension
    weighted contribution comparisons.

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
    ) -> ExplainabilityImpactResponse:
        """Run the full explainability impact analysis.

        Args:
            simulation_id: The simulation scenario ID.
            execution_id: Optional specific execution ID. If None, uses
                         the latest completed execution.

        Returns:
            Complete explainability impact analysis response.

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
        base_config = snapshot.get("baseline") or {}
        sim_config = snapshot.get("simulation") or {}

        # Extract scoring weights
        base_weights = (base_config.get("scoring_weights") or {})
        sim_weights = (sim_config.get("scoring_weights") or {})

        # Compute weight changes
        weight_changes = self._compute_weight_changes(base_weights, sim_weights)

        # Compute per-candidate explainability impacts
        candidate_impacts = self._compute_candidate_impacts(
            results, base_weights, sim_weights,
        )

        # Compute summary
        summary = self._compute_summary(candidate_impacts)

        # Generate insights
        insights = self._generate_insights(
            summary, weight_changes, candidate_impacts,
        )

        return ExplainabilityImpactResponse(
            simulation_id=simulation_id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            summary=summary,
            weight_changes=weight_changes,
            candidates=candidate_impacts,
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

    def _compute_weight_changes(
        self,
        base_weights: dict,
        sim_weights: dict,
    ) -> list[WeightChange]:
        """Compute weight changes between baseline and simulation configs."""
        changes: list[WeightChange] = []

        for dim, weight_key in DIMENSION_KEYS.items():
            bw = round(base_weights.get(weight_key, 0.0), 4)
            sw = round(sim_weights.get(weight_key, 0.0), 4)
            wc = round(sw - bw, 4)

            changes.append(WeightChange(
                feature=dim,
                feature_label=_DIMENSION_LABELS.get(dim, dim),
                baseline_weight=bw,
                simulation_weight=sw,
                weight_change=wc,
            ))

        return changes

    def _compute_weighted_contributions(
        self,
        dimensions: dict[str, int],
        weights: dict[str, float],
    ) -> dict[str, float]:
        """Compute weighted contributions from raw dimension scores and weights."""
        contributions: dict[str, float] = {}
        for dim, weight_key in DIMENSION_KEYS.items():
            dim_score = dimensions.get(dim, 0)
            weight = weights.get(weight_key, 0.0)
            contributions[dim] = round(weight * dim_score, 2)
        return contributions

    def _compute_candidate_impacts(
        self,
        results: list[SimulationResult],
        base_weights: dict,
        sim_weights: dict,
    ) -> list[CandidateExplainabilityImpact]:
        """Compute per-candidate explainability impact."""
        impacts: list[CandidateExplainabilityImpact] = []

        for r in results:
            base_dims = r.baseline_dimensions or {}
            sim_dims = r.simulation_dimensions or {}

            base_contributions = self._compute_weighted_contributions(base_dims, base_weights)
            sim_contributions = self._compute_weighted_contributions(sim_dims, sim_weights)

            # Build per-feature contribution changes
            feature_changes: list[FeatureContributionChange] = []
            for dim, weight_key in DIMENSION_KEYS.items():
                bw = round(base_weights.get(weight_key, 0.0), 4)
                sw = round(sim_weights.get(weight_key, 0.0), 4)
                bds = base_dims.get(dim, 0)
                sds = sim_dims.get(dim, 0)
                bc = base_contributions.get(dim, 0.0)
                sc = sim_contributions.get(dim, 0.0)

                feature_changes.append(FeatureContributionChange(
                    feature=dim,
                    feature_label=_DIMENSION_LABELS.get(dim, dim),
                    baseline_weight=bw,
                    simulation_weight=sw,
                    weight_change=round(sw - bw, 4),
                    baseline_dimension_score=bds,
                    simulation_dimension_score=sds,
                    dimension_score_change=sds - bds,
                    baseline_contribution=bc,
                    simulation_contribution=sc,
                    contribution_change=round(sc - bc, 2),
                ))

            # Sort by absolute contribution change
            sorted_changes = sorted(
                feature_changes,
                key=lambda fc: abs(fc.contribution_change),
                reverse=True,
            )

            top_positive = [
                fc for fc in sorted_changes if fc.contribution_change > 0
            ][:3]
            top_negative = [
                fc for fc in sorted_changes if fc.contribution_change < 0
            ][:3]

            # Determine qualification change
            base_qualified = r.baseline_status == "qualified"
            sim_qualified = r.simulation_status == "qualified"
            if base_qualified and sim_qualified:
                qual_change = "qualified_to_qualified"
            elif not base_qualified and sim_qualified:
                qual_change = "unqualified_to_qualified"
            elif base_qualified and not sim_qualified:
                qual_change = "qualified_to_unqualified"
            else:
                qual_change = "unqualified_to_unqualified"

            # Determine impact type
            score_changed = r.score_change != 0
            rank_changed = r.rank_change != 0
            contributions_changed = any(
                fc.contribution_change != 0 for fc in feature_changes
            )

            if score_changed:
                impact_type = "score_changed"
            elif rank_changed and not score_changed:
                impact_type = "rank_only_changed"
            elif r.baseline_status != r.simulation_status:
                impact_type = "threshold_only"
            else:
                impact_type = "unchanged"

            impacts.append(CandidateExplainabilityImpact(
                candidate_id=r.candidate_id,
                candidate_name=r.candidate_name,
                baseline_score=r.baseline_score,
                simulation_score=r.simulation_score,
                score_change=r.score_change,
                baseline_rank=r.baseline_rank,
                simulation_rank=r.simulation_rank,
                rank_change=r.rank_change,
                baseline_shortlisted=r.baseline_shortlisted,
                simulation_shortlisted=r.simulation_shortlisted,
                qualification_change=qual_change,
                feature_contributions=feature_changes,
                top_positive_changes=top_positive,
                top_negative_changes=top_negative,
                reason=r.reason,
                impact_type=impact_type,
            ))

        # Sort by absolute score change descending
        impacts.sort(key=lambda c: abs(c.score_change), reverse=True)
        return impacts

    def _compute_summary(
        self,
        candidates: list[CandidateExplainabilityImpact],
    ) -> ExplainabilityImpactSummary:
        """Compute aggregate summary statistics."""
        total = len(candidates)
        score_changes = sum(1 for c in candidates if c.score_change != 0)
        rank_changes = sum(1 for c in candidates if c.rank_change != 0)
        contrib_changes = sum(
            1 for c in candidates
            if any(fc.contribution_change != 0 for fc in c.feature_contributions)
        )
        unchanged = sum(1 for c in candidates if c.impact_type == "unchanged")

        score_deltas = [c.score_change for c in candidates]
        avg_change = _safe_divide(sum(score_deltas), len(score_deltas)) if score_deltas else 0.0
        positives = [d for d in score_deltas if d > 0]
        negatives = [d for d in score_deltas if d < 0]
        max_increase = max(positives) if positives else 0
        max_decrease = min(negatives) if negatives else 0

        return ExplainabilityImpactSummary(
            total_candidates=total,
            candidates_with_score_changes=score_changes,
            candidates_with_rank_changes=rank_changes,
            candidates_with_contribution_changes=contrib_changes,
            candidates_unchanged=unchanged,
            average_score_change=round(avg_change, 2),
            largest_score_increase=max_increase,
            largest_score_decrease=max_decrease,
        )

    def _generate_insights(
        self,
        summary: ExplainabilityImpactSummary,
        weight_changes: list[WeightChange],
        candidates: list[CandidateExplainabilityImpact],
    ) -> list[ExplainabilityInsight]:
        """Generate deterministic factual insights."""
        insights: list[ExplainabilityInsight] = []

        # Weight changes
        changed_weights = [wc for wc in weight_changes if wc.weight_change != 0]
        if changed_weights:
            for wc in changed_weights:
                direction = "increased" if wc.weight_change > 0 else "decreased"
                abs_change = round(abs(wc.weight_change) * 100, 1)
                insights.append(ExplainabilityInsight(
                    type="weight_change",
                    message=(
                        f"{wc.feature_label} weight {direction} by {abs_change} "
                        f"percentage points ({round(wc.baseline_weight * 100, 1)}% "
                        f"-> {round(wc.simulation_weight * 100, 1)}%)."
                    ),
                    metric_value=wc.weight_change,
                    metric_unit="weight_fraction",
                ))

        # Score change summary
        if summary.candidates_with_score_changes > 0:
            insights.append(ExplainabilityInsight(
                type="score_change_summary",
                message=(
                    f"{summary.candidates_with_score_changes} of "
                    f"{summary.total_candidates} candidates experienced "
                    f"score changes."
                ),
                metric_value=summary.candidates_with_score_changes,
                metric_unit="candidates",
            ))

        if summary.largest_score_increase > 0:
            insights.append(ExplainabilityInsight(
                type="score_change_summary",
                message=(
                    f"Largest score increase: +{summary.largest_score_increase} points."
                ),
                metric_value=summary.largest_score_increase,
                metric_unit="points",
            ))

        if summary.largest_score_decrease < 0:
            insights.append(ExplainabilityInsight(
                type="score_change_summary",
                message=(
                    f"Largest score decrease: {summary.largest_score_decrease} points."
                ),
                metric_value=summary.largest_score_decrease,
                metric_unit="points",
            ))

        # Rank-only changes
        rank_only = [
            c for c in candidates if c.impact_type == "rank_only_changed"
        ]
        if rank_only:
            insights.append(ExplainabilityInsight(
                type="rank_only_change",
                message=(
                    f"{len(rank_only)} candidate(s) had rank changes without "
                    f"score changes, due to changes in relative ordering."
                ),
                metric_value=len(rank_only),
                metric_unit="candidates",
            ))

        # Threshold-only changes
        threshold_only = [
            c for c in candidates if c.impact_type == "threshold_only"
        ]
        if threshold_only:
            insights.append(ExplainabilityInsight(
                type="threshold_only_change",
                message=(
                    f"{len(threshold_only)} candidate(s) had qualification "
                    f"status changes without score changes (threshold-only effect)."
                ),
                metric_value=len(threshold_only),
                metric_unit="candidates",
            ))

        # Top contributing feature changes across all candidates
        if candidates:
            feature_impact_totals: dict[str, float] = {}
            for c in candidates:
                for fc in c.feature_contributions:
                    feature_impact_totals[fc.feature] = (
                        feature_impact_totals.get(fc.feature, 0.0)
                        + abs(fc.contribution_change)
                    )

            if feature_impact_totals:
                top_feature = max(feature_impact_totals, key=feature_impact_totals.get)  # type: ignore[arg-type]
                insights.append(ExplainabilityInsight(
                    type="dominant_feature",
                    message=(
                        f"'{_DIMENSION_LABELS.get(top_feature, top_feature)}' "
                        f"had the largest aggregate contribution change across "
                        f"all candidates."
                    ),
                    metric_value=round(feature_impact_totals[top_feature], 2),
                    metric_unit="total_contribution_change",
                ))

        return insights

    def _empty_response(
        self,
        scenario: SimulationScenario,
        execution: SimulationExecution,
    ) -> ExplainabilityImpactResponse:
        """Return a valid but empty analysis when no results exist."""
        return ExplainabilityImpactResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            summary=ExplainabilityImpactSummary(
                total_candidates=0,
                candidates_with_score_changes=0,
                candidates_with_rank_changes=0,
                candidates_with_contribution_changes=0,
                candidates_unchanged=0,
                average_score_change=0.0,
                largest_score_increase=0,
                largest_score_decrease=0,
            ),
            weight_changes=[],
            candidates=[],
            insights=[],
        )
