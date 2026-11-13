"""Pydantic schemas for Phase 10 — Multi-Scenario Comparison.

All fields are READ-ONLY computed values derived from persisted SimulationResult
rows, configuration snapshots, and existing phase outputs across multiple
simulation scenarios.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ─── Request ─────────────────────────────────────────────────────


class ComparisonInclude(BaseModel):
    """Flags controlling which comparison sections to compute."""
    configuration: bool = Field(default=True)
    ranking: bool = Field(default=True)
    shortlist: bool = Field(default=True)
    requirements: bool = Field(default=True)
    fairness: bool = Field(default=True)
    explainability: bool = Field(default=True)
    skills: bool = Field(default=True)


class SimulationComparisonRequest(BaseModel):
    """Request body for multi-scenario comparison."""
    scenario_ids: list[uuid.UUID] = Field(
        ..., min_length=2, max_length=5,
        description="2–5 completed scenario IDs to compare",
    )
    include: ComparisonInclude = Field(default_factory=ComparisonInclude)


# ─── Scenario Metadata ──────────────────────────────────────────


class ScenarioMetadata(BaseModel):
    """Metadata for a single scenario in the comparison."""
    scenario_id: uuid.UUID
    execution_id: uuid.UUID
    name: str = ""
    description: str | None = None
    job_id: uuid.UUID
    job_title: str = ""
    company: str = ""
    created_by_name: str = ""
    created_at: datetime | None = None
    completed_at: datetime | None = None
    engine_version: str = ""
    total_candidates: int = 0
    processed_candidates: int = 0
    status: str = ""


# ─── Configuration Comparison ────────────────────────────────────


class WeightComparison(BaseModel):
    """Comparison of a single scoring weight across scenarios."""
    weight_name: str
    weight_label: str
    values: dict[str, float] = Field(
        default_factory=dict,
        description="Map of scenario_id -> weight value",
    )
    min_value: float = 0.0
    max_value: float = 0.0
    range_spread: float = 0.0


class ThresholdComparison(BaseModel):
    """Comparison of threshold values across scenarios."""
    values: dict[str, int] = Field(
        default_factory=dict,
        description="Map of scenario_id -> threshold value",
    )
    min_value: int = 0
    max_value: int = 0


class ShortlistSizeComparison(BaseModel):
    """Comparison of shortlist sizes across scenarios."""
    values: dict[str, int] = Field(
        default_factory=dict,
        description="Map of scenario_id -> shortlist_size value",
    )
    min_value: int = 0
    max_value: int = 0


class SkillRequirementComparison(BaseModel):
    """Comparison of a single skill's requirement status across scenarios."""
    skill_name: str
    values: dict[str, Literal["mandatory", "preferred", "not_required"]] = Field(
        default_factory=dict,
        description="Map of scenario_id -> requirement status",
    )
    change_type: Literal["added", "removed", "promoted", "demoted", "unchanged"] = "unchanged"


class ConfigurationComparison(BaseModel):
    """Full configuration comparison across scenarios."""
    weights: list[WeightComparison] = Field(default_factory=list)
    threshold: ThresholdComparison = Field(default_factory=ThresholdComparison)
    shortlist_size: ShortlistSizeComparison = Field(default_factory=ShortlistSizeComparison)
    skill_requirements: list[SkillRequirementComparison] = Field(default_factory=list)
    skills_added: list[str] = Field(default_factory=list)
    skills_removed: list[str] = Field(default_factory=list)
    skills_promoted: list[str] = Field(default_factory=list)
    skills_demoted: list[str] = Field(default_factory=list)


# ─── Candidate Comparison ────────────────────────────────────────


class CandidateScenarioOutcome(BaseModel):
    """A single candidate's outcome in one scenario."""
    scenario_id: str
    simulation_score: int = 0
    simulation_rank: int = 0
    score_change: int = 0
    rank_change: int = 0
    qualified: bool = False
    shortlisted: bool = False
    matched_skills: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)


class CandidateComparison(BaseModel):
    """Cross-scenario comparison for a single candidate."""
    candidate_id: uuid.UUID
    candidate_name: str = ""
    baseline_score: int = 0
    baseline_rank: int = 0
    scenarios: list[CandidateScenarioOutcome] = Field(default_factory=list)
    rank_range_min: int = 0
    rank_range_max: int = 0
    score_range_min: int = 0
    score_range_max: int = 0
    max_rank_movement: int = 0
    qualified_count: int = 0
    shortlisted_count: int = 0


class CandidatePoolComparison(BaseModel):
    """Metadata about candidate pool overlap across scenarios."""
    identical_pools: bool = False
    common_candidates: int = 0
    scenario_only_counts: dict[str, int] = Field(default_factory=dict)
    total_unique: int = 0


# ─── Ranking Comparison ──────────────────────────────────────────


class RankingDistribution(BaseModel):
    """Rank distribution for a single scenario."""
    scenario_id: str
    total_candidates: int = 0
    avg_score: float = 0.0
    median_score: float = 0.0
    avg_rank: float = 0.0
    qualified_count: int = 0
    shortlisted_count: int = 0


class ShortlistOverlap(BaseModel):
    """Pairwise shortlist overlap between two scenarios."""
    scenario_a_id: str
    scenario_b_id: str
    shortlist_a_count: int = 0
    shortlist_b_count: int = 0
    common_count: int = 0
    only_a_count: int = 0
    only_b_count: int = 0
    jaccard_similarity: float = 0.0


class RankingComparison(BaseModel):
    """Aggregate ranking comparison across scenarios."""
    distributions: list[RankingDistribution] = Field(default_factory=list)
    pairwise_overlaps: list[ShortlistOverlap] = Field(default_factory=list)
    top_movers: list[CandidateComparison] = Field(default_factory=list)
    most_stable: list[CandidateComparison] = Field(default_factory=list)


# ─── Requirement Comparison ──────────────────────────────────────


class RequirementComparisonItem(BaseModel):
    """Comparison of a single requirement across scenarios."""
    requirement_type: str = ""
    requirement_name: str = ""
    values: dict[str, str] = Field(
        default_factory=dict,
        description="Map of scenario_id -> requirement value/label",
    )
    is_changed: bool = False


class RequirementComparison(BaseModel):
    """Aggregate requirement comparison."""
    items: list[RequirementComparisonItem] = Field(default_factory=list)
    total_changed: int = 0
    skills_added: int = 0
    skills_removed: int = 0
    skills_promoted: int = 0
    skills_demoted: int = 0


# ─── Fairness Comparison ─────────────────────────────────────────


class FairnessScenarioMetric(BaseModel):
    """Fairness metrics for a single scenario."""
    scenario_id: str
    available: bool = False
    unavailable_reason: str = ""
    groups: list[dict] = Field(default_factory=list)
    cross_group: list[dict] = Field(default_factory=list)
    insight_count: int = 0


class FairnessComparison(BaseModel):
    """Aggregate fairness comparison across scenarios."""
    scenarios: list[FairnessScenarioMetric] = Field(default_factory=list)
    any_available: bool = False


# ─── Explainability Comparison ───────────────────────────────────


class ExplainabilityScenarioSummary(BaseModel):
    """Explainability summary for a single scenario."""
    scenario_id: str
    available: bool = False
    total_candidates: int = 0
    candidates_with_changes: int = 0
    avg_score_change: float = 0.0
    weight_changes: list[dict] = Field(default_factory=list)
    top_insight: str = ""


class ExplainabilityComparison(BaseModel):
    """Aggregate explainability comparison."""
    scenarios: list[ExplainabilityScenarioSummary] = Field(default_factory=list)
    any_available: bool = False


# ─── Skill Comparison ────────────────────────────────────────────


class SkillScenarioSummary(BaseModel):
    """Skill impact summary for a single scenario."""
    scenario_id: str
    available: bool = False
    total_skills_analyzed: int = 0
    skills_added: int = 0
    skills_removed: int = 0
    skills_promoted: int = 0
    skills_demoted: int = 0
    candidates_affected: int = 0
    top_gaps: list[dict] = Field(default_factory=list)


class SkillComparison(BaseModel):
    """Aggregate skill comparison across scenarios."""
    scenarios: list[SkillScenarioSummary] = Field(default_factory=list)
    any_available: bool = False


# ─── Insight ─────────────────────────────────────────────────────


class ComparisonInsight(BaseModel):
    """A deterministic factual insight from the comparison."""
    type: str = ""
    message: str = ""
    scenario_ids: list[str] = Field(default_factory=list)
    metric_value: float | int = 0
    metric_unit: str = ""


# ─── Main Response ───────────────────────────────────────────────


class MultiScenarioComparisonResponse(BaseModel):
    """Complete multi-scenario comparison response."""
    scenarios: list[ScenarioMetadata] = Field(default_factory=list)
    configuration_comparison: ConfigurationComparison = Field(
        default_factory=ConfigurationComparison,
    )
    candidate_pool: CandidatePoolComparison = Field(
        default_factory=CandidatePoolComparison,
    )
    candidate_comparison: list[CandidateComparison] = Field(default_factory=list)
    ranking_comparison: RankingComparison = Field(default_factory=RankingComparison)
    requirement_comparison: RequirementComparison = Field(
        default_factory=RequirementComparison,
    )
    fairness_comparison: FairnessComparison = Field(default_factory=FairnessComparison)
    explainability_comparison: ExplainabilityComparison = Field(
        default_factory=ExplainabilityComparison,
    )
    skill_comparison: SkillComparison = Field(default_factory=SkillComparison)
    insights: list[ComparisonInsight] = Field(default_factory=list)
