"""Pydantic schemas for Phase 13 — Simulation Reports & Decision Intelligence.

Defines request/response schemas for report generation, retrieval, export,
and the structured report content sections.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ─── Request Schemas ─────────────────────────────────────────────


class ReportIncludeOptions(BaseModel):
    """Flags controlling which sections to include in the report."""
    include_candidate_details: bool = Field(default=True)
    include_fairness: bool = Field(default=True)
    include_explainability: bool = Field(default=True)
    include_skill_impact: bool = Field(default=True)
    include_ranking: bool = Field(default=True)
    include_requirements: bool = Field(default=True)
    include_threshold: bool = Field(default=True)
    include_shortlist: bool = Field(default=True)
    include_comparison: bool = Field(default=True)
    include_limitations: bool = True
    include_audit: bool = True


class SimulationReportCreate(BaseModel):
    """Request to generate a simulation report."""
    report_type: Literal[
        "simulation", "candidate_impact", "fairness_impact",
        "comparison", "sandbox", "executive", "technical",
    ]
    simulation_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    comparison_scenario_ids: list[uuid.UUID] | None = Field(default=None, max_length=5)
    format: Literal["web", "pdf", "json", "csv"] = "web"
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    include: ReportIncludeOptions = Field(default_factory=ReportIncludeOptions)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str | None) -> str | None:
        return v.strip() if v else v


# ─── Response Schemas ────────────────────────────────────────────


class SimulationReportListItem(BaseModel):
    """List item for report listing."""
    id: uuid.UUID
    organization_id: uuid.UUID | None
    sandbox_id: uuid.UUID | None
    scenario_id: uuid.UUID | None
    execution_id: uuid.UUID | None
    job_id: uuid.UUID | None
    created_by: uuid.UUID
    report_type: str
    title: str
    description: str | None
    status: str
    format: str
    report_version: str
    job_title: str = ""
    scenario_name: str = ""
    sandbox_name: str = ""
    created_by_name: str = ""
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SimulationReportListResponse(BaseModel):
    items: list[SimulationReportListItem]
    total: int = 0
    page: int = 1
    page_size: int = 20


class SimulationReportResponse(BaseModel):
    """Full report response with metadata and sections."""
    id: uuid.UUID
    organization_id: uuid.UUID | None
    sandbox_id: uuid.UUID | None
    scenario_id: uuid.UUID | None
    execution_id: uuid.UUID | None
    job_id: uuid.UUID | None
    created_by: uuid.UUID
    report_type: str
    title: str
    description: str | None
    status: str
    format: str
    parameters: dict | None = None
    report_data: dict | None = None
    error_message: str | None = None
    report_version: str
    job_title: str = ""
    scenario_name: str = ""
    sandbox_name: str = ""
    created_by_name: str = ""
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimulationReportStatusResponse(BaseModel):
    """Lightweight status check for polling."""
    report_id: uuid.UUID
    status: str
    error_message: str | None = None
    completed_at: datetime | None = None


# ─── Report Content Sub-Components ───────────────────────────────


class ReportCandidateMover(BaseModel):
    candidate_id: str
    candidate_name: str
    baseline_score: int = 0
    simulation_score: int = 0
    score_change: int = 0
    baseline_rank: int = 0
    simulation_rank: int = 0
    rank_change: int = 0
    shortlisted: bool = False


class ReportWeightDiff(BaseModel):
    weight_name: str
    weight_label: str
    baseline: float
    simulation: float
    change: float
    change_label: str = ""


class ReportScalarDiff(BaseModel):
    label: str
    baseline: int | float
    simulation: int | float
    change: int | float
    change_label: str = ""


class ReportRequirementChange(BaseModel):
    skill: str
    from_status: str
    to_status: str


# ─── Report Content Sections ─────────────────────────────────────


class ReportHeader(BaseModel):
    title: str
    report_type: str
    job_title: str = ""
    job_id: str = ""
    sandbox_name: str = ""
    sandbox_id: str = ""
    scenario_name: str = ""
    scenario_id: str = ""
    simulation_id: str = ""
    execution_id: str = ""
    generated_by: str = ""
    generated_at: str = ""
    report_version: str = "1.0"
    status: str = ""


class ReportExecutiveSummary(BaseModel):
    narrative: str
    total_candidates_evaluated: int = 0
    key_configuration_changes: list[str] = Field(default_factory=list)
    candidate_impact_summary: str = ""
    fairness_summary: str = ""
    major_observed_differences: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportConfigurationDiff(BaseModel):
    """Baseline vs simulation configuration comparison."""
    weights: list[ReportWeightDiff] = Field(default_factory=list)
    threshold: ReportScalarDiff | None = None
    shortlist_size: ReportScalarDiff | None = None
    requirement_changes: list[ReportRequirementChange] = Field(default_factory=list)


class ReportCandidateImpact(BaseModel):
    total_candidates: int = 0
    candidates_with_score_changes: int = 0
    candidates_with_rank_changes: int = 0
    candidates_entering_shortlist: int = 0
    candidates_leaving_shortlist: int = 0
    retained_shortlist_candidates: int = 0
    qualification_changes: int = 0
    largest_score_movement: int = 0
    largest_rank_movement: int = 0
    average_score_change: float = 0.0
    average_rank_change: float = 0.0
    top_movers_increases: list[ReportCandidateMover] = Field(default_factory=list)
    top_movers_decreases: list[ReportCandidateMover] = Field(default_factory=list)
    top_rank_improvements: list[ReportCandidateMover] = Field(default_factory=list)
    top_rank_declines: list[ReportCandidateMover] = Field(default_factory=list)


class ReportCandidateImpactTable(BaseModel):
    """Paginated candidate impact table."""
    items: list[ReportCandidateMover] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ReportRankingImpact(BaseModel):
    overview: dict = Field(default_factory=dict)
    score_movement: dict = Field(default_factory=dict)
    rank_movement: dict = Field(default_factory=dict)
    shortlist_impact: dict = Field(default_factory=dict)
    qualification_matrix: dict = Field(default_factory=dict)
    distributions: dict = Field(default_factory=dict)
    insights: list[dict] = Field(default_factory=list)


class ReportRequirementImpact(BaseModel):
    total_changed: int = 0
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    promoted: list[str] = Field(default_factory=list)
    demoted: list[str] = Field(default_factory=list)
    per_requirement: list[dict] = Field(default_factory=list)
    candidates_affected: int = 0


class ReportThresholdImpact(BaseModel):
    baseline_threshold: int = 0
    simulation_threshold: int = 0
    qualified_baseline: int = 0
    qualified_simulation: int = 0
    newly_qualified: int = 0
    newly_disqualified: int = 0
    boundary_candidates: list[dict] = Field(default_factory=list)
    qualification_change: str = ""


class ReportShortlistImpact(BaseModel):
    baseline_shortlist_size: int = 0
    simulation_shortlist_size: int = 0
    retained: int = 0
    entering: int = 0
    leaving: int = 0
    overlap_percentage: float = 0.0
    boundary_candidates: list[dict] = Field(default_factory=list)


class ReportFairnessImpact(BaseModel):
    available: bool = False
    unavailable_reason: str = ""
    groups: list[dict] = Field(default_factory=list)
    cross_group_metrics: list[dict] = Field(default_factory=list)
    selection_rate_changes: list[dict] = Field(default_factory=list)
    spd_change: float | None = None
    dir_change: float | None = None
    small_sample_warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportExplainabilityImpact(BaseModel):
    available: bool = False
    unavailable_reason: str = ""
    feature_contribution_changes: list[dict] = Field(default_factory=list)
    weight_changes: list[dict] = Field(default_factory=list)
    score_attribution: list[dict] = Field(default_factory=list)
    candidate_explanations: list[dict] = Field(default_factory=list)


class ReportSkillImpact(BaseModel):
    available: bool = False
    unavailable_reason: str = ""
    changed_skills: list[dict] = Field(default_factory=list)
    skill_coverage_changes: list[dict] = Field(default_factory=list)
    skill_gaps: list[dict] = Field(default_factory=list)
    candidates_affected: int = 0


class ReportComparisonMatrix(BaseModel):
    """Multi-scenario comparison matrix."""
    scenarios: list[dict] = Field(default_factory=list)
    dimensions: list[dict] = Field(default_factory=list)
    stable_candidates: list[dict] = Field(default_factory=list)
    variable_candidates: list[dict] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)


class ReportLimitations(BaseModel):
    items: list[str] = Field(default_factory=list)
    data_integrity_notes: list[str] = Field(default_factory=list)
    simulation_isolation_notice: str = (
        "What-if Analysis: These results represent a hypothetical simulation. "
        "No live hiring data, job configuration, applications, candidate records, "
        "or production rankings were modified by this simulation."
    )


class ReportAuditInfo(BaseModel):
    report_id: str
    generated_by: str
    generated_at: str
    simulation_id: str = ""
    execution_id: str = ""
    scenario_id: str = ""
    sandbox_id: str = ""
    report_type: str
    report_version: str
    engine_version: str = ""


class ReportData(BaseModel):
    """Complete structured report data."""
    header: ReportHeader = Field(default_factory=ReportHeader)
    executive_summary: ReportExecutiveSummary = Field(default_factory=ReportExecutiveSummary)
    configuration_diff: ReportConfigurationDiff = Field(default_factory=ReportConfigurationDiff)
    candidate_impact: ReportCandidateImpact = Field(default_factory=ReportCandidateImpact)
    candidate_impact_table: ReportCandidateImpactTable = Field(default_factory=ReportCandidateImpactTable)
    ranking_impact: ReportRankingImpact = Field(default_factory=ReportRankingImpact)
    requirement_impact: ReportRequirementImpact = Field(default_factory=ReportRequirementImpact)
    threshold_impact: ReportThresholdImpact = Field(default_factory=ReportThresholdImpact)
    shortlist_impact: ReportShortlistImpact = Field(default_factory=ReportShortlistImpact)
    fairness_impact: ReportFairnessImpact = Field(default_factory=ReportFairnessImpact)
    explainability_impact: ReportExplainabilityImpact = Field(default_factory=ReportExplainabilityImpact)
    skill_impact: ReportSkillImpact = Field(default_factory=ReportSkillImpact)
    comparison_matrix: ReportComparisonMatrix = Field(default_factory=ReportComparisonMatrix)
    limitations: ReportLimitations = Field(default_factory=ReportLimitations)
    audit_info: ReportAuditInfo = Field(default_factory=ReportAuditInfo)
