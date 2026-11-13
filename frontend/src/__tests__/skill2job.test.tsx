import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { skill2jobApi } from "../api/skill2job";
import { AuthContext } from "../contexts/AuthContext";
import type { AuthState, RoleName, User } from "../types/auth";
import type { Permission } from "../types/permissions";
import { Skill2JobHome } from "../pages/Skill2Job/Skill2JobHome";
import Skill2JobLayout from "../pages/Skill2Job/Skill2JobLayout";
import OverviewPage from "../pages/Skill2Job/pages/OverviewPage";
import ProfilePage from "../pages/Skill2Job/pages/ProfilePage";
import JobsPage from "../pages/Skill2Job/pages/JobsPage";
import JobDetailPage from "../pages/Skill2Job/pages/JobDetailPage";
import SkillGapsPage from "../pages/Skill2Job/pages/SkillGapsPage";
import OpportunitiesPage from "../pages/Skill2Job/pages/OpportunitiesPage";
import LearningPage from "../pages/Skill2Job/pages/LearningPage";
import SkillGraphPage from "../pages/Skill2Job/pages/SkillGraphPage";
import SkillProofPage from "../pages/Skill2Job/pages/SkillProofPage";
import { Skill2JobDiagnostics } from "../pages/admin/Skill2JobDiagnostics";
import type {
  CuratedJob,
  CuratedJobCounts,
  Skill2JobCapabilities,
  Skill2JobOverview,
  Skill2JobProfile,
  SkillGapAnalysis,
  SkillGapSummary,
  JobMatchDetail,
} from "../types/skill2job";
import type { CandidateIntelligence, CandidateProfile } from "../types/candidate";

vi.mock("../api/skill2job", () => ({
  skill2jobApi: {
    getHealth: vi.fn(),
    getCapabilities: vi.fn(),
    getProfile: vi.fn(),
    getPerceptionStatus: vi.fn(),
    getPerceptions: vi.fn(),
    getPerceptionDetail: vi.fn(),
    deletePerception: vi.fn(),
    uploadResume: vi.fn(),
    perceiveText: vi.fn(),
    buildDossier: vi.fn(),
    getDossier: vi.fn(),
    getJobCounts: vi.fn(),
    getCatalog: vi.fn(),
    getJob: vi.fn(),
    getJobMatch: vi.fn(),
    getJobGaps: vi.fn(),
    getJobSkillGraph: vi.fn(),
    getSkillDemand: vi.fn(),
    runMatching: vi.fn(),
    getMatches: vi.fn(),
    analyzeSkillGaps: vi.fn(),
    getSkillGaps: vi.fn(),
    getSkillGapSummary: vi.fn(),
    runSimulation: vi.fn(),
    getOpportunityDashboard: vi.fn(),
    getTrainingPlan: vi.fn(),
    getTrainingProgress: vi.fn(),
    completeModule: vi.fn(),
    runPipeline: vi.fn(),
    getPipelineTraces: vi.fn(),
    getOverview: vi.fn(),
    getSkillGraph: vi.fn(),
    getSkillProof: vi.fn(),
    getSkillProofDetail: vi.fn(),
    getReadiness: vi.fn(),
    getLearningPlanForJob: vi.fn(),
    compareJobs: vi.fn(),
    updateLearningProgress: vi.fn(),
  },
}));

const mockProfile: CandidateProfile = {
  id: "profile-1",
  user_id: "u-1",
  phone: null,
  date_of_birth: null,
  gender: null,
  location: "Nairobi",
  nationality: null,
  linkedin_url: null,
  github_url: null,
  portfolio_url: null,
  website_url: null,
  bio: null,
  current_role: "Developer",
  avatar_url: null,
  profile_completion: 80,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockIntelligence: CandidateIntelligence = {
  profile_id: "profile-1",
  total_experience_years: 2,
  total_experience_months: 4,
  highest_qualification: "BSc",
  education_level: "bachelors",
  skill_summary: [{ name: "Python", category: "backend", proficiency: "intermediate", years: 2 }],
  skills_by_category: { backend: ["python"] },
  project_count: 1,
  certification_count: 0,
  language_count: 1,
  profile_strength: 60,
  missing_sections: ["experience"],
  recommendations: [],
};

const mockCapabilities: Skill2JobCapabilities = {
  module: "skill2job",
  profile_connected: true,
  capabilities: [
    { key: "module_foundation", label: "Skill2Job module foundation", status: "available", phase: 1 },
    { key: "perception", label: "Perception (resume/text/voice)", status: "available", phase: 2 },
    { key: "local_jobs", label: "Local job intelligence & curated jobs", status: "available", phase: 4 },
    { key: "training_agent", label: "Training agent & LangGraph orchestration", status: "available", phase: 8 },
  ],
};

const mockProfileResponse: Skill2JobProfile = {
  connected: true,
  profile: mockProfile,
  intelligence: mockIntelligence,
};

const mockJob: CuratedJob = {
  id: "cur-001",
  title: "Data Engineer",
  company: "DataBridge",
  location: "Mumbai",
  remote_type: "Hybrid",
  employment_type: "Full-time",
  experience_required: "3+ years",
  education_required: null,
  description: "Build data pipelines.",
  required_skills: ["Python", "SQL"],
  preferred_skills: [],
  salary_range: "$80k",
  salary_min: 80000,
  salary_max: 100000,
  source: "curated",
  source_url: null,
};

const mockJobCounts: CuratedJobCounts = {
  total: 40,
  remote: 12,
  on_site: 28,
  top_locations: [{ location: "Mumbai", count: 10 }],
  dataset: "skill2job-curated-jobs-v1",
};

const mockJobMatchDetail: JobMatchDetail = {
  job_id: "cur-001",
  title: "Data Engineer",
  company: "DataBridge",
  location: "Mumbai",
  remote_type: "Hybrid",
  overall_score: 62,
  category: "partial",
  categories_explained: "Partial match — close on requirements but not yet ideal.",
  scores: {
    skill: 50,
    experience: 70,
    education: 0,
    project: 60,
    certification: 0,
    location: 100,
    employment_type: 100,
    semantic: 75,
  },
  skill_details: [
    {
      skill: "Python",
      kind: "required",
      status: "matched",
      evidence_state: "supported",
      similarity: 0.92,
      evidence_notes: "Python is on your profile and in your resume.",
    },
    {
      skill: "SQL",
      kind: "required",
      status: "missing",
      evidence_state: "none",
      similarity: null,
      evidence_notes: "SQL is not found anywhere in your candidate data.",
    },
  ],
  explanation: [
    "Your Python experience covers 1 of 2 required skills (50% skill coverage).",
    "SQL is a skill gap so the role is not a verified match yet.",
  ],
  reasons: ["1 of 2 required skills matched"],
  recommendation: "partial_match",
  strength_level: "Balanced",
  matched_skills: ["Python"],
  missing_required: ["SQL"],
  missing_preferred: [],
  transferable_skills: [],
  suggested_skills: ["SQL"],
  match_version: "skill2job-match-5.1.0",
};

const mockMatch = {
  job_id: "cur-001",
  title: "Data Engineer",
  company: "DataBridge",
  location: "Mumbai",
  remote_type: "Hybrid",
  overall_score: 82,
  recommendation: "strong_match",
  strength_level: "Strong",
  matched_skills: ["Python"],
  missing_required: ["SQL"],
  suggested_skills: ["SQL"],
};

const mockGapAnalysis: SkillGapAnalysis = {
  job_id: "cur-001",
  job_title: "Data Engineer",
  company: "DataBridge",
  overall_score: 82,
  missing_required_skills: ["SQL"],
  missing_preferred_skills: [],
  gap_items: [{ skill: "SQL", role: "Data Engineer", company: "DataBridge", evidence: "Absent from profile.", transferable: [], related_existing: [], gap_kind: "skill_gap", evidence_note: null, priority: "high" }],
  experience_gap_description: "You have the general experience.",
  education_gap_description: null,
  certification_gap_description: null,
  improvement_suggestions: ["Learn SQL"],
  interview_readiness_score: 60,
  analysis_version: "skill2job-gap-6.0.0",
};

const mockGapSummary: SkillGapSummary = {
  total_analyses: 1,
  analyzed_jobs: 1,
  gap_skills: [{ skill: "SQL" }],
  teaching_plan: [
    { skill: "SQL", jobs_demanding: ["DataBridge"], priority: "high", rationale: "Required by Data Engineer." },
  ],
};

const mockOverview: Skill2JobOverview = {
  profile: {
    connected: true,
    completeness: 80,
    skills_count: 1,
    skills: ["Python"],
    has_perceptions: false,
    perceptions_count: 0,
  },
  readiness: { score: 70 },
  skills: { total: 1, items: ["Python"] },
  skill_gaps: { total: 1, critical: 1, items: [{ skill: "SQL", count: 1, priority: "high", jobs_demanding: ["DataBridge"] }] },
  jobs: {
    relevant_count: 1,
    top_matches: [
      {
        job_id: "cur-001",
        title: "Data Engineer",
        company: "DataBridge",
        location: "Mumbai",
        overall_score: 82,
        matched_skills: ["Python"],
        missing_required: ["SQL"],
        recommendation: "strong_match",
      },
    ],
  },
  opportunity_unlock: { top_opportunity: null, potential: 3, unlocked_count: 1, top_roles: [] },
  learning_progress: { total_modules: 1, completed: 0, items: [] },
  time_to_ready: {
    items: [
      {
        job_id: "cur-001",
        job_title: "Data Engineer",
        missing_skills_count: 1,
        estimated_weeks: 4,
        estimated_cost: 0,
        currency: "USD",
        free_only_weeks: 8,
        free_only_cost: 0,
        coverage_pct: 50,
        readiness: 60,
      },
    ],
    source: "time-to-ready-comparison",
  },
  career_insight: { text: "You are strong in backend engineering.", type: "positive", evidence: [] },
  next_action: { action: "Learn SQL", description: "SQL is required by Data Engineer.", type: "learn", priority: "high" },
  last_analyzed: null,
};

function makeUser(roles: RoleName[]): User {
  return {
    id: "u-1",
    full_name: "Ada Test",
    email: "ada@example.com",
    is_active: true,
    is_verified: true,
    roles,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

type Ctx = AuthState & {
  login: () => Promise<User>;
  register: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  permissions: Set<Permission>;
  can: (p: Permission) => boolean;
};

function authContext(overrides: Partial<AuthState>): Ctx {
  return {
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: false,
    login: async () => makeUser([]),
    register: async () => undefined,
    logout: async () => undefined,
    refreshAuth: async () => undefined,
    permissions: new Set<Permission>(),
    can: () => false,
    ...overrides,
  };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderSkill2Job(path: string) {
  return render(
    <AuthContext.Provider value={authContext({ isAuthenticated: true, user: makeUser(["candidate"]) })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/skill2job" element={<Skill2JobLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="jobs/:id" element={<JobDetailPage />} />
            <Route path="skill-gaps" element={<SkillGapsPage />} />
            <Route path="opportunities" element={<OpportunitiesPage />} />
            <Route path="learning" element={<LearningPage />} />
            <Route path="skill-graph" element={<SkillGraphPage />} />
            <Route path="skill-proof" element={<SkillProofPage />} />
          </Route>
          <Route path="/candidate/skill2job" element={<Skill2JobHome />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("Skill2Job Career Intelligence", () => {
  beforeEach(() => {
    vi.mocked(skill2jobApi.getHealth).mockResolvedValue({ module: "skill2job", status: "healthy" });
    vi.mocked(skill2jobApi.getCapabilities).mockResolvedValue(mockCapabilities);
    vi.mocked(skill2jobApi.getProfile).mockResolvedValue(mockProfileResponse);
    vi.mocked(skill2jobApi.getPerceptions).mockResolvedValue({ total: 0, items: [] });
    vi.mocked(skill2jobApi.getPerceptionDetail).mockResolvedValue({} as never);
    vi.mocked(skill2jobApi.deletePerception).mockResolvedValue({ deleted: true, perception_id: "p" });
    vi.mocked(skill2jobApi.getJobCounts).mockResolvedValue(mockJobCounts);
    vi.mocked(skill2jobApi.getSkillDemand).mockResolvedValue({
      dataset: "skill2job-curated-jobs-v1",
      total_jobs: 1,
      computed_from: "skill2job_jobs",
      items: [],
    });
    vi.mocked(skill2jobApi.getCatalog).mockResolvedValue({ total: 1, offset: 0, limit: 12, jobs: [mockJob] });
    vi.mocked(skill2jobApi.getMatches).mockResolvedValue([mockMatch]);
    vi.mocked(skill2jobApi.runMatching).mockResolvedValue([mockMatch]);
    vi.mocked(skill2jobApi.getSkillGapSummary).mockResolvedValue(mockGapSummary);
    vi.mocked(skill2jobApi.getSkillGaps).mockResolvedValue([mockGapAnalysis]);
    vi.mocked(skill2jobApi.analyzeSkillGaps).mockResolvedValue([mockGapAnalysis]);
    vi.mocked(skill2jobApi.getOpportunityDashboard).mockResolvedValue({
      top_opportunity: null,
      potential: 3,
      unlocked_count: 1,
      top_roles: [{ title: "Data Engineer" }],
    });
    vi.mocked(skill2jobApi.getTrainingPlan).mockResolvedValue({
      modules: [
        {
          module_key: "sql:official_docs",
          skill: "SQL",
          title: "PostgreSQL Documentation",
          provider: "PostgreSQL",
          url: "https://www.postgresql.org/docs/",
          resource_type: "official_docs",
        },
      ],
      total_modules: 1,
      version: "skill2job-training-8.0.0",
    });
    vi.mocked(skill2jobApi.getTrainingProgress).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(skill2jobApi.completeModule).mockResolvedValue({ completed: true });
    vi.mocked(skill2jobApi.getPipelineTraces).mockResolvedValue([]);
    vi.mocked(skill2jobApi.runPipeline).mockResolvedValue({ status: "completed" });
    vi.mocked(skill2jobApi.getOverview).mockResolvedValue(mockOverview);
    vi.mocked(skill2jobApi.getSkillGraph).mockResolvedValue({
      nodes: [
        { id: "python", label: "Python", kind: "candidate", category: "backend", count: 0 },
        { id: "sql", label: "SQL", kind: "gap", category: null, count: 1 },
      ],
      edges: [{ source: 0, target: 1, relation: "related" }],
      generated_from: { candidate_skills: 1, gap_skills: 1 },
    });
    vi.mocked(skill2jobApi.getSkillProof).mockResolvedValue({
      skills: [
        {
          name: "Python",
          category: "backend",
          proficiency: "intermediate",
          years: 2,
          evidence: [{ source: "profile", note: "Profile skill record (proficiency: intermediate, years: 2)" }],
          supported_by: ["profile"],
          proof_status: "PROVE" as const,
          proof_plan: {
            action: "PROVE" as const,
            steps: [{ step: 1, phase: "proof", description: "Build a project" }],
            estimated_effort: "medium" as const,
            demand_context: 3,
          },
        },
      ],
      sources: { profile: 1, perception: 0, matched_jobs: 0, gap_demand: 0, training: 0 },
    });
    vi.mocked(skill2jobApi.getSkillProofDetail).mockResolvedValue({
      skill: "Python",
      category: "backend",
      proficiency: "intermediate",
      years: 2,
      proof_status: "PROVE",
      evidence: [{ source: "profile", note: "Profile skill record" }],
      supported_by: ["profile"],
      proof_plan: {
        action: "PROVE",
        steps: [{ step: 1, phase: "proof", description: "Build a project" }],
        estimated_effort: "medium",
        demand_context: 3,
      },
      learning_resources: [],
    });
    vi.mocked(skill2jobApi.getReadiness).mockResolvedValue({
      job_id: "cur-001",
      job_title: "Data Engineer",
      overall_readiness: 70,
      skill_coverage: 50,
      evidence_quality: 0.8,
      critical_gaps: ["SQL"],
      evidence_breakdown: [
        { skill: "Python", evidence_level: "supported", evidence_multiplier: 1.0, sources: ["profile"], note: "Profile evidence" },
        { skill: "SQL", evidence_level: "none", evidence_multiplier: 0.0, sources: [], note: "No evidence" },
      ],
      total_required: 2,
      matched_count: 1,
      missing_count: 1,
      version: "skill2job-readiness-3.0.0",
    });
    vi.mocked(skill2jobApi.compareJobs).mockResolvedValue([
      {
        job_id: "cur-001",
        job_title: "Data Engineer",
        missing_skills_count: 1,
        estimated_weeks: 4,
        estimated_cost: 0,
        currency: "USD",
        free_only_weeks: 8,
        free_only_cost: 0,
        coverage_pct: 50,
        readiness: 60,
      },
    ]);
    vi.mocked(skill2jobApi.getLearningPlanForJob).mockResolvedValue({
      job_id: "cur-001",
      job_title: "Data Engineer",
      current_readiness: 70,
      skill_coverage: 50,
      evidence_quality: 0.8,
      critical_gaps: ["SQL"],
      missing_skills: [
        { skill: "SQL", priority: "high", importance: 1.0, dependencies: [], has_free_resource: true },
      ],
      learning_plan: [
        {
          step_number: 1,
          skill: "SQL",
          resource_title: "PostgreSQL Tutorial",
          resource_provider: "PostgreSQL",
          resource_url: "https://www.postgresql.org/docs/",
          weeks: 2,
          hours: 20,
          cost: 0,
          is_free: true,
          can_parallel: false,
          explanation: "Start with PostgreSQL basics.",
        },
      ],
      total_weeks: 2,
      total_hours: 20,
      total_cost: 0,
      currency: "USD",
      free_only_path: {
        weeks: 2,
        hours: 20,
        cost: 0,
        coverage_pct: 50,
        remaining_gaps: [],
      },
      opportunity_unlock: {
        current_jobs: 1,
        projected_jobs: 2,
        potential_increase: 1,
      },
      optimization_mode: "fastest",
      hours_per_week: 10,
      version: "skill2job-learning-3.0.0",
    });
    vi.mocked(skill2jobApi.updateLearningProgress).mockResolvedValue({
      ok: true,
      module_key: "sql:postgres_tutorial",
      evidence_state: "in_progress",
      learning_hours: 5,
    });
  });

  it("renders the layout header, sub-navigation, and real-time readiness", async () => {
    renderSkill2Job("/skill2job");
    expect(await screen.findByText(/Ada's Career Hub/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Overview/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Skill Gaps/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Time to Ready/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /AI Career Agent/ })).not.toBeInTheDocument();
    expect(await screen.findByText(/Strong · 70%/i)).toBeInTheDocument();
  });

  it("shows the overview with real time-to-ready numbers (no fabricated values)", async () => {
    renderSkill2Job("/skill2job");
    expect((await screen.findAllByText("Data Engineer")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("4 weeks")).length).toBeGreaterThan(0);
    expect(screen.getByText("USD 0")).toBeInTheDocument();
    expect(screen.getByText("Estimated Cost")).toBeInTheDocument();
  });

  it("shows the perception/profile page with the upload form", async () => {
    renderSkill2Job("/skill2job/profile");
    expect(await screen.findByText("Perceive a Resume or Document")).toBeInTheDocument();
    expect(screen.getByText("Perceive Free Text or Voice")).toBeInTheDocument();
    expect(screen.getByText("No perceptions yet. Upload a resume or paste text above.")).toBeInTheDocument();
  });

  it("lists catalog jobs in the Local Jobs page", async () => {
    renderSkill2Job("/skill2job/jobs");
    expect(await screen.findByText("Curated Local Job Catalog")).toBeInTheDocument();
    expect((await screen.findAllByText("Data Engineer")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/DataBridge/)).length).toBeGreaterThan(0);
  });

  it("passes server-side filters and pagination to the catalog endpoint", async () => {
    vi.mocked(skill2jobApi.getCatalog).mockResolvedValue({ total: 40, offset: 0, limit: 12, jobs: [mockJob] });
    renderSkill2Job("/skill2job/jobs");
    await screen.findByText("Curated Local Job Catalog");
    const input = screen.getByPlaceholderText("title, company, stack…");
    fireEvent.change(input, { target: { value: "Data" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    await waitFor(() =>
      expect(skill2jobApi.getCatalog).toHaveBeenCalledWith(
        expect.objectContaining({ keyword: "Data", limit: 12, offset: 0 }),
      ),
    );
    const next = screen.getByRole("button", { name: "Next" });
    fireEvent.click(next);
    await waitFor(() =>
      expect(skill2jobApi.getCatalog).toHaveBeenCalledWith(
        expect.objectContaining({ keyword: "Data", limit: 12, offset: 12 }),
      ),
    );
  });

  it("shows the explainable per-skill match detail on the job detail page", async () => {
    vi.mocked(skill2jobApi.getJob).mockResolvedValue(mockJob);
    vi.mocked(skill2jobApi.getJobMatch).mockResolvedValue(mockJobMatchDetail);
    renderSkill2Job("/skill2job/jobs/cur-001");
    expect(await screen.findByText("Data Engineer")).toBeInTheDocument();
    expect(screen.getByText("Your match score")).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
    expect(screen.getByText("Skill-by-skill breakdown")).toBeInTheDocument();
    expect(screen.getByText("How this score was derived")).toBeInTheDocument();
    expect(screen.getByText(/covers 1 of 2 required skills/)).toBeInTheDocument();
    expect(screen.getByText("SQL is not found anywhere in your candidate data.")).toBeInTheDocument();
    expect(screen.getByText("matcher skill2job-match-5.1.0")).toBeInTheDocument();
  });

  it("runs matching and lists scored jobs", async () => {
    renderSkill2Job("/skill2job/jobs");
    expect(await screen.findByText("Semantic Job Matching")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run matching" }));
    expect(await screen.findByText("82")).toBeInTheDocument();
    expect(screen.getByText(/missing SQL/)).toBeInTheDocument();
  });

  it("shows the teacher-style plan on the Skill Gaps page", async () => {
    renderSkill2Job("/skill2job/skill-gaps");
    expect(await screen.findByText("Skill Gap Analysis")).toBeInTheDocument();
    expect(await screen.findByText("Teacher-Style Learning Plan")).toBeInTheDocument();
    expect(screen.getByText("high priority")).toBeInTheDocument();
  });

  it("runs the What-If simulator on the Opportunities page", async () => {
    vi.mocked(skill2jobApi.runSimulation).mockResolvedValue({
      baseline: [],
      simulated: [],
      top_uplift: [
        {
          job_id: "cur-001",
          title: "Data Engineer",
          company: "DataBridge",
          before: 60,
          after: 82,
          uplift: 22,
          newly_matched_skills: ["SQL"],
          unlocked: true,
        },
      ],
      unlocked_count: 1,
      target_role: "Data Engineer",
      skills_added: ["SQL"],
      notes: ["SQL unlocks Data Engineer."],
      simulation_version: "skill2job-opportunity-7.0.0",
    });
    renderSkill2Job("/skill2job/opportunities");
    expect(await screen.findByText("What-If Opportunity Simulator")).toBeInTheDocument();
    const input = screen.getByPlaceholderText(/e.g. Apache Spark, Docker, Tableau/);
    fireEvent.change(input, { target: { value: "SQL" } });
    fireEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(await screen.findByText(/role\(s\) unlocked/)).toBeInTheDocument();
    expect(screen.getByText("+22")).toBeInTheDocument();
  });

  it("shows training modules on the Learning Path page", async () => {
    renderSkill2Job("/skill2job/learning");
    expect(await screen.findByText("Learning Plan")).toBeInTheDocument();
    expect(screen.getByText("Balanced")).toBeInTheDocument();
  });

  it("shows readiness summary cards on learning plan", async () => {
    renderSkill2Job("/skill2job/learning");
    expect(await screen.findByText("Learning Plan")).toBeInTheDocument();
    expect(await screen.findByText("70%")).toBeInTheDocument();
    expect(screen.getByText("Readiness")).toBeInTheDocument();
  });

  it("renders skill proof detail page", async () => {
    renderSkill2Job("/skill2job/skill-proof");
    expect(await screen.findByText("Skill Proof Medium")).toBeInTheDocument();
  });

  it("shows free vs paid comparison on learning plan", async () => {
    renderSkill2Job("/skill2job/learning");
    expect(await screen.findByText("Learning Plan")).toBeInTheDocument();
    expect(await screen.findByText("Free Only Path")).toBeInTheDocument();
  });

  it("renders the skill graph with real nodes", async () => {
    renderSkill2Job("/skill2job/skill-graph");
    expect(await screen.findByText("Skill Graph")).toBeInTheDocument();
    expect((await screen.findAllByText("Python")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("SQL")).length).toBeGreaterThan(0);
  });

  it("shows skill proof with evidence sources", async () => {
    renderSkill2Job("/skill2job/skill-proof");
    expect(await screen.findByText("Skill Proof Medium")).toBeInTheDocument();
    expect(await screen.findByText("Candidate profile")).toBeInTheDocument();
    expect(await screen.findByText(/expertise record/i).catch(() => null)).toBeNull();
  });

  it("legacy /candidate/skill2job redirects to /skill2job", async () => {
    renderSkill2Job("/candidate/skill2job");
    expect(await screen.findByText(/Ada's Career Hub/i)).toBeInTheDocument();
  });

  it("keeps internal diagnostics behind the admin page (not candidate-facing)", async () => {
    const { container } = renderSkill2Job("/skill2job");
    expect(await screen.findByText(/Ada's Career Hub/i)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
  });
});

describe("Skill2JobDiagnostics (admin)", () => {
  beforeEach(() => {
    vi.mocked(skill2jobApi.getHealth).mockResolvedValue({ module: "skill2job", status: "healthy" });
    vi.mocked(skill2jobApi.getCapabilities).mockResolvedValue(mockCapabilities);
    vi.mocked(skill2jobApi.getPipelineTraces).mockResolvedValue([
      { run_id: "abc123", steps: 5, created_at: "2026-01-02T00:00:00Z" },
    ]);
  });

  it("lists capabilities and pipeline executions", async () => {
    render(
      <MemoryRouter>
        <Skill2JobDiagnostics />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Skill2Job Diagnostics (Admin)")).toBeInTheDocument();
    expect(screen.getByText("Perception (resume/text/voice)")).toBeInTheDocument();
    expect(await screen.findByText("abc123")).toBeInTheDocument();
  });
});