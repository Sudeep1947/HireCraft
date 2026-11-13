/**
 * The interviewer's record of an interview that just happened.
 *
 * The order and authority of the three steps is what matters here:
 *
 * 1. The interview is completed (a fact) and the feedback saved (ratings,
 *    derived recommendation, notes) *before* any decision is offered — a
 *    decision cannot exist without the evidence behind it being recorded.
 * 2. Advance and Reject are separate, explicit choices on a second step, each
 *    through its existing endpoint: advancing makes no scheduling promise,
 *    rejecting goes through the controlled reason vocabulary.
 * 3. A server refusal is shown, never swallowed: if the lifecycle refuses the
 *    completion or the decision, the panel stays where it was and says why.
 * 4. The notes field states plainly that the candidate never sees it — the
 *    confidentiality rule is part of the UI, not just the API.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { interviewApi } from "../../api/interview";
import { InterviewEndPanel } from "./InterviewEndPanel";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    completeApplicationInterview: vi.fn(),
    saveApplicationInterviewFeedback: vi.fn(),
    advanceApplicationToHr: vi.fn(),
    rejectApplicationFromInterview: vi.fn(),
  },
}));

const applicationId = "app-1";
const interviewId = "int-1";

function renderPanel() {
  return render(
    <InterviewEndPanel applicationId={applicationId} interviewId={interviewId} />,
  );
}

describe("InterviewEndPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(interviewApi.completeApplicationInterview).mockResolvedValue(
      {} as never,
    );
    vi.mocked(interviewApi.saveApplicationInterviewFeedback).mockResolvedValue(
      {} as never,
    );
    vi.mocked(interviewApi.advanceApplicationToHr).mockResolvedValue(
      {} as never,
    );
    vi.mocked(interviewApi.rejectApplicationFromInterview).mockResolvedValue(
      {} as never,
    );
  });

  it("states that the notes are internal before anything is typed", () => {
    renderPanel();
    expect(
      screen.getByText(/Notes \(internal — not shown to the candidate\)/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the candidate never sees them/i),
    ).toBeInTheDocument();
  });

  it("completes the interview, saves feedback, then offers the decision", async () => {
    renderPanel();

    await userEvent.click(
      screen.getByRole("button", { name: /complete interview/i }),
    );

    await waitFor(() =>
      expect(interviewApi.saveApplicationInterviewFeedback).toHaveBeenCalled(),
    );
    // Completion first: the fact the interview was held is recorded before
    // the scorecard that comments on it.
    expect(interviewApi.completeApplicationInterview).toHaveBeenCalledTimes(1);
    expect(interviewApi.completeApplicationInterview).toHaveBeenCalledWith(
      applicationId,
      interviewId,
    );
    expect(interviewApi.saveApplicationInterviewFeedback).toHaveBeenCalledWith(
      applicationId,
      interviewId,
      expect.objectContaining({
        technical_skills: 50,
        communication: 50,
        problem_solving: 50,
        // 50s derive "consider" — the recommendation travels with the feedback.
        recommendation: "consider",
      }),
    );

    // The decision step appears only after the feedback is safely stored.
    expect(
      await screen.findByText(/Overall recommendation/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /advance candidate/i }),
    ).toBeInTheDocument();
    expect(interviewApi.advanceApplicationToHr).not.toHaveBeenCalled();
  });

  it("advancing makes no scheduling promise and uses the existing endpoint", async () => {
    renderPanel();
    await userEvent.click(
      screen.getByRole("button", { name: /complete interview/i }),
    );
    await screen.findByText(/Overall recommendation/i);

    await userEvent.click(screen.getByRole("button", { name: /advance candidate/i }));

    await waitFor(() =>
      expect(interviewApi.advanceApplicationToHr).toHaveBeenCalledWith(
        applicationId,
        expect.any(Object),
      ),
    );
    expect(screen.getByText(/No time has been picked/i)).toBeInTheDocument();
    expect(interviewApi.rejectApplicationFromInterview).not.toHaveBeenCalled();
  });

  it("rejecting requires the controlled reason and keeps the note internal", async () => {
    renderPanel();
    await userEvent.click(
      screen.getByRole("button", { name: /complete interview/i }),
    );
    await screen.findByText(/Overall recommendation/i);

    await userEvent.click(
      screen.getByRole("radio", { name: /reject candidate/i }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText(/rejection reason/i),
      "failed_interview",
    );
    await userEvent.type(
      screen.getByLabelText(/internal note/i),
      "Could not design a cache",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /reject candidate/i }),
    );

    await waitFor(() =>
      expect(interviewApi.rejectApplicationFromInterview).toHaveBeenCalledWith(
        applicationId,
        {
          rejection_reason: "failed_interview",
          internal_note: "Could not design a cache",
        },
      ),
    );
    expect(screen.getByText(/internal note stays with the hiring team/i)).toBeInTheDocument();
    expect(interviewApi.advanceApplicationToHr).not.toHaveBeenCalled();
  });

  it("shows a server refusal instead of pretending the step happened", async () => {
    vi.mocked(interviewApi.completeApplicationInterview).mockRejectedValue({
      response: {
        data: { error: { message: "This interview is already completed" } },
      },
    });
    renderPanel();

    await userEvent.click(
      screen.getByRole("button", { name: /complete interview/i }),
    );

    expect(
      await screen.findByText("This interview is already completed"),
    ).toBeInTheDocument();
    // Still on the feedback step: no decision UI from a save that failed.
    expect(
      screen.queryByRole("button", { name: /advance candidate/i }),
    ).toBeNull();
    expect(interviewApi.saveApplicationInterviewFeedback).not.toHaveBeenCalled();
  });
});
