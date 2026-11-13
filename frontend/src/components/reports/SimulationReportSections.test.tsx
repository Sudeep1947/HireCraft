import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SimulationReportSections } from "./SimulationReportSections";

describe("SimulationReportSections", () => {
  it("renders readable sections instead of raw JSON", () => {
    const reportData = {
      header: {
        job_title: "Senior Frontend Engineer",
        scenario_name: "Tighten skills filter",
        generated_by: "Aisha Khan",
        generated_at: "2026-09-20T12:00:00Z",
      },
      candidate_impact: {
        total_candidates: 112,
        candidates_with_score_changes: 3,
        candidates_with_rank_changes: 2,
        candidates_entering_shortlist: 4,
        candidates_leaving_shortlist: 2,
        retained_shortlist_candidates: 12,
        largest_score_movement: 12.5,
        largest_rank_movement: 4,
        average_score_change: 0.8,
        average_rank_change: -0.3,
        top_movers_increases: [
          {
            candidate_name: "Aarav Chen",
            baseline_score: 71,
            simulation_score: 84,
            score_change: 13,
            baseline_rank: 18,
            simulation_rank: 7,
            rank_change: -11,
            shortlisted: true,
          },
        ],
        top_movers_decreases: [],
        top_rank_improvements: [],
        top_rank_declines: [],
      },
      ranking_impact: {
        overview: {
          total_candidates: 112,
          average_score_change: 0.8,
          median_score_change: 0.4,
          average_rank_change: -0.3,
          candidates_moved_up: 14,
          candidates_moved_down: 11,
          candidates_unchanged: 87,
        },
        score_movement: {
          average_change: 0.8,
          minimum_change: -4,
          maximum_change: 13,
          positive_count: 3,
          negative_count: 1,
        },
        distributions: { score_median: 74, score_mean: 72.4, score_stdev: 8.1 },
        rank_movement: {},
        shortlist_impact: {
          entering_shortlist: 4,
          leaving_shortlist: 2,
          net_change: 2,
        },
        qualification_matrix: [],
        insights: [],
      },
      requirement_impact: {
        total_changed: 2,
        candidates_affected: 5,
        added: ["TypeScript 5.x"],
        removed: ["Legacy jQuery"],
        promoted: [],
        demoted: [],
        per_requirement: [
          { requirement: "TypeScript", status: "added", candidates_affected: 3 },
        ],
      },
      threshold_impact: {
        baseline_threshold: 60,
        simulation_threshold: 72,
        qualified_baseline: 64,
        qualified_simulation: 41,
        newly_qualified: 0,
        newly_disqualified: 23,
        boundary_candidates: [
          { candidate_name: "Maya Patel", baseline_score: 71, simulation_score: 71, baseline_status: "Qualified", simulation_status: "Disqualified" },
        ],
      },
      shortlist_impact: {
        baseline_shortlist_size: 15,
        simulation_shortlist_size: 17,
        retained: 12,
        entering: 4,
        leaving: 2,
        overlap_percentage: 80,
        boundary_candidates: [],
      },
      limitations: {
        simulation_isolation_notice:
          "This simulation is an isolated what-if. No live job data was modified.",
        items: ["Small sample size for minority groups (n<5)."],
        data_integrity_notes: [],
      },
    };

    const { container } = render(<SimulationReportSections reportData={reportData} />);

    expect(screen.getByText("Candidate Impact")).toBeTruthy();
    expect(screen.getAllByText("Total candidates").length).toBeGreaterThan(0);
    expect(screen.getAllByText("112").length).toBeGreaterThan(0);
    expect(screen.getByText("Top score increases")).toBeTruthy();
    expect(screen.getByText("Aarav Chen")).toBeTruthy();
    expect(screen.getByText("+13")).toBeTruthy();

    expect(screen.getAllByText("Ranking Impact").length).toBeGreaterThan(0);
    expect(screen.getByText("Moved up")).toBeTruthy();
    expect(screen.getByText("14")).toBeTruthy();

    expect(screen.getByText("Threshold Impact")).toBeTruthy();
    expect(screen.getByText("Maya Patel")).toBeTruthy();

    expect(screen.getByText("Shortlist Impact")).toBeTruthy();
    expect(screen.getByText("80")).toBeTruthy();

    expect(screen.getByText(/isolated what-if/)).toBeTruthy();
    expect(container.textContent).not.toContain("{");
  });
});