export interface ScreeningWeights {
  skills: number;
  experience: number;
  education: number;
  projects: number;
  certifications: number;
  location: number;
  employment_type: number;
  semantic: number;
}

export interface ScreeningConfig {
  weights?: ScreeningWeights;
}

export interface ScreeningResult {
  id: string;
  job_id: string;
  candidate_id: string;
  application_id: string | null;
  resume_id: string | null;
  overall_match_score: number;
  skill_match_score: number;
  experience_match_score: number;
  education_match_score: number;
  project_match_score: number;
  certification_match_score: number;
  location_match_score: number;
  employment_type_match_score: number;
  semantic_match_score: number;
  matched_skills: string[] | null;
  missing_required_skills: string[] | null;
  missing_preferred_skills: string[] | null;
  strengths: string[] | null;
  weaknesses: string[] | null;
  recommendation: HiringRecommendation;
  strength_level: StrengthLevel;
  created_at: string;
  updated_at: string;
}

export type StrengthLevel = "excellent" | "good" | "average" | "low";
export type HiringRecommendation =
  | "strongly_recommend"
  | "recommend"
  | "consider"
  | "not_recommended";

export interface CandidateRanking {
  id: string;
  job_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  screening_result_id: string;
  rank: number;
  previous_rank: number | null;
  rank_change: number;
  overall_score: number;
  strength_level: StrengthLevel;
  created_at: string;
  updated_at: string;
}

export interface SkillGapAnalysis {
  id: string;
  screening_result_id: string;
  missing_required_skills: string[] | null;
  missing_preferred_skills: string[] | null;
  experience_gap_description: string | null;
  education_gap_description: string | null;
  certification_gap_description: string | null;
  skill_suggestions: string[] | null;
  improvement_suggestions: string[] | null;
  interview_readiness_score: number;
  created_at: string;
  updated_at: string;
}

export interface CandidateComparisonItem {
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  overall_match_score: number;
  skill_match_score: number;
  experience_match_score: number;
  education_match_score: number;
  project_match_score: number;
  certification_match_score: number;
  matched_skills: string[] | null;
  missing_required_skills: string[] | null;
  strengths: string[] | null;
  weaknesses: string[] | null;
  recommendation: HiringRecommendation;
  strength_level: StrengthLevel;
}

export interface CandidateComparisonResponse {
  job_id: string;
  job_title: string;
  candidates: CandidateComparisonItem[];
}

export interface RankingListResponse {
  items: CandidateRanking[];
  total: number;
  job_id: string;
  job_title: string;
}

export interface ScreeningTriggerResponse {
  message: string;
  job_id: string;
  candidates_screened: number;
}

export interface CandidateMatchReport {
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  screening: ScreeningResult | null;
  skill_gap: SkillGapAnalysis | null;
  interview_readiness_score: number | null;
  improvement_suggestions: string[] | null;
}

// ─── AI Search ──────────────────────────────────────────────────────

export interface AISearchRequest {
  query: string;
  job_id?: string;
  limit?: number;
  offset?: number;
}

export interface AISearchResultItem {
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  overall_score: number;
  relevance_score: number;
  matched_skills: string[];
  missing_skills: string[];
  recommendation: string;
  strength_level: string;
  experience_years: number;
  location: string;
  has_screening: boolean;
}

export interface AISearchResponse {
  results: AISearchResultItem[];
  total: number;
  query_skills: string[];
  query_years: number | null;
  query_location: string | null;
  job_id: string | null;
  job_title: string | null;
}

// ─── Candidate AI Summary ───────────────────────────────────────────

export interface TopSkill {
  skill: string;
  relevance: number;
}

export interface CandidateAISummary {
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  professional_summary: string;
  top_skills: TopSkill[];
  strengths: string[];
  weaknesses: string[];
  career_highlights: string[];
  risk_factors: string[];
  experience_level: string;
  technical_expertise: string;
  leadership_potential: string;
  learning_ability: string;
  total_experience_years: number;
  education_summary: string[];
  certification_count: number;
  project_count: number;
  job_match_score: number | null;
  hiring_recommendation: string | null;
  matched_skills: string[] | null;
  missing_skills: string[] | null;
  strengths_from_screening: string[] | null;
  weaknesses_from_screening: string[] | null;
  interview_readiness: number | null;
  improvement_suggestions: string[] | null;
}

// ─── Job AI Summary ─────────────────────────────────────────────────

export interface SkillCount {
  skill: string;
  count: number;
}

export interface JobAISummary {
  job_id: string;
  job_title: string;
  total_applicants: number;
  total_screened: number;
  average_score: number;
  top_candidates: Array<{
    candidate_id: string;
    candidate_name: string;
    rank: number;
    score: number;
    strength_level: string;
    recommendation: string;
  }>;
  score_distribution: Record<string, number>;
  recommendation_breakdown: Record<string, number>;
  most_common_matched_skills: SkillCount[];
  most_common_missing_skills: SkillCount[];
}

// ─── Top Candidates ─────────────────────────────────────────────────

export interface TopCandidateItem {
  rank: number;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  overall_score: number;
  strength_level: string;
  recommendation: string;
  skill_match: number;
  experience_match: number;
  matched_skills: string[];
  rank_change: number;
}

export interface TopCandidatesResponse {
  job_id: string | null;
  job_title: string | null;
  candidates: TopCandidateItem[];
  total_ranked: number;
  total_jobs: number;
}

// ─── Hiring Recommendation ──────────────────────────────────────────

export interface HiringRecommendationExplanation {
  title: string;
  summary: string;
  factors: string[];
  next_steps: string[];
  score_breakdown: Record<string, number>;
}

export interface HiringRecommendationResponse {
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  recommendation: string;
  overall_score: number;
  confidence_score: number;
  strength_level: string;
  explanation: HiringRecommendationExplanation;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  weaknesses: string[];
  interview_readiness: number | null;
  improvement_suggestions: string[];
}

// ─── Recruiter AI Dashboard ─────────────────────────────────────────

export interface RecruiterDashboardSummary {
  total_jobs: number;
  total_applications: number;
  total_screened: number;
  average_score: number;
  job_summaries: Array<{
    job_id: string;
    job_title: string;
    applicant_count: number;
    screened_count: number;
    average_score: number;
    top_candidate_name: string;
    top_candidate_score: number;
    status: string;
  }>;
  recent_rankings: Array<{
    job_title: string;
    candidate_name: string;
    score: number;
    rank: number;
    rank_change: number;
  }>;
}

// ─── XAI (Explainable AI) ──────────────────────────────────────────

export interface FeatureImportanceItem {
  category: string;
  label: string;
  score: number;
  weight: number;
  contribution_pct: number;
  impact: "positive" | "negative" | "neutral";
  impact_description: string;
  shap_value?: number;
  method?: string;
}

export interface FactorItem {
  category: string;
  score: number;
  contribution_pct: number;
  reason: string;
}

export interface ConfidenceScore {
  score: number;
  level: "very_high" | "high" | "medium" | "low";
  description: string;
  data_completeness_pct: number;
  data_points_available: number;
  data_points_max: number;
}

export interface SkillImprovement {
  skill: string;
  priority: string;
  reason: string;
}

export interface CertificationSuggestion {
  area: string;
  suggestion: string;
  priority: string;
}

export interface ImprovementRecommendations {
  skill_improvements: SkillImprovement[];
  certification_recommendations: CertificationSuggestion[];
  project_suggestions: string[];
  resume_improvements: string[];
  interview_preparation: string[];
}

export interface CandidateExplanation {
  candidate_id: string;
  candidate_name: string;
  job_id: string;
  job_title: string;
  overall_score: number;
  feature_importance: FeatureImportanceItem[];
  positive_factors: FactorItem[];
  negative_factors: FactorItem[];
  reasoning_summary: string;
  confidence: ConfidenceScore;
  improvement_suggestions: ImprovementRecommendations;
  strengths: string[];
  weaknesses: string[];
  matched_skills: string[];
  missing_skills: string[];
  recommendation: string;
  strength_level: string;
  shap_available: boolean;
  lime_available: boolean;
}

export interface PairwiseComparison {
  higher_candidate: string;
  higher_name: string;
  higher_score: number;
  lower_candidate: string;
  lower_name: string;
  lower_score: number;
  score_difference: number;
  key_differences: Array<{
    category: string;
    higher_score: number;
    lower_score: number;
    difference: number;
    direction: string;
  }>;
  skills_only_higher_has: string[];
  skills_only_lower_has: string[];
  summary: string;
}

// ─── Evidence-Grounded Job Fit (Phase 2) ────────────────────────────

export type MatchStatus = "match" | "partial" | "gap" | "unknown";
export type EvidenceStrength = "strong" | "moderate" | "weak" | "none";
export type EvidenceSource =
  | "experience"
  | "project"
  | "certification"
  | "education"
  | "skills_section"
  | "resume_text";

export interface FitEvidenceItem {
  source: EvidenceSource;
  quote: string;
  context: string;
  section: string;
}

export interface FitRequirementResult {
  requirement: string;
  requirement_type: string;
  level: string;
  category: string;
  status: MatchStatus;
  evidence_strength: EvidenceStrength;
  reason: string;
  evidence: FitEvidenceItem[];
}

export interface FitExperienceAlignment {
  status: MatchStatus;
  required_years: number | null;
  relevant_years: number | null;
  total_years: number | null;
  relevance_basis: string;
  reason: string;
}

export interface FitResponsibilityAlignment {
  responsibility: string;
  alignment: EvidenceStrength;
  evidence: FitEvidenceItem[];
}

export interface FitSkillGapSummary {
  strengths: string[];
  partial: string[];
  gaps: string[];
  unknown: string[];
}

export interface FitScoreBreakdown {
  weights: Record<string, number>;
  components: Record<string, number>;
  formula: string;
}

export interface FitOverall {
  classification: string;
  score: number;
  breakdown: FitScoreBreakdown;
  summary: string;
  summary_source: string;
  disclaimer: string;
}

export interface JobRequirementsInfo {
  extracted_count: number;
  extractor_version: string;
}

export interface JobFitResponse {
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  resume_id: string | null;
  requirements: FitRequirementResult[];
  experience_alignment: FitExperienceAlignment;
  responsibilities: FitResponsibilityAlignment[];
  skill_gaps: FitSkillGapSummary;
  overall: FitOverall;
  requirements_info: JobRequirementsInfo;
  cached: boolean;
  engine_version: string;
}

export interface CandidateComparisonXAI {
  job_id: string;
  job_title: string;
  candidates: Array<{
    candidate_id: string;
    candidate_name: string;
    candidate_email: string;
    overall_score: number;
    skill_match_score: number;
    experience_match_score: number;
    education_match_score: number;
    project_match_score: number;
    certification_match_score: number;
    matched_skills: string[];
    missing_skills: string[];
    strengths: string[];
    weaknesses: string[];
    recommendation: string;
    strength_level: string;
    feature_importance: FeatureImportanceItem[];
    confidence: ConfidenceScore;
  }>;
  pairwise_comparisons: PairwiseComparison[];
}

// ─── Candidate Evidence Intelligence (Phase 3) ──────────────────────

export type SkillDepth =
  | "expert_level_evidence"
  | "strong"
  | "moderate"
  | "limited"
  | "mention_only"
  | "no_evidence";

export type IntelConfidence = "high" | "medium" | "low" | "insufficient";

export type ReviewFlagSeverity = "info" | "warning";

export type ReviewFlagType =
  | "stated_vs_timeline_mismatch"
  | "overlapping_employment"
  | "date_inconsistency"
  | "missing_dates"
  | "employment_gap";

export interface ProfileSnapshot {
  total_experience_months: number;
  total_experience_years: number | null;
  experience_count: number;
  project_count: number;
  certification_count: number;
  education_count: number;
  skills_mentioned: number;
  highest_degree: string | null;
}

export interface TimelineInfo {
  computed_months: number;
  stated_years_found: boolean;
  stated_years_value: number | null;
  entries_with_dates: number;
  entries_total: number;
}

export interface SkillAssessment {
  skill: string;
  category: string | null;
  depth: SkillDepth;
  confidence: IntelConfidence;
  professional_months: number;
  counts: Record<string, number>;
  reason: string;
  evidence: FitEvidenceItem[];
}

export interface StrengthInsight {
  title: string;
  category: string | null;
  depth: SkillDepth;
  confidence: IntelConfidence;
  reason: string;
  evidence: FitEvidenceItem[];
}

export interface AchievementInsight {
  text: string;
  context: string | null;
  source_type: "experience" | "project";
  label: string;
}

export interface ReviewFlag {
  flag_type: ReviewFlagType;
  severity: ReviewFlagSeverity;
  title: string;
  description: string;
  possible_explanation: string | null;
  evidence: FitEvidenceItem[];
}

export interface ScreeningQuestionSuggestion {
  question: string;
  topic: string;
  reason: string;
}

export interface EvidenceGapInsight {
  skill: string;
  current_depth: SkillDepth;
  note: string;
}

export interface IntelSummary {
  text: string;
  source: "deterministic" | "llm_polished";
  disclaimer: string;
}

export interface CandidateEvidenceIntelResponse {
  candidate_id: string;
  candidate_name: string;
  resume_id: string | null;
  engine_version: string;
  cached: boolean;
  snapshot: ProfileSnapshot;
  timeline: TimelineInfo;
  strengths: StrengthInsight[];
  skill_assessments: SkillAssessment[];
  achievements: AchievementInsight[];
  review_flags: ReviewFlag[];
  evidence_gaps: EvidenceGapInsight[];
  screening_questions: ScreeningQuestionSuggestion[];
  summary: IntelSummary;
}

export interface JobContextBlock {
  job_id: string;
  job_title: string;
  fit_classification: string;
  fit_score: number;
  required_years: number | null;
  relevant_years: number | null;
  total_years: number | null;
  relevance_basis: string | null;
  requirement_gaps: string[];
  requirement_unknown: string[];
  additional_questions: ScreeningQuestionSuggestion[];
  summary: IntelSummary;
}

export interface JobIntelligenceResponse {
  candidate_id: string;
  candidate_name: string;
  job_id: string;
  job_title: string;
  engine_version: string;
  cached: boolean;
  candidate_intelligence: CandidateEvidenceIntelResponse;
  job_context: JobContextBlock;
}

// ─── Application Screening Detail (Phase 5) ─────────────────────────

export type ApplicationScreeningState =
  | "not_started"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | string;

export interface ScreeningExecutionState {
  effective_status: ApplicationScreeningState;
  recorded_status: string;
  attempts: number;
  task_id: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ScreeningApplicationContext {
  id: string;
  job_id: string;
  candidate_id: string;
  resume_id: string | null;
  status: string;
  applied_at: string | null;
  updated_at: string | null;
  cover_letter: string | null;
  decision_reason: string | null;
  decision_comment: string | null;
  decided_at: string | null;
  screening: ScreeningExecutionState;
}

export interface ScreeningCandidateContext {
  id: string;
  name: string;
  email: string;
  resume_id: string | null;
  has_resume: boolean;
}

export interface ScreeningJobContext {
  id: string;
  title: string;
  company: string;
  location: string;
  employment_type: string;
  experience_required: string;
  education_required: string;
  required_skills: string[];
  preferred_skills: string[];
}

export interface ScreeningDimensionScore {
  key: string;
  label: string;
  score: number;
  source_column: string;
}

export interface ScreeningFreshness {
  screened_at: string | null;
  screening_resume_id: string | null;
  application_resume_id: string | null;
  resume_matches_application: boolean | null;
  engine_version: string | null;
  fit_engine_version: string | null;
  evidence_engine_version: string | null;
}

export interface ScreeningIntelligenceSection {
  available: boolean;
  reason: string | null;
}

export interface ApplicationScreeningDetailResponse {
  application: ScreeningApplicationContext;
  candidate: ScreeningCandidateContext;
  job: ScreeningJobContext;
  screening_result: ScreeningResult | null;
  match_breakdown: ScreeningDimensionScore[];
  evidence_intelligence: CandidateEvidenceIntelResponse | null;
  evidence_intelligence_section: ScreeningIntelligenceSection;
  fit: JobFitResponse | null;
  fit_section: ScreeningIntelligenceSection;
  job_context: JobContextBlock | null;
  job_context_section: ScreeningIntelligenceSection;
  freshness: ScreeningFreshness;
  limitations: string[];
}

// ─── Application Explanation (Phase 6) ─────────────────────────────
// One explanation, two authorized projections. The recruiter and candidate
// responses are deliberately different types: the candidate type is the only
// thing a candidate-facing component may accept, and it has no field for an
// internal verdict, a weight, a formula, a review flag or another candidate's
// data. `weight` exists on the recruiter feature type only.

export type ExplanationState =
  | "not_started"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "unknown";

export interface ExplanationSection {
  available: boolean;
  reason: string | null;
}

export interface ExplanationEvidence {
  source: string;
  quote: string;
  context: string | null;
  section: string | null;
}

export interface ExplanationFeature {
  category: string;
  label: string;
  score: number;
  contribution_pct: number;
  impact: string;
  impact_description: string;
  method: string | null;
}

export interface RecruiterExplanationFeature extends ExplanationFeature {
  weight: number | null;
}

export interface ExplanationFactor {
  category: string;
  score: number;
  contribution_pct: number;
  reason: string;
  evidence: ExplanationEvidence[];
  evidence_available: boolean;
}

export interface ExplanationRequirement {
  requirement: string;
  requirement_type: string;
  level: string;
  category: string | null;
  status: string;
  evidence_strength: string;
  reason: string;
  evidence: ExplanationEvidence[];
}

export interface ExplanationSkillAlignment {
  matched_skills: string[];
  missing_required_skills: string[];
  missing_preferred_skills: string[];
  supported_skills: string[];
  partial_evidence_skills: string[];
  skills_without_evidence: string[];
  insufficient_information_skills: string[];
}

export interface ExplanationAlignment {
  status: string;
  required_years: number | null;
  relevant_years: number | null;
  total_years: number | null;
  relevance_basis: string | null;
  reason: string;
}

export interface ExplanationEvidenceGap {
  subject: string;
  category: string;
  note: string;
}

export interface ExplanationSuggestion {
  category: "skill" | "certification" | "project" | "resume" | "interview";
  subject: string | null;
  text: string;
  priority: string | null;
}

export interface ExplanationConfidence {
  score: number;
  level: string;
  description: string;
  data_completeness_pct: number;
  data_points_available: number;
  data_points_max: number;
}

export interface ExplanationFreshness {
  screening_resume_id: string | null;
  application_resume_id: string | null;
  primary_resume_id: string | null;
  evidence_resume_id: string | null;
  screening_resume_is_current_primary: boolean | null;
  evidence_resume_is_screening_resume: boolean | null;
  screened_at: string | null;
  fit_engine_version: string | null;
  evidence_engine_version: string | null;
  explainability_method: string;
}

export interface ExplanationScreeningState {
  effective_status: ExplanationState;
  screened: boolean;
  message: string;
}

export interface ExplanationEvidenceStrength {
  title: string;
  category: string | null;
  depth: string;
  confidence: string;
  reason: string;
  evidence: ExplanationEvidence[];
  evidence_available: boolean;
}

// ── Recruiter projection ──

export interface ExplanationJob {
  id: string;
  title: string;
  company: string;
  required_skills: string[];
  preferred_skills: string[];
  experience_required: string | null;
  education_required: string | null;
}

export interface RecruiterExplanationCandidate {
  id: string;
  name: string;
  email: string;
}

// Recruiter-only free-form objects. The backend models these as untyped
// dicts on purpose, so they are kept loose here rather than guessed at.
export type ExplanationRecord = Record<string, unknown>;

export interface RecruiterExplanationApplication {
  id: string;
  job_id: string;
  candidate_id: string;
  resume_id: string | null;
  status: string;
  applied_at: string | null;
  updated_at: string | null;
  screening_status: string;
  screening_attempts: number;
  screening_error: string | null;
  screening_started_at: string | null;
  screening_completed_at: string | null;
}

export interface RecruiterExplanationScore {
  overall_score: number | null;
  recommendation: string | null;
  strength_level: string | null;
  screened_at: string | null;
  source: "screening_result" | "unavailable";
}

export interface RecruiterApplicationExplanation {
  application: RecruiterExplanationApplication;
  candidate: RecruiterExplanationCandidate;
  job: ExplanationJob;
  screening_state: ExplanationScreeningState;
  score: RecruiterExplanationScore;
  match_breakdown: ScreeningDimensionScore[];
  feature_importance: RecruiterExplanationFeature[];
  positive_factors: ExplanationFactor[];
  negative_factors: ExplanationFactor[];
  reasoning_summary: string;
  confidence: ExplanationConfidence | null;
  improvement_suggestions: ExplanationSuggestion[];
  skill_alignment: ExplanationSkillAlignment;
  requirements: ExplanationRequirement[];
  experience_alignment: ExplanationAlignment | null;
  evidence_gaps: ExplanationEvidenceGap[];
  evidence_strengths: ExplanationEvidenceStrength[];
  fit_classification: string | null;
  fit_score: number | null;
  fit_summary: string | null;
  fit_summary_source: string | null;
  fit_formula: string | null;
  fit_weights: Record<string, number>;
  review_flags: ExplanationRecord[];
  screening_questions: ExplanationRecord[];
  evidence_snapshot: ExplanationRecord | null;
  explainability: ExplanationSection;
  evidence_intelligence: ExplanationSection;
  fit: ExplanationSection;
  freshness: ExplanationFreshness;
  limitations: string[];
  disclaimer: string;
}

// ── Candidate projection ──

export interface CandidateExplanationApplication {
  id: string;
  job_id: string;
  status: string;
  applied_at: string | null;
  screening_status: string;
}

export interface CandidateExplanationScore {
  overall_score: number | null;
  screened_at: string | null;
  source: "screening_result" | "unavailable";
  match_classification: string | null;
  match_score: number | null;
  match_summary: string | null;
  match_summary_source: string | null;
}

export interface CandidateApplicationExplanation {
  application: CandidateExplanationApplication;
  job: ExplanationJob;
  screening_state: ExplanationScreeningState;
  score: CandidateExplanationScore;
  matched_skills: string[];
  areas_with_limited_evidence: string[];
  skill_alignment: ExplanationSkillAlignment;
  aligned_areas: ExplanationFactor[];
  limited_areas: ExplanationFactor[];
  feature_importance: ExplanationFeature[];
  requirements: ExplanationRequirement[];
  experience_alignment: ExplanationAlignment | null;
  evidence_gaps: ExplanationEvidenceGap[];
  resume_evidence: ExplanationEvidence[];
  improvement_suggestions: ExplanationSuggestion[];
  confidence: ExplanationConfidence | null;
  explainability: ExplanationSection;
  evidence_intelligence: ExplanationSection;
  fit: ExplanationSection;
  freshness: ExplanationFreshness;
  screening_notice: string;
  limitations: string[];
}

// --- Application Fairness Context (Phase 7) ------------------------
// Fairness is a property of a job's *screened population*, not of one
// applicant. These types make that structural: the payload is scoped to a
// population, the application appears only as a member of it, and there is no
// per-candidate fairness score anywhere in the shape.
//
// Two rules encoded in the types rather than left to convention:
//   * every metric carries a status and a reason, so "unavailable" is
//     distinguishable from "favourable";
//   * there is no field that combines fairness with the match score, so a
//     component cannot render a fairness-adjusted score even by mistake.

export type FairnessSectionStatus =
  | "available"
  | "insufficient_data"
  | "no_screening_data"
  | "unavailable";

export interface FairnessSection {
  status: FairnessSectionStatus;
  reason: string | null;
}

export interface FairnessContextApplication {
  id: string;
  job_id: string;
  status: string;
  applied_at: string | null;
}

export interface FairnessContextJob {
  id: string;
  title: string;
  company: string;
}

export interface FairnessScreeningState {
  effective_status: ExplanationState | "failed" | "skipped" | "unknown";
  screened: boolean;
  message: string;
}

export interface FairnessPopulation {
  job_id: string;
  job_title: string;
  applications: number;
  screened: number;
  unscreened: number;
  application_is_in_population: boolean;
  application_screening_included: boolean;
  scope: string;
  note: string;
}

export interface FairnessScoreDistribution {
  average: number;
  minimum: number;
  maximum: number;
  median: number;
  std_dev: number;
  positive_outcome_threshold: number;
  note: string;
}

export type FairnessGroupMetricStatus =
  | "available"
  | "insufficient_sample"
  | "no_demographic_data"
  | "unknown";

export interface FairnessGroupOutcome {
  group_value: string;
  sample_size: number;
  positive_outcome_count: number | null;
  positive_outcome_rate: number | null;
  metric_status: FairnessGroupMetricStatus;
  status_reason: string | null;
}

export type FairnessCrossGroupMetricStatus =
  | "available"
  | "identical_rates"
  | "insufficient_data"
  | "no_reference_group";

export interface FairnessCrossGroupMetric {
  metric_name: string;
  metric_label: string;
  value: number | null;
  reference_group: string | null;
  groups_compared: string[];
  metric_status: FairnessCrossGroupMetricStatus;
  status_reason: string | null;
}

export interface FairnessCoverage {
  group_dimension: string;
  attribute_source: string;
  attributes_inferred: boolean;
  population: number;
  candidates_with_demographic: number;
  candidates_missing_demographic: number;
  demographic_coverage_pct: number;
  minimum_group_size: number;
  positive_outcome_threshold: number;
}

export interface FairnessGroupAnalysis {
  metric_status: string;
  status_reason: string | null;
  reference_group: string | null;
  coverage: FairnessCoverage;
  group_outcomes: FairnessGroupOutcome[];
  cross_group_metrics: FairnessCrossGroupMetric[];
  methodology: string;
  grouping_note: string;
}

export interface FairnessAlertView {
  type: string;
  severity: string;
  message: string;
  recommendation: string;
}

export interface FairnessFinding {
  term: string;
  category: string;
  suggestion: string;
}

export interface FairnessSuggestion {
  category: string;
  suggestion: string;
  priority: string;
}

export interface JobDescriptionBiasView {
  job_id: string;
  bias_score: number;
  overall_assessment: string;
  total_issues: number;
  issue_counts: Record<string, number>;
  findings: FairnessFinding[];
  suggestions: FairnessSuggestion[];
  note: string;
}

export interface AdversarialContextView {
  status: "no_stored_result";
  tested: boolean;
  stability_score: number | null;
  sensitivity: string | null;
  reason: string;
  run_on_demand_endpoint: string;
}

export interface ApplicationFairnessContext {
  application: FairnessContextApplication;
  job: FairnessContextJob;
  screening_state: FairnessScreeningState;
  population: FairnessPopulation;
  sections: Record<string, FairnessSection>;
  score_distribution: FairnessScoreDistribution | null;
  group_analysis: FairnessGroupAnalysis | null;
  alerts: FairnessAlertView[];
  job_description_bias: JobDescriptionBiasView | null;
  adversarial: AdversarialContextView;
  limitations: string[];
  disclaimer: string;
}