/**
 * Recruiter interview scheduling.
 *
 * The recruiter picks a **job**, then an **applicant** on that job, and
 * schedules. The candidate and the application are resolved from the applicant
 * the recruiter selected -- the form never asks for an identifier, and the
 * request is keyed by application id.
 *
 * This is a deliberate change from the previous version of this page, which had
 * a required "Candidate ID *" text box with the placeholder "Enter candidate
 * UUID" and posted to `POST /interview/schedule`. That flow made a recruiter
 * leave the hiring workflow, find a UUID in a URL or the database, and paste it
 * back in, with no verification that it belonged to the candidate they had in
 * mind. Scheduling through the application instead:
 *
 * - takes the identity from the application the recruiter actually clicked, so
 *   the interview cannot land on a different candidate;
 * - is authorized server-side against that application, so another
 *   organization's application is refused even if its id is known;
 * - and moves the application through the recorded lifecycle, so the status the
 *   candidate sees changes with it.
 *
 * The endpoint the old form used is left in place and still reachable, for the
 * one case it exists to serve: a practice interview for a candidate who has not
 * applied. That is behind a collapsed, explicitly labelled section rather than
 * being the default, because it is the exception, not the workflow.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { recruiterJobApi } from "../../api/jobs";
import { interviewApi } from "../../api/interview";
import { ApplicationIdentityCard } from "../../components/ui/ApplicationIdentityCard";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useToast } from "../../contexts/ToastContext";
import { getServerErrorMessage } from "../../utils/error";
import type { JobApplication } from "../../types/jobs";

const STATUS_LABELS: Record<string, string> = {
  applied: "Applied",
  under_review: "Under review",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview scheduled",
  interviewed: "Interviewed",
  offered: "Offered",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const ALL_CATEGORIES = [
  "technical",
  "behavioral",
  "hr",
  "situational",
  "coding",
  "system_design",
  "problem_solving",
];

/**
 * Default slot: tomorrow, an hour from now, truncated to the hour.
 *
 * `datetime-local` wants "YYYY-MM-DDTHH:mm" in local time, so this is built
 * from the local getters rather than from an ISO instant.
 */
function defaultSlot(): string {
  const when = new Date();
  when.setDate(when.getDate() + 1);
  when.setHours(when.getHours() + 1, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}T${pad(when.getHours())}:${pad(when.getMinutes())}`;
}

/** Null for an empty or unparseable value, so an empty form never posts "Invalid Date". */
function slotToIso(slot: string): string | null {
  if (!slot) return null;
  const parsed = new Date(slot);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function statusLabel(status: string | undefined): string {
  if (!status) return "";
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ");
}

export function InterviewSchedule() {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [jobs, setJobs] = useState<{ id: string; title: string }[]>([]);
  const [jobId, setJobId] = useState("");
  const [applicants, setApplicants] = useState<JobApplication[]>([]);
  const [applicationId, setApplicationId] = useState("");
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingApplicants, setLoadingApplicants] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [slot, setSlot] = useState(defaultSlot);
  const [duration, setDuration] = useState(60);
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState("medium");
  const [categories, setCategories] = useState<string[]>(["technical", "behavioral"]);

  // The practice-interview path, behind a collapsed <details> so it is neither
  // the default nor something a recruiter can hit by accident. See the module
  // note. The candidate id field is the only identifier entry left on this page,
  // and it is only reachable for a candidate who never applied.
  const [practiceCandidateId, setPracticeCandidateId] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await recruiterJobApi.listJobs();
        if (!active) return;
        setJobs(
          (result ?? []).map((j) => ({ id: j.id, title: j.title })),
        );
      } catch (err) {
        if (!active) return;
        setLoadError(
          getServerErrorMessage(err, "Could not load your jobs. Please try again."),
        );
      } finally {
        if (active) setLoadingJobs(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Applicants are loaded per job. A recruiter never needs a candidate list
  // for a job they cannot see, and the server scopes the response to jobs they
  // own or share through their organization.
  useEffect(() => {
    let active = true;
    if (!jobId) {
      setApplicants([]);
      setApplicationId("");
      setLoadingApplicants(false);
      return;
    }
    setLoadingApplicants(true);
    (async () => {
      try {
        const rows = await recruiterJobApi.getApplications(jobId);
        if (!active) return;
        setApplicants(rows ?? []);
        setApplicationId("");
      } catch (err) {
        if (!active) return;
        setApplicants([]);
        setLoadError(
          getServerErrorMessage(
            err,
            "Could not load the applicants for this job. Please try again.",
          ),
        );
      } finally {
        if (active) setLoadingApplicants(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [jobId]);

  const selectedJob = useMemo(
    () => jobs.find((j) => j.id === jobId) ?? null,
    [jobs, jobId],
  );
  const selectedApplication = useMemo(
    () => applicants.find((a) => a.id === applicationId) ?? null,
    [applicants, applicationId],
  );

  const toggleCategory = (category: string) => {
    setCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category],
    );
  };

  async function schedule() {
    if (!selectedApplication) {
      addToast(
        "Select an applicant before scheduling. The candidate and application are taken from that selection.",
        "error",
      );
      return;
    }
    const iso = slotToIso(slot);
    if (!iso) {
      addToast("Choose a valid date and time", "error");
      return;
    }
    setSubmitting(true);
    try {
      // Keyed by application id only. The server derives the job, the candidate
      // and the organization from it, so there is nothing here to get wrong.
      const result = await interviewApi.scheduleApplicationInterview(
        selectedApplication.id,
        {
          scheduled_at: iso,
          duration_minutes: duration,
          question_count: questionCount,
          difficulty,
          categories,
        },
      );
      addToast(result.message || "Interview scheduled", "success");
      navigate("/recruiter/interviews");
    } catch (err) {
      addToast(
        getServerErrorMessage(
          err,
          "Unable to schedule the interview because the candidate and application could not be loaded. Please refresh and try again.",
        ),
        "error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function schedulePractice() {
    if (!jobId || !practiceCandidateId.trim()) {
      addToast("Choose a job and enter the candidate's ID", "error");
      return;
    }
    const iso = slotToIso(slot);
    if (!iso) {
      addToast("Choose a valid date and time", "error");
      return;
    }
    setSubmitting(true);
    try {
      await interviewApi.scheduleInterview({
        job_id: jobId,
        candidate_id: practiceCandidateId.trim(),
        scheduled_at: iso,
        duration_minutes: duration,
        question_count: questionCount,
        difficulty,
        categories,
      });
      addToast("Practice interview scheduled", "success");
      navigate("/recruiter/interviews");
    } catch (err) {
      addToast(
        getServerErrorMessage(
          err,
          "Unable to schedule the practice interview. Check the candidate ID and try again.",
        ),
        "error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <button
          onClick={() => navigate(-1)}
          className="mb-2 text-sm text-primary-600 hover:text-primary-700"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Schedule interview</h1>
        <p className="mt-1 text-sm text-gray-500">
          Pick the job, then the applicant. The candidate and application are
          taken from the applicant you select, so there is no ID to look up.
        </p>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {loadError}
        </div>
      ) : null}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void schedule();
        }}
        className="space-y-5 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
      >
        {/* Step 1 — the job */}
        <div className="space-y-1">
          <label
            htmlFor="schedule-job"
            className="block text-sm font-medium text-gray-700"
          >
            Job
          </label>
          <select
            id="schedule-job"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            disabled={loadingJobs}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
          >
            <option value="">
              {loadingJobs ? "Loading jobs…" : "Select a job"}
            </option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        </div>

        {/* Step 2 — the applicant, chosen by person, not by identifier */}
        <div className="space-y-1">
          <label
            htmlFor="schedule-applicant"
            className="block text-sm font-medium text-gray-700"
          >
            Applicant
          </label>
          <select
            id="schedule-applicant"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
            disabled={!jobId || loadingApplicants}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none disabled:bg-gray-50"
          >
            <option value="">
              {!jobId
                ? "Select a job first"
                : loadingApplicants
                  ? "Loading applicants…"
                  : applicants.length === 0
                    ? "No applicants on this job"
                    : "Select an applicant"}
            </option>
            {applicants.map((applicant) => (
              <option key={applicant.id} value={applicant.id}>
                {applicant.candidate_name || "Unnamed candidate"}
                {applicant.candidate_email ? ` · ${applicant.candidate_email}` : ""}
                {` — ${statusLabel(applicant.status)}`}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">
            Applicants are the people who applied to this job. Their candidate
            and application IDs are shown below once one is selected.
          </p>
        </div>

        {/* The identifiers, labelled and copyable, so nothing has to be hunted
            down in a URL or the database to answer a question or pass one on. */}
        {selectedApplication ? (
          <ApplicationIdentityCard
            candidateName={
              selectedApplication.candidate_name || "Unnamed candidate"
            }
            candidateEmail={selectedApplication.candidate_email}
            candidateId={selectedApplication.candidate_id}
            applicationId={selectedApplication.id}
            jobTitle={selectedApplication.job_title || selectedJob?.title}
            jobId={selectedApplication.job_id || jobId}
            applicationStatus={selectedApplication.status}
          />
        ) : null}

        {/* Step 3 — the interview itself */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <label
              htmlFor="schedule-slot"
              className="block text-sm font-medium text-gray-700"
            >
              Date &amp; time
            </label>
            <input
              id="schedule-slot"
              type="datetime-local"
              value={slot}
              onChange={(e) => setSlot(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            />
          </div>
          <Input
            id="schedule-duration"
            label="Duration (minutes)"
            type="number"
            min={15}
            max={180}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value) || 60)}
          />
          <Input
            id="schedule-questions"
            label="Questions"
            type="number"
            min={1}
            max={50}
            value={questionCount}
            onChange={(e) => setQuestionCount(Number(e.target.value) || 10)}
          />
          <div className="space-y-1">
            <label
              htmlFor="schedule-difficulty"
              className="block text-sm font-medium text-gray-700"
            >
              Difficulty
            </label>
            <select
              id="schedule-difficulty"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
              <option value="mixed">Mixed</option>
            </select>
          </div>
        </div>

        <div>
          <span className="block text-sm font-medium text-gray-700">
            Categories
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {ALL_CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => toggleCategory(category)}
                aria-pressed={categories.includes(category)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  categories.includes(category)
                    ? "bg-primary-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {category.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>

        <Button
          type="submit"
          isLoading={submitting}
          disabled={!selectedApplication}
          className="w-full"
        >
          {submitting ? "Scheduling…" : "Schedule interview"}
        </Button>
        {!selectedApplication ? (
          <p className="text-center text-xs text-gray-500">
            Select an applicant to enable scheduling.
          </p>
        ) : null}
      </form>

      {/* The exception, kept but out of the way. The legacy endpoint takes a
          candidate id because it can schedule for someone who never applied;
          that is only meaningful for a practice interview, so it is labelled as
          one and is not the default path. */}
      <details
        className="rounded-xl border border-gray-200 bg-white p-4"
        data-testid="practice-interview"
      >
        <summary className="cursor-pointer text-sm font-semibold text-gray-800">
          Practice interview for a candidate who has not applied
        </summary>
        <div className="mt-3 space-y-3">
          <p className="text-xs text-gray-500">
            A practice interview is not tied to an application, so it is
            scheduled directly against the candidate's account ID. For anyone who
            has applied to your job, use the applicant picker above instead —
            it carries the candidate and application through automatically.
          </p>
          <Input
            id="practice-candidate-id"
            label="Candidate ID"
            value={practiceCandidateId}
            onChange={(e) => setPracticeCandidateId(e.target.value)}
            placeholder="The candidate's account UUID"
          />
          <Button
            type="button"
            variant="secondary"
            isLoading={submitting}
            disabled={!jobId || !practiceCandidateId.trim()}
            onClick={() => void schedulePractice()}
          >
            Schedule practice interview
          </Button>
        </div>
      </details>
    </div>
  );
}

export default InterviewSchedule;
