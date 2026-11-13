"""Pydantic schemas for Phase 14 Advanced Simulation & Research Intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import (
    ExperimentStatus,
    ExperimentType,
    PerturbationType,
    SensitivityDimension,
)

# ── Limits ──────────────────────────────────────────────────────────

MAX_CONFIGURATIONS_PER_EXPERIMENT = 50
MAX_PARAMETER_DIMENSIONS = 5
MAX_EXPERIMENT_NAME_LEN = 255


# ── Request Schemas ─────────────────────────────────────────────────


class ParameterRange(BaseModel):
    """Definition of a single parameter sweep range."""

    dimension: SensitivityDimension
    values: list[Any] | None = Field(
        default=None,
        description="Explicit list of values to test. Mutually exclusive with start/end/step.",
    )
    start: float | None = Field(default=None, description="Start of numeric range (inclusive).")
    end: float | None = Field(default=None, description="End of numeric range (inclusive).")
    step: float | None = Field(default=None, description="Step size for numeric range.")

    @field_validator("values")
    @classmethod
    def validate_values_or_range(cls, v: Any, info: Any) -> Any:
        return v


class PerturbationSpec(BaseModel):
    """Defines a single perturbation around a base configuration."""

    dimension: SensitivityDimension
    perturbation_type: PerturbationType
    delta: float | None = None
    percentage: float | None = None
    values: list[Any] | None = None
    requirement_skill: str | None = None


class ExperimentCreate(BaseModel):
    """Request to create a new research experiment."""

    name: str = Field(max_length=MAX_EXPERIMENT_NAME_LEN)
    description: str | None = None
    research_question: str | None = None
    hypothesis: str | None = None
    base_scenario_id: uuid.UUID
    sandbox_id: uuid.UUID | None = None
    experiment_type: ExperimentType
    parameter_ranges: list[ParameterRange]
    perturbations: list[PerturbationSpec] | None = None
    max_configurations: int = Field(default=20, ge=2, le=MAX_CONFIGURATIONS_PER_EXPERIMENT)
    random_seed: int | None = None
    execution_config: dict[str, Any] | None = None


class ExperimentUpdate(BaseModel):
    """Request to update an experiment (only DRAFT status)."""

    name: str | None = Field(default=None, max_length=MAX_EXPERIMENT_NAME_LEN)
    description: str | None = None
    research_question: str | None = None
    hypothesis: str | None = None
    parameter_ranges: list[ParameterRange] | None = None
    perturbations: list[PerturbationSpec] | None = None
    max_configurations: int | None = Field(default=None, ge=2, le=MAX_CONFIGURATIONS_PER_EXPERIMENT)


class ExperimentExecuteRequest(BaseModel):
    """Request to execute an experiment."""

    force_rerun: bool = False


# ── Response Schemas ────────────────────────────────────────────────


class ParameterRangeResponse(BaseModel):
    dimension: str
    values: list[Any] | None = None
    start: float | None = None
    end: float | None = None
    step: float | None = None


class ExperimentListItem(BaseModel):
    id: str
    name: str
    description: str | None = None
    experiment_type: str
    status: str
    base_scenario_name: str
    job_title: str
    total_configurations: int
    completed_configurations: int
    failed_configurations: int
    created_by_name: str
    created_at: datetime
    completed_at: datetime | None = None


class ExperimentListResponse(BaseModel):
    items: list[ExperimentListItem]
    total: int
    page: int
    page_size: int


class ExperimentResponse(BaseModel):
    id: str
    organization_id: str | None = None
    sandbox_id: str | None = None
    base_scenario_id: str
    job_id: str
    created_by: str
    name: str
    description: str | None = None
    research_question: str | None = None
    hypothesis: str | None = None
    experiment_type: str
    status: str
    parameters: dict[str, Any]
    parameter_ranges: dict[str, Any]
    execution_config: dict[str, Any] | None = None
    generated_configs: dict[str, Any] | None = None
    result_summary: dict[str, Any] | None = None
    sensitivity_results: dict[str, Any] | None = None
    robustness_results: dict[str, Any] | None = None
    stability_results: dict[str, Any] | None = None
    fairness_sensitivity_results: dict[str, Any] | None = None
    candidate_stability_results: dict[str, Any] | None = None
    error_message: str | None = None
    total_configurations: int
    completed_configurations: int
    failed_configurations: int
    random_seed: int | None = None
    experiment_version: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ExperimentStatusResponse(BaseModel):
    experiment_id: str
    status: str
    total_configurations: int
    completed_configurations: int
    failed_configurations: int
    error_message: str | None = None


class ExperimentResultItem(BaseModel):
    id: str
    parameter_values: dict[str, Any]
    execution_status: str
    metrics: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime


class ExperimentResultsResponse(BaseModel):
    items: list[ExperimentResultItem]
    total: int


# ── Analysis Response Schemas ───────────────────────────────────────


class SensitivityPoint(BaseModel):
    parameter_value: Any
    metric_name: str
    metric_value: float
    configuration_hash: str | None = None


class SensitivityCurve(BaseModel):
    dimension: str
    points: list[SensitivityPoint]
    min_value: float
    max_value: float
    range_spread: float
    direction: str  # "increasing", "decreasing", "mixed", "stable"


class SensitivityAnalysisResponse(BaseModel):
    experiment_id: str
    curves: list[SensitivityCurve]
    summary: dict[str, Any]


class RobustnessPerturbationResult(BaseModel):
    dimension: str
    perturbation_type: str
    delta: float | None = None
    ranking_change: float | None = None
    shortlist_change: int | None = None
    qualification_change: int | None = None
    fairness_metric_change: float | None = None


class RobustnessProfile(BaseModel):
    parameter: str
    range_tested: str
    rank_variation: float
    shortlist_variation: float
    fairness_variation: float | None = None


class RobustnessAnalysisResponse(BaseModel):
    experiment_id: str
    perturbation_results: list[RobustnessPerturbationResult]
    profiles: list[RobustnessProfile]
    summary: dict[str, Any]


class CandidateStabilityMetrics(BaseModel):
    candidate_id: str
    candidate_name: str
    appearance_frequency: float
    shortlist_frequency: float
    rank_range_min: int
    rank_range_max: int
    rank_range: int
    rank_variance: float
    qualification_frequency: float
    score_range_min: float
    score_range_max: float


class StabilityAnalysisResponse(BaseModel):
    experiment_id: str
    ranking_stability: dict[str, Any]
    shortlist_stability: dict[str, Any]
    candidate_stability: list[CandidateStabilityMetrics]
    summary: dict[str, Any]


class FairnessSensitivityPoint(BaseModel):
    parameter_value: Any
    spd: float | None = None
    di: float | None = None
    eod: float | None = None
    selection_rates: dict[str, float] | None = None


class FairnessSensitivityResponse(BaseModel):
    experiment_id: str
    dimension: str
    points: list[FairnessSensitivityPoint]
    summary: dict[str, Any]


class ExperimentComparisonRequest(BaseModel):
    experiment_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)


class ExperimentComparisonResponse(BaseModel):
    experiments: list[ExperimentListItem]
    parameter_comparison: dict[str, Any]
    metric_comparison: dict[str, Any]
    insights: list[dict[str, Any]]
