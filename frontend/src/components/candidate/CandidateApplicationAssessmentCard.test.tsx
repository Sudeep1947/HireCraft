import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { applicationAssessmentApi } from "../../api/applicationAssessment";
import { CandidateApplicationAssessmentCard } from "./CandidateApplicationAssessmentCard";
import type { CandidateApplicationAssessmentView } from "../../types/applicationAssessment";

vi.mock("../../api/applicationAssessment", () => ({
  applicationAssessmentApi: {
    getOptions: vi.fn(),
    assign: vi.fn(),
    getEvidence: vi.fn(),
    getMyApplicationAssessment: vi.fn(),
  },
}));

const applicationId = "app-1";
const assessmentId = "assess-1";
const attemptId = "attempt-1";

function view(
  overrides: Partial<CandidateApplicationAssessmentView> = {},
): CandidateApplicationAssessmentView {
  return {
    application_id: applicationId,
    attempt_id: null,
    assessment_id: null,
    assessment_title: null,
    status: null,
    attempt_number: null,
    job_id: null,
    job_title: null,
    scheduled_at: null,
    assessment_link: null,
    has_assessment: false,
    has_completed: false,
    completed_count: 0,
    attempt_count: 0,
    can_start: false,
    can_continue: false,
    expires_at: null,
    submitted_at: null,
    overall_score: null,
    strong_skills: [],
    recommended_topics: [],
    summary_text: null,
    message: null,
    ...overrides,
  };
}

function renderCard() {
  return render(
    <MemoryRouter initialEntries={["/candidate/applications/app-1"]}>
      <Routes>
        <Route
          path="/candidate/applications/:applicationId"
          element={<CandidateApplicationAssessmentCard applicationId={applicationId} />}
        />
        <Route
          path="/candidate/assessments/take/:assessmentId"
          element={<div data-testid="take-page" />}
        />
        <Route
          path="/candidate/assessments/results/:attemptId"
          element={<div data-testid="result-page" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CandidateApplicationAssessmentCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches the candidate view for the application in the route", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view(),
    );
    renderCard();

    await screen.findByTestId("candidate-assessment-empty");
    expect(applicationAssessmentApi.getMyApplicationAssessment).toHaveBeenCalledWith(
      applicationId,
    );
  });

  it("shows a loading state before the answer arrives", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view(),
    );
    renderCard();

    expect(screen.getByTestId("candidate-assessment-loading")).toBeInTheDocument();
    await screen.findByTestId("candidate-assessment-empty");
  });

  it("states plainly that no assessment is assigned", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view(),
    );
    renderCard();

    expect(
      await screen.findByText("No assessment assigned"),
    ).toBeInTheDocument();
  });

  it("offers a start that goes to the existing assessment-taking experience", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        assessment_title: "Backend Engineering Assessment",
        status: "assigned",
        attempt_number: 1,
        can_start: true,
        message: "You have been assigned an assessment.",
      }),
    );
    renderCard();

    await userEvent.click(await screen.findByRole("button", { name: "Start assessment" }));

    // The platform's own taking route, not a second candidate assessment UI.
    expect(await screen.findByTestId("take-page")).toBeInTheDocument();
  });

  it("offers a resume that carries the attempt id when one is in progress", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        assessment_title: "Backend Engineering Assessment",
        status: "in_progress",
        attempt_number: 1,
        can_continue: true,
        can_start: false,
        message: "Your assessment is in progress. Continue where you left off.",
      }),
    );
    renderCard();

    expect(
      await screen.findByRole("button", { name: "Continue assessment" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continue assessment" }));

    expect(await screen.findByTestId("take-page")).toBeInTheDocument();
  });

  it("offers no start once the attempt is finished, and points at the result", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        has_completed: true,
        completed_count: 1,
        attempt_count: 1,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        assessment_title: "Backend Engineering Assessment",
        status: "completed",
        attempt_number: 1,
        can_start: false,
        can_continue: false,
        overall_score: 82,
        message: "Your assessment has been submitted. Your result is available.",
      }),
    );
    renderCard();

    expect(screen.queryByRole("button", { name: /Start assessment/ })).toBeNull();
    await userEvent.click(
      await screen.findByRole("button", { name: "View your result" }),
    );
    expect(await screen.findByTestId("result-page")).toBeInTheDocument();
  });

  it("shows the score once there is one, and no score before that", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment)
      .mockResolvedValueOnce(
        view({
          has_assessment: true,
          attempt_id: attemptId,
          assessment_id: assessmentId,
          status: "assigned",
          can_start: true,
        }),
      )
      .mockResolvedValueOnce(
        view({
          has_assessment: true,
          has_completed: true,
          attempt_id: attemptId,
          assessment_id: assessmentId,
          status: "completed",
          can_start: false,
          overall_score: 82,
        }),
      );

    const first = renderCard();
    // Ungraded: no score is shown, and specifically not a zero.
    await screen.findByRole("button", { name: "Start assessment" });
    expect(screen.queryByText("Your score")).toBeNull();
    first.unmount();

    renderCard();
    expect(await screen.findByText("Your score")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
  });

  it("shows the strengths and practice topics the server derived", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        has_completed: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        status: "completed",
        can_start: false,
        overall_score: 82,
        strong_skills: ["Python", "SQL"],
        recommended_topics: ["Recursion"],
      }),
    );
    renderCard();

    expect(await screen.findByText("Python")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.getByText("Recursion")).toBeInTheDocument();
  });

  it("frames the assessment as evidence and keeps the decision with the team", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        status: "assigned",
        can_start: true,
      }),
    );
    renderCard();

    expect(
      await screen.findByText(/the final decision is made by the hiring team/i),
    ).toBeInTheDocument();
  });

  it("never renders a staff-only field even if one reaches the client", async () => {
    const leaky = {
      ...view({
        has_assessment: true,
        has_completed: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        status: "completed",
        can_start: false,
        overall_score: 82,
      }),
      // Fields the server's allowlist does not include. If the UI ever started
      // reading one of these, a leaked internal label would become visible.
      recruiter_notes: "SECRET_RECRUITER_NOTE_do_not_leak",
      recommendation: "strong_hire",
      readiness_level: "high",
      fairness_score: 0.97,
    } as unknown as CandidateApplicationAssessmentView;
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      leaky,
    );
    renderCard();

    await screen.findByText("82%");
    expect(screen.queryByText(/SECRET_RECRUITER_NOTE/)).toBeNull();
    expect(screen.queryByText(/strong_hire/)).toBeNull();
    expect(screen.queryByText(/readiness/i)).toBeNull();
    expect(screen.queryByText(/0\.97/)).toBeNull();
  });

  it("surfaces a failure with a recovery action rather than hiding the assessment", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockRejectedValue(
      new Error("boom"),
    );
    renderCard();

    expect(await screen.findByTestId("candidate-assessment-error")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();

    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        status: "assigned",
        can_start: true,
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("button", { name: "Start assessment" }),
    ).toBeInTheDocument();
  });

  it("renders no call to action when the server offers none", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view({
        has_assessment: true,
        attempt_id: attemptId,
        assessment_id: assessmentId,
        status: "expired",
        can_start: false,
        can_continue: false,
        message: "Your assessment time expired before it was submitted.",
      }),
    );
    renderCard();

    await screen.findByText(/time expired/);
    // An expired attempt offers neither a start nor a resume, rather than a
    // button that would be refused.
    expect(screen.queryByRole("button", { name: "Start assessment" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Continue assessment" })).toBeNull();
  });

  it("re-fetches when the application id changes", async () => {
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      view(),
    );
    const { rerender } = render(
      <MemoryRouter>
        <CandidateApplicationAssessmentCard applicationId="app-1" />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(applicationAssessmentApi.getMyApplicationAssessment).toHaveBeenCalledWith(
        "app-1",
      );
    });

    rerender(
      <MemoryRouter>
        <CandidateApplicationAssessmentCard applicationId="app-2" />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(applicationAssessmentApi.getMyApplicationAssessment).toHaveBeenCalledWith(
        "app-2",
      );
    });
  });
});
