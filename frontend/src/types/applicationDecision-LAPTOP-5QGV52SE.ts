/**
 * Phase 8 recruiter decision contracts.
 *
 * These mirror the backend Pydantic schemas in
 * `app/domain/application_decision_schemas.py`. The decision vocabulary and the
 * candidate-facing reason text are delivered by the API, so the UI never
 * hardcodes which transitions are legal or what a candidate will be told.
 */

export type ApplicationDecisionType =
  | "keep_under_review"
  | "shortlist"
  | "reject"
  /**
   * Phase 13: the explicit positive decision. It is a separate outcome from
   * being hired, so the type is spelled out rather than folded into an
   * existing value.
   */
  | "select";

export type RejectionReasonValue =
  | "missing_required_skill"
  | "insufficient_experience"
  | "education_requirement"
  | "low_job_match"
  | "failed_assessment"
  | "failed_interview"
  | "position_filled"
  | "other";

export interface RejectionReasonOption {
  value: RejectionReasonValue;
  label: string;
  /** Exactly the wording the candidate will be shown. */
  candidate_message: string;
}

export interface ApplicationDecisionOption {
  decision: ApplicationDecisionType;
  label: string;
  description: string;
  target_status: string;
  requires_rejection_reason: boolean;
  available: boolean;
  unavailable_reason: string | null;
  /**
   * Phase 13: the exact candidate-facing wording this decision would send, so
   * the confirmation step previews real text instead of a client-side guess.
   * `null` when the wording depends on a reason that has not been chosen yet.
   */
  candidate_message?: string | null;
}

export interface ApplicationDecisionOptions {
  application_id: string;
  current_status: string;
  status_is_final: boolean;
  options: ApplicationDecisionOption[];
  rejection_reasons: RejectionReasonOption[];
}

export interface ApplicationDecisionResult {
  application_id: string;
  decision: ApplicationDecisionType;
  previous_status: string;
  status: string;
  changed_status: boolean;
  rejection_reason: RejectionReasonValue | null;
  rejection_reason_label: string | null;
  internal_note: string | null;
  candidate_status_label: string;
  candidate_message: string | null;
  decided_at: string | null;
  decided_by: string | null;
}

export interface ApplicationDecisionHistoryItem {
  id: string;
  decision: ApplicationDecisionType | null;
  from_status: string | null;
  to_status: string;
  rejection_reason: RejectionReasonValue | null;
  rejection_reason_label: string | null;
  internal_note: string | null;
  changed_by: string | null;
  changed_by_name: string | null;
  changed_at: string;
}

export interface ApplicationDecisionHistory {
  application_id: string;
  status: string;
  decided_by: string | null;
  decided_at: string | null;
  rejection_reason: RejectionReasonValue | null;
  internal_note: string | null;
  candidate_message: string | null;
  history: ApplicationDecisionHistoryItem[];
}

/**
 * The candidate's view of a decision. This is an allowlist from the server: it
 * contains no internal note, no recruiter identity, no score, no ranking, no
 * fairness data and no audit trail.
 */
export interface CandidateApplicationDecision {
  application_id: string;
  job_id: string;
  job_title: string;
  status: string;
  status_label: string;
  decision_outcome: string;
  rejection_reason: RejectionReasonValue | null;
  candidate_message: string | null;
  decided_at: string | null;
  is_decision_final: boolean;
}
