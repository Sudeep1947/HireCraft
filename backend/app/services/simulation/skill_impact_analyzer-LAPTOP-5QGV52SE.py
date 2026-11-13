"""SkillImpactAnalyzer — Phase 9 Skill Impact Simulation.

Consumes persisted Phase 3 results (SimulationResult, SimulationExecution)
and configuration snapshots to compare skill-related changes between
baseline and simulation hiring configurations.

Architecture:
    Phase 3: Candidate Pool -> Baseline Evaluation -> Simulation Evaluation
             -> Persist Candidate Results (with per-skill matched/missing data)
    Phase 9: Persisted Candidate Results + Config Snapshots
             + Existing SkillGraph + MatchingEngine
             -> Skill Impact Analyzer -> Skill Change Detection
             -> Coverage/Gap Analysis -> Candidate Impact -> Frontend

This service is READ-ONLY with respect to production hiring data.
It never modifies JobDescription, Candidate, CandidateRanking, or any
live hiring records.

All calculations are deterministic and derived from actual simulation
results, configuration snapshots, and existing Skill Intelligence data.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.skill_impact_schemas import (
    CandidateSkillImpact,
    SkillChange,
    SkillCoverage,
    SkillGap,
    SkillGraphRelationship,
    SkillImpactInsight,
    SkillImpactResponse,
    SkillImpactSummary,
)
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationResult,
    SimulationScenario,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)
from app.services.screening.skill_graph import SkillGraph

logger = get_logger(__name__)


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _normalize_skill(skill: str) -> str:
    """Normalize a skill name using the existing SkillGraph canonical form."""
    return SkillGraph.normalize(skill)


def _skill_list(config: dict, key: str) -> list[str]:
    """Extract a normalized skill list from a config dict."""
    requirements = config.get("requirements") or {}
    raw = requirements.get(key) or []
    return [_normalize_skill(s) for s in raw if isinstance(s, str)]


def _skill_list_raw(config: dict, key: str) -> list[str]:
    """Extract the raw (un-normalized) skill list from a config dict."""
    requirements = config.get("requirements") or {}
    raw = requirements.get(key) or []
    return [s for s in raw if isinstance(s, str)]


def _detect_skill_changes(
    baseline: dict, simulation: dict,
) -> list[SkillChange]:
    """Detect all skill requirement changes between baseline and simulation configs.

    Returns a list of SkillChange objects describing added, removed, promoted,
    demoted, and unchanged skills.
    """
    base_mandatory = set(_skill_list(baseline, "mandatory_skills"))
    base_preferred = set(_skill_list(baseline, "preferred_skills"))
    sim_mandatory = set(_skill_list(simulation, "mandatory_skills"))
    sim_preferred = set(_skill_list(simulation, "preferred_skills"))

    # Display name maps: normalized -> original
    base_mandatory_names = {
        _normalize_skill(s): s
        for s in _skill_list_raw(baseline, "mandatory_skills")
    }
    base_preferred_names = {
        _normalize_skill(s): s
        for s in _skill_list_raw(baseline, "preferred_skills")
    }
    sim_mandatory_names = {
        _normalize_skill(s): s
        for s in _skill_list_raw(simulation, "mandatory_skills")
    }
    sim_preferred_names = {
        _normalize_skill(s): s
        for s in _skill_list_raw(simulation, "preferred_skills")
    }

    all_skills = base_mandatory | base_preferred | sim_mandatory | sim_preferred
    changes: list[SkillChange] = []
    seen: set[str] = set()

    for skill in sorted(all_skills):
        # Determine baseline requirement
        if skill in base_mandatory:
            base_req = "mandatory"
        elif skill in base_preferred:
            base_req = "preferred"
        else:
            base_req = "not_required"

        # Determine simulation requirement
        if skill in sim_mandatory:
            sim_req = "mandatory"
        elif skill in sim_preferred:
            sim_req = "preferred"
        else:
            sim_req = "not_required"

        # Determine change type
        if base_req == sim_req:
            change_type = "unchanged"
        elif base_req == "not_required" and sim_req == "mandatory":
            change_type = "added"
        elif base_req == "not_required" and sim_req == "preferred":
            change_type = "added"
        elif base_req == "mandatory" and sim_req == "not_required":
            change_type = "removed"
        elif base_req == "preferred" and sim_req == "not_required":
            change_type = "removed"
        elif base_req == "preferred" and sim_req == "mandatory":
            change_type = "promoted"
        elif base_req == "mandatory" and sim_req == "preferred":
            change_type = "demoted"
        else:
            change_type = "unchanged"

        # Get display name (prefer simulation, fallback to baseline)
        display_name = (
            sim_mandatory_names.get(skill)
            or sim_preferred_names.get(skill)
            or base_mandatory_names.get(skill)
            or base_preferred_names.get(skill)
            or skill
        )

        if display_name.lower() in seen:
            continue
        seen.add(display_name.lower())

        changes.append(SkillChange(
            skill_name=display_name,
            change_type=change_type,
            baseline_requirement=base_req,
            simulation_requirement=sim_req,
        ))

    return changes


class SkillImpactAnalyzer:
    """Analyzes skill impact from persisted Phase 3 simulation results.

    This is a READ-ONLY analyzer. It consumes SimulationResult rows
    produced by Phase 3 and configuration snapshots to compute per-skill
    coverage, gaps, and candidate impact. It reuses the existing SkillGraph
    and skill-matching semantics from the Skill Intelligence system.

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
    ) -> SkillImpactResponse:
        """Run the full skill impact analysis.

        Args:
            simulation_id: The simulation scenario ID.
            execution_id: Optional specific execution ID. If None, uses
                         the latest completed execution.

        Returns:
            Complete skill impact analysis response.

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

        # 1. Detect skill changes
        skill_changes = _detect_skill_changes(baseline_config, simulation_config)

        # 2. Compute coverage for each skill
        skill_coverage = self._compute_skill_coverage(
            results, skill_changes, baseline_config, simulation_config,
        )

        # 3. Compute gaps
        skill_gaps = self._compute_skill_gaps(skill_coverage)

        # 4. Compute candidate impacts
        candidate_impacts = self._compute_candidate_impacts(
            results, skill_changes, baseline_config, simulation_config,
        )

        # 5. Enrich skill changes with candidate metrics
        self._enrich_skill_changes(
            skill_changes, results, baseline_config, simulation_config,
        )

        # 6. Compute Skill Graph relationships for changed skills
        graph_relationships = self._compute_graph_relationships(skill_changes)

        # 7. Build summary
        summary = self._compute_summary(
            skill_changes, candidate_impacts, results,
        )

        # 8. Generate insights
        insights = self._generate_insights(
            summary, skill_changes, skill_gaps, candidate_impacts,
        )

        return SkillImpactResponse(
            simulation_id=simulation_id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            summary=summary,
            skill_changes=skill_changes,
            skill_coverage=skill_coverage,
            skill_gaps=skill_gaps,
            skill_graph_relationships=graph_relationships,
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

    def _compute_skill_coverage(
        self,
        results: list[SimulationResult],
        skill_changes: list[SkillChange],
        baseline_config: dict,
        simulation_config: dict,
    ) -> list[SkillCoverage]:
        """Compute per-skill coverage metrics for all relevant skills."""
        total = len(results)
        if total == 0:
            return []

        # Build skill sets for baseline and simulation
        base_mandatory = set(_skill_list(baseline_config, "mandatory_skills"))
        base_preferred = set(_skill_list(baseline_config, "preferred_skills"))
        sim_mandatory = set(_skill_list(simulation_config, "mandatory_skills"))
        sim_preferred = set(_skill_list(simulation_config, "preferred_skills"))

        # All relevant skills (union of both configs)
        all_skills = base_mandatory | base_preferred | sim_mandatory | sim_preferred

        coverage_list: list[SkillCoverage] = []

        for skill in sorted(all_skills):
            # Count how many candidates match this skill in baseline and simulation
            baseline_match_count = 0
            simulation_match_count = 0

            for r in results:
                base_matched = r.baseline_matched_skills or []
                sim_matched = r.simulation_matched_skills or []

                if any(_normalize_skill(s) == skill for s in base_matched):
                    baseline_match_count += 1
                if any(_normalize_skill(s) == skill for s in sim_matched):
                    simulation_match_count += 1

            baseline_coverage = _safe_divide(baseline_match_count, total)
            simulation_coverage = _safe_divide(simulation_match_count, total)

            coverage_list.append(SkillCoverage(
                skill_name=skill,
                baseline_coverage=round(baseline_coverage, 4),
                simulation_coverage=round(simulation_coverage, 4),
                coverage_change=round(simulation_coverage - baseline_coverage, 4),
                baseline_candidates_match=baseline_match_count,
                simulation_candidates_match=simulation_match_count,
                total_eligible=total,
                is_mandatory_baseline=skill in base_mandatory,
                is_mandatory_simulation=skill in sim_mandatory,
                is_preferred_baseline=skill in base_preferred,
                is_preferred_simulation=skill in sim_preferred,
            ))

        return coverage_list

    def _compute_skill_gaps(
        self, skill_coverage: list[SkillCoverage],
    ) -> list[SkillGap]:
        """Compute skill gaps from coverage data."""
        gaps: list[SkillGap] = []

        for sc in skill_coverage:
            baseline_gap = 1.0 - sc.baseline_coverage
            simulation_gap = 1.0 - sc.simulation_coverage

            gaps.append(SkillGap(
                skill_name=sc.skill_name,
                baseline_gap=round(baseline_gap, 4),
                simulation_gap=round(simulation_gap, 4),
                gap_change=round(simulation_gap - baseline_gap, 4),
                is_required=sc.is_mandatory_simulation,
                coverage_unavailable=False,
            ))

        return gaps

    def _compute_candidate_impacts(
        self,
        results: list[SimulationResult],
        skill_changes: list[SkillChange],
        baseline_config: dict,
        simulation_config: dict,
    ) -> list[CandidateSkillImpact]:
        """Compute per-candidate skill impact."""
        impacts: list[CandidateSkillImpact] = []

        # Build set of changed skill names (normalized) for quick lookup
        changed_skills = {
            _normalize_skill(sc.skill_name)
            for sc in skill_changes
            if sc.change_type != "unchanged"
        }

        base_mandatory = set(_skill_list(baseline_config, "mandatory_skills"))
        sim_mandatory = set(_skill_list(simulation_config, "mandatory_skills"))

        for r in results:
            base_matched = set(
                _normalize_skill(s) for s in (r.baseline_matched_skills or [])
            )
            sim_matched = set(
                _normalize_skill(s) for s in (r.simulation_matched_skills or [])
            )
            base_missing_req = set(
                _normalize_skill(s) for s in (r.baseline_missing_required or [])
            )
            sim_missing_req = set(
                _normalize_skill(s) for s in (r.simulation_missing_required or [])
            )

            # Skills gained/lost
            skills_gained = sorted(sim_matched - base_matched)
            skills_lost = sorted(base_matched - sim_matched)

            # Required skills: newly satisfied / newly unsatisfied
            newly_satisfied = sorted(base_missing_req - sim_missing_req)
            newly_unsatisfied = sorted(sim_missing_req - base_missing_req)

            # Only include candidates with at least one skill-related change
            has_change = (
                bool(skills_gained)
                or bool(skills_lost)
                or bool(newly_satisfied)
                or bool(newly_unsatisfied)
                or r.score_change != 0
                or r.rank_change != 0
            )

            if not has_change:
                continue

            # Qualification change
            base_qualified = r.baseline_status == "qualified"
            sim_qualified = r.simulation_status == "qualified"
            if base_qualified and sim_qualified:
                qual_change = "remained_qualified"
            elif not base_qualified and sim_qualified:
                qual_change = "newly_qualified"
            elif base_qualified and not sim_qualified:
                qual_change = "newly_disqualified"
            else:
                qual_change = "remained_unqualified"

            impacts.append(CandidateSkillImpact(
                candidate_id=r.candidate_id,
                candidate_name=r.candidate_name,
                baseline_matched_skills=sorted(base_matched),
                simulation_matched_skills=sorted(sim_matched),
                skills_gained=skills_gained,
                skills_lost=skills_lost,
                baseline_missing_required=sorted(base_missing_req),
                simulation_missing_required=sorted(sim_missing_req),
                newly_satisfied_required=newly_satisfied,
                newly_unsatisfied_required=newly_unsatisfied,
                baseline_score=r.baseline_score,
                simulation_score=r.simulation_score,
                score_change=r.score_change,
                baseline_rank=r.baseline_rank,
                simulation_rank=r.simulation_rank,
                rank_change=r.rank_change,
                baseline_qualified=base_qualified,
                simulation_qualified=sim_qualified,
                qualification_change=qual_change,
                skill_match_change=len(sim_matched) - len(base_matched),
            ))

        # Sort by absolute score change descending
        impacts.sort(key=lambda c: abs(c.score_change), reverse=True)
        return impacts

    def _enrich_skill_changes(
        self,
        skill_changes: list[SkillChange],
        results: list[SimulationResult],
        baseline_config: dict,
        simulation_config: dict,
    ) -> None:
        """Enrich skill change objects with candidate-level metrics."""
        total = len(results)
        if total == 0:
            return

        for sc in skill_changes:
            skill_norm = _normalize_skill(sc.skill_name)

            baseline_match_count = 0
            simulation_match_count = 0

            for r in results:
                base_matched = r.baseline_matched_skills or []
                sim_matched = r.simulation_matched_skills or []

                if any(_normalize_skill(s) == skill_norm for s in base_matched):
                    baseline_match_count += 1
                if any(_normalize_skill(s) == skill_norm for s in sim_matched):
                    simulation_match_count += 1

            sc.baseline_candidates_match = baseline_match_count
            sc.simulation_candidates_match = simulation_match_count

            base_cov = _safe_divide(baseline_match_count, total)
            sim_cov = _safe_divide(simulation_match_count, total)
            sc.coverage_change = round(sim_cov - base_cov, 4)

            # Count candidates affected by this skill change
            if sc.change_type == "unchanged":
                sc.candidates_affected = 0
                continue

            affected = 0
            newly_qualified = 0
            newly_disqualified = 0

            for r in results:
                base_matched = r.baseline_matched_skills or []
                sim_matched = r.simulation_matched_skills or []

                base_has = any(_normalize_skill(s) == skill_norm for s in base_matched)
                sim_has = any(_normalize_skill(s) == skill_norm for s in sim_matched)

                if base_has != sim_has:
                    affected += 1

                # Mandatory skill qualification impact
                is_mandatory_sim = skill_norm in set(
                    _skill_list(simulation_config, "mandatory_skills")
                )
                if is_mandatory_sim:
                    if not base_has and sim_has:
                        # Candidate gained this mandatory skill
                        if r.baseline_status != "qualified" and r.simulation_status == "qualified":
                            newly_qualified += 1
                    elif base_has and not sim_has:
                        # Candidate lost this mandatory skill
                        if r.baseline_status == "qualified" and r.simulation_status != "qualified":
                            newly_disqualified += 1

            sc.candidates_affected = affected
            sc.candidates_newly_qualified = newly_qualified
            sc.candidates_newly_disqualified = newly_disqualified

    def _compute_graph_relationships(
        self, skill_changes: list[SkillChange],
    ) -> list[SkillGraphRelationship]:
        """Compute Skill Graph relationships for changed skills."""
        relationships: list[SkillGraphRelationship] = []
        seen: set[tuple[str, str]] = set()

        changed_skill_names = {
            sc.skill_name for sc in skill_changes if sc.change_type != "unchanged"
        }

        for skill_name in changed_skill_names:
            # Check synonyms
            related = SkillGraph.get_related_skills(skill_name)
            for rel in related:
                key = (skill_name.lower(), rel.lower())
                if key in seen:
                    continue
                seen.add(key)

                if SkillGraph.are_synonyms(skill_name, rel):
                    rel_type = "synonym"
                    sim_score = SkillGraph.similarity_score(skill_name, rel)
                elif SkillGraph.is_transferable(skill_name, rel):
                    rel_type = "transferable"
                    sim_score = SkillGraph.similarity_score(skill_name, rel)
                else:
                    rel_type = "similar"
                    sim_score = SkillGraph.similarity_score(skill_name, rel)

                relationships.append(SkillGraphRelationship(
                    source_skill=skill_name,
                    target_skill=rel,
                    relationship_type=rel_type,
                    similarity_score=round(sim_score, 4),
                ))

        # Sort by similarity descending
        relationships.sort(key=lambda r: r.similarity_score, reverse=True)
        return relationships

    def _compute_summary(
        self,
        skill_changes: list[SkillChange],
        candidate_impacts: list[CandidateSkillImpact],
        results: list[SimulationResult],
    ) -> SkillImpactSummary:
        """Compute aggregate summary statistics."""
        total_skills = len(skill_changes)
        added = sum(1 for sc in skill_changes if sc.change_type == "added")
        removed = sum(1 for sc in skill_changes if sc.change_type == "removed")
        promoted = sum(1 for sc in skill_changes if sc.change_type == "promoted")
        demoted = sum(1 for sc in skill_changes if sc.change_type == "demoted")
        unchanged = sum(1 for sc in skill_changes if sc.change_type == "unchanged")

        candidates_affected = len(candidate_impacts)
        newly_qualified = sum(
            1 for c in candidate_impacts
            if c.qualification_change == "newly_qualified"
        )
        newly_disqualified = sum(
            1 for c in candidate_impacts
            if c.qualification_change == "newly_disqualified"
        )

        avg_match_change = 0.0
        if candidate_impacts:
            total_change = sum(c.skill_match_change for c in candidate_impacts)
            avg_match_change = round(_safe_divide(total_change, len(candidate_impacts)), 2)

        return SkillImpactSummary(
            total_skills_analyzed=total_skills,
            skills_added=added,
            skills_removed=removed,
            skills_promoted=promoted,
            skills_demoted=demoted,
            skills_unchanged=unchanged,
            candidates_affected=candidates_affected,
            candidates_newly_qualified=newly_qualified,
            candidates_newly_disqualified=newly_disqualified,
            average_skill_match_change=avg_match_change,
        )

    def _generate_insights(
        self,
        summary: SkillImpactSummary,
        skill_changes: list[SkillChange],
        skill_gaps: list[SkillGap],
        candidate_impacts: list[CandidateSkillImpact],
    ) -> list[SkillImpactInsight]:
        """Generate deterministic factual insights."""
        insights: list[SkillImpactInsight] = []

        # Requirement changes
        if summary.skills_added > 0:
            added_names = [
                sc.skill_name for sc in skill_changes if sc.change_type == "added"
            ]
            insights.append(SkillImpactInsight(
                type="skills_added",
                message=(
                    f"{summary.skills_added} skill(s) added to requirements: "
                    f"{', '.join(added_names[:5])}"
                    f"{'...' if len(added_names) > 5 else ''}."
                ),
                metric_value=summary.skills_added,
                metric_unit="skills",
            ))

        if summary.skills_removed > 0:
            removed_names = [
                sc.skill_name for sc in skill_changes if sc.change_type == "removed"
            ]
            insights.append(SkillImpactInsight(
                type="skills_removed",
                message=(
                    f"{summary.skills_removed} skill(s) removed from requirements: "
                    f"{', '.join(removed_names[:5])}"
                    f"{'...' if len(removed_names) > 5 else ''}."
                ),
                metric_value=summary.skills_removed,
                metric_unit="skills",
            ))

        if summary.skills_promoted > 0:
            promoted_names = [
                sc.skill_name for sc in skill_changes if sc.change_type == "promoted"
            ]
            insights.append(SkillImpactInsight(
                type="skills_promoted",
                message=(
                    f"{summary.skills_promoted} skill(s) promoted to mandatory: "
                    f"{', '.join(promoted_names[:5])}"
                    f"{'...' if len(promoted_names) > 5 else ''}."
                ),
                metric_value=summary.skills_promoted,
                metric_unit="skills",
            ))

        if summary.skills_demoted > 0:
            demoted_names = [
                sc.skill_name for sc in skill_changes if sc.change_type == "demoted"
            ]
            insights.append(SkillImpactInsight(
                type="skills_demoted",
                message=(
                    f"{summary.skills_demoted} skill(s) demoted to preferred: "
                    f"{', '.join(demoted_names[:5])}"
                    f"{'...' if len(demoted_names) > 5 else ''}."
                ),
                metric_value=summary.skills_demoted,
                metric_unit="skills",
            ))

        # Candidate impact
        if summary.candidates_affected > 0:
            insights.append(SkillImpactInsight(
                type="candidate_impact",
                message=(
                    f"{summary.candidates_affected} candidate(s) had skill match "
                    f"changes."
                ),
                metric_value=summary.candidates_affected,
                metric_unit="candidates",
            ))

        if summary.candidates_newly_qualified > 0:
            insights.append(SkillImpactInsight(
                type="qualification_change",
                message=(
                    f"{summary.candidates_newly_qualified} candidate(s) became "
                    f"qualified due to skill configuration changes."
                ),
                metric_value=summary.candidates_newly_qualified,
                metric_unit="candidates",
            ))

        if summary.candidates_newly_disqualified > 0:
            insights.append(SkillImpactInsight(
                type="qualification_change",
                message=(
                    f"{summary.candidates_newly_disqualified} candidate(s) became "
                    f"unqualified due to skill configuration changes."
                ),
                metric_value=summary.candidates_newly_disqualified,
                metric_unit="candidates",
            ))

        # Largest skill gaps
        required_gaps = [
            sg for sg in skill_gaps
            if sg.is_required and not sg.coverage_unavailable
        ]
        if required_gaps:
            largest_gap = max(required_gaps, key=lambda g: g.simulation_gap)
            insights.append(SkillImpactInsight(
                type="largest_skill_gap",
                message=(
                    f"Largest skill gap for a required skill: "
                    f"{largest_gap.skill_name} "
                    f"({round(largest_gap.simulation_gap * 100, 1)}% gap)."
                ),
                metric_value=round(largest_gap.simulation_gap * 100, 1),
                metric_unit="percent",
            ))

        # Skill graph context
        if candidate_impacts:
            all_gained = set()
            all_lost = set()
            for c in candidate_impacts:
                all_gained.update(c.skills_gained)
                all_lost.update(c.skills_lost)
            if all_gained:
                insights.append(SkillImpactInsight(
                    type="skill_movement",
                    message=(
                        f"Candidates collectively gained matches in: "
                        f"{', '.join(sorted(all_gained)[:5])}"
                        f"{'...' if len(all_gained) > 5 else ''}."
                    ),
                    metric_value=len(all_gained),
                    metric_unit="skills",
                ))
            if all_lost:
                insights.append(SkillImpactInsight(
                    type="skill_movement",
                    message=(
                        f"Candidates collectively lost matches in: "
                        f"{', '.join(sorted(all_lost)[:5])}"
                        f"{'...' if len(all_lost) > 5 else ''}."
                    ),
                    metric_value=len(all_lost),
                    metric_unit="skills",
                ))

        return insights

    def _empty_response(
        self,
        scenario: SimulationScenario,
        execution: SimulationExecution,
    ) -> SkillImpactResponse:
        """Return a valid but empty analysis when no results exist."""
        return SkillImpactResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            execution_status=execution.status,
            scenario_name=scenario.name,
            job_title=scenario.job.title if scenario.job else "",
            company=scenario.job.company if scenario.job else "",
            engine_version=execution.engine_version,
            completed_at=execution.completed_at,
            summary=SkillImpactSummary(),
            skill_changes=[],
            skill_coverage=[],
            skill_gaps=[],
            skill_graph_relationships=[],
            candidates=[],
            insights=[],
        )
