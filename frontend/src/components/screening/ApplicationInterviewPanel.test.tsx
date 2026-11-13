import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { interviewApi } from "../../api/interview";
import { ToastProvider } from "../../contexts/ToastContext";
import { ApplicationInterviewPanel } from "./ApplicationInterviewPanel";
import type {
  ApplicationInterviewActionOption,
  ApplicationInterviewEvidence,
  ApplicationInterviewOptions,
  ApplicationInterviewScheduleResult,
  ApplicationInterviewSummary,
  InterviewRoomState,
} from "../../types/interview";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    getApplicationInterviewOptions: vi.fn(),
    getApplicationInterviews: vi.fn(),
    scheduleApplicationInterview: vi.fn(),
    rescheduleApplicationInterview: vi.fn(),
    cancelApplicationInterview: vi.fn(),
    completeApplicationInterview: vi.fn(),
    // Phase 15: feedback + stage actions. Only called on user action, but they
    // must exist so a test that exercises them does not hit an undefined mock.
    saveApplicationInterviewFeedback: vi.fn(),
    getApplicationInterviewFeedback: vi.fn(),
    advanceApplicationToHr: vi.fn(),
    rejectApplicationFromInterview: vi.fn(),
    // The room panel is mounted per interview, so these must exist for any test
    // that renders a panel containing an interview.
    getInterviewRoom: vi.fn(),
    joinInterviewRoom: vi.fn(),
  },
}));

const applicationId = "app-1";

function actionOption(
  overrides: Partial<ApplicationInterviewActionOption> = {},
): ApplicationInterviewActionOption {
  return {
    interview_id: "int-1",
    status: "scheduled",
    can_reschedule: true,
    reschedule_unavailable_reason: null,
    can_cancel: true,
    cancel_unavailable_reason: null,
    can_complete: true,
    complete_unavailable_reason: null,
    ...overrides,
  };
}

function options(
  overrides: Partial<ApplicationInterviewOptions> = {},
): ApplicationInterviewOptions {
  return {
    application_id: applicationId,
    current_status: "shortlisted",
    status_is_final: false,
    can_schedule: true,
    schedule_unavailable_reason: null,
    has_interviews: false,
    active_interview_id: null,
    options: [],
    hr_eligible: false,
    recruiter_stage_complete: false,
    can_advance: false,
    advance_unavailable_reason: null,
    can_schedule_hr: false,
    schedule_hr_unavailable_reason: null,
    can_reject: false,
    reject_unavailable_reason: null,
    ...overrides,
  };
}

function summary(
  overrides: Partial<ApplicationInterviewSummary> = {},
): ApplicationInterviewSummary {
  return {
    id: "int-1",
    application_id: applicationId,
    job_id: "job-1",
    candidate_id: "cand-1",
    interview_type: "recruiter_scheduled",
    stage: "recruiter",
    status: "scheduled",
    scheduled_at: "2026-01-05T14:00:00Z",
    rescheduled_at: null,
    started_at: null,
    completed_at: null,
    duration_minutes: 60,
    total_questions: 10,
    questions_answered: 0,
    has_scorecard: false,
    overall_score: null,
    recommendation: null,
    created_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

function evidence(
  overrides: Partial<ApplicationInterviewEvidence> = {},
): ApplicationInterviewEvidence {
  return {
    application_id: applicationId,
    job_id: "job-1",
    job_title: "Backend Engineer",
    candidate_id: "cand-1",
    candidate_name: "Dana Candidate",
    application_status: "shortlisted",
    interview_count: 0,
    completed_count: 0,
    average_overall_score: null,
    interviews: [],
    hr_eligible: false,
    advanced_to_hr_at: null,
    ...overrides,
  };
}

function roomState(
  overrides: Partial<InterviewRoomState> = {},
): InterviewRoomState {
  return {
    interview_id: "int-1",
    application_id: applicationId,
    interview_type: "recruiter_scheduled",
    stage: "recruiter",
    status: "scheduled",
    state: "ready_to_join",
    your_role: "interviewer",
    room_id: "room-abc123",
    scheduled_at: "2026-01-05T14:00:00Z",
    rescheduled_at: null,
    timezone: "UTC",
    duration_minutes: 60,
    join_opens_at: "2026-01-05T13:45:00Z",
    join_closes_at: "2026-01-05T15:00:00Z",
    server_time: "2026-01-05T13:50:00Z",
    can_join: true,
    unavailable_reason: null,
    you_joined: false,
    presence: {
      candidate_joined: false,
      candidate_joined_at: null,
      interviewer_joined: false,
      interviewer_joined_at: null,
    },
    message: "The room is open. Join when you are ready.",
    ...overrides,
  };
}

function result(
  overrides: Partial<ApplicationInterviewScheduleResult> = {},
): ApplicationInterviewScheduleResult {
  return {
    application_id: applicationId,
    interview_id: "int-1",
    interview_status: "scheduled",
    application_status: "interview_scheduled",
    application_status_changed: true,
    message: "Interview scheduled.",
    ...overrides,
  };
}

function mockLoad(
  loadedOptions: ApplicationInterviewOptions,
  loadedEvidence: ApplicationInterviewEvidence,
) {
  vi.mocked(interviewApi.getApplicationInterviewOptions).mockResolvedValue(
    loadedOptions,
  );
  vi.mocked(interviewApi.getApplicationInterviews).mockResolvedValue(
    loadedEvidence,
  );
  // Default the room to a plain closed state so a panel that mounts it does not
  // depend on an unmocked promise; tests about the room override this.
  vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue({
    ...roomState(),
    can_join: false,
    unavailable_reason: "join_window_not_open",
  });
}

function renderPanel(onStatusChanged = vi.fn()) {
  render(
    <MemoryRouter>
      <ToastProvider>
        <ApplicationInterviewPanel
          applicationId={applicationId}
          onStatusChanged={onStatusChanged}
        />
      </ToastProvider>
    </MemoryRouter>,
  );
  return onStatusChanged;
}

describe("ApplicationInterviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoad(options(), evidence());
  });

  it("loads the options and the evidence together, keyed by the application", async () => {
    renderPanel();

    await screen.findByRole("heading", { name: "Interview" });
    expect(interviewApi.getApplicationInterviewOptions).toHaveBeenCalledWith(
      applicationId,
    );
    expect(interviewApi.getApplicationInterviews).toHaveBeenCalledWith(
      applicationId,
    );
  });

  it("says scheduling is not a hiring decision", async () => {
    renderPanel();

    await screen.findByRole("heading", { name: "Interview" });
    expect(screen.getByText(/not a hiring decision/i)).toBeInTheDocument();
  });

  it("shows the empty state when no interview is recorded", async () => {
    renderPanel();

    expect(
      await screen.findByText("No interviews recorded for this application yet."),
    ).toBeInTheDocument();
  });

  it("reports a load failure instead of rendering an empty panel", async () => {
    vi.mocked(interviewApi.getApplicationInterviews).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "Not authorized" } },
    });
    renderPanel();

    expect(await screen.findByText("Not authorized")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Schedule interview" }),
    ).toBeNull();
  });

  it("schedules an interview and tells the page the application moved", async () => {
    vi.mocked(interviewApi.scheduleApplicationInterview).mockResolvedValue(
      result(),
    );
    const onStatusChanged = renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Schedule interview" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm schedule" }),
    );

    await waitFor(() => {
      expect(interviewApi.scheduleApplicationInterview).toHaveBeenCalledWith(
        applicationId,
        expect.objectContaining({
          scheduled_at: expect.any(String),
          duration_minutes: 60,
          question_count: 10,
          difficulty: "medium",
        }),
      );
    });
    // Only the server decides whether the status moved, and the page is told.
    expect(onStatusChanged).toHaveBeenCalledWith(
      expect.objectContaining({ application_status: "interview_scheduled" }),
    );
  });

  it("sends the instant as ISO, not the local datetime-local string", async () => {
    vi.mocked(interviewApi.scheduleApplicationInterview).mockResolvedValue(
      result(),
    );
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Schedule interview" }),
    );
    const slot = screen.getByLabelText("Date & time");
    await userEvent.clear(slot);
    await userEvent.type(slot, "2026-03-04T09:30");
    await userEvent.click(screen.getByRole("button", { name: "Confirm schedule" }));

    await waitFor(() => {
      const call = vi.mocked(interviewApi.scheduleApplicationInterview).mock
        .calls[0];
      expect(call[1].scheduled_at).toBe(new Date("2026-03-04T09:30").toISOString());
    });
  });

  it("refuses to send an empty date instead of posting an invalid instant", async () => {
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Schedule interview" }),
    );
    await userEvent.clear(screen.getByLabelText("Date & time"));
    await userEvent.click(screen.getByRole("button", { name: "Confirm schedule" }));

    expect(
      await screen.findByText("Choose a valid date and time"),
    ).toBeInTheDocument();
    expect(interviewApi.scheduleApplicationInterview).not.toHaveBeenCalled();
  });

  it("does not tell the page to re-sort when only the interview changed", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [actionOption()],
      }),
      evidence({
        application_status: "interview_scheduled",
        interview_count: 1,
        interviews: [summary()],
      }),
    );
    vi.mocked(interviewApi.completeApplicationInterview).mockResolvedValue(
      result({
        interview_status: "completed",
        application_status: "interviewed",
        application_status_changed: false,
      }),
    );
    const onStatusChanged = renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(interviewApi.completeApplicationInterview).toHaveBeenCalledWith(
        applicationId,
        "int-1",
      );
    });
    expect(onStatusChanged).not.toHaveBeenCalled();
  });

  it("marks a scheduled interview complete", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [actionOption()],
      }),
      evidence({
        interview_count: 1,
        interviews: [summary()],
      }),
    );
    vi.mocked(interviewApi.completeApplicationInterview).mockResolvedValue(
      result({ interview_status: "completed", application_status: "interviewed" }),
    );
    const onStatusChanged = renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(interviewApi.completeApplicationInterview).toHaveBeenCalled();
    });
    expect(onStatusChanged).toHaveBeenCalledWith(
      expect.objectContaining({ application_status: "interviewed" }),
    );
  });

  it("cancels an interview with the internal reason, and says who sees it", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [actionOption()],
      }),
      evidence({ interview_count: 1, interviews: [summary()] }),
    );
    vi.mocked(interviewApi.cancelApplicationInterview).mockResolvedValue(
      result({ interview_status: "cancelled", message: "Interview cancelled." }),
    );
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await userEvent.type(
      screen.getByLabelText(/Reason \(internal/),
      "Candidate rescheduled",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm cancellation" }),
    );

    await waitFor(() => {
      expect(interviewApi.cancelApplicationInterview).toHaveBeenCalledWith(
        applicationId,
        "int-1",
        { reason: "Candidate rescheduled" },
      );
    });
  });

  it("omits an empty cancel reason rather than sending a blank string", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [actionOption()],
      }),
      evidence({ interview_count: 1, interviews: [summary()] }),
    );
    vi.mocked(interviewApi.cancelApplicationInterview).mockResolvedValue(
      result({ interview_status: "cancelled" }),
    );
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm cancellation" }),
    );

    await waitFor(() => {
      expect(interviewApi.cancelApplicationInterview).toHaveBeenCalledWith(
        applicationId,
        "int-1",
        {},
      );
    });
  });

  it("reschedules the same interview, keeping its record", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [actionOption()],
      }),
      evidence({ interview_count: 1, interviews: [summary()] }),
    );
    vi.mocked(interviewApi.rescheduleApplicationInterview).mockResolvedValue(
      result({ application_status_changed: false }),
    );
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Reschedule" }));
    const field = screen.getByLabelText("New date & time");
    await userEvent.clear(field);
    await userEvent.type(field, "2026-04-01T10:00");
    await userEvent.click(screen.getByRole("button", { name: "Save new time" }));

    await waitFor(() => {
      expect(interviewApi.rescheduleApplicationInterview).toHaveBeenCalledWith(
        applicationId,
        "int-1",
        expect.objectContaining({
          scheduled_at: new Date("2026-04-01T10:00").toISOString(),
        }),
      );
    });
    // Rescheduling moves the interview, not the application stage.
    expect(interviewApi.completeApplicationInterview).not.toHaveBeenCalled();
  });

  it("explains a disabled action with the server's reason rather than hiding it", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [
          actionOption({
            can_complete: false,
            complete_unavailable_reason: "interview_already_finished",
          }),
        ],
      }),
      evidence({
        interview_count: 1,
        completed_count: 1,
        interviews: [summary({ status: "completed" })],
      }),
    );
    renderPanel();

    const complete = await screen.findByRole("button", { name: "Mark complete" });
    expect(complete).toBeDisabled();
    expect(complete).toHaveAttribute(
      "title",
      "This interview has already finished",
    );
  });

  it("does not offer scheduling for an application that is not shortlisted", async () => {
    mockLoad(
      options({
        current_status: "applied",
        can_schedule: false,
        schedule_unavailable_reason: "application_not_shortlisted",
      }),
      evidence({ application_status: "applied" }),
    );
    renderPanel();

    expect(
      await screen.findByText("Only a shortlisted application can be interviewed"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Schedule interview" }),
    ).toBeNull();
  });

  it("does not offer scheduling once the application is final", async () => {
    mockLoad(
      options({
        current_status: "rejected",
        status_is_final: true,
        can_schedule: false,
        schedule_unavailable_reason: "application_is_final",
      }),
      evidence({ application_status: "rejected" }),
    );
    renderPanel();

    expect(
      await screen.findByText("This application is finalized"),
    ).toBeInTheDocument();
  });

  it("shows the score as evidence and averages only completed interviews", async () => {
    mockLoad(
      options({
        current_status: "interviewed",
        has_interviews: true,
        options: [actionOption({ status: "completed" })],
      }),
      evidence({
        application_status: "interviewed",
        interview_count: 2,
        completed_count: 1,
        average_overall_score: 78,
        interviews: [
          summary({
            status: "completed",
            overall_score: 78,
            recommendation: "recommend",
            has_scorecard: true,
            questions_answered: 10,
            completed_at: "2026-01-05T15:00:00Z",
          }),
          summary({
            id: "int-2",
            status: "scheduled",
            scheduled_at: "2026-01-08T14:00:00Z",
          }),
        ],
      }),
    );
    renderPanel();

    // 78 appears twice: the average, and the one completed interview's score.
    await waitFor(() => {
      expect(screen.getAllByText("78")).toHaveLength(2);
    });
    expect(screen.getByText("Recommend")).toBeInTheDocument();

    // The interview nobody has taken yet must contribute no score, and so must
    // not pull the average down toward 39.
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[1]).toHaveTextContent("0/10 answered");
    expect(rows[1]).not.toHaveTextContent("Score");
    expect(rows[1]).not.toHaveTextContent("Recommend");
  });

  it("re-reads the state after the server refuses an action, rather than leaving a stale button", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-1",
        options: [actionOption()],
      }),
      evidence({ interview_count: 1, interviews: [summary()] }),
    );
    vi.mocked(interviewApi.completeApplicationInterview).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "This interview has already finished" } },
    });
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Mark complete" }));

    // Both reads are re-issued so the panel matches the server again.
    await waitFor(() => {
      expect(interviewApi.getApplicationInterviewOptions).toHaveBeenCalledTimes(2);
    });
    expect(
      await screen.findByText("This interview has already finished"),
    ).toBeInTheDocument();
  });

  it("clears the previous applicant's evidence when the selection changes", async () => {
    const { rerender } = render(
      <MemoryRouter>
        <ToastProvider>
          <ApplicationInterviewPanel applicationId="app-1" />
        </ToastProvider>
      </MemoryRouter>,
    );
    await screen.findByText("No interviews recorded for this application yet.");

    mockLoad(
      options({ current_status: "interviewed", can_schedule: false, schedule_unavailable_reason: "application_is_final" }),
      evidence({ application_status: "interviewed", interview_count: 1, interviews: [summary({ status: "completed" })] }),
    );
    rerender(
      <MemoryRouter>
        <ToastProvider>
          <ApplicationInterviewPanel applicationId="app-2" />
        </ToastProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(interviewApi.getApplicationInterviewOptions).toHaveBeenCalledWith(
        "app-2",
      );
    });
    expect(screen.getByText("This application is finalized")).toBeInTheDocument();
  });

  it("displays HR interview in coordination view without room panel, complete button, or feedback controls", async () => {
    mockLoad(
      options({
        current_status: "interview_scheduled",
        has_interviews: true,
        active_interview_id: "int-hr-1",
        options: [actionOption({ interview_id: "int-hr-1", can_complete: true, can_reschedule: true, can_cancel: true })],
      }),
      evidence({
        interview_count: 1,
        interviews: [
          summary({
            id: "int-hr-1",
            stage: "hr",
            status: "scheduled",
          }),
        ],
      }),
    );
    renderPanel();

    expect(await screen.findByText("HR Interview")).toBeInTheDocument();
    expect(screen.getByText(/Conducted, attended, and evaluated by the assigned HR Manager/i)).toBeInTheDocument();

    // Verify forbidden controls are absent
    expect(screen.queryByRole("button", { name: "Mark complete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record feedback" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Join room" })).not.toBeInTheDocument();

    // Verify allowed coordination controls are present
    expect(screen.getByRole("button", { name: "Reschedule" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });
});
