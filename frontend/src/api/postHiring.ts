import apiClient from "./client";
import type {
  ApprovedCandidateSummary,
  RecruiterPostHiringCandidateItem,
  PostHiringTimelineEvent,
  CandidateDocument,
  Employee,
  EmployeeCreatePayload,
  JobOffer,
  JobOfferCreatePayload,
  OnboardingTask,
  PostHiringStats,
  JoiningConfirmPayload,
  CandidateTaskSubmitPayload,
  TaskReviewPayload,
} from "../types/postHiring";

export const postHiringApi = {
  // --- HR & Staff Statistics ---
  getStats: async (): Promise<PostHiringStats> => {
    const res = await apiClient.get<PostHiringStats>("/post-hiring/stats");
    return res.data;
  },

  getApprovedCandidates: async (): Promise<ApprovedCandidateSummary[]> => {
    const res = await apiClient.get<ApprovedCandidateSummary[]>("/post-hiring/approved-candidates");
    return res.data;
  },

  // --- Offer Operations ---
  getOffers: async (status?: string): Promise<JobOffer[]> => {
    const res = await apiClient.get<JobOffer[]>("/post-hiring/offers", {
      params: status ? { status } : undefined,
    });
    return res.data;
  },

  getOffer: async (offerId: string): Promise<JobOffer> => {
    const res = await apiClient.get<JobOffer>(`/post-hiring/offers/${offerId}`);
    return res.data;
  },

  createOffer: async (payload: JobOfferCreatePayload): Promise<JobOffer> => {
    const res = await apiClient.post<JobOffer>("/post-hiring/offers", payload);
    return res.data;
  },

  updateOffer: async (offerId: string, payload: Partial<JobOfferCreatePayload>): Promise<JobOffer> => {
    const res = await apiClient.put<JobOffer>(`/post-hiring/offers/${offerId}`, payload);
    return res.data;
  },

  sendOffer: async (offerId: string): Promise<JobOffer> => {
    const res = await apiClient.post<JobOffer>(`/post-hiring/offers/${offerId}/send`);
    return res.data;
  },

  withdrawOffer: async (offerId: string): Promise<JobOffer> => {
    const res = await apiClient.post<JobOffer>(`/post-hiring/offers/${offerId}/withdraw`);
    return res.data;
  },

  downloadOfferPdf: async (offerId: string): Promise<Blob> => {
    const res = await apiClient.get(`/post-hiring/offers/${offerId}/pdf`, {
      responseType: "blob",
    });
    return res.data;
  },

  // --- Document Operations ---
  getDocuments: async (applicationId?: string, candidateId?: string): Promise<CandidateDocument[]> => {
    const res = await apiClient.get<CandidateDocument[]>("/post-hiring/documents", {
      params: { application_id: applicationId, candidate_id: candidateId },
    });
    return res.data;
  },

  verifyDocument: async (
    documentId: string,
    status: "verified" | "rejected" | "resubmission_required",
    hrRemarks?: string,
  ): Promise<CandidateDocument> => {
    const res = await apiClient.post<CandidateDocument>(`/post-hiring/documents/${documentId}/verify`, {
      status,
      hr_remarks: hrRemarks,
    });
    return res.data;
  },

  // --- Employee & Onboarding Operations ---
  getEmployees: async (params?: {
    department?: string;
    employment_status?: string;
    search?: string;
  }): Promise<Employee[]> => {
    const res = await apiClient.get<Employee[]>("/post-hiring/employees", { params });
    return res.data;
  },

  createEmployee: async (payload: EmployeeCreatePayload): Promise<Employee> => {
    const res = await apiClient.post<Employee>("/post-hiring/employees", payload);
    return res.data;
  },

  getEmployee: async (employeeId: string): Promise<Employee> => {
    const res = await apiClient.get<Employee>(`/post-hiring/employees/${employeeId}`);
    return res.data;
  },

  updateEmployee: async (employeeId: string, payload: Partial<EmployeeCreatePayload>): Promise<Employee> => {
    const res = await apiClient.put<Employee>(`/post-hiring/employees/${employeeId}`, payload);
    return res.data;
  },

  confirmJoining: async (employeeId: string, payload: JoiningConfirmPayload): Promise<Employee> => {
    const res = await apiClient.post<Employee>(`/post-hiring/employees/${employeeId}/confirm-joining`, payload);
    return res.data;
  },

  activateEmployee: async (employeeId: string): Promise<Employee> => {
    const res = await apiClient.post<Employee>(`/post-hiring/employees/${employeeId}/activate`);
    return res.data;
  },

  addOnboardingTask: async (
    employeeId: string,
    payload: {
      title: string;
      description?: string;
      category?: string;
      assigned_to_role?: string;
      deadline?: string;
      instructions?: string;
      hr_remarks?: string;
    },
  ): Promise<OnboardingTask> => {
    const res = await apiClient.post<OnboardingTask>(`/post-hiring/employees/${employeeId}/tasks`, payload);
    return res.data;
  },

  updateTask: async (
    taskId: string,
    payload: { is_completed?: boolean; hr_remarks?: string; deadline?: string; instructions?: string },
  ): Promise<OnboardingTask> => {
    const res = await apiClient.put<OnboardingTask>(`/post-hiring/tasks/${taskId}`, payload);
    return res.data;
  },

  reviewTask: async (taskId: string, payload: TaskReviewPayload): Promise<OnboardingTask> => {
    const res = await apiClient.post<OnboardingTask>(`/post-hiring/tasks/${taskId}/review`, payload);
    return res.data;
  },

  sendTaskReminder: async (taskId: string): Promise<{ status: string; message: string }> => {
    const res = await apiClient.post<{ status: string; message: string }>(`/post-hiring/tasks/${taskId}/reminder`);
    return res.data;
  },

  completeOnboarding: async (employeeId: string): Promise<Employee> => {
    const res = await apiClient.post<Employee>(`/post-hiring/employees/${employeeId}/complete-onboarding`);
    return res.data;
  },

  // --- Candidate Operations ---
  candidateGetOffers: async (): Promise<JobOffer[]> => {
    const res = await apiClient.get<JobOffer[]>("/post-hiring/candidate/offers");
    return res.data;
  },

  candidateRespondOffer: async (
    offerId: string,
    action: "accept" | "decline",
    declineReason?: string,
    candidateNotes?: string,
  ): Promise<JobOffer> => {
    const res = await apiClient.post<JobOffer>(`/post-hiring/candidate/offers/${offerId}/respond`, {
      action,
      decline_reason: declineReason,
      candidate_notes: candidateNotes,
    });
    return res.data;
  },

  candidateClarifyOffer: async (offerId: string, question: string): Promise<{ status: string; message: string }> => {
    const res = await apiClient.post<{ status: string; message: string }>(
      `/post-hiring/candidate/offers/${offerId}/clarify`,
      { question },
    );
    return res.data;
  },

  candidateGetDocuments: async (): Promise<CandidateDocument[]> => {
    const res = await apiClient.get<CandidateDocument[]>("/post-hiring/candidate/documents");
    return res.data;
  },

  candidateUploadDocument: async (
    applicationId: string,
    documentType: string,
    documentTitle: string,
    file: File,
  ): Promise<CandidateDocument> => {
    const formData = new FormData();
    formData.append("application_id", applicationId);
    formData.append("document_type", documentType);
    formData.append("document_title", documentTitle);
    formData.append("file", file);

    const res = await apiClient.post<CandidateDocument>("/post-hiring/candidate/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  candidateGetOnboarding: async (): Promise<Employee | null> => {
    const res = await apiClient.get<Employee | null>("/post-hiring/candidate/onboarding");
    return res.data;
  },

  candidateToggleTask: async (taskId: string): Promise<OnboardingTask> => {
    const res = await apiClient.post<OnboardingTask>(`/post-hiring/candidate/tasks/${taskId}/toggle`);
    return res.data;
  },

  candidateSubmitTask: async (taskId: string, payload: CandidateTaskSubmitPayload): Promise<OnboardingTask> => {
    const res = await apiClient.post<OnboardingTask>(`/post-hiring/candidate/tasks/${taskId}/submit`, payload);
    return res.data;
  },

  getAdminStats: async (): Promise<PostHiringStats> => {
    const res = await apiClient.get<PostHiringStats>("/post-hiring/admin/stats");
    return res.data;
  },

  getRecruiterTracker: async (): Promise<RecruiterPostHiringCandidateItem[]> => {
    const res = await apiClient.get<RecruiterPostHiringCandidateItem[]>("/post-hiring/recruiter/tracker");
    return res.data;
  },

  getTimeline: async (applicationId: string): Promise<PostHiringTimelineEvent[]> => {
    const res = await apiClient.get<PostHiringTimelineEvent[]>(`/post-hiring/timeline/${applicationId}`);
    return res.data;
  },
};

export default postHiringApi;
