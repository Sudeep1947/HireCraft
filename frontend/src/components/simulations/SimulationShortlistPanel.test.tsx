import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { simulationApi } from "../../api/simulations";
import { SimulationShortlistPanel } from "./SimulationShortlistPanel";

vi.mock("../../api/simulations", () => ({
  simulationApi: {
    listResults: vi.fn(),
    applyShortlist: vi.fn(),
  },
}));

vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

const alice = {
  candidate_id: "cand-alice",
  candidate_name: "Alice",
  simulation_score: 88,
  simulation_rank: 1,
  simulation_shortlisted: true,
};
const bob = {
  candidate_id: "cand-bob",
  candidate_name: "Bob",
  simulation_score: 74,
  simulation_rank: 2,
  simulation_shortlisted: false,
};

function mockResultsPage(items = [alice, bob]) {
  vi.mocked(simulationApi.listResults).mockResolvedValue({
    scenario_id: "sim-1",
    execution_id: "exec-1",
    total: items.length,
    page: 1,
    page_size: 100,
    items: items as never[],
  });
}

function renderPanel(hasResults = true) {
  return render(
    <SimulationShortlistPanel
      simulationId="sim-1"
      executionId="exec-1"
      hasResults={hasResults}
    />,
  );
}

describe("SimulationShortlistPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when there is nothing to shortlist from", () => {
    const { container } = renderPanel(false);
    expect(container.textContent).toBe("");
  });

  it("opens the selection dialog and pre-selects hypothetical shortlisted candidates", async () => {
    mockResultsPage();
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Shortlist Candidates" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Select Alice")).toBeChecked();
    });
    expect(screen.getByLabelText("Select Bob")).not.toBeChecked();
  });

  it("shows an empty state when the simulation produced no candidates", async () => {
    mockResultsPage([]);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Shortlist Candidates" }));

    await waitFor(() => {
      expect(
        screen.getByText("No candidates are available for this hypothetical shortlist."),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("cancelling the dialog never touches live data", async () => {
    mockResultsPage();
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Shortlist Candidates" }));
    await waitFor(() => expect(screen.getByLabelText("Select Alice")).toBeChecked());

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByTestId("shortlist-dialog")).not.toBeInTheDocument();
    expect(simulationApi.applyShortlist).not.toHaveBeenCalled();
  });

  it("cancelling at the confirmation step never touches live data", async () => {
    mockResultsPage();
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Shortlist Candidates" }));
    await waitFor(() => expect(screen.getByLabelText("Select Alice")).toBeChecked());

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(simulationApi.applyShortlist).not.toHaveBeenCalled();
  });

  it("confirms and applies only the explicitly selected candidates", async () => {
    mockResultsPage();
    vi.mocked(simulationApi.applyShortlist).mockResolvedValue({
      simulation_id: "sim-1",
      execution_id: "exec-1",
      job_id: "job-1",
      scenario_status: "completed",
      shortlist_status: "applied",
      applied: true,
      updated: [
        {
          candidate_id: "cand-alice",
          candidate_name: "Alice",
          application_id: "app-alice",
          previous_status: "applied",
          new_status: "shortlisted",
          updated: true,
        },
      ],
      skipped: [],
    });
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Shortlist Candidates" }));
    await waitFor(() => expect(screen.getByLabelText("Select Alice")).toBeChecked());

    // Bob stays un-selected (hypothetically not shortlisted), so only Alice is sent.
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    const applyButton = screen.getByRole("button", { name: /Apply Shortlist/ });
    expect(applyButton).not.toBeDisabled();

    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(simulationApi.applyShortlist).toHaveBeenCalledTimes(1);
    });
    expect(simulationApi.applyShortlist).toHaveBeenCalledWith("sim-1", {
      candidate_ids: ["cand-alice"],
      execution_id: "exec-1",
    });
    await waitFor(() => {
      expect(screen.getByText("Shortlist applied")).toBeInTheDocument();
    });
  });

  it("allows deselecting every candidate, which blocks confirmation", async () => {
    mockResultsPage();
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Shortlist Candidates" }));
    await waitFor(() => expect(screen.getByLabelText("Select Alice")).toBeChecked());

    fireEvent.click(screen.getByLabelText("Select Alice"));

    expect(screen.getByText("0 selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    // Nothing to apply: confirmation is unreachable, so no live call can fire.
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    expect(simulationApi.applyShortlist).not.toHaveBeenCalled();
  });
});