export interface InterviewQuestion {
  id: string;
  question_text: string;
  category: string;
  difficulty: string;
  order_index: number;
  context: Record<string, unknown> | null;
}

export interface InterviewEvaluation {
  id: string;
  technical_accuracy: number;
  completeness: number;
  communication: number;
  problem_solving: number;
  confidence: number;
  relevance: number;
  overall_score: number;
  feedback: string | null;
  improvement_suggestions: string[] | null;
  follow_up_questions: string[] | null;
}

export interface InterviewAnswer {
  id: string;
  answer_text: string;
  time_taken_seconds: number | null;
  evaluation: InterviewEvaluation | null;
}

export interface QuestionWithAnswer extends InterviewQuestion {
  answer: InterviewAnswer | null;
}

export interface InterviewScorecard {
  id: string;
  interview_id: string;
  technical_skills: number;
  communication: number;
  teamwork: number;
  leadership: number;
  problem_solving: number;
  culture_fit: number;
  learning_ability: number;
  overall_score: number;
  recommendation: string;
  hiring_confidence: number;
  recruiter_notes: string | null;
  ai_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewDetail {
  id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  /**
   * The application this interview was scheduled from, or null for a
   * practice/mock interview, which has none.
   */
  application_id: string | null;
  recruiter_id: string | null;
  /**
   * Null for the candidate: the interviewer's identity is withheld, since who
   * interviewed you is not part of your own interview record.
   */
  recruiter_name: string | null;
  interview_type: string;
  status: string;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_minutes: number | null;
  total_questions: number;
  questions_answered: number;
  questions: QuestionWithAnswer[];
  scorecard: InterviewScorecard | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewListItem {
  id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  /** See `InterviewDetail.application_id`. */
  application_id: string | null;
  interview_type: string;
  status: string;
  scheduled_at: string | null;
  completed_at: string | null;
  /** The interview's scheduled length; null when the row predates it. */
  duration_minutes: number | null;
  total_questions: number;
  questions_answered: number;
  overall_score: number | null;
  /** The interviewer's display name; empty when the row has none recorded. */
  recruiter_name: string;
  created_at: string;
}

export interface InterviewGenerateRequest {
  job_id: string;
  categories?: string[];
  difficulty?: string;
  count?: number;
  candidate_id?: string;
}

export interface InterviewGenerateResponse {
  interview_id: string;
  questions: InterviewQuestion[];
  total_questions: number;
  categories: string[];
  difficulty: string;
}

export interface MockInterviewStartResponse {
  interview_id: string;
  job_id: string;
  job_title: string;
  first_question: InterviewQuestion;
  total_questions: number;
  message: string;
}

export interface AnswerSubmitResponse {
  answer_id: string;
  evaluation: InterviewEvaluation;
  next_question: InterviewQuestion | null;
  questions_remaining: number;
}

export interface InterviewCompleteResponse {
  interview_id: string;
  overall_score: number;
  strong_areas: string[];
  weak_areas: string[];
  improvement_suggestions: string[];
  feedback_summary: string;
}

export interface InterviewDashboard {
  total_interviews: number;
  mock_interviews?: number;
  scheduled_interviews?: number;
  upcoming_interviews: number;
  completed_interviews?: number;
  average_score: number;
  recent_interviews?: InterviewListItem[];
  upcoming?: InterviewListItem[];
  recent_scores?: Record<string, unknown>[];
  score_distribution?: Record<string, number>;
  category_performance?: Record<string, number>;
}

export interface InterviewAnalytics {
  total_interviews: number;
  completion_rate: number;
  average_score: number;
  median_score: number;
  score_distribution: Record<string, number>;
  category_averages: Record<string, number>;
  difficulty_distribution: Record<string, number>;
  recommendation_breakdown: Record<string, number>;
  skill_performance: Record<string, number>;
  hiring_prediction: Record<string, number>;
  trends: Record<string, unknown>[];
}

export interface CodingAssessment {
  id: string;
  problem_title: string;
  problem_description: string;
  difficulty: string;
  category: string;
  candidate_solution: string | null;
  is_correct: boolean | null;
  score: number;
}

export interface CodingSubmissionResponse {
  assessment_id: string;
  is_correct: boolean;
  score: number;
  feedback: string;
  expected_approach: string;
}

export interface InterviewScheduleRequest {
  job_id: string;
  candidate_id: string;
  scheduled_at: string;
  duration_minutes?: number;
  categories?: string[];
  difficulty?: string;
  question_count?: number;
}

export interface ScorecardCreateRequest {
  technical_skills: number;
  communication: number;
  teamwork: number;
  leadership: number;
  problem_solving: number;
  culture_fit: number;
  learning_ability: number;
  recommendation: string;
  hiring_confidence: number;
  recruiter_notes?: string;
}

export type QuestionCategory =
  | "technical"
  | "behavioral"
  | "hr"
  | "situational"
  | "coding"
  | "system_design"
  | "problem_solving";

export type InterviewStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

export type InterviewType = "mock" | "recruiter_scheduled";

/**
 * Which hiring round an interview is.
 *
 * Separate from the interview status and from the application status: a
 * recruiter round and an HR round are two interviews, each with its own status.
 * `recruiter` is the first round and the default; `hr` is only schedulable once
 * the candidate has been advanced (see `can_schedule_hr`).
 */
export type InterviewStage = "recruiter" | "hr";

export const INTERVIEW_STAGE_LABELS: Record<InterviewStage, string> = {
  recruiter: "Recruiter Interview",
  hr: "HR Interview",
};

export const CATEGORY_LABELS: Record<QuestionCategory, string> = {
  technical: "Technical",
  behavioral: "Behavioral",
  hr: "HR",
  situational: "Situational",
  coding: "Coding",
  system_design: "System Design",
  problem_solving: "Problem Solving",
};

export const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-green-100 text-green-700",
  medium: "bg-amber-100 text-amber-700",
  hard: "bg-red-100 text-red-700",
};

export const STATUS_COLORS: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-gray-100 text-gray-500",
};

// ── Phase 11: application-driven interviews ──────────────────────────
//
// An interview is scheduled from a job application, so every request and
// response below is keyed by `application_id` and never by job, candidate or
// recruiter. The server derives the participants from the application; sending
// them from here would either be ignored or rejected, and a UI that implied it
// could choose them would be lying to the recruiter.

export type ApplicationStatus =
  | "applied"
  | "under_review"
  | "shortlisted"
  | "interview_scheduled"
  | "interviewed"
  | "offered"
  | "hired"
  | "rejected"
  | "withdrawn";

/**
 * Why an action is unavailable.
 *
 * A controlled vocabulary from the server, not a message: the panel shows a
 * human explanation mapped from these codes, so the reason a button is disabled
 * survives a copy change and can be asserted in tests.
 */
export type InterviewActionReason =
  | "application_is_final"
  | "application_not_shortlisted"
  | "interview_already_scheduled"
  | "interview_already_finished"
  // Phase 15: HR-stage and advancement affordance reasons.
  | "candidate_not_advanced_to_hr"
  | "candidate_already_advanced_to_hr"
  | "hr_interview_already_scheduled"
  | "recruiter_interview_not_completed";

export interface ApplicationInterviewSummary {
  id: string;
  application_id: string | null;
  job_id: string;
  candidate_id: string;
  interview_type: InterviewType;
  /** Which hiring round this is. */
  stage: InterviewStage;
  status: InterviewStatus;
  scheduled_at: string | null;
  /** Set when the interview was moved, so the UI can say "rescheduled". */
  rescheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_minutes: number;
  total_questions: number;
  questions_answered: number;
  has_scorecard: boolean;
  overall_score: number | null;
  recommendation: string | null;
  recruiter_id?: string | null;
  recruiter_name?: string | null;
  room_id?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ApplicationInterviewEvidence {
  application_id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  application_status: ApplicationStatus;
  interview_count: number;
  completed_count: number;
  /**
   * Averaged over completed interviews only, so an interview nobody has taken
   * cannot drag the figure down. Null until one is completed.
   */
  average_overall_score: number | null;
  interviews: ApplicationInterviewSummary[];
  /** True once the candidate has been advanced to the HR stage. */
  hr_eligible: boolean;
  advanced_to_hr_at: string | null;
}

export interface ApplicationInterviewActionOption {
  interview_id: string;
  status: InterviewStatus;
  can_reschedule: boolean;
  reschedule_unavailable_reason: InterviewActionReason | null;
  can_cancel: boolean;
  cancel_unavailable_reason: InterviewActionReason | null;
  can_complete: boolean;
  complete_unavailable_reason: InterviewActionReason | null;
}

export interface ApplicationInterviewOptions {
  application_id: string;
  current_status: ApplicationStatus;
  status_is_final: boolean;
  can_schedule: boolean;
  schedule_unavailable_reason: InterviewActionReason | null;
  has_interviews: boolean;
  active_interview_id: string | null;
  options: ApplicationInterviewActionOption[];
  // ── Phase 15: HR stage + advancement affordances ──────────────
  /** True once the candidate has been advanced to the HR stage. */
  hr_eligible: boolean;
  /** True once a recruiter-round interview reached `completed`. */
  recruiter_stage_complete: boolean;
  can_advance: boolean;
  advance_unavailable_reason: InterviewActionReason | null;
  can_schedule_hr: boolean;
  schedule_hr_unavailable_reason: InterviewActionReason | null;
  can_reject: boolean;
  reject_unavailable_reason: InterviewActionReason | null;
}

export interface ApplicationInterviewScheduleResult {
  application_id: string;
  interview_id: string;
  interview_status: InterviewStatus;
  application_status: ApplicationStatus;
  application_status_changed: boolean;
  message: string;
}

/**
 * The candidate's view of their own interview.
 *
 * An allowlist that deliberately has no scorecard, recommendation, evaluation,
 * recruiter identity or notes. The server sends nothing else, so a field added
 * here would be a field the candidate should not have.
 */
export interface CandidateApplicationInterviewView {
  application_id: string;
  interview_id: string | null;
  status: InterviewStatus | null;
  scheduled_at: string | null;
  duration_minutes: number | null;
  completed_at: string | null;
  next_upcoming_at: string | null;
  has_completed: boolean;
  interview_count: number;
  /**
   * Approved candidate wording for the current stage, or null when the server
   * has no wording to give. Never built from recruiter prose.
   */
  message: string | null;
}

/** No job, candidate or recruiter field: the application in the path decides. */
export interface ApplicationInterviewScheduleRequest {
  scheduled_at: string;
  duration_minutes?: number;
  categories?: string[];
  difficulty?: string;
  question_count?: number;
  /**
   * Which round to schedule. Defaults to the recruiter round; `hr` is only
   * accepted once the candidate has been advanced to the HR stage.
   */
  stage?: InterviewStage;
  interviewer_id?: string;
  notes?: string;
  focus_areas?: string[];
}

export interface ApplicationInterviewRescheduleRequest {
  scheduled_at: string;
  duration_minutes?: number;
}

/** `reason` is internal. The candidate is only ever told it was cancelled. */
export interface ApplicationInterviewCancelRequest {
  reason?: string;
}

export interface ApplicationInterviewCompleteRequest {
  completed_at?: string;
}

/** Explanations for the controlled `InterviewActionReason` codes. */
export const INTERVIEW_REASON_LABELS: Record<InterviewActionReason, string> = {
  application_is_final: "This application is finalized",
  application_not_shortlisted: "Only a shortlisted application can be interviewed",
  interview_already_scheduled: "An interview is already scheduled for this application",
  interview_already_finished: "This interview has already finished",
  candidate_not_advanced_to_hr: "Advance the candidate to the HR stage first",
  candidate_already_advanced_to_hr: "The candidate is already in the HR stage",
  hr_interview_already_scheduled: "An HR interview is already scheduled",
  recruiter_interview_not_completed:
    "Complete the recruiter interview before advancing to HR",
};

// ── Phase 15: recruiter feedback + advance/reject from the interview stage ──
//
// Manual technical feedback the interviewer records against one interview. It is
// staff-only evidence and the candidate never receives it. Stored on the
// interview's scorecard; the overall score is averaged from the three ratings
// when the caller does not supply one.

export type HiringRecommendation =
  | "strongly_recommend"
  | "recommend"
  | "consider"
  | "not_recommended";

export const HIRING_RECOMMENDATION_LABELS: Record<HiringRecommendation, string> = {
  strongly_recommend: "Strongly recommend",
  recommend: "Recommend",
  consider: "Consider",
  not_recommended: "Not recommended",
};

/** The Phase 8 controlled rejection vocabulary, reused verbatim. */
export type RejectionReason =
  | "missing_required_skill"
  | "insufficient_experience"
  | "education_requirement"
  | "low_job_match"
  | "failed_assessment"
  | "failed_interview"
  | "position_filled"
  | "other";

export interface ApplicationInterviewFeedbackRequest {
  technical_skills: number;
  communication: number;
  problem_solving: number;
  teamwork?: number;
  leadership?: number;
  culture_fit?: number;
  /** Omitted: the server averages the ratings above. */
  overall_score?: number;
  hiring_confidence?: number;
  recommendation?: HiringRecommendation;
  recruiter_notes?: string;
  strengths?: string;
  concerns?: string;
}

export interface ApplicationInterviewFeedback {
  interview_id: string;
  application_id: string;
  technical_skills: number;
  communication: number;
  problem_solving: number;
  teamwork?: number;
  leadership?: number;
  culture_fit?: number;
  overall_score: number;
  hiring_confidence: number;
  recommendation: HiringRecommendation;
  recruiter_notes: string | null;
  strengths?: string | null;
  concerns?: string | null;
  created_at: string;
  updated_at: string;
}

export interface HRInterviewerOption {
  id: string;
  full_name: string;
  email: string;
  role: string;
}

/** Carries only an internal note: advancing picks no time and makes no decision. */
export interface ApplicationInterviewAdvanceRequest {
  note?: string;
}

export interface ApplicationInterviewRejectRequest {
  rejection_reason: RejectionReason;
  internal_note?: string;
}

export interface ApplicationInterviewStageActionResult {
  application_id: string;
  application_status: ApplicationStatus;
  application_status_changed: boolean;
  hr_eligible: boolean;
  candidate_message: string | null;
  message: string;
}

// ── Phase 14: the shared interview room ───────────────────────────
//
// One room per interview, which both participants reach by the same interview id.
// `can_join` and `unavailable_reason` are the server's answer, computed from the
// stored schedule and status: the UI renders them rather than deciding from its
// own clock, so the Join button and the Join the API accepts cannot disagree.
//
// There is deliberately no field here for the other party's name, id or email.
// Presence is reported as *they are here* and nothing more, so the interviewer's
// account cannot reach the candidate even by accident. Nor is there any score,
// recommendation or note: interview intelligence stays staff-only evidence.

export type InterviewRoomRole = "candidate" | "interviewer";

/**
 * The server-derived display state of a room.
 *
 * A fixed vocabulary so the UI renders one label per state instead of
 * re-deriving "is it ready?" from raw timestamps. `expired` is display state
 * only: the interview is still `scheduled` and no status was written, because
 * the join window closing is not the interview ending.
 */
export type RoomDisplayState =
  | "upcoming"
  | "ready_to_join"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "rescheduled"
  | "expired";

export const ROOM_STATE_LABELS: Record<RoomDisplayState, string> = {
  upcoming: "Upcoming",
  ready_to_join: "Ready to join",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
  expired: "Expired",
};

export const ROOM_STATE_COLORS: Record<RoomDisplayState, string> = {
  upcoming: "bg-blue-100 text-blue-700",
  ready_to_join: "bg-emerald-100 text-emerald-700",
  in_progress: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-gray-100 text-gray-500",
  rescheduled: "bg-indigo-100 text-indigo-700",
  expired: "bg-red-100 text-red-700",
};

/** Why a join is unavailable. Mirrors the server's controlled vocabulary. */
export type InterviewRoomReason =
  | "interview_not_joinable"
  | "interview_has_no_schedule"
  | "join_window_not_open"
  | "join_window_closed";

export interface InterviewRoomPresence {
  candidate_joined: boolean;
  candidate_joined_at: string | null;
  interviewer_joined: boolean;
  interviewer_joined_at: string | null;
}

export interface InterviewRoomState {
  interview_id: string;
  /** Null for a mock interview and for pre-Phase-11 interviews. */
  application_id: string | null;
  interview_type: InterviewType;
  /** Which hiring round this is. Safe for both participants to see. */
  stage: InterviewStage;
  status: InterviewStatus;
  /** The human-facing summary of `status` and the schedule. */
  state: RoomDisplayState;
  your_role: InterviewRoomRole;
  room_id: string;
  scheduled_at: string | null;
  /** Set when the interview was moved, so the room can say "rescheduled". */
  rescheduled_at: string | null;
  /** The interviewer's wall-clock zone, for showing a local time. */
  timezone: string;
  duration_minutes: number | null;
  /** The window the server enforces, echoed so the countdown matches it. */
  join_opens_at: string | null;
  join_closes_at: string | null;
  /** The server's clock, so a countdown does not trust the viewer's device. */
  server_time: string;
  can_join: boolean;
  unavailable_reason: InterviewRoomReason | null;
  /** True once *this* caller has entered. Re-joining is allowed and idempotent. */
  you_joined: boolean;
  presence: InterviewRoomPresence;
  /** Server-authored wording for the current state. */
  message: string;
}

export const ROOM_REASON_LABELS: Record<InterviewRoomReason, string> = {
  interview_not_joinable: "This interview is not open for joining",
  interview_has_no_schedule: "This interview has no scheduled time",
  join_window_not_open: "The room opens shortly before the scheduled time",
  join_window_closed: "This interview's join window has closed",
};

// ── Phase 16: real-time video (WebRTC + WebSocket signaling) ───────
//
// Audio and video travel peer-to-peer between the two browsers; the server
// only relays the small signaling messages, so no provider secrets exist and
// nothing sensitive transits the backend. The signaling socket reuses the same
// access token as the REST client (as a query parameter, because browsers
// cannot attach an Authorization header to a WebSocket handshake) and the
// server re-runs the same room authorization and join window before it will
// relay anything.

/** Which side of the interview a signaling connection occupies. */
export type VideoSignalingRole = "candidate" | "interviewer";

/** WebSocket close codes the signaling endpoint uses; the client maps these
 *  to human messages rather than showing "connection lost" for every case. */
export const VIDEO_CLOSE_CODES = {
  ended: 4400,
  unauthenticated: 4401,
  forbidden: 4403,
  notFound: 4404,
  replaced: 4409,
  protocol: 1008,
} as const;

/** Client → server messages. `signal` carries the SDP/ICE payloads. */
export interface VideoClientSignalMessage {
  type: "signal";
  payload:
    | { kind: "offer"; sdp: string }
    | { kind: "answer"; sdp: string }
    | { kind: "ice"; candidate: RTCIceCandidateInit | null };
}

export interface VideoClientMediaStateMessage {
  type: "media_state";
  payload: { camera: boolean; mic: boolean };
}

export interface VideoClientLeaveMessage {
  type: "leave";
}

export interface VideoClientEndMessage {
  type: "end";
}

export interface VideoClientPingMessage {
  type: "ping";
}

export interface VideoClientChatMessage {
  type: "chat";
  payload: { text: string; sender?: string; timestamp?: string };
}

export interface VideoClientHandRaiseMessage {
  type: "hand_raise";
  payload: { raised: boolean };
}

export interface VideoClientCaptionMessage {
  type: "caption";
  payload: { text: string; is_final?: boolean };
}

export type VideoClientMessage =
  | VideoClientSignalMessage
  | VideoClientMediaStateMessage
  | VideoClientLeaveMessage
  | VideoClientEndMessage
  | VideoClientPingMessage
  | VideoClientChatMessage
  | VideoClientHandRaiseMessage
  | VideoClientCaptionMessage;

/** Server → client messages. */
export interface VideoServerJoinedMessage {
  type: "joined";
  payload: {
    role: VideoSignalingRole;
    peer_present: boolean;
    peer_media: { camera: boolean; mic: boolean } | null;
  };
}

export interface VideoServerPeerJoinedMessage {
  type: "peer_joined";
  payload: { role: VideoSignalingRole };
}

export interface VideoServerPeerLeftMessage {
  type: "peer_left";
  payload: { role: VideoSignalingRole };
}

export interface VideoServerSignalMessage {
  type: "signal";
  payload: { from: VideoSignalingRole } & VideoClientSignalMessage["payload"];
}

export interface VideoServerMediaStateMessage {
  type: "media_state";
  payload: {
    role: VideoSignalingRole;
    camera: boolean;
    mic: boolean;
  };
}

export interface VideoServerEndedMessage {
  type: "ended";
  payload: { by: VideoSignalingRole };
}

export interface VideoServerPongMessage {
  type: "pong";
}

export interface VideoServerChatMessage {
  type: "chat";
  payload: { from: VideoSignalingRole; text: string; sender?: string; timestamp?: string };
}

export interface VideoServerHandRaiseMessage {
  type: "hand_raise";
  payload: { from: VideoSignalingRole; raised: boolean };
}

export interface VideoServerCaptionMessage {
  type: "caption";
  payload: { from: VideoSignalingRole; text: string; is_final?: boolean };
}

export type VideoServerMessage =
  | VideoServerJoinedMessage
  | VideoServerPeerJoinedMessage
  | VideoServerPeerLeftMessage
  | VideoServerSignalMessage
  | VideoServerMediaStateMessage
  | VideoServerEndedMessage
  | VideoServerPongMessage
  | VideoServerChatMessage
  | VideoServerHandRaiseMessage
  | VideoServerCaptionMessage;

/** What the call surface shows about the connection itself. */
export type VideoCallStatus =
  | "idle"
  | "connecting" // socket + media being set up
  | "waiting" // connected, waiting for the other side
  | "connecting_peer" // negotiating with the peer
  | "connected"
  | "reconnecting"
  | "failed"
  | "ended"; // the interviewer ended the call
