import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { applicationAssessmentApi } from "../../api/applicationAssessment";
import { ToastProvider } from "../../contexts/ToastContext";
import { ApplicationAssessmentPanel } from "./ApplicationAssessmentPanel";
import type {
  ApplicationAssessmentEvidence,
  ApplicationAssessmentOptions,
  ApplicationAssessmentSummary,
  AssignableAssessment,
} from "../../types/applicationAssessment";

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

function assignable(
  overrides: Partial<AssignableAssessment> = {},
): AssignableAssessment {
  return {
    assessment_id: assessmentId,
    title: "Backend Engineering Assessment",
    description: "Covers the backend stack",
    mode: "technical",
    status: "published",
    duration_minutes: 60,
    question_count: 12,
    passing_score: 70,
    allowed_attempts: 1,
    adaptive: false,
    skills: ["Python", "SQL"],
    already_assigned: false,
    ...overrides,
  };
}

function options(
  overrides: Partial<ApplicationAssessmentOptions> = {},
): ApplicationAssessmentOptions {
  return {
    application_id: applicationId,
    current_status: "shortlisted",
    status_is_final: false,
    can_assign: true,
    assign_unavailable_reason: null,
    has_assessments: false,
    attempt_count: 0,
    available: [],
    actions: [],
    ...overrides,
  };
}

function summary(
  overrides: Partial<ApplicationAssessmentSummary> = {},
): ApplicationAssessmentSummary {
  return {
    attempt_id: "attempt-1",
    assessment_id: assessmentId,
    assessment_title: "Backend Engineering Assessment",
    mode: "technical",
    status: "assigned",
    attempt_number: 1,
    scheduled_for_hint: "2026-01-05T09:00:00Z",
    started_at: null,
    expires_at: null,
    submitted_at: null,
    completed_at: null,
    questions_total: 12,
    questions_answered: 0,
    overall_score: null,
    passed_threshold: 70,
    passed: null,
    section_scores: [],
    strong_skills: [],
    weak_skills: [],
    recommended_topics: [],
    accuracy: null,
    time_management: null,
    summary_text: null,
    integrity_flag_count: 0,
    ...overrides,
  };
}

function evidence(
  overrides: Partial<ApplicationAssessmentEvidence> = {},
): ApplicationAssessmentEvidence {
  return {
    application_id: applicationId,
    job_id: "job-1",
    job_title: "Backend Engineer",
    candidate_id: "cand-1",
    candidate_name: "Dana Candidate",
    application_status: "shortlisted",
    attempt_count: 0,
    completed_count: 0,
    average_overall_score: null,
    attempts: [],
    ...overrides,
  };
}

function mockLoad(
  loadedOptions: ApplicationAssessmentOptions,
  loadedEvidence: ApplicationAssessmentEvidence,
) {
  vi.mocked(applicationAssessmentApi.getOptions).mockResolvedValue(loadedOptions);
  vi.mocked(applicationAssessmentApi.getEvidence).mockResolvedValue(loadedEvidence);
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <ApplicationAssessmentPanel applicationId={applicationId} />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("ApplicationAssessmentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoad(options(), evidence());
  });

  it("loads the options and the evidence together, keyed by the application", async () => {
    renderPanel();

    await screen.findByRole("heading", { name: "Assessment" });
    expect(applicationAssessmentApi.getOptions).toHaveBeenCalledWith(applicationId);
    expect(applicationAssessmentApi.getEvidence).toHaveBeenCalledWith(applicationId);
  });

  it("shows an empty state when no assessment is assigned", async () => {
    renderPanel();

    expect(
      await screen.findByText("No assessment assigned to this application yet."),
    ).toBeInTheDocument();
  });

  it("offers only the assessments the server marked assignable", async () => {
    mockLoad(
      options({
        available: [
          assignable(),
          assignable({
            assessment_id: "assess-2",
            title: "Already live",
            already_assigned: true,
          }),
        ],
      }),
      evidence(),
    );
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Assign assessment" }),
    );

    const picker = screen.getByLabelText("Assessment to assign");
    const values = within(picker)
      .getAllByRole("option")
      .map((o) => (o as HTMLOptionElement).value);
    // The already-assigned row stays in the catalog so the recruiter can see it,
    // but it is not offered as something to assign a second time.
    expect(values).toEqual([assessmentId]);
  });

  it("previews the real assessment metadata for the selected entry", async () => {
    mockLoad(options({ available: [assignable()] }), evidence());
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Assign assessment" }),
    );

    const preview = await screen.findByTestId("assessment-preview");
    expect(preview).toHaveTextContent("Covers the backend stack");
    expect(preview).toHaveTextContent("60 minutes");
    expect(preview).toHaveTextContent("12 questions");
    expect(preview).toHaveTextContent("pass mark 70%");
    expect(preview).toHaveTextContent("Python, SQL");
  });

  it("assigns with the application id and an assessment id, nothing else", async () => {
    mockLoad(options({ available: [assignable()] }), evidence());
    vi.mocked(applicationAssessmentApi.assign).mockResolvedValue({
      application_id: applicationId,
      attempt_id: "attempt-1",
      assessment_id: assessmentId,
      assessment_title: "Backend Engineering Assessment",
      attempt_status: "assigned",
      already_assigned: false,
      message: "Backend Engineering Assessment has been assigned.",
    });
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Assign assessment" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm assignment" }),
    );

    await waitFor(() => {
      expect(applicationAssessmentApi.assign).toHaveBeenCalledWith(applicationId, {
        assessment_id: assessmentId,
      });
    });
    // The body carries no job, candidate or recruiter: those are derived
    // server-side, so a client cannot aim an assessment at someone else.
    expect(vi.mocked(applicationAssessmentApi.assign).mock.calls[0][1]).toEqual({
      assessment_id: assessmentId,
    });
  });

  it("sends the chosen schedule as an ISO instant", async () => {
    mockLoad(options({ available: [assignable()] }), evidence());
    vi.mocked(applicationAssessmentApi.assign).mockResolvedValue({
      application_id: applicationId,
      attempt_id: "attempt-1",
      assessment_id: assessmentId,
      assessment_title: "Backend Engineering Assessment",
      attempt_status: "assigned",
      already_assigned: false,
      message: "Assigned.",
    });
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Assign assessment" }),
    );
    await userEvent.type(
      await screen.findByLabelText(/Scheduled date\/time/i),
      "2026-01-05T09:30",
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm assignment" }),
    );

    await waitFor(() => {
      expect(applicationAssessmentApi.assign).toHaveBeenCalled();
    });
    const body = vi.mocked(applicationAssessmentApi.assign).mock.calls[0][1];
    expect(body.assessment_id).toBe(assessmentId);
    // Still no identity fields: a schedule says when, never who.
    expect(body).not.toHaveProperty("candidate_id");
    expect(body).not.toHaveProperty("job_id");
    // The picker gives local wall-clock time; the API takes an instant.
    expect(new Date(body.scheduled_for as string).getTime()).toBe(
      new Date("2026-01-05T09:30").getTime(),
    );
  });

  it("re-reads both projections after a successful assignment", async () => {
    mockLoad(options({ available: [assignable()] }), evidence());
    vi.mocked(applicationAssessmentApi.assign).mockResolvedValue({
      application_id: applicationId,
      attempt_id: "attempt-1",
      assessment_id: assessmentId,
      assessment_title: "Backend Engineering Assessment",
      attempt_status: "assigned",
      already_assigned: false,
      message: "Assigned.",
    });
    renderPanel();

    await screen.findByRole("heading", { name: "Assessment" });
    await userEvent.click(screen.getByRole("button", { name: "Assign assessment" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm assignment" }));

    await waitFor(() => {
      // Options and evidence each fetched a second time: the panel is never
      // patched locally, it re-reads authoritative state.
      expect(applicationAssessmentApi.getOptions).toHaveBeenCalledTimes(2);
      expect(applicationAssessmentApi.getEvidence).toHaveBeenCalledTimes(2);
    });
  });

  it("treats an already-assigned retry as a success, not a failure", async () => {
    mockLoad(options({ available: [assignable()] }), evidence());
    // What the server returns for a double-click or a retried request.
    vi.mocked(applicationAssessmentApi.assign).mockResolvedValue({
      application_id: applicationId,
      attempt_id: "attempt-1",
      assessment_id: assessmentId,
      assessment_title: "Backend Engineering Assessment",
      attempt_status: "assigned",
      already_assigned: true,
      message: "Backend Engineering Assessment is already assigned to this application.",
    });
    renderPanel();

    await screen.findByRole("heading", { name: "Assessment" });
    await userEvent.click(screen.getByRole("button", { name: "Assign assessment" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm assignment" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "Backend Engineering Assessment is already assigned to this application.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("explains why assignment is unavailable instead of hiding the control", async () => {
    mockLoad(
      options({
        current_status: "applied",
        can_assign: false,
        assign_unavailable_reason: "application_not_assessable",
        available: [assignable()],
      }),
      evidence(),
    );
    renderPanel();

    expect(
      await screen.findByText(
        "An assessment can only be assigned to a shortlisted application",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Assign assessment" }),
    ).toBeNull();
  });

  it("reports a finalized application with its own reason", async () => {
    mockLoad(
      options({
        current_status: "rejected",
        status_is_final: true,
        can_assign: false,
        assign_unavailable_reason: "application_is_final",
      }),
      evidence(),
    );
    renderPanel();

    expect(
      await screen.findByText("This application has reached a final outcome"),
    ).toBeInTheDocument();
  });

  it("says so when an assignable application has no published assessments", async () => {
    mockLoad(options({ available: [] }), evidence());
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Assign assessment" }),
    );
    expect(
      await screen.findByText(/No published assessments are available for this job yet/),
    ).toBeInTheDocument();
  });

  it("shows an assigned attempt as pending with no score and no pass verdict", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({
        attempt_count: 1,
        attempts: [summary()],
      }),
    );
    renderPanel();

    expect(await screen.findByText("Assigned")).toBeInTheDocument();
    expect(screen.getByText("Not graded")).toBeInTheDocument();
    // Nothing has been graded, so no pass/fail claim is made at all.
    expect(screen.queryByText(/pass mark of 70%/)).toBeNull();
    expect(screen.getByText(/0\/12 answered/)).toBeInTheDocument();
  });

  it("shows an in-progress attempt with its progress", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({
        attempt_count: 1,
        attempts: [summary({ status: "in_progress", questions_answered: 5 })],
      }),
    );
    renderPanel();

    expect(await screen.findByText("In progress")).toBeInTheDocument();
    expect(screen.getByText(/5\/12 answered/)).toBeInTheDocument();
  });

  it("presents a completed result as the assessment's own threshold, not a decision", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({
        attempt_count: 1,
        completed_count: 1,
        average_overall_score: 82,
        attempts: [
          summary({
            status: "completed",
            overall_score: 82,
            passed: true,
            submitted_at: "2026-01-06T10:00:00Z",
            completed_at: "2026-01-06T10:00:00Z",
            section_scores: [
              { section: "Coding", percentage: 88 },
              { section: "Technical MCQ", percentage: 80 },
            ],
            strong_skills: ["Python"],
            weak_skills: ["SQL"],
          }),
        ],
      }),
    );
    renderPanel();

    expect(await screen.findByTestId("attempt-status-attempt-1")).toHaveTextContent(
      "Completed",
    );
    // 82% legitimately appears twice: the attempt's own score and the
    // application-level average, which with one completed attempt is the same
    // figure. Both are shown rather than one standing in for the other.
    expect(screen.getAllByText("82%")).toHaveLength(2);
    // Explicitly framed as the assessment's own pass mark.
    expect(
      screen.getByText("Above this assessment's pass mark of 70%."),
    ).toBeInTheDocument();
    const sections = screen.getByTestId("assessment-section-scores");
    expect(within(sections).getByText("Coding")).toBeInTheDocument();
    expect(within(sections).getByText("88%")).toBeInTheDocument();
    expect(within(sections).getByText("Technical MCQ")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
  });

  it("reports a failing result as below the pass mark, not as a rejection", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({
        attempt_count: 1,
        completed_count: 1,
        average_overall_score: 40,
        attempts: [
          summary({ status: "completed", overall_score: 40, passed: false }),
        ],
      }),
    );
    renderPanel();

    expect(
      await screen.findByText("Below this assessment's pass mark of 70%."),
    ).toBeInTheDocument();
    // The panel never issues a hiring verdict of its own. (The header
    // deliberately says it does not, so the assertion looks for a verdict being
    // *made* rather than for the word appearing anywhere.)
    expect(screen.queryByText(/was rejected/i)).toBeNull();
    expect(screen.queryByText(/has been hired/i)).toBeNull();
    expect(screen.queryByText(/candidate (was|has been) (rejected|selected)/i)).toBeNull();
  });

  it("links to the detailed result for a graded attempt", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({
        attempt_count: 1,
        completed_count: 1,
        average_overall_score: 82,
        attempts: [summary({ status: "completed", overall_score: 82, passed: true })],
      }),
    );
    renderPanel();

    const link = await screen.findByRole("link", {
      name: "View detailed result",
    });
    expect(link).toHaveAttribute(
      "href",
      "/recruiter/assessments/results/attempt-1",
    );
  });

  it("offers no result link for an attempt that has not been graded", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({ attempt_count: 1, attempts: [summary()] }),
    );
    renderPanel();

    await screen.findByText("Assigned");
    expect(
      screen.queryByRole("link", { name: "View detailed result" }),
    ).toBeNull();
  });

  it("surfaces an integrity count without exposing the individual events", async () => {
    mockLoad(
      options({ has_assessments: true, attempt_count: 1 }),
      evidence({
        attempt_count: 1,
        attempts: [summary({ integrity_flag_count: 2 })],
      }),
    );
    renderPanel();

    expect(await screen.findByText(/2 integrity events recorded/)).toBeInTheDocument();
  });

  it("offers a retake only when the server says one is available", async () => {
    mockLoad(
      options({
        has_assessments: true,
        attempt_count: 1,
        actions: [
          {
            attempt_id: "attempt-1",
            status: "completed",
            can_reassign: true,
            reassign_unavailable_reason: null,
          },
        ],
      }),
      evidence({
        attempt_count: 1,
        completed_count: 1,
        average_overall_score: 82,
        attempts: [summary({ status: "completed", overall_score: 82, passed: true })],
      }),
    );
    renderPanel();

    const retake = await screen.findByRole("button", { name: "Assign a retake" });
    expect(retake).toBeEnabled();
  });

  it("disables the retake with the server's reason when one is not available", async () => {
    mockLoad(
      options({
        has_assessments: true,
        attempt_count: 1,
        actions: [
          {
            attempt_id: "attempt-1",
            status: "in_progress",
            can_reassign: false,
            reassign_unavailable_reason: "assessment_already_assigned",
          },
        ],
      }),
      evidence({
        attempt_count: 1,
        attempts: [summary({ status: "in_progress" })],
      }),
    );
    renderPanel();

    const retake = await screen.findByRole("button", { name: "Assign a retake" });
    expect(retake).toBeDisabled();
    // A disabled control carries the reason rather than vanishing, so "not
    // available yet" is distinguishable from "broken".
    expect(retake).toHaveAttribute(
      "title",
      "This assessment is already assigned to the application",
    );
  });

  it("shows a load failure with a recovery action instead of failing silently", async () => {
    vi.mocked(applicationAssessmentApi.getOptions).mockRejectedValue(
      new Error("boom"),
    );
    vi.mocked(applicationAssessmentApi.getEvidence).mockRejectedValue(
      new Error("boom"),
    );
    renderPanel();

    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("retries the load when the recovery action is used", async () => {
    vi.mocked(applicationAssessmentApi.getOptions).mockRejectedValueOnce(
      new Error("boom"),
    );
    vi.mocked(applicationAssessmentApi.getEvidence).mockRejectedValueOnce(
      new Error("boom"),
    );
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

    await waitFor(() => {
      expect(applicationAssessmentApi.getOptions).toHaveBeenCalledTimes(2);
    });
    expect(
      await screen.findByText("No assessment assigned to this application yet."),
    ).toBeInTheDocument();
  });

  it("states plainly that the result is evidence and never a decision", async () => {
    renderPanel();

    expect(
      await screen.findByText(/It never shortlists or rejects on its own/),
    ).toBeInTheDocument();
  });
});
