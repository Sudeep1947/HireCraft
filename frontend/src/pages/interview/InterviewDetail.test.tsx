/**
 * Who may see which identifier on an interview.
 *
 * This page is reached by both roles, and the server has already narrowed the
 * rest of the payload per role. The identifier block has to narrow in the same
 * way: a candidate gets the references for their own record, and the account
 * identifiers of other people are staff-only.
 */

import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { interviewApi } from "../../api/interview";
import { InterviewDetailPage } from "./InterviewDetail";
import type { InterviewDetail } from "../../types/interview";

vi.mock("../../api/interview", () => ({
  interviewApi: {
    getInterviewDetail: vi.fn(),
  },
}));

const { authState } = vi.hoisted(() => ({
  authState: { roles: ["recruiter"] as string[] },
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "user-1", roles: authState.roles } }),
}));

const INTERVIEW_ID = "b3e9a517-2f84-4d0a-9c66-71a4e8d35b29";
const JOB_ID = "6b1d9f20-4c77-4a91-8f3e-2a5c0b7d1e66";
const APPLICATION_ID = "8f4c2b91-3d6e-4a58-b0f1-92c7e6d4a803";
const CANDIDATE_ID = "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44";
const RECRUITER_ID = "5c0d8b36-9a1e-4f27-8d63-0b7e2f4c19a5";

function interview(overrides: Partial<InterviewDetail> = {}): InterviewDetail {
  return {
    id: INTERVIEW_ID,
    job_id: JOB_ID,
    job_title: "Senior Backend Engineer",
    candidate_id: CANDIDATE_ID,
    candidate_name: "John Doe",
    candidate_email: "john@example.com",
    application_id: APPLICATION_ID,
    recruiter_id: RECRUITER_ID,
    recruiter_name: "Recruiter Person",
    interview_type: "scheduled",
    status: "scheduled",
    scheduled_at: "2026-01-05T14:00:00Z",
    started_at: null,
    completed_at: null,
    duration_minutes: 60,
    total_questions: 4,
    questions_answered: 0,
    questions: [],
    ...overrides,
  } as InterviewDetail;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/interviews/${INTERVIEW_ID}`]}>
      <Routes>
        <Route path="/interviews/:id" element={<InterviewDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function identifiers() {
  return within(await screen.findByTestId("interview-identifiers"));
}

describe("InterviewDetail identifiers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.roles = ["recruiter"];
    vi.mocked(interviewApi.getInterviewDetail).mockResolvedValue(interview());
  });

  it("gives staff every identifier on the record", async () => {
    renderPage();
    const block = await identifiers();

    for (const label of [
      "Interview ID",
      "Job ID",
      "Application ID",
      "Candidate ID",
      "Recruiter ID",
    ]) {
      expect(block.getByText(label, { selector: "label" })).toBeInTheDocument();
    }
    expect(block.getByTitle(INTERVIEW_ID)).toBeInTheDocument();
    expect(block.getByTitle(APPLICATION_ID)).toBeInTheDocument();
    expect(block.getByTitle(CANDIDATE_ID)).toBeInTheDocument();
  });

  it("gives an hr user the same view as a recruiter", async () => {
    authState.roles = ["hr"];
    renderPage();
    const block = await identifiers();
    expect(block.getByText("Candidate ID", { selector: "label" })).toBeInTheDocument();
    expect(block.getByText("Recruiter ID", { selector: "label" })).toBeInTheDocument();
  });

  it("withholds another person's account ids from the candidate", async () => {
    authState.roles = ["candidate"];
    renderPage();
    const block = await identifiers();

    // Their own record is quotable...
    expect(block.getByText("Interview ID", { selector: "label" })).toBeInTheDocument();
    expect(block.getByTitle(INTERVIEW_ID)).toBeInTheDocument();
    expect(block.getByTitle(APPLICATION_ID)).toBeInTheDocument();

    // ...but the identifiers are not printed on the page for them. The payload
    // still carries them, so this is a presentation rule, not a data rule.
    expect(
      block.queryByText("Candidate ID", { selector: "label" }),
    ).not.toBeInTheDocument();
    expect(
      block.queryByText("Recruiter ID", { selector: "label" }),
    ).not.toBeInTheDocument();
    expect(block.queryByTitle(CANDIDATE_ID)).not.toBeInTheDocument();
    expect(block.queryByTitle(RECRUITER_ID)).not.toBeInTheDocument();
  });

  it("omits the application id for a practice interview rather than showing a blank", async () => {
    vi.mocked(interviewApi.getInterviewDetail).mockResolvedValue(
      interview({ application_id: null, interview_type: "mock" }),
    );
    renderPage();
    const block = await identifiers();

    expect(
      block.queryByText("Application ID", { selector: "label" }),
    ).not.toBeInTheDocument();
    // The other identifiers are unaffected.
    expect(block.getByTitle(INTERVIEW_ID)).toBeInTheDocument();
  });

  it("treats an unknown role as a candidate, not as staff", async () => {
    // A role this build does not know about must not be granted the wider view
    // by default; the safe reading of an unrecognised role is the narrower one.
    authState.roles = ["some_future_role"];
    renderPage();
    const block = await identifiers();
    expect(
      block.queryByText("Candidate ID", { selector: "label" }),
    ).not.toBeInTheDocument();
  });

  it("still offers staff a way to copy an identifier", async () => {
    renderPage();
    const block = await identifiers();
    expect(
      block.getByRole("button", { name: /copy application id/i }),
    ).toBeInTheDocument();
  });
});
