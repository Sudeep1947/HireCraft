"""Pydantic schemas for Phase 9 — Skill Impact Simulation.

All fields are READ-ONLY computed values derived from persisted SimulationResult
rows, configuration snapshots, and existing Skill Intelligence data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import uuid

from pydantic import BaseModel, Field


# ─── Skill-Level Schemas ──────────────────────────────────────────


class SkillChange(BaseModel):
    """A single skill requirement change between baseline and simulation."""
    skill_name: str = Field(..., description="Canonical skill name")
    change_type: Literal["added", "removed", "promoted", "demoted", "unchanged"] = Field(
        ..., description="Type of skill requirement change"
    )
    baseline_requirement: Literal["mandatory", "preferred", "not_required"] = Field(
        ..., description="Baseline requirement status"
    )
    simulation_requirement: Literal["mandatory", "preferred", "not_required"] = Field(
        ..., description="Simulation requirement status"
    )
    baseline_candidates_match: int = Field(
        default=0, description="Number of candidates matching this skill in baseline"
    )
    simulation_candidates_match: int = Field(
        default=0, description="Number of candidates matching this skill in simulation"
    )
    coverage_change: float = Field(
        default=0.0, description="Change in coverage percentage (simulation - baseline)"
    )
    candidates_affected: int = Field(
        default=0, description="Number of candidates affected by this skill change"
    )
    candidates_newly_qualified: int = Field(
        default=0, description="Candidates newly qualified due to this skill change"
    )
    candidates_newly_disqualified: int = Field(
        default=0, description="Candidates newly disqualified due to this skill change"
    )


class SkillCoverage(BaseModel):
    """Skill coverage metrics for a single skill."""
    skill_name: str = Field(..., description="Canonical skill name")
    baseline_coverage: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Fraction of eligible candidates matching in baseline (0.0-1.0)"
    )
    simulation_coverage: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Fraction of eligible candidates matching in simulation (0.0-1.0)"
    )
    coverage_change: float = Field(
        default=0.0,
        description="Change in coverage (simulation - baseline)"
    )
    baseline_candidates_match: int = Field(
        default=0, description="Number of candidates matching in baseline"
    )
    simulation_candidates_match: int = Field(
        default=0, description="Number of candidates matching in simulation"
    )
    total_eligible: int = Field(
        default=0, description="Total eligible candidates in the pool"
    )
    is_mandatory_baseline: bool = Field(
        default=False, description="Whether skill is mandatory in baseline"
    )
    is_mandatory_simulation: bool = Field(
        default=False, description="Whether skill is mandatory in simulation"
    )
    is_preferred_baseline: bool = Field(
        default=False, description="Whether skill is preferred in baseline"
    )
    is_preferred_simulation: bool = Field(
        default=False, description="Whether skill is preferred in simulation"
    )


class SkillGap(BaseModel):
    """Skill gap metrics for a single skill."""
    skill_name: str = Field(..., description="Canonical skill name")
    baseline_gap: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Baseline gap (1 - coverage)"
    )
    simulation_gap: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Simulation gap (1 - coverage)"
    )
    gap_change: float = Field(
        default=0.0,
        description="Change in gap (simulation - baseline). Positive = worse gap."
    )
    is_required: bool = Field(
        default=False, description="Whether skill is required in simulation"
    )
    coverage_unavailable: bool = Field(
        default=False,
        description="True when coverage cannot be computed (e.g. skill not in any config)"
    )


class SkillGraphRelationship(BaseModel):
    """Contextual Skill Graph relationship for a changed skill."""
    source_skill: str = Field(..., description="The changed skill")
    target_skill: str = Field(..., description="Related skill")
    relationship_type: Literal["synonym", "transferable", "similar"] = Field(
        ..., description="Type of relationship from SkillGraph"
    )
    similarity_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Similarity score from SkillGraph"
    )


class CandidateSkillImpact(BaseModel):
    """Per-candidate skill impact from skill configuration changes."""
    candidate_id: uuid.UUID = Field(..., description="Candidate user ID")
    candidate_name: str = Field(default="", description="Candidate display name")
    baseline_matched_skills: list[str] = Field(
        default_factory=list, description="Skills matched in baseline"
    )
    simulation_matched_skills: list[str] = Field(
        default_factory=list, description="Skills matched in simulation"
    )
    skills_gained: list[str] = Field(
        default_factory=list,
        description="Skills newly matched in simulation (not matched in baseline)"
    )
    skills_lost: list[str] = Field(
        default_factory=list,
        description="Skills no longer matched (matched in baseline, not in simulation)"
    )
    baseline_missing_required: list[str] = Field(
        default_factory=list, description="Required skills missing in baseline"
    )
    simulation_missing_required: list[str] = Field(
        default_factory=list, description="Required skills missing in simulation"
    )
    newly_satisfied_required: list[str] = Field(
        default_factory=list,
        description="Previously missing required skills now satisfied"
    )
    newly_unsatisfied_required: list[str] = Field(
        default_factory=list,
        description="Previously satisfied required skills now missing"
    )
    baseline_score: int = Field(default=0, description="Baseline overall score")
    simulation_score: int = Field(default=0, description="Simulation overall score")
    score_change: int = Field(default=0, description="Score change (simulation - baseline)")
    baseline_rank: int = Field(default=0, description="Baseline rank")
    simulation_rank: int = Field(default=0, description="Simulation rank")
    rank_change: int = Field(default=0, description="Rank change (simulation - baseline)")
    baseline_qualified: bool = Field(default=False, description="Baseline qualification status")
    simulation_qualified: bool = Field(default=False, description="Simulation qualification status")
    qualification_change: Literal[
        "newly_qualified", "newly_disqualified",
        "remained_qualified", "remained_unqualified",
    ] = Field(default="remained_unqualified", description="Qualification change")
    skill_match_change: int = Field(
        default=0,
        description="Net change in matched skills count (simulation - baseline)"
    )


# ─── Aggregate Schemas ────────────────────────────────────────────


class SkillImpactSummary(BaseModel):
    """Aggregate summary of skill impact analysis."""
    total_skills_analyzed: int = Field(
        default=0, description="Total unique skills across both configs"
    )
    skills_added: int = Field(default=0, description="Skills added to requirements")
    skills_removed: int = Field(default=0, description="Skills removed from requirements")
    skills_promoted: int = Field(default=0, description="Skills promoted (preferred -> mandatory)")
    skills_demoted: int = Field(default=0, description="Skills demoted (mandatory -> preferred)")
    skills_unchanged: int = Field(default=0, description="Skills with no requirement change")
    candidates_affected: int = Field(
        default=0, description="Candidates with at least one skill match change"
    )
    candidates_newly_qualified: int = Field(
        default=0, description="Candidates becoming qualified due to skill changes"
    )
    candidates_newly_disqualified: int = Field(
        default=0, description="Candidates becoming unqualified due to skill changes"
    )
    average_skill_match_change: float = Field(
        default=0.0, description="Average net skill match change across affected candidates"
    )


class SkillImpactInsight(BaseModel):
    """A deterministic factual insight about skill impact."""
    type: str = Field(..., description="Insight category")
    message: str = Field(..., description="Human-readable insight")
    metric_value: float | int = Field(default=0, description="Associated numeric value")
    metric_unit: str = Field(default="", description="Unit of the metric")


# ─── Main Response ────────────────────────────────────────────────


class SkillImpactResponse(BaseModel):
    """Complete Skill Impact Simulation response."""
    simulation_id: uuid.UUID = Field(..., description="Simulation scenario ID")
    execution_id: uuid.UUID = Field(..., description="Execution ID used for analysis")
    execution_status: str = Field(default="", description="Execution status")
    scenario_name: str = Field(default="", description="Scenario name")
    job_title: str = Field(default="", description="Job title")
    company: str = Field(default="", description="Company name")
    engine_version: str = Field(default="", description="Engine version")
    completed_at: datetime | None = Field(
        default=None, description="Execution completion timestamp"
    )
    summary: SkillImpactSummary = Field(
        default_factory=SkillImpactSummary,
        description="Aggregate summary statistics"
    )
    skill_changes: list[SkillChange] = Field(
        default_factory=list, description="Skill requirement changes"
    )
    skill_coverage: list[SkillCoverage] = Field(
        default_factory=list, description="Per-skill coverage metrics"
    )
    skill_gaps: list[SkillGap] = Field(
        default_factory=list, description="Per-skill gap metrics"
    )
    skill_graph_relationships: list[SkillGraphRelationship] = Field(
        default_factory=list,
        description="Contextual Skill Graph relationships for changed skills"
    )
    candidates: list[CandidateSkillImpact] = Field(
        default_factory=list, description="Per-candidate skill impact"
    )
    insights: list[SkillImpactInsight] = Field(
        default_factory=list, description="Deterministic factual insights"
    )
