"""MultiScenarioComparisonService — Phase 10 Multi-Scenario Comparison.

Aggregates and compares persisted outputs from completed simulation
scenarios.  This is a READ-ONLY analysis layer that never modifies
live hiring data, simulation scenarios, or simulation results.

Architecture:
    Existing Phase 1-9 results + config snapshots
            ↓
    MultiScenarioComparisonService
            ↓
    Cross-scenario comparison response
"""

from __future__ import annotations

import statistics
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.simulation_comparison_schemas import (
    CandidateComparison,
    CandidatePoolComparison,
    CandidateScenarioOutcome,
    ComparisonInsight,
    ConfigurationComparison,
    ExplainabilityComparison,
    ExplainabilityScenarioSummary,
    FairnessComparison,
    FairnessScenarioMetric,
    MultiScenarioComparisonResponse,
    RankingComparison,
    RankingDistribution,
    RequirementComparison,
    RequirementComparisonItem,
    ScenarioMetadata,
    ShortlistOverlap,
    ShortlistSizeComparison,
    SkillComparison,
    SkillScenarioSummary,
    SkillRequirementComparison,
    SimulationComparisonRequest,
    ThresholdComparison,
    WeightComparison,
)
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationResult,
    SimulationScenario,
)
from app.domain.enums import SimulationStatus
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)
from app.services.screening.skill_graph import SkillGraph

logger = get_logger(__name__)

# Weight display labels
_WEIGHT_LABELS: dict[str, str] = {
    "skills": "Skills",
    "experience": "Experience",
    "education": "Education",
    "projects": "Projects",
    "certifications": "Certifications",
    "location": "Location",
    "employment_type": "Employment Type",
    "semantic": "Semantic Match",
}

_WEIGHT_KEYS = list(_WEIGHT_LABELS.keys())


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _normalize_skill(skill: str) -> str:
    return SkillGraph.normalize(skill)


class MultiScenarioComparisonService:
    """Compares multiple completed simulation scenarios.

    READ-ONLY: never writes to live hiring tables, simulation scenarios,
    or simulation results.
    """

    def __init__(
        self,
        session: AsyncSession,
        scenario_repo: SimulationRepository | None = None,
        execution_repo: SimulationExecutionRepository | None = None,
        result_repo: SimulationResultRepository | None = None,
    ) -> None:
        self._session = session
        self._scenario_repo = scenario_repo or SimulationRepository(session)
        self._exec_repo = execution_repo or SimulationExecutionRepository(session)
        self._result_repo = result_repo or SimulationResultRepository(session)

    async def compare(
        self, request: SimulationComparisonRequest,
    ) -> MultiScenarioComparisonResponse:
        """Run multi-scenario comparison.

        Args:
            request: Comparison request with 2–5 scenario IDs and include flags.

        Returns:
            Complete comparison response.

        Raises:
            ValidationError: If scenarios are incompatible.
            NotFoundError: If any scenario not found.
        """
        # 1. Load and validate scenarios
        scenarios, executions, results_map = await self._load_and_validate(request)

        # 2. Build metadata
        metadata = self._build_metadata(scenarios, executions)

        # 3. Build configuration comparison
        config_comparison = self._build_configuration_comparison(scenarios, executions)

        # 4. Build candidate pool comparison
        candidate_pool = self._build_candidate_pool(results_map)

        # 5. Build candidate-level comparison (common candidates)
        candidate_comparison = self._build_candidate_comparison(results_map, metadata)

        # 6. Build ranking comparison
        ranking_comparison = self._build_ranking_comparison(
            results_map, metadata, candidate_comparison,
        )

        # 7. Build requirement comparison
        requirement_comparison = self._build_requirement_comparison(scenarios, executions)

        # 8. Build fairness comparison (from persisted phase 7 data)
        fairness_comparison = self._build_fairness_comparison(executions)

        # 9. Build explainability comparison (from persisted phase 8 data)
        explainability_comparison = self._build_explainability_comparison(executions)

        # 10. Build skill comparison (from persisted phase 9 data)
        skill_comparison = self._build_skill_comparison(executions)

        # 11. Generate insights
        insights = self._generate_insights(
            metadata, config_comparison, candidate_comparison,
            ranking_comparison, requirement_comparison,
        )

        return MultiScenarioComparisonResponse(
            scenarios=metadata,
            configuration_comparison=config_comparison,
            candidate_pool=candidate_pool,
            candidate_comparison=candidate_comparison,
            ranking_comparison=ranking_comparison,
            requirement_comparison=requirement_comparison,
            fairness_comparison=fairness_comparison,
            explainability_comparison=explainability_comparison,
            skill_comparison=skill_comparison,
            insights=insights,
        )

    # ─── Loading & Validation ─────────────────────────────────────

    async def _load_and_validate(
        self,
        request: SimulationComparisonRequest,
    ) -> tuple[
        list[SimulationScenario],
        list[SimulationExecution],
        dict[str, list[SimulationResult]],
    ]:
        """Load scenarios, validate compatibility, and load results."""
        scenario_ids = request.scenario_ids

        # Deduplicate
        unique_ids = list(dict.fromkeys(scenario_ids))
        if len(unique_ids) != len(scenario_ids):
            raise ValidationError("Duplicate scenario IDs are not allowed.")
        if len(unique_ids) < 2:
            raise ValidationError("At least 2 distinct scenarios are required.")
        if len(unique_ids) > 5:
            raise ValidationError("At most 5 scenarios can be compared.")

        # Load scenarios
        scenarios: list[SimulationScenario] = []
        for sid in unique_ids:
            scenario = await self._scenario_repo.get_with_details(sid)
            if not scenario:
                raise NotFoundError(f"Scenario {sid} not found.")
            scenarios.append(scenario)

        # Validate same organization
        org_ids = {s.organization_id for s in scenarios}
        if len(org_ids) > 1:
            raise ValidationError(
                "All scenarios must belong to the same organization."
            )

        # Validate same job
        job_ids = {s.job_id for s in scenarios}
        if len(job_ids) > 1:
            raise ValidationError(
                "All scenarios must reference the same job for comparison."
            )

        # Load latest completed execution per scenario
        executions: list[SimulationExecution] = []
        for scenario in scenarios:
            execution = await self._exec_repo.latest_completed(scenario.id)
            if not execution:
                raise ValidationError(
                    f"Scenario '{scenario.name}' has no completed execution."
                )
            executions.append(execution)

        # Load results per execution
        results_map: dict[str, list[SimulationResult]] = {}
        for execution in executions:
            results = await self._result_repo.list_by_execution(execution.id)
            results_map[str(execution.id)] = results

        return scenarios, executions, results_map

    # ─── Metadata ─────────────────────────────────────────────────

    def _build_metadata(
        self,
        scenarios: list[SimulationScenario],
        executions: list[SimulationExecution],
    ) -> list[ScenarioMetadata]:
        """Build scenario metadata list."""
        metadata = []
        for scenario, execution in zip(scenarios, executions):
            job = scenario.job
            creator = scenario.creator
            metadata.append(ScenarioMetadata(
                scenario_id=scenario.id,
                execution_id=execution.id,
                name=scenario.name,
                description=scenario.description,
                job_id=scenario.job_id,
                job_title=job.title if job else "",
                company=job.company if job else "",
                created_by_name=creator.full_name if creator else "",
                created_at=scenario.created_at,
                completed_at=execution.completed_at,
                engine_version=execution.engine_version,
                total_candidates=execution.total_candidates,
                processed_candidates=execution.processed_candidates,
                status=execution.status,
            ))
        return metadata

    # ─── Configuration Comparison ─────────────────────────────────

    def _build_configuration_comparison(
        self,
        scenarios: list[SimulationScenario],
        executions: list[SimulationExecution],
    ) -> ConfigurationComparison:
        """Compare configurations across scenarios."""
        # Extract scoring weights per scenario
        weights_per_scenario: dict[str, dict[str, float]] = {}
        thresholds: dict[str, int] = {}
        shortlist_sizes: dict[str, int] = {}
        skills_per_scenario: dict[str, dict[str, set[str]]] = {}

        for scenario, execution in zip(scenarios, executions):
            sid = str(scenario.id)
            snapshot = execution.configuration_snapshot or {}
            sim_config = snapshot.get("simulation") or {}
            weights = sim_config.get("scoring_weights") or {}
            thresholds[sid] = sim_config.get("threshold", 70)
            shortlist_sizes[sid] = sim_config.get("shortlist_size", 10)

            # Store weights
            w: dict[str, float] = {}
            for key in _WEIGHT_KEYS:
                w[key] = round(weights.get(key, 0.0), 4)
            weights_per_scenario[sid] = w

            # Store skill requirements
            reqs = sim_config.get("requirements") or {}
            mandatory = {
                _normalize_skill(s)
                for s in (reqs.get("mandatory_skills") or [])
                if isinstance(s, str)
            }
            preferred = {
                _normalize_skill(s)
                for s in (reqs.get("preferred_skills") or [])
                if isinstance(s, str)
            }
            skills_per_scenario[sid] = {
                "mandatory": mandatory,
                "preferred": preferred,
            }

        # Build weight comparisons
        weight_comparisons: list[WeightComparison] = []
        for key in _WEIGHT_KEYS:
            values = {
                sid: weights_per_scenario[sid].get(key, 0.0)
                for sid in weights_per_scenario
            }
            vals = list(values.values())
            wc = WeightComparison(
                weight_name=key,
                weight_label=_WEIGHT_LABELS.get(key, key),
                values=values,
                min_value=min(vals) if vals else 0.0,
                max_value=max(vals) if vals else 0.0,
                range_spread=round(max(vals) - min(vals), 4) if vals else 0.0,
            )
            weight_comparisons.append(wc)

        # Build threshold comparison
        t_vals = list(thresholds.values())
        threshold_comp = ThresholdComparison(
            values=thresholds,
            min_value=min(t_vals) if t_vals else 0,
            max_value=max(t_vals) if t_vals else 0,
        )

        # Build shortlist size comparison
        s_vals = list(shortlist_sizes.values())
        shortlist_comp = ShortlistSizeComparison(
            values=shortlist_sizes,
            min_value=min(s_vals) if s_vals else 0,
            max_value=max(s_vals) if s_vals else 0,
        )

        # Build skill requirement comparisons
        all_skills: set[str] = set()
        for skill_data in skills_per_scenario.values():
            all_skills.update(skill_data["mandatory"])
            all_skills.update(skill_data["preferred"])

        skill_req_comparisons: list[SkillRequirementComparison] = []
        skills_added: list[str] = []
        skills_removed: list[str] = []
        skills_promoted: list[str] = []
        skills_demoted: list[str] = []

        for skill in sorted(all_skills):
            values: dict[str, str] = {}
            first_req = None
            for sid in skills_per_scenario:
                if skill in skills_per_scenario[sid]["mandatory"]:
                    values[sid] = "mandatory"
                elif skill in skills_per_scenario[sid]["preferred"]:
                    values[sid] = "preferred"
                else:
                    values[sid] = "not_required"
                if first_req is None:
                    first_req = values[sid]

            unique_reqs = set(values.values())
            if len(unique_reqs) == 1:
                change_type = "unchanged"
            else:
                # Determine the most significant change
                has_mandatory = "mandatory" in unique_reqs
                has_preferred = "preferred" in unique_reqs
                has_not_required = "not_required" in unique_reqs

                if has_not_required and (has_mandatory or has_preferred):
                    change_type = "added"
                elif (has_mandatory or has_preferred) and has_not_required:
                    change_type = "removed"
                elif has_mandatory and has_preferred:
                    # Check direction
                    first_val = first_req
                    if first_val == "preferred":
                        change_type = "promoted"
                    else:
                        change_type = "demoted"
                else:
                    change_type = "unchanged"

            is_changed = change_type != "unchanged"
            scr = SkillRequirementComparison(
                skill_name=skill,
                values=values,
                change_type=change_type,
            )
            skill_req_comparisons.append(scr)

            if is_changed:
                if change_type == "added":
                    skills_added.append(skill)
                elif change_type == "removed":
                    skills_removed.append(skill)
                elif change_type == "promoted":
                    skills_promoted.append(skill)
                elif change_type == "demoted":
                    skills_demoted.append(skill)

        return ConfigurationComparison(
            weights=weight_comparisons,
            threshold=threshold_comp,
            shortlist_size=shortlist_comp,
            skill_requirements=skill_req_comparisons,
            skills_added=skills_added,
            skills_removed=skills_removed,
            skills_promoted=skills_promoted,
            skills_demoted=skills_demoted,
        )

    # ─── Candidate Pool Comparison ────────────────────────────────

    def _build_candidate_pool(
        self, results_map: dict[str, list[SimulationResult]],
    ) -> CandidatePoolComparison:
        """Compare candidate pools across scenarios."""
        candidate_sets: dict[str, set[uuid.UUID]] = {}
        for exec_id, results in results_map.items():
            candidate_sets[exec_id] = {r.candidate_id for r in results}

        all_ids = set()
        for s in candidate_sets.values():
            all_ids.update(s)

        if not all_ids:
            return CandidatePoolComparison(total_unique=0)

        common = all_ids.copy()
        for s in candidate_sets.values():
            common &= s

        scenario_only: dict[str, int] = {}
        for exec_id, cands in candidate_sets.items():
            scenario_only[exec_id] = len(cands - common)

        identical = all(
            cands == common for cands in candidate_sets.values()
        ) and len(candidate_sets) > 1

        return CandidatePoolComparison(
            identical_pools=identical,
            common_candidates=len(common),
            scenario_only_counts=scenario_only,
            total_unique=len(all_ids),
        )

    # ─── Candidate Comparison ─────────────────────────────────────

    def _build_candidate_comparison(
        self,
        results_map: dict[str, list[SimulationResult]],
        metadata: list[ScenarioMetadata],
    ) -> list[CandidateComparison]:
        """Build per-candidate cross-scenario comparison."""
        # Build candidate -> {exec_id: result} mapping
        candidate_results: dict[uuid.UUID, dict[str, SimulationResult]] = defaultdict(dict)
        for exec_id, results in results_map.items():
            for r in results:
                candidate_results[r.candidate_id][exec_id] = r

        comparisons: list[CandidateComparison] = []

        for candidate_id, exec_results in candidate_results.items():
            # Get baseline from first scenario
            first_exec_id = str(metadata[0].execution_id)
            first_result = exec_results.get(first_exec_id)
            if not first_result:
                continue

            scenario_outcomes: list[CandidateScenarioOutcome] = []
            ranks: list[int] = []
            scores: list[int] = []
            qualified_count = 0
            shortlisted_count = 0

            for meta in metadata:
                exec_id_str = str(meta.execution_id)
                result = exec_results.get(exec_id_str)
                if not result:
                    continue

                outcome = CandidateScenarioOutcome(
                    scenario_id=str(meta.scenario_id),
                    simulation_score=result.simulation_score,
                    simulation_rank=result.simulation_rank,
                    score_change=result.score_change,
                    rank_change=result.rank_change,
                    qualified=result.simulation_status == "qualified",
                    shortlisted=result.simulation_shortlisted,
                    matched_skills=result.simulation_matched_skills or [],
                    missing_required=result.simulation_missing_required or [],
                )
                scenario_outcomes.append(outcome)
                ranks.append(result.simulation_rank)
                scores.append(result.simulation_score)
                if outcome.qualified:
                    qualified_count += 1
                if outcome.shortlisted:
                    shortlisted_count += 1

            if len(scenario_outcomes) < 2:
                continue

            comparisons.append(CandidateComparison(
                candidate_id=candidate_id,
                candidate_name=first_result.candidate_name,
                baseline_score=first_result.baseline_score,
                baseline_rank=first_result.baseline_rank,
                scenarios=scenario_outcomes,
                rank_range_min=min(ranks),
                rank_range_max=max(ranks),
                score_range_min=min(scores),
                score_range_max=max(scores),
                max_rank_movement=max(ranks) - min(ranks),
                qualified_count=qualified_count,
                shortlisted_count=shortlisted_count,
            ))

        # Sort by max rank movement descending
        comparisons.sort(key=lambda c: c.max_rank_movement, reverse=True)
        return comparisons

    # ─── Ranking Comparison ───────────────────────────────────────

    def _build_ranking_comparison(
        self,
        results_map: dict[str, list[SimulationResult]],
        metadata: list[ScenarioMetadata],
        candidate_comparisons: list[CandidateComparison],
    ) -> RankingComparison:
        """Build aggregate ranking comparison."""
        distributions: list[RankingDistribution] = []

        for meta in metadata:
            exec_id_str = str(meta.execution_id)
            results = results_map.get(exec_id_str, [])
            if not results:
                continue

            scores = [r.simulation_score for r in results]
            ranks = [r.simulation_rank for r in results]
            qualified = sum(1 for r in results if r.simulation_status == "qualified")
            shortlisted = sum(1 for r in results if r.simulation_shortlisted)

            distributions.append(RankingDistribution(
                scenario_id=str(meta.scenario_id),
                total_candidates=len(results),
                avg_score=round(_safe_divide(sum(scores), len(scores)), 2),
                median_score=round(statistics.median(scores) if scores else 0, 2),
                avg_rank=round(_safe_divide(sum(ranks), len(ranks)), 2),
                qualified_count=qualified,
                shortlisted_count=shortlisted,
            ))

        # Pairwise shortlist overlaps
        overlaps: list[ShortlistOverlap] = []
        for i, meta_a in enumerate(metadata):
            for meta_b in metadata[i + 1:]:
                results_a = results_map.get(str(meta_a.execution_id), [])
                results_b = results_map.get(str(meta_b.execution_id), [])

                shortlisted_a = {
                    r.candidate_id for r in results_a if r.simulation_shortlisted
                }
                shortlisted_b = {
                    r.candidate_id for r in results_b if r.simulation_shortlisted
                }

                common = shortlisted_a & shortlisted_b
                only_a = shortlisted_a - shortlisted_b
                only_b = shortlisted_b - shortlisted_a
                union = shortlisted_a | shortlisted_b

                jaccard = _safe_divide(len(common), len(union))

                overlaps.append(ShortlistOverlap(
                    scenario_a_id=str(meta_a.scenario_id),
                    scenario_b_id=str(meta_b.scenario_id),
                    shortlist_a_count=len(shortlisted_a),
                    shortlist_b_count=len(shortlisted_b),
                    common_count=len(common),
                    only_a_count=len(only_a),
                    only_b_count=len(only_b),
                    jaccard_similarity=round(jaccard, 4),
                ))

        # Top movers and most stable
        top_movers = candidate_comparisons[:10]
        most_stable = sorted(
            candidate_comparisons, key=lambda c: c.max_rank_movement,
        )[:10]

        return RankingComparison(
            distributions=distributions,
            pairwise_overlaps=overlaps,
            top_movers=top_movers,
            most_stable=most_stable,
        )

    # ─── Requirement Comparison ───────────────────────────────────

    def _build_requirement_comparison(
        self,
        scenarios: list[SimulationScenario],
        executions: list[SimulationExecution],
    ) -> RequirementComparison:
        """Compare requirements across scenarios."""
        items: list[RequirementComparisonItem] = []

        # Extract requirements per scenario
        reqs_per_scenario: dict[str, dict] = {}
        for scenario, execution in zip(scenarios, executions):
            sid = str(scenario.id)
            snapshot = execution.configuration_snapshot or {}
            sim_config = snapshot.get("simulation") or {}
            reqs_per_scenario[sid] = sim_config.get("requirements") or {}

        # Compare mandatory skills
        all_mandatory: dict[str, dict[str, bool]] = defaultdict(dict)
        all_preferred: dict[str, dict[str, bool]] = defaultdict(dict)

        for sid, reqs in reqs_per_scenario.items():
            mandatory = {
                _normalize_skill(s)
                for s in (reqs.get("mandatory_skills") or [])
                if isinstance(s, str)
            }
            preferred = {
                _normalize_skill(s)
                for s in (reqs.get("preferred_skills") or [])
                if isinstance(s, str)
            }
            for skill in mandatory | preferred:
                all_mandatory[skill][sid] = skill in mandatory
                all_preferred[skill][sid] = skill in preferred

        # Build items
        for skill in sorted(set(all_mandatory.keys()) | set(all_preferred.keys())):
            values: dict[str, str] = {}
            for sid in reqs_per_scenario:
                if all_mandatory.get(skill, {}).get(sid, False):
                    values[sid] = "mandatory"
                elif all_preferred.get(skill, {}).get(sid, False):
                    values[sid] = "preferred"
                else:
                    values[sid] = "not_required"

            unique_vals = set(values.values())
            is_changed = len(unique_vals) > 1

            items.append(RequirementComparisonItem(
                requirement_type="skill",
                requirement_name=skill,
                values=values,
                is_changed=is_changed,
            ))

        total_changed = sum(1 for item in items if item.is_changed)

        return RequirementComparison(
            items=items,
            total_changed=total_changed,
        )

    # ─── Fairness Comparison ──────────────────────────────────────

    def _build_fairness_comparison(
        self, executions: list[SimulationExecution],
    ) -> FairnessComparison:
        """Build fairness comparison from persisted execution summaries."""
        scenario_metrics: list[FairnessScenarioMetric] = []
        any_available = False

        for execution in executions:
            summary = execution.summary or {}
            # Fairness data might be in summary or stored elsewhere
            # For now, check if summary has fairness-related keys
            fairness_data = summary.get("fairness") or summary.get("fairness_metrics")

            if fairness_data:
                any_available = True
                scenario_metrics.append(FairnessScenarioMetric(
                    scenario_id=str(execution.scenario_id),
                    available=True,
                    groups=fairness_data.get("groups", []) if isinstance(fairness_data, dict) else [],
                    cross_group=fairness_data.get("cross_group", []) if isinstance(fairness_data, dict) else [],
                    insight_count=fairness_data.get("insight_count", 0) if isinstance(fairness_data, dict) else 0,
                ))
            else:
                scenario_metrics.append(FairnessScenarioMetric(
                    scenario_id=str(execution.scenario_id),
                    available=False,
                    unavailable_reason="Fairness data not available in execution summary.",
                ))

        return FairnessComparison(
            scenarios=scenario_metrics,
            any_available=any_available,
        )

    # ─── Explainability Comparison ────────────────────────────────

    def _build_explainability_comparison(
        self, executions: list[SimulationExecution],
    ) -> ExplainabilityComparison:
        """Build explainability comparison from persisted execution summaries."""
        scenario_summaries: list[ExplainabilityScenarioSummary] = []
        any_available = False

        for execution in executions:
            summary = execution.summary or {}
            xai_data = summary.get("explainability") or summary.get("xai")

            if xai_data:
                any_available = True
                scenario_summaries.append(ExplainabilityScenarioSummary(
                    scenario_id=str(execution.scenario_id),
                    available=True,
                    total_candidates=xai_data.get("total_candidates", 0) if isinstance(xai_data, dict) else 0,
                    candidates_with_changes=xai_data.get("candidates_with_changes", 0) if isinstance(xai_data, dict) else 0,
                    avg_score_change=xai_data.get("avg_score_change", 0.0) if isinstance(xai_data, dict) else 0.0,
                    weight_changes=xai_data.get("weight_changes", []) if isinstance(xai_data, dict) else [],
                    top_insight=xai_data.get("top_insight", "") if isinstance(xai_data, dict) else "",
                ))
            else:
                scenario_summaries.append(ExplainabilityScenarioSummary(
                    scenario_id=str(execution.scenario_id),
                    available=False,
                ))

        return ExplainabilityComparison(
            scenarios=scenario_summaries,
            any_available=any_available,
        )

    # ─── Skill Comparison ─────────────────────────────────────────

    def _build_skill_comparison(
        self, executions: list[SimulationExecution],
    ) -> SkillComparison:
        """Build skill comparison from persisted execution summaries."""
        scenario_summaries: list[SkillScenarioSummary] = []
        any_available = False

        for execution in executions:
            summary = execution.summary or {}
            skill_data = summary.get("skill_impact") or summary.get("skills")

            if skill_data:
                any_available = True
                scenario_summaries.append(SkillScenarioSummary(
                    scenario_id=str(execution.scenario_id),
                    available=True,
                    total_skills_analyzed=skill_data.get("total_skills_analyzed", 0) if isinstance(skill_data, dict) else 0,
                    skills_added=skill_data.get("skills_added", 0) if isinstance(skill_data, dict) else 0,
                    skills_removed=skill_data.get("skills_removed", 0) if isinstance(skill_data, dict) else 0,
                    skills_promoted=skill_data.get("skills_promoted", 0) if isinstance(skill_data, dict) else 0,
                    skills_demoted=skill_data.get("skills_demoted", 0) if isinstance(skill_data, dict) else 0,
                    candidates_affected=skill_data.get("candidates_affected", 0) if isinstance(skill_data, dict) else 0,
                    top_gaps=skill_data.get("top_gaps", []) if isinstance(skill_data, dict) else [],
                ))
            else:
                scenario_summaries.append(SkillScenarioSummary(
                    scenario_id=str(execution.scenario_id),
                    available=False,
                ))

        return SkillComparison(
            scenarios=scenario_summaries,
            any_available=any_available,
        )

    # ─── Insights ─────────────────────────────────────────────────

    def _generate_insights(
        self,
        metadata: list[ScenarioMetadata],
        config: ConfigurationComparison,
        candidates: list[CandidateComparison],
        ranking: RankingComparison,
        requirements: RequirementComparison,
    ) -> list[ComparisonInsight]:
        """Generate deterministic factual insights."""
        insights: list[ComparisonInsight] = []

        # Threshold differences
        if config.threshold.min_value != config.threshold.max_value:
            insights.append(ComparisonInsight(
                type="threshold_difference",
                message=(
                    f"Threshold varies from {config.threshold.min_value} to "
                    f"{config.threshold.max_value} across scenarios."
                ),
                metric_value=config.threshold.max_value - config.threshold.min_value,
                metric_unit="points",
            ))

        # Shortlist size differences
        if config.shortlist_size.min_value != config.shortlist_size.max_value:
            insights.append(ComparisonInsight(
                type="shortlist_size_difference",
                message=(
                    f"Shortlist size varies from {config.shortlist_size.min_value} to "
                    f"{config.shortlist_size.max_value} across scenarios."
                ),
                metric_value=config.shortlist_size.max_value - config.shortlist_size.min_value,
                metric_unit="candidates",
            ))

        # Weight spread
        max_spread_wc = max(config.weights, key=lambda w: w.range_spread, default=None)
        if max_spread_wc and max_spread_wc.range_spread > 0:
            insights.append(ComparisonInsight(
                type="weight_difference",
                message=(
                    f"'{max_spread_wc.weight_label}' weight has the largest spread "
                    f"({round(max_spread_wc.range_spread * 100, 1)} pp) across scenarios."
                ),
                metric_value=round(max_spread_wc.range_spread * 100, 1),
                metric_unit="percentage_points",
            ))

        # Requirement changes
        if requirements.skills_added:
            insights.append(ComparisonInsight(
                type="requirement_change",
                message=(
                    f"{len(requirements.skills_added)} skill(s) added across scenarios: "
                    f"{', '.join(requirements.skills_added[:3])}"
                    f"{'...' if len(requirements.skills_added) > 3 else ''}."
                ),
                metric_value=len(requirements.skills_added),
                metric_unit="skills",
            ))

        if requirements.skills_removed:
            insights.append(ComparisonInsight(
                type="requirement_change",
                message=(
                    f"{len(requirements.skills_removed)} skill(s) removed across scenarios: "
                    f"{', '.join(requirements.skills_removed[:3])}"
                    f"{'...' if len(requirements.skills_removed) > 3 else ''}."
                ),
                metric_value=len(requirements.skills_removed),
                metric_unit="skills",
            ))

        # Candidate pool
        if candidates:
            most_moved = candidates[0]
            insights.append(ComparisonInsight(
                type="candidate_movement",
                message=(
                    f"'{most_moved.candidate_name}' has the largest rank movement "
                    f"(rank range: {most_moved.rank_range_min}–{most_moved.rank_range_max})."
                ),
                metric_value=most_moved.max_rank_movement,
                metric_unit="ranks",
            ))

        # Shortlist overlap
        for overlap in ranking.pairwise_overlaps:
            if overlap.common_count > 0:
                insights.append(ComparisonInsight(
                    type="shortlist_overlap",
                    message=(
                        f"{overlap.common_count} candidate(s) appear in both shortlists. "
                        f"Jaccard similarity: {round(overlap.jaccard_similarity * 100, 1)}%."
                    ),
                    metric_value=overlap.common_count,
                    metric_unit="candidates",
                    scenario_ids=[overlap.scenario_a_id, overlap.scenario_b_id],
                ))

        return insights
