/**
 * The dashboard used to label people and jobs by a truncated UUID, because the
 * API returned only ids. These cover the fix: a name is used when the server
 * sends one, and the id is still available behind it.
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { dashboardApi } from "../../api/dashboard";
import { RecruiterDashboard } from "./RecruiterDashboard";

vi.mock("../../api/dashboard", () => ({
  dashboardApi: {
    getRecruiter: vi.fn(),
  },
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "recruiter-1", roles: ["recruiter"] } }),
}));

const addToast = vi.fn();
vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast }),
}));

const CANDIDATE_ID = "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44";
const APPLICATION_ID = "8f4c2b91-3d6e-4a58-b0f1-92c7e6d4a803";
const JOB_ID = "6b1d9f20-4c77-4a91-8f3e-2a5c0b7d1e66";

function dashboard(overrides: Record<string, unknown> = {}) {
  return {
    total_jobs: 1,
    active_jobs: 1,
    total_applications: 1,
    candidates_screened: 1,
    top_candidates: [
      {
        candidate_id: CANDIDATE_ID,
        candidate_name: "John Doe",
        overall_score: 88,
        rank: 1,
        strength_level: "strong",
      },
    ],
    interview_pipeline: {},
    hiring_status: {},
    recent_applications: [
      {
        id: APPLICATION_ID,
        job_id: JOB_ID,
        job_title: "Senior Backend Engineer",
        candidate_id: CANDIDATE_ID,
        status: "under_review",
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RecruiterDashboard />
    </MemoryRouter>,
  );
}

describe("RecruiterDashboard identifiers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardApi.getRecruiter).mockResolvedValue(
      dashboard() as never,
    );
  });

  it("labels a candidate by name, not by a truncated uuid", async () => {
    renderPage();
    expect(await screen.findByText("John Doe")).toBeInTheDocument();
    // The old rendering was "Candidate 2a91f6d3", which identifies nobody.
    expect(screen.queryByText(/Candidate 2a91f6d3/)).not.toBeInTheDocument();
  });

  it("keeps the full candidate id available next to the name", async () => {
    renderPage();
    expect(
      await screen.findByText(`Candidate ID ${CANDIDATE_ID}`),
    ).toBeInTheDocument();
  });

  it("names the job on a recent application", async () => {
    renderPage();
    expect(
      await screen.findByText(`Senior Backend Engineer · Job ID ${JOB_ID}`),
    ).toBeInTheDocument();
  });

  it("falls back to a short id when the server sends no name", async () => {
    // An older or partially-populated row must not leave the row blank.
    vi.mocked(dashboardApi.getRecruiter).mockResolvedValue(
      dashboard({
        top_candidates: [
          {
            candidate_id: CANDIDATE_ID,
            overall_score: 88,
            rank: 1,
            strength_level: "strong",
          },
        ],
        recent_applications: [
          {
            id: APPLICATION_ID,
            job_id: JOB_ID,
            candidate_id: CANDIDATE_ID,
            status: "under_review",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      }) as never,
    );
    renderPage();
    expect(await screen.findByText("Candidate 2a91f6d3")).toBeInTheDocument();
    expect(screen.getByText(`Job ID ${JOB_ID}`)).toBeInTheDocument();
  });
});
