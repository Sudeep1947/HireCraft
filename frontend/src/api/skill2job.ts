import apiClient from "./client";
import type {
  CuratedJob,
  CuratedJobCounts,
  CuratedJobPage,
  JobMatchDetail,
  JobMatchEntry,
  JobSkillGraph,
  OpportunityDashboard,
  PerceptionDetail,
  PerceptionListResponse,
  PerceptionStatus,
  PipelineTraceSummary,
  Skill2JobCapabilities,
  Skill2JobHealth,
  Skill2JobProfile,
  SkillDemand,
  SkillGapAnalysis,
  SkillGapSummary,
  SimulateRequest,
  SimulationResult,
  TrainingPlan,
  TrainingProgress,
} from "../types/skill2job";

export const skill2jobApi = {
  getHealth: () =>
    apiClient.get<Skill2JobHealth>("/skill2job/health").then((r) => r.data),
  getCapabilities: () =>
    apiClient.get<Skill2JobCapabilities>("/skill2job/capabilities").then((r) => r.data),
  getProfile: () =>
    apiClient.get<Skill2JobProfile>("/skill2job/profile").then((r) => r.data),

  // Phase 2 — perception
  getPerceptionStatus: () =>
    apiClient.get<PerceptionStatus>("/skill2job/perception/status").then((r) => r.data),
  getPerceptions: () =>
    apiClient.get<PerceptionListResponse>("/skill2job/perception").then((r) => r.data),
  getPerceptionDetail: (perceptionId: string) =>
    apiClient.get<PerceptionDetail>(`/skill2job/perception/${perceptionId}`).then((r) => r.data),
  deletePerception: (perceptionId: string) =>
    apiClient.delete<{ deleted: boolean; perception_id: string }>(`/skill2job/perception/${perceptionId}`).then((r) => r.data),
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<{ perception_id: string; result: Record<string, unknown>; skill_count: number; processing_status: string; processing_message: string | null }>("/skill2job/perception/upload", form)
      .then((r) => r.data);
  },
  perceiveText: (text: string) => {
    const form = new FormData();
    form.append("text", text);
    return apiClient
      .post<{ perception_id: string; result: Record<string, unknown>; skill_count: number; processing_status: string; processing_message: string | null }>("/skill2job/perception/text", form)
      .then((r) => r.data);
  },

  // Phase 3 — profile agent
  buildDossier: () =>
    apiClient.post<Record<string, unknown>>("/skill2job/profile/agent/dossier").then((r) => r.data),
  getDossier: () =>
    apiClient
      .get<Record<string, unknown> | null>("/skill2job/profile/agent/dossier")
      .then((r) => r.data),

  // Phase 4 — local job intelligence
  getJobCounts: () =>
    apiClient.get<CuratedJobCounts>("/skill2job/jobs/counts").then((r) => r.data),
  getCatalog: (params?: Record<string, string | number | boolean>) =>
    apiClient.get<CuratedJobPage>("/skill2job/jobs/catalog", { params }).then((r) => r.data),
  getJob: (jobId: string) =>
    apiClient.get<CuratedJob>(`/skill2job/jobs/${jobId}`).then((r) => r.data),
  getSkillDemand: () =>
    apiClient.get<SkillDemand>("/skill2job/skills/demand").then((r) => r.data),

  // Phase 5 — job matching
  runMatching: (params?: { limit?: number }) =>
    apiClient
      .post<JobMatchEntry[]>("/skill2job/jobs/match", params ?? {})
      .then((r) => r.data),
  getMatches: (limit = 20) =>
    apiClient.get<JobMatchEntry[]>("/skill2job/jobs/match", { params: { limit } }).then((r) => r.data),

  // Phase 2 extensions — explainable per-job detail
  getJobMatch: (jobId: string) =>
    apiClient.get<JobMatchDetail>(`/skill2job/jobs/${jobId}/match`).then((r) => r.data),
  getJobGaps: (jobId: string) =>
    apiClient.get<SkillGapAnalysis>(`/skill2job/jobs/${jobId}/gaps`).then((r) => r.data),
  getJobSkillGraph: (jobId: string) =>
    apiClient.get<JobSkillGraph>(`/skill2job/jobs/${jobId}/graph`).then((r) => r.data),

  // Phase 6 — skill gap
  analyzeSkillGaps: (params?: { limit?: number }) =>
    apiClient
      .post<SkillGapAnalysis[]>("/skill2job/skillgap/analyze", params ?? {})
      .then((r) => r.data),
  getSkillGaps: () =>
    apiClient
      .get<SkillGapAnalysis[]>("/skill2job/skillgap/analyze")
      .then((r) => r.data),
  getSkillGapSummary: () =>
    apiClient.get<SkillGapSummary>("/skill2job/skillgap/summary").then((r) => r.data),

  // Phase 7 — opportunity unlock
  runSimulation: (request: SimulateRequest) =>
    apiClient.post<SimulationResult>("/skill2job/opportunity/simulate", request).then((r) => r.data),
  getOpportunityDashboard: () =>
    apiClient.get<OpportunityDashboard>("/skill2job/opportunity/dashboard").then((r) => r.data),

  // Phase 8 — training agent + LangGraph orchestration
  getTrainingPlan: () =>
    apiClient.get<TrainingPlan>("/skill2job/training/plan").then((r) => r.data),
  getTrainingProgress: () =>
    apiClient.get<TrainingProgress>("/skill2job/training/progress").then((r) => r.data),
  completeModule: (moduleKey: string) =>
    apiClient
      .post<Record<string, unknown>>("/skill2job/training/progress", {
        module_key: moduleKey,
        status: "completed",
      })
      .then((r) => r.data),
  runPipeline: () =>
    apiClient
      .post<Record<string, unknown>>("/skill2job/training/run")
      .then((r) => r.data),
  getPipelineTraces: () =>
    apiClient
      .get<{ items: PipelineTraceSummary[]; total: number } | PipelineTraceSummary[]>("/skill2job/training/traces")
      .then((r) => (Array.isArray(r.data) ? r.data : (r.data?.items ?? []))),

  // Phase 9 -- Time-to-Ready Engine
  calculateTimeToReady: (request: {
    job_id?: string;
    job_title?: string;
    hours_per_week?: number;
    free_only?: boolean;
    optimization_mode?: string;
  }) =>
    apiClient
      .post<Record<string, unknown>>("/skill2job/time-to-ready/calculate", request)
      .then((r) => r.data),

  simulateWhatIf: (request: { skills_to_add: string[]; hours_per_week?: number }) =>
    apiClient
      .post<Record<string, unknown>>("/skill2job/time-to-ready/simulate", request)
      .then((r) => r.data),

  compareTargetJobs: (hoursPerWeek = 10) =>
    apiClient
      .get<Record<string, unknown>[]>("/skill2job/time-to-ready/compare", {
        params: { hours_per_week: hoursPerWeek },
      })
      .then((r) => r.data),

  // ─── Overview Aggregation ────────────────────────────────────────

  getOverview: () =>
    apiClient.get<import("../types/skill2job").Skill2JobOverview>("/skill2job/overview").then((r) => r.data),

  // ─── Skill Graph & Skill Proof ───────────────────────────────────

  getSkillGraph: () =>
    apiClient
      .get<import("../types/skill2job").Skill2JobSkillGraph>("/skill2job/skill-graph")
      .then((r) => r.data),

  getSkillProof: () =>
    apiClient
      .get<import("../types/skill2job").Skill2JobSkillProof>("/skill2job/skill-proof")
      .then((r) => r.data),

  // ─── Phase 3: Skill Proof Detail ─────────────────────────────────

  getSkillProofDetail: (skillId: string) =>
    apiClient
      .get<import("../types/skill2job").SkillProofDetail>(`/skill2job/skill-proof/${encodeURIComponent(skillId)}`)
      .then((r) => r.data),

  // ─── Phase 3: Evidence-Aware Readiness ───────────────────────────

  getReadiness: (jobId: string) =>
    apiClient
      .get<import("../types/skill2job").ReadinessResult>(`/skill2job/readiness/${encodeURIComponent(jobId)}`)
      .then((r) => r.data),

  // ─── Phase 3: Per-Job Learning Plan ──────────────────────────────

  getLearningPlanForJob: (
    jobId: string,
    params?: {
      hours_per_week?: number;
      free_only?: boolean;
      optimization_mode?: string;
    }
  ) =>
    apiClient
      .get<import("../types/skill2job").LearningPlanForJob>(`/skill2job/learning/plan/${encodeURIComponent(jobId)}`, {
        params,
      })
      .then((r) => r.data),

  // ─── Phase 3: Multi-Job Comparison ───────────────────────────────

  compareJobs: (hoursPerWeek = 10) =>
    apiClient
      .get<import("../types/skill2job").OverviewTimeToReadyItem[]>("/skill2job/jobs/compare", {
        params: { hours_per_week: hoursPerWeek },
      })
      .then((r) => r.data),

  // ─── Voice Profile Agent ───────────────────────────────────────

  applyProfileReview: (request: {
    skills_to_add: string[];
    skills_to_exclude: string[];
    corrections: Array<{ field: string; value: string; note: string }>;
  }) =>
    apiClient
      .post<{
        applied_skills: Record<string, unknown>[];
        excluded_skills: string[];
        corrections_applied: Record<string, unknown>[];
      }>("/skill2job/profile/agent/review", request)
      .then((r) => r.data),

  // ─── Phase 3: Learning Progress State Update ─────────────────────

  updateLearningProgress: (
    moduleKey: string,
    evidenceState: string,
    learningHours: number = 0
  ) => {
    const formData = new FormData();
    formData.append("module_key", moduleKey);
    formData.append("evidence_state", evidenceState);
    formData.append("learning_hours", String(learningHours));
    return apiClient
      .post<import("../types/skill2job").LearningProgressUpdate>(
        "/skill2job/learning/progress",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      )
      .then((r) => r.data);
  },
};