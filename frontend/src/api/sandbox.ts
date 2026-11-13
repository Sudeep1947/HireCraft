import apiClient from "./client";
import type {
  SandboxCreate,
  SandboxListResponse,
  SandboxResponse,
  SandboxUpdate,
  StrategyCreate,
  StrategyDuplicate,
  StrategyListResponse,
  StrategyResponse,
  StrategyUpdate,
  SandboxCompareRequest,
  SandboxActivityResponse,
} from "../types/sandbox";

export const sandboxApi = {
  // ─── Sandbox CRUD ────────────────────────────────────────────

  list: () =>
    apiClient.get<SandboxListResponse>("/sandboxes").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<SandboxResponse>(`/sandboxes/${id}`).then((r) => r.data),

  create: (data: SandboxCreate) =>
    apiClient.post<SandboxResponse>("/sandboxes", data).then((r) => r.data),

  update: (id: string, data: SandboxUpdate) =>
    apiClient.patch<SandboxResponse>(`/sandboxes/${id}`, data).then((r) => r.data),

  archive: (id: string) =>
    apiClient.post<SandboxResponse>(`/sandboxes/${id}/archive`).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/sandboxes/${id}`).then((r) => r.data),

  // ─── Strategy Management ─────────────────────────────────────

  listStrategies: (sandboxId: string) =>
    apiClient.get<StrategyListResponse>(`/sandboxes/${sandboxId}/strategies`).then((r) => r.data),

  getStrategy: (sandboxId: string, strategyId: string) =>
    apiClient.get<StrategyResponse>(`/sandboxes/${sandboxId}/strategies/${strategyId}`).then((r) => r.data),

  createStrategy: (sandboxId: string, data: StrategyCreate) =>
    apiClient.post<StrategyResponse>(`/sandboxes/${sandboxId}/strategies`, data).then((r) => r.data),

  updateStrategy: (sandboxId: string, strategyId: string, data: StrategyUpdate) =>
    apiClient.patch<StrategyResponse>(`/sandboxes/${sandboxId}/strategies/${strategyId}`, data).then((r) => r.data),

  duplicateStrategy: (sandboxId: string, strategyId: string, data: StrategyDuplicate) =>
    apiClient.post<StrategyResponse>(`/sandboxes/${sandboxId}/strategies/${strategyId}/duplicate`, data).then((r) => r.data),

  removeStrategy: (sandboxId: string, strategyId: string) =>
    apiClient.delete(`/sandboxes/${sandboxId}/strategies/${strategyId}`).then((r) => r.data),

  // ─── Comparison ──────────────────────────────────────────────

  compare: (sandboxId: string, data: SandboxCompareRequest) =>
    apiClient.post(`/sandboxes/${sandboxId}/compare`, data).then((r) => r.data),

  // ─── Activity ────────────────────────────────────────────────

  getActivity: (sandboxId: string) =>
    apiClient.get<SandboxActivityResponse>(`/sandboxes/${sandboxId}/activity`).then((r) => r.data),
};
