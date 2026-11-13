/**
 * Phase 1: job-scoped, candidate-specific bulk assessment assignment.
 *
 * The single-application panel (`ApplicationAssessmentPanel`) assigns one
 * assessment to one applicant. This is the batch counterpart: a recruiter opens
 * one job, ticks several of *that job's* applicants, picks one assessment and
 * assigns it to all of them in a single request.
 *
 * Everything below mirrors the backend contract at
 * `/recruiter/jobs/{job_id}/assessments/*`. The two properties that matter and
 * are not negotiable from this side:
 *
 * 1. **Partial success, reported per candidate.** One ineligible applicant
 *    (not yet shortlisted, already final, out of attempts) never fails the batch;
 *    every requested application gets one `outcome` row so the UI can tell the
 *    recruiter exactly who was assigned and, for the rest, why not.
 * 2. **The job in the path is the only scope.** The request carries application
 *    ids and an assessment id and nothing else; the job, candidate and recruiter
 *    are derived server-side, so a body that names a participant is rejected.
 */

import type { AssignableAssessment } from "./applicationAssessment";
import type { AssessmentSectionConfig } from "./assessment";

/**
 * One candidate's outcome in a batch.
 *
 * `already_assigned` is a success from the recruiter's point of view but wrote
 * nothing, which is exactly the distinction a retried request or a double-click
 * turns on, so it is reported separately from a fresh `assigned`.
 */
export type JobAssessmentOutcome = "assigned" | "already_assigned" | "skipped";

/**
 * Why a candidate was skipped.
 *
 * A controlled vocabulary from the server, not a prose message: the panel maps
 * these to sentences so the reason survives a copy change and can be asserted in
 * tests. `not_an_applicant` means the application id did not belong to this job;
 * the server deliberately does not disclose whether it exists elsewhere.
 */
export type JobAssessmentSkipReason =
  | "not_an_applicant"
  | "application_is_final"
  | "application_not_assessable"
  | "no_attempts_remaining";

/** Human explanations for the controlled `JobAssessmentSkipReason` codes. */
export const JOB_ASSESSMENT_SKIP_LABELS: Record<JobAssessmentSkipReason, string> = {
  not_an_applicant: "This candidate has not applied to this job",
  application_is_final: "The application has reached a final outcome",
  application_not_assessable:
    "The candidate must be shortlisted before an assessment can be assigned",
  no_attempts_remaining:
    "The candidate has used every allowed attempt for this assessment",
};

/** Human labels for a batch outcome. */
export const JOB_ASSESSMENT_OUTCOME_LABELS: Record<JobAssessmentOutcome, string> = {
  assigned: "Assigned",
  already_assigned: "Already assigned",
  skipped: "Skipped",
};

/** Badge colours for a batch outcome, matching the platform's palette. */
export const JOB_ASSESSMENT_OUTCOME_COLORS: Record<JobAssessmentOutcome, string> = {
  assigned: "bg-green-100 text-green-800",
  already_assigned: "bg-blue-100 text-blue-800",
  skipped: "bg-gray-100 text-gray-700",
};

/**
 * The assessments a recruiter may assign to a job's applicants.
 *
 * Job-scoped counterpart of `ApplicationAssessmentOptions`. There is no single
 * `can_assign` flag: eligibility is per candidate, so it is reported per row in
 * the assignment result rather than guessed at the job level here.
 */
export interface JobAssessmentOptions {
  job_id: string;
  job_title: string;
  available: AssignableAssessment[];
}

/** The outcome for one requested candidate in a batch. */
export interface JobAssessmentAssignItem {
  application_id: string;
  /** Absent for a `not_an_applicant` row, where the id could not be attributed. */
  candidate_id: string | null;
  candidate_name: string | null;
  outcome: JobAssessmentOutcome;
  reason: JobAssessmentSkipReason | null;
  attempt_id: string | null;
  assessment_id: string;
  assessment_title: string;
  scheduled_for: string | null;
  assessment_link: string | null;
  message: string;
}

/** Outcome of a batch assignment: counts plus one row per candidate. */
export interface JobAssessmentAssignResult {
  job_id: string;
  job_title: string;
  assessment_id: string;
  assessment_title: string;
  /** True when this request authored a new assessment (create-and-assign path). */
  created_new_assessment: boolean;
  requested_count: number;
  assigned_count: number;
  already_assigned_count: number;
  skipped_count: number;
  items: JobAssessmentAssignItem[];
}

/**
 * Assign an existing assessment to several of one job's applicants.
 *
 * `application_ids` is deliberately a list so the response can be correlated with
 * what was sent, but the server de-duplicates it: naming the same application
 * twice is one attempt, not two.
 */
export interface JobAssessmentAssignRequest {
  assessment_id: string;
  application_ids: string[];
  /** When the candidate is expected to take it; omit for "waiting". */
  scheduled_for?: string;
}

/**
 * Author one assessment for a job and assign it to several applicants in one
 * action.
 *
 * Carries authored content only — no `job_id`/`candidate_id`/`recruiter_id`. The
 * server derives the job from the path and uses it as the assessment's `job_id`,
 * so the authored assessment is scoped to exactly this role.
 */
export interface JobAssessmentCreateAndAssignRequest {
  title: string;
  description?: string | null;
  mode?: string;
  duration_minutes?: number;
  sections: AssessmentSectionConfig[];
  passing_score?: number;
  negative_marking?: number;
  allowed_attempts?: number;
  adaptive?: boolean;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
  scheduled_for?: string | null;
  application_ids: string[];
}
