/**
 * The shared live-room page, as each side experiences it.
 *
 * What is under test is the orchestration, not the media stack:
 *
 * - The page decides nothing about access. Whether the call may start comes
 *   from the server's room payload (`can_join`, `unavailable_reason`,
 *   `message`), and the countdown is measured against the server's clock — so
 *   an early or late candidate reads the server's own explanation with its own
 *   "opens in X minutes" hint, never a client-side guess.
 * - Join is the existing Phase 14 room join, called by interview id, and the
 *   role passed into the live call is the one the *server* resolved.
 * - After the call ends, only an interviewer on an application-linked
 *   interview sees the feedback panel; a candidate sees the calm end state and
 *   can never reach the confidential feedback UI.
 * - Leaving the call is not the call ending: the page returns to the
 *   server-gated ready screen instead of pretending the interview is over.
 *
 * The WebRTC component is stubbed deliberately: this test pins the page's
 * behaviour, and jsdom has no camera, microphone or network worth faking.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { interviewApi } from "../../api/interview";
import { InterviewVideoPage } from "./InterviewVideoPage";
import type { InterviewRoomState } from "../../types/interview";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    getInterviewRoom: vi.fn(),
    joinInterviewRoom: vi.fn(),
  },
}));

// Stubbed with plain createElement inside an async factory so the mock never
// races the module graph's import bindings.
vi.mock("../../components/interview/InterviewVideoRoom", async () => {
  const React = await import("react");
  return {
    InterviewVideoRoom: (props: {
      interviewId: string;
      role: string;
      peerPresentOnJoin: boolean;
      onEnded: () => void;
      onLeft?: () => void;
    }) =>
      React.createElement(
        "div",
        {
          "data-testid": "video-room-stub",
          "data-role": props.role,
          "data-interview": props.interviewId,
          "data-peer-present": String(props.peerPresentOnJoin),
        },
        React.createElement(
          "button",
          { "data-testid": "stub-end", onClick: props.onEnded },
          "End",
        ),
        React.createElement(
          "button",
          { "data-testid": "stub-leave", onClick: props.onLeft },
          "Leave",
        ),
      ),
  };
});

vi.mock("../../components/interview/InterviewEndPanel", async () => {
  const React = await import("react");
  return {
    InterviewEndPanel: (props: { applicationId: string; interviewId: string }) =>
      React.createElement("div", {
        "data-testid": "end-panel-stub",
        "data-application": props.applicationId,
        "data-interview": props.interviewId,
      }),
  };
});

const interviewId = "int-1";

function room(overrides: Partial<InterviewRoomState> = {}): InterviewRoomState {
  return {
    interview_id: interviewId,
    application_id: "app-1",
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

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/interviews/${interviewId}/room`]}>
      <Routes>
        <Route path="/interviews/:id/room" element={<InterviewVideoPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InterviewVideoPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(room());
  });

  it("reads the room by interview id and renders the server's verdict", async () => {
    renderPage();

    await screen.findByTestId("video-room-ready");
    expect(interviewApi.getInterviewRoom).toHaveBeenCalledWith(interviewId);
    expect(
      screen.getByText("The room is open. Join when you are ready."),
    ).toBeInTheDocument();
    // The room id is displayed, never demanded: both sides enter the same
    // room automatically, so there is nothing for anyone to type.
    expect(screen.getByText(/no meeting ID/i)).toBeInTheDocument();
    expect(screen.getByTestId("join-interview")).toBeEnabled();
  });

  it("passes the server-resolved role into the live call after joining", async () => {
    vi.mocked(interviewApi.joinInterviewRoom).mockResolvedValue(
      room({ your_role: "candidate", you_joined: true }),
    );
    renderPage();
    await screen.findByTestId("video-room-ready");

    await userEvent.click(screen.getByTestId("join-interview"));

    expect(interviewApi.joinInterviewRoom).toHaveBeenCalledWith(interviewId);
    const stub = await screen.findByTestId("video-room-stub");
    expect(stub).toHaveAttribute("data-role", "candidate");
    expect(stub).toHaveAttribute("data-interview", interviewId);
  });

  it("refuses an early join with the server's reason and countdown", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({
        can_join: false,
        unavailable_reason: "join_window_not_open",
        state: "upcoming",
        message: "This interview has not reached its join window.",
        // 20 minutes after the server's "now", so the hint is deterministic.
        join_opens_at: "2026-01-05T14:10:00Z",
      }),
    );
    renderPage();

    await screen.findByTestId("video-room-ready");
    expect(screen.getByTestId("join-interview")).toBeDisabled();
    expect(
      screen.getByText(/The room opens shortly before the scheduled time/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/opens in 20 minutes/i)).toBeInTheDocument();
    expect(screen.queryByTestId("video-room-stub")).toBeNull();
  });

  it("states a load failure instead of offering any join", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockRejectedValue({
      response: { data: { error: { message: "Interview not found" } } },
    });
    renderPage();

    expect(await screen.findByText("Interview not found")).toBeInTheDocument();
    expect(screen.queryByTestId("join-interview")).toBeNull();
    expect(interviewApi.joinInterviewRoom).not.toHaveBeenCalled();
  });

  it("shows an interviewer the feedback panel once the call ends", async () => {
    vi.mocked(interviewApi.joinInterviewRoom).mockResolvedValue(
      room({ your_role: "interviewer", you_joined: true }),
    );
    renderPage();
    await screen.findByTestId("video-room-ready");
    await userEvent.click(screen.getByTestId("join-interview"));
    await screen.findByTestId("video-room-stub");

    await userEvent.click(screen.getByTestId("stub-end"));

    const panel = await screen.findByTestId("end-panel-stub");
    expect(panel).toHaveAttribute("data-application", "app-1");
    expect(panel).toHaveAttribute("data-interview", interviewId);
    expect(screen.getByText(/Attendance is recorded/i)).toBeInTheDocument();
  });

  it("never shows the interviewer's feedback panel to the candidate", async () => {
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue(
      room({ your_role: "candidate" }),
    );
    vi.mocked(interviewApi.joinInterviewRoom).mockResolvedValue(
      room({ your_role: "candidate", you_joined: true }),
    );
    renderPage();
    await screen.findByTestId("video-room-ready");
    await userEvent.click(screen.getByTestId("join-interview"));
    await screen.findByTestId("video-room-stub");

    await userEvent.click(screen.getByTestId("stub-end"));

    expect(await screen.findByText(/Thank you for your time/i)).toBeInTheDocument();
    expect(screen.queryByTestId("end-panel-stub")).toBeNull();
  });

  it("returns to the server-gated ready screen when someone leaves the call", async () => {
    vi.mocked(interviewApi.joinInterviewRoom).mockResolvedValue(
      room({ your_role: "interviewer", you_joined: true }),
    );
    renderPage();
    await screen.findByTestId("video-room-ready");
    await userEvent.click(screen.getByTestId("join-interview"));
    await screen.findByTestId("video-room-stub");

    await userEvent.click(screen.getByTestId("stub-leave"));

    // Not "ended": leaving the call is local, the interview status is
    // untouched, and the server still decides whether rejoining is possible.
    expect(await screen.findByTestId("video-room-ready")).toBeInTheDocument();
    expect(screen.queryByTestId("video-room-stub")).toBeNull();
    expect(screen.queryByTestId("end-panel-stub")).toBeNull();
    expect(screen.getByTestId("join-interview")).toBeEnabled();
  });
});
