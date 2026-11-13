import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChartCard } from "../components/analytics/ChartCard";
import type { ChartData as ChartDataType } from "../types/analytics";

const HEIGHT = 200;
const PLOT_HEIGHT = HEIGHT - 24; // mirrors ChartCard plot area

const chart: ChartDataType = {
  labels: ["Jan", "Feb", "Mar"],
  datasets: [
    { label: "Applications", data: [20, 8, 12], color: "#3B82F6" },
    { label: "Offers", data: [5, 6, 10], color: "#10B981" },
  ],
};

describe("ChartCard", () => {
  it("renders dataset legend labels", () => {
    render(<ChartCard data={chart} />);
    expect(screen.getByText("Applications")).toBeInTheDocument();
    expect(screen.getByText("Offers")).toBeInTheDocument();
  });

  it("renders bars with non-zero pixel heights", () => {
    render(<ChartCard data={chart} />);
    const topBar = screen.getByTitle("Applications: 20");
    expect(topBar.style.height).toBe("176px");
    const midBar = screen.getByTitle("Offers: 6");
    expect(midBar.style.height).toBe(`${Math.round((6 / 20) * PLOT_HEIGHT)}px`);
    expect(midBar.style.height).not.toBe("0px");
  });

  it("anchors bars to the bottom of the plot area", () => {
    render(<ChartCard data={chart} />);
    const topBar = screen.getByTitle("Applications: 20");
    expect(topBar.style.height).toBeTruthy();
  });

  it("shows an empty message when all values are zero", () => {
    const empty: ChartDataType = {
      labels: ["Jan", "Feb"],
      datasets: [
        { label: "Applications", data: [0, 0], color: "#3B82F6" },
        { label: "Offers", data: [0, 0], color: "#10B981" },
      ],
    };
    render(<ChartCard data={empty} />);
    expect(
      screen.getByText("No analytics data available yet."),
    ).toBeInTheDocument();
    expect(screen.queryByTitle("Applications: 0")).not.toBeInTheDocument();
  });

  it("renders line-type charts with visible bars", () => {
    render(<ChartCard data={chart} type="line" />);
    const bar = screen.getByTitle("Applications: 20");
    expect(bar.style.height).not.toBe("0px");
  });
});
