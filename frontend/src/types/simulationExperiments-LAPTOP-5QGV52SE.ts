/* Phase 14: Advanced Simulation & Research Intelligence — TypeScript Types */

export type ExperimentType =
  | "threshold_sweep"
  | "weight_sweep"
  | "shortlist_sweep"
  | "requirement_sweep"
  | "one_parameter_sensitivity"
  | "multi_parameter_sensitivity"
  | "robustness_test"
  | "fairness_sensitivity"
  | "ranking_stability";

export type ExperimentStatus =
  | "draft"
  | "ready"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type SensitivityDimension =
  | "threshold"
  | "shortlist_size"
  | "skills_weight"
  | "experience_weight"
  | "education_weight"
  | "projects_weight"
  | "certifications_weight"
  | "location_weight"
  | "employment_type_weight"
  | "semantic_weight"
  | "mandatory_skills"
  | "preferred_skills"
  | "experience_min"
  | "education_level";

export interface ParameterRange {
  dimension: SensitivityDimension;
  values?: (string | number)[];
  start?: number;
  end?: number;
  step?: number;
}

export interface PerturbationSpec {
  dimension: SensitivityDimension;
  perturbation_type: "numeric_delta" | "numeric_percentage" | "numeric_explicit";
  delta?: number;
  percentage?: number;
  values?: (string | number)[];
}

export interface ExperimentCreateRequest {
  name: string;
  description?: string;
  research_question?: string;
  hypothesis?: string;
  base_scenario_id: string;
  sandbox_id?: string;
  experiment_type: ExperimentType;
  parameter_ranges: ParameterRange[];
  perturbations?: PerturbationSpec[];
  max_configurations?: number;
  random_seed?: number;
}

export interface ExperimentListItem {
  id: string;
  name: string;
  description?: string;
  experiment_type: string;
  status: string;
  base_scenario_name: string;
  job_title: string;
  total_configurations: number;
  completed_configurations: number;
  failed_configurations: number;
  created_by_name: string;
  created_at: string;
  completed_at?: string;
}

export interface ExperimentListResponse {
  items: ExperimentListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExperimentResponse {
  id: string;
  organization_id?: string;
  sandbox_id?: string;
  base_scenario_id: string;
  job_id: string;
  created_by: string;
  name: string;
  description?: string;
  research_question?: string;
  hypothesis?: string;
  experiment_type: string;
  status: string;
  parameters: Record<string, unknown>;
  parameter_ranges: Record<string, unknown>;
  execution_config?: Record<string, unknown>;
  generated_configs?: Record<string, unknown>;
  result_summary?: Record<string, unknown>;
  sensitivity_results?: Record<string, unknown>;
  robustness_results?: Record<string, unknown>;
  stability_results?: Record<string, unknown>;
  fairness_sensitivity_results?: Record<string, unknown>;
  candidate_stability_results?: Record<string, unknown>;
  error_message?: string;
  total_configurations: number;
  completed_configurations: number;
  failed_configurations: number;
  random_seed?: number;
  experiment_version: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface ExperimentStatusResponse {
  experiment_id: string;
  status: string;
  total_configurations: number;
  completed_configurations: number;
  failed_configurations: number;
  error_message?: string;
}

export interface ExperimentResultItem {
  id: string;
  parameter_values: Record<string, unknown>;
  execution_status: string;
  metrics?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
}

export interface ExperimentResultsResponse {
  items: ExperimentResultItem[];
  total: number;
}

export interface SensitivityPoint {
  parameter_value: unknown;
  metric_name: string;
  metric_value: number;
  configuration_hash?: string;
}

export interface SensitivityCurve {
  dimension: string;
  points: SensitivityPoint[];
  min_value: number;
  max_value: number;
  range_spread: number;
  direction: string;
}

export interface SensitivityAnalysisResponse {
  experiment_id: string;
  curves: SensitivityCurve[];
  summary: Record<string, unknown>;
}

export interface RobustnessPerturbationResult {
  dimension: string;
  perturbation_type: string;
  delta?: number;
  ranking_change?: number;
  shortlist_change?: number;
  qualification_change?: number;
  fairness_metric_change?: number;
}

export interface RobustnessProfile {
  parameter: string;
  range_tested: string;
  rank_variation: number;
  shortlist_variation: number;
  fairness_variation?: number;
}

export interface RobustnessAnalysisResponse {
  experiment_id: string;
  perturbation_results: RobustnessPerturbationResult[];
  profiles: RobustnessProfile[];
  summary: Record<string, unknown>;
}

export interface CandidateStabilityMetrics {
  candidate_id: string;
  candidate_name: string;
  appearance_frequency: number;
  shortlist_frequency: number;
  rank_range_min: number;
  rank_range_max: number;
  rank_range: number;
  rank_variance: number;
  qualification_frequency: number;
  score_range_min: number;
  score_range_max: number;
}

export interface StabilityAnalysisResponse {
  experiment_id: string;
  ranking_stability: Record<string, unknown>;
  shortlist_stability: Record<string, unknown>;
  candidate_stability: CandidateStabilityMetrics[];
  summary: Record<string, unknown>;
}

export interface FairnessSensitivityPoint {
  parameter_value: unknown;
  spd?: number;
  di?: number;
  eod?: number;
  selection_rates?: Record<string, number>;
}

export interface FairnessSensitivityResponse {
  experiment_id: string;
  dimension: string;
  points: FairnessSensitivityPoint[];
  summary: Record<string, unknown>;
}

export const EXPERIMENT_TYPE_LABELS: Record<string, string> = {
  threshold_sweep: "Threshold Sweep",
  weight_sweep: "Weight Sweep",
  shortlist_sweep: "Shortlist Sweep",
  requirement_sweep: "Requirement Sweep",
  one_parameter_sensitivity: "One-Parameter Sensitivity",
  multi_parameter_sensitivity: "Multi-Parameter Sensitivity",
  robustness_test: "Robustness Test",
  fairness_sensitivity: "Fairness Sensitivity",
  ranking_stability: "Ranking Stability",
};

export const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  ready: "bg-blue-100 text-blue-700",
  queued: "bg-yellow-100 text-yellow-700",
  running: "bg-purple-100 text-purple-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

export const SENSITIVITY_DIMENSION_LABELS: Record<string, string> = {
  threshold: "Minimum Score Threshold",
  shortlist_size: "Shortlist Size",
  skills_weight: "Skills Weight",
  experience_weight: "Experience Weight",
  education_weight: "Education Weight",
  projects_weight: "Projects Weight",
  certifications_weight: "Certifications Weight",
  location_weight: "Location Weight",
  employment_type_weight: "Employment Type Weight",
  semantic_weight: "Semantic Match Weight",
  mandatory_skills: "Mandatory Skills",
  preferred_skills: "Preferred Skills",
  experience_min: "Experience Minimum",
  education_level: "Education Level",
};
