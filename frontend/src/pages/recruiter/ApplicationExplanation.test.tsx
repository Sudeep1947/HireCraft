import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { getApplicationExplanation } from "../../api/screening";
import { RecruiterApplicationExplanationPage } from "./ApplicationExplanation";
import type { RecruiterApplicationExplanation } from "../../types/screening";

vi.mock("../../api/screening", () => ({
  getApplicationExplanation: vi.fn(),
}));

const jobId = "job-1";
const applicationId = "app-1";

function buildExplanation(
  overrides: Partial<RecruiterApplicationExplanation> = {},
): RecruiterApplicationExplanation {
  return {
    application: {
      id: applicationId,
      job_id: jobId,
      candidate_id: "candidate-1",
      resume_id: "resume-1",
      status: "under_review",
      applied_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
      screening_status: "completed",
      screening_attempts: 1,
      screening_error: null,
      screening_started_at: null,
      screening_completed_at: "2026-01-02T00:00:00Z",
    },
    candidate: { id: "candidate-1", name: "Ada Lovelace", email: "ada@example.com" },
    job: {
      id: jobId,
      title: "Senior Backend Engineer",
      company: "Example Co",
      required_skills: ["Python", "FastAPI"],
      preferred_skills: ["Docker"],
      experience_required: "5 years",
      education_required: null,
    },
    screening_state: {
      effective_status: "completed",
      screened: true,
      message: "",
    },
    score: {
      overall_score: 88,
      recommendation: "recommend",
      strength_level: "good",
      screened_at: "2026-01-02T00:00:00Z",
      source: "screening_result",
    },
    match_breakdown: [
      { key: "skills", label: "Skills", score: 92, source_column: "skill_match_score" },
    ],
    feature_importance: [
      {
        category: "skill_match",
        label: "Skills",
        score: 92,
        contribution_pct: 34.5,
        impact: "positive",
        impact_description: "Strong skill evidence for the required stack.",
        method: "rule_based",
        weight: 0.35,
      },
      {
        category: "experience_match",
        label: "Experience",
        score: 84,
        contribution_pct: 21.0,
        impact: "positive",
        impact_description: "Relevant years meet the stated requirement.",
        method: "rule_based",
        weight: 0.25,
      },
    ],
    positive_factors: [
      {
        category: "skill_match",
        score: 92,
        contribution_pct: 34.5,
        reason: "Resume lists Python and FastAPI explicitly.",
        evidence: [
          {
            source: "skills_section",
            quote: "Python, FastAPI",
            context: "Skills",
            section: "Skills",
          },
        ],
        evidence_available: true,
      },
    ],
    negative_factors: [
      {
        category: "certification_match",
        score: 40,
        contribution_pct: 8.0,
        reason: "No certification evidence was found.",
        evidence: [],
        evidence_available: false,
      },
    ],
    reasoning_summary: "Strong backend Python evidence with a certification gap.",
    confidence: {
      score: 78,
      level: "high",
      description: "Most screening data points were available.",
      data_completeness_pct: 78,
      data_points_available: 7,
      data_points_max: 9,
    },
    improvement_suggestions: [
      {
        category: "certification",
        subject: "Kubernetes",
        text: "Add a certification or project evidence for Kubernetes.",
        priority: "medium",
      },
    ],
    skill_alignment: {
      matched_skills: ["Python", "FastAPI"],
      missing_required_skills: ["Kubernetes"],
      missing_preferred_skills: ["Terraform"],
      supported_skills: ["Python"],
      partial_evidence_skills: ["FastAPI"],
      skills_without_evidence: ["Docker"],
      insufficient_information_skills: [],
    },
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
    ],
    experience_alignment: {
      status: "match",
      required_years: 5,
      relevant_years: 6,
      total_years: 7,
      relevance_basis: "titles",
      reason: "Relevant experience meets the requirement.",
    },
    evidence_gaps: [
      { subject: "Kubernetes", category: "certification", note: "No evidence found." },
    ],
    evidence_strengths: [
      {
        title: "Backend Python",
        category: "skill",
        depth: "strong",
        confidence: "high",
        reason: "Multiple years across projects.",
        evidence: [
          { source: "experience", quote: "Backend engineer 2019-2024", context: null, section: null },
        ],
        evidence_available: true,
      },
    ],
    fit_classification: "strong_fit",
    fit_score: 82,
    fit_summary: "Strong backend fit for this role.",
    fit_summary_source: "deterministic",
    fit_formula: "0.5 * skill + 0.3 * experience + 0.2 * education",
    fit_weights: { skill: 0.5, experience: 0.3, education: 0.2 },
    review_flags: [
      {
        flag_type: "thin_evidence",
        title: "Thin certification evidence",
        severity: "warning",
        description: "Only one certification is evidenced.",
        possible_explanation: "Candidate may list certifications without detail.",
      },
    ],
    screening_questions: [
      {
        topic: "certifications",
        question: "Can you describe your Kubernetes certification?",
        reason: "Certification evidence is thin.",
      },
    ],
    evidence_snapshot: { project_count: 3, certification_count: 1 },
    explainability: { available: true, reason: null },
    evidence_intelligence: { available: true, reason: null },
    fit: { available: true, reason: null },
    freshness: {
      screening_resume_id: "resume-1",
      application_resume_id: "resume-1",
      primary_resume_id: "resume-1",
      evidence_resume_id: "resume-1",
      screening_resume_is_current_primary: true,
      evidence_resume_is_screening_resume: true,
      screened_at: "2026-01-02T00:00:00Z",
      fit_engine_version: "fit-1.0.0",
      evidence_engine_version: "evidence-1.0.0",
      explainability_method: "rule_based",
    },
    limitations: ["Screening reflects the resume version submitted at screening time."],
    disclaimer: "AI-assisted screening explanation. Decision support for human review, not a hiring decision.",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter
      initialEntries={[`/recruiter/jobs/${jobId}/applicants/${applicationId}/explanation`]}
    >
      <Routes>
        <Route
          path="/recruiter/jobs/:jobId/applicants/:applicationId/explanation"
          element={<RecruiterApplicationExplanationPage />}
        />
        <Route path="/recruiter/jobs/:jobId/applicants" element={<p>Applicants list</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RecruiterApplicationExplanationPage", () => {
  beforeEach(() => {
    vi.mocked(getApplicationExplanation).mockReset();
  });

  it("renders the stored score exactly as the server reported it", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(getApplicationExplanation).toHaveBeenCalledWith(applicationId);
    expect(await screen.findByText("Why this score?")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("Recommend")).toBeInTheDocument();
    expect(screen.getByText(/Copied verbatim/)).toBeInTheDocument();
  });

  it("shows dimension contributions and the recruiter-only weights", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(await screen.findByText("What drove this score")).toBeInTheDocument();
    expect(screen.getByText("34.5%")).toBeInTheDocument();
    expect(screen.getByText("21%")).toBeInTheDocument();
    const weights = screen.getAllByTestId("feature-weight");
    expect(weights).toHaveLength(2);
    expect(weights[0]).toHaveTextContent("w 0.35");
  });

  it("grounds each factor in resume evidence and marks unevidenced factors", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(await screen.findByText("Factors in this candidate's favour")).toBeInTheDocument();
    expect(screen.getByText(/Resume lists Python and FastAPI explicitly/)).toBeInTheDocument();
    // The same resume quote appears in the positive factor and in the
    // requirement-level match, which is the point: one evidence item, cited
    // wherever it is used.
    expect(screen.getAllByText(/Python, FastAPI/)).toHaveLength(2);
    expect(
      screen.getByText("Factors working against this candidate"),
    ).toBeInTheDocument();
    expect(screen.getByText(/No certification evidence was found/)).toBeInTheDocument();
    expect(screen.getByText("No quote")).toBeInTheDocument();
  });

  it("renders requirements, gaps and suggestions", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(await screen.findByText("Requirement-level matching")).toBeInTheDocument();
    expect(screen.getByText(/Found in skills section/)).toBeInTheDocument();
    expect(screen.getByText("Improvement suggestions")).toBeInTheDocument();
    expect(
      screen.getByText(/Add a certification or project evidence for Kubernetes/),
    ).toBeInTheDocument();
    expect(screen.getByText("Evidence gaps")).toBeInTheDocument();
  });

  it("exposes recruiter-only internals that the candidate view must never receive", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(await screen.findByText("Fit analysis")).toBeInTheDocument();
    expect(screen.getByText("Strong backend fit for this role.")).toBeInTheDocument();
    expect(
      screen.getByText("0.5 * skill + 0.3 * experience + 0.2 * education"),
    ).toBeInTheDocument();
    expect(screen.getByText("Component weights")).toBeInTheDocument();
    expect(screen.getByText("Evidence review flags")).toBeInTheDocument();
    expect(screen.getByText("Thin certification evidence")).toBeInTheDocument();
    expect(screen.getByText("Suggested screening questions")).toBeInTheDocument();
    expect(screen.getByText(/Can you describe your Kubernetes certification/)).toBeInTheDocument();
  });

  it("shows a pending state with no fabricated score when screening has not run", async () => {
    const explanation = buildExplanation();
    explanation.screening_state = {
      effective_status: "queued",
      screened: false,
      message: "Screening has not produced a result yet.",
    };
    explanation.score = {
      overall_score: null,
      recommendation: null,
      strength_level: null,
      screened_at: null,
      source: "unavailable",
    };
    explanation.feature_importance = [];
    explanation.positive_factors = [];
    explanation.negative_factors = [];
    explanation.confidence = null;
    vi.mocked(getApplicationExplanation).mockResolvedValue(explanation);

    renderPage();

    expect(await screen.findByText("Screening is queued")).toBeInTheDocument();
    expect(screen.getByText("Screening has not produced a result yet.")).toBeInTheDocument();
    expect(
      screen.getByText("No stored screening result exists, so there is no score to explain."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No dimension breakdown is available for this application."),
    ).toBeInTheDocument();
    expect(screen.queryByText("88")).not.toBeInTheDocument();
  });

  it("degrades fit and evidence sections with a reason instead of inventing values", async () => {
    const explanation = buildExplanation();
    explanation.fit = { available: false, reason: "Fit analysis is unavailable." };
    explanation.evidence_intelligence = {
      available: false,
      reason: "Evidence intelligence is unavailable.",
    };
    explanation.fit_score = null;
    explanation.fit_summary = null;
    vi.mocked(getApplicationExplanation).mockResolvedValue(explanation);

    renderPage();

    expect(await screen.findByText("Fit analysis")).toBeInTheDocument();
    expect(screen.getByText("Fit analysis is unavailable.")).toBeInTheDocument();
  });

  it("warns when the candidate uploaded a newer resume after screening", async () => {
    const explanation = buildExplanation();
    explanation.freshness = {
      ...explanation.freshness,
      screening_resume_is_current_primary: false,
    };
    vi.mocked(getApplicationExplanation).mockResolvedValue(explanation);

    renderPage();

    expect(await screen.findByTestId("explanation-resume-drift")).toBeInTheDocument();
    expect(screen.getByText(/has not been rescored/)).toBeInTheDocument();
  });

  it("shows the decision-support disclaimer", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(
      await screen.findByText(
        "AI-assisted screening explanation. Decision support for human review, not a hiring decision.",
      ),
    ).toBeInTheDocument();
    // Confidence is about the available evidence, never about the candidate.
    expect(screen.getByText(/Confidence in the data the explanation rests on/)).toBeInTheDocument();
  });

  it("does not reveal the application for a forbidden or missing response", async () => {
    vi.mocked(getApplicationExplanation).mockRejectedValue({
      response: { status: 404 },
      message: "Not found",
    });

    renderPage();

    expect(await screen.findByText("Explanation unavailable")).toBeInTheDocument();
    expect(screen.getByText("Back to applicants")).toBeInTheDocument();
    expect(screen.queryByText("Why this score?")).not.toBeInTheDocument();
  });

  it("shows a retryable error state for a failed request", async () => {
    vi.mocked(getApplicationExplanation).mockRejectedValue(new Error("Network down"));

    renderPage();

    expect(await screen.findByText("Could not load the score explanation")).toBeInTheDocument();
    expect(screen.getByText("Network down")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("navigates back to the applicant list", async () => {
    vi.mocked(getApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    (await screen.findByText("← Back to applicants")).click();

    await waitFor(() => {
      expect(screen.getByText("Applicants list")).toBeInTheDocument();
    });
  });
});
