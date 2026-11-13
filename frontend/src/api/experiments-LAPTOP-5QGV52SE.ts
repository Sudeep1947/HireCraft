import apiClient from "./client";
import type {
  ExperimentCreateRequest,
  ExperimentListResponse,
  ExperimentResponse,
  ExperimentStatusResponse,
  ExperimentResultsResponse,
  SensitivityAnalysisResponse,
  RobustnessAnalysisResponse,
  StabilityAnalysisResponse,
  FairnessSensitivityResponse,
} from "../types/simulationExperiments";

export const experimentApi = {
  create: (data: ExperimentCreateRequest) =>
    apiClient
      .post<ExperimentResponse>("/simulation-experiments", data)
      .then((r) => r.data),

  list: (params?: { page?: number; page_size?: number }) =>
    apiClient
      .get<ExperimentListResponse>("/simulation-experiments", { params })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient
      .get<ExperimentResponse>(`/simulation-experiments/${id}`)
      .then((r) => r.data),

  update: (id: string, data: Partial<ExperimentCreateRequest>) =>
    apiClient
      .patch<ExperimentResponse>(`/simulation-experiments/${id}`, data)
      .then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/simulation-experiments/${id}`),

  execute: (id: string) =>
    apiClient
      .post<ExperimentStatusResponse>(`/simulation-experiments/${id}/execute`, {})
      .then((r) => r.data),

  cancel: (id: string) =>
    apiClient
      .post<ExperimentStatusResponse>(`/simulation-experiments/${id}/cancel`)
      .then((r) => r.data),

  getStatus: (id: string) =>
    apiClient
      .get<ExperimentStatusResponse>(`/simulation-experiments/${id}/status`)
      .then((r) => r.data),

  getResults: (id: string) =>
    apiClient
      .get<ExperimentResultsResponse>(`/simulation-experiments/${id}/results`)
      .then((r) => r.data),

  getSensitivity: (id: string) =>
    apiClient
      .get<SensitivityAnalysisResponse>(`/simulation-experiments/${id}/sensitivity`)
      .then((r) => r.data),

  getRobustness: (id: string) =>
    apiClient
      .get<RobustnessAnalysisResponse>(`/simulation-experiments/${id}/robustness`)
      .then((r) => r.data),

  getStability: (id: string) =>
    apiClient
      .get<StabilityAnalysisResponse>(`/simulation-experiments/${id}/stability`)
      .then((r) => r.data),

  getFairnessSensitivity: (id: string) =>
    apiClient
      .get<FairnessSensitivityResponse>(
        `/simulation-experiments/${id}/fairness-sensitivity`,
      )
      .then((r) => r.data),
};
