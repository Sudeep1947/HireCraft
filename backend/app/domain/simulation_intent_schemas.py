"""Structured intermediate representation for natural-language simulation requests.

The LLM interprets user language and produces a SimulationIntent.  The backend
validates and executes the intent deterministically — the LLM never invents
numerical results.

Architecture:

    Natural Language
          ↓
    SimulationIntent (structured IR)
          ↓
    SimulationConfiguration (validated)
          ↓
    SimulationScenario
          ↓
    Existing Engine → Results
          ↓
    Grounded Explanation
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ─── Change Types ───────────────────────────────────────────────────


class ChangeType(str, Enum):
    """Supported natural-language change operations."""

    SCORING_WEIGHT = "SCORING_WEIGHT"
    THRESHOLD = "THRESHOLD"
    SHORTLIST = "SHORTLIST"
    REQUIREMENT = "REQUIREMENT"
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"
    PRESET = "PRESET"
    COMPARE = "COMPARE"


class RequirementOperation(str, Enum):
    """Skill/requirement change operations."""

    ADD = "ADD"
    REMOVE = "REMOVE"
    PROMOTE = "PROMOTE"
    DEMOTE = "DEMOTE"


class EducationOperation(str, Enum):
    """Education requirement change operations."""

    SET_LEVEL = "SET_LEVEL"
    SET_REQUIREMENT = "SET_REQUIREMENT"
    REMOVE = "REMOVE"


class IntentStatus(str, Enum):
    """Interpretation pipeline status."""

    INTERPRETED = "INTERPRETED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    VALIDATED = "VALIDATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


# ─── Individual Change Operations ───────────────────────────────────


class ScoringWeightChange(BaseModel):
    """Change a single scoring weight dimension."""

    type: Literal[ChangeType.SCORING_WEIGHT] = ChangeType.SCORING_WEIGHT
    parameter: str = Field(..., description="Weight dimension name")
    value: float = Field(..., ge=0.0, le=1.0, description="New weight as 0.0-1.0")
    unit: Literal["ratio"] = "ratio"

    @field_validator("parameter")
    @classmethod
    def _validate_parameter(cls, v: str) -> str:
        valid = {
            "skills", "experience", "education", "projects",
            "certifications", "location", "employment_type", "semantic",
        }
        if v not in valid:
            raise ValueError(f"Unknown weight dimension: {v}. Valid: {sorted(valid)}")
        return v


class ThresholdChange(BaseModel):
    """Change the minimum qualification threshold."""

    type: Literal[ChangeType.THRESHOLD] = ChangeType.THRESHOLD
    value: int = Field(..., ge=0, le=100, description="New threshold (0-100)")


class ShortlistChange(BaseModel):
    """Change the shortlist size."""

    type: Literal[ChangeType.SHORTLIST] = ChangeType.SHORTLIST
    value: int = Field(..., ge=1, le=500, description="New shortlist size")


class RequirementChange(BaseModel):
    """Add, remove, promote, or demote a skill requirement."""

    type: Literal[ChangeType.REQUIREMENT] = ChangeType.REQUIREMENT
    operation: RequirementOperation
    skill: str = Field(..., min_length=1, max_length=100)
    target: Literal["mandatory", "preferred"] | None = Field(
        default=None,
        description="Target list for PROMOTE/DEMOTE",
    )

    @field_validator("target")
    @classmethod
    def _validate_target(cls, v: str | None, info) -> str | None:
        op = info.data.get("operation")
        if op in (RequirementOperation.PROMOTE, RequirementOperation.DEMOTE) and v is None:
            raise ValueError("target is required for PROMOTE/DEMOTE")
        return v


class ExperienceChange(BaseModel):
    """Change the experience requirement."""

    type: Literal[ChangeType.EXPERIENCE] = ChangeType.EXPERIENCE
    operation: Literal["SET_MIN", "SET_MAX", "REMOVE"]
    value: int | None = Field(default=None, ge=0, le=50)

    @field_validator("value")
    @classmethod
    def _validate_value(cls, v: int | None, info) -> int | None:
        op = info.data.get("operation")
        if op in ("SET_MIN", "SET_MAX") and v is None:
            raise ValueError("value is required for SET_MIN/SET_MAX")
        if op == "REMOVE" and v is not None:
            raise ValueError("value must be null for REMOVE")
        return v


class EducationChange(BaseModel):
    """Change the education requirement."""

    type: Literal[ChangeType.EDUCATION] = ChangeType.EDUCATION
    operation: EducationOperation
    level: str | None = Field(default=None, description="Education level value")
    requirement: str | None = Field(default=None, description="required/preferred/optional")


class PresetChange(BaseModel):
    """Apply a predefined configuration preset."""

    type: Literal[ChangeType.PRESET] = ChangeType.PRESET
    preset: str = Field(..., description="Preset name")


# ─── Union of all change types ──────────────────────────────────────


ChangeOperation = (
    ScoringWeightChange
    | ThresholdChange
    | ShortlistChange
    | RequirementChange
    | ExperienceChange
    | EducationChange
    | PresetChange
)


# ─── SimulationIntent (Intermediate Representation) ─────────────────


class Clarification(BaseModel):
    """A clarification the agent needs from the user before proceeding."""

    question: str
    context: str = ""
    options: list[str] = Field(default_factory=list)


class SimulationIntent(BaseModel):
    """Structured intermediate representation of a natural-language request.

    The LLM produces this from raw user input.  The backend validates it
    before execution.  No numerical results appear here — only intent.
    """

    intent: str = Field(
        default="SIMULATE_HIRING_STRATEGY",
        description="Primary intent classification",
    )
    job_id: uuid.UUID | None = Field(
        default=None,
        description="Resolved job ID (null if ambiguous)",
    )
    changes: list[ChangeOperation] = Field(default_factory=list)
    clarifications_required: list[Clarification] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    natural_language_request: str = Field(default="")
    comparison_scenario_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Scenario IDs for comparison requests",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Interpretation confidence",
    )
    status: IntentStatus = IntentStatus.INTERPRETED


# ─── API Request / Response Schemas ─────────────────────────────────


class NLInterpretRequest(BaseModel):
    """Request to interpret a natural-language simulation request."""

    job_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=2000)


class ProposalChange(BaseModel):
    """A single human-readable change in a proposal."""

    category: str
    label: str
    baseline: str
    proposed: str
    change_type: str = "modified"


class NLInterpretResponse(BaseModel):
    """Response from interpreting a natural-language request."""

    intent: SimulationIntent
    proposal: list[ProposalChange] = Field(default_factory=list)
    validation_errors: list[dict[str, str]] = Field(default_factory=list)
    requires_confirmation: bool = True
    can_execute: bool = False
    message: str = ""


class NLConfirmRequest(BaseModel):
    """User confirms and optionally edits the proposed configuration."""

    job_id: uuid.UUID
    intent: SimulationIntent
    scenario_name: str = Field(default="NL Simulation", max_length=255)
    scenario_description: str | None = Field(default=None, max_length=2000)
    edited_config: dict | None = Field(
        default=None,
        description="User-edited configuration overrides",
    )


class NLConfirmResponse(BaseModel):
    """Result after confirmation — scenario created and optionally executed."""

    scenario_id: uuid.UUID
    execution_id: uuid.UUID | None = None
    status: str
    message: str = ""
    requires_execution: bool = True


class NLExplainRequest(BaseModel):
    """Request for natural-language explanation of simulation results."""

    scenario_id: uuid.UUID
    execution_id: uuid.UUID | None = None
    question: str = Field(default="", max_length=2000)


class NLExplainResponse(BaseModel):
    """Grounded explanation of simulation results."""

    explanation: str
    data_sources: list[str] = Field(default_factory=list)
    scenario_id: uuid.UUID
    execution_id: uuid.UUID | None = None
