import apiClient from "./client";
import type {
  InterviewGenerateRequest,
  InterviewGenerateResponse,
  InterviewDetail,
  InterviewListItem,
  InterviewDashboard,
  InterviewAnalytics,
  MockInterviewStartResponse,
  AnswerSubmitResponse,
  InterviewCompleteResponse,
  InterviewScheduleRequest,
  ScorecardCreateRequest,
  CodingSubmissionResponse,
  ApplicationInterviewCancelRequest,
  ApplicationInterviewCompleteRequest,
  ApplicationInterviewEvidence,
  ApplicationInterviewOptions,
  ApplicationInterviewRescheduleRequest,
  ApplicationInterviewScheduleRequest,
  ApplicationInterviewScheduleResult,
  ApplicationInterviewAdvanceRequest,
  ApplicationInterviewFeedback,
  ApplicationInterviewFeedbackRequest,
  ApplicationInterviewRejectRequest,
  ApplicationInterviewStageActionResult,
  InterviewRoomState,
} from "../types/interview";

export const interviewApi = {
  generateQuestions: async (data: InterviewGenerateRequest): Promise<InterviewGenerateResponse> => {
    const res = await apiClient.post("/interview/generate", data);
    return res.data;
  },

  scheduleInterview: async (data: InterviewScheduleRequest): Promise<{ message: string; interview_id: string; status: string }> => {
    const res = await apiClient.post("/interview/schedule", data);
    return res.data;
  },

  startMockInterview: async (jobId: string): Promise<MockInterviewStartResponse> => {
    const res = await apiClient.post("/interview/mock/start", { interview_id: jobId });
    return res.data;
  },

  submitAnswer: async (questionId: string, answerText: string, timeTaken?: number): Promise<AnswerSubmitResponse> => {
    const res = await apiClient.post("/interview/mock/answer", {
      question_id: questionId,
      answer_text: answerText,
      time_taken_seconds: timeTaken,
    });
    return res.data;
  },

  completeMockInterview: async (interviewId: string): Promise<InterviewCompleteResponse> => {
    const res = await apiClient.post("/interview/mock/complete", { interview_id: interviewId });
    return res.data;
  },

  listInterviews: async (): Promise<{ items: InterviewListItem[]; total: number }> => {
    const res = await apiClient.get("/interview/list");
    return res.data;
  },

  getInterviewDetail: async (interviewId: string): Promise<InterviewDetail> => {
    const res = await apiClient.get(`/interview/${interviewId}`);
    return res.data;
  },

  evaluateInterview: async (interviewId: string): Promise<Record<string, unknown>> => {
    const res = await apiClient.post(`/interview/${interviewId}/evaluate`);
    return res.data;
  },

  getScorecard: async (interviewId: string): Promise<Record<string, unknown>> => {
    const res = await apiClient.get(`/interview/${interviewId}/scorecard`);
    return res.data;
  },

  createScorecard: async (interviewId: string, data: ScorecardCreateRequest): Promise<Record<string, unknown>> => {
    const res = await apiClient.post(`/interview/${interviewId}/scorecard`, data);
    return res.data;
  },

  addNotes: async (interviewId: string, notes: string): Promise<{ message: string }> => {
    const res = await apiClient.post(`/interview/${interviewId}/notes`, { notes });
    return res.data;
  },

  getCandidateScorecards: async (candidateId: string): Promise<Record<string, unknown>[]> => {
    const res = await apiClient.get(`/interview/scorecard/${candidateId}`);
    return res.data;
  },

  getDashboard: async (): Promise<InterviewDashboard> => {
    const res = await apiClient.get("/interview/dashboard");
    return res.data;
  },

  getAnalytics: async (): Promise<InterviewAnalytics> => {
    const res = await apiClient.get("/interview/analytics");
    return res.data;
  },

  generateCodingAssessment: async (interviewId: string, category: string, difficulty: string, count: number): Promise<{ assessments: Record<string, unknown>[]; total: number }> => {
    const res = await apiClient.post("/interview/coding/generate", {
      interview_id: interviewId,
      category,
      difficulty,
      count,
    });
    return res.data;
  },

  submitCodingSolution: async (assessmentId: string, solution: string): Promise<CodingSubmissionResponse> => {
    const res = await apiClient.post("/interview/coding/submit", {
      assessment_id: assessmentId,
      solution,
    });
    return res.data;
  },

  // ── Phase 11: application-driven interviews ──────────────────────
  //
  // Every call is keyed by application id. The job, candidate and recruiter are
  // derived server-side from that application, so none of these methods accept
  // them: a panel that could pass a candidate id would suggest a recruiter can
  // aim an interview at someone other than the applicant.

  getApplicationInterviews: async (applicationId: string): Promise<ApplicationInterviewEvidence> => {
    const res = await apiClient.get(
      `/interview/applications/${applicationId}/interviews`,
    );
    return res.data;
  },

  getApplicationInterviewOptions: async (applicationId: string): Promise<ApplicationInterviewOptions> => {
    const res = await apiClient.get(
      `/interview/applications/${applicationId}/interviews/options`,
    );
    return res.data;
  },

  scheduleApplicationInterview: async (
    applicationId: string,
    data: ApplicationInterviewScheduleRequest,
  ): Promise<ApplicationInterviewScheduleResult> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/interviews`,
      data,
    );
    return res.data;
  },

  rescheduleApplicationInterview: async (
    applicationId: string,
    interviewId: string,
    data: ApplicationInterviewRescheduleRequest,
  ): Promise<ApplicationInterviewScheduleResult> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/interviews/${interviewId}/reschedule`,
      data,
    );
    return res.data;
  },

  cancelApplicationInterview: async (
    applicationId: string,
    interviewId: string,
    data: ApplicationInterviewCancelRequest = {},
  ): Promise<ApplicationInterviewScheduleResult> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/interviews/${interviewId}/cancel`,
      data,
    );
    return res.data;
  },

  completeApplicationInterview: async (
    applicationId: string,
    interviewId: string,
    data: ApplicationInterviewCompleteRequest = {},
  ): Promise<ApplicationInterviewScheduleResult> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/interviews/${interviewId}/complete`,
      data,
    );
    return res.data;
  },

  // ── Phase 15: recruiter feedback + advance/reject from the interview stage ──
  //
  // Feedback is keyed by application *and* interview: the interview id is scoped
  // to the application in the path, so a feedback write cannot reach an interview
  // on a different application. Advance and reject are keyed by application id,
  // because they act on the application's stage, not on one interview.

  /** Record the interviewer's manual feedback for one interview (staff-only). */
  saveApplicationInterviewFeedback: async (
    applicationId: string,
    interviewId: string,
    data: ApplicationInterviewFeedbackRequest,
  ): Promise<ApplicationInterviewFeedback> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/interviews/${interviewId}/feedback`,
      data,
    );
    return res.data;
  },

  /** Read the feedback recorded for one interview (staff-only). */
  getApplicationInterviewFeedback: async (
    applicationId: string,
    interviewId: string,
  ): Promise<ApplicationInterviewFeedback> => {
    const res = await apiClient.get(
      `/interview/applications/${applicationId}/interviews/${interviewId}/feedback`,
    );
    return res.data;
  },

  /** Get authorized HR interviewers in the organization. */
  getHrInterviewers: async (
    applicationId: string,
  ): Promise<Array<{ id: string; full_name: string; email: string; role: string }>> => {
    const res = await apiClient.get(
      `/interview/applications/${applicationId}/hr-interviewers`,
    );
    return res.data;
  },

  /** Advance the candidate to the HR stage. Picks no time and makes no decision. */
  advanceApplicationToHr: async (
    applicationId: string,
    data: ApplicationInterviewAdvanceRequest = {},
  ): Promise<ApplicationInterviewStageActionResult> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/advance-to-hr`,
      data,
    );
    return res.data;
  },

  /** Reject the candidate from the interview stage, through the decision service. */
  rejectApplicationFromInterview: async (
    applicationId: string,
    data: ApplicationInterviewRejectRequest,
  ): Promise<ApplicationInterviewStageActionResult> => {
    const res = await apiClient.post(
      `/interview/applications/${applicationId}/reject`,
      data,
    );
    return res.data;
  },

  // ── Phase 14: the shared interview room ──────────────────────────
  //
  // Keyed by interview id, not by application, because a room belongs to one
  // interview and both participants address it the same way. Neither method takes
  // a candidate, recruiter or room id: the server resolves who is calling from
  // the interview it loads, so a client cannot claim to be somebody else.

  /** Read the room without joining. Has no side effects: it does not attend. */
  getInterviewRoom: async (interviewId: string): Promise<InterviewRoomState> => {
    const res = await apiClient.get(`/interview/${interviewId}/room`);
    return res.data;
  },

  /** Enter the room. Idempotent, and the first join starts the interview. */
  joinInterviewRoom: async (interviewId: string): Promise<InterviewRoomState> => {
    const res = await apiClient.post(`/interview/${interviewId}/join`);
    return res.data;
  },
};
