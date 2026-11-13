import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { getMyApplicationExplanation } from "../../api/screening";
import { CandidateApplicationExplanationPage } from "./ApplicationExplanation";
import type { CandidateApplicationExplanation } from "../../types/screening";

vi.mock("../../api/screening", () => ({
  getMyApplicationExplanation: vi.fn(),
}));

const applicationId = "app-1";

function buildExplanation(
  overrides: Partial<CandidateApplicationExplanation> = {},
): CandidateApplicationExplanation {
  return {
    application: {
      id: applicationId,
      job_id: "job-1",
      status: "under_review",
      applied_at: "2026-01-01T00:00:00Z",
      screening_status: "completed",
    },
    job: {
      id: "job-1",
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
      screened_at: "2026-01-02T00:00:00Z",
      source: "screening_result",
      match_classification: "strong_fit",
      match_score: 82,
      match_summary: "Your backend experience aligns well with this role.",
      match_summary_source: "deterministic",
    },
    matched_skills: ["Python", "FastAPI"],
    areas_with_limited_evidence: ["Kubernetes"],
    skill_alignment: {
      matched_skills: ["Python", "FastAPI"],
      missing_required_skills: ["Kubernetes"],
      missing_preferred_skills: ["Terraform"],
      supported_skills: ["Python"],
      partial_evidence_skills: ["FastAPI"],
      skills_without_evidence: ["Docker"],
      insufficient_information_skills: ["Kafka"],
    },
    aligned_areas: [
      {
        category: "skill_match",
        score: 92,
        contribution_pct: 34.5,
        reason: "Your resume lists Python and FastAPI explicitly.",
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
    limited_areas: [
      {
        category: "certification_match",
        score: 40,
        contribution_pct: 8.0,
        reason: "No certification evidence was found in your resume.",
        evidence: [],
        evidence_available: false,
      },
    ],
    feature_importance: [
      {
        category: "skill_match",
        label: "Skills",
        score: 92,
        contribution_pct: 34.5,
        impact: "positive",
        impact_description: "Your skills closely match what this role needs.",
        method: "rule_based",
      },
      {
        category: "experience_match",
        label: "Experience",
        score: 84,
        contribution_pct: 21.0,
        impact: "positive",
        impact_description: "Your relevant years meet the stated requirement.",
        method: "rule_based",
      },
    ],
    requirements: [
      {
        requirement: "Python",
        requirement_type: "required_skill",
        level: "core",
        category: "skill",
        status: "match",
        evidence_strength: "strong",
        reason: "Found in your skills section",
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
        reason: "No supporting evidence was found",
        evidence: [],
      },
    ],
    experience_alignment: {
      status: "match",
      required_years: 5,
      relevant_years: 6,
      total_years: 7,
      relevance_basis: "titles",
      reason: "Your relevant experience meets the requirement.",
    },
    evidence_gaps: [
      { subject: "Kubernetes", category: "certification", note: "No evidence found." },
    ],
    resume_evidence: [
      { source: "skills_section", quote: "Python, FastAPI", context: "Skills", section: "Skills" },
    ],
    improvement_suggestions: [
      {
        category: "certification",
        subject: "Kubernetes",
        text: "Add a certification or project evidence for Kubernetes.",
        priority: "medium",
      },
    ],
    confidence: {
      score: 78,
      level: "high",
      description: "Most screening data points were available.",
      data_completeness_pct: 78,
      data_points_available: 7,
      data_points_max: 9,
    },
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
    screening_notice:
      "This is an automated review of the evidence in your resume against this role's requirements. It supports human review and is not a decision about your application.",
    limitations: ["This reflects the resume version submitted at screening time."],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/candidate/applications/${applicationId}/explanation`]}>
      <Routes>
        <Route
          path="/candidate/applications/:applicationId/explanation"
          element={<CandidateApplicationExplanationPage />}
        />
        <Route path="/candidate/applications" element={<p>My applications list</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CandidateApplicationExplanationPage", () => {
  beforeEach(() => {
    vi.mocked(getMyApplicationExplanation).mockReset();
  });

  it("shows the same stored score the recruiter sees", async () => {
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(getMyApplicationExplanation).toHaveBeenCalledWith(applicationId);
    expect(
      await screen.findByText("How your profile matches this role"),
    ).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText(/not recalculated here/)).toBeInTheDocument();
  });

  it("explains the result in terms of the candidate's own resume evidence", async () => {
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(await screen.findByText("Skills that matched this role")).toBeInTheDocument();
    expect(screen.getByText("Where your experience aligned")).toBeInTheDocument();
    expect(
      screen.getByText(/Your resume lists Python and FastAPI explicitly/),
    ).toBeInTheDocument();
    expect(screen.getByText("Where evidence was limited")).toBeInTheDocument();
    expect(
      screen.getByText(/No certification evidence was found in your resume/),
    ).toBeInTheDocument();
    expect(screen.getByText("No quote available")).toBeInTheDocument();
  });

  it("frames evidence gaps as gaps in the resume, not judgements about the candidate", async () => {
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(await screen.findByText("Evidence gaps")).toBeInTheDocument();
    expect(
      screen.getByText(/These are gaps in evidence, not judgements about you/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("How to strengthen a future application"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not a prediction about this application/),
    ).toBeInTheDocument();
  });

  it("never renders internal verdicts, weights, flags or other candidates", async () => {
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    await screen.findByText("How your profile matches this role");

    // The candidate response has no field for any of these, so nothing can
    // render them.
    expect(screen.queryByText("Strongly Recommend")).not.toBeInTheDocument();
    expect(screen.queryByText("Recommend")).not.toBeInTheDocument();
    expect(screen.queryByText("Not Recommended")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Strength:/)).not.toBeInTheDocument();
    expect(screen.queryByText("Component weights")).not.toBeInTheDocument();
    expect(screen.queryByText("Formula")).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence review flags")).not.toBeInTheDocument();
    expect(screen.queryByText("Suggested screening questions")).not.toBeInTheDocument();
    expect(screen.queryByTestId("feature-weight")).not.toBeInTheDocument();
    expect(screen.queryByText(/rank/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/shortlist/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/fairness|bias|protected attribute/i)).not.toBeInTheDocument();
    // Internal missing-skill buckets are not surfaced; only the curated
    // candidate-safe fields are rendered.
    expect(screen.queryByText("Missing required")).not.toBeInTheDocument();
    expect(screen.queryByText("Missing preferred")).not.toBeInTheDocument();
  });

  it("states plainly that the review is not a decision", async () => {
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    expect(
      await screen.findByText(/It supports human review and is not a decision about your application/),
    ).toBeInTheDocument();
  });

  it("shows a pending state with no fabricated score", async () => {
    const explanation = buildExplanation();
    explanation.screening_state = {
      effective_status: "queued",
      screened: false,
      message: "Your application has not been screened yet.",
    };
    explanation.score = {
      overall_score: null,
      screened_at: null,
      source: "unavailable",
      match_classification: null,
      match_score: null,
      match_summary: null,
      match_summary_source: null,
    };
    explanation.feature_importance = [];
    explanation.aligned_areas = [];
    explanation.limited_areas = [];
    explanation.confidence = null;
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(explanation);

    renderPage();

    expect(await screen.findByText("Screening is queued")).toBeInTheDocument();
    expect(screen.getByText("Your application has not been screened yet.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your application has not been screened yet, so there is no match result to show.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("88")).not.toBeInTheDocument();
  });

  it("warns when the explanation describes an older resume version", async () => {
    const explanation = buildExplanation();
    explanation.freshness = {
      ...explanation.freshness,
      screening_resume_is_current_primary: false,
    };
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(explanation);

    renderPage();

    expect(await screen.findByTestId("explanation-resume-drift")).toBeInTheDocument();
    expect(screen.getByText(/has not been rescored/)).toBeInTheDocument();
  });

  it("hides the explanation when the application is not the candidate's own", async () => {
    vi.mocked(getMyApplicationExplanation).mockRejectedValue({
      response: { status: 404 },
      message: "Not found",
    });

    renderPage();

    expect(await screen.findByText("Explanation unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("This explanation does not exist or is not available for your account."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Back to my applications"),
    ).toBeInTheDocument();
    expect(screen.queryByText("88")).not.toBeInTheDocument();
  });

  it("shows a retryable error state for a failed request", async () => {
    vi.mocked(getMyApplicationExplanation).mockRejectedValue(new Error("Network down"));

    renderPage();

    expect(await screen.findByText("Could not load your match explanation")).toBeInTheDocument();
    expect(screen.getByText("Network down")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("navigates back to my applications", async () => {
    vi.mocked(getMyApplicationExplanation).mockResolvedValue(buildExplanation());

    renderPage();

    (await screen.findByText("← Back to my applications")).click();

    await waitFor(() => {
      expect(screen.getByText("My applications list")).toBeInTheDocument();
    });
  });
});
