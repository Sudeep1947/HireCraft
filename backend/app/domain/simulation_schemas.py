"""Pydantic schemas for Simulation Intelligence.

Scenario management and configuration snapshot structures are modelled here.
There is intentionally no execution/result payload — simulation execution is
out of scope for this phase. Phase 2 adds structured experience/education
requirements, versioned configuration, and validation/change-detection payloads
for the "what-if" Scenario Builder.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.enums import SimulationEducationLevel, SimulationEducationRequirement, SimulationStatus


class SimulationScoringWeights(BaseModel):
    """Hypothetical scoring weights. Mirrors the screening engine's eight
    dimension weights; each dimension is bounded to [0, 1]."""

    skills: float = Field(default=0.40, ge=0.0, le=1.0)
    experience: float = Field(default=0.25, ge=0.0, le=1.0)
    education: float = Field(default=0.15, ge=0.0, le=1.0)
    projects: float = Field(default=0.20, ge=0.0, le=1.0)
    certifications: float = Field(default=0.00, ge=0.0, le=1.0)
    location: float = Field(default=0.00, ge=0.0, le=1.0)
    employment_type: float = Field(default=0.00, ge=0.0, le=1.0)
    semantic: float = Field(default=0.00, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _weights_must_not_all_be_zero(self) -> "SimulationScoringWeights":
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("At least one scoring weight must be greater than zero")
        return self


class ExperienceRange(BaseModel):
    """Structured experience requirement: minimum/maximum years of experience.

    Both bounds are optional; a missing bound means "no constraint" on that
    side (e.g. minimum_years=3 with maximum_years=None means "3+ years").
    """

    minimum_years: int | None = Field(default=None, ge=0, le=50)
    maximum_years: int | None = Field(default=None, ge=0, le=50)

    @model_validator(mode="after")
    def _bounds_must_be_ordered(self) -> "ExperienceRange":
        if (
            self.minimum_years is not None
            and self.maximum_years is not None
            and self.maximum_years < self.minimum_years
        ):
            raise ValueError("Maximum experience years cannot be lower than the minimum")
        return self


class EducationRequirement(BaseModel):
    """Structured education requirement: a level plus how strictly it applies."""

    level: SimulationEducationLevel | None = Field(default=None)
    requirement: SimulationEducationRequirement = Field(
        default=SimulationEducationRequirement.REQUIRED,
    )


class SimulationRequirements(BaseModel):
    mandatory_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    # Structured, editable requirements (Scenario Builder).
    experience: ExperienceRange | None = Field(default=None)
    education: EducationRequirement | None = Field(default=None)
    # Legacy free-text mirrors of the live job posting fields. Kept for
    # backward compatibility with Phase 1 scenario snapshots where the job had
    # no structured experience/education requirement.
    experience_required: str | None = Field(default=None, max_length=255)
    education_required: str | None = Field(default=None, max_length=255)


class SimulationConfiguration(BaseModel):
    """Validated simulation configuration.

    `extra="forbid"` rejects unsupported keys so arbitrary unvalidated
    configuration can never enter the system. Future simulation parameters are
    added by extending this schema (and the surrounding validator), not by
    letting raw JSON through.

    `version` mirrors the scenario's `config_version` so the persisted JSON
    blob is self-describing; the service writes it in sync with the column.
    """

    model_config = {"extra": "forbid"}

    version: int = Field(default=1, ge=1)
    scoring_weights: SimulationScoringWeights = Field(default_factory=SimulationScoringWeights)
    threshold: int = Field(default=70, ge=0, le=100)
    shortlist_size: int = Field(default=10, ge=1, le=500)
    requirements: SimulationRequirements = Field(default_factory=SimulationRequirements)

    @field_validator("scoring_weights", mode="before")
    @classmethod
    def _coerce_weights(cls, value):
        if value is None:
            return SimulationScoringWeights()
        return value


class SimulationScenarioCreate(BaseModel):
    job_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    simulation_config: SimulationConfiguration | None = None
    metadata: dict | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()


class SimulationScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: SimulationStatus | None = None
    simulation_config: SimulationConfiguration | None = None
    metadata: dict | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()


class SimulationScenarioListItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    job_id: uuid.UUID
    created_by: uuid.UUID
    name: str
    status: str
    job_title: str = ""
    company: str = ""
    created_by_name: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimulationScenarioResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    job_id: uuid.UUID
    created_by: uuid.UUID
    name: str
    description: str | None
    status: str
    baseline_config: dict
    simulation_config: dict | None
    config_version: int
    # Mapped attribute name matches the ORM column so model_validate(scenario)
    # reads it directly; the JSON key is exposed as "metadata".
    metadata_json: dict | None = Field(default=None, serialization_alias="metadata")
    job_title: str = ""
    company: str = ""
    created_by_name: str = ""
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimulationStatusResponse(BaseModel):
    simulation_id: uuid.UUID
    status: str
    can_edit: bool
    updated_at: datetime
    completed_at: datetime | None


class SimulationStatsResponse(BaseModel):
    total: int = 0
    drafts: int = 0
    ready: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)


class SimulationScenarioListResponse(BaseModel):
    items: list[SimulationScenarioListItem]
    stats: SimulationStatsResponse


# Status transitions permitted through the Phase 1 API. Execution states
# (queued/running/completed/failed) are reserved for the future execution
# engine and cannot be set manually.
ALLOWED_STATUS_TRANSITIONS: dict[str, set[Literal["draft", "ready", "cancelled"]]] = {
    SimulationStatus.DRAFT.value: {SimulationStatus.READY.value, SimulationStatus.CANCELLED.value},
    SimulationStatus.READY.value: {SimulationStatus.DRAFT.value, SimulationStatus.CANCELLED.value},
    SimulationStatus.CANCELLED.value: {SimulationStatus.DRAFT.value, SimulationStatus.READY.value},
}


# ─── Validation ─────────────────────────────────────────────────────────

class SimulationValidationIssue(BaseModel):
    """A single configuration validation problem with a stable field path."""

    field: str
    message: str


class SimulationValidationResponse(BaseModel):
    valid: bool
    errors: list[SimulationValidationIssue] = Field(default_factory=list)


# ─── Change detection (baseline vs scenario) ────────────────────────────

class SimulationFieldChange(BaseModel):
    """A single comparable dimension: baseline value vs scenario value.

    `change` uses a compact vocabulary for the UI:
      unchanged | increased | decreased | added | removed | changed
    """

    key: str
    label: str
    baseline: object | None = None
    scenario: object | None = None
    change: str = "unchanged"


class SimulationSkillMovement(BaseModel):
    """A skill that moved between the mandatory and preferred lists."""

    skill: str
    from_list: str
    to_list: str


class SimulationSkillsChange(BaseModel):
    mandatory_added: list[str] = Field(default_factory=list)
    mandatory_removed: list[str] = Field(default_factory=list)
    preferred_added: list[str] = Field(default_factory=list)
    preferred_removed: list[str] = Field(default_factory=list)
    moved: list[SimulationSkillMovement] = Field(default_factory=list)


class SimulationChangesResponse(BaseModel):
    simulation_id: uuid.UUID
    config_version: int
    total_changes: int = 0
    changed_fields: list[str] = Field(default_factory=list)
    fields: list[SimulationFieldChange] = Field(default_factory=list)
    skills: SimulationSkillsChange = Field(default_factory=SimulationSkillsChange)


# ─── Execution (Phase 3 – real what-if runs) ──────────────────────────


class SimulationExecutionResponse(BaseModel):
    """A single execution of a simulation scenario.

    `status` follows queued -> running -> completed (or failed/cancelled).
    `progress` is the engine's completion percentage (0-100) so the UI can show
    live progress while the worker processes the candidate pool.
    """

    id: uuid.UUID
    scenario_id: uuid.UUID
    organization_id: uuid.UUID | None
    job_id: uuid.UUID
    created_by: uuid.UUID
    status: str
    progress: int
    total_candidates: int
    processed_candidates: int
    engine_version: str
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimulationExecutionListResponse(BaseModel):
    scenario_id: uuid.UUID
    items: list[SimulationExecutionResponse] = Field(default_factory=list)


class SimulationImpactMetric(BaseModel):
    metric: str
    baseline_value: float
    simulation_value: float
    change_value: float

    model_config = {"from_attributes": True}


class SimulationResultItem(BaseModel):
    """One candidate's baseline-vs-scenario outcome for an execution."""

    candidate_id: uuid.UUID
    candidate_name: str
    baseline_score: int
    simulation_score: int
    score_change: int
    baseline_rank: int
    simulation_rank: int
    rank_change: int
    baseline_status: str
    simulation_status: str
    baseline_shortlisted: bool
    simulation_shortlisted: bool
    baseline_dimensions: dict | None = None
    simulation_dimensions: dict | None = None
    reason: str | None = None

    model_config = {"from_attributes": True}


class SimulationResultsResponse(BaseModel):
    scenario_id: uuid.UUID
    execution_id: uuid.UUID
    total: int
    page: int
    page_size: int
    items: list[SimulationResultItem] = Field(default_factory=list)


class SimulationSummaryResponse(BaseModel):
    """Aggregate impact of an execution on the candidate pool.

    `summary` mirrors the engine's persisted JSON, `metrics` are the
    simulation_impacts rows, and `major_movements` highlights the candidates
    with the largest score/rank deltas so the results page can surface movers
    without downloading the whole result set.
    """

    scenario_id: uuid.UUID
    execution_id: uuid.UUID
    status: str
    engine_version: str
    total_candidates: int
    processed_candidates: int
    threshold_baseline: int
    threshold_simulation: int
    shortlist_baseline: int
    shortlist_simulation: int
    summary: dict = Field(default_factory=dict)
    metrics: list[SimulationImpactMetric] = Field(default_factory=list)
    major_movements: list[SimulationResultItem] = Field(default_factory=list)
    completed_at: datetime | None = None
    error_message: str | None = None


# ─── Optional manual shortlist (hypothetical → live, human-confirmed) ─────


class SimulationShortlistApplyRequest(BaseModel):
    """The recruiter's explicitly chosen candidates for the live shortlist.

    Every id is re-validated server-side against the simulation's job,
    execution, and application pool. The frontend selection is temporary UI
    state; only an explicit Apply Shortlist request may touch live data.
    """

    candidate_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)
    execution_id: uuid.UUID | None = None


class SimulationShortlistCandidateResult(BaseModel):
    """Outcome for one candidate during an Apply Shortlist operation.

    ``updated`` is True only when the existing application-status workflow
    actually changed the live application (all other actions stay hypothetical).
    """

    candidate_id: uuid.UUID
    candidate_name: str
    application_id: uuid.UUID
    previous_status: str
    new_status: str
    updated: bool


class SimulationShortlistApplyResponse(BaseModel):
    """Result of applying a shortlist chosen from a hypothetical simulation.

    The simulation is never overwritten: ``scenario_status`` keeps reporting
    the scenario's own lifecycle state (typically ``completed``), while
    ``shortlist_status`` records whether the optional shortlist action was
    applied. ``updated`` lists applications changed by the existing shortlist
    workflow; ``skipped`` lists candidates already shortlisted (idempotent
    retries land here).
    """

    simulation_id: uuid.UUID
    execution_id: uuid.UUID
    job_id: uuid.UUID
    scenario_status: str
    shortlist_status: str
    applied: bool
    updated: list[SimulationShortlistCandidateResult] = Field(default_factory=list)
    skipped: list[SimulationShortlistCandidateResult] = Field(default_factory=list)