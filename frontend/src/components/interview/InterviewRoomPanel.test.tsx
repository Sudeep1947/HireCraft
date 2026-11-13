import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { interviewApi } from "../../api/interview";
import { InterviewRoomPanel } from "./InterviewRoomPanel";
import type { InterviewRoomState } from "../../types/interview";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    getInterviewRoom: vi.fn(),
    joinInterviewRoom: vi.fn(),
  },
}));

const interviewId = "int-1";

function room(
  overrides: Partial<InterviewRoomState> = {},
): InterviewRoomState {
  return {
    interview_id: interviewId,
    application_id: "app-1",
    interview_type: "recruiter_scheduled",
    stage: "recruiter",
    status: "scheduled",
    // The server's human-facing display state, which the panel renders in the
    // status badge. It is a separate field from `status`, and the server always
    // sends it.
    state: "ready_to_join",
    your_role: "interviewer",
    room_id: "room-abc123",
    scheduled_at: "2026-01-05T14:00:00Z",
    rescheduled_at: null,
    timezone: "UTC",
    duration_minutes: 60,
    join_opens_at: "2026-01-05T13:45:00Z",
    join_closes_at: "2026-01-05T15:00:00Z",
    // Fixed so countdowns are deterministic: 10 minutes before the start, i.e.
    // inside the window that opened 15 minutes early.
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

function renderPanel(onJoined?: () => void) {
  render(<InterviewRoomPanel interviewId={interviewId} onJoined={onJoined} />);
}

describe("InterviewRoomPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(room());
  });

  it("reads the room by interview id, not by application or room id", async () => {
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(interviewApi.getInterviewRoom).toHaveBeenCalledWith(interviewId);
  });

  it("shows the server's own status and message rather than its own wording", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        status: "in_progress",
        state: "in_progress",
        message: "The interview is under way.",
      }),
    );
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.getByText("The interview is under way.")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  // The load-bearing property: the button reflects the server's verdict rather
  // than a rule reimplemented from the browser clock.
  it("offers Join when the server says the window is open", async () => {
    renderPanel();
    const join = await screen.findByRole("button", { name: /join interview room/i });
    expect(join).toBeEnabled();
  });

  it("disables Join and shows the server's reason when joining is refused", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        can_join: false,
        unavailable_reason: "join_window_not_open",
        join_opens_at: "2026-01-05T13:55:00Z",
      }),
    );
    renderPanel();
    const join = await screen.findByRole("button", { name: /join interview room/i });
    expect(join).toBeDisabled();
    expect(
      screen.getByText(/room opens shortly before the scheduled time/i),
    ).toBeInTheDocument();
  });

  it("distinguishes a closed window from an interview that is not joinable", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        status: "cancelled",
        can_join: false,
        unavailable_reason: "interview_not_joinable",
      }),
    );
    renderPanel();
    const join = await screen.findByRole("button", { name: /join interview room/i });
    expect(join).toBeDisabled();
    expect(
      screen.getByText(/not open for joining/i),
    ).toBeInTheDocument();
  });

  it("counts down against the server clock, not the viewer's device", async () => {
    // A device 30 minutes fast would, from its own clock, already be past the
    // start time. The gap must be measured from server_time: 13:50 server time
    // to a 14:00 opening is ten minutes, whatever the browser thinks.
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        can_join: false,
        unavailable_reason: "join_window_not_open",
        join_opens_at: "2026-01-05T14:00:00Z",
      }),
    );
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.getByText(/opens in 10 minutes/i)).toBeInTheDocument();
  });

  it("joins once and reports it to the caller so the page can refresh", async () => {
    const onJoined = vi.fn();
    vi.mocked(interviewApi.joinInterviewRoom).mockResolvedValue(
      room({
        status: "in_progress",
        you_joined: true,
        presence: {
          candidate_joined: false,
          candidate_joined_at: null,
          interviewer_joined: true,
          interviewer_joined_at: "2026-01-05T13:50:00Z",
        },
      }),
    );
    renderPanel(onJoined);

    await userEvent.click(
      await screen.findByRole("button", { name: /join interview room/i }),
    );

    await waitFor(() =>
      expect(interviewApi.joinInterviewRoom).toHaveBeenCalledWith(interviewId),
    );
    expect(onJoined).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/you are in this room/i)).toBeInTheDocument();
  });

  it("stops offering Join to someone who has already joined", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({ you_joined: true, presence: room().presence }),
    );
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.queryByRole("button", { name: /join interview room/i })).toBeNull();
  });

  // Attendance is a record, not a connection: no Leave control exists, because
  // one would imply the server can un-record a participant.
  it("offers no Leave control, since attendance is recorded", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(room({ you_joined: true }));
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.queryByRole("button", { name: /leave/i })).toBeNull();
    expect(screen.getByText(/leaving this page does not remove it/i)).toBeInTheDocument();
  });

  // Presence is labelled by role, never by person: the recruiter's view must not
  // name the candidate, and the candidate's must not name the interviewer.
  it("reports the other participant's attendance by role, not by identity", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        your_role: "interviewer",
        presence: {
          candidate_joined: true,
          candidate_joined_at: "2026-01-05T13:49:00Z",
          interviewer_joined: true,
          interviewer_joined_at: "2026-01-05T13:50:00Z",
        },
      }),
    );
    renderPanel();
    await screen.findByTestId("interview-room");

    expect(screen.getByText("Candidate")).toBeInTheDocument();
    expect(screen.getByText(/^Joined/)).toBeInTheDocument();
    expect(screen.queryByText(/Dana|Candidate Name|cand-/i)).toBeNull();
  });

  it("swaps the roles for a candidate without changing the component", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        your_role: "candidate",
        presence: {
          candidate_joined: false,
          candidate_joined_at: null,
          interviewer_joined: true,
          interviewer_joined_at: "2026-01-05T13:50:00Z",
        },
      }),
    );
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.getByText("Interviewer")).toBeInTheDocument();
    expect(screen.getByText("Not joined")).toBeInTheDocument();
  });

  it("re-reads the room after a refused join rather than guessing locally", async () => {
    vi.mocked(interviewApi.joinInterviewRoom).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "This interview has already finished." } },
    });
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /join interview room/i }),
    );

    expect(
      await screen.findByText("This interview has already finished."),
    ).toBeInTheDocument();
    // Two reads: the initial load, then the re-read after the refusal.
    expect(interviewApi.getInterviewRoom).toHaveBeenCalledTimes(2);
  });

  it("reports a failed load instead of showing an empty room", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "Interview not found." } },
    });
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.getByText("Interview not found.")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /join interview room/i }),
    ).toBeNull();
  });

  it("shows the room id so either participant can confirm they are in one room", async () => {
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.getByTestId("identifier-room-id")).toHaveTextContent("room-abc123");
  });

  it("never offers a hiring decision from inside the room", async () => {
    renderPanel();
    await screen.findByTestId("interview-room");
    expect(screen.queryByRole("button", { name: /select|reject|hire/i })).toBeNull();
  });
});