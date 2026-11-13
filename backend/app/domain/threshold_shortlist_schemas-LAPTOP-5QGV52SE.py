"""Pydantic schemas for Phase 6 — Threshold & Shortlist Impact Analysis.

These schemas define the structured API response for threshold and shortlist
impact analysis. The analyzer consumes persisted Phase 3 results
(SimulationResult, SimulationExecution) and configuration snapshots to compute
what-if projections when threshold or shortlist size changes.

All values are derived from actual data — never hardcoded.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Threshold Analysis ────────────────────────────────────────────


class ThresholdBoundaryCandidate(BaseModel):
    """A candidate near the threshold boundary."""

    candidate_id: uuid.UUID
    candidate_name: str
    score: int
    threshold: int
    distance_from_threshold: int
    qualified: bool
    baseline_qualified: bool
    qualification_change: str  # "newly_qualified" | "newly_disqualified" | "remained_qualified" | "remained_unqualified"
    baseline_rank: int
    simulation_rank: int
    rank_change: int
    baseline_shortlisted: bool
    simulation_shortlisted: bool


class ThresholdSensitivityPoint(BaseModel):
    """Qualified candidate count at a hypothetical threshold."""

    threshold: int
    qualified_count: int
    percentage_qualified: float


class ThresholdScoreDistribution(BaseModel):
    """Score band with candidate counts around the threshold."""

    label: str
    lower_bound: int
    upper_bound: int
    candidate_count: int
    is_threshold_band: bool


class ThresholdImpactResponse(BaseModel):
    """Complete threshold impact analysis response.

    This is the primary API response for GET /simulations/{id}/threshold-impact.
    All values are derived from persisted Phase 3 simulation results by
    re-projecting qualification status at different thresholds.
    """

    simulation_id: uuid.UUID
    execution_id: uuid.UUID
    execution_status: str
    scenario_name: str
    job_title: str
    company: str
    engine_version: str
    completed_at: datetime | None

    # Baseline vs simulation threshold
    baseline_threshold: int
    simulation_threshold: int
    threshold_change: int

    # Qualification counts
    baseline_qualified_count: int
    simulation_qualified_count: int
    qualified_change: int
    percentage_qualified_before: float
    percentage_qualified_after: float

    # Threshold crossings
    newly_qualified_count: int
    newly_disqualified_count: int
    remained_qualified_count: int
    remained_unqualified_count: int

    # Retention & turnover
    qualification_retention_rate: float | None
    qualification_turnover_rate: float | None

    # Boundary analysis
    boundary_range: int
    boundary_candidates: list[ThresholdBoundaryCandidate]

    # Sensitivity analysis
    sensitivity_data: list[ThresholdSensitivityPoint]

    # Score distribution around threshold
    score_distribution: list[ThresholdScoreDistribution]

    # Total candidates for percentage calculations
    total_candidates: int

    # Factual insights
    insights: list[ThresholdInsight]


class ThresholdInsight(BaseModel):
    """A factual, deterministic observation about threshold impact."""

    type: str  # "threshold_change" | "qualification_impact" | "boundary" | "sensitivity"
    message: str
    metric_value: float | int | None = None
    metric_unit: str | None = None


# ─── Shortlist Analysis ────────────────────────────────────────────


class ShortlistBoundaryCandidate(BaseModel):
    """A candidate near the shortlist boundary."""

    candidate_id: uuid.UUID
    candidate_name: str
    rank: int
    score: int
    baseline_shortlisted: bool
    simulation_shortlisted: bool
    shortlist_change: str  # "entered" | "exited" | "retained" | "unchanged"
    distance_from_boundary: int


class ShortlistSensitivityPoint(BaseModel):
    """Shortlist composition at a hypothetical shortlist size."""

    shortlist_size: int
    actual_shortlisted: int
    overlap_with_baseline: int
    newly_included: int
    overlap_percentage: float


class ShortlistImpactResponse(BaseModel):
    """Complete shortlist impact analysis response.

    This is the primary API response for GET /simulations/{id}/shortlist-impact.
    All values are derived from persisted Phase 3 simulation results by
    re-projecting shortlist membership at different sizes.
    """

    simulation_id: uuid.UUID
    execution_id: uuid.UUID
    execution_status: str
    scenario_name: str
    job_title: str
    company: str
    engine_version: str
    completed_at: datetime | None

    # Baseline vs simulation shortlist
    baseline_shortlist_size: int
    simulation_shortlist_size: int
    shortlist_change: int
    actual_baseline_shortlisted: int
    actual_simulation_shortlisted: int

    # Composition changes
    retained_count: int
    entered_count: int
    exited_count: int

    # Overlap metrics
    overlap_count: int
    overlap_union_count: int
    jaccard_similarity: float
    retention_rate: float
    turnover_rate: float

    # Boundary analysis
    boundary_range: int
    boundary_candidates: list[ShortlistBoundaryCandidate]

    # Sensitivity analysis
    sensitivity_data: list[ShortlistSensitivityPoint]

    # Total candidates
    total_candidates: int

    # Factual insights
    insights: list[ShortlistInsight]


class ShortlistInsight(BaseModel):
    """A factual, deterministic observation about shortlist impact."""

    type: str  # "shortlist_change" | "composition" | "boundary" | "sensitivity"
    message: str
    metric_value: float | int | None = None
    metric_unit: str | None = None


# ─── Combined Impact ───────────────────────────────────────────────


class CombinedImpactMatrix(BaseModel):
    """Matrix showing baseline vs simulation shortlist membership."""

    retained: int
    entered: int
    exited: int
    remained_outside: int


class CandidateThresholdShortlistImpact(BaseModel):
    """Per-candidate impact from combined threshold + shortlist changes."""

    candidate_id: uuid.UUID
    candidate_name: str

    # Baseline state
    baseline_score: int
    baseline_rank: int
    baseline_threshold: int
    baseline_qualified: bool
    baseline_shortlisted: bool

    # Simulation state
    simulation_score: int
    simulation_rank: int
    simulation_threshold: int
    simulation_qualified: bool
    simulation_shortlisted: bool

    # Changes
    qualification_change: str  # "newly_qualified" | "newly_disqualified" | "remained_qualified" | "remained_unqualified"
    shortlist_change: str  # "entered" | "exited" | "retained" | "unchanged"
    score_change: int
    rank_change: int

    # Impact explanation
    explanation: str


class CombinedThresholdShortlistResponse(BaseModel):
    """Combined threshold + shortlist impact analysis response.

    This is the API response for GET /simulations/{id}/threshold-shortlist-impact.
    """

    simulation_id: uuid.UUID
    execution_id: uuid.UUID
    execution_status: str
    scenario_name: str
    job_title: str
    company: str
    completed_at: datetime | None

    # Threshold section
    threshold_impact: ThresholdImpactResponse

    # Shortlist section
    shortlist_impact: ShortlistImpactResponse

    # Combined metrics
    combined_matrix: CombinedImpactMatrix
    total_affected_candidates: int

    # Candidate-level impacts (affected candidates only)
    candidate_impacts: list[CandidateThresholdShortlistImpact]

    # Combined insights
    insights: list[ThresholdInsight | ShortlistInsight]
