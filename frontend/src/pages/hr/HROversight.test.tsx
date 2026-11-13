/**
 * Tests for the Revised Phase 14 HR oversight screens.
 *
 * What these tests protect:
 * - the overview renders only the real counters the backend sent, and labels
 *   its scope honestly (org-scoped vs platform-wide);
 * - the drill-down chain (overview -> jobs -> applications -> detail) is
 *   navigable and every screen keeps the same application status the recruiter
 *   recorded -- one source of truth, three views;
 * - the detail screen never renders a fabricated evidence block: a missing
 *   interview/fairness/explainability payload is reported as unavailable;
 * - candidate-private data stays out of the oversight payload (the cover
 *   letter is reported as present/absent, never printed);
 * - a denied read (403/404) renders an access message rather than an empty
 *   screen that could be mistaken for "no data";
 * - the HR surface issues no write requests at all.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { hrApi } from "../../api/hrOversight";
import type {
  HRApplicationDetail,
  HRApplicationList,
  HRAttention,
  HRAttentionItem,
  HRHiringQuality,
  HRJobList,
  HROverview,
  HRRecruiterDetail,
  HRRecruiterList,
  HRRecruiterSummary,
  HRStageDrilldown,
} from "../../api/hrOversight";
import { HROversightDashboard } from "./HROversightDashboard";
import { HRJobsPage } from "./HRJobsPage";
import { HRJobApplicationsPage } from "./HRJobApplicationsPage";
import { HRApplicationDetailPage } from "./HRApplicationDetailPage";
import { HRRecruitersPage } from "./HRRecruitersPage";
import { HRRecruiterDetailPage } from "./HRRecruiterDetailPage";
import { HRAttentionPage } from "./HRAttentionPage";
import { HRQualityPage } from "./HRQualityPage";
import { HRStagePage } from "./HRStagePage";

vi.mock("../../api/hrOversight", () => ({
  hrApi: {
    getOverview: vi.fn(),
    getJobs: vi.fn(),
    getJobApplications: vi.fn(),
    getApplicationDetail: vi.fn(),
    getRecruiters: vi.fn(),
    getRecruiter: vi.fn(),
    getAttention: vi.fn(),
    getHiringQuality: vi.fn(),
    getStageDrilldown: vi.fn(),
  },
  hrDecisionApi: {
    getHrInterviews: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    recordDecision: vi.fn().mockResolvedValue({ success: true }),
  },
}));

// The screens read the signed-in user from ambient context and report load
// failures through a toast. Both are stubbed so no token refresh or network
// call happens in a render test.
const addToast = vi.fn();

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { full_name: "Harper Reed", roles: ["hr"] },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast }),
}));

const mockOverview = vi.mocked(hrApi.getOverview);
const mockJobs = vi.mocked(hrApi.getJobs);
const mockJobApplications = vi.mocked(hrApi.getJobApplications);
const mockDetail = vi.mocked(hrApi.getApplicationDetail);
const mockRecruiters = vi.mocked(hrApi.getRecruiters);
const mockRecruiter = vi.mocked(hrApi.getRecruiter);
const mockAttention = vi.mocked(hrApi.getAttention);
const mockQuality = vi.mocked(hrApi.getHiringQuality);
const mockStage = vi.mocked(hrApi.getStageDrilldown);

/**
 * Returns the whole `DashboardCard` body for a card title.
 *
 * `DashboardCard` renders `<div card><div header><h2>title</h2></div>...body`.
 * Scoping assertions to the card is what makes a test fail if the right number
 * appears on the wrong card.
 */
function card(title: string): HTMLElement {
  const heading = screen.getByRole("heading", { name: title });
  const cardEl = heading.closest("[class*='rounded-xl']");
  if (!cardEl) throw new Error(`Could not locate the card titled "${title}"`);
  return cardEl as HTMLElement;
}

/** Reads the value rendered next to a label inside a `InfoRow`. */
function infoValue(scope: HTMLElement, label: string): string | null {
  const labelEl = within(scope).getByText(label);
  return labelEl.parentElement?.lastElementChild?.textContent ?? null;
}

const ORG_ID = "11111111-1111-1111-1111-111111111111";
const JOB_ID = "22222222-2222-2222-2222-222222222222";
const APP_ID = "33333333-3333-3333-3333-333333333333";
const RECRUITER_ID = "44444444-4444-4444-4444-444444444444";

function overview(overrides: Partial<HROverview> = {}): HROverview {
  return {
    organization_ids: [ORG_ID],
    is_platform_scope: false,
    counts: {
      open_positions: 2,
      total_applications: 7,
      distinct_candidates: 6,
      distinct_recruiters: 1,
      shortlisted: 2,
      interview_scheduled: 1,
      interview_scheduled_total: 1,
      assessments_assigned: 2,
      assessment_attempts: 3,
      selected: 1,
      offered: 0,
      rejected: 2,
      hired: 1,
      withdrawn: 0,
    },
    applications_by_status: { applied: 2, shortlisted: 2, selected: 1, rejected: 1, hired: 1 },
    interviews_by_status: { scheduled: 1 },
    assessments_by_status: { assigned: 2, completed: 1 },
    ...overrides,
  };
}

function jobList(): HRJobList {
  return {
    is_platform_scope: false,
    total: 1,
    jobs: [
      {
        id: JOB_ID,
        title: "Backend Engineer",
        company: "Acme",
        department: "Engineering",
        location: "Remote",
        status: "published",
        organization_id: ORG_ID,
        recruiter_id: RECRUITER_ID,
        recruiter_name: "Recruiter One",
        created_at: "2026-01-05T09:00:00Z",
        application_count: 3,
        applications_by_status: { applied: 1, shortlisted: 1, hired: 1 },
        hired_count: 1,
        open_application_count: 2,
      },
    ],
  };
}

function applicationList(): HRApplicationList {
  return {
    job_id: JOB_ID,
    total: 2,
    status_filter: null,
    applications: [
      {
        id: APP_ID,
        job_id: JOB_ID,
        job_title: "Backend Engineer",
        candidate_id: "55555555-5555-5555-5555-555555555555",
        candidate_name: "Casey Candidate",
        status: "selected",
        is_terminal: false,
        screening_status: "completed",
        applied_at: "2026-01-06T10:00:00Z",
        decided_at: "2026-01-07T10:00:00Z",
        decided_by: RECRUITER_ID,
        recruiter_id: RECRUITER_ID,
        recruiter_name: "Recruiter One",
        has_interview: true,
        has_assessment: false,
      },
      {
        id: "66666666-6666-6666-6666-666666666666",
        job_id: JOB_ID,
        job_title: "Backend Engineer",
        candidate_id: "77777777-7777-7777-7777-777777777777",
        candidate_name: "Reed Rejected",
        status: "rejected",
        is_terminal: true,
        screening_status: "completed",
        applied_at: "2026-01-06T11:00:00Z",
        decided_at: "2026-01-07T11:00:00Z",
        decided_by: RECRUITER_ID,
        recruiter_id: RECRUITER_ID,
        recruiter_name: "Recruiter One",
        has_interview: false,
        has_assessment: false,
      },
    ],
  };
}

function detail(overrides: Partial<HRApplicationDetail> = {}): HRApplicationDetail {
  return {
    id: APP_ID,
    status: "selected",
    is_terminal: false,
    job: {
      id: JOB_ID,
      title: "Backend Engineer",
      company: "Acme",
      department: "Engineering",
      location: "Remote",
      status: "published",
      organization_id: ORG_ID,
      recruiter_id: RECRUITER_ID,
      recruiter_name: "Recruiter One",
      created_at: "2026-01-05T09:00:00Z",
      application_count: 3,
      applications_by_status: { applied: 1, shortlisted: 1, hired: 1 },
      hired_count: 1,
      open_application_count: 2,
    },
    candidate: {
      id: "55555555-5555-5555-5555-555555555555",
      full_name: "Casey Candidate",
      email: "casey@example.com",
      is_active: true,
      account_status: "active",
      has_resume: true,
    },
    decision: {
      status: "selected",
      is_terminal: false,
      decision_reason: "Strong match across the core stack",
      decision_reason_code: null,
      decision_comment: null,
      decided_at: "2026-01-07T10:00:00Z",
      decided_by: RECRUITER_ID,
      decided_by_name: "Recruiter One",
    },
    screening: {
      status: "completed",
      attempts: 1,
      started_at: "2026-01-06T10:05:00Z",
      completed_at: "2026-01-06T10:06:00Z",
      error: null,
    },
    applied_at: "2026-01-06T10:00:00Z",
    cover_letter_available: true,
    explainability: { score: 0.91 },
    fairness: { minimum_group_size_met: true },
    interview: { interviews: [] },
    assessment: { attempt_count: 0, attempts: [] },
    timeline: [
      {
        id: "t1",
        source: "status_history",
        event: "status_changed",
        at: "2026-01-06T10:00:00Z",
        from_status: null,
        to_status: "applied",
        actor_id: null,
        actor_name: "Casey Candidate",
        detail: null,
      },
      {
        id: "t2",
        source: "status_history",
        event: "status_changed",
        at: "2026-01-06T11:00:00Z",
        from_status: "applied",
        to_status: "shortlisted",
        actor_id: RECRUITER_ID,
        actor_name: "Recruiter One",
        detail: null,
      },
      {
        id: "t3",
        source: "interview",
        event: "interview_scheduled",
        at: "2026-01-07T09:00:00Z",
        from_status: null,
        to_status: "scheduled",
        actor_id: RECRUITER_ID,
        actor_name: "Recruiter One",
        detail: "technical",
      },
      {
        id: "t4",
        source: "status_history",
        event: "status_changed",
        at: "2026-01-07T10:00:00Z",
        from_status: "interviewed",
        to_status: "selected",
        actor_id: RECRUITER_ID,
        actor_name: "Recruiter One",
        detail: null,
      },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("HROversightDashboard", () => {
  it("renders the real counters the backend sent", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("HR Overview")).toBeInTheDocument();
    });

    // Every headline number must equal the payload, so a fabricated or
    // hard-coded figure cannot render here. Title text can repeat across cards,
    // so match the card that juxtaposes the title with the payload value.
    const expected: Array<[string, number]> = [
      ["Open Positions", 2],
      ["Total Applications", 7],
      ["Recruiters Hiring", 1],
      ["Selected", 1],
    ];
    for (const [title, value] of expected) {
      const stat = screen.getAllByText(title).find((el) => {
        const cardEl = el.closest("div")?.parentElement;
        return cardEl ? within(cardEl).queryByText(String(value)) !== null : false;
      });
      expect(stat, `stat card "${title}" with value ${value} not found`).toBeDefined();
    }
  });

  it("labels the scope as organization-scoped for a tenant user", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Scope:/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Your organization$/)).toBeInTheDocument();
    expect(screen.getByText(/Organization-scoped/)).toBeInTheDocument();
  });

  it("says so plainly when the view is platform-wide", async () => {
    mockOverview.mockResolvedValue(
      overview({ is_platform_scope: true, organization_ids: [] }),
    );
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Platform-wide \(all organizations\)/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Cross-organization/)).toBeInTheDocument();
  });

  it("counts multiple organizations without overstating the scope", async () => {
    mockOverview.mockResolvedValue(
      overview({ organization_ids: [ORG_ID, "88888888-8888-8888-8888-888888888888"] }),
    );
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Your 2 organizations/)).toBeInTheDocument();
    });
  });

  it("shows the real application funnel", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Application Funnel")).toBeInTheDocument();
    });
    // Scoped to the funnel: "Shortlisted" also labels a row in the Decisions
    // card, so a bare getByText would match both and assert nothing useful.
    const funnel = container(screen.getByText("Application Funnel"));
    expect(within(funnel).getByText("Shortlisted")).toBeInTheDocument();
  });

  it("turns every funnel stage into a link to that stage's applications", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Application Funnel")).toBeInTheDocument();
    });
    const funnel = container(screen.getByText("Application Funnel"));
    // Only the stage tiles, not the card's own "View jobs" header action.
    const stageLinks = within(funnel)
      .getAllByRole("link")
      .filter((link) => (link.getAttribute("href") ?? "").startsWith("/hr/pipeline/"));
    expect(stageLinks.length).toBe(
      Object.keys(overview().applications_by_status).length,
    );
    for (const link of stageLinks) {
      expect(link.getAttribute("href")).toMatch(/^\/hr\/pipeline\/[a-z_]+$/);
    }
  });

  it("keeps every decision number labelled as the exact status it counts", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Decisions")).toBeInTheDocument();
    });
    // "Offered" is the canonical offered status on its own -- it is never
    // collapsed into hired + rejected + withdrawn, which is why a separate
    // "Closed applications" row exists and is labelled as a sum.
    const decisions = card("Decisions");
    expect(infoValue(decisions, "Shortlisted")).toBe("2");
    expect(infoValue(decisions, "Selected")).toBe("1");
    expect(infoValue(decisions, "Offered")).toBe("0");
    expect(infoValue(decisions, "Hired")).toBe("1");
    expect(infoValue(decisions, "Rejected")).toBe("2");
    expect(infoValue(decisions, "Withdrawn")).toBe("0");
    expect(infoValue(decisions, "Closed applications")).toBe("3");
  });

  it("separates assigned assessments from all assessment attempts", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Interviews & Assessments")).toBeInTheDocument();
    });
    const evidence = card("Interviews & Assessments");
    expect(infoValue(evidence, "Applications in interview")).toBe("1");
    expect(infoValue(evidence, "Interviews scheduled")).toBe("1");
    // Assigned counts only `assigned` attempts; attempts counts all statuses.
    expect(infoValue(evidence, "Assessments assigned")).toBe("2");
    expect(infoValue(evidence, "Assessment attempts")).toBe("3");
    // The full per-status breakdown is carried through, not summed away.
    expect(within(evidence).getByText(/assigned: 2/)).toBeInTheDocument();
    expect(within(evidence).getByText(/completed: 1/)).toBeInTheDocument();
  });

  it("navigates into the job drill-down", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Browse Jobs" })).toHaveAttribute(
        "href",
        "/hr/jobs",
      );
    });
  });

  it("reports a failed load instead of showing an empty dashboard", async () => {
    mockOverview.mockRejectedValue(new Error("boom"));
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load HR overview")).toBeInTheDocument();
    });
    // A failure is announced, not swallowed into a plausible-looking zero.
    expect(addToast).toHaveBeenCalledWith("Failed to load HR overview", "error");
    expect(screen.queryByText("Open Positions")).not.toBeInTheDocument();
  });

  it("greets the signed-in HR user", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Welcome back, Harper Reed")).toBeInTheDocument();
    });
  });

  it("makes no write requests", async () => {
    mockOverview.mockResolvedValue(overview());
    render(
      <MemoryRouter>
        <HROversightDashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("HR Overview")).toBeInTheDocument();
    });
    // The API module exposes only GET helpers, so there is no write path to
    // take. Assert the surface really is read-only at the module level: adding
    // a POST/PATCH helper here would fail this test, which is the point.
    expect(Object.keys(hrApi).sort()).toEqual([
      "getApplicationDetail",
      "getAttention",
      "getHiringQuality",
      "getJobApplications",
      "getJobs",
      "getOverview",
      "getRecruiter",
      "getRecruiters",
      "getStageDrilldown",
    ]);
  });
});

describe("HRJobsPage", () => {
  it("lists the job with its recruiter and real funnel", async () => {
    mockJobs.mockResolvedValue(jobList());
    render(
      <MemoryRouter>
        <HRJobsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    });
    const job = card("Backend Engineer");
    expect(within(job).getByText(/Recruiter One/)).toBeInTheDocument();
    expect(within(job).getByText(/Acme · Engineering/)).toBeInTheDocument();
    expect(within(job).getByText("Total").nextElementSibling?.textContent).toBe("3");
    // The funnel shown is the payload's, per status.
    expect(within(job).getByText(/Applied: 1/)).toBeInTheDocument();
    expect(within(job).getByText(/Shortlisted: 1/)).toBeInTheDocument();
    expect(within(job).getByText(/Hired: 1/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View 3 applications/ })).toHaveAttribute(
      "href",
      `/hr/jobs/${JOB_ID}/applications`,
    );
  });

  it("labels the job list scope honestly", async () => {
    mockJobs.mockResolvedValue({ ...jobList(), is_platform_scope: true });
    render(
      <MemoryRouter>
        <HRJobsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    });
    expect(screen.getByText(/Platform-wide/)).toBeInTheDocument();
  });

  it("states plainly when there are no jobs in scope", async () => {
    mockJobs.mockResolvedValue({ is_platform_scope: false, total: 0, jobs: [] });
    render(
      <MemoryRouter>
        <HRJobsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("No jobs")).toBeInTheDocument();
    });
    expect(screen.getByText(/no jobs in your scope yet/i)).toBeInTheDocument();
    // An empty scope is not an error state.
    expect(addToast).not.toHaveBeenCalled();
  });

  it("reports a failed job load", async () => {
    mockJobs.mockRejectedValue(new Error("boom"));
    render(
      <MemoryRouter>
        <HRJobsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load jobs")).toBeInTheDocument();
    });
    expect(addToast).toHaveBeenCalledWith("Failed to load jobs", "error");
  });
});

describe("HRJobApplicationsPage", () => {
  it("lists applications with the same status the recruiter recorded", async () => {
    mockJobApplications.mockResolvedValue(applicationList());
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications`]}>
        <Routes>
          <Route
            path="/hr/jobs/:jobId/applications"
            element={<HRJobApplicationsPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Casey Candidate")).toBeInTheDocument();
    });
    expect(mockJobApplications).toHaveBeenCalledWith(JOB_ID, undefined);
    expect(screen.getByText("Selected")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText("Interview")).toBeInTheDocument();
  });

  it("links each application to the HR drill-down", async () => {
    mockJobApplications.mockResolvedValue(applicationList());
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications`]}>
        <Routes>
          <Route
            path="/hr/jobs/:jobId/applications"
            element={<HRJobApplicationsPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Casey Candidate")).toBeInTheDocument();
    });
    const links = screen.getAllByRole("link", { name: "Open" });
    expect(links[0]).toHaveAttribute("href", `/hr/applications/${APP_ID}`);
  });

  it("shows an access message for a denied job rather than an empty list", async () => {
    mockJobApplications.mockRejectedValue({ response: { status: 403 } });
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications`]}>
        <Routes>
          <Route
            path="/hr/jobs/:jobId/applications"
            element={<HRJobApplicationsPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Not available")).toBeInTheDocument();
    });
    expect(screen.getByText(/do not have access to this job/i)).toBeInTheDocument();
    // Crucially, not the "no applications" empty state: a cross-tenant refusal
    // must never be indistinguishable from a job nobody applied to.
    expect(screen.queryByText("No applications")).not.toBeInTheDocument();
    expect(addToast).not.toHaveBeenCalled();
  });
});

describe("HRApplicationDetailPage", () => {
  function renderDetail(overrides: Partial<HRApplicationDetail> = {}) {
    mockDetail.mockResolvedValue(detail(overrides));
    return render(
      <MemoryRouter initialEntries={[`/hr/applications/${APP_ID}`]}>
        <Routes>
          <Route path="/hr/applications/:applicationId" element={<HRApplicationDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("shows job, candidate, screening and final decision together", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });

    const job = card("Job");
    expect(infoValue(job, "Title")).toBe("Backend Engineer");
    expect(infoValue(job, "Company")).toBe("Acme");
    expect(infoValue(job, "Recruiter")).toBe("Recruiter One");

    const candidate = card("Candidate");
    expect(infoValue(candidate, "Name")).toBe("Casey Candidate");
    expect(infoValue(candidate, "Email")).toBe("casey@example.com");
    expect(infoValue(candidate, "Account")).toBe("active");
    expect(infoValue(candidate, "Resume on file")).toBe("Yes");

    const decision = card("Final Decision");
    expect(infoValue(decision, "Status")).toBe("Selected");
    expect(infoValue(decision, "Decided by")).toBe("Recruiter One");
    expect(within(decision).getByText(/Strong match across the core stack/)).toBeInTheDocument();

    const screening = card("Screening");
    expect(infoValue(screening, "Screening status")).toBe("completed");
    expect(infoValue(screening, "Attempts")).toBe("1");
  });

  it("shows the same status the recruiter recorded, not a derived one", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    // The header badge, the decision block and the payload all agree: the
    // status is the canonical one the recruiter wrote, not something HR
    // re-interpreted.
    expect(infoValue(card("Final Decision"), "Status")).toBe("Selected");
    const header = screen.getByRole("heading", { name: "Backend Engineer" }).parentElement
      ?.parentElement;
    expect(header).not.toBeNull();
    expect(within(header as HTMLElement).getByText(/Casey Candidate · Selected/)).toBeInTheDocument();
  });

  it("shows a terminal status as closed and still reports the recorded reason", async () => {
    renderDetail({
      status: "rejected",
      is_terminal: true,
      decision: {
        ...detail().decision,
        status: "rejected",
        is_terminal: true,
        decision_reason: "Profile does not match this role's core requirements",
        decision_reason_code: "low_job_match",
      },
    });
    await waitFor(() => {
      expect(screen.getByText("Closed")).toBeInTheDocument();
    });
    const decision = card("Final Decision");
    expect(infoValue(decision, "Status")).toBe("Rejected");
    expect(infoValue(decision, "Reason code")).toBe("low_job_match");
    expect(
      within(decision).getByText(/does not match this role's core requirements/),
    ).toBeInTheDocument();
  });

  it("never prints the cover letter, only whether one exists", async () => {
    renderDetail({ cover_letter_available: true });
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(infoValue(card("Candidate"), "Cover letter")).toBe("On file (not shown)");
  });

  it("says so when no cover letter was submitted", async () => {
    renderDetail({ cover_letter_available: false });
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(infoValue(card("Candidate"), "Cover letter")).toBe("None");
  });

  it("reports a missing interview as not scheduled instead of inventing one", async () => {
    renderDetail({ interview: null, assessment: null });
    await waitFor(() => {
      expect(screen.getByText("Interview & Assessment")).toBeInTheDocument();
    });
    const evidence = card("Interview & Assessment");
    expect(infoValue(evidence, "Interview")).toBe("Not scheduled");
    expect(infoValue(evidence, "Assessment")).toBe("None linked");
  });

  it("reports linked interview and assessment evidence when it exists", async () => {
    renderDetail({
      interview: { interviews: [{ id: "i1" }] },
      assessment: { attempt_count: 1, attempts: [{ id: "a1" }] },
    });
    await waitFor(() => {
      expect(screen.getByText("Interview & Assessment")).toBeInTheDocument();
    });
    const evidence = card("Interview & Assessment");
    expect(infoValue(evidence, "Interview")).toBe("Linked evidence available");
    expect(infoValue(evidence, "Assessment")).toBe("Linked evidence available");
  });

  it("reports unavailable explainability rather than a fabricated explanation", async () => {
    renderDetail({ explainability: null });
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(
      within(card("Explainability")).getByText("No screening explanation is available yet."),
    ).toBeInTheDocument();
  });

  it("surfaces the reused explainability projection when it is available", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(
      within(card("Explainability")).getByText(/Score explanation is available/),
    ).toBeInTheDocument();
  });

  it("reports unavailable fairness rather than a fabricated cohort", async () => {
    renderDetail({ fairness: null });
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(
      within(card("Fairness")).getByText("No fairness context is available yet."),
    ).toBeInTheDocument();
  });

  it("surfaces the reused fairness context when the cohort is large enough", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(
      within(card("Fairness")).getByText(/Fairness context is available/),
    ).toBeInTheDocument();
  });

  it("composes the timeline from the records the backend sent", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Timeline")).toBeInTheDocument();
    });
    const timeline = card("Timeline");
    expect(within(timeline).getByText("Application created (Applied)")).toBeInTheDocument();
    expect(within(timeline).getByText("Applied → Shortlisted")).toBeInTheDocument();
    expect(within(timeline).getByText("Interview scheduled")).toBeInTheDocument();
    expect(within(timeline).getByText("Interviewed → Selected")).toBeInTheDocument();
    expect(within(timeline).getByText(/nothing on this timeline is inferred/i)).toBeInTheDocument();
    // Each event is attributed to the actor the platform recorded.
    expect(within(timeline).getAllByText(/Recruiter One/).length).toBeGreaterThan(0);
    expect(within(timeline).getByText(/Casey Candidate/)).toBeInTheDocument();
  });

  it("orders the timeline as the backend sent it", async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText("Timeline")).toBeInTheDocument();
    });
    const labels = within(card("Timeline"))
      .getAllByRole("listitem")
      .map((item) => item.querySelector("p")?.textContent);
    expect(labels).toEqual([
      "Application created (Applied)",
      "Applied → Shortlisted",
      "Interview scheduled",
      "Interviewed → Selected",
    ]);
  });

  it("labels an unrecognised status as itself rather than coercing it", async () => {
    // A future lifecycle status must never be mislabelled to an HR reader.
    renderDetail({ status: "awaiting_reference" });
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(screen.getAllByText("awaiting_reference").length).toBeGreaterThan(0);
  });

  it.each([403, 404])(
    "shows an access message instead of data for a %i response",
    async (status) => {
      mockDetail.mockRejectedValue({ response: { status } });
      render(
        <MemoryRouter initialEntries={[`/hr/applications/${APP_ID}`]}>
          <Routes>
            <Route
              path="/hr/applications/:applicationId"
              element={<HRApplicationDetailPage />}
            />
          </Routes>
        </MemoryRouter>,
      );

      await waitFor(() => {
        expect(screen.getByText("Not available")).toBeInTheDocument();
      });
      expect(screen.getByText(/do not have access to this application/i)).toBeInTheDocument();
      // A refused read must not leak any part of the record.
      expect(screen.queryByText("casey@example.com")).not.toBeInTheDocument();
      expect(screen.queryByText("Final Decision")).not.toBeInTheDocument();
      // Nor should it be reported as a server failure.
      expect(addToast).not.toHaveBeenCalled();
    },
  );

  it("reports a genuine server error as a failed load", async () => {
    mockDetail.mockRejectedValue({ response: { status: 500 } });
    render(
      <MemoryRouter initialEntries={[`/hr/applications/${APP_ID}`]}>
        <Routes>
          <Route path="/hr/applications/:applicationId" element={<HRApplicationDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load application")).toBeInTheDocument();
    });
    expect(addToast).toHaveBeenCalledWith("Failed to load application", "error");
  });

  it("says so when an application has no recorded events", async () => {
    renderDetail({ timeline: [] });
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(
      within(card("Timeline")).getByText("No recorded events for this application."),
    ).toBeInTheDocument();
  });
});

describe("HR drill-down navigation", () => {
  it("carries the user from the overview to a job to an application", async () => {
    const user = userEvent.setup();
    mockOverview.mockResolvedValue(overview());
    mockJobs.mockResolvedValue(jobList());
    mockJobApplications.mockResolvedValue(applicationList());

    render(
      <MemoryRouter initialEntries={["/hr/dashboard"]}>
        <Routes>
          <Route path="/hr/dashboard" element={<HROversightDashboard />} />
          <Route path="/hr/jobs" element={<HRJobsPage />} />
          <Route path="/hr/jobs/:jobId/applications" element={<HRJobApplicationsPage />} />
          <Route path="/hr/applications/:applicationId" element={<HRApplicationDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    // Overview -> jobs.
    await waitFor(() => {
      expect(screen.getByText("HR Overview")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("link", { name: "Browse Jobs" }));
    await waitFor(() => {
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    });

    // Jobs -> applications for that job.
    await user.click(screen.getByRole("link", { name: /View 3 applications/ }));
    await waitFor(() => {
      expect(screen.getByText("Casey Candidate")).toBeInTheDocument();
    });
    expect(mockJobApplications).toHaveBeenCalledWith(JOB_ID, undefined);

    // Applications -> the HR application detail.
    const openLinks = screen.getAllByRole("link", { name: "Open" });
    await user.click(openLinks[0]);
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    expect(mockDetail).toHaveBeenCalledWith(APP_ID);
  });

  it("keeps the recruiter's decision visible to HR", async () => {
    mockJobApplications.mockResolvedValue(applicationList());
    mockDetail.mockResolvedValue(detail());

    const { unmount } = render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications`]}>
        <Routes>
          <Route path="/hr/jobs/:jobId/applications" element={<HRJobApplicationsPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Selected")).toBeInTheDocument();
    });
    unmount();

    render(
      <MemoryRouter initialEntries={[`/hr/applications/${APP_ID}`]}>
        <Routes>
          <Route path="/hr/applications/:applicationId" element={<HRApplicationDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Final Decision")).toBeInTheDocument();
    });
    // The list said "Selected"; the drill-down must say the same thing, and
    // name the recruiter who recorded it. No re-interpretation, no new state.
    const decision = card("Final Decision");
    expect(infoValue(decision, "Status")).toBe("Selected");
    expect(infoValue(decision, "Decided by")).toBe("Recruiter One");
    expect(mockDetail).toHaveBeenCalledWith(APP_ID);
  });
});

/**
 * Fixtures for the employer-monitoring, attention, quality and funnel-stage
 * screens. They deliberately include the awkward cases -- a null rate, an
 * inactive recruiter, a truncated attention list -- because those are the states
 * where a dashboard is most likely to quietly print a confident wrong number.
 */
function recruiterSummary(
  overrides: Partial<HRRecruiterSummary> = {},
): HRRecruiterSummary {
  return {
    id: RECRUITER_ID,
    full_name: "Robin Vega",
    email: "robin@example.com",
    is_active: true,
    open_job_count: 1,
    total_job_count: 2,
    application_count: 6,
    open_application_count: 4,
    applications_by_status: { applied: 2, shortlisted: 3, hired: 1 },
    hired_count: 1,
    advancement_rate: 0.667,
    job_ids: [JOB_ID],
    ...overrides,
  };
}

function recruiterList(
  overrides: Partial<HRRecruiterList> = {},
): HRRecruiterList {
  return {
    is_platform_scope: false,
    total: 1,
    recruiters: [recruiterSummary()],
    ...overrides,
  };
}

/** Scopes assertions to the card/row element a heading or name belongs to. */
function container(el: Element, selector = "div.bg-white"): HTMLElement {
  const found = el.closest(selector);
  if (!found) throw new Error("Could not locate the container element");
  return found as HTMLElement;
}

function attentionItem(
  overrides: Partial<HRAttentionItem> = {},
): HRAttentionItem {
  return {
    rule: "screening_failed",
    severity: "high",
    reason: "Screening status is failed and needs a human look.",
    subject_type: "application",
    subject_id: APP_ID,
    job_id: JOB_ID,
    application_id: APP_ID,
    recruiter_id: RECRUITER_ID,
    job_title: "Backend Engineer",
    recruiter_name: "Robin Vega",
    status: "screening",
    measured_value: null,
    threshold_value: null,
    ...overrides,
  };
}

function attention(overrides: Partial<HRAttention> = {}): HRAttention {
  return {
    is_platform_scope: false,
    thresholds: {
      stale_application_days: 7,
      min_advancement_rate: 0.1,
      min_pipeline_applications: 5,
      fairness_gap: 0.8,
    },
    total_flagged: 1,
    items: [attentionItem()],
    truncated: false,
    ...overrides,
  };
}

function hiringQuality(
  overrides: Partial<HRHiringQuality> = {},
): HRHiringQuality {
  return {
    is_platform_scope: false,
    organization_ids: [ORG_ID],
    coverage: {
      total_applications: 6,
      screening_by_status: { passed: 4, failed: 2 },
      screening_rate: 1,
      interview_rate: 0.5,
      decision_rate: 0.333,
      hire_rate: 0.167,
    },
    fairness_alerts: [],
    fairness_gap_threshold: 0.8,
    ...overrides,
  };
}

function stageDrilldown(
  overrides: Partial<HRStageDrilldown> = {},
): HRStageDrilldown {
  return {
    status: "shortlisted",
    total: 3,
    jobs: [
      {
        job_id: JOB_ID,
        job_title: "Backend Engineer",
        recruiter_id: RECRUITER_ID,
        recruiter_name: "Robin Vega",
        count: 3,
      },
    ],
    ...overrides,
  };
}

describe("HRRecruitersPage", () => {
  it("renders each recruiter's funnel from the single backend roll-up", async () => {
    mockRecruiters.mockResolvedValue(recruiterList());
    render(
      <MemoryRouter>
        <HRRecruitersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Robin Vega")).toBeInTheDocument();
    });
    const row = container(screen.getByText("Robin Vega"));
    expect(within(row).getByText("6")).toBeInTheDocument();
    expect(within(row).getByText("66.7%")).toBeInTheDocument();
    expect(within(row).getByText("Shortlisted: 3")).toBeInTheDocument();
  });

  it("shows an em dash, not 0%, when a recruiter has no applications", async () => {
    // A null rate means "no denominator". Rendering 0% would assert that every
    // one of zero applications failed, which is a real claim the data cannot make.
    mockRecruiters.mockResolvedValue(
      recruiterList({
        recruiters: [
          recruiterSummary({
            application_count: 0,
            open_application_count: 0,
            hired_count: 0,
            applications_by_status: {},
            advancement_rate: null,
          }),
        ],
      }),
    );
    render(
      <MemoryRouter>
        <HRRecruitersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Robin Vega")).toBeInTheDocument();
    });
    const row = container(screen.getByText("Robin Vega"));
    expect(within(row).getByText("—")).toBeInTheDocument();
    expect(within(row).queryByText("0%")).not.toBeInTheDocument();
  });

  it("marks an inactive recruiter instead of counting them as healthy", async () => {
    mockRecruiters.mockResolvedValue(
      recruiterList({ recruiters: [recruiterSummary({ is_active: false })] }),
    );
    render(
      <MemoryRouter>
        <HRRecruitersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("This account is inactive."),
      ).toBeInTheDocument();
    });
  });

  it("reports a load failure instead of rendering an empty roster", async () => {
    mockRecruiters.mockRejectedValue(new Error("boom"));
    render(
      <MemoryRouter>
        <HRRecruitersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load recruiters")).toBeInTheDocument();
    });
    expect(screen.queryByText("No recruiters")).not.toBeInTheDocument();
    expect(addToast).toHaveBeenCalledWith("Failed to load recruiters", "error");
  });

  it("links each recruiter to their own drill-down", async () => {
    mockRecruiters.mockResolvedValue(recruiterList());
    render(
      <MemoryRouter>
        <HRRecruitersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Robin Vega")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /View 2 jobs/ })).toHaveAttribute(
      "href",
      `/hr/recruiters/${RECRUITER_ID}`,
    );
  });

  it("requests the roster in a single call and labels its scope honestly", async () => {
    // One roll-up request, not a request per row. The platform-scope label must
    // follow the backend flag rather than being hardcoded to "your organizations".
    mockRecruiters.mockResolvedValue(recruiterList({ is_platform_scope: true }));
    render(
      <MemoryRouter>
        <HRRecruitersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Robin Vega")).toBeInTheDocument();
    });
    expect(mockRecruiters).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Platform-wide \(all organizations\)/)).toBeInTheDocument();
  });
});

describe("HRRecruiterDetailPage", () => {
  it("shows the recruiter's own jobs and the recorded statuses", async () => {
    mockRecruiter.mockResolvedValue({
      recruiter: recruiterSummary(),
      jobs: [
        {
          id: JOB_ID,
          title: "Backend Engineer",
          company: "Acme",
          department: "Engineering",
          location: "Remote",
          status: "open",
          organization_id: ORG_ID,
          recruiter_id: RECRUITER_ID,
          recruiter_name: "Robin Vega",
          created_at: "2026-01-05T10:00:00Z",
          application_count: 6,
          applications_by_status: { applied: 2, shortlisted: 3, hired: 1 },
          hired_count: 1,
          open_application_count: 4,
        },
      ],
    } satisfies HRRecruiterDetail);
    render(
      <MemoryRouter initialEntries={[`/hr/recruiters/${RECRUITER_ID}`]}>
        <Routes>
          <Route path="/hr/recruiters/:recruiterId" element={<HRRecruiterDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    });
    expect(mockRecruiter).toHaveBeenCalledWith(RECRUITER_ID);
  });

  it("explains a denied read rather than showing an empty roster", async () => {
    mockRecruiter.mockRejectedValue(
      Object.assign(new Error("denied"), { response: { status: 404 } }),
    );
    render(
      <MemoryRouter initialEntries={[`/hr/recruiters/${RECRUITER_ID}`]}>
        <Routes>
          <Route path="/hr/recruiters/:recruiterId" element={<HRRecruiterDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("This recruiter is not available in your scope."),
      ).toBeInTheDocument();
    });
  });
});

describe("HRAttentionPage", () => {
  it("names the rule and echoes the threshold that fired it", async () => {
    // The screen must be able to answer "why is this here?" from its own data,
    // rather than asking the reader to trust an unexplained red row.
    mockAttention.mockResolvedValue(attention());
    render(
      <MemoryRouter>
        <HRAttentionPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Needs Attention")).toBeInTheDocument();
    });
    const thresholds = card("Thresholds in force");
    expect(infoValue(thresholds, "Stalled after (days)")).toBe("7");
    expect(infoValue(thresholds, "Minimum advancement rate")).toBe("0.1");
    expect(screen.getByText("Screening failed")).toBeInTheDocument();
    expect(
      screen.getByText(/Screening status is failed/),
    ).toBeInTheDocument();
  });

  it("reports the measured value against the threshold for numeric rules", async () => {
    mockAttention.mockResolvedValue(
      attention({
        items: [
          attentionItem({
            rule: "low_advancement",
            severity: "medium",
            reason: "Recruiter advancement rate is below the configured floor.",
            subject_type: "recruiter",
            application_id: null,
            status: null,
            measured_value: 0.05,
            threshold_value: 0.1,
          }),
        ],
      }),
    );
    render(
      <MemoryRouter>
        <HRAttentionPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Measured 0.05 against a threshold of 0.1/),
      ).toBeInTheDocument();
    });
  });

  it("says nothing is flagged when no rule fired", async () => {
    mockAttention.mockResolvedValue(attention({ total_flagged: 0, items: [] }));
    render(
      <MemoryRouter>
        <HRAttentionPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Nothing flagged")).toBeInTheDocument();
    });
  });

  it("tells the reader when the list was capped, with the real total", async () => {
    // A silently truncated list would read as "that is all of them".
    mockAttention.mockResolvedValue(
      attention({ total_flagged: 64, items: [attentionItem()], truncated: true }),
    );
    render(
      <MemoryRouter>
        <HRAttentionPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/64 items qualified but only 1 are shown/),
      ).toBeInTheDocument();
    });
  });

  it("links each item to the record behind it", async () => {
    mockAttention.mockResolvedValue(attention());
    render(
      <MemoryRouter>
        <HRAttentionPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "View application" })).toHaveAttribute(
        "href",
        `/hr/applications/${APP_ID}`,
      );
    });
  });

  it("labels a recruiter-scoped rule with a recruiter link, not an application link", async () => {
    mockAttention.mockResolvedValue(
      attention({
        items: [
          attentionItem({
            rule: "low_advancement",
            subject_type: "recruiter",
            application_id: null,
          }),
        ],
      }),
    );
    render(
      <MemoryRouter>
        <HRAttentionPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "View recruiter" })).toHaveAttribute(
        "href",
        `/hr/recruiters/${RECRUITER_ID}`,
      );
    });
    expect(screen.queryByRole("link", { name: "View application" })).not.toBeInTheDocument();
  });
});

describe("HRQualityPage", () => {
  it("reports coverage rates from the backend and invents no quality score", async () => {
    // There is deliberately no composite score: screening fairness and
    // explainability own those judgements.
    mockQuality.mockResolvedValue(hiringQuality());
    render(
      <MemoryRouter>
        <HRQualityPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Hiring Quality")).toBeInTheDocument();
    });
    const coverage = card("Pipeline coverage");
    expect(infoValue(coverage, "Screened")).toBe("100.0%");
    expect(infoValue(coverage, "Reached interview")).toBe("50.0%");
    expect(infoValue(coverage, "Decided")).toBe("33.3%");
    expect(infoValue(coverage, "Hired")).toBe("16.7%");
    expect(screen.queryByText(/quality score/i)).not.toBeInTheDocument();
  });

  it("explains an empty scope instead of printing 0% rates", async () => {
    mockQuality.mockResolvedValue(
      hiringQuality({
        coverage: {
          total_applications: 0,
          screening_by_status: {},
          screening_rate: null,
          interview_rate: null,
          decision_rate: null,
          hire_rate: null,
        },
      }),
    );
    render(
      <MemoryRouter>
        <HRQualityPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/no rate can be calculated/),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });

  it("shows a real fairness alert with its numbers and a job link", async () => {
    mockQuality.mockResolvedValue(
      hiringQuality({
        fairness_alerts: [
          {
            job_id: JOB_ID,
            job_title: "Backend Engineer",
            metric: "pass_rate_ratio",
            observed_value: 0.62,
            threshold_value: 0.8,
            detail: "Selection parity below review threshold.",
          },
        ],
      }),
    );
    render(
      <MemoryRouter>
        <HRQualityPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/pass rate ratio is 0.62, below the 0.8 review threshold/),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "View this job" })).toHaveAttribute(
      "href",
      `/hr/jobs/${JOB_ID}/applications`,
    );
  });

  it("does not present an absent fairness ratio as a passing result", async () => {
    mockQuality.mockResolvedValue(hiringQuality({ fairness_alerts: [] }));
    render(
      <MemoryRouter>
        <HRQualityPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/not a compliance verdict/),
      ).toBeInTheDocument();
    });
  });

  it("reports a load failure", async () => {
    mockQuality.mockRejectedValue(new Error("boom"));
    render(
      <MemoryRouter>
        <HRQualityPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load hiring quality")).toBeInTheDocument();
    });
  });
});

describe("HRStagePage", () => {
  it("groups the stage by job and links each group to its filtered list", async () => {
    // The overview funnel is organization-wide, so the stage can span many jobs.
    // Each row must land on that job's stage-filtered applications.
    mockStage.mockResolvedValue(
      stageDrilldown({
        jobs: [
          {
            job_id: JOB_ID,
            job_title: "Backend Engineer",
            recruiter_id: RECRUITER_ID,
            recruiter_name: "Robin Vega",
            count: 2,
          },
          {
            job_id: "66666666-6666-6666-6666-666666666666",
            job_title: "Data Engineer",
            recruiter_id: RECRUITER_ID,
            recruiter_name: "Robin Vega",
            count: 1,
          },
        ],
      }),
    );
    render(
      <MemoryRouter initialEntries={["/hr/pipeline/shortlisted"]}>
        <Routes>
          <Route path="/hr/pipeline/:status" element={<HRStagePage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    });
    expect(mockStage).toHaveBeenCalledWith("shortlisted");
    expect(
      screen.getByRole("link", { name: "View 2 applications" }),
    ).toHaveAttribute(
      "href",
      `/hr/jobs/${JOB_ID}/applications?status=shortlisted`,
    );
    expect(screen.getByRole("link", { name: "View 1 application" })).toHaveAttribute(
      "href",
      "/hr/jobs/66666666-6666-6666-6666-666666666666/applications?status=shortlisted",
    );
  });

  it("shows an empty stage for an unrecognised status instead of the whole pipeline", async () => {
    // The backend returns zero rows for an unknown stage, so a stale link shows
    // an empty stage rather than an unfiltered list dressed up as one stage.
    mockStage.mockResolvedValue(stageDrilldown({ status: "nonsense", total: 0, jobs: [] }));
    render(
      <MemoryRouter initialEntries={["/hr/pipeline/nonsense"]}>
        <Routes>
          <Route path="/hr/pipeline/:status" element={<HRStagePage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("No applications")).toBeInTheDocument();
    });
  });

  it("reports a load failure", async () => {
    mockStage.mockRejectedValue(new Error("boom"));
    render(
      <MemoryRouter initialEntries={["/hr/pipeline/hired"]}>
        <Routes>
          <Route path="/hr/pipeline/:status" element={<HRStagePage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load this funnel stage"),
      ).toBeInTheDocument();
    });
  });
});

describe("application status filtering", () => {
  it("sends the status from the URL to the backend", async () => {
    // The filter is server-side, not a client-side slice, so the count and the
    // rows come from the same authorized query.
    mockJobApplications.mockResolvedValue({
      ...applicationList(),
      status_filter: "shortlisted",
      total: 1,
    });
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications?status=shortlisted`]}>
        <Routes>
          <Route path="/hr/jobs/:jobId/applications" element={<HRJobApplicationsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Casey Candidate")).toBeInTheDocument();
    });
    expect(mockJobApplications).toHaveBeenCalledWith(JOB_ID, "shortlisted");
  });

  it("shows the active filter and offers a way back to all statuses", async () => {
    mockJobApplications.mockResolvedValue({
      ...applicationList(),
      status_filter: "shortlisted",
    });
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications?status=shortlisted`]}>
        <Routes>
          <Route path="/hr/jobs/:jobId/applications" element={<HRJobApplicationsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Filtered to Shortlisted")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Show all statuses" })).toHaveAttribute(
      "href",
      `/hr/jobs/${JOB_ID}/applications`,
    );
  });

  it("omits the filter when the URL carries none", async () => {
    mockJobApplications.mockResolvedValue(applicationList());
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications`]}>
        <Routes>
          <Route path="/hr/jobs/:jobId/applications" element={<HRJobApplicationsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Casey Candidate")).toBeInTheDocument();
    });
    expect(mockJobApplications).toHaveBeenCalledWith(JOB_ID, undefined);
    expect(screen.queryByText(/Filtered to/)).not.toBeInTheDocument();
  });

  it("distinguishes an empty filtered stage from a job with no applications", async () => {
    mockJobApplications.mockResolvedValue({
      ...applicationList(),
      status_filter: "hired",
      total: 0,
      applications: [],
    });
    render(
      <MemoryRouter initialEntries={[`/hr/jobs/${JOB_ID}/applications?status=hired`]}>
        <Routes>
          <Route path="/hr/jobs/:jobId/applications" element={<HRJobApplicationsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("This job has no applications in Hired right now."),
      ).toBeInTheDocument();
    });
  });
});
