// Phase 12 – Assessment Platform types

export interface AssessmentSectionConfig {
  question_type: string;
  count: number;
  skills?: string[];
  difficulty?: string;
  time_limit_seconds?: number | null;
  points_per_question?: number;
}

export interface AssessmentCreateRequest {
  title: string;
  description?: string | null;
  job_id?: string | null;
  mode?: string;
  duration_minutes?: number;
  sections: AssessmentSectionConfig[];
  passing_score?: number;
  negative_marking?: number;
  allowed_attempts?: number;
  adaptive?: boolean;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
}

export interface QuestionPublic {
  id: string;
  question_type: string;
  skill: string;
  topic: string;
  difficulty: string;
  question_text: string;
  options: string[];
  code_snippet: string | null;
  language: string | null;
  starter_code: string | null;
  tables: unknown[] | null;
  schema_sql: string | null;
  estimated_time_seconds: number;
  points: number;
  section: string;
  order_index: number;
}

export interface AssessmentResponse {
  id: string;
  title: string;
  description: string | null;
  job_id: string | null;
  job_title: string | null;
  mode: string;
  status: string;
  duration_minutes: number;
  passing_score: number;
  negative_marking: number;
  allowed_attempts: number;
  adaptive: boolean;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  created_by: string | null;
  question_count: number;
  attempt_count: number;
  created_at: string | null;
}

export interface AttemptStartResponse {
  attempt_id: string;
  assessment_id: string;
  status: string;
  started_at: string | null;
  expires_at: string | null;
  total_questions: number;
  instructions: string[];
  sections: string[];
}

export interface AttemptState {
  attempt_id: string;
  status: string;
  expires_at: string | null;
  duration_minutes: number;
  questions: QuestionPublic[];
  answered: Record<string, AnsweredEntry>;
}

export interface AnsweredEntry {
  answer_data?: Record<string, unknown>;
  is_correct?: boolean | null;
  score_awarded?: number;
}

export interface Evaluation {
  score: number;
  is_correct: boolean | null;
  feedback: string | null;
  dimensions: Record<string, unknown> | null;
}

export interface AnswerResultResponse {
  answer_id: string;
  evaluation: Evaluation;
  correct_answer_revealed: boolean;
  explanation: string | null;
  next_question: QuestionPublic | null;
  questions_remaining: number;
  progress: { answered: number; total: number };
}

export interface CodeRunResponse {
  ok: boolean;
  stdout: string;
  stderr: string;
  execution_time_ms: number;
  passed_count: number;
  total_count: number;
  timed_out: boolean;
  sandbox_mode: string;
}

export interface SectionScore {
  section: string;
  question_type: string;
  earned: number;
  possible: number;
  percentage: number;
  accuracy: number | null;
}

export interface PerQuestionEntry {
  question_id: string;
  type: string;
  skill: string;
  difficulty: string;
  score_pct: number;
  is_correct: boolean | null;
  time_seconds: number | null;
}

export interface ResultResponse {
  attempt_id: string;
  assessment_id: string;
  candidate_id: string;
  status: string;
  submitted_at: string | null;
  overall_score: number;
  passing_score: number;
  passed: boolean;
  section_scores: SectionScore[];
  skill_scores: Record<string, number>;
  strong_skills: string[];
  weak_skills: string[];
  recommended_topics: string[];
  accuracy: number;
  time_management: number;
  readiness_level: string;
  recommendation: string;
  ai_summary: string | null;
  integrity_flags: number;
  per_question: PerQuestionEntry[];
}

export interface AttemptListItem {
  attempt_id: string;
  assessment_id: string;
  application_id: string | null;
  assessment_title: string;
  mode: string;
  status: string;
  /** When the recruiter assigned it. Null for a self-started attempt. */
  scheduled_at: string | null;
  /** Take link returned by the API, so page and notification agree. */
  assessment_link: string | null;
  /** Job the assignment belongs to, when it came from an application. */
  job_title: string | null;
  started_at: string | null;
  expires_at: string | null;
  submitted_at: string | null;
  overall_score: number | null;
  passed: boolean | null;
}

export interface QuestionAccuracyRow {
  question_id: string;
  topic: string;
  type: string;
  accuracy: number;
  responses: number;
}

export interface CandidateComparisonRow {
  candidate_id: string;
  candidate_name: string;
  attempts: number;
  best_score: number;
  latest_score: number;
  recommendation: string;
}

export interface AnalyticsResponse {
  assessment_id: string;
  title: string;
  total_assigned: number;
  completed: number;
  in_progress: number;
  completion_rate: number;
  average_score: number;
  pass_rate: number;
  median_time_minutes: number;
  skill_performance: Record<string, number>;
  question_accuracy: QuestionAccuracyRow[];
  difficulty_performance: Record<string, number>;
  coding_success_rate: number;
  candidates: CandidateComparisonRow[];
}
