import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { getApplicationFairnessContext } from "../../api/screening";
import { ApplicationFairnessContextCard } from "./ApplicationFairnessContextCard";
import type { ApplicationFairnessContext } from "../../types/screening";

vi.mock("../../api/screening", () => ({
  getApplicationFairnessContext: vi.fn(),
}));

const applicationId = "app-1";
const jobId = "job-1";

function baseContext(
  overrides: Partial<ApplicationFairnessContext> = {},
): ApplicationFairnessContext {
  return {
    application: {
      id: applicationId,
      job_id: jobId,
      status: "under_review",
      applied_at: "2026-01-01T00:00:00Z",
    },
    job: { id: jobId, title: "Backend Engineer", company: "Northwind" },
    screening_state: {
      effective_status: "completed",
      screened: true,
      message:
        "This application's screening result is included in the fairness population below.",
    },
    population: {
      job_id: jobId,
      job_title: "Backend Engineer",
      applications: 20,
      screened: 14,
      unscreened: 6,
      application_is_in_population: true,
      application_screening_included: true,
      scope: "screened_population",
      note:
        "Fairness metrics describe this job's screened population as a whole. They are not a property of the individual candidate.",
    },
    sections: {
      group_analysis: { status: "available", reason: null },
      alerts: { status: "available", reason: null },
      job_description_bias: { status: "available", reason: null },
      adversarial: {
        status: "unavailable",
        reason: "No stored adversarial test result is available for this job.",
      },
    },
    score_distribution: {
      average: 68.4,
      minimum: 20,
      maximum: 95,
      median: 72.5,
      std_dev: 21.1,
      positive_outcome_threshold: 70,
      note: "These are descriptive statistics of this job's screening scores.",
    },
    group_analysis: {
      metric_status: "available",
      status_reason: null,
      reference_group: "male",
      coverage: {
        group_dimension: "gender",
        attribute_source: "self_reported",
        attributes_inferred: false,
        population: 14,
        candidates_with_demographic: 12,
        candidates_missing_demographic: 2,
        demographic_coverage_pct: 85.71,
        minimum_group_size: 5,
        positive_outcome_threshold: 70,
      },
      group_outcomes: [
        {
          group_value: "male",
          sample_size: 7,
          positive_outcome_count: 7,
          positive_outcome_rate: 1.0,
          metric_status: "available",
          status_reason: null,
        },
        {
          group_value: "female",
          sample_size: 5,
          positive_outcome_count: 2,
          positive_outcome_rate: 0.4,
          metric_status: "available",
          status_reason: null,
        },
        {
          group_value: "unknown",
          sample_size: 2,
          positive_outcome_count: null,
          positive_outcome_rate: null,
          metric_status: "no_demographic_data",
          status_reason:
            "These candidates have not supplied a self-reported gender. No value is inferred or assumed for them.",
        },
      ],
      cross_group_metrics: [
        {
          metric_name: "statistical_parity_difference",
          metric_label: "Statistical Parity Difference",
          value: 0.6,
          reference_group: "male",
          groups_compared: ["female", "male"],
          metric_status: "available",
          status_reason: null,
        },
        {
          metric_name: "disparate_impact_ratio",
          metric_label: "Disparate Impact Ratio",
          value: 0.4,
          reference_group: "male",
          groups_compared: ["female", "male"],
          metric_status: "available",
          status_reason: null,
        },
      ],
      methodology: "Selection rate defined as a screening score at or above 70.",
      grouping_note:
        "Location is reported as an advisory signal only, never as a protected group.",
    },
    alerts: [
      {
        type: "gender_skew",
        severity: "high",
        message: "Screened population is 70% male.",
        recommendation: "Review the sourcing channels for this role.",
      },
    ],
    job_description_bias: {
      job_id: jobId,
      bias_score: 62,
      overall_assessment: "moderate_bias",
      total_issues: 2,
      issue_counts: { age_biased_language: 1, exclusive_language: 1 },
      findings: [
        {
          term: "young",
          category: "age_biased_language",
          suggestion: "Remove age-coded language.",
        },
        {
          term: "rockstar",
          category: "exclusive_language",
          suggestion: "Describe the actual responsibilities.",
        },
      ],
      suggestions: [],
      note: "The same findings apply to every applicant to this role.",
    },
    adversarial: {
      status: "no_stored_result",
      tested: false,
      stability_score: null,
      sensitivity: null,
      reason: "No stored adversarial test result is available for this job.",
      run_on_demand_endpoint: "/api/v1/fairness/adversarial-test",
    },
    limitations: [
      "The screened population is small.",
      "No hiring decision has been made for this application.",
    ],
    disclaimer:
      "Fairness analysis is decision support for human review. It does not make or change any hiring decision.",
    ...overrides,
  };
}

function renderCard() {
  return render(
    <MemoryRouter>
      <ApplicationFairnessContextCard applicationId={applicationId} jobId={jobId} />
    </MemoryRouter>,
  );
}

describe("ApplicationFairnessContextCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state before the request resolves", async () => {
    let resolve: (value: ApplicationFairnessContext) => void = () => {};
    vi.mocked(getApplicationFairnessContext).mockReturnValue(
      new Promise<ApplicationFairnessContext>((r) => {
        resolve = r;
      }),
    );

    renderCard();
    expect(await screen.findByText(/Loading fairness context/i)).toBeInTheDocument();
    resolve(baseContext());
    await waitFor(() =>
      expect(screen.queryByText(/Loading fairness context/i)).not.toBeInTheDocument(),
    );
  });

  it("requests the context for the application being viewed", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();
    await waitFor(() =>
      expect(getApplicationFairnessContext).toHaveBeenCalledWith(applicationId),
    );
  });

  it("states that metrics describe the population, not the individual", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    expect(
      await screen.findByText(/not a property of the individual candidate/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/decision support for human review/i).length).toBeGreaterThan(0);
  });

  it("renders the population counts including whether this application is in it", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    expect(await screen.findByText("Applications")).toBeInTheDocument();
    const population = await screen.findByText(
      /This application's screening result is included/i,
    );
    expect(population).toBeInTheDocument();
    expect(screen.getByText("In population")).toBeInTheDocument();
  });

  it("reports that an unscreened application is excluded from the population", async () => {
    const context = baseContext();
    context.population.application_screening_included = false;
    context.screening_state = {
      effective_status: "queued",
      screened: false,
      message: "This application has no screening result.",
    };
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(context);
    renderCard();

    expect(await screen.findByText("Not included")).toBeInTheDocument();
    expect(
      await screen.findByText("This application has no screening result."),
    ).toBeInTheDocument();
  });

  it("renders the metric values exactly as returned, with no client math", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    // 0.6 and 0.4 are formatted, not recomputed: if the component derived them
    // from the group rates these would read differently.
    expect(await screen.findByText("0.60")).toBeInTheDocument();
    expect(screen.getByText("0.40")).toBeInTheDocument();
    expect(screen.getByText("Statistical Parity Difference")).toBeInTheDocument();
    expect(screen.getAllByText(/Compared against "male"/).length).toBe(2);
  });

  it("shows coverage and confirms attributes are never inferred", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    const coverage = await screen.findByText(/12 of 14 screened candidates/i);
    expect(coverage).toBeInTheDocument();
    expect(screen.getByText(/Attributes inferred: no/i)).toBeInTheDocument();
    expect(screen.getByText(/2 supplied nothing and are excluded/i)).toBeInTheDocument();
  });

  it("renders group rates as returned, including a null rate as an em dash", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    const groupSection = (await screen.findByText("Group comparison")).closest("section");
    expect(groupSection).not.toBeNull();
    const table = within(groupSection as HTMLElement);
    expect(table.getByText("100.0%")).toBeInTheDocument();
    expect(table.getByText("40.0%")).toBeInTheDocument();
    // The unknown group has no rate and must not be shown as 0%.
    expect(table.queryByText("0.0%")).not.toBeInTheDocument();
  });

  it("explains an insufficient-data state instead of showing a metric", async () => {
    const context = baseContext();
    context.group_analysis = {
      ...context.group_analysis!,
      metric_status: "insufficient_data",
      status_reason:
        "Fewer than two gender groups meet the minimum size threshold of 5, so no cross-group metric is reported.",
      reference_group: null,
      cross_group_metrics: [
        {
          metric_name: "statistical_parity_difference",
          metric_label: "Statistical Parity Difference",
          value: null,
          reference_group: null,
          groups_compared: [],
          metric_status: "insufficient_data",
          status_reason: "No eligible group to compare against.",
        },
      ],
    };
    context.sections.group_analysis = {
      status: "insufficient_data",
      reason: null,
    };
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(context);
    renderCard();

    expect(
      await screen.findByText(/Fewer than two gender groups meet the minimum size/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("0.60")).not.toBeInTheDocument();
  });

  it("handles a job with no screening data", async () => {
    const context = baseContext();
    context.group_analysis = {
      ...context.group_analysis!,
      metric_status: "no_screening_data",
      status_reason:
        "This job has no screening results, so there is no population to compare.",
      cross_group_metrics: [],
    };
    context.score_distribution = null;
    context.sections.group_analysis = {
      status: "no_screening_data",
      reason: null,
    };
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(context);
    renderCard();

    expect(
      await screen.findByText(/no screening results, so there is no population/i),
    ).toBeInTheDocument();
  });

  it("renders review alerts as prompts, not as decisions", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    expect(await screen.findByText("Review alerts")).toBeInTheDocument();
    expect(screen.getByText(/Screened population is 70% male/)).toBeInTheDocument();
    expect(
      screen.getByText(/Review the sourcing channels for this role/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Not decisions/i)).toBeInTheDocument();
  });

  it("omits the alert section when there are no alerts", async () => {
    const context = baseContext();
    context.alerts = [];
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(context);
    renderCard();

    await screen.findByText("Group comparison");
    expect(screen.queryByText("Review alerts")).not.toBeInTheDocument();
  });

  it("presents job description bias as a property of the posting", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    expect(await screen.findByText("Job description bias")).toBeInTheDocument();
    expect(screen.getByText("62")).toBeInTheDocument();
    expect(screen.getByText("Moderate bias detected")).toBeInTheDocument();
    expect(screen.getByText("young")).toBeInTheDocument();
    expect(
      screen.getByText(/same findings apply to every applicant to this role/i),
    ).toBeInTheDocument();
  });

  it("never claims an adversarial result that was not run", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    expect(await screen.findByText("Adversarial testing")).toBeInTheDocument();
    expect(screen.getByText(/No stored adversarial test result/i)).toBeInTheDocument();
    expect(screen.queryByText(/stability score/i)).not.toBeInTheDocument();
  });

  it("surfaces limitations", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    renderCard();

    expect(await screen.findByText("Limitations")).toBeInTheDocument();
    expect(screen.getByText("The screened population is small.")).toBeInTheDocument();
  });

  it("shows an error state with a retry that refetches", async () => {
    const user = userEvent.setup();
    vi.mocked(getApplicationFairnessContext)
      .mockRejectedValueOnce(new Error("Fairness service unavailable"))
      .mockResolvedValueOnce(baseContext());

    renderCard();

    expect(
      await screen.findByText(/Fairness service unavailable/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() =>
      expect(getApplicationFairnessContext).toHaveBeenCalledTimes(2),
    );
    expect(await screen.findByText("Group comparison")).toBeInTheDocument();
  });

  it("never renders a per-candidate fairness score", async () => {
    vi.mocked(getApplicationFairnessContext).mockResolvedValue(baseContext());
    const { container } = renderCard();
    await screen.findByText("Group comparison");

    // There is no such field in the response, so the UI must not invent one.
    const text = (container.textContent ?? "").toLowerCase();
    expect(text).not.toContain("fairness score");
    expect(text).not.toContain("adjusted score");
    expect(text).not.toContain("fair match score");
  });
});
