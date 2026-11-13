/* ─── Phase 11: Natural Language Simulation Agent Types ──────── */

export type ChangeType =
  | "SCORING_WEIGHT"
  | "THRESHOLD"
  | "SHORTLIST"
  | "REQUIREMENT"
  | "EXPERIENCE"
  | "EDUCATION"
  | "PRESET"
  | "COMPARE";

export type RequirementOperation = "ADD" | "REMOVE" | "PROMOTE" | "DEMOTE";
export type EducationOperation = "SET_LEVEL" | "SET_REQUIREMENT" | "REMOVE";
export type IntentStatus = "INTERPRETED" | "AMBIGUOUS" | "UNSUPPORTED" | "VALIDATED" | "VALIDATION_FAILED";

export interface Clarification {
  question: string;
  context: string;
  options: string[];
}

export interface ScoringWeightChange {
  type: "SCORING_WEIGHT";
  parameter: string;
  value: number;
  unit: "ratio";
}

export interface ThresholdChange {
  type: "THRESHOLD";
  value: number;
}

export interface ShortlistChange {
  type: "SHORTLIST";
  value: number;
}

export interface RequirementChange {
  type: "REQUIREMENT";
  operation: RequirementOperation;
  skill: string;
  target?: "mandatory" | "preferred";
}

export interface ExperienceChange {
  type: "EXPERIENCE";
  operation: "SET_MIN" | "SET_MAX" | "REMOVE";
  value?: number;
}

export interface EducationChange {
  type: "EDUCATION";
  operation: EducationOperation;
  level?: string;
  requirement?: string;
}

export interface PresetChange {
  type: "PRESET";
  preset: string;
}

export type ChangeOperation =
  | ScoringWeightChange
  | ThresholdChange
  | ShortlistChange
  | RequirementChange
  | ExperienceChange
  | EducationChange
  | PresetChange;

export interface SimulationIntent {
  intent: string;
  job_id: string | null;
  changes: ChangeOperation[];
  clarifications_required: Clarification[];
  unsupported_requests: string[];
  assumptions: string[];
  natural_language_request: string;
  comparison_scenario_ids: string[];
  confidence: number;
  status: IntentStatus;
}

export interface ProposalChange {
  category: string;
  label: string;
  baseline: string;
  proposed: string;
  change_type: string;
}

export interface NLInterpretRequest {
  job_id: string;
  message: string;
}

export interface NLInterpretResponse {
  intent: SimulationIntent;
  proposal: ProposalChange[];
  validation_errors: { field: string; message: string }[];
  requires_confirmation: boolean;
  can_execute: boolean;
  message: string;
}

export interface NLConfirmRequest {
  job_id: string;
  intent: SimulationIntent;
  scenario_name: string;
  scenario_description?: string;
  edited_config?: Record<string, unknown>;
}

export interface NLConfirmResponse {
  scenario_id: string;
  execution_id: string | null;
  status: string;
  message: string;
  requires_execution: boolean;
}

export interface NLExplainRequest {
  scenario_id: string;
  execution_id?: string;
  question: string;
}

export interface NLExplainResponse {
  explanation: string;
  data_sources: string[];
  scenario_id: string;
  execution_id: string | null;
}

/* ─── Chat Message Types ─────────────────────────────────────── */

export type MessageRole = "user" | "agent";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  proposal?: ProposalChange[];
  intent?: SimulationIntent;
  validationErrors?: { field: string; message: string }[];
  canExecute?: boolean;
  scenarioId?: string;
  executionId?: string;
  isLoading?: boolean;
}

/* ─── Suggestion Prompts ─────────────────────────────────────── */

export const SUGGESTION_PROMPTS = [
  "What if experience becomes 40%?",
  "Make PostgreSQL mandatory",
  "Raise the threshold to 80",
  "Shortlist 20 candidates",
  "What happens if we increase the shortlist to 25?",
  "Compare skills-focused vs experience-focused strategies",
  "Make master's degree preferred",
  "Increase skills weight by 10%",
  "Remove Docker from requirements",
  "What happens to fairness if we raise the threshold?",
] as const;

/* ─── Weight Labels ──────────────────────────────────────────── */

export const WEIGHT_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  education: "Education",
  projects: "Projects",
  certifications: "Certifications",
  location: "Location",
  employment_type: "Employment Type",
  semantic: "Semantic Match",
};
