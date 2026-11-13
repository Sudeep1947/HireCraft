import apiClient from "./client";
import type {
  ApplicantDashboardQuery,
  ApplicantDashboardResponse,
  ApplicantSummary,
  CandidateApplicationTrack,
  CandidateJobDashboard,
  Job,
  JobApplication,
  JobFormData,
  JobListItem,
  JobSearchResult,
  SavedJob,
  RecruiterDashboard,
  RecruiterNote,
} from "../types/jobs";
import type {
  ApplicationDecisionHistory,
  ApplicationDecisionOptions,
  ApplicationDecisionResult,
  ApplicationDecisionType,
  CandidateApplicationDecision,
  RejectionReasonValue,
} from "../types/applicationDecision";
import type {
  JobAssessmentAssignRequest,
  JobAssessmentAssignResult,
  JobAssessmentCreateAndAssignRequest,
  JobAssessmentOptions,
} from "../types/jobAssessment";

function buildApplicantParams(params?: ApplicantDashboardQuery): Record<string, string | number> {
  const clean: Record<string, string | number> = {};
  if (!params) return clean;
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    clean[key] = value as string | number;
  }
  return clean;
}

export const recruiterJobApi = {
  getDashboard: () =>
    apiClient.get<RecruiterDashboard>("/recruiter/jobs/dashboard").then((r) => r.data),

  listJobs: () =>
    apiClient.get<JobListItem[]>("/recruiter/jobs").then((r) => r.data),

  getJob: (id: string) =>
    apiClient.get<Job>(`/recruiter/jobs/${id}`).then((r) => r.data),

  createJob: (data: JobFormData) =>
    apiClient.post<Job>("/recruiter/jobs", data).then((r) => r.data),

  updateJob: (id: string, data: Partial<JobFormData>) =>
    apiClient.put<Job>(`/recruiter/jobs/${id}`, data).then((r) => r.data),

  deleteJob: (id: string) =>
    apiClient.delete(`/recruiter/jobs/${id}`).then((r) => r.data),

  changeStatus: (id: string, status: string) =>
    apiClient.patch<Job>(`/recruiter/jobs/${id}/status?status=${status}`).then((r) => r.data),

  getApplications: (jobId: string) =>
    apiClient.get<JobApplication[]>(`/recruiter/jobs/${jobId}/applications`).then((r) => r.data),

  getApplicantDashboard: (jobId: string, params?: ApplicantDashboardQuery) =>
    apiClient
      .get<ApplicantDashboardResponse>(`/recruiter/jobs/${jobId}/applicants`, {
        params: buildApplicantParams(params),
      })
      .then((r) => r.data),

  getApplicantSummary: (jobId: string) =>
    apiClient.get<ApplicantSummary>(`/recruiter/jobs/${jobId}/applicants/summary`).then((r) => r.data),

  updateApplicationStatus: (
    applicationId: string,
    status: string,
    options?: { reason?: string; comment?: string }
  ) =>
    apiClient
      .patch(`/recruiter/jobs/applications/${applicationId}/status`, {
        status,
        reason: options?.reason,
        comment: options?.comment,
      })
      .then((r) => r.data),

  // ── Phase 8: explicit recruiter decisions ─────────────────────────
  // These are the endpoints a decision UI must use. The legacy status patch
  // above takes a free-text reason and cannot require one, so it stays for the
  // simulation/demo callers and is not used for human decisions.

  getApplicationDecisionOptions: (applicationId: string) =>
    apiClient
      .get<ApplicationDecisionOptions>(
        `/recruiter/jobs/applications/${applicationId}/decision-options`
      )
      .then((r) => r.data),

  recordApplicationDecision: (
    applicationId: string,
    decision: ApplicationDecisionType,
    options?: { rejectionReason?: RejectionReasonValue; internalNote?: string }
  ) =>
    apiClient
      .post<ApplicationDecisionResult>(
        `/recruiter/jobs/applications/${applicationId}/decision`,
        {
          decision,
          rejection_reason: options?.rejectionReason ?? null,
          internal_note: options?.internalNote ?? null,
        }
      )
      .then((r) => r.data),

  getApplicationDecisionHistory: (applicationId: string) =>
    apiClient
      .get<ApplicationDecisionHistory>(
        `/recruiter/jobs/applications/${applicationId}/decision-history`
      )
      .then((r) => r.data),

  addNote: (applicationId: string, note: string) =>
    apiClient.post<RecruiterNote>(`/recruiter/jobs/applications/${applicationId}/notes`, { note }).then((r) => r.data),

  // ── Phase 1: job-scoped bulk assessment assignment ────────────────
  // The job is the only scope: these bodies carry assessment content and
  // application ids, never a candidate or recruiter id. The single-application
  // assessment routes in `applicationAssessment.ts` stay the per-candidate
  // entry point; these are the batch entry point for the same engine.

  /** The assessments this recruiter may assign to this job's applicants. */
  getJobAssessmentOptions: (jobId: string) =>
    apiClient
      .get<JobAssessmentOptions>(`/recruiter/jobs/${jobId}/assessment-options`)
      .then((r) => r.data),

  /** Assign an existing assessment to several of this job's applicants. */
  assignJobAssessment: (jobId: string, data: JobAssessmentAssignRequest) =>
    apiClient
      .post<JobAssessmentAssignResult>(`/recruiter/jobs/${jobId}/assessments/assign`, data)
      .then((r) => r.data),

  /** Author one assessment for this job and assign it to several applicants. */
  createAndAssignJobAssessment: (jobId: string, data: JobAssessmentCreateAndAssignRequest) =>
    apiClient
      .post<JobAssessmentAssignResult>(
        `/recruiter/jobs/${jobId}/assessments/create-and-assign`,
        data
      )
      .then((r) => r.data),
};

export const candidateJobApi = {
  getDashboard: () =>
    apiClient.get<CandidateJobDashboard>("/candidate/jobs/dashboard").then((r) => r.data),

  searchJobs: (params: {
    q?: string;
    employment_type?: string;
    location?: string;
    salary_min?: number;
    salary_max?: number;
    skills?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) =>
    apiClient.get<JobSearchResult>("/candidate/jobs/search", { params }).then((r) => r.data),

  getJob: (id: string) =>
    apiClient.get<Job>(`/candidate/jobs/${id}`).then((r) => r.data),

  apply: (jobId: string, resumeId?: string, coverLetter?: string) =>
    apiClient
      .post<JobApplication>("/candidate/jobs/apply", {
        job_id: jobId,
        resume_id: resumeId,
        cover_letter: coverLetter,
      })
      .then((r) => r.data),

  getMyApplications: () =>
    apiClient.get<JobApplication[]>("/candidate/jobs/applications").then((r) => r.data),

  // Phase 9: one application's tracking view (stages + timeline + the same
  // decision projection the decision endpoint returns).
  getMyApplicationTrack: (applicationId: string) =>
    apiClient
      .get<CandidateApplicationTrack>(`/candidate/jobs/applications/${applicationId}`)
      .then((r) => r.data),

  getMyApplicationDecision: (applicationId: string) =>
    apiClient
      .get<CandidateApplicationDecision>(
        `/candidate/jobs/applications/${applicationId}/decision`
      )
      .then((r) => r.data),

  getMyApplicationDecisions: () =>
    apiClient
      .get<CandidateApplicationDecision[]>("/candidate/jobs/applications/decisions")
      .then((r) => r.data),

  withdrawApplication: (id: string) =>
    apiClient.post(`/candidate/jobs/applications/${id}/withdraw`).then((r) => r.data),

  saveJob: (jobId: string) =>
    apiClient.post<SavedJob>("/candidate/jobs/saved", null, { params: { job_id: jobId } }).then((r) => r.data),

  unsaveJob: (jobId: string) =>
    apiClient.delete(`/candidate/jobs/saved/${jobId}`).then((r) => r.data),

  getSavedJobs: () =>
    apiClient.get<JobListItem[]>("/candidate/jobs/saved").then((r) => r.data),
};
