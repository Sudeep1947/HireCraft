/**
 * Phase 12: types for running an assessment *from an application*.
 *
 * An assessment is reached through an application, so everything below is keyed
 * by `application_id` and never by job, candidate or recruiter. The server
 * derives the participants from the authorized application; a UI that implied it
 * could choose them would be lying to the recruiter.
 *
 * Two properties are load-bearing and are not negotiable from this side:
 *
 * 1. **The server owns availability.** `ApplicationAssessmentOptions` is the
 *    single source of truth for whether an assignment is allowed and why not, so
 *    a control the UI offers is one the API will accept, and one the API would
 *    refuse is never offered.
 * 2. **A result is evidence, not a verdict.** `passed` reports the assessment's
 *    own configured threshold. It says nothing about hiring, and the copy that
 *    renders it must keep saying so — the recruiter's decision is the only thing
 *    that advances or ends an application.
 */

import type { ApplicationStatus } from "./interview";

/**
 * The attempt lifecycle.
 *
 * Mirrors the backend `AttemptStatus` enum. `assigned` is the pre-existing status
 * a recruiter-created attempt is created in; the candidate starts it, which moves
 * it to `in_progress`. The last three are terminal.
 */
export type AttemptStatus =
  | "assigned"
  | "in_progress"
  | "completed"
  | "expired"
  | "abandoned";

/** Mirrors the backend `AssessmentMode` enum. */
export type AssessmentMode =
  | "quick_test"
  | "technical"
  | "aptitude"
  | "coding"
  | "full_technical_interview"
  | "campus_placement"
  | "experienced_developer"
  | "system_design"
  | "custom";

/**
 * Why an action is unavailable.
 *
 * A controlled vocabulary from the server, not a message: the panel shows a human
 * explanation mapped from these codes, so the reason a button is disabled
 * survives a copy change and can be asserted in tests.
 */
export type AssessmentActionReason =
  | "application_is_final"
  | "application_not_assessable"
  | "assessment_already_assigned"
  | "assessment_already_finished"
  | "assessment_unavailable"
  | "no_attempts_remaining";

/** Explanations for the controlled `AssessmentActionReason` codes. */
export const ASSESSMENT_REASON_LABELS: Record<AssessmentActionReason, string> = {
  application_is_final: "This application has reached a final outcome",
  application_not_assessable:
    "An assessment can only be assigned to a shortlisted application",
  assessment_already_assigned:
    "This assessment is already assigned to the application",
  assessment_already_finished: "This attempt has already finished",
  assessment_unavailable: "This assessment is not available to assign",
  no_attempts_remaining:
    "This candidate has used every allowed attempt for this assessment",
};

/** Human labels for the attempt lifecycle. */
export const ATTEMPT_STATUS_LABELS: Record<AttemptStatus, string> = {
  assigned: "Assigned",
  in_progress: "In progress",
  completed: "Completed",
  expired: "Expired",
  abandoned: "Closed",
};

/** Human labels for an assessment mode. */
export const ASSESSMENT_MODE_LABELS: Record<AssessmentMode, string> = {
  quick_test: "Quick test",
  technical: "Technical",
  aptitude: "Aptitude",
  coding: "Coding",
  full_technical_interview: "Full technical interview",
  campus_placement: "Campus placement",
  experienced_developer: "Experienced developer",
  system_design: "System design",
  custom: "Custom",
};

/** Badge colours for the attempt lifecycle, matching the interview panel's. */
export const ATTEMPT_STATUS_COLORS: Record<AttemptStatus, string> = {
  assigned: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  expired: "bg-amber-100 text-amber-700",
  abandoned: "bg-gray-100 text-gray-500",
};

/**
 * One entry of the catalog a recruiter may assign to this application.
 *
 * Every field is read from an existing assessment row; nothing is invented to fill
 * the UI. `question_count` is the real count of generated questions and `skills`
 * the distinct skills those questions exercise, so a recruiter sees what the
 * assessment actually contains rather than a label.
 */
export interface AssignableAssessment {
  assessment_id: string;
  title: string;
  description: string | null;
  mode: AssessmentMode;
  status: string;
  duration_minutes: number;
  question_count: number;
  passing_score: number;
  allowed_attempts: number;
  adaptive: boolean;
  skills: string[];
  /**
   * True when this assessment is already live on this application, so the UI can
   * show it as current rather than offering a duplicate assignment.
   *
   * Note that the server reports a real `question_count` of 0 for these: the
   * catalog query that aggregates counts deliberately excludes an assessment
   * that already has a live attempt, and the recruiter gets the authoritative
   * numbers from the evidence list instead. The UI does not paper over the zero.
   */
  already_assigned: boolean;
}

/** What may be done to one assigned attempt. */
export interface ApplicationAssessmentAttemptAction {
  attempt_id: string;
  status: AttemptStatus;
  /**
   * A finished attempt is immutable: its answers and result are evidence, so
   * reopening one would rewrite history. A retake is a *new* attempt.
   */
  can_reassign: boolean;
  reassign_unavailable_reason: AssessmentActionReason | null;
}

export interface ApplicationAssessmentOptions {
  application_id: string;
  current_status: ApplicationStatus;
  status_is_final: boolean;
  can_assign: boolean;
  assign_unavailable_reason: AssessmentActionReason | null;
  has_assessments: boolean;
  attempt_count: number;
  /**
   * Assessments this recruiter may assign to this application, already filtered by
   * organization access. Empty when none are reachable, which is a real answer and
   * not a reason to fall back to an unscoped list.
   */
  available: AssignableAssessment[];
  actions: ApplicationAssessmentAttemptAction[];
}

/** One section's score, as the platform's grading engine recorded it. */
export interface ApplicationAssessmentSectionScore {
  section?: string;
  question_type?: string;
  earned?: number;
  possible?: number;
  percentage?: number;
  accuracy?: number | null;
  [key: string]: unknown;
}

/**
 * One attempt, as evidence on the application.
 *
 * `overall_score`, `passed` and `passed_threshold` describe the assessment's own
 * configured threshold. They are not a hiring signal and must not be presented as
 * one.
 */
export interface ApplicationAssessmentSummary {
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  mode: AssessmentMode;
  status: AttemptStatus;
  attempt_number: number;
  /** When the recruiter assigned it. Not a deadline — the attempt has none. */
  scheduled_for_hint: string | null;
  started_at: string | null;
  expires_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  questions_total: number;
  questions_answered: number;
  /**
   * Null until the attempt is graded. Never defaulted to 0: an ungraded attempt
   * and a scored zero are very different facts and must not look alike.
   */
  overall_score: number | null;
  passed_threshold: number | null;
  /** Null when there is no result yet, or when the assessment has no threshold. */
  passed: boolean | null;
  section_scores: ApplicationAssessmentSectionScore[];
  strong_skills: string[];
  weak_skills: string[];
  recommended_topics: string[];
  accuracy: number | null;
  time_management: number | null;
  /**
   * The platform's own deterministic summary, formatted from the authoritative
   * score, so it cannot disagree with it.
   */
  summary_text: string | null;
  /**
   * Count only. The individual events can contain detail a recruiter should read
   * deliberately, so the count is what the application view carries.
   */
  integrity_flag_count: number;
}

/** All assessment evidence for one application. Staff-only. */
export interface ApplicationAssessmentEvidence {
  application_id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  application_status: ApplicationStatus;
  attempt_count: number;
  completed_count: number;
  /**
   * Averaged over completed attempts only, so an attempt nobody has finished
   * cannot drag the figure down. Null until one is completed.
   */
  average_overall_score: number | null;
  attempts: ApplicationAssessmentSummary[];
}

/**
 * Outcome of an assignment.
 *
 * `already_assigned` makes the endpoint idempotent in the sense that matters: a
 * double-click or a retried request re-reads the existing assignment and reports
 * it instead of creating a second live attempt for one application.
 */
export interface ApplicationAssessmentAssignResult {
  application_id: string;
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  attempt_status: AttemptStatus;
  already_assigned: boolean;
  message: string;
}

/**
 * The candidate's view of the assessment on their application.
 *
 * An explicit allowlist. It carries what the candidate needs in order to start and
 * what they are entitled to see afterwards, and deliberately has no recruiter
 * identity, recruiter notes, other candidates' results, protected attributes,
 * internal fairness calculations, internal hiring thresholds, or the platform's
 * private `recommendation`/`readiness_level` grading labels, which read as a
 * hiring verdict and are the recruiter's to reach.
 */
export interface CandidateApplicationAssessmentView {
  application_id: string;
  attempt_id: string | null;
  assessment_id: string | null;
  assessment_title: string | null;
  status: AttemptStatus | null;
  attempt_number: number | null;
  /** Job the assessment was assigned for, when attached to an application. */
  job_id: string | null;
  job_title: string | null;
  /** When the recruiter assigned it. Not a deadline. */
  scheduled_at: string | null;
  /** Take link returned by the API so page and notification agree. */
  assessment_link: string | null;
  has_assessment: boolean;
  /**
   * True once at least one attempt on this application reached a finished state,
   * so the UI can say the assessment is done even after a later retake.
   */
  has_completed: boolean;
  completed_count: number;
  attempt_count: number;
  /** Whether this attempt can still be started. Drives the single call to action. */
  can_start: boolean;
  /** True when the candidate may resume an attempt already in progress. */
  can_continue: boolean;
  expires_at: string | null;
  submitted_at: string | null;
  overall_score: number | null;
  strong_skills: string[];
  recommended_topics: string[];
  summary_text: string | null;
  message: string | null;
}

/**
 * Assign an assessment to an application.
 *
 * `assessment_id` and nothing else. The job, candidate and organization are all
 * derived from the application, so a client cannot aim an assessment at a
 * different candidate or another tenant's job — the server rejects a body that
 * carries anything extra.
 */
export interface ApplicationAssessmentAssignRequest {
  assessment_id: string;
  /**
   * When the recruiter wants this assessment to happen, as an ISO-8601 instant.
   *
   * Optional, and about *when* rather than *who*: omit it and the assessment is
   * simply waiting for the candidate, which is what every caller did before the
   * schedule existed. Never defaulted client-side either, because a "now" we
   * invented could not be told apart from a time the recruiter actually chose.
   */
  scheduled_for?: string;
}

export interface ApplicationAssessmentCreateRequest {
  title: string;
  description?: string | null;
  mode?: string;
  duration_minutes?: number;
  sections: Array<{
    question_type: string;
    count: number;
    skills?: string[];
    difficulty?: string;
    time_limit_seconds?: number | null;
    points_per_question?: number;
  }>;
  passing_score?: number;
  negative_marking?: number;
  allowed_attempts?: number;
  adaptive?: boolean;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
  scheduled_for?: string | null;
}

export interface ApplicationAssessmentCreateResult {
  application_id: string;
  job_id: string;
  candidate_id: string;
  recruiter_id: string;
  assessment_id: string;
  assessment_title: string;
  question_count: number;
  created_new_assessment: boolean;
  assignment: ApplicationAssessmentAssignResult;
}
