export type SimulationStatus =
  | "draft"
  | "ready"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type SimulationEducationLevel =
  | "high_school"
  | "associate"
  | "bachelor"
  | "master"
  | "doctorate";

export type SimulationEducationRequirement = "required" | "preferred" | "optional";

export interface SimulationScoringWeights {
  skills: number;
  experience: number;
  education: number;
  projects: number;
  certifications: number;
  location: number;
  employment_type: number;
  semantic: number;
}

export interface ExperienceRange {
  minimum_years: number | null;
  maximum_years: number | null;
}

export interface EducationRequirement {
  level: SimulationEducationLevel | null;
  requirement: SimulationEducationRequirement;
}

export interface SimulationRequirements {
  mandatory_skills: string[];
  preferred_skills: string[];
  /** Structured, editable range (Scenario Builder). */
  experience?: ExperienceRange | null;
  /** Structured, editable education requirement (Scenario Builder). */
  education?: EducationRequirement | null;
  /** Legacy free-text mirrors of the live job posting fields. */
  experience_required?: string | null;
  education_required?: string | null;
}

export interface SimulationConfiguration {
  /** Mirrors the scenario's config_version; self-describing persisted JSON. */
  version: number;
  scoring_weights: SimulationScoringWeights;
  threshold: number;
  shortlist_size: number;
  requirements: SimulationRequirements;
}

export interface SimulationBaselineConfig {
  source: string;
  job_id: string;
  job_version: number;
  title: string;
  company: string;
  scoring_weights: SimulationScoringWeights;
  threshold: number;
  shortlist_size: number;
  requirements: SimulationRequirements;
}

export interface SimulationScenario {
  id: string;
  organization_id: string | null;
  job_id: string;
  created_by: string;
  name: string;
  description: string | null;
  status: SimulationStatus;
  baseline_config: SimulationBaselineConfig;
  simulation_config: SimulationConfiguration | null;
  config_version: number;
  metadata: Record<string, unknown> | null;
  job_title: string;
  company: string;
  created_by_name: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimulationScenarioListItem {
  id: string;
  organization_id: string | null;
  job_id: string;
  created_by: string;
  name: string;
  status: SimulationStatus;
  job_title: string;
  company: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface SimulationStats {
  total: number;
  drafts: number;
  ready: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  by_status: Record<string, number>;
}

export interface SimulationScenarioListResponse {
  items: SimulationScenarioListItem[];
  stats: SimulationStats;
}

export interface SimulationStatusResponse {
  simulation_id: string;
  status: SimulationStatus;
  can_edit: boolean;
  updated_at: string;
  completed_at: string | null;
}

export interface SimulationScenarioFormData {
  job_id: string;
  name: string;
  description?: string;
  simulation_config?: SimulationConfiguration;
  metadata?: Record<string, unknown>;
}

export interface SimulationScenarioUpdateData {
  name?: string;
  description?: string;
  status?: SimulationStatus;
  simulation_config?: SimulationConfiguration;
  metadata?: Record<string, unknown>;
}

// ─── Validation ──────────────────────────────────────────────────────

export interface SimulationValidationIssue {
  field: string;
  message: string;
}

export interface SimulationValidationResponse {
  valid: boolean;
  errors: SimulationValidationIssue[];
}

// ─── Change detection (baseline vs scenario) ────────────────────────

export type FieldChangeKind =
  | "unchanged"
  | "increased"
  | "decreased"
  | "added"
  | "removed"
  | "changed";

export interface SimulationFieldChange {
  key: string;
  label: string;
  baseline: string | number | null;
  scenario: string | number | null;
  change: FieldChangeKind;
}

export interface SimulationSkillMovement {
  skill: string;
  from_list: string;
  to_list: string;
}

export interface SimulationSkillsChange {
  mandatory_added: string[];
  mandatory_removed: string[];
  preferred_added: string[];
  preferred_removed: string[];
  moved: SimulationSkillMovement[];
}

export interface SimulationChangesResponse {
  simulation_id: string;
  config_version: number;
  total_changes: number;
  changed_fields: string[];
  fields: SimulationFieldChange[];
  skills: SimulationSkillsChange;
}

// ─── Execution (Phase 3 — real what-if runs) ───────────────────────

export interface SimulationExecution {
  id: string;
  scenario_id: string;
  organization_id: string | null;
  job_id: string;
  created_by: string;
  status: SimulationStatus;
  progress: number;
  total_candidates: number;
  processed_candidates: number;
  engine_version: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimulationExecutionListResponse {
  scenario_id: string;
  items: SimulationExecution[];
}

export interface SimulationImpactMetric {
  metric: string;
  baseline_value: number;
  simulation_value: number;
  change_value: number;
}

export type SimulationCandidateStatus = "qualified" | "not_qualified";

export interface SimulationResultItem {
  candidate_id: string;
  candidate_name: string;
  baseline_score: number;
  simulation_score: number;
  score_change: number;
  baseline_rank: number;
  simulation_rank: number;
  rank_change: number;
  baseline_status: SimulationCandidateStatus;
  simulation_status: SimulationCandidateStatus;
  baseline_shortlisted: boolean;
  simulation_shortlisted: boolean;
  baseline_dimensions: Record<string, number> | null;
  simulation_dimensions: Record<string, number> | null;
  reason: string | null;
}

export interface SimulationResultsResponse {
  scenario_id: string;
  execution_id: string;
  total: number;
  page: number;
  page_size: number;
  items: SimulationResultItem[];
}

export type SimulationChangeFilter =
  | "improved"
  | "declined"
  | "entered_shortlist"
  | "left_shortlist"
  | "qualified"
  | "disqualified";

export type SimulationResultsSortBy =
  | "simulation_rank"
  | "baseline_rank"
  | "score_change"
  | "rank_change";

export interface SimulationResultsParams {
  execution_id?: string;
  page?: number;
  page_size?: number;
  sort_by?: SimulationResultsSortBy;
  order?: "asc" | "desc";
  change_filter?: SimulationChangeFilter;
}

export interface SimulationSummaryAggregate {
  engine_version: string;
  candidate_count: number;
  threshold: { baseline: number; simulation: number };
  shortlist: { baseline: number; simulation: number };
  qualified: { baseline: number; simulation: number; change: number };
  shortlisted: { baseline: number; simulation: number; change: number };
  pool_movement: { entered_shortlist: number; left_shortlist: number };
  score_movement: { improved: number; declined: number; unchanged: number };
  average_score: { baseline: number; simulation: number; change: number };
  top_candidate_changed: boolean;
  baseline_top_candidate: string | null;
  simulation_top_candidate: string | null;
}

export interface SimulationSummaryResponse {
  scenario_id: string;
  execution_id: string;
  status: SimulationStatus | "no_execution";
  engine_version: string;
  total_candidates: number;
  processed_candidates: number;
  threshold_baseline: number;
  threshold_simulation: number;
  shortlist_baseline: number;
  shortlist_simulation: number;
  summary: SimulationSummaryAggregate | Record<string, never>;
  metrics: SimulationImpactMetric[];
  major_movements: SimulationResultItem[];
  completed_at: string | null;
  error_message: string | null;
}

export const DEFAULT_SCORING_WEIGHTS: SimulationScoringWeights = {
  skills: 0.4,
  experience: 0.25,
  education: 0.15,
  projects: 0.2,
  certifications: 0,
  location: 0,
  employment_type: 0,
  semantic: 0,
};

export const SCORING_WEIGHT_FIELDS: { key: keyof SimulationScoringWeights; label: string }[] = [
  { key: "skills", label: "Skills" },
  { key: "experience", label: "Experience" },
  { key: "education", label: "Education" },
  { key: "projects", label: "Projects" },
  { key: "certifications", label: "Certifications" },
  { key: "location", label: "Location" },
  { key: "employment_type", label: "Employment type" },
  { key: "semantic", label: "Semantic match" },
];

export const EDUCATION_LEVEL_LABELS: Record<SimulationEducationLevel, string> = {
  high_school: "High School",
  associate: "Associate's",
  bachelor: "Bachelor's",
  master: "Master's",
  doctorate: "Doctorate",
};

export const EDUCATION_LEVEL_OPTIONS: SimulationEducationLevel[] = [
  "high_school",
  "associate",
  "bachelor",
  "master",
  "doctorate",
];

export const EDUCATION_REQUIREMENT_OPTIONS: SimulationEducationRequirement[] = [
  "required",
  "preferred",
  "optional",
];

export const EDUCATION_REQUIREMENT_LABELS: Record<SimulationEducationRequirement, string> = {
  required: "Required",
  preferred: "Preferred",
  optional: "Optional",
};

export function createDefaultSimulationConfiguration(
  requirements?: Partial<SimulationRequirements>,
): SimulationConfiguration {
  return {
    version: 1,
    scoring_weights: { ...DEFAULT_SCORING_WEIGHTS },
    threshold: 70,
    shortlist_size: 10,
    requirements: {
      mandatory_skills: [],
      preferred_skills: [],
      experience: null,
      education: null,
      experience_required: null,
      education_required: null,
      ...requirements,
    },
  };
}

export function isSimulationEditable(status: SimulationStatus): boolean {
  return status === "draft" || status === "cancelled";
}

/** Build an editable configuration from a frozen baseline snapshot. */
export function simulationConfigFromBaseline(
  baseline: SimulationBaselineConfig,
): SimulationConfiguration {
  return {
    version: 1,
    scoring_weights: { ...baseline.scoring_weights },
    threshold: baseline.threshold,
    shortlist_size: baseline.shortlist_size,
    requirements: {
      mandatory_skills: [...(baseline.requirements.mandatory_skills ?? [])],
      preferred_skills: [...(baseline.requirements.preferred_skills ?? [])],
      experience: null,
      education: null,
      experience_required: baseline.requirements.experience_required ?? null,
      education_required: baseline.requirements.education_required ?? null,
    },
  };
}

// ─── Client-side validation (mirror of the backend rules) ────────────

export function scoringWeightsTotal(weights: SimulationScoringWeights): number {
  return SCORING_WEIGHT_FIELDS.reduce((sum, field) => sum + (weights[field.key] || 0), 0);
}

export function scoringWeightsTotalPercent(weights: SimulationScoringWeights): number {
  return Math.round(scoringWeightsTotal(weights) * 1000) / 10;
}

function normalizeSkillName(skill: string): string {
  return skill.trim().toLowerCase().replace(/\s+/g, " ");
}

function fieldError(field: string, message: string): SimulationValidationIssue {
  return { field, message };
}

export function validateSimulationConfig(
  config: SimulationConfiguration | null | undefined,
): SimulationValidationResponse {
  if (!config) {
    return {
      valid: false,
      errors: [
        fieldError(
          "config",
          "No simulation configuration recorded. Configure the scenario before validating.",
        ),
      ],
    };
  }

  const errors: SimulationValidationIssue[] = [];

  const total = scoringWeightsTotal(config.scoring_weights);
  if (Math.abs(total - 1) > 0.001) {
    errors.push(
      fieldError(
        "scoring_weights.total",
        `Scoring weights must total 100% (currently ${scoringWeightsTotalPercent(config.scoring_weights)}%).`,
      ),
    );
  }
  for (const field of SCORING_WEIGHT_FIELDS) {
    const value = config.scoring_weights[field.key];
    if (typeof value !== "number" || value < 0 || value > 1) {
      errors.push(
        fieldError(`scoring_weights.${field.key}`, `Weight for ${field.label} must be between 0 and 1.`),
      );
    }
  }

  if (!Number.isInteger(config.threshold) || config.threshold < 0 || config.threshold > 100) {
    errors.push(fieldError("threshold", `Pass threshold must be between 0 and 100.`));
  }
  if (!Number.isInteger(config.shortlist_size) || config.shortlist_size < 1 || config.shortlist_size > 500) {
    errors.push(fieldError("shortlist_size", `Shortlist size must be between 1 and 500.`));
  }

  const requirements = config.requirements || {};
  const mandatory = requirements.mandatory_skills ?? [];
  const preferred = requirements.preferred_skills ?? [];

  const seenMandatory = new Set<string>();
  for (const skill of mandatory) {
    if (typeof skill !== "string") continue;
    const normalized = normalizeSkillName(skill);
    if (!normalized) {
      errors.push(fieldError("requirements.mandatory_skills", "Skill names cannot be empty."));
      continue;
    }
    if (seenMandatory.has(normalized)) {
      errors.push(fieldError("requirements.mandatory_skills", `Duplicated skill: "${skill.trim()}".`));
    }
    seenMandatory.add(normalized);
  }
  const seenPreferred = new Set<string>();
  for (const skill of preferred) {
    if (typeof skill !== "string") continue;
    const normalized = normalizeSkillName(skill);
    if (!normalized) {
      errors.push(fieldError("requirements.preferred_skills", "Skill names cannot be empty."));
      continue;
    }
    if (seenPreferred.has(normalized)) {
      errors.push(fieldError("requirements.preferred_skills", `Duplicated skill: "${skill.trim()}".`));
    }
    seenPreferred.add(normalized);
  }

  const overlap = [...seenMandatory].filter((skill) => seenPreferred.has(skill));
  if (overlap.length > 0) {
    errors.push(
      fieldError(
        "requirements",
        `A skill cannot be both mandatory and preferred: ${overlap.join(", ")}.`,
      ),
    );
  }

  const experience = requirements.experience;
  if (experience) {
    const minimum = experience.minimum_years;
    const maximum = experience.maximum_years;
    if (minimum == null && maximum == null) {
      errors.push(
        fieldError(
          "requirements.experience",
          "Specify at least one of minimum or maximum years of experience.",
        ),
      );
    }
    if (minimum != null && (typeof minimum !== "number" || !Number.isInteger(minimum) || minimum < 0 || minimum > 50)) {
      errors.push(fieldError("requirements.experience.minimum_years", "Minimum years must be between 0 and 50."));
    }
    if (maximum != null && (typeof maximum !== "number" || !Number.isInteger(maximum) || maximum < 0 || maximum > 50)) {
      errors.push(fieldError("requirements.experience.maximum_years", "Maximum years must be between 0 and 50."));
    }
    if (minimum != null && maximum != null && maximum < minimum) {
      errors.push(
        fieldError(
          "requirements.experience",
          `Maximum years (${maximum}) cannot be lower than minimum years (${minimum}).`,
        ),
      );
    }
  }

  const education = requirements.education;
  if (education) {
    if (
      education.level != null &&
      !EDUCATION_LEVEL_OPTIONS.includes(education.level as SimulationEducationLevel)
    ) {
      errors.push(fieldError("requirements.education.level", `Unknown education level: ${education.level}.`));
    }
    if (!EDUCATION_REQUIREMENT_OPTIONS.includes(education.requirement)) {
      errors.push(
        fieldError("requirements.education.requirement", `Unknown education requirement: ${education.requirement}.`),
      );
    }
  }

  return { valid: errors.length === 0, errors };
}

// ─── Client-side change detection (live preview) ─────────────────────

export function experienceLabel(requirements: SimulationRequirements): string {
  const experience = requirements.experience;
  if (experience) {
    if (experience.minimum_years != null && experience.maximum_years != null) {
      return `${experience.minimum_years}–${experience.maximum_years} years`;
    }
    if (experience.minimum_years != null) return `${experience.minimum_years}+ years`;
    if (experience.maximum_years != null) return `Up to ${experience.maximum_years} years`;
  }
  return requirements.experience_required ?? "—";
}

export function educationLabel(requirements: SimulationRequirements): string {
  const education = requirements.education;
  if (education) {
    if (!education.level) return "Any level";
    const levelText = EDUCATION_LEVEL_LABELS[education.level] ?? education.level;
    if (education.requirement === "required") return levelText;
    return `${levelText} (${EDUCATION_REQUIREMENT_LABELS[education.requirement] ?? education.requirement})`;
  }
  return requirements.education_required ?? "—";
}

function compareNumber(baseline: number | string | null, scenario: number | string | null): FieldChangeKind {
  if (typeof baseline === "number" && typeof scenario === "number") {
    if (Math.abs(baseline - scenario) < 1e-9) return "unchanged";
    return scenario > baseline ? "increased" : "decreased";
  }
  return baseline === scenario ? "unchanged" : "changed";
}

function diffSkills(
  baselineRequirements: SimulationRequirements,
  scenarioRequirements: SimulationRequirements,
): SimulationSkillsChange {
  const bMandatory = (baselineRequirements.mandatory_skills ?? []).map(normalizeSkillName);
  const bPreferred = (baselineRequirements.preferred_skills ?? []).map(normalizeSkillName);
  const sMandatory = (scenarioRequirements.mandatory_skills ?? []).map(normalizeSkillName);
  const sPreferred = (scenarioRequirements.preferred_skills ?? []).map(normalizeSkillName);

  const mandatoryAdded = sMandatory.filter((skill) => !bMandatory.includes(skill) && !bPreferred.includes(skill));
  const mandatoryRemoved = bMandatory.filter((skill) => !sMandatory.includes(skill) && !sPreferred.includes(skill));
  const preferredAdded = sPreferred.filter((skill) => !bPreferred.includes(skill) && !bMandatory.includes(skill));
  const preferredRemoved = bPreferred.filter((skill) => !sPreferred.includes(skill) && !sMandatory.includes(skill));

  const moved = [
    ...sPreferred
      .filter((skill) => bMandatory.includes(skill) && !sMandatory.includes(skill))
      .map((skill) => ({ skill, from_list: "mandatory", to_list: "preferred" })),
    ...sMandatory
      .filter((skill) => bPreferred.includes(skill) && !sPreferred.includes(skill))
      .map((skill) => ({ skill, from_list: "preferred", to_list: "mandatory" })),
  ];

  return {
    mandatory_added: mandatoryAdded,
    mandatory_removed: mandatoryRemoved,
    preferred_added: preferredAdded,
    preferred_removed: preferredRemoved,
    moved,
  };
}

/** Live review preview; the backend GET /changes endpoint is authoritative. */
export function computeClientChanges(
  baseline: SimulationBaselineConfig,
  config: SimulationConfiguration | null,
): SimulationChangesResponse {
  const scenarioRequirements = config?.requirements ?? { mandatory_skills: [], preferred_skills: [] };

  const fields: SimulationFieldChange[] = SCORING_WEIGHT_FIELDS.map((field) => ({
    key: `scoring_weights.${field.key}`,
    label: `${field.label} weight`,
    baseline: baseline.scoring_weights[field.key] ?? 0,
    scenario: config ? (config.scoring_weights[field.key] ?? 0) : null,
    change: compareNumber(
      baseline.scoring_weights[field.key] ?? 0,
      config?.scoring_weights[field.key] ?? null,
    ),
  }));

  fields.push(
    {
      key: "threshold",
      label: "Pass threshold",
      baseline: baseline.threshold,
      scenario: config?.threshold ?? null,
      change: compareNumber(baseline.threshold, config?.threshold ?? null),
    },
    {
      key: "shortlist_size",
      label: "Shortlist size",
      baseline: baseline.shortlist_size,
      scenario: config?.shortlist_size ?? null,
      change: compareNumber(baseline.shortlist_size, config?.shortlist_size ?? null),
    },
    {
      key: "requirements.experience",
      label: "Experience",
      baseline: experienceLabel(baseline.requirements),
      scenario: config ? experienceLabel(scenarioRequirements) : null,
      change:
        experienceLabel(baseline.requirements) === (config ? experienceLabel(scenarioRequirements) : "")
          ? "unchanged"
          : "changed",
    },
    {
      key: "requirements.education",
      label: "Education",
      baseline: educationLabel(baseline.requirements),
      scenario: config ? educationLabel(scenarioRequirements) : null,
      change:
        educationLabel(baseline.requirements) === (config ? educationLabel(scenarioRequirements) : "")
          ? "unchanged"
          : "changed",
    },
  );

  const skills = diffSkills(baseline.requirements, scenarioRequirements);
  const changedFieldKeys = fields.filter((f) => f.change !== "unchanged").map((f) => f.key);
  if (skills.mandatory_added.length || skills.mandatory_removed.length) {
    changedFieldKeys.push("requirements.mandatory_skills");
  }
  if (skills.preferred_added.length || skills.preferred_removed.length) {
    changedFieldKeys.push("requirements.preferred_skills");
  }
  if (skills.moved.length) {
    changedFieldKeys.push("requirements.skills_moved");
  }

  const totalChanges =
    fields.filter((f) => f.change !== "unchanged").length +
    skills.mandatory_added.length +
    skills.mandatory_removed.length +
    skills.preferred_added.length +
    skills.preferred_removed.length +
    skills.moved.length;

  return {
    simulation_id: "",
    config_version: config?.version ?? 1,
    total_changes: totalChanges,
    changed_fields: changedFieldKeys,
    fields,
    skills,
  };
}

// ─── Execution helpers (Phase 3) ────────────────────────────────────

/** Statuses a scenario can be re-run from (draft cannot run; queued/running
 * already have an in-flight execution). */
export function canRunSimulation(status: SimulationStatus): boolean {
  return status === "ready" || status === "completed" || status === "failed";
}

export function isExecutionActive(status: SimulationStatus): boolean {
  return status === "queued" || status === "running";
}

export const SIMULATION_METRIC_LABELS: Record<string, string> = {
  candidate_count: "Candidates evaluated",
  qualified_count: "Qualified",
  shortlisted_count: "Shortlisted",
  entered_shortlist: "Entered shortlist",
  left_shortlist: "Left shortlist",
  average_score: "Average score",
  score_improved_count: "Improved scores",
  score_declined_count: "Declined scores",
  top_candidate_changed: "Top candidate changed",
};

export function simulationMetricLabel(metric: string): string {
  return SIMULATION_METRIC_LABELS[metric] ?? metric.replace(/_/g, " ");
}

export function formatScoreDelta(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}

// ─── Optional manual shortlist (hypothetical → live, human-confirmed) ───

export interface SimulationShortlistApplyRequest {
  /** Exactly the candidates the recruiter checked and explicitly confirmed. */
  candidate_ids: string[];
  /** Optional: apply from a specific completed execution. */
  execution_id?: string;
}

export interface SimulationShortlistCandidateResult {
  candidate_id: string;
  candidate_name: string;
  application_id: string;
  previous_status: string;
  new_status: string;
  updated: boolean;
}

export interface SimulationShortlistApplyResponse {
  simulation_id: string;
  execution_id: string;
  job_id: string;
  /** The simulation is never overwritten; stays "completed". */
  scenario_status: string;
  shortlist_status: string;
  applied: boolean;
  updated: SimulationShortlistCandidateResult[];
  skipped: SimulationShortlistCandidateResult[];
}