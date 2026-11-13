import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentBuilder } from "./AssessmentBuilder";
import { assessmentApi } from "../../api/assessment";
import { recruiterJobApi } from "../../api/jobs";
import type { AssessmentResponse } from "../../types/assessment";
import type { ApplicantDashboardItem, JobListItem } from "../../types/jobs";
import type { JobAssessmentAssignResult } from "../../types/jobAssessment";

vi.mock("../../api/assessment", () => ({
  assessmentApi: { generate: vi.fn() },
}));

vi.mock("../../api/jobs", () => ({
  recruiterJobApi: {
    listJobs: vi.fn(),
    getApplicantDashboard: vi.fn(),
    createAndAssignJobAssessment: vi.fn(),
  },
}));

vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function jobListItem(overrides: Partial<JobListItem> = {}): JobListItem {
  return {
    id: "job-1",
    recruiter_id: "recruiter-1",
    title: "Senior Engineer",
    company: "Example Co",
    department: "Engineering",
    employment_type: "full_time",
    location: "Remote",
    salary_min: null,
    salary_max: null,
    salary_currency: "USD",
    status: "published",
    application_deadline: null,
    application_count: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function applicantItem(overrides: Partial<ApplicantDashboardItem> = {}): ApplicantDashboardItem {
  return {
    id: "app-1",
    job_id: "job-1",
    candidate_id: "candidate-1",
    resume_id: null,
    cover_letter: null,
    status: "shortlisted",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    candidate_name: "Alice Applicant",
    candidate_email: "alice@example.com",
    job_title: "Senior Engineer",
    effective_screening_status: "completed",
    screening_attempts: 1,
    screening_task_id: null,
    screening_started_at: null,
    screening_result: null,
    overall_match_score: null,
    recommendation: null,
    strength_level: null,
    decision_reason: null,
    decision_comment: null,
    decided_at: null,
    ...overrides,
  };
}

function dashboard(items: ApplicantDashboardItem[]) {
  return {
    job: {
      id: "job-1",
      recruiter_id: "recruiter-1",
      title: "Senior Engineer",
      company: "Example Co",
      department: "Engineering",
      employment_type: "full_time",
      experience_required: null,
      education_required: null,
      required_skills: [],
      preferred_skills: [],
      location: "Remote",
      salary_min: null,
      salary_max: null,
      salary_currency: "USD",
      description: "",
      benefits: null,
      application_deadline: null,
      status: "published",
      is_archived: false,
      version: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    items,
    total: items.length,
    page: 1,
    page_size: 100,
    total_pages: 1,
    summary: {
      job_id: "job-1",
      total_applicants: items.length,
      total_screened: 0,
      not_screened: 0,
      queued: 0,
      running: 0,
      failed: 0,
      skipped: 0,
      average_score: null,
      high_match_count: 0,
      status_breakdown: {},
      application_status_breakdown: {},
      screening_status_breakdown: {},
      recommendation_breakdown: {},
      strength_level_breakdown: {},
    },
  };
}

function assignResult(overrides: Partial<JobAssessmentAssignResult> = {}): JobAssessmentAssignResult {
  return {
    job_id: "job-1",
    job_title: "Senior Engineer",
    assessment_id: "asm-1",
    assessment_title: "Python Screen",
    created_new_assessment: true,
    requested_count: 1,
    assigned_count: 1,
    already_assigned_count: 0,
    skipped_count: 0,
    items: [
      {
        application_id: "app-1",
        candidate_id: "candidate-1",
        candidate_name: "Alice Applicant",
        outcome: "assigned",
        reason: null,
        attempt_id: "attempt-1",
        assessment_id: "asm-1",
        assessment_title: "Python Screen",
        scheduled_for: null,
        assessment_link: "/assessments/attempt-1",
        message: "Assigned and waiting for the candidate.",
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AssessmentBuilder />
    </MemoryRouter>,
  );
}

async function fillTitle() {
  await userEvent.type(screen.getByPlaceholderText(/Senior Python Engineer Screen/i), "Python Screen");
}

describe("AssessmentBuilder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(recruiterJobApi.listJobs).mockResolvedValue([jobListItem()]);
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(dashboard([applicantItem()]));
    vi.mocked(recruiterJobApi.createAndAssignJobAssessment).mockResolvedValue(assignResult());
    vi.mocked(assessmentApi.generate).mockResolvedValue({
      id: "asm-lib-1",
    } as unknown as AssessmentResponse);
  });

  it("builds an assessment and assigns it to the selected job's applicants in one action", async () => {
    renderPage();

    await fillTitle();
    await userEvent.selectOptions(await screen.findByLabelText("Job"), "job-1");

    await userEvent.click(await screen.findByLabelText("Select Alice Applicant"));
    await userEvent.click(screen.getByRole("button", { name: "Generate & assign to 1" }));

    await waitFor(() => {
      expect(recruiterJobApi.createAndAssignJobAssessment).toHaveBeenCalledTimes(1);
    });
    const [jobId, payload] = vi.mocked(recruiterJobApi.createAndAssignJobAssessment).mock.calls[0];
    expect(jobId).toBe("job-1");
    expect(payload.title).toBe("Python Screen");
    expect(payload.application_ids).toEqual(["app-1"]);
    // The job is never sent in the body: it is the path scope.
    expect(payload as unknown as Record<string, unknown>).not.toHaveProperty("job_id");
    // A per-candidate outcome is reported, not a single opaque success.
    expect(await screen.findByText("Assigned and waiting for the candidate.")).toBeInTheDocument();
    expect(recruiterJobApi.createAndAssignJobAssessment).toHaveBeenCalled();
  });

  it("publishes to the library without a job when that target is chosen", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: "Publish to library" }));
    await fillTitle();
    await userEvent.click(screen.getByRole("button", { name: "Generate & Publish" }));

    await waitFor(() => {
      expect(assessmentApi.generate).toHaveBeenCalledTimes(1);
    });
    expect(recruiterJobApi.createAndAssignJobAssessment).not.toHaveBeenCalled();
    expect(await screen.findByText("Assessment created")).toBeInTheDocument();
  });

  it("refuses to assign with no applicant selected", async () => {
    renderPage();

    await fillTitle();
    await userEvent.selectOptions(await screen.findByLabelText("Job"), "job-1");
    await userEvent.click(screen.getByRole("button", { name: "Generate & assign to 0" }));

    expect(
      await screen.findByText("Select at least one applicant to assign this assessment to."),
    ).toBeInTheDocument();
    expect(recruiterJobApi.createAndAssignJobAssessment).not.toHaveBeenCalled();
  });
});
