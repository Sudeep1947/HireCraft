"""Pydantic schemas for Phase 7 — Fairness Impact Simulation.

These schemas define the structured API response for fairness impact
analysis comparing baseline vs simulated hiring configurations across
demographic groups.

All values are derived from actual persisted simulation results and
self-reported candidate demographic data. No demographic information
is inferred or fabricated.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FairnessGroupMetric(BaseModel):
    """Fairness metric for a single demographic group."""

    group_dimension: str
    group_value: str
    sample_size: int = Field(description="Total candidates in this group")
    eligible_count: int = Field(description="Candidates eligible (in pool)")
    baseline_selected_count: int = Field(description="Candidates selected in baseline")
    simulation_selected_count: int = Field(description="Candidates selected in simulation")
    baseline_selection_rate: float | None = Field(
        default=None,
        description="Baseline selection rate (selected / eligible)",
    )
    simulation_selection_rate: float | None = Field(
        default=None,
        description="Simulation selection rate (selected / eligible)",
    )
    selection_rate_change: float | None = Field(
        default=None,
        description="Absolute change in selection rate",
    )
    entered_selection: int = Field(
        default=0,
        description="Candidates who entered selection in simulation",
    )
    exited_selection: int = Field(
        default=0,
        description="Candidates who exited selection in simulation",
    )
    retained_selection: int = Field(
        default=0,
        description="Candidates retained in selection across both",
    )
    metric_status: str = Field(
        description="Status: available | insufficient_sample | no_demographic_data",
    )
    status_reason: str | None = Field(
        default=None,
        description="Human-readable reason when metric is unavailable",
    )


class FairnessCrossGroupMetric(BaseModel):
    """Cross-group fairness metric comparing groups against a reference."""

    metric_name: str = Field(
        description="statistical_parity_difference | disparate_impact_ratio",
    )
    metric_label: str = Field(description="Human-readable metric name")
    baseline_value: float | None = Field(
        default=None,
        description="Baseline metric value",
    )
    simulation_value: float | None = Field(
        default=None,
        description="Simulation metric value",
    )
    absolute_change: float | None = Field(
        default=None,
        description="Absolute change (simulation - baseline)",
    )
    relative_change: float | None = Field(
        default=None,
        description="Relative change (absolute / |baseline|) when baseline != 0",
    )
    reference_group: str | None = Field(
        default=None,
        description="Reference group used for comparison",
    )
    groups_compared: list[str] = Field(
        default_factory=list,
        description="Groups included in this metric calculation",
    )
    metric_status: str = Field(
        description="available | insufficient_data | no_reference_group | identical_rates",
    )
    status_reason: str | None = Field(
        default=None,
        description="Human-readable reason when metric is unavailable",
    )


class FairnessInsight(BaseModel):
    """A factual, deterministic observation about fairness impact."""

    type: str
    message: str
    metric_value: float | int | None = None
    metric_unit: str | None = None


class FairnessImpactResponse(BaseModel):
    """Complete fairness impact analysis response.

    This is the primary API response for GET /simulations/{id}/fairness-impact.
    All values are derived from persisted Phase 3 simulation results grouped
    by self-reported candidate demographic attributes.
    """

    simulation_id: uuid.UUID
    execution_id: uuid.UUID
    execution_status: str
    scenario_name: str
    job_title: str
    company: str
    engine_version: str
    completed_at: datetime | None

    group_dimension: str = Field(
        description="Demographic dimension analyzed (e.g. 'gender')",
    )
    reference_group: str | None = Field(
        default=None,
        description="Reference group for cross-group comparisons",
    )
    total_candidates: int = Field(description="Total candidates in simulation")
    candidates_with_demographic: int = Field(
        description="Candidates with available demographic data",
    )
    candidates_missing_demographic: int = Field(
        description="Candidates with missing demographic data",
    )
    minimum_group_size: int = Field(
        description="Minimum group size threshold for metric calculation",
    )

    group_metrics: list[FairnessGroupMetric] = Field(
        description="Per-group fairness metrics",
    )
    cross_group_metrics: list[FairnessCrossGroupMetric] = Field(
        description="Cross-group fairness metrics (SPD, DI)",
    )
    insights: list[FairnessInsight] = Field(
        default_factory=list,
        description="Deterministic factual insights",
    )
