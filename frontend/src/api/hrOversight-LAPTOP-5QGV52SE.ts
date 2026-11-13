import apiClient from "./client";

/**
 * Revised Phase 14 -- HR organization-level oversight.
 *
 * These types mirror the backend contracts in
 * ``app/domain/hr_oversight_schemas.py``. The HR surface is read-only and
 * organization-scoped: there are no POST/PATCH/DELETE helpers here by design,
 * because hiring-state writes belong to the recruiter.
 *
 * `is_platform_scope` matters: when it is true the numbers cover every
 * organization (platform admin only), and the UI labels them as such instead of
 * presenting them as the viewer's own org.
 */

export interface HROverviewCounts {
  open_positions: number;
  total_applications: number;
  distinct_candidates: number;
  distinct_recruiters: number;
  shortlisted: number;
  interview_scheduled: number;
  interview_scheduled_total: number;
  /** Attempts still in `assigned` state only -- not an all-status total. */
  assessments_assigned: number;
  /** Every assessment attempt in scope, whatever its status. */
  assessment_attempts: number;
  selected: number;
  offered: number;
  rejected: number;
  hired: number;
  withdrawn: number;
}

export interface HROverview {
  organization_ids: string[];
  is_platform_scope: boolean;
  counts: HROverviewCounts;
  applications_by_status: Record<string, number>;
  interviews_by_status: Record<string, number>;
  assessments_by_status: Record<string, number>;
}

export interface HRJobSummary {
  id: string;
  title: string;
  company: string;
  department: string | null;
  location: string | null;
  status: string;
  organization_id: string | null;
  recruiter_id: string;
  recruiter_name: string | null;
  created_at: string | null;
  application_count: number;
  applications_by_status: Record<string, number>;
  hired_count: number;
  open_application_count: number;
}

export interface HRJobList {
  is_platform_scope: boolean;
  total: number;
  jobs: HRJobSummary[];
}

export interface HRApplicationSummary {
  id: string;
  job_id: string;
  job_title: string | null;
  candidate_id: string;
  candidate_name: string;
  status: string;
  is_terminal: boolean;
  screening_status: string | null;
  applied_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
  recruiter_id: string;
  recruiter_name: string | null;
  has_interview: boolean;
  has_assessment: boolean;
}

export interface HRApplicationList {
  job_id: string;
  /** The funnel stage that was applied, or null when unfiltered. */
  status_filter: string | null;
  total: number;
  applications: HRApplicationSummary[];
}

export interface HRRecruiterSummary {
  id: string;
  full_name: string;
  email: string | null;
  is_active: boolean;
  open_job_count: number;
  total_job_count: number;
  application_count: number;
  open_application_count: number;
  applications_by_status: Record<string, number>;
  hired_count: number;
  /**
   * Share of applications the recruiter actually acted on. `null` means there
   * were no applications at all, which is not the same as a 0% rate -- the UI
   * must say "no applications" rather than print a number.
   */
  advancement_rate: number | null;
  job_ids: string[];
}

export interface HRRecruiterList {
  is_platform_scope: boolean;
  total: number;
  recruiters: HRRecruiterSummary[];
}

export interface HRRecruiterDetail {
  recruiter: HRRecruiterSummary;
  jobs: HRJobSummary[];
}

/**
 * One deterministic "needs a human look" item.
 *
 * `rule` and `reason` say which condition fired and what was measured, so the
 * screen can explain itself. `measured_value` / `threshold_value` are present
 * for the numeric rules and null for the rest. Nothing here decides anything:
 * a flagged row is a review trigger, and the recruiter write surface is the
 * only thing that can change an application.
 */
export interface HRAttentionItem {
  rule: string;
  severity: string;
  reason: string;
  subject_type: string;
  subject_id: string | null;
  job_id: string | null;
  application_id: string | null;
  recruiter_id: string | null;
  job_title: string | null;
  recruiter_name: string | null;
  status: string | null;
  measured_value: number | null;
  threshold_value: number | null;
}

export interface HRAttention {
  is_platform_scope: boolean;
  /** The thresholds the backend actually applied, echoed for transparency. */
  thresholds: Record<string, number>;
  /** How many items qualified, before the cap. */
  total_flagged: number;
  items: HRAttentionItem[];
  /** True when the cap dropped qualifying items. */
  truncated: boolean;
}

export interface HRQualityCoverage {
  total_applications: number;
  screening_by_status: Record<string, number>;
  screening_rate: number | null;
  interview_rate: number | null;
  decision_rate: number | null;
  hire_rate: number | null;
}

export interface HRFairnessAlert {
  job_id: string | null;
  job_title: string | null;
  metric: string;
  observed_value: number;
  threshold_value: number;
  detail: string | null;
}

export interface HRHiringQuality {
  is_platform_scope: boolean;
  organization_ids: string[];
  coverage: HRQualityCoverage;
  fairness_alerts: HRFairnessAlert[];
  fairness_gap_threshold: number;
}

export interface HRStageJobCount {
  job_id: string;
  job_title: string;
  recruiter_id: string;
  recruiter_name: string | null;
  count: number;
}

/**
 * The records behind one overview funnel bar, grouped by job.
 *
 * The overview funnel is organization-wide, so a single stage can stand for
 * thousands of applications across many jobs. The backend groups them instead
 * of flattening them, and each `HRStageJobCount` links to that job's
 * stage-filtered application list.
 */
export interface HRStageDrilldown {
  status: string;
  total: number;
  jobs: HRStageJobCount[];
}

/**
 * The candidate projection is intentionally narrow. The backend sends only
 * these six fields, and the UI must not expect roles, memberships, a resume
 * body or the cover-letter text.
 */
export interface HRCandidateView {
  id: string;
  full_name: string;
  email: string | null;
  is_active: boolean;
  account_status: string | null;
  has_resume: boolean;
}

export interface HRDecisionView {
  status: string;
  is_terminal: boolean;
  decision_reason: string | null;
  decision_reason_code: string | null;
  decision_comment: string | null;
  decided_at: string | null;
  decided_by: string | null;
  decided_by_name: string | null;
}

export interface HRScreeningSummary {
  status: string;
  attempts: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface HRTimelineEvent {
  id: string;
  /** "status_history" | "interview" | "assessment" -- never synthesized. */
  source: string;
  event: string;
  at: string | null;
  from_status: string | null;
  to_status: string | null;
  actor_id: string | null;
  actor_name: string | null;
  detail: string | null;
}

export interface HRApplicationDetail {
  id: string;
  status: string;
  is_terminal: boolean;
  job: HRJobSummary;
  candidate: HRCandidateView;
  decision: HRDecisionView;
  screening: HRScreeningSummary;
  applied_at: string | null;
  cover_letter_available: boolean;
  /** Reused recruiter explainability projection, or null when unavailable. */
  explainability: Record<string, unknown> | null;
  /** Reused fairness context, or null when the cohort is too small. */
  fairness: Record<string, unknown> | null;
  /** Reused Phase 11 interview evidence, or null when unscheduled. */
  interview: Record<string, unknown> | null;
  /** Reused Phase 12 assessment evidence, or null when unavailable. */
  assessment: Record<string, unknown> | null;
  timeline: HRTimelineEvent[];
}

export const hrApi = {
  /** One request for the whole overview -- no per-card waterfall. */
  getOverview: () =>
    apiClient.get<HROverview>("/hr/overview").then((r) => r.data),

  /** Jobs with their real application funnel already attached. */
  getJobs: () => apiClient.get<HRJobList>("/hr/jobs").then((r) => r.data),

  /**
   * Applications for one job, optionally narrowed to a single funnel stage so
   * the clickable pipeline can drill into one bar. The backend checks access
   * to that job, so this cannot read another organization's applications, and
   * an unrecognised stage matches nothing rather than widening back to all.
   */
  getJobApplications: (jobId: string, status?: string) =>
    apiClient
      .get<HRApplicationList>(`/hr/jobs/${jobId}/applications`, {
        params: status ? { status } : undefined,
      })
      .then((r) => r.data),

  /** Employers in scope, rolled up with their real funnel. */
  getRecruiters: () =>
    apiClient.get<HRRecruiterList>("/hr/recruiters").then((r) => r.data),

  /** One recruiter plus the jobs behind their aggregate. */
  getRecruiter: (recruiterId: string) =>
    apiClient
      .get<HRRecruiterDetail>(`/hr/recruiters/${recruiterId}`)
      .then((r) => r.data),

  /** Deterministic review triggers with the thresholds that produced them. */
  getAttention: () =>
    apiClient.get<HRAttention>("/hr/attention").then((r) => r.data),

  /** Organization-scoped coverage of the existing quality signals. */
  getHiringQuality: () =>
    apiClient.get<HRHiringQuality>("/hr/quality").then((r) => r.data),

  /** Which jobs hold the applications in one funnel stage, for the overview. */
  getStageDrilldown: (status: string) =>
    apiClient
      .get<HRStageDrilldown>(`/hr/pipeline/${status}`)
      .then((r) => r.data),

  /** Full drill-down in a single call: evidence blocks + composed timeline. */
  getApplicationDetail: (applicationId: string) =>
    apiClient
      .get<HRApplicationDetail>(`/hr/applications/${applicationId}`)
      .then((r) => r.data),
};
