import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { candidateJobApi } from "../../api/jobs";
import { applicationAssessmentApi } from "../../api/applicationAssessment";
import { CandidateApplicationDetail } from "./ApplicationDetail";
import type { CandidateApplicationTrack } from "../../types/jobs";
import type { CandidateApplicationDecision } from "../../types/applicationDecision";
import type { CandidateApplicationInterviewView } from "../../types/interview";
import type { CandidateApplicationAssessmentView } from "../../types/applicationAssessment";

vi.mock("../../api/jobs", () => ({
  candidateJobApi: {
    getMyApplicationTrack: vi.fn(),
    withdrawApplication: vi.fn(),
  },
}));

// The page now mounts the Phase 12 assessment card, which loads on its own.
// Mocked so these tests are not silently making real HTTP calls.
vi.mock("../../api/applicationAssessment", () => ({
  applicationAssessmentApi: {
    getOptions: vi.fn(),
    assign: vi.fn(),
    getEvidence: vi.fn(),
    getMyApplicationAssessment: vi.fn(),
  },
}));

const addToast = vi.fn();
vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast }),
}));

const SECRET_INTERNAL_NOTE = "SECRET_INTERNAL_NOTE_do_not_leak";

function decision(
  overrides: Partial<CandidateApplicationDecision> = {},
): CandidateApplicationDecision {
  return {
    application_id: "app-1",
    job_id: "job-1",
    job_title: "Backend Engineer",
    status: "shortlisted",
    status_label: "Shortlisted",
    decision_outcome: "shortlisted",
    rejection_reason: null,
    candidate_message:
      "Your application for Backend Engineer has been shortlisted. The hiring team will be in touch about the next step.",
    decided_at: "2026-01-02T00:00:00Z",
    is_decision_final: false,
    ...overrides,
  };
}

function track(overrides: Partial<CandidateApplicationTrack> = {}): CandidateApplicationTrack {
  return {
    application_id: "app-1",
    job_id: "job-1",
    job_title: "Backend Engineer",
    company: "Northwind",
    location: "Remote",
    employment_type: "full_time",
    status: "shortlisted",
    status_label: "Shortlisted",
    is_decision_final: false,
    can_withdraw: true,
    applied_at: "2026-01-01T00:00:00Z",
    last_status_change_at: "2026-01-02T00:00:00Z",
    decided_at: "2026-01-02T00:00:00Z",
    status_changed: true,
    screening_status: "completed",
    screening_completed_at: "2026-01-01T12:00:00Z",
    has_match_explanation: true,
    decision: decision(),
    interview: null,
    stages: [
      { status: "applied", status_label: "Applied", reached: true, is_current: false },
      { status: "under_review", status_label: "Under Review", reached: true, is_current: false },
      { status: "shortlisted", status_label: "Shortlisted", reached: true, is_current: true },
    ],
    timeline: [
      {
        status: "applied",
        status_label: "Applied",
        from_status: null,
        occurred_at: "2026-01-01T00:00:00Z",
        is_current: false,
        message: null,
      },
      {
        status: "under_review",
        status_label: "Under Review",
        from_status: "applied",
        occurred_at: "2026-01-01T18:00:00Z",
        is_current: false,
        message:
          "Your application for Backend Engineer is still under review. No decision has been made yet.",
      },
      {
        status: "shortlisted",
        status_label: "Shortlisted",
        from_status: "under_review",
        occurred_at: "2026-01-02T00:00:00Z",
        is_current: true,
        message:
          "Your application for Backend Engineer has been shortlisted. The hiring team will be in touch about the next step.",
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/candidate/applications/app-1"]}>
      <Routes>
        <Route
          path="/candidate/applications/:applicationId"
          element={<CandidateApplicationDetail />}
        />
        <Route path="/candidate/applications" element={<p>Applications list</p>} />
        <Route
          path="/candidate/applications/:applicationId/explanation"
          element={<p>Match explanation page</p>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

function assessmentView(
  overrides: Partial<CandidateApplicationAssessmentView> = {},
): CandidateApplicationAssessmentView {
  return {
    application_id: "app-1",
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

describe("CandidateApplicationDetail tracking view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(track());
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      assessmentView(),
    );
  });

  it("fetches the tracking view for the application in the route", async () => {
    renderPage();

    await screen.findByText("Where things stand");
    expect(candidateJobApi.getMyApplicationTrack).toHaveBeenCalledWith("app-1");
  });

  it("shows only the stages the server reported, marking the current one", async () => {
    renderPage();

    await screen.findByText("Where things stand");
    expect(screen.getByTestId("stage-applied")).toHaveTextContent("Applied");
    expect(screen.getByTestId("stage-shortlisted")).toHaveTextContent("current");
    // No stage is rendered that the server did not report.
    expect(screen.queryByTestId("stage-offered")).toBeNull();
    expect(screen.queryByTestId("stage-hired")).toBeNull();
  });

  it("renders the recorded timeline in order with the approved wording", async () => {
    renderPage();

    await screen.findByText("Where things stand");
    const activity = screen.getByRole("heading", { name: "Activity" }).parentElement!;
    const entries = activity.querySelectorAll("li");
    expect(entries).toHaveLength(3);
    expect(entries[0]).toHaveTextContent("Applied");
    expect(entries[1]).toHaveTextContent("Under Review");
    expect(entries[2]).toHaveTextContent("Shortlisted");
    expect(entries[2]).toHaveTextContent("current");
    // The decision wording the API returned is shown verbatim.
    expect(
      screen.getAllByText(/has been shortlisted/).length,
    ).toBeGreaterThan(0);
  });

  it("reports a 404 as an unavailable application rather than an error", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockRejectedValue({
      response: { status: 404 },
    });
    renderPage();

    expect(await screen.findByText("Application unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Could not load this application")).toBeNull();
  });

  it("offers a retry when the request fails for another reason", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockRejectedValue(new Error("boom"));
    renderPage();

    expect(
      await screen.findByText("Could not load this application"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => {
      expect(candidateJobApi.getMyApplicationTrack).toHaveBeenCalledTimes(2);
    });
  });

  it("offers withdrawal only when the server says it is still allowed", async () => {
    const { unmount } = renderPage();
    await screen.findByText("Where things stand");
    expect(screen.getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    unmount();

    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ status: "rejected", status_label: "Not Selected", can_withdraw: false, is_decision_final: true }),
    );
    renderPage();

    await screen.findByText("Where things stand");
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
    expect(
      screen.getByText(/reached a final outcome and is no longer changing/),
    ).toBeInTheDocument();
  });

  it("re-reads the tracking view after a withdrawal instead of patching state", async () => {
    vi.mocked(candidateJobApi.withdrawApplication).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Withdraw" }));

    await waitFor(() => {
      expect(candidateJobApi.withdrawApplication).toHaveBeenCalledWith("app-1");
    });
    await waitFor(() => {
      expect(candidateJobApi.getMyApplicationTrack).toHaveBeenCalledTimes(2);
    });
  });

  it("links to the match explanation only when one exists", async () => {
    const { unmount } = renderPage();
    await screen.findByText("Where things stand");
    await userEvent.click(
      screen.getByRole("button", { name: "How does my profile match?" }),
    );
    expect(await screen.findByText("Match explanation page")).toBeInTheDocument();
    unmount();

    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ screening_status: "not_started", has_match_explanation: false }),
    );
    renderPage();

    await screen.findByText("Where things stand");
    expect(
      screen.queryByRole("button", { name: "How does my profile match?" }),
    ).toBeNull();
    expect(
      screen.getByText(/A match explanation is not available for this application yet/),
    ).toBeInTheDocument();
  });

  it("never renders a staff-only field even if one reaches the client", async () => {
    // The server allowlists the response; this guards the UI against a field
    // being added to the payload later and rendered without review.
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({
        decision: decision(),
        ...({
          internal_note: SECRET_INTERNAL_NOTE,
        } as Record<string, unknown>),
      } as Partial<CandidateApplicationTrack>),
    );
    renderPage();

    await screen.findByText("Where things stand");
    expect(screen.queryByText(SECRET_INTERNAL_NOTE)).toBeNull();
  });

  it("copes with an application whose job is no longer listed", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({
        job_title: "",
        company: "",
        location: "",
        decision: decision({ job_title: "" }),
      }),
    );
    renderPage();

    expect(await screen.findByText("Position no longer listed")).toBeInTheDocument();
  });

  it("renders an empty activity list when no history exists yet", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ timeline: [], stages: [] }),
    );
    renderPage();

    expect(
      await screen.findByText("No status updates recorded yet."),
    ).toBeInTheDocument();
  });
});

function interview(
  overrides: Partial<CandidateApplicationInterviewView> = {},
): CandidateApplicationInterviewView {
  return {
    application_id: "app-1",
    interview_id: "int-1",
    status: "scheduled",
    scheduled_at: "2026-01-05T14:00:00Z",
    duration_minutes: 45,
    completed_at: null,
    next_upcoming_at: "2026-01-05T14:00:00Z",
    has_completed: false,
    interview_count: 1,
    message: "Your interview has been scheduled.",
    ...overrides,
  };
}

describe("CandidateApplicationDetail interview card", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      assessmentView(),
    );
  });

  it("shows nothing about the interview when none is linked", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ interview: null }),
    );
    renderPage();

    await screen.findByText("Where things stand");
    expect(screen.queryByTestId("candidate-interview")).toBeNull();
  });

  it("shows the scheduled time and duration the server sent", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ interview: interview() }),
    );
    renderPage();

    const card = await screen.findByTestId("candidate-interview");
    expect(card).toHaveTextContent("Your interview");
    expect(card).toHaveTextContent("Your interview has been scheduled.");
    expect(card).toHaveTextContent("45 minutes");
    // The approved stage wording is shown, not a raw enum value.
    expect(card).toHaveTextContent("Scheduled");
  });

  it("shows the completed date once the interview happened", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({
        status: "interviewed",
        status_label: "Interviewed",
        interview: interview({
          status: "completed",
          has_completed: true,
          completed_at: "2026-01-05T15:00:00Z",
        }),
      }),
    );
    renderPage();

    const card = await screen.findByTestId("candidate-interview");
    expect(card).toHaveTextContent("Interviewed");
    expect(card).toHaveTextContent("Completed");
  });

  it("copes with a null message and no schedule time", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({
        interview: interview({
          message: null,
          scheduled_at: null,
          next_upcoming_at: null,
          duration_minutes: null,
        }),
      }),
    );
    renderPage();

    const card = await screen.findByTestId("candidate-interview");
    expect(card).toHaveTextContent("Your interview details will appear here.");
  });

  it("never renders staff-only interview fields even if one reaches the client", async () => {
    // The server allowlists this view. This guards the UI against a scorecard or
    // recruiter note being added to the payload later and rendered unreviewed.
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({
        interview: interview({
          ...({
            scorecard: { overall_score: 91 },
            recruiter_notes: SECRET_INTERNAL_NOTE,
          } as Record<string, unknown>),
        }),
      } as Partial<CandidateApplicationTrack>),
    );
    renderPage();

    await screen.findByTestId("candidate-interview");
    expect(screen.queryByText(SECRET_INTERNAL_NOTE)).toBeNull();
    expect(screen.queryByText(/overall_score|91/)).toBeNull();
  });
});

describe("CandidateApplicationDetail assessment card", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      assessmentView(),
    );
  });

  it("shows no assessment section content when none is assigned", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(track());
    renderPage();

    await screen.findByText("Where things stand");
    expect(await screen.findByTestId("candidate-assessment-empty")).toHaveTextContent(
      "No assessment assigned",
    );
  });

  it("surfaces an assigned assessment and its start action on the application", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(track());
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      assessmentView({
        has_assessment: true,
        attempt_id: "attempt-1",
        assessment_id: "assess-1",
        assessment_title: "Backend Engineering Assessment",
        status: "assigned",
        attempt_number: 1,
        can_start: true,
        message: "You have been assigned an assessment.",
      }),
    );
    renderPage();

    const card = await screen.findByTestId("candidate-assessment");
    expect(card).toHaveTextContent("Backend Engineering Assessment");
    expect(card).toHaveTextContent("You have been assigned an assessment.");
    expect(
      screen.getByRole("button", { name: "Start assessment" }),
    ).toBeInTheDocument();
  });

  it("keeps the interview and the assessment on the same application page", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ interview: interview() }),
    );
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      assessmentView({
        has_assessment: true,
        has_completed: true,
        completed_count: 1,
        attempt_count: 1,
        attempt_id: "attempt-1",
        assessment_id: "assess-1",
        assessment_title: "Backend Engineering Assessment",
        status: "completed",
        can_start: false,
        overall_score: 82,
      }),
    );
    renderPage();

    // Neither subsystem displaces the other, and neither overwrites the other's
    // state: the interview card and the assessment card coexist.
    expect(await screen.findByTestId("candidate-interview")).toBeInTheDocument();
    const card = await screen.findByTestId("candidate-assessment");
    expect(card).toHaveTextContent("82%");
    expect(card).not.toHaveTextContent(SECRET_INTERNAL_NOTE);
  });
});

/**
 * A candidate quoting an id to support is the whole point of showing these, so
 * they have to be present, labelled, and copyable -- and the copy has to yield
 * the full value, not the abbreviation on screen.
 */
describe("CandidateApplicationDetail identifiers", () => {
  const APPLICATION_UUID = "8f4c2b91-3d6e-4a58-b0f1-92c7e6d4a803";
  const JOB_UUID = "6b1d9f20-4c77-4a91-8f3e-2a5c0b7d1e66";
  const INTERVIEW_UUID = "b3e9a517-2f84-4d0a-9c66-71a4e8d35b29";

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(applicationAssessmentApi.getMyApplicationAssessment).mockResolvedValue(
      assessmentView(),
    );
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({
        application_id: APPLICATION_UUID,
        job_id: JOB_UUID,
        interview: interview({ interview_id: INTERVIEW_UUID }),
      }),
    );
  });

  it("labels the application and job ids distinctly", async () => {
    renderPage();
    await screen.findByText("Where things stand");

    // "Application ID" and "Job ID" cannot be read as the same thing.
    expect(
      screen.getByText("Application ID", { selector: "label" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Job ID", { selector: "label" })).toBeInTheDocument();
    expect(screen.getByTitle(APPLICATION_UUID)).toBeInTheDocument();
    expect(screen.getByTitle(JOB_UUID)).toBeInTheDocument();
  });

  it("copies the full application id even though the screen shows a prefix", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });
    renderPage();
    await screen.findByText("Where things stand");

    const shown = screen.getByTitle(APPLICATION_UUID);
    expect(shown).not.toHaveTextContent(APPLICATION_UUID);

    await userEvent.click(
      screen.getByRole("button", { name: /copy application id/i }),
    );
    expect(writeText).toHaveBeenCalledWith(APPLICATION_UUID);
  });

  it("shows the interview id once the application has one", async () => {
    renderPage();
    await screen.findByText("Where things stand");
    expect(
      screen.getByText("Interview ID", { selector: "label" }),
    ).toBeInTheDocument();
    expect(screen.getByTitle(INTERVIEW_UUID)).toBeInTheDocument();
  });

  it("omits the interview id before an interview is scheduled", async () => {
    vi.mocked(candidateJobApi.getMyApplicationTrack).mockResolvedValue(
      track({ application_id: APPLICATION_UUID, job_id: JOB_UUID, interview: null }),
    );
    renderPage();
    await screen.findByText("Where things stand");

    expect(
      screen.queryByText("Interview ID", { selector: "label" }),
    ).not.toBeInTheDocument();
    // The application reference is still there: it is the candidate's own record.
    expect(screen.getByTitle(APPLICATION_UUID)).toBeInTheDocument();
  });
});
