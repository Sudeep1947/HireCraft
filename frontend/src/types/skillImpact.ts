/* ─── Phase 9: Skill Impact Simulation Types ────────────────── */

export type SkillChangeType = "added" | "removed" | "promoted" | "demoted" | "unchanged";
export type RequirementStatus = "mandatory" | "preferred" | "not_required";

export interface SkillChange {
  skill_name: string;
  change_type: SkillChangeType;
  baseline_requirement: RequirementStatus;
  simulation_requirement: RequirementStatus;
  baseline_candidates_match: number;
  simulation_candidates_match: number;
  coverage_change: number;
  candidates_affected: number;
  candidates_newly_qualified: number;
  candidates_newly_disqualified: number;
}

export interface SkillCoverage {
  skill_name: string;
  baseline_coverage: number;
  simulation_coverage: number;
  coverage_change: number;
  baseline_candidates_match: number;
  simulation_candidates_match: number;
  total_eligible: number;
  is_mandatory_baseline: boolean;
  is_mandatory_simulation: boolean;
  is_preferred_baseline: boolean;
  is_preferred_simulation: boolean;
}

export interface SkillGap {
  skill_name: string;
  baseline_gap: number;
  simulation_gap: number;
  gap_change: number;
  is_required: boolean;
  coverage_unavailable: boolean;
}

export interface SkillGraphRelationship {
  source_skill: string;
  target_skill: string;
  relationship_type: "synonym" | "transferable" | "similar";
  similarity_score: number;
}

export interface CandidateSkillImpact {
  candidate_id: string;
  candidate_name: string;
  baseline_matched_skills: string[];
  simulation_matched_skills: string[];
  skills_gained: string[];
  skills_lost: string[];
  baseline_missing_required: string[];
  simulation_missing_required: string[];
  newly_satisfied_required: string[];
  newly_unsatisfied_required: string[];
  baseline_score: number;
  simulation_score: number;
  score_change: number;
  baseline_rank: number;
  simulation_rank: number;
  rank_change: number;
  baseline_qualified: boolean;
  simulation_qualified: boolean;
  qualification_change:
    | "newly_qualified"
    | "newly_disqualified"
    | "remained_qualified"
    | "remained_unqualified";
  skill_match_change: number;
}

export interface SkillImpactSummary {
  total_skills_analyzed: number;
  skills_added: number;
  skills_removed: number;
  skills_promoted: number;
  skills_demoted: number;
  skills_unchanged: number;
  candidates_affected: number;
  candidates_newly_qualified: number;
  candidates_newly_disqualified: number;
  average_skill_match_change: number;
}

export interface SkillImpactInsight {
  type: string;
  message: string;
  metric_value: number;
  metric_unit: string;
}

export interface SkillImpactResponse {
  simulation_id: string;
  execution_id: string;
  execution_status: string;
  scenario_name: string;
  job_title: string;
  company: string;
  engine_version: string;
  completed_at: string | null;
  summary: SkillImpactSummary;
  skill_changes: SkillChange[];
  skill_coverage: SkillCoverage[];
  skill_gaps: SkillGap[];
  skill_graph_relationships: SkillGraphRelationship[];
  candidates: CandidateSkillImpact[];
  insights: SkillImpactInsight[];
}

/* ─── Display Helpers ─────────────────────────────────────────── */

export const CHANGE_TYPE_LABELS: Record<SkillChangeType, string> = {
  added: "Added",
  removed: "Removed",
  promoted: "Promoted",
  demoted: "Demoted",
  unchanged: "Unchanged",
};

export const CHANGE_TYPE_COLORS: Record<SkillChangeType, string> = {
  added: "text-green-600 bg-green-50",
  removed: "text-red-600 bg-red-50",
  promoted: "text-blue-600 bg-blue-50",
  demoted: "text-amber-600 bg-amber-50",
  unchanged: "text-gray-500 bg-gray-50",
};

export const REQUIREMENT_LABELS: Record<RequirementStatus, string> = {
  mandatory: "Mandatory",
  preferred: "Preferred",
  not_required: "Not Required",
};

export const REQUIREMENT_COLORS: Record<RequirementStatus, string> = {
  mandatory: "text-red-700 bg-red-100",
  preferred: "text-blue-700 bg-blue-100",
  not_required: "text-gray-500 bg-gray-100",
};

export const QUALIFICATION_COLORS: Record<string, string> = {
  newly_qualified: "text-green-600 bg-green-50",
  newly_disqualified: "text-red-600 bg-red-50",
  remained_qualified: "text-green-700 bg-green-50",
  remained_unqualified: "text-gray-500 bg-gray-50",
};

export const INSIGHT_TYPE_ICONS: Record<string, string> = {
  skills_added: "+",
  skills_removed: "\u2212",
  skills_promoted: "\u2191",
  skills_demoted: "\u2193",
  candidate_impact: "\u2731",
  qualification_change: "\u26A0",
  largest_skill_gap: "\u25BC",
  skill_movement: "\u21C4",
};

/* ─── Utility Functions ───────────────────────────────────────── */

export function formatCoverage(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatGap(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatScoreChange(change: number): string {
  if (change > 0) return `+${change}`;
  return `${change}`;
}

export function formatRankChange(change: number): string {
  if (change > 0) return `#${change}`;
  if (change < 0) return `#${change}`;
  return "-";
}

export function getScoreColor(change: number): string {
  if (change > 0) return "text-green-600";
  if (change < 0) return "text-red-600";
  return "text-gray-500";
}

export function getCoverageColor(change: number): string {
  if (change > 0) return "text-green-600";
  if (change < 0) return "text-red-600";
  return "text-gray-500";
}
