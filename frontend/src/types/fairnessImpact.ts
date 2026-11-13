/**
 * Types for Phase 7 — Fairness Impact Simulation.
 *
 * All values are derived from actual persisted simulation results
 * and self-reported candidate demographic data.
 */

// ─── Group-Level Metrics ─────────────────────────────────────────

export interface FairnessGroupMetric {
  group_dimension: string;
  group_value: string;
  sample_size: number;
  eligible_count: number;
  baseline_selected_count: number;
  simulation_selected_count: number;
  baseline_selection_rate: number | null;
  simulation_selection_rate: number | null;
  selection_rate_change: number | null;
  entered_selection: number;
  exited_selection: number;
  retained_selection: number;
  metric_status: "available" | "insufficient_sample" | "no_demographic_data";
  status_reason: string | null;
}

// ─── Cross-Group Metrics ────────────────────────────────────────

export interface FairnessCrossGroupMetric {
  metric_name: string;
  metric_label: string;
  baseline_value: number | null;
  simulation_value: number | null;
  absolute_change: number | null;
  relative_change: number | null;
  reference_group: string | null;
  groups_compared: string[];
  metric_status:
    | "available"
    | "insufficient_data"
    | "no_reference_group"
    | "identical_rates";
  status_reason: string | null;
}

// ─── Insights ───────────────────────────────────────────────────

export interface FairnessInsight {
  type: string;
  message: string;
  metric_value?: number;
  metric_unit?: string;
}

// ─── Main Response ──────────────────────────────────────────────

export interface FairnessImpactResponse {
  simulation_id: string;
  execution_id: string;
  execution_status: string;
  scenario_name: string;
  job_title: string;
  company: string;
  engine_version: string;
  completed_at: string | null;

  group_dimension: string;
  reference_group: string | null;
  total_candidates: number;
  candidates_with_demographic: number;
  candidates_missing_demographic: number;
  minimum_group_size: number;

  group_metrics: FairnessGroupMetric[];
  cross_group_metrics: FairnessCrossGroupMetric[];
  insights: FairnessInsight[];
}

// ─── Helper Constants ───────────────────────────────────────────

export const METRIC_STATUS_LABELS: Record<string, string> = {
  available: "Available",
  insufficient_sample: "Insufficient Sample",
  insufficient_data: "Insufficient Data",
  no_demographic_data: "No Demographic Data",
  no_reference_group: "No Reference Group",
  identical_rates: "Identical Rates",
};

export const INSIGHT_TYPE_ICONS: Record<string, string> = {
  demographic_coverage: "\u{1F4CA}",
  reference_group: "\u2696",
  selection_rate_change: "\u2195",
  candidate_transition: "\u{1F504}",
  cross_group_metric: "\u{1F4CA}",
  insufficient_sample: "\u26A0",
  data_limitation: "\u2753",
};

// ─── Helper Functions ───────────────────────────────────────────

export function formatSelectionRate(rate: number | null): string {
  if (rate === null) return "N/A";
  return `${(rate * 100).toFixed(1)}%`;
}

export function formatRateChange(change: number | null): string {
  if (change === null) return "N/A";
  const pp = change * 100;
  if (pp > 0) return `+${pp.toFixed(1)} pp`;
  if (pp < 0) return `${pp.toFixed(1)} pp`;
  return "0.0 pp";
}

export function formatMetricValue(value: number | null, unit?: string): string {
  if (value === null) return "N/A";
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "rate") return value.toFixed(4);
  return value.toFixed(4);
}

export function formatDelta(value: number | null): string {
  if (value === null) return "N/A";
  if (value > 0) return `+${value.toFixed(4)}`;
  if (value < 0) return value.toFixed(4);
  return "0.0000";
}

export function getChangePositive(change: number | null): boolean | undefined {
  if (change === null) return undefined;
  return change > 0;
}
