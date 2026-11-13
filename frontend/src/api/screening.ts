import apiClient from "./client";
import type {
  CandidateComparisonResponse,
  CandidateMatchReport,
  RankingListResponse,
  ScreeningConfig,
  ScreeningResult,
  ScreeningTriggerResponse,
  SkillGapAnalysis,
  AISearchRequest,
  AISearchResponse,
  CandidateAISummary,
  JobAISummary,
  TopCandidatesResponse,
  HiringRecommendationResponse,
  RecruiterDashboardSummary,
  CandidateExplanation,
  CandidateComparisonXAI,
  JobFitResponse,
  CandidateEvidenceIntelResponse,
  JobIntelligenceResponse,
  ApplicationScreeningDetailResponse,
  RecruiterApplicationExplanation,
  CandidateApplicationExplanation,
  ApplicationFairnessContext,
} from "../types/screening";

export async function screenJobApplicants(
  jobId: string,
  config?: ScreeningConfig,
): Promise<ScreeningTriggerResponse> {
  const response = await apiClient.post<ScreeningTriggerResponse>(
    `/screening/jobs/${jobId}/screen`,
    config || {},
  );
  return response.data;
}

export async function getJobRankings(
  jobId: string,
): Promise<RankingListResponse> {
  const response = await apiClient.get<RankingListResponse>(
    `/screening/jobs/${jobId}/rankings`,
  );
  return response.data;
}

export async function getScreeningResult(
  jobId: string,
  candidateId: string,
): Promise<ScreeningResult> {
  const response = await apiClient.get<ScreeningResult>(
    `/screening/jobs/${jobId}/candidates/${candidateId}`,
  );
  return response.data;
}

export async function screenApplication(
  applicationId: string,
  config?: ScreeningConfig,
): Promise<ScreeningResult> {
  const response = await apiClient.post<ScreeningResult>(
    `/recruiter/jobs/applications/${applicationId}/screen`,
    config || {},
  );
  return response.data;
}

export async function getApplicationScreening(
  applicationId: string,
): Promise<ScreeningResult> {
  const response = await apiClient.get<ScreeningResult>(
    `/recruiter/jobs/applications/${applicationId}/screening`,
  );
  return response.data;
}

// ─── Application Screening Detail (Phase 5) ─────────────────────────

export async function getApplicationScreeningDetail(
  applicationId: string,
): Promise<ApplicationScreeningDetailResponse> {
  const response = await apiClient.get<ApplicationScreeningDetailResponse>(
    `/recruiter/jobs/applications/${applicationId}/screening-detail`,
  );
  return response.data;
}

// ─── Application Explanation (Phase 6) ─────────────────────────────
// Both surfaces read the same server-side explanation. The score is never
// recomputed here; these functions only fetch it.

export async function getApplicationExplanation(
  applicationId: string,
): Promise<RecruiterApplicationExplanation> {
  const response = await apiClient.get<RecruiterApplicationExplanation>(
    `/recruiter/jobs/applications/${applicationId}/explanation`,
  );
  return response.data;
}

export async function getMyApplicationExplanation(
  applicationId: string,
): Promise<CandidateApplicationExplanation> {
  const response = await apiClient.get<CandidateApplicationExplanation>(
    `/candidate/jobs/applications/${applicationId}/explanation`,
  );
  return response.data;
}

/**
 * Fairness context for one application (Phase 7, recruiter only).
 *
 * The response describes the job's screened population; the application is
 * included only as a member of it. Read-only: this never mutates a score,
 * status or rank, and it never triggers an adversarial run.
 */
export async function getApplicationFairnessContext(
  applicationId: string,
  minimumGroupSize?: number,
): Promise<ApplicationFairnessContext> {
  const params =
    minimumGroupSize !== undefined ? `?minimum_group_size=${minimumGroupSize}` : "";
  const response = await apiClient.get<ApplicationFairnessContext>(
    `/recruiter/jobs/applications/${applicationId}/fairness-context${params}`,
  );
  return response.data;
}

export async function getSkillGap(
  jobId: string,
  candidateId: string,
): Promise<SkillGapAnalysis> {
  const response = await apiClient.get<SkillGapAnalysis>(
    `/screening/jobs/${jobId}/candidates/${candidateId}/skill-gap`,
  );
  return response.data;
}

export async function getJobCandidateFit(
  jobId: string,
  candidateId: string,
): Promise<JobFitResponse> {
  const response = await apiClient.get<JobFitResponse>(
    `/screening/jobs/${jobId}/candidates/${candidateId}/fit`,
  );
  return response.data;
}

// ─── Candidate Evidence Intelligence (Phase 3) ─────────────────────

export async function getCandidateIntelligence(
  candidateId: string,
): Promise<CandidateEvidenceIntelResponse> {
  const response = await apiClient.get<CandidateEvidenceIntelResponse>(
    `/screening/candidates/${candidateId}/intelligence`,
  );
  return response.data;
}

export async function getCandidateJobIntelligence(
  jobId: string,
  candidateId: string,
): Promise<JobIntelligenceResponse> {
  const response = await apiClient.get<JobIntelligenceResponse>(
    `/screening/jobs/${jobId}/candidates/${candidateId}/intelligence`,
  );
  return response.data;
}

export async function compareCandidates(
  jobId: string,
  candidateIds: string[],
): Promise<CandidateComparisonResponse> {
  const response = await apiClient.post<CandidateComparisonResponse>(
    `/screening/jobs/${jobId}/compare`,
    { candidate_ids: candidateIds },
  );
  return response.data;
}

export async function getMyMatch(
  jobId: string,
): Promise<CandidateMatchReport> {
  const response = await apiClient.get<CandidateMatchReport>(
    `/screening/jobs/${jobId}/my-match`,
  );
  return response.data;
}

export async function getMyScores(): Promise<ScreeningResult[]> {
  const response = await apiClient.get<ScreeningResult[]>(
    "/screening/my-scores",
  );
  return response.data;
}

// ─── AI Intelligence APIs ─────────────────────────────────────────

export async function aiSearch(
  params: AISearchRequest,
): Promise<AISearchResponse> {
  const response = await apiClient.post<AISearchResponse>(
    "/ai/search",
    params,
  );
  return response.data;
}

export async function getCandidateSummary(
  candidateId: string,
  jobId?: string,
): Promise<CandidateAISummary> {
  const params = jobId ? `?job_id=${jobId}` : "";
  const response = await apiClient.get<CandidateAISummary>(
    `/ai/summary/${candidateId}${params}`,
  );
  return response.data;
}

export async function getMyAISummary(
  jobId?: string,
): Promise<CandidateAISummary> {
  const params = jobId ? `?job_id=${jobId}` : "";
  const response = await apiClient.get<CandidateAISummary>(
    `/ai/my-summary${params}`,
  );
  return response.data;
}

export async function getJobAISummary(
  jobId: string,
): Promise<JobAISummary> {
  const response = await apiClient.get<JobAISummary>(
    `/ai/job-summary/${jobId}`,
  );
  return response.data;
}

export async function getTopCandidates(
  jobId?: string,
  limit: number = 10,
): Promise<TopCandidatesResponse> {
  const params = new URLSearchParams();
  if (jobId) params.set("job_id", jobId);
  params.set("limit", String(limit));
  const response = await apiClient.get<TopCandidatesResponse>(
    `/ai/top-candidates?${params.toString()}`,
  );
  return response.data;
}

export async function getHiringRecommendation(
  jobId: string,
  candidateId: string,
): Promise<HiringRecommendationResponse> {
  const response = await apiClient.get<HiringRecommendationResponse>(
    `/ai/recommendation/${jobId}/${candidateId}`,
  );
  return response.data;
}

export async function getRecruiterAIDashboard(): Promise<RecruiterDashboardSummary> {
  const response = await apiClient.get<RecruiterDashboardSummary>(
    "/ai/recruiter-dashboard",
  );
  return response.data;
}

// ─── XAI (Explainable AI) APIs ─────────────────────────────────────

export async function getCandidateExplanation(
  candidateId: string,
  jobId?: string,
): Promise<CandidateExplanation> {
  const params = jobId ? `?job_id=${jobId}` : "";
  const response = await apiClient.get<CandidateExplanation>(
    `/xai/explain/${candidateId}${params}`,
  );
  return response.data;
}

export async function getMyExplanation(
  jobId?: string,
): Promise<CandidateExplanation> {
  const params = jobId ? `?job_id=${jobId}` : "";
  const response = await apiClient.get<CandidateExplanation>(
    `/xai/my-explain${params}`,
  );
  return response.data;
}

export async function getXAIComparison(
  candidateIds: string[],
  jobId: string,
): Promise<CandidateComparisonXAI> {
  const response = await apiClient.post<CandidateComparisonXAI>(
    "/xai/compare",
    { candidate_ids: candidateIds, job_id: jobId },
  );
  return response.data;
}
