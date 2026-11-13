import type { CandidateApplicationDecision } from "./applicationDecision";
import type { CandidateApplicationInterviewView } from "./interview";
import type {
  HiringRecommendation,
  ScreeningResult,
  StrengthLevel,
} from "./screening";

export interface Job {
  id: string;
  recruiter_id: string;
  title: string;
  company: string;
  department: string | null;
  employment_type: string;
  experience_required: string | null;
  education_required: string | null;
  required_skills: string[];
  preferred_skills: string[] | null;
  location: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  description: string;
  benefits: string | null;
  application_deadline: string | null;
  status: string;
  is_archived: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface JobListItem {
  id: string;
  recruiter_id: string;
  title: string;
  company: string;
  department: string | null;
  employment_type: string;
  location: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  status: string;
  application_deadline: string | null;
  application_count: number;
  created_at: string;
  updated_at: string;
}

export interface JobFormData {
  title: string;
  company: string;
  department?: string;
  employment_type: string;
  experience_required?: string;
  education_required?: string;
  required_skills: string[];
  preferred_skills: string[];
  location: string;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string;
  description: string;
  benefits?: string;
  application_deadline?: string | null;
  status?: string;
}

export interface JobApplication {
  id: string;
  job_id: string;
  candidate_id: string;
  resume_id: string | null;
  cover_letter: string | null;
  status: string;
  screening_status?: string;
  screening_error?: string | null;
  screening_completed_at?: string | null;
  created_at: string;
  updated_at: string;
  candidate_name?: string;
  candidate_email?: string;
  job_title?: string;
  company?: string;
  location?: string;
  employment_type?: string;
  recruiter_notes?: RecruiterNote[];
}

export interface RecruiterNote {
  id: string;
  job_application_id: string;
  recruiter_id: string;
  note: string;
  created_at: string;
  updated_at: string;
}

/**
 * Phase 9 candidate tracking contracts. These mirror the backend Pydantic
 * schemas in `app/domain/application_tracking_schemas.py`.
 *
 * `reached` and the timeline are driven entirely by the recorded
 * `ApplicationStatusHistory` rows, and `can_withdraw` is resolved server-side
 * from the same transition map the write path enforces, so this UI never
 * re-implements the lifecycle.
 */
export interface CandidateApplicationStage {
  status: string;
  status_label: string;
  /** True only when a history row exists for this status. */
  reached: boolean;
  is_current: boolean;
}

export interface CandidateApplicationTimelineEvent {
  status: string;
  status_label: string;
  from_status: string | null;
  occurred_at: string;
  is_current: boolean;
  message: string | null;
}

export interface CandidateApplicationTrack {
  application_id: string;
  job_id: string;
  job_title: string;
  company: string;
  location: string;
  employment_type: string;
  status: string;
  status_label: string;
  is_decision_final: boolean;
  can_withdraw: boolean;
  applied_at: string;
  last_status_change_at: string | null;
  decided_at: string | null;
  status_changed: boolean;
  screening_status: string;
  screening_completed_at: string | null;
  has_match_explanation: boolean;
  decision: CandidateApplicationDecision | null;
  stages: CandidateApplicationStage[];
  timeline: CandidateApplicationTimelineEvent[];
  /**
   * The candidate's own interview, or null when none is linked.
   *
   * An allowlist: no scorecard, recommendation, evaluation, notes or recruiter
   * identity. It carries what the candidate needs to attend, and nothing about
   * how they were judged.
   */
  interview: CandidateApplicationInterviewView | null;
}

export type ApplicantScreeningStatus =
  | "not_started"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export type ApplicantDashboardSort =
  | "created_at"
  | "-created_at"
  | "overall_match_score"
  | "-overall_match_score"
  | "candidate_name"
  | "-candidate_name"
  | "status"
  | "-status";

export interface ApplicantDashboardItem extends JobApplication {
  effective_screening_status: ApplicantScreeningStatus;
  screening_attempts: number;
  screening_task_id: string | null;
  screening_started_at: string | null;
  screening_result: ScreeningResult | null;
  overall_match_score: number | null;
  recommendation: HiringRecommendation | null;
  strength_level: StrengthLevel | null;
  decision_reason: string | null;
  decision_comment: string | null;
  decided_at: string | null;
}

export interface ApplicantSummary {
  job_id: string;
  total_applicants: number;
  total_screened: number;
  not_screened: number;
  queued: number;
  running: number;
  failed: number;
  skipped: number;
  average_score: number | null;
  high_match_count: number;
  status_breakdown: Record<string, number>;
  application_status_breakdown: Record<string, number>;
  screening_status_breakdown: Record<string, number>;
  recommendation_breakdown: Record<string, number>;
  strength_level_breakdown: Record<string, number>;
}

export interface ApplicantDashboardQuery {
  q?: string;
  application_status?: string;
  screening_status?: ApplicantScreeningStatus;
  recommendation?: HiringRecommendation;
  min_score?: number;
  max_score?: number;
  sort_by?: ApplicantDashboardSort;
  page?: number;
  page_size?: number;
}

export interface ApplicantDashboardResponse {
  job: Job;
  items: ApplicantDashboardItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  summary: ApplicantSummary;
}

export interface SavedJob {
  job_id: string;
  created_at: string;
}

export interface JobSearchResult {
  items: JobListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RecruiterDashboard {
  total_jobs: number;
  published_jobs: number;
  draft_jobs: number;
  closed_jobs: number;
  total_applications: number;
  recent_applications: RecentApplication[];
}

export interface RecentApplication {
  id: string;
  job_title: string;
  candidate_name: string;
  status: string;
  created_at: string;
}

export interface CandidateJobDashboard {
  total_applications: number;
  saved_jobs: number;
  status_breakdown: Record<string, number>;
  recent_applications: {
    id: string;
    job_id: string;
    status: string;
    created_at: string;
  }[];
}
