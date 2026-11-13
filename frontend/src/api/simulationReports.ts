import apiClient from "./client";

export interface ReportIncludeOptions {
  include_candidate_details?: boolean;
  include_fairness?: boolean;
  include_explainability?: boolean;
  include_skill_impact?: boolean;
  include_ranking?: boolean;
  include_requirements?: boolean;
  include_threshold?: boolean;
  include_shortlist?: boolean;
  include_comparison?: boolean;
  include_limitations?: boolean;
  include_audit?: boolean;
}

export interface SimulationReportCreateRequest {
  report_type:
    | "simulation"
    | "candidate_impact"
    | "fairness_impact"
    | "comparison"
    | "sandbox"
    | "executive"
    | "technical";
  simulation_id?: string;
  execution_id?: string;
  sandbox_id?: string;
  comparison_scenario_ids?: string[];
  format?: "web" | "pdf" | "json" | "csv";
  title?: string;
  description?: string;
  include?: ReportIncludeOptions;
}

export interface SimulationReportListItem {
  id: string;
  organization_id: string | null;
  sandbox_id: string | null;
  scenario_id: string | null;
  execution_id: string | null;
  job_id: string | null;
  created_by: string;
  report_type: string;
  title: string;
  description: string | null;
  status: string;
  format: string;
  report_version: string;
  job_title: string;
  scenario_name: string;
  sandbox_name: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface SimulationReportListResponse {
  items: SimulationReportListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SimulationReportResponse {
  id: string;
  organization_id: string | null;
  sandbox_id: string | null;
  scenario_id: string | null;
  execution_id: string | null;
  job_id: string | null;
  created_by: string;
  report_type: string;
  title: string;
  description: string | null;
  status: string;
  format: string;
  parameters: Record<string, unknown> | null;
  report_data: Record<string, unknown> | null;
  error_message: string | null;
  report_version: string;
  job_title: string;
  scenario_name: string;
  sandbox_name: string;
  created_by_name: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimulationReportStatusResponse {
  report_id: string;
  status: string;
  error_message: string | null;
  completed_at: string | null;
}

export const simulationReportApi = {
  create: (data: SimulationReportCreateRequest) =>
    apiClient
      .post<SimulationReportResponse>("/simulation-reports", data)
      .then((r) => r.data),

  list: (params?: { page?: number; page_size?: number }) =>
    apiClient
      .get<SimulationReportListResponse>("/simulation-reports", { params })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient
      .get<SimulationReportResponse>(`/simulation-reports/${id}`)
      .then((r) => r.data),

  getStatus: (id: string) =>
    apiClient
      .get<SimulationReportStatusResponse>(`/simulation-reports/${id}/status`)
      .then((r) => r.data),

  getJson: (id: string) =>
    apiClient
      .get<Record<string, unknown>>(`/simulation-reports/${id}/json`)
      .then((r) => r.data),

  getPdfUrl: (id: string) => `/api/v1/simulation-reports/${id}/pdf`,

  getCsvUrl: (id: string, section: string = "candidate_impact") =>
    `/api/v1/simulation-reports/${id}/csv?section=${section}`,


  // Authenticated binary downloads (need Authorization header; window.open can't send it)
  getPdfBlob: (id: string) =>
    apiClient
      .get<Blob>(`/simulation-reports/${id}/pdf`, { responseType: "blob" })
      .then((r) => r.data),

  getCsvBlob: (id: string, section: string = "candidate_impact") =>
    apiClient
      .get<Blob>(`/simulation-reports/${id}/csv?section=${section}`, { responseType: "blob" })
      .then((r) => r.data),
  delete: (id: string) =>
    apiClient.delete(`/simulation-reports/${id}`),
};
