/**
 * The recruiter's Interview Analytics page.
 *
 * What matters here is honesty about the data:
 *
 * - Every figure rendered comes from the one server report
 *   (`interviewApi.getAnalytics`); the page computes nothing of its own and
 *   fills in nothing when a section is empty.
 * - A failed load is *shown*, with the server's own message when it sent one,
 *   and with a Retry that re-requests the same endpoint -- not swallowed, not
 *   replaced by sample statistics, and not a permanently dead page.
 * - No interviews yet is an empty state, not a grid of zeroes pretending to
 *   be insight.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { interviewApi } from "../../api/interview";
import { InterviewAnalyticsPage } from "./InterviewAnalytics";
import type { InterviewAnalytics } from "../../types/interview";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    getAnalytics: vi.fn(),
  },
}));

function report(
  overrides: Partial<InterviewAnalytics> = {},
): InterviewAnalytics {
  return {
    total_interviews: 4,
    completion_rate: 75,
    average_score: 71.5,
    median_score: 72,
    score_distribution: { excellent: 1, good: 2, average: 0, below_average: 0 },
    category_averages: { technical: 74, behavioral: 68 },
    difficulty_distribution: { easy: 0, medium: 12, hard: 0 },
    recommendation_breakdown: {
      strongly_recommend: 0,
      recommend: 2,
      consider: 1,
      not_recommended: 0,
    },
    skill_performance: { technical_skills_avg: 73, total_evaluated: 3 },
    hiring_prediction: { likely_hire_pct: 3, needs_review_pct: 0, unlikely_hire_pct: 0 },
    trends: [],
    ...overrides,
  };
}

describe("InterviewAnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the statistics from the server's report", async () => {
    vi.mocked(interviewApi.getAnalytics).mockResolvedValue(report());

    render(<InterviewAnalyticsPage />);

    expect(await screen.findByText("Interview Analytics")).toBeInTheDocument();
    expect(interviewApi.getAnalytics).toHaveBeenCalledTimes(1);
    expect(screen.getByText("4")).toBeInTheDocument(); // total interviews
    expect(screen.getByText("75%")).toBeInTheDocument(); // completion rate
    expect(screen.getByText("71.5")).toBeInTheDocument(); // average score
    expect(screen.getByText("72")).toBeInTheDocument(); // median score
    // Panels come from the same report, not local computation.
    expect(screen.getByText("Good (65-79)")).toBeInTheDocument();
    expect(screen.getByText("technical")).toBeInTheDocument();
    expect(screen.getByText("Strongly Recommend")).toBeInTheDocument();
  });

  it("shows an empty state when there are no interviews, not fake statistics", async () => {
    vi.mocked(interviewApi.getAnalytics).mockResolvedValue(
      report({
        total_interviews: 0,
        completion_rate: 0,
        average_score: 0,
        median_score: 0,
        score_distribution: { excellent: 0, good: 0, average: 0, below_average: 0 },
        category_averages: {},
        recommendation_breakdown: {
          strongly_recommend: 0,
          recommend: 0,
          consider: 0,
          not_recommended: 0,
        },
        hiring_prediction: { likely_hire_pct: 0, needs_review_pct: 0, unlikely_hire_pct: 0 },
      }),
    );

    render(<InterviewAnalyticsPage />);

    expect(await screen.findByText("No interviews yet")).toBeInTheDocument();
    expect(
      screen.getByText(/scheduled and completed/i),
    ).toBeInTheDocument();
    // The stat cards and charts are absent rather than rendered as zeroes.
    expect(screen.queryByText("Total Interviews")).toBeNull();
    expect(screen.queryByText("Score Distribution")).toBeNull();
    expect(screen.queryByText("Completion Rate")).toBeNull();
  });

  it("shows the server's failure with a working retry", async () => {
    vi.mocked(interviewApi.getAnalytics).mockRejectedValueOnce({
      response: { data: { error: { message: "Interview service unavailable" } } },
    });

    render(<InterviewAnalyticsPage />);

    // The server's own message, not just the generic sentence.
    expect(
      await screen.findByText("Interview service unavailable"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Total Interviews")).toBeNull();

    // Retry re-requests the same endpoint and renders what comes back.
    vi.mocked(interviewApi.getAnalytics).mockResolvedValueOnce(report());
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(await screen.findByText("71.5")).toBeInTheDocument();
    await waitFor(() =>
      expect(interviewApi.getAnalytics).toHaveBeenCalledTimes(2),
    );
  });

  it("falls back to a readable message when the failure had none", async () => {
    vi.mocked(interviewApi.getAnalytics).mockRejectedValue(
      new Error("socket hang up"),
    );

    render(<InterviewAnalyticsPage />);

    // Raw exception text is never shown to a user; the fallback is.
    expect(await screen.findByText("Failed to load analytics")).toBeInTheDocument();
    expect(screen.queryByText(/socket hang up/)).toBeNull();
  });
});
