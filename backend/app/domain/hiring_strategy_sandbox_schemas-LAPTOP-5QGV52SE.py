"""Pydantic schemas for Hiring Strategy Sandbox (Phase 12).

Defines request/response schemas for sandbox CRUD, strategy management,
branching, duplication, and comparison operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ─── Sandbox Schemas ────────────────────────────────────────────────


class SandboxCreate(BaseModel):
    job_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()


class SandboxUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()


class SandboxListItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    job_id: uuid.UUID
    created_by: uuid.UUID
    name: str
    status: str
    job_title: str = ""
    company: str = ""
    created_by_name: str = ""
    strategy_count: int = 0
    completed_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SandboxResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    job_id: uuid.UUID
    created_by: uuid.UUID
    name: str
    description: str | None
    status: str
    baseline_snapshot: dict
    metadata_json: dict | None = Field(default=None, serialization_alias="metadata")
    job_title: str = ""
    company: str = ""
    created_by_name: str = ""
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SandboxListResponse(BaseModel):
    items: list[SandboxListItem]
    total: int = 0


# ─── Strategy Schemas ───────────────────────────────────────────────


class StrategyCreate(BaseModel):
    """Create a new strategy from scratch or from an existing scenario."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    simulation_config: dict | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()


class StrategyDuplicate(BaseModel):
    """Duplicate or branch an existing strategy."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    branch: bool = Field(default=False, description="If True, create a branch with lineage tracking")
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()


class StrategyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()


class StrategyListItem(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    parent_strategy_id: uuid.UUID | None
    branch_name: str | None
    name: str
    status: str
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime
    # Denormalized from scenario
    job_title: str = ""
    threshold: int = 0
    shortlist_size: int = 0
    skills_weight: float = 0.0
    experience_weight: float = 0.0
    total_candidates: int = 0
    qualified_candidates: int = 0
    shortlisted_candidates: int = 0

    model_config = {"from_attributes": True}


class StrategyResponse(BaseModel):
    id: uuid.UUID
    sandbox_id: uuid.UUID
    scenario_id: uuid.UUID
    parent_strategy_id: uuid.UUID | None
    branch_name: str | None
    name: str
    description: str | None
    tags: list[str] | None
    notes: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategyListResponse(BaseModel):
    items: list[StrategyListItem]
    total: int = 0


# ─── Comparison ──────────────────────────────────────────────────────


class SandboxCompareRequest(BaseModel):
    """Compare selected strategies inside a sandbox."""
    strategy_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=5)


# ─── Activity Log ────────────────────────────────────────────────────


class SandboxActivityItem(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    user_name: str = ""
    metadata: dict | None = None


class SandboxActivityResponse(BaseModel):
    items: list[SandboxActivityItem]
