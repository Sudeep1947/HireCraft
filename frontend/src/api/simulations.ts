import apiClient from "./client";
import type {
  SimulationChangesResponse,
  SimulationExecution,
  SimulationExecutionListResponse,
  SimulationResultsParams,
  SimulationResultsResponse,
  SimulationScenario,
  SimulationScenarioFormData,
  SimulationScenarioListResponse,
  SimulationScenarioUpdateData,
  SimulationShortlistApplyRequest,
  SimulationShortlistApplyResponse,
  SimulationStatusResponse,
  SimulationSummaryResponse,
  SimulationValidationResponse,
} from "../types/simulations";
import type {
  CandidateImpactListResponse,
  CandidateSingleImpactResponse,
  RankingImpactResponse,
} from "../types/rankingImpact";
import type {
  CandidateRequirementImpactDetailResponse,
  CandidateRequirementImpactListResponse,
  RequirementImpactListResponse,
  RequirementImpactResponse,
} from "../types/requirementImpact";
import type {
  CombinedThresholdShortlistResponse,
  ThresholdImpactResponse,
  ShortlistImpactResponse,
} from "../types/thresholdShortlist";
import type { FairnessImpactResponse } from "../types/fairnessImpact";
import type { ExplainabilityImpactResponse } from "../types/explainabilityImpact";
import type { SkillImpactResponse } from "../types/skillImpact";
import type {
  MultiScenarioComparisonResponse,
  SimulationComparisonRequest,
} from "../types/simulationComparison";
import type {
  NLInterpretRequest,
  NLInterpretResponse,
  NLConfirmRequest,
  NLConfirmResponse,
  NLExplainRequest,
  NLExplainResponse,
} from "../types/simulationIntent";

export const simulationApi = {
  list: () =>
    apiClient.get<SimulationScenarioListResponse>("/simulations").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<SimulationScenario>(`/simulations/${id}`).then((r) => r.data),

  getStatus: (id: string) =>
    apiClient.get<SimulationStatusResponse>(`/simulations/${id}/status`).then((r) => r.data),

  create: (data: SimulationScenarioFormData) =>
    apiClient.post<SimulationScenario>("/simulations", data).then((r) => r.data),

  update: (id: string, data: SimulationScenarioUpdateData) =>
    apiClient.patch<SimulationScenario>(`/simulations/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/simulations/${id}`).then((r) => r.data),

  validate: (id: string) =>
    apiClient.post<SimulationValidationResponse>(`/simulations/${id}/validate`).then((r) => r.data),

  getChanges: (id: string) =>
    apiClient.get<SimulationChangesResponse>(`/simulations/${id}/changes`).then((r) => r.data),

  // ─── Phase 3: execution engine ────────────────────────────────────

  run: (id: string) =>
    apiClient.post<SimulationExecution>(`/simulations/${id}/run`).then((r) => r.data),

  listExecutions: (id: string) =>
    apiClient.get<SimulationExecutionListResponse>(`/simulations/${id}/executions`).then((r) => r.data),

  getExecution: (simulationId: string, executionId: string) =>
    apiClient
      .get<SimulationExecution>(`/simulations/${simulationId}/executions/${executionId}`)
      .then((r) => r.data),

  cancelExecution: (simulationId: string, executionId: string) =>
    apiClient
      .post<SimulationExecution>(`/simulations/${simulationId}/executions/${executionId}/cancel`)
      .then((r) => r.data),

  listResults: (simulationId: string, params?: SimulationResultsParams) =>
    apiClient
      .get<SimulationResultsResponse>(`/simulations/${simulationId}/results`, { params })
      .then((r) => r.data),

  getSummary: (simulationId: string, executionId?: string) =>
    apiClient
      .get<SimulationSummaryResponse>(`/simulations/${simulationId}/summary`, {
        params: executionId ? { execution_id: executionId } : undefined,
      })
      .then((r) => r.data),

  // ─── Optional manual shortlist (human-confirmed) ─────────────────

  applyShortlist: (simulationId: string, data: SimulationShortlistApplyRequest) =>
    apiClient
      .post<SimulationShortlistApplyResponse>(
        `/simulations/${simulationId}/apply-shortlist`,
        data,
      )
      .then((r) => r.data),

  // ─── Phase 4: Ranking Impact Analysis ─────────────────────────────

  getRankingImpact: (simulationId: string, executionId?: string) =>
    apiClient
      .get<RankingImpactResponse>(`/simulations/${simulationId}/ranking-impact`, {
        params: executionId ? { execution_id: executionId } : undefined,
      })
      .then((r) => r.data),

  getRankingImpactCandidates: (
    simulationId: string,
    params?: {
      execution_id?: string;
      page?: number;
      page_size?: number;
      movement?: string;
      shortlist?: string;
      qualification?: string;
      sort_by?: string;
      order?: string;
    },
  ) =>
    apiClient
      .get<CandidateImpactListResponse>(
        `/simulations/${simulationId}/ranking-impact/candidates`,
        { params },
      )
      .then((r) => r.data),

  getCandidateImpactDetail: (
    simulationId: string,
    candidateId: string,
    executionId?: string,
  ) =>
    apiClient
      .get<CandidateSingleImpactResponse>(
        `/simulations/${simulationId}/ranking-impact/candidates/${candidateId}`,
        { params: executionId ? { execution_id: executionId } : undefined },
      )
      .then((r) => r.data),

  // ─── Phase 5: Requirement Impact Analysis ─────────────────────────

  getRequirementImpact: (simulationId: string, executionId?: string) =>
    apiClient
      .get<RequirementImpactResponse>(`/simulations/${simulationId}/requirement-impact`, {
        params: executionId ? { execution_id: executionId } : undefined,
      })
      .then((r) => r.data),

  getRequirementImpactRequirements: (
    simulationId: string,
    params?: {
      execution_id?: string;
      page?: number;
      page_size?: number;
    },
  ) =>
    apiClient
      .get<RequirementImpactListResponse>(
        `/simulations/${simulationId}/requirement-impact/requirements`,
        { params },
      )
      .then((r) => r.data),

  getRequirementImpactCandidates: (
    simulationId: string,
    params?: {
      execution_id?: string;
      page?: number;
      page_size?: number;
      requirement?: string;
      requirement_type?: string;
      newly_qualified?: boolean;
      newly_disqualified?: boolean;
      sort_by?: string;
      order?: string;
    },
  ) =>
    apiClient
      .get<CandidateRequirementImpactListResponse>(
        `/simulations/${simulationId}/requirement-impact/candidates`,
        { params },
      )
      .then((r) => r.data),

  getCandidateRequirementImpactDetail: (
    simulationId: string,
    candidateId: string,
    executionId?: string,
  ) =>
    apiClient
      .get<CandidateRequirementImpactDetailResponse>(
        `/simulations/${simulationId}/requirement-impact/candidates/${candidateId}`,
        { params: executionId ? { execution_id: executionId } : undefined },
      )
      .then((r) => r.data),

  // ─── Phase 6: Threshold & Shortlist Impact Analysis ─────────────

  getThresholdImpact: (simulationId: string, executionId?: string, boundaryRange?: number) =>
    apiClient
      .get<ThresholdImpactResponse>(`/simulations/${simulationId}/threshold-impact`, {
        params: {
          ...(executionId ? { execution_id: executionId } : {}),
          ...(boundaryRange !== undefined ? { boundary_range: boundaryRange } : {}),
        },
      })
      .then((r) => r.data),

  getShortlistImpact: (simulationId: string, executionId?: string, boundaryRange?: number) =>
    apiClient
      .get<ShortlistImpactResponse>(`/simulations/${simulationId}/shortlist-impact`, {
        params: {
          ...(executionId ? { execution_id: executionId } : {}),
          ...(boundaryRange !== undefined ? { boundary_range: boundaryRange } : {}),
        },
      })
      .then((r) => r.data),

  getCombinedThresholdShortlistImpact: (
    simulationId: string,
    executionId?: string,
    boundaryRange?: number,
  ) =>
    apiClient
      .get<CombinedThresholdShortlistResponse>(
        `/simulations/${simulationId}/threshold-shortlist-impact`,
        {
          params: {
            ...(executionId ? { execution_id: executionId } : {}),
            ...(boundaryRange !== undefined ? { boundary_range: boundaryRange } : {}),
          },
        },
      )
      .then((r) => r.data),

  // ─── Phase 7: Fairness Impact Analysis ───────────────────────────

  getFairnessImpact: (
    simulationId: string,
    executionId?: string,
    minimumGroupSize?: number,
  ) =>
    apiClient
      .get<FairnessImpactResponse>(
        `/simulations/${simulationId}/fairness-impact`,
        {
          params: {
            ...(executionId ? { execution_id: executionId } : {}),
            ...(minimumGroupSize !== undefined
              ? { minimum_group_size: minimumGroupSize }
              : {}),
          },
        },
      )
      .then((r) => r.data),

  // ─── Phase 8: Explainability Impact Analysis ───────────────────

  getExplainabilityImpact: (
    simulationId: string,
    executionId?: string,
  ) =>
    apiClient
      .get<ExplainabilityImpactResponse>(
        `/simulations/${simulationId}/explainability-impact`,
        {
          params: {
            ...(executionId ? { execution_id: executionId } : {}),
          },
        },
      )
      .then((r) => r.data),

  // ─── Phase 9: Skill Impact Analysis ─────────────────────────

  getSkillImpact: (simulationId: string, executionId?: string) =>
    apiClient
      .get<SkillImpactResponse>(
        `/simulations/${simulationId}/skill-impact`,
        {
          params: {
            ...(executionId ? { execution_id: executionId } : {}),
          },
        },
      )
      .then((r) => r.data),

  // ─── Phase 10: Multi-Scenario Comparison ─────────────────────

  compareScenarios: (data: SimulationComparisonRequest) =>
    apiClient
      .post<MultiScenarioComparisonResponse>("/simulations/compare", data)
      .then((r) => r.data),

  // ─── Phase 11: Natural Language Simulation Agent ─────────────

  interpretNL: (data: NLInterpretRequest) =>
    apiClient
      .post<NLInterpretResponse>("/simulations/interpret", data)
      .then((r) => r.data),

  confirmNL: (data: NLConfirmRequest) =>
    apiClient
      .post<NLConfirmResponse>("/simulations/confirm", data)
      .then((r) => r.data),

  explainResults: (data: NLExplainRequest) =>
    apiClient
      .post<NLExplainResponse>("/simulations/explain", data)
      .then((r) => r.data),
};