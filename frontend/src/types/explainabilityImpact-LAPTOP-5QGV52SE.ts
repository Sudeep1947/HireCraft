/**
 * Types for Phase 8 — Explainability Impact Simulation.
 *
 * All values are derived from persisted Phase 3 simulation results
 * and configuration snapshots.
 */

// ─── Feature Contributions ──────────────────────────────────────

export interface FeatureContributionChange {
  feature: string;
  feature_label: string;
  baseline_weight: number;
  simulation_weight: number;
  weight_change: number;
  baseline_dimension_score: number;
  simulation_dimension_score: number;
  dimension_score_change: number;
  baseline_contribution: number;
  simulation_contribution: number;
  contribution_change: number;
}

// ─── Candidate Impact ───────────────────────────────────────────

export interface CandidateExplainabilityImpact {
  candidate_id: string;
  candidate_name: string;
  baseline_score: number;
  simulation_score: number;
  score_change: number;
  baseline_rank: number;
  simulation_rank: number;
  rank_change: number;
  baseline_shortlisted: boolean;
  simulation_shortlisted: boolean;
  qualification_change: string;
  feature_contributions: FeatureContributionChange[];
  top_positive_changes: FeatureContributionChange[];
  top_negative_changes: FeatureContributionChange[];
  reason: string | null;
  impact_type:
    | "score_changed"
    | "rank_only_changed"
    | "threshold_only"
    | "unchanged";
}

// ─── Weight Changes ─────────────────────────────────────────────

export interface WeightChange {
  feature: string;
  feature_label: string;
  baseline_weight: number;
  simulation_weight: number;
  weight_change: number;
}

// ─── Summary ────────────────────────────────────────────────────

export interface ExplainabilityImpactSummary {
  total_candidates: number;
  candidates_with_score_changes: number;
  candidates_with_rank_changes: number;
  candidates_with_contribution_changes: number;
  candidates_unchanged: number;
  average_score_change: number;
  largest_score_increase: number;
  largest_score_decrease: number;
}

// ─── Insights ───────────────────────────────────────────────────

export interface ExplainabilityInsight {
  type: string;
  message: string;
  metric_value?: number;
  metric_unit?: string;
}

// ─── Main Response ──────────────────────────────────────────────

export interface ExplainabilityImpactResponse {
  simulation_id: string;
  execution_id: string;
  execution_status: string;
  scenario_name: string;
  job_title: string;
  company: string;
  engine_version: string;
  completed_at: string | null;
  summary: ExplainabilityImpactSummary;
  weight_changes: WeightChange[];
  candidates: CandidateExplainabilityImpact[];
  insights: ExplainabilityInsight[];
}

// ─── Helper Constants ───────────────────────────────────────────

export const IMPACT_TYPE_LABELS: Record<string, string> = {
  score_changed: "Score Changed",
  rank_only_changed: "Rank Only Changed",
  threshold_only: "Threshold Only",
  unchanged: "Unchanged",
};

export const IMPACT_TYPE_COLORS: Record<string, string> = {
  score_changed: "bg-blue-100 text-blue-800",
  rank_only_changed: "bg-purple-100 text-purple-800",
  threshold_only: "bg-orange-100 text-orange-800",
  unchanged: "bg-gray-100 text-gray-600",
};

export const INSIGHT_TYPE_ICONS: Record<string, string> = {
  weight_change: "\u2699",
  score_change_summary: "\u{1F4CA}",
  rank_only_change: "\u2195",
  threshold_only_change: "\u2696",
  dominant_feature: "\u2B50",
};

// ─── Helper Functions ───────────────────────────────────────────

export function formatContribution(value: number): string {
  return value >= 0 ? `+${value.toFixed(1)}` : value.toFixed(1);
}

export function formatWeight(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatScoreChange(change: number): string {
  if (change > 0) return `+${change}`;
  return `${change}`;
}

export function getScoreColor(change: number): string {
  if (change > 0) return "text-green-600";
  if (change < 0) return "text-red-600";
  return "text-gray-600";
}

export function getContributionColor(change: number): string {
  if (change > 0) return "text-green-600";
  if (change < 0) return "text-red-600";
  return "text-gray-500";
}
