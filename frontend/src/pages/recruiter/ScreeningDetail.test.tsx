import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { getApplicationScreeningDetail } from "../../api/screening";
import { RecruiterScreeningDetail } from "./ScreeningDetail";
import type { ApplicationScreeningDetailResponse } from "../../types/screening";

vi.mock("../../api/screening", () => ({
  getApplicationScreeningDetail: vi.fn(),
}));

const jobId = "job-1";
const applicationId = "app-1";

function buildDetail(
  overrides: Partial<ApplicationScreeningDetailResponse> = {},
): ApplicationScreeningDetailResponse {
  return {
    application: {
      id: applicationId,
      job_id: jobId,
      candidate_id: "candidate-1",
      resume_id: null,
      status: "under_review",
      applied_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
      cover_letter: null,
      decision_reason: null,
      decision_comment: null,
      decided_at: null,
      screening: {
        effective_status: "completed",
        recorded_status: "completed",
        attempts: 1,
        task_id: null,
        error: null,
        started_at: null,
        completed_at: "2026-01-02T00:00:00Z",
      },
    },
    candidate: {
      id: "candidate-1",
      name: "Ada Lovelace",
      email: "ada@example.com",
      resume_id: "resume-1",
      has_resume: true,
    },
    job: {
      id: jobId,
      title: "Senior Backend Engineer",
      company: "Example Co",
      location: "Remote",
      employment_type: "full_time",
      experience_required: "5 years",
      education_required: "",
      required_skills: ["Python", "FastAPI"],
      preferred_skills: ["Docker"],
    },
    screening_result: {
      id: "screening-1",
      job_id: jobId,
      candidate_id: "candidate-1",
      application_id: applicationId,
      resume_id: "resume-1",
      overall_match_score: 88,
      skill_match_score: 92,
      experience_match_score: 84,
      education_match_score: 90,
      project_match_score: 81,
      certification_match_score: 70,
      location_match_score: 100,
      employment_type_match_score: 95,
      semantic_match_score: 86,
      matched_skills: ["Python", "FastAPI"],
      missing_required_skills: ["Kubernetes"],
      missing_preferred_skills: ["Terraform"],
      strengths: ["Strong backend Python"],
      weaknesses: ["No Kubernetes evidence"],
      recommendation: "recommend",
      strength_level: "good",
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    },
    match_breakdown: [
      { key: "skills", label: "Skills", score: 92, source_column: "skill_match_score" },
      { key: "experience", label: "Experience", score: 84, source_column: "experience_match_score" },
    ],
    evidence_intelligence: null,
    evidence_intelligence_section: { available: false, reason: "Evidence intelligence unavailable." },
    fit: null,
    fit_section: { available: false, reason: "Fit analysis unavailable." },
    job_context: null,
    job_context_section: { available: false, reason: "Evidence intelligence unavailable." },
    freshness: {
      screened_at: "2026-01-02T00:00:00Z",
      screening_resume_id: "resume-1",
      application_resume_id: null,
      resume_matches_application: true,
      engine_version: null,
      fit_engine_version: null,
      evidence_engine_version: null,
    },
    limitations: ["No confidence value is stored for screening results."],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/recruiter/jobs/${jobId}/applicants/${applicationId}/screening`]}>
      <Routes>
        <Route
          path="/recruiter/jobs/:jobId/applicants/:applicationId/screening"
          element={<RecruiterScreeningDetail />}
        />
        <Route path="/recruiter/jobs/:jobId/applicants" element={<p>Applicants list</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RecruiterScreeningDetail", () => {
  beforeEach(() => {
    vi.mocked(getApplicationScreeningDetail).mockReset();
  });

  it("shows a loading state and then the stored screening result", async () => {
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(buildDetail());

    renderPage();

    expect(getApplicationScreeningDetail).toHaveBeenCalledWith(applicationId);
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("Recommend")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getByText("No Kubernetes evidence")).toBeInTheDocument();
  });

  it("renders stored per-dimension scores without computing new ones", async () => {
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(buildDetail());

    renderPage();

    expect(await screen.findByText("Match breakdown")).toBeInTheDocument();
    const skillsRow = screen.getByText("Skills").closest("li");
    expect(skillsRow).not.toBeNull();
    expect(skillsRow).toHaveTextContent("92");
    expect(screen.getByText("84")).toBeInTheDocument();
  });

  it("shows requirement-level matching and evidence when available", async () => {
    const detail = buildDetail();
    detail.fit_section = { available: true, reason: null };
    detail.fit = {
      job_id: jobId,
      job_title: "Senior Backend Engineer",
      candidate_id: "candidate-1",
      candidate_name: "Ada Lovelace",
      resume_id: "resume-1",
      requirements: [
        {
          requirement: "Python",
          requirement_type: "required_skill",
          level: "core",
          category: "skill",
          status: "match",
          evidence_strength: "strong",
          reason: "Found in skills section",
          evidence: [
            {
              source: "skills_section",
              quote: "Python, FastAPI",
              context: "Skills",
              section: "Skills",
            },
          ],
        },
        {
          requirement: "Kubernetes",
          requirement_type: "required_skill",
          level: "core",
          category: "skill",
          status: "gap",
          evidence_strength: "none",
          reason: "No supporting evidence found",
          evidence: [],
        },
      ],
      experience_alignment: {
        status: "match",
        required_years: 5,
        relevant_years: 6,
        total_years: 6,
        relevance_basis: "titles",
        reason: "Relevant experience",
      },
      responsibilities: [],
      skill_gaps: { strengths: ["Python"], partial: [], gaps: ["Kubernetes"], unknown: ["Docker"] },
      overall: {
        classification: "strong_fit",
        score: 82,
        breakdown: { weights: {}, components: {}, formula: "" },
        summary: "Strong backend fit.",
        summary_source: "deterministic",
        disclaimer: "Decision support only.",
      },
      requirements_info: { extracted_count: 3, extractor_version: "v1" },
      cached: false,
      engine_version: "fit-1.0.0",
    };
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(detail);

    renderPage();

    expect(await screen.findByText("Requirement-level matching")).toBeInTheDocument();
    expect(screen.getByText("Met")).toBeInTheDocument();
    expect(screen.getByText("Gap")).toBeInTheDocument();
    expect(screen.getByText(/Found in skills section/)).toBeInTheDocument();
    expect(screen.getByText(/Python, FastAPI/)).toBeInTheDocument();
    expect(screen.getByText("Strong backend fit.")).toBeInTheDocument();
  });

  it("shows an unavailable state with the reason when intelligence is missing", async () => {
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(buildDetail());

    renderPage();

    expect(await screen.findByText("Evidence intelligence")).toBeInTheDocument();
    const fitCards = screen.getAllByText("Not available");
    expect(fitCards.length).toBeGreaterThan(0);
    expect(screen.getByText("Fit analysis unavailable.")).toBeInTheDocument();
  });

  it("shows a pending state with no fabricated score", async () => {
    const detail = buildDetail();
    detail.screening_result = null;
    detail.match_breakdown = [];
    detail.application.screening = {
      effective_status: "queued",
      recorded_status: "queued",
      attempts: 1,
      task_id: "task-9",
      error: null,
      started_at: null,
      completed_at: null,
    };
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(detail);

    renderPage();

    expect(await screen.findByText("Screening is queued")).toBeInTheDocument();
    expect(screen.getByText("No stored screening result for this application.")).toBeInTheDocument();
    expect(
      screen.getByText("No stored dimension scores for this application."),
    ).toBeInTheDocument();
    expect(screen.queryByText("88")).not.toBeInTheDocument();
  });

  it("shows the failed screening state with the recorded error", async () => {
    const detail = buildDetail();
    detail.screening_result = null;
    detail.match_breakdown = [];
    detail.application.screening = {
      effective_status: "failed",
      recorded_status: "failed",
      attempts: 2,
      task_id: null,
      error: "Matching engine timed out",
      started_at: null,
      completed_at: null,
    };
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(detail);

    renderPage();

    expect(await screen.findByText("Screening failed")).toBeInTheDocument();
    expect(screen.getByText("Matching engine timed out")).toBeInTheDocument();
  });

  it("warns when the candidate uploaded a newer resume after screening", async () => {
    const detail = buildDetail();
    detail.freshness = { ...detail.freshness, resume_matches_application: false };
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(detail);

    renderPage();

    expect(await screen.findByText(/uploaded a newer resume/)).toBeInTheDocument();
  });

  it("surfaces freshness and limitations", async () => {
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(buildDetail());

    renderPage();

    expect(await screen.findByText("Data freshness and limitations")).toBeInTheDocument();
    expect(
      screen.getByText("No confidence value is stored for screening results."),
    ).toBeInTheDocument();
  });

  it("shows an access denied state for a forbidden response", async () => {
    vi.mocked(getApplicationScreeningDetail).mockRejectedValue({
      response: { status: 403 },
      message: "Request failed",
    });

    renderPage();

    expect(await screen.findByText("Access denied")).toBeInTheDocument();
    expect(screen.getByText("Back to applicants")).toBeInTheDocument();
  });

  it("shows a retryable error state for a failed request", async () => {
    vi.mocked(getApplicationScreeningDetail).mockRejectedValue(new Error("Network down"));

    renderPage();

    expect(await screen.findByText("Could not load screening detail")).toBeInTheDocument();
    expect(screen.getByText("Network down")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("navigates back to the applicant dashboard", async () => {
    vi.mocked(getApplicationScreeningDetail).mockResolvedValue(buildDetail());

    renderPage();

    const backLink = await screen.findByText("← Back to applicants");
    backLink.click();

    await waitFor(() => {
      expect(screen.getByText("Applicants list")).toBeInTheDocument();
    });
  });
});
