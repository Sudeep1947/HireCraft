/* ─── Phase 10: Multi-Scenario Comparison Types ─────────────── */

export interface ComparisonInclude {
  configuration: boolean;
  ranking: boolean;
  shortlist: boolean;
  requirements: boolean;
  fairness: boolean;
  explainability: boolean;
  skills: boolean;
}

export interface SimulationComparisonRequest {
  scenario_ids: string[];
  include?: ComparisonInclude;
}

export interface ScenarioMetadata {
  scenario_id: string;
  execution_id: string;
  name: string;
  description: string | null;
  job_id: string;
  job_title: string;
  company: string;
  created_by_name: string;
  created_at: string | null;
  completed_at: string | null;
  engine_version: string;
  total_candidates: number;
  processed_candidates: number;
  status: string;
}

export interface WeightComparison {
  weight_name: string;
  weight_label: string;
  values: Record<string, number>;
  min_value: number;
  max_value: number;
  range_spread: number;
}

export interface ThresholdComparison {
  values: Record<string, number>;
  min_value: number;
  max_value: number;
}

export interface ShortlistSizeComparison {
  values: Record<string, number>;
  min_value: number;
  max_value: number;
}

export interface SkillRequirementComparison {
  skill_name: string;
  values: Record<string, "mandatory" | "preferred" | "not_required">;
  change_type: "added" | "removed" | "promoted" | "demoted" | "unchanged";
}

export interface ConfigurationComparison {
  weights: WeightComparison[];
  threshold: ThresholdComparison;
  shortlist_size: ShortlistSizeComparison;
  skill_requirements: SkillRequirementComparison[];
  skills_added: string[];
  skills_removed: string[];
  skills_promoted: string[];
  skills_demoted: string[];
}

export interface CandidateScenarioOutcome {
  scenario_id: string;
  simulation_score: number;
  simulation_rank: number;
  score_change: number;
  rank_change: number;
  qualified: boolean;
  shortlisted: boolean;
  matched_skills: string[];
  missing_required: string[];
}

export interface CandidateComparison {
  candidate_id: string;
  candidate_name: string;
  baseline_score: number;
  baseline_rank: number;
  scenarios: CandidateScenarioOutcome[];
  rank_range_min: number;
  rank_range_max: number;
  score_range_min: number;
  score_range_max: number;
  max_rank_movement: number;
  qualified_count: number;
  shortlisted_count: number;
}

export interface CandidatePoolComparison {
  identical_pools: boolean;
  common_candidates: number;
  scenario_only_counts: Record<string, number>;
  total_unique: number;
}

export interface RankingDistribution {
  scenario_id: string;
  total_candidates: number;
  avg_score: number;
  median_score: number;
  avg_rank: number;
  qualified_count: number;
  shortlisted_count: number;
}

export interface ShortlistOverlap {
  scenario_a_id: string;
  scenario_b_id: string;
  shortlist_a_count: number;
  shortlist_b_count: number;
  common_count: number;
  only_a_count: number;
  only_b_count: number;
  jaccard_similarity: number;
}

export interface RankingComparison {
  distributions: RankingDistribution[];
  pairwise_overlaps: ShortlistOverlap[];
  top_movers: CandidateComparison[];
  most_stable: CandidateComparison[];
}

export interface RequirementComparisonItem {
  requirement_type: string;
  requirement_name: string;
  values: Record<string, string>;
  is_changed: boolean;
}

export interface RequirementComparison {
  items: RequirementComparisonItem[];
  total_changed: number;
  skills_added: number;
  skills_removed: number;
  skills_promoted: number;
  skills_demoted: number;
}

export interface FairnessScenarioMetric {
  scenario_id: string;
  available: boolean;
  unavailable_reason: string;
  groups: Record<string, unknown>[];
  cross_group: Record<string, unknown>[];
  insight_count: number;
}

export interface FairnessComparison {
  scenarios: FairnessScenarioMetric[];
  any_available: boolean;
}

export interface ExplainabilityScenarioSummary {
  scenario_id: string;
  available: boolean;
  total_candidates: number;
  candidates_with_changes: number;
  avg_score_change: number;
  weight_changes: Record<string, unknown>[];
  top_insight: string;
}

export interface ExplainabilityComparison {
  scenarios: ExplainabilityScenarioSummary[];
  any_available: boolean;
}

export interface SkillScenarioSummary {
  scenario_id: string;
  available: boolean;
  total_skills_analyzed: number;
  skills_added: number;
  skills_removed: number;
  skills_promoted: number;
  skills_demoted: number;
  candidates_affected: number;
  top_gaps: Record<string, unknown>[];
}

export interface SkillComparison {
  scenarios: SkillScenarioSummary[];
  any_available: boolean;
}

export interface ComparisonInsight {
  type: string;
  message: string;
  scenario_ids: string[];
  metric_value: number;
  metric_unit: string;
}

export interface MultiScenarioComparisonResponse {
  scenarios: ScenarioMetadata[];
  configuration_comparison: ConfigurationComparison;
  candidate_pool: CandidatePoolComparison;
  candidate_comparison: CandidateComparison[];
  ranking_comparison: RankingComparison;
  requirement_comparison: RequirementComparison;
  fairness_comparison: FairnessComparison;
  explainability_comparison: ExplainabilityComparison;
  skill_comparison: SkillComparison;
  insights: ComparisonInsight[];
}

/* ─── Display Helpers ─────────────────────────────────────────── */

export const CHANGE_TYPE_COLORS: Record<string, string> = {
  added: "text-green-600 bg-green-50",
  removed: "text-red-600 bg-red-50",
  promoted: "text-blue-600 bg-blue-50",
  demoted: "text-amber-600 bg-amber-50",
  unchanged: "text-gray-500 bg-gray-50",
};

export const REQUIREMENT_COLORS: Record<string, string> = {
  mandatory: "text-red-700 bg-red-100",
  preferred: "text-blue-700 bg-blue-100",
  not_required: "text-gray-500 bg-gray-100",
};

export function formatWeight(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatScoreChange(change: number): string {
  if (change > 0) return `+${change}`;
  return `${change}`;
}

export function getScoreColor(change: number): string {
  if (change > 0) return "text-green-600";
  if (change < 0) return "text-red-600";
  return "text-gray-500";
}

export function getRankColor(change: number): string {
  // Positive rank_change means rank improved (lower number = better)
  if (change > 0) return "text-green-600";
  if (change < 0) return "text-red-600";
  return "text-gray-500";
}
