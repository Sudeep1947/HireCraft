/**
 * The scheduling flow a recruiter actually uses.
 *
 * The point of these tests is the thing the old page got wrong: there is no
 * field to type a candidate's UUID into, and the interview is keyed by the
 * application the recruiter picked rather than by an identifier they supplied.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { interviewApi } from "../../api/interview";
import { recruiterJobApi } from "../../api/jobs";
import { InterviewSchedule } from "./InterviewSchedule";
import type { JobApplication } from "../../types/jobs";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    scheduleApplicationInterview: vi.fn(),
    scheduleInterview: vi.fn(),
  },
}));

vi.mock("../../api/jobs", () => ({
  recruiterJobApi: {
    listJobs: vi.fn(),
    getApplications: vi.fn(),
  },
}));

const addToast = vi.fn();
vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast }),
}));

const CANDIDATE_ID = "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44";
const APPLICATION_ID = "8f4c2b91-3d6e-4a58-b0f1-92c7e6d4a803";
const JOB_ID = "6b1d9f20-4c77-4a91-8f3e-2a5c0b7d1e66";

function application(overrides: Partial<JobApplication> = {}): JobApplication {
  return {
    id: APPLICATION_ID,
    job_id: JOB_ID,
    candidate_id: CANDIDATE_ID,
    candidate_name: "John Doe",
    candidate_email: "john@example.com",
    job_title: "Senior Backend Engineer",
    status: "shortlisted",
    resume_id: null,
    cover_letter: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as JobApplication;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/recruiter/interviews/schedule"]}>
      <Routes>
        <Route
          path="/recruiter/interviews/schedule"
          element={<InterviewSchedule />}
        />
        <Route path="/recruiter/interviews" element={<p>Interview workspace</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * The job picker, once its options have actually arrived.
 *
 * `selectOptions` validates the value against the rendered options, so waiting
 * for the select to stop being disabled is not enough -- it can be enabled
 * while the list is still empty.
 */
async function jobSelect() {
  await waitFor(() =>
    expect(
      screen.getByRole("option", { name: "Senior Backend Engineer" }),
    ).toBeInTheDocument(),
  );
  return screen.getByLabelText("Job");
}

/** Choose a job, then an applicant, and wait for the identity card to settle. */
async function selectApplicant() {
  await userEvent.selectOptions(await jobSelect(), JOB_ID);
  await waitFor(() =>
    expect(screen.getByLabelText("Applicant")).not.toBeDisabled(),
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Applicant"),
    APPLICATION_ID,
  );
  await screen.findByTestId("application-identity");
}

describe("InterviewSchedule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(recruiterJobApi.listJobs).mockResolvedValue([
      { id: JOB_ID, title: "Senior Backend Engineer" },
    ] as never);
    vi.mocked(recruiterJobApi.getApplications).mockResolvedValue([
      application(),
    ] as never);
    vi.mocked(interviewApi.scheduleApplicationInterview).mockResolvedValue({
      application_id: APPLICATION_ID,
      interview_id: "int-1",
      interview_status: "scheduled",
      application_status: "interview_scheduled",
      application_status_changed: true,
      message: "Interview scheduled successfully",
    } as never);
  });

  it("never asks the recruiter to type a candidate UUID", async () => {
    renderPage();
    await selectApplicant();

    // The regression this replaces: a required "Candidate ID *" text box with
    // the placeholder "Enter candidate UUID".
    expect(
      screen.queryByPlaceholderText("Enter candidate UUID"),
    ).not.toBeInTheDocument();
    // The practice-interview section is collapsed, so the only identifier input
    // on the page is not even part of the form's visible workflow.
    expect(
      screen.getByText(/practice interview for a candidate who has not applied/i),
    ).toBeInTheDocument();
  });

  it("shows the candidate and application identifiers for the selected applicant", async () => {
    renderPage();
    await selectApplicant();

    const identity = screen.getByTestId("application-identity");
    expect(within(identity).getByText("John Doe")).toBeInTheDocument();
    expect(
      within(identity).getByText("Senior Backend Engineer"),
    ).toBeInTheDocument();

    // Labelled, and each says what it identifies.
    for (const label of ["Candidate ID", "Application ID", "Job ID"]) {
      expect(within(identity).getByText(label, { selector: "label" })).toBeInTheDocument();
    }
    expect(
      within(identity).getByTitle(CANDIDATE_ID),
    ).toBeInTheDocument();
    expect(
      within(identity).getByTitle(APPLICATION_ID),
    ).toBeInTheDocument();
  });

  it("schedules by application id, deriving the candidate server-side", async () => {
    renderPage();
    await selectApplicant();

    await userEvent.click(
      screen.getByRole("button", { name: /schedule interview/i }),
    );

    await waitFor(() =>
      expect(interviewApi.scheduleApplicationInterview).toHaveBeenCalledTimes(1),
    );

    // The application id is the only identifier in the request. There is no
    // candidate_id and no job_id for the server to be misled by.
    const [applicationId, body] = vi.mocked(
      interviewApi.scheduleApplicationInterview,
    ).mock.calls[0];
    expect(applicationId).toBe(APPLICATION_ID);
    expect(body).not.toHaveProperty("candidate_id");
    expect(body).not.toHaveProperty("job_id");
    expect(body).toMatchObject({
      duration_minutes: 60,
      question_count: 10,
      difficulty: "medium",
    });
    expect(typeof body.scheduled_at).toBe("string");

    // The legacy job+candidate endpoint is not used for a real applicant.
    expect(interviewApi.scheduleInterview).not.toHaveBeenCalled();
    expect(addToast).toHaveBeenCalledWith(
      "Interview scheduled successfully",
      "success",
    );
  });

  it("cannot submit until an applicant is chosen", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByLabelText("Job")).not.toBeDisabled(),
    );
    expect(
      screen.getByRole("button", { name: /schedule interview/i }),
    ).toBeDisabled();
    expect(
      screen.getByText(/select an applicant to enable scheduling/i),
    ).toBeInTheDocument();
  });

  it("does not look up applicants until a job is chosen", () => {
    renderPage();
    expect(recruiterJobApi.getApplications).not.toHaveBeenCalled();
    expect(
      screen.getByText(/select a job first/i),
    ).toBeInTheDocument();
  });

  it("explains a scheduling failure without leaking a stack trace", async () => {
    vi.mocked(interviewApi.scheduleApplicationInterview).mockRejectedValue(
      new Error("Request failed with status code 409"),
    );
    renderPage();
    await selectApplicant();

    await userEvent.click(
      screen.getByRole("button", { name: /schedule interview/i }),
    );

    await waitFor(() =>
      expect(addToast).toHaveBeenCalledWith(expect.any(String), "error"),
    );
    const errorCall = addToast.mock.calls.find(([, kind]) => kind === "error");
    const message = errorCall?.[0];
    // A human sentence: not a traceback, and not an API-level complaint about a
    // field the recruiter never saw on this page.
    expect(typeof message).toBe("string");
    expect(message).not.toMatch(/Traceback|File "|at async/i);
    expect(message).not.toMatch(/^Candidate ID required/i);
  });

  it("keeps the practice path for a candidate who never applied, and labels it as such", async () => {
    renderPage();

    const practice = screen.getByTestId("practice-interview");
    // Closed by default: the exception is not the default path.
    expect(practice).not.toHaveAttribute("open");

    await userEvent.selectOptions(await jobSelect(), JOB_ID);
    await waitFor(() =>
      expect(screen.getByLabelText("Applicant")).not.toBeDisabled(),
    );

    const practiceButton = within(practice).getByRole("button", {
      name: /schedule practice interview/i,
    });
    // Still gated: a job and a candidate id are both required.
    expect(practiceButton).toBeDisabled();

    await userEvent.type(
      within(practice).getByLabelText("Candidate ID"),
      CANDIDATE_ID,
    );
    expect(practiceButton).not.toBeDisabled();

    vi.mocked(interviewApi.scheduleInterview).mockResolvedValue({
      message: "Interview scheduled successfully",
      interview_id: "int-2",
      status: "scheduled",
    } as never);

    await userEvent.click(practiceButton);
    await waitFor(() =>
      expect(interviewApi.scheduleInterview).toHaveBeenCalledWith(
        expect.objectContaining({
          job_id: JOB_ID,
          candidate_id: CANDIDATE_ID,
        }),
      ),
    );
  });

  it("reports an unreachable job list instead of rendering an empty picker", async () => {
    vi.mocked(recruiterJobApi.listJobs).mockRejectedValue(new Error("boom"));
    renderPage();
    // The fallback is shown, not the raw "boom" from the exception: a generic
    // failure is not something a recruiter can act on.
    await waitFor(() =>
      expect(
        screen.getByText(/could not load your jobs/i),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
  });

  it("still surfaces a message the server wrote for the user", async () => {
    vi.mocked(recruiterJobApi.listJobs).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "Your session has expired." } },
    });
    renderPage();
    expect(
      await screen.findByText("Your session has expired."),
    ).toBeInTheDocument();
  });
});
