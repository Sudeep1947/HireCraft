import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { recruiterJobApi } from "../../api/jobs";
import { screenApplication } from "../../api/screening";
import { interviewApi } from "../../api/interview";
import { applicationAssessmentApi } from "../../api/applicationAssessment";
import { RecruiterJobApplicants } from "./JobApplicants";
import type { ApplicantDashboardItem, ApplicantDashboardResponse } from "../../types/jobs";
import type { ApplicationDecisionOptions } from "../../types/applicationDecision";
import type {
  ApplicationInterviewEvidence,
  ApplicationInterviewOptions,
} from "../../types/interview";
import type {
  ApplicationAssessmentEvidence,
  ApplicationAssessmentOptions,
} from "../../types/applicationAssessment";
import type {
  JobAssessmentAssignResult,
  JobAssessmentOptions,
} from "../../types/jobAssessment";

vi.mock("../../api/jobs", () => ({
  recruiterJobApi: {
    getApplicantDashboard: vi.fn(),
    getApplicantSummary: vi.fn(),
    updateApplicationStatus: vi.fn(),
    addNote: vi.fn(),
    getApplicationDecisionOptions: vi.fn(),
    recordApplicationDecision: vi.fn(),
    getApplicationDecisionHistory: vi.fn(),
    getJobAssessmentOptions: vi.fn(),
    assignJobAssessment: vi.fn(),
    createAndAssignJobAssessment: vi.fn(),
  },
}));

vi.mock("../../api/screening", () => ({
  screenApplication: vi.fn(),
}));

// The applicant detail mounts the Phase 11 interview panel, which loads on its
// own. Mocked here so the page's tests are not silently making real HTTP calls.
vi.mock("../../api/interview", () => ({
  interviewApi: {
    getApplicationInterviewOptions: vi.fn(),
    getApplicationInterviews: vi.fn(),
    scheduleApplicationInterview: vi.fn(),
    rescheduleApplicationInterview: vi.fn(),
    cancelApplicationInterview: vi.fn(),
    completeApplicationInterview: vi.fn(),
    // The room panel mounts with the interview panel and calls these on render,
    // so they have to exist here too or the panel throws while loading.
    getInterviewRoom: vi.fn(),
    joinInterviewRoom: vi.fn(),
  },
}));

// Same reason, for the Phase 12 assessment panel the applicant detail now mounts.
vi.mock("../../api/applicationAssessment", () => ({
  applicationAssessmentApi: {
    getOptions: vi.fn(),
    assign: vi.fn(),
    getEvidence: vi.fn(),
    getMyApplicationAssessment: vi.fn(),
  },
}));

vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

const applicantId = "app-1";
const candidateId = "candidate-1";

const job = {
  id: "job-1",
  recruiter_id: "recruiter-1",
  title: "Senior Engineer",
  company: "Example Co",
  department: "Engineering",
  employment_type: "full_time",
  experience_required: "5 years",
  education_required: null,
  required_skills: ["Python"],
  preferred_skills: [],
  location: "Remote",
  salary_min: 100000,
  salary_max: 150000,
  salary_currency: "USD",
  description: "Build reliable systems",
  benefits: null,
  application_deadline: null,
  status: "published",
  is_archived: false,
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const screeningResult = {
  id: "screening-1",
  job_id: "job-1",
  candidate_id: candidateId,
  application_id: applicantId,
  resume_id: null,
  overall_match_score: 91,
  skill_match_score: 90,
  experience_match_score: 92,
  education_match_score: 90,
  project_match_score: 89,
  certification_match_score: 88,
  location_match_score: 95,
  employment_type_match_score: 90,
  semantic_match_score: 93,
  matched_skills: ["Python"],
  missing_required_skills: [],
  missing_preferred_skills: [],
  strengths: ["Python"],
  weaknesses: [],
  recommendation: "strongly_recommend" as const,
  strength_level: "excellent" as const,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function makeResponse(overrides: Partial<ApplicantDashboardItem> = {}): ApplicantDashboardResponse {
  const applicant: ApplicantDashboardItem = {
    id: applicantId,
    job_id: "job-1",
    candidate_id: candidateId,
    resume_id: null,
    cover_letter: null,
    status: "under_review",
    screening_status: "completed",
    effective_screening_status: "completed",
    screening_task_id: null,
    screening_error: null,
    screening_started_at: null,
    screening_completed_at: "2026-01-02T00:00:00Z",
    screening_attempts: 1,
    screening_result: screeningResult,
    overall_match_score: 91,
    recommendation: "strongly_recommend",
    strength_level: "excellent",
    decision_reason: null,
    decision_comment: null,
    decided_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    candidate_name: "Alice Applicant",
    candidate_email: "alice@example.com",
    job_title: "Senior Engineer",
    company: "Example Co",
    location: "Remote",
    employment_type: "full_time",
    recruiter_notes: [],
    ...overrides,
  };

  return {
    job,
    items: [applicant],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    summary: {
      job_id: "job-1",
      total_applicants: 1,
      total_screened: 1,
      not_screened: 0,
      queued: 0,
      running: 0,
      failed: 0,
      skipped: 0,
      average_score: 91,
      high_match_count: 1,
      status_breakdown: { under_review: 1 },
      application_status_breakdown: { under_review: 1 },
      screening_status_breakdown: { completed: 1 },
      recommendation_breakdown: { strongly_recommend: 1 },
      strength_level_breakdown: { excellent: 1 },
    },
  };
}

function decisionOptions(
  overrides: Partial<ApplicationDecisionOptions> = {},
): ApplicationDecisionOptions {
  return {
    application_id: applicantId,
    current_status: "under_review",
    status_is_final: false,
    rejection_reasons: [
      {
        value: "low_job_match",
        label: "Profile does not match this role's core requirements",
        candidate_message: "Approved candidate wording for a low job match.",
      },
    ],
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

function interviewOptions(
  overrides: Partial<ApplicationInterviewOptions> = {},
): ApplicationInterviewOptions {
  return {
    application_id: applicantId,
    current_status: "under_review",
    status_is_final: false,
    can_schedule: false,
    schedule_unavailable_reason: "application_not_shortlisted",
    has_interviews: false,
    active_interview_id: null,
    options: [],
    hr_eligible: false,
    recruiter_stage_complete: false,
    can_advance: false,
    advance_unavailable_reason: "recruiter_interview_not_completed",
    can_schedule_hr: false,
    schedule_hr_unavailable_reason: "candidate_not_advanced_to_hr",
    can_reject: false,
    reject_unavailable_reason: null,
    ...overrides,
  };
}

function interviewEvidence(
  overrides: Partial<ApplicationInterviewEvidence> = {},
): ApplicationInterviewEvidence {
  return {
    application_id: applicantId,
    job_id: "job-1",
    job_title: "Senior Engineer",
    candidate_id: candidateId,
    candidate_name: "Dana Candidate",
    application_status: "under_review",
    interview_count: 0,
    completed_count: 0,
    average_overall_score: null,
    interviews: [],
    hr_eligible: false,
    advanced_to_hr_at: null,
    ...overrides,
  };
}

function assessmentOptions(
  overrides: Partial<ApplicationAssessmentOptions> = {},
): ApplicationAssessmentOptions {
  return {
    application_id: applicantId,
    current_status: "shortlisted",
    status_is_final: false,
    can_assign: true,
    assign_unavailable_reason: null,
    has_assessments: false,
    attempt_count: 0,
    available: [],
    actions: [],
    ...overrides,
  };
}

function assessmentEvidence(
  overrides: Partial<ApplicationAssessmentEvidence> = {},
): ApplicationAssessmentEvidence {
  return {
    application_id: applicantId,
    job_id: "job-1",
    job_title: "Senior Engineer",
    candidate_id: candidateId,
    candidate_name: "Dana Candidate",
    application_status: "shortlisted",
    attempt_count: 0,
    completed_count: 0,
    average_overall_score: null,
    attempts: [],
    ...overrides,
  };
}

function renderPage() {  return render(
    <MemoryRouter initialEntries={[`/recruiter/jobs/job-1/applicants?application=${applicantId}`]}>
      <Routes>
        <Route path="/recruiter/jobs/:id/applicants" element={<RecruiterJobApplicants />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RecruiterJobApplicants", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(makeResponse());
    vi.mocked(recruiterJobApi.getApplicantSummary).mockResolvedValue(makeResponse().summary);
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(decisionOptions());
    vi.mocked(interviewApi.getApplicationInterviewOptions).mockResolvedValue(
      interviewOptions(),
    );
    vi.mocked(interviewApi.getApplicationInterviews).mockResolvedValue(
      interviewEvidence(),
    );
    vi.mocked(applicationAssessmentApi.getOptions).mockResolvedValue(
      assessmentOptions(),
    );
    vi.mocked(applicationAssessmentApi.getEvidence).mockResolvedValue(
      assessmentEvidence(),
    );
    vi.mocked(interviewApi.getInterviewRoom).mockResolvedValue({
      interview_id: "int-1",
      application_id: "app-1",
      interview_type: "recruiter_scheduled",
      stage: "recruiter",
      status: "scheduled",
      state: "ready_to_join",
      rescheduled_at: null,
      your_role: "interviewer",
      room_id: "room-abc123",
      scheduled_at: "2026-01-05T14:00:00Z",
      timezone: "UTC",
      duration_minutes: 60,
      join_opens_at: "2026-01-05T13:45:00Z",
      join_closes_at: "2026-01-05T15:00:00Z",
      server_time: "2026-01-05T13:50:00Z",
      can_join: true,
      unavailable_reason: null,
      you_joined: false,
      presence: {
        candidate_joined: false,
        candidate_joined_at: null,
        interviewer_joined: false,
        interviewer_joined_at: null,
      },
      message: "The room is open. Join when you are ready.",
    });
  });

  it("loads the selected applicant and sends dashboard filters to the API", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Applicants for Senior Engineer" })).toBeInTheDocument();
    expect(await screen.findByText("Screening: Screened")).toBeInTheDocument();
    expect(screen.getByText("Match 91")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Screening status"), { target: { value: "completed" } });

    await waitFor(() => {
      expect(recruiterJobApi.getApplicantDashboard).toHaveBeenLastCalledWith("job-1", {
        sort_by: "-created_at",
        screening_status: "completed",
        page: 1,
        page_size: 20,
      });
    });
  });

  it("links the selected applicant to the screening detail page", async () => {
    renderPage();

    const link = await screen.findByRole("link", { name: "Screening detail" });
    expect(link).toHaveAttribute(
      "href",
      "/recruiter/jobs/job-1/applicants/app-1/screening",
    );
  });

  it("runs screening for the selected applicant", async () => {
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(
      makeResponse({
        screening_status: "not_started",
        effective_screening_status: "not_started",
        screening_result: null,
        overall_match_score: null,
        recommendation: null,
        strength_level: null,
      }),
    );
    vi.mocked(screenApplication).mockResolvedValue(screeningResult);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Run screening" }));

    await waitFor(() => {
      expect(screenApplication).toHaveBeenCalledWith(applicantId);
    });
    await waitFor(() => {
      expect(recruiterJobApi.getApplicantDashboard).toHaveBeenCalledTimes(2);
    });
  });

  it("hides manual screening for a final application status", async () => {
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(
      makeResponse({
        status: "rejected",
        effective_screening_status: "not_started",
        screening_result: null,
        overall_match_score: null,
        recommendation: null,
        strength_level: null,
      }),
    );
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
      decisionOptions({ current_status: "rejected", status_is_final: true }),
    );
    renderPage();

    expect(await screen.findByRole("heading", { name: "Applicants for Senior Engineer" })).toBeInTheDocument();
    expect(
      await screen.findByText("This application reached a final status, so screening can no longer be started."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run screening" })).not.toBeInTheDocument();
  });

  it("omits out-of-range score inputs from the dashboard query", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Applicants for Senior Engineer" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Min match score"), { target: { value: "150" } });

    expect(await screen.findByText("Enter a whole number between 0 and 100")).toBeInTheDocument();
    expect(recruiterJobApi.getApplicantDashboard).toHaveBeenCalledTimes(1);
    expect(recruiterJobApi.getApplicantDashboard).not.toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({ min_score: 150 }),
    );
  });

  // ── Phase 8: explicit decisions ───────────────────────────────────

  it("offers the server-provided decisions for the selected applicant", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: "Shortlist" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(recruiterJobApi.getApplicationDecisionOptions).toHaveBeenCalledWith(applicantId);
  });

  it("no longer offers a raw status dropdown", async () => {
    renderPage();

    await screen.findByRole("button", { name: "Shortlist" });
    expect(screen.queryByLabelText(/change application status/i)).toBeNull();
  });

  it("records a decision and refreshes the applicant list", async () => {
    vi.mocked(recruiterJobApi.recordApplicationDecision).mockResolvedValue({
      application_id: applicantId,
      decision: "shortlist",
      previous_status: "under_review",
      status: "shortlisted",
      changed_status: true,
      rejection_reason: null,
      rejection_reason_label: null,
      internal_note: null,
      candidate_status_label: "Shortlisted",
      candidate_message: "Approved candidate wording.",
      decided_at: "2026-01-02T00:00:00Z",
      decided_by: "recruiter-1",
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Shortlist" }));

    await waitFor(() => {
      expect(recruiterJobApi.recordApplicationDecision).toHaveBeenCalledWith(
        applicantId,
        "shortlist",
        undefined,
      );
    });
    // The row's status is refreshed from the server rather than guessed locally.
    await waitFor(() => {
      expect(recruiterJobApi.getApplicantDashboard).toHaveBeenCalledTimes(2);
    });
  });

  it("shows a final application with no decision buttons", async () => {
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(
      makeResponse({
        status: "rejected",
        effective_screening_status: "not_started",
        screening_result: null,
        overall_match_score: null,
        recommendation: null,
        strength_level: null,
      }),
    );
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
      decisionOptions({
        current_status: "rejected",
        status_is_final: true,
        options: decisionOptions().options.map((o) => ({
          ...o,
          available: false,
          unavailable_reason: "Application is already rejected",
        })),
      }),
    );
    renderPage();

    expect(
      await screen.findByText(
        "This application reached a final status, so screening can no longer be started.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Shortlist" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
  });

  it("mounts the interview panel for the selected application", async () => {
    renderPage();

    await screen.findByRole("heading", { name: "Interview" });
    // Keyed by the application, never by job/candidate/recruiter.
    expect(interviewApi.getApplicationInterviewOptions).toHaveBeenCalledWith(
      applicantId,
    );
    expect(interviewApi.getApplicationInterviews).toHaveBeenCalledWith(applicantId);
  });

  it("labels an application that has completed an interview as Interviewed", async () => {
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(
      makeResponse({ status: "interviewed" }),
    );
    vi.mocked(interviewApi.getApplicationInterviewOptions).mockResolvedValue(
      interviewOptions({ current_status: "interviewed" }),
    );
    vi.mocked(interviewApi.getApplicationInterviews).mockResolvedValue(
      interviewEvidence({ application_status: "interviewed" }),
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getAllByText("Interviewed").length).toBeGreaterThan(0);
    });
  });

  it("does not let a failed interview load hide the rest of the applicant", async () => {
    vi.mocked(interviewApi.getApplicationInterviews).mockRejectedValue(
      new Error("network down"),
    );
    renderPage();

    // The interview panel degrades on its own; screening is still usable.
    expect(await screen.findByText("network down")).toBeInTheDocument();
    expect(screen.getByText("Match 91")).toBeInTheDocument();
  });

  it("mounts the assessment panel for the selected application", async () => {
    renderPage();

    // Wait for the panel's *loaded* state, not its heading: the heading also
    // exists in the loading state and is replaced by a new node when the load
    // resolves, which would detach whatever the query handed back.
    expect(
      await screen.findByText("No assessment assigned to this application yet."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assessment" })).toBeInTheDocument();
    // Keyed by the application, never by job/candidate/recruiter: the panel
    // cannot aim an assessment at a different candidate or job.
    expect(applicationAssessmentApi.getOptions).toHaveBeenCalledWith(applicantId);
    expect(applicationAssessmentApi.getEvidence).toHaveBeenCalledWith(applicantId);
  });

  it("keeps the decision, interview and assessment panels together on one application", async () => {
    renderPage();

    // All three evidence surfaces coexist, and none of them is a decision.
    expect(
      await screen.findByText("No assessment assigned to this application yet."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assessment" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Interview" })).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Shortlist" }),
    ).toBeInTheDocument();
  });

  it("does not let a failed assessment load hide the rest of the applicant", async () => {
    vi.mocked(applicationAssessmentApi.getEvidence).mockRejectedValue(
      new Error("assessment service down"),
    );
    renderPage();

    // The assessment panel degrades on its own; the rest of the applicant is
    // still readable and the decision is still available.
    expect(await screen.findByText("assessment service down")).toBeInTheDocument();
    expect(screen.getByText("Match 91")).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Shortlist" }),
    ).toBeInTheDocument();
  });

  it("offers no assignment on an application the server says is finalized", async () => {
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(
      makeResponse({ status: "rejected", effective_screening_status: "not_started" }),
    );
    vi.mocked(applicationAssessmentApi.getOptions).mockResolvedValue(
      assessmentOptions({
        current_status: "rejected",
        status_is_final: true,
        can_assign: false,
        assign_unavailable_reason: "application_is_final",
      }),
    );
    renderPage();

    expect(
      await screen.findByText("This application has reached a final outcome"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign assessment" })).toBeNull();
  });
});

/**
 * Phase 1 bulk assignment. Ticking one or more applicants in the list is the
 * only way to reach the batch panel, and the request the panel sends names the
 * job and the ticked application ids and nothing else.
 */
describe("RecruiterJobApplicants bulk assessment assignment", () => {
  function jobAssessmentOptions(): JobAssessmentOptions {
    return {
      job_id: "job-1",
      job_title: "Senior Engineer",
      available: [
        {
          assessment_id: "asm-1",
          title: "Python Screen",
          description: "Core Python",
          mode: "technical",
          status: "published",
          duration_minutes: 45,
          question_count: 20,
          passing_score: 60,
          allowed_attempts: 1,
          adaptive: false,
          skills: ["Python"],
          already_assigned: false,
        },
      ],
    };
  }

  function assignResult(
    overrides: Partial<JobAssessmentAssignResult> = {},
  ): JobAssessmentAssignResult {
    return {
      job_id: "job-1",
      job_title: "Senior Engineer",
      assessment_id: "asm-1",
      assessment_title: "Python Screen",
      created_new_assessment: false,
      requested_count: 1,
      assigned_count: 1,
      already_assigned_count: 0,
      skipped_count: 0,
      items: [
        {
          application_id: applicantId,
          candidate_id: candidateId,
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

  beforeEach(() => {
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(makeResponse());
    vi.mocked(recruiterJobApi.getApplicantSummary).mockResolvedValue(makeResponse().summary);
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(decisionOptions());
    vi.mocked(interviewApi.getApplicationInterviewOptions).mockResolvedValue(interviewOptions());
    vi.mocked(interviewApi.getApplicationInterviews).mockResolvedValue(interviewEvidence());
    vi.mocked(applicationAssessmentApi.getOptions).mockResolvedValue(assessmentOptions());
    vi.mocked(applicationAssessmentApi.getEvidence).mockResolvedValue(assessmentEvidence());
    vi.mocked(recruiterJobApi.getJobAssessmentOptions).mockResolvedValue(jobAssessmentOptions());
    vi.mocked(recruiterJobApi.assignJobAssessment).mockResolvedValue(assignResult());
  });

  it("offers no batch action until an applicant is ticked", async () => {
    renderPage();

    await screen.findByText("Alice Applicant");
    expect(
      screen.queryByRole("button", { name: "Bulk assign assessment" }),
    ).not.toBeInTheDocument();
  });

  it("sends only the job and the ticked application ids", async () => {
    renderPage();

    await userEvent.click(await screen.findByLabelText("Select Alice Applicant"));
    await userEvent.click(
      await screen.findByRole("button", { name: "Bulk assign assessment" }),
    );

    await screen.findByRole("heading", { name: "Assign an assessment to 1 applicant" });
    await userEvent.click(await screen.findByRole("button", { name: "Assign to 1" }));

    await waitFor(() => {
      expect(recruiterJobApi.assignJobAssessment).toHaveBeenCalledWith("job-1", {
        assessment_id: "asm-1",
        application_ids: [applicantId],
      });
    });
    expect(
      await screen.findByText("Assigned and waiting for the candidate."),
    ).toBeInTheDocument();
  });

  it("clears the selection", async () => {
    renderPage();

    await userEvent.click(await screen.findByLabelText("Select Alice Applicant"));
    expect(await screen.findByText("1 applicant selected")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(
      screen.queryByRole("button", { name: "Bulk assign assessment" }),
    ).not.toBeInTheDocument();
  });
});

/**
 * A recruiter ends up in support with "this is the candidate" and no name. The
 * identifiers are the fix, and they have to be unambiguous: a bare uuid beside
 * a name is not enough to tell a recruiter which uuid to quote.
 */
describe("RecruiterJobApplicants identifiers", () => {
  const CANDIDATE_UUID = "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44";
  const APPLICATION_UUID = "8f4c2b91-3d6e-4a58-b0f1-92c7e6d4a803";
  const JOB_UUID = "6b1d9f20-4c77-4a91-8f3e-2a5c0b7d1e66";

  // The page picks its detail pane from the `application` query parameter, so
  // the id baked into the fixture has to be the one in the URL.
  function renderIdentifiersPage() {
    return render(
      <MemoryRouter
        initialEntries={[
          `/recruiter/jobs/${JOB_UUID}/applicants?application=${APPLICATION_UUID}`,
        ]}
      >
        <Routes>
          <Route
            path="/recruiter/jobs/:id/applicants"
            element={<RecruiterJobApplicants />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(recruiterJobApi.getApplicantDashboard).mockResolvedValue(
      makeResponse({
        id: APPLICATION_UUID,
        job_id: JOB_UUID,
        candidate_id: CANDIDATE_UUID,
      }),
    );
    vi.mocked(recruiterJobApi.getApplicantSummary).mockResolvedValue(
      makeResponse().summary,
    );
    vi.mocked(recruiterJobApi.getApplicationDecisionOptions).mockResolvedValue(
      decisionOptions(),
    );
    vi.mocked(interviewApi.getApplicationInterviewOptions).mockResolvedValue(
      interviewOptions(),
    );
    vi.mocked(interviewApi.getApplicationInterviews).mockResolvedValue(
      interviewEvidence(),
    );
    vi.mocked(applicationAssessmentApi.getOptions).mockResolvedValue(
      assessmentOptions(),
    );
    vi.mocked(applicationAssessmentApi.getEvidence).mockResolvedValue(
      assessmentEvidence(),
    );
  });

  it("names the applicant instead of showing a bare uuid as the heading", async () => {
    renderIdentifiersPage();
    expect(await screen.findByText("Alice Applicant")).toBeInTheDocument();
    // The old behaviour was to lead with a truncated uuid in place of a name.
    expect(
      screen.queryByText(CANDIDATE_UUID.slice(0, 13)),
    ).not.toBeInTheDocument();
  });

  it("labels the candidate, application and job ids separately", async () => {
    renderIdentifiersPage();
    const identity = await screen.findByTestId("application-identity");

    for (const label of ["Candidate ID", "Application ID", "Job ID"]) {
      expect(within(identity).getByText(label, { selector: "label" })).toBeInTheDocument();
    }
    expect(within(identity).getByTitle(CANDIDATE_UUID)).toBeInTheDocument();
    expect(within(identity).getByTitle(APPLICATION_UUID)).toBeInTheDocument();
    expect(within(identity).getByTitle(JOB_UUID)).toBeInTheDocument();
  });

  it("copies the full candidate id, not the abbreviation on screen", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });
    renderIdentifiersPage();
    await screen.findByTestId("application-identity");

    await userEvent.click(
      await screen.findByRole("button", { name: /copy candidate id/i }),
    );
    expect(writeText).toHaveBeenCalledWith(CANDIDATE_UUID);
  });
});
