/** Phase 6 — Threshold & Shortlist Impact Analysis Types */

// ─── Threshold Types ──────────────────────────────────────────────

export interface ThresholdBoundaryCandidate {
  candidate_id: string;
  candidate_name: string;
  score: number;
  threshold: number;
  distance_from_threshold: number;
  qualified: boolean;
  baseline_qualified: boolean;
  qualification_change: string;
  baseline_rank: number;
  simulation_rank: number;
  rank_change: number;
  baseline_shortlisted: boolean;
  simulation_shortlisted: boolean;
}

export interface ThresholdSensitivityPoint {
  threshold: number;
  qualified_count: number;
  percentage_qualified: number;
}

export interface ThresholdScoreDistribution {
  label: string;
  lower_bound: number;
  upper_bound: number;
  candidate_count: number;
  is_threshold_band: boolean;
}

export interface ThresholdInsight {
  type: string;
  message: string;
  metric_value?: number | null;
  metric_unit?: string | null;
}

export interface ThresholdImpactResponse {
  simulation_id: string;
  execution_id: string;
  execution_status: string;
  scenario_name: string;
  job_title: string;
  company: string;
  engine_version: string;
  completed_at: string | null;

  baseline_threshold: number;
  simulation_threshold: number;
  threshold_change: number;

  baseline_qualified_count: number;
  simulation_qualified_count: number;
  qualified_change: number;
  percentage_qualified_before: number;
  percentage_qualified_after: number;

  newly_qualified_count: number;
  newly_disqualified_count: number;
  remained_qualified_count: number;
  remained_unqualified_count: number;

  qualification_retention_rate: number | null;
  qualification_turnover_rate: number | null;

  boundary_range: number;
  boundary_candidates: ThresholdBoundaryCandidate[];

  sensitivity_data: ThresholdSensitivityPoint[];

  score_distribution: ThresholdScoreDistribution[];

  total_candidates: number;

  insights: ThresholdInsight[];
}

// ─── Shortlist Types ──────────────────────────────────────────────

export interface ShortlistBoundaryCandidate {
  candidate_id: string;
  candidate_name: string;
  rank: number;
  score: number;
  baseline_shortlisted: boolean;
  simulation_shortlisted: boolean;
  shortlist_change: string;
  distance_from_boundary: number;
}

export interface ShortlistSensitivityPoint {
  shortlist_size: number;
  actual_shortlisted: number;
  overlap_with_baseline: number;
  newly_included: number;
  overlap_percentage: number;
}

export interface ShortlistInsight {
  type: string;
  message: string;
  metric_value?: number | null;
  metric_unit?: string | null;
}

export interface ShortlistImpactResponse {
  simulation_id: string;
  execution_id: string;
  execution_status: string;
  scenario_name: string;
  job_title: string;
  company: string;
  engine_version: string;
  completed_at: string | null;

  baseline_shortlist_size: number;
  simulation_shortlist_size: number;
  shortlist_change: number;
  actual_baseline_shortlisted: number;
  actual_simulation_shortlisted: number;

  retained_count: number;
  entered_count: number;
  exited_count: number;

  overlap_count: number;
  overlap_union_count: number;
  jaccard_similarity: number;
  retention_rate: number;
  turnover_rate: number;

  boundary_range: number;
  boundary_candidates: ShortlistBoundaryCandidate[];

  sensitivity_data: ShortlistSensitivityPoint[];

  total_candidates: number;

  insights: ShortlistInsight[];
}

// ─── Combined Types ───────────────────────────────────────────────

export interface CombinedImpactMatrix {
  retained: number;
  entered: number;
  exited: number;
  remained_outside: number;
}

export interface CandidateThresholdShortlistImpact {
  candidate_id: string;
  candidate_name: string;

  baseline_score: number;
  baseline_rank: number;
  baseline_threshold: number;
  baseline_qualified: boolean;
  baseline_shortlisted: boolean;

  simulation_score: number;
  simulation_rank: number;
  simulation_threshold: number;
  simulation_qualified: boolean;
  simulation_shortlisted: boolean;

  qualification_change: string;
  shortlist_change: string;
  score_change: number;
  rank_change: number;

  explanation: string;
}

export interface CombinedThresholdShortlistResponse {
  simulation_id: string;
  execution_id: string;
  execution_status: string;
  scenario_name: string;
  job_title: string;
  company: string;
  completed_at: string | null;

  threshold_impact: ThresholdImpactResponse;
  shortlist_impact: ShortlistImpactResponse;

  combined_matrix: CombinedImpactMatrix;
  total_affected_candidates: number;

  candidate_impacts: CandidateThresholdShortlistImpact[];

  insights: (ThresholdInsight | ShortlistInsight)[];
}

// ─── Helper Functions ─────────────────────────────────────────────

export const QUALIFICATION_CHANGE_LABELS: Record<string, string> = {
  newly_qualified: "Newly Qualified",
  newly_disqualified: "Newly Disqualified",
  remained_qualified: "Remained Qualified",
  remained_unqualified: "Remained Unqualified",
};

export const SHORTLIST_CHANGE_LABELS: Record<string, string> = {
  entered: "Entered Shortlist",
  exited: "Exited Shortlist",
  retained: "Retained",
  unchanged: "Unchanged",
};

export function formatImpactDelta(value: number): string {
  if (value > 0) return `+${value}`;
  return `${value}`;
}

export function formatImpactPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}
