import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { candidateJobApi } from "../../api/jobs";
import { MyApplications } from "./MyApplications";
import type { JobApplication } from "../../types/jobs";
import type { CandidateApplicationDecision } from "../../types/applicationDecision";

vi.mock("../../api/jobs", () => ({
  candidateJobApi: {
    getMyApplications: vi.fn(),
    getMyApplicationDecisions: vi.fn(),
    getMyApplicationDecision: vi.fn(),
    withdrawApplication: vi.fn(),
  },
}));

// Stable identity, matching the real provider's useCallback, so the load
// effect is not re-triggered on every render.
const addToast = vi.fn();
vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast }),
}));

function application(overrides: Partial<JobApplication> = {}): JobApplication {
  return {
    id: "app-1",
    job_id: "job-1",
    job_title: "Backend Engineer",
    company: "Northwind",
    location: "Remote",
    status: "under_review",
    cover_letter: "I build reliable systems.",
    screening_status: "not_started",
    screening_error: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as JobApplication;
}

function decision(
  overrides: Partial<CandidateApplicationDecision> = {},
): CandidateApplicationDecision {
  return {
    application_id: "app-1",
    job_id: "job-1",
    job_title: "Backend Engineer",
    status: "rejected",
    status_label: "Not Selected",
    decision_outcome: "rejected",
    rejection_reason: "low_job_match",
    candidate_message:
      "After reviewing your application for Backend Engineer, we decided to move forward with candidates whose background aligns more closely with the core requirements of this role.",
    decided_at: "2026-01-02T00:00:00Z",
    is_decision_final: true,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/candidate/applications"]}>
      <Routes>
        <Route path="/candidate/applications" element={<MyApplications />} />
        <Route path="/candidate/applications/:applicationId" element={<p>Application detail page</p>} />
        <Route path="/candidate/jobs" element={<p>Job portal</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MyApplications decision display", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application(),
    ]);
    vi.mocked(candidateJobApi.getMyApplicationDecisions).mockResolvedValue([
      decision(),
    ]);
  });

  it("shows the candidate-safe status label instead of the internal status", async () => {
    renderPage();

    expect(await screen.findByText("Not Selected")).toBeInTheDocument();
    expect(screen.queryByText("rejected")).toBeNull();
  });

  it("shows the approved candidate message for the recorded reason", async () => {
    renderPage();

    const message = await screen.findByText(/aligns more closely with the core requirements/i);
    expect(message).toBeInTheDocument();
    expect(within(message.closest("div")!).getByText(/Updated/)).toBeInTheDocument();
  });

  it("fetches the decision projections in one request, not one per row", async () => {
    renderPage();

    await screen.findByText("Not Selected");
    expect(candidateJobApi.getMyApplicationDecisions).toHaveBeenCalledTimes(1);
    expect(candidateJobApi.getMyApplicationDecision).not.toHaveBeenCalled();
  });

  it("falls back to the raw status when no decision projection exists yet", async () => {
    vi.mocked(candidateJobApi.getMyApplicationDecisions).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("under review")).toBeInTheDocument();
    expect(screen.queryByText(/aligns more closely/i)).toBeNull();
  });

  it("does not withdraw an application that reached a final decision", async () => {
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application({ status: "rejected" }),
    ]);
    renderPage();

    await screen.findByText("Not Selected");
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("re-reads the decision projection after a withdrawal", async () => {
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application({ status: "applied" }),
    ]);
    vi.mocked(candidateJobApi.withdrawApplication).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Withdraw" }));

    await waitFor(() => {
      expect(candidateJobApi.withdrawApplication).toHaveBeenCalledWith("app-1");
    });
    await waitFor(() => {
      expect(candidateJobApi.getMyApplicationDecisions).toHaveBeenCalledTimes(2);
    });
  });

  it("keeps the screening explanation link separate from the decision outcome", async () => {
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application({ screening_status: "completed" }),
    ]);
    renderPage();

    await screen.findByText("Not Selected");
    const link = screen.getByRole("button", { name: /How does my profile match\?/ });
    expect(link).toBeInTheDocument();
  });
});

describe("MyApplications tracking affordances", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application(),
    ]);
    vi.mocked(candidateJobApi.getMyApplicationDecisions).mockResolvedValue([
      decision(),
    ]);
  });

  it("always offers a link into the tracking detail, whatever the screening state", async () => {
    // The explanation link is gated on screening, so tracking needed its own
    // entry point that is present for every application.
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application({ id: "app-1", screening_status: "not_started", status: "applied" }),
    ]);
    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: /View status & activity/ }),
    );
    expect(await screen.findByText("Application detail page")).toBeInTheDocument();
  });

  it("offers a status filter built only from the statuses the API returned", async () => {
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application({ id: "app-1", status: "applied" }),
      application({ id: "app-2", status: "rejected" }),
    ]);
    renderPage();

    const filter = await screen.findByLabelText("Filter by status");
    const values = [...(filter as HTMLSelectElement).options].map((o) => o.value);
    // "all" plus exactly the two statuses present in the response.
    expect(values).toEqual(["", "applied", "rejected"]);
    // Option wording comes from the server's status label, not a local table.
    expect(
      [...(filter as HTMLSelectElement).options].map((o) => o.textContent),
    ).toContain("Not Selected (1)");
  });

  it("narrows the list to the selected status and can clear it again", async () => {
    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([
      application({ id: "app-1", status: "applied" }),
      application({ id: "app-2", status: "rejected" }),
    ]);
    vi.mocked(candidateJobApi.getMyApplicationDecisions).mockResolvedValue([
      decision({ application_id: "app-2" }),
    ]);
    renderPage();

    await screen.findByLabelText("Filter by status");
    await userEvent.selectOptions(
      screen.getByLabelText("Filter by status"),
      "rejected",
    );

    // Only the rejected application is left, so the withdrawable one is gone.
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
    });
    expect(screen.getByText("Not Selected")).toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Filter by status"),
      "",
    );
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    });
  });

  it("hides the filter when every application shares one status", async () => {
    renderPage();

    await screen.findByText("Not Selected");
    expect(screen.queryByLabelText("Filter by status")).toBeNull();
  });

  it("shows a retryable error state instead of a blank page when loading fails", async () => {
    vi.mocked(candidateJobApi.getMyApplications).mockRejectedValue(new Error("boom"));
    renderPage();

    expect(
      await screen.findByText("Could not load your applications"),
    ).toBeInTheDocument();

    vi.mocked(candidateJobApi.getMyApplications).mockResolvedValue([application()]);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Not Selected")).toBeInTheDocument();
  });
});
