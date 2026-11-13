/* ─── Phase 12: Hiring Strategy Sandbox Types ────────────────── */

export interface SandboxListItem {
  id: string;
  organization_id: string | null;
  job_id: string;
  created_by: string;
  name: string;
  status: string;
  job_title: string;
  company: string;
  created_by_name: string;
  strategy_count: number;
  completed_count: number;
  created_at: string;
  updated_at: string;
}

export interface SandboxResponse {
  id: string;
  organization_id: string | null;
  job_id: string;
  created_by: string;
  name: string;
  description: string | null;
  status: string;
  baseline_snapshot: Record<string, unknown>;
  metadata: Record<string, unknown> | null;
  job_title: string;
  company: string;
  created_by_name: string;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SandboxListResponse {
  items: SandboxListItem[];
  total: number;
}

export interface SandboxCreate {
  job_id: string;
  name: string;
  description?: string;
}

export interface SandboxUpdate {
  name?: string;
  description?: string;
}

export interface StrategyListItem {
  id: string;
  scenario_id: string;
  parent_strategy_id: string | null;
  branch_name: string | null;
  name: string;
  status: string;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
  job_title: string;
  threshold: number;
  shortlist_size: number;
  skills_weight: number;
  experience_weight: number;
  total_candidates: number;
  qualified_candidates: number;
  shortlisted_candidates: number;
}

export interface StrategyResponse {
  id: string;
  sandbox_id: string;
  scenario_id: string;
  parent_strategy_id: string | null;
  branch_name: string | null;
  name: string;
  description: string | null;
  tags: string[] | null;
  notes: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface StrategyListResponse {
  items: StrategyListItem[];
  total: number;
}

export interface StrategyCreate {
  name: string;
  description?: string;
  simulation_config?: Record<string, unknown>;
  tags?: string[];
  notes?: string;
}

export interface StrategyDuplicate {
  name: string;
  description?: string;
  branch: boolean;
  tags?: string[];
  notes?: string;
}

export interface StrategyUpdate {
  name?: string;
  description?: string;
  tags?: string[];
  notes?: string;
}

export interface SandboxCompareRequest {
  strategy_ids: string[];
}

export interface SandboxActivityItem {
  timestamp: string;
  event_type: string;
  description: string;
  user_name: string;
  metadata: Record<string, unknown> | null;
}

export interface SandboxActivityResponse {
  items: SandboxActivityItem[];
}

export interface SandboxPreset {
  name: string;
  label: string;
  description: string;
  config: Record<string, unknown>;
}

export const SANDBOX_PRESETS: SandboxPreset[] = [
  {
    name: "balanced",
    label: "Balanced",
    description: "Equal emphasis on skills and experience",
    config: {
      scoring_weights: {
        skills: 0.35, experience: 0.25, education: 0.15,
        projects: 0.15, certifications: 0.05, location: 0.02,
        employment_type: 0.01, semantic: 0.02,
      },
      threshold: 70, shortlist_size: 10,
      requirements: { mandatory_skills: [], preferred_skills: [], experience: null, education: null },
    },
  },
  {
    name: "skills_focused",
    label: "Skills Focus",
    description: "Maximum emphasis on technical skills",
    config: {
      scoring_weights: {
        skills: 0.50, experience: 0.15, education: 0.10,
        projects: 0.15, certifications: 0.05, location: 0.02,
        employment_type: 0.01, semantic: 0.02,
      },
      threshold: 70, shortlist_size: 10,
      requirements: { mandatory_skills: [], preferred_skills: [], experience: null, education: null },
    },
  },
  {
    name: "experience_focused",
    label: "Experience Focus",
    description: "Maximum emphasis on work experience",
    config: {
      scoring_weights: {
        skills: 0.25, experience: 0.45, education: 0.10,
        projects: 0.10, certifications: 0.05, location: 0.02,
        employment_type: 0.01, semantic: 0.02,
      },
      threshold: 70, shortlist_size: 10,
      requirements: { mandatory_skills: [], preferred_skills: [], experience: null, education: null },
    },
  },
  {
    name: "high_threshold",
    label: "High Threshold",
    description: "Raise minimum score to 85",
    config: {
      scoring_weights: {
        skills: 0.40, experience: 0.25, education: 0.15,
        projects: 0.20, certifications: 0.00, location: 0.00,
        employment_type: 0.00, semantic: 0.00,
      },
      threshold: 85, shortlist_size: 10,
      requirements: { mandatory_skills: [], preferred_skills: [], experience: null, education: null },
    },
  },
  {
    name: "broad_shortlist",
    label: "Broad Shortlist",
    description: "Consider top 25 candidates",
    config: {
      scoring_weights: {
        skills: 0.40, experience: 0.25, education: 0.15,
        projects: 0.20, certifications: 0.00, location: 0.00,
        employment_type: 0.00, semantic: 0.00,
      },
      threshold: 70, shortlist_size: 25,
      requirements: { mandatory_skills: [], preferred_skills: [], experience: null, education: null },
    },
  },
];
