import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { recruiterJobApi } from "../../api/jobs";
import { ToastProvider } from "../../contexts/ToastContext";
import { ApplicationDecisionPanel } from "./ApplicationDecisionPanel";
import type {
  ApplicationDecisionOptions,
  ApplicationDecisionResult,
} from "../../types/applicationDecision";

vi.mock("../../api/jobs", () => ({
  recruiterJobApi: {
    getApplicationDecisionOptions: vi.fn(),
    recordApplicationDecision: vi.fn(),
  },
}));

const applicationId = "app-1";

const REASONS = [
  {
    value: "low_job_match" as const,
    label: "Profile does not match this role's core requirements",
    candidate_message:
      "After reviewing your application for Backend Engineer, we decided to move forward with candidates whose background aligns more closely with the core requirements of this role.",
  },
  {
    value: "position_filled" as const,
    label: "Position has been filled",
    candidate_message:
      "The position for Backend Engineer has been filled. We appreciate the time you invested in applying.",
  },
];

function baseOptions(
  overrides: Partial<ApplicationDecisionOptions> = {},
): ApplicationDecisionOptions {
  return {
    application_id: applicationId,
    current_status: "under_review",
    status_is_final: false,
    rejection_reasons: REASONS,
    options: [
      {
        decision: "keep_under_review",
        label: "Keep Under Review",
        description: "Record that you are continuing to review this application.",
        target_status: "under_review",
        requires_rejection_reason: false,
        available: true,
        unavailable_reason: null,
      },
      {
        decision: "shortlist",
        label: "Shortlist",
        description: "Move this application to Shortlisted.",
        target_status: "shortlisted",
        requires_rejection_reason: false,
        available: true,
        unavailable_reason: null,
      },
      {
        decision: "reject",
        label: "Reject",
        description: "Reject this application.",
        target_status: "rejected",
        requires_rejection_reason: true,
        available: true,
        unavailable_reason: null,
      },
    ],
    ...overrides,
  };
}

function baseResult(
  overrides: Partial<ApplicationDecisionResult> = {},
): ApplicationDecisionResult {
  return {
    application_id: applicationId,
    decision: "reject",
    previous_status: "under_review",
    status: "rejected",
    changed_status: true,
    rejection_reason: "low_job_match",
    rejection_reason_label: "Profile does not match this role's core requirements",
    internal_note: null,
    candidate_status_label: "Not Selected",
    candidate_message: "Approved candidate wording.",
    decided_at: "2026-01-02T00:00:00Z",
    decided_by: "rec-1",
    ...overrides,
  };
}

function renderPanel(onDecisionMade = vi.fn()) {
  render(
    <MemoryRouter>
      <ToastProvider>
        <ApplicationDecisionPanel
          applicationId={applicationId}
          onDecisionMade={onDecisionMade}
        />
      </ToastProvider>
    </MemoryRouter>,
  );
  return { onDecisionMade };
}

describe("ApplicationDecisionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
      baseOptions(),
    );
    vi.mocked(recruiterJobApi.recordApplicationDecision).mockResolvedValue(
      baseResult(),
    );
  });

  it("renders exactly the decisions the server says are available", async () => {
    renderPanel();
    await screen.findByRole("button", { name: "Shortlist" });
    expect(screen.getByRole("button", { name: "Keep Under Review" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Shortlist" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("disables decisions the server reports as unavailable and explains why", async () => {
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
      baseOptions({
        options: baseOptions().options.map((o) =>
          o.decision === "shortlist"
            ? { ...o, available: false, unavailable_reason: "Not allowed from under review" }
            : o,
        ),
      }),
    );
    renderPanel();
    await screen.findByRole("button", { name: "Shortlist" });
    expect(screen.getByRole("button", { name: "Shortlist" })).toBeDisabled();
    expect(screen.getByText(/not allowed from under review/i)).toBeInTheDocument();
  });

  it("offers no decisions at all once the status is final", async () => {
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
      baseOptions({
        current_status: "rejected",
        status_is_final: true,
        options: baseOptions().options.map((o) => ({
          ...o,
          available: false,
          unavailable_reason: "Application is already rejected",
        })),
      }),
    );
    renderPanel();
    await screen.findByText(/reached a final status/i);
    expect(screen.queryByRole("button", { name: "Shortlist" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
    expect(screen.queryByLabelText(/rejection reason/i)).toBeNull();
  });

  it("sends a shortlist decision with no rejection reason", async () => {
    const { onDecisionMade } = renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Shortlist" }));

    await waitFor(() => {
      expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
        applicationId,
        "shortlist",
        undefined,
      );
    });
    expect(onDecisionMade).toHaveBeenCalledWith(baseResult());
  });

  it("sends a keep-under-review decision that changes no status", async () => {
    vi.mocked(recruiterJobApi.recordApplicationDecision).mockResolvedValue(
      baseResult({
        decision: "keep_under_review",
        status: "under_review",
        changed_status: false,
        rejection_reason: null,
      }),
    );
    renderPanel();
    await userEvent.click(
      await screen.findByRole("button", { name: "Keep Under Review" }),
    );
    await waitFor(() => {
      expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
        applicationId,
        "keep_under_review",
        undefined,
      );
    });
  });

  // ── Rejection flow ────────────────────────────────────────────────

  it("requires a reason before a rejection can be reviewed", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));

    expect(screen.getByLabelText(/rejection reason/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /review rejection/i })).toBeDisabled();
    // Nothing is sent while the reason is missing.
    expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();
  });

  it("previews the exact candidate-facing wording and hides the internal note", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));

    await userEvent.selectOptions(
      screen.getByLabelText(/rejection reason/i),
      "low_job_match",
    );
    await userEvent.type(
      screen.getByLabelText(/internal note/i),
      "INTERNAL-ONLY secret note",
    );

    expect(screen.getByText(/the candidate will see/i)).toBeInTheDocument();
    expect(
      screen.getByText(REASONS[0].candidate_message),
    ).toBeInTheDocument();
    // The internal note is never rendered in the candidate preview block.
    const preview = screen.getByText(/the candidate will see/i).parentElement!;
    expect(within(preview).queryByText(/INTERNAL-ONLY/)).toBeNull();

    // The note is labelled private.
    expect(screen.getByLabelText(/internal note/i)).toHaveAttribute(
      "aria-label",
      "Internal note",
    );
  });

  it("requires an explicit confirmation step before rejecting", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.selectOptions(
      screen.getByLabelText(/rejection reason/i),
      "position_filled",
    );

    // First click only reveals the confirmation.
    await userEvent.click(screen.getByRole("button", { name: /review rejection/i }));
    expect(
      screen.getByText(/confirm: this moves the application to rejected/i),
    ).toBeInTheDocument();
    expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole("button", { name: /confirm rejection/i }),
    );
    await waitFor(() => {
      expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
        applicationId,
        "reject",
        { rejectionReason: "position_filled", internalNote: undefined },
      );
    });
  });

  it("sends the internal note alongside the reason, never in place of it", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.selectOptions(
      screen.getByLabelText(/rejection reason/i),
      "low_job_match",
    );
    await userEvent.type(
      screen.getByLabelText(/internal note/i),
      "Strong screen, wrong stack",
    );
    await userEvent.click(screen.getByRole("button", { name: /review rejection/i }));
    await userEvent.click(
      screen.getByRole("button", { name: /confirm rejection/i }),
    );

    await waitFor(() => {
      expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
        applicationId,
        "reject",
        {
          rejectionReason: "low_job_match",
          internalNote: "Strong screen, wrong stack",
        },
      );
    });
  });

  it("lets the recruiter back out of a rejection without deciding", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.selectOptions(
      screen.getByLabelText(/rejection reason/i),
      "low_job_match",
    );
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();
    expect(screen.queryByLabelText(/rejection reason/i)).toBeNull();
  });

  it("surfaces a server rejection without recording a decision", async () => {
    vi.mocked(recruiterJobApi.recordApplicationDecision).mockRejectedValue(
      new Error("Application is already rejected"),
    );
    const { onDecisionMade } = renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Shortlist" }));

    await waitFor(() => {
      expect(screen.getByText(/application is already rejected/i)).toBeInTheDocument();
    });
    expect(onDecisionMade).not.toHaveBeenCalled();
  });

  it("never presents the screening score as a reason to decide", async () => {
    renderPanel();
    await screen.findByRole("button", { name: "Shortlist" });
    // The panel states the decision is the recruiter's own.
    expect(
      screen.getByText(/scores and fairness metrics are context only/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/recommendation/i)).toBeNull();
  });

  it("shows an error state when the options cannot be loaded", async () => {
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockRejectedValue(
      new Error("You do not have permission to update this application"),
    );
    renderPanel();
    expect(
      await screen.findByText(/do not have permission/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
  });

  // ── Phase 13: the final selection decision ────────────────────────────

  const SELECT_MESSAGE =
    "You have been selected for Backend Engineer. The hiring team will be in touch about the next step.";

  function selectOptions(
    overrides: Partial<ApplicationDecisionOptions> = {},
  ): ApplicationDecisionOptions {
    return baseOptions({
      current_status: "interviewed",
      options: [
        ...baseOptions().options,
        {
          decision: "select",
          label: "Select",
          description: "Select this candidate as your choice for this role.",
          target_status: "selected",
          requires_rejection_reason: false,
          available: true,
          unavailable_reason: null,
          candidate_message: SELECT_MESSAGE,
        },
      ],
      ...overrides,
    });
  }

  function selectResult(): ApplicationDecisionResult {
    return baseResult({
      decision: "select",
      previous_status: "interviewed",
      status: "selected",
      changed_status: true,
      rejection_reason: null,
      candidate_status_label: "Selected",
      candidate_message: SELECT_MESSAGE,
    });
  }

  describe("final selection", () => {
    beforeEach(() => {
      vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
        selectOptions(),
      );
      vi.mocked(recruiterJobApi.recordApplicationDecision).mockResolvedValue(
        selectResult(),
      );
    });

    it("offers Select as a distinct decision from Shortlist", async () => {
      renderPanel();
      await screen.findByRole("button", { name: "Select" });
      expect(screen.getByRole("button", { name: "Shortlist" })).toBeEnabled();
      expect(screen.getByRole("button", { name: "Select" })).toBeEnabled();
    });

    it("does not record a selection on the first click", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));

      // A final decision about a person must be deliberate, never one click away.
      expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();
      expect(await screen.findByText(/select this candidate/i)).toBeInTheDocument();
    });

    it("previews the exact candidate wording before committing", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));

      // The wording comes from the server, not a client-side guess.
      expect(await screen.findByText(SELECT_MESSAGE)).toBeInTheDocument();
    });

    it("states that selecting is not being hired", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));
      expect(
        await screen.findByText(/not the same as being hired/i),
      ).toBeInTheDocument();
    });

    it("requires a second confirmation before sending the selection", async () => {
      const { onDecisionMade } = renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));

      await userEvent.click(
        await screen.findByRole("button", { name: /review selection/i }),
      );
      // Still nothing sent: the reviewer has not committed yet.
      expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();

      await userEvent.click(
        screen.getByRole("button", { name: /confirm selection/i }),
      );
      await waitFor(() => {
        expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
          applicationId,
          "select",
          undefined,
        );
      });
      expect(onDecisionMade).toHaveBeenCalledWith(selectResult());
    });

    it("sends the selection with an optional private internal note", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));
      await userEvent.type(
        await screen.findByLabelText(/select internal note/i),
        "Chose on evidence",
      );
      await userEvent.click(
        screen.getByRole("button", { name: /review selection/i }),
      );
      await userEvent.click(
        screen.getByRole("button", { name: /confirm selection/i }),
      );

      await waitFor(() => {
        expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
          applicationId,
          "select",
          { internalNote: "Chose on evidence" },
        );
      });
    });

    it("abandons the selection when cancelled", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));
      await userEvent.click(
        await screen.findByRole("button", { name: /^cancel$/i }),
      );

      expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();
      expect(screen.queryByText(/select this candidate/i)).toBeNull();
    });

    it("can go back from the confirmation step without recording anything", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));
      await userEvent.click(
        await screen.findByRole("button", { name: /review selection/i }),
      );
      await userEvent.click(screen.getByRole("button", { name: /back/i }));

      expect(recruiterJobApi.recordApplicationDecision).not.toHaveBeenCalled();
      expect(
        await screen.findByRole("button", { name: /review selection/i }),
      ).toBeInTheDocument();
    });

    it("disables Select and explains when the server says it is not allowed", async () => {
      vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
        selectOptions({
          current_status: "under_review",
          options: selectOptions().options.map((o) =>
            o.decision === "select"
              ? {
                  ...o,
                  available: false,
                  unavailable_reason: "Not allowed from under review",
                }
              : o,
          ),
        }),
      );
      renderPanel();
      await screen.findByRole("button", { name: "Select" });

      expect(screen.getByRole("button", { name: "Select" })).toBeDisabled();
      expect(
        screen.getByText(/not allowed from under review/i),
      ).toBeInTheDocument();
    });

    it("never offers a rejection reason for a positive decision", async () => {
      renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));

      expect(screen.queryByLabelText(/rejection reason/i)).toBeNull();
    });

    it("surfaces a server conflict without recording a selection", async () => {
      vi.mocked(recruiterJobApi.recordApplicationDecision).mockRejectedValue(
        new Error("Application is already selected"),
      );
      const { onDecisionMade } = renderPanel();
      await userEvent.click(await screen.findByRole("button", { name: "Select" }));
      await userEvent.click(
        await screen.findByRole("button", { name: /review selection/i }),
      );
      await userEvent.click(
        screen.getByRole("button", { name: /confirm selection/i }),
      );

      await waitFor(() => {
        expect(screen.getByText(/already selected/i)).toBeInTheDocument();
      });
      expect(onDecisionMade).not.toHaveBeenCalled();
    });
  });
});
