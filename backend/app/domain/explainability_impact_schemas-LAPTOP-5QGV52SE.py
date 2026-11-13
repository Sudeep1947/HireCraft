"""Pydantic schemas for Phase 8 — Explainability Impact Simulation.

These schemas define the structured API response for explainability
impact analysis comparing baseline vs simulated candidate scoring
factor contributions.

All values are derived from persisted Phase 3 simulation results
and configuration snapshots. No scores are recalculated.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FeatureContribution(BaseModel):
    """Per-dimension weighted contribution for one configuration."""

    feature: str = Field(description="Dimension key (e.g. 'skill', 'experience')")
    feature_label: str = Field(description="Human-readable dimension name")
    weight: float = Field(description="Scoring weight for this dimension")
    dimension_score: int = Field(description="Raw dimension match score (0-100)")
    weighted_contribution: float = Field(
        description="Weight * dimension_score contribution to overall score",
    )


class FeatureContributionChange(BaseModel):
    """Comparison of one feature's contribution between baseline and simulation."""

    feature: str
    feature_label: str
    baseline_weight: float
    simulation_weight: float
    weight_change: float
    baseline_dimension_score: int
    simulation_dimension_score: int
    dimension_score_change: int
    baseline_contribution: float
    simulation_contribution: float
    contribution_change: float


class CandidateExplainabilityImpact(BaseModel):
    """Per-candidate explainability impact comparing baseline vs simulation."""

    candidate_id: uuid.UUID
    candidate_name: str

    baseline_score: int
    simulation_score: int
    score_change: int

    baseline_rank: int
    simulation_rank: int
    rank_change: int

    baseline_shortlisted: bool
    simulation_shortlisted: bool
    qualification_change: str = Field(
        description="qualified_to_qualified | unqualified_to_qualified | "
        "qualified_to_unqualified | unqualified_to_unqualified",
    )

    feature_contributions: list[FeatureContributionChange] = Field(
        description="Per-feature contribution changes between configurations",
    )

    top_positive_changes: list[FeatureContributionChange] = Field(
        default_factory=list,
        description="Largest positive contribution changes",
    )
    top_negative_changes: list[FeatureContributionChange] = Field(
        default_factory=list,
        description="Largest negative contribution changes",
    )

    reason: str | None = Field(
        default=None,
        description="Human-readable explanation from the simulation engine",
    )

    impact_type: str = Field(
        description="score_changed | rank_only_changed | threshold_only | unchanged",
    )


class WeightChange(BaseModel):
    """Configuration weight change for one dimension."""

    feature: str
    feature_label: str
    baseline_weight: float
    simulation_weight: float
    weight_change: float


class ExplainabilityImpactSummary(BaseModel):
    """Aggregate summary of explainability impact across all candidates."""

    total_candidates: int
    candidates_with_score_changes: int
    candidates_with_rank_changes: int
    candidates_with_contribution_changes: int
    candidates_unchanged: int
    average_score_change: float
    largest_score_increase: int
    largest_score_decrease: int


class ExplainabilityImpactResponse(BaseModel):
    """Complete explainability impact analysis response.

    This is the API response for GET /simulations/{id}/explainability-impact.
    All values are derived from persisted Phase 3 simulation results and
    configuration snapshots.
    """

    simulation_id: uuid.UUID
    execution_id: uuid.UUID
    execution_status: str
    scenario_name: str
    job_title: str
    company: str
    engine_version: str
    completed_at: datetime | None

    summary: ExplainabilityImpactSummary
    weight_changes: list[WeightChange] = Field(
        description="Configuration weight changes between baseline and simulation",
    )
    candidates: list[CandidateExplainabilityImpact] = Field(
        description="Per-candidate explainability impact details",
    )
    insights: list[ExplainabilityInsight] = Field(
        default_factory=list,
        description="Deterministic factual insights",
    )


class ExplainabilityInsight(BaseModel):
    """A factual, deterministic observation about explainability impact."""

    type: str
    message: str
    metric_value: float | int | None = None
    metric_unit: str | None = None
