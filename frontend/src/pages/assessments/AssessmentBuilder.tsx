import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { assessmentApi } from "../../api/assessment";
import { recruiterJobApi } from "../../api/jobs";
import { useToast } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/error";
import type { AssessmentSectionConfig } from "../../types/assessment";
import type { ApplicantDashboardItem, JobListItem } from "../../types/jobs";
import {
  JOB_ASSESSMENT_OUTCOME_COLORS,
  JOB_ASSESSMENT_OUTCOME_LABELS,
  JOB_ASSESSMENT_SKIP_LABELS,
  type JobAssessmentAssignResult,
} from "../../types/jobAssessment";

const QUESTION_TYPES: { value: string; label: string }[] = [
  { value: "mcq", label: "Technical MCQ" },
  { value: "aptitude_quantitative", label: "Quantitative Aptitude" },
  { value: "aptitude_logical", label: "Logical Reasoning" },
  { value: "aptitude_verbal", label: "Verbal Ability" },
  { value: "technical_theory", label: "CS Fundamentals" },
  { value: "code_output", label: "Code Output Prediction" },
  { value: "debugging", label: "Debugging" },
  { value: "sql_mcq", label: "SQL Theory" },
  { value: "sql_query", label: "SQL Query Writing" },
  { value: "coding", label: "Coding Challenge" },
  { value: "system_design", label: "System Design" },
  { value: "scenario", label: "Scenario" },
  { value: "case_study", label: "Case Study" },
  { value: "behavioral", label: "Behavioral" },
  { value: "situational_judgment", label: "Situational Judgment" },
];

const DIFFICULTIES = ["mixed", "easy", "medium", "hard", "expert"];

// One page of a job's applicants, matching the dashboard endpoint's cap. A
// recruiter building an assessment for more than this many applicants at once
// is a bulk import, which Phase 1 is deliberately not.
const APPLICANT_PAGE_SIZE = 100;

type BuilderTarget = "applicants" | "library";

interface SectionRow extends AssessmentSectionConfig {
  key: number;
}

let sectionKey = 0;
function newRow(type = "mcq"): SectionRow {
  sectionKey += 1;
  return { key: sectionKey, question_type: type, count: 5, difficulty: "mixed" };
}

export function AssessmentBuilder() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [title, setTitle] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(45);
  const [passingScore, setPassingScore] = useState(60);
  const [negativeMarking, setNegativeMarking] = useState(0);
  const [allowedAttempts, setAllowedAttempts] = useState(1);
  const [adaptive, setAdaptive] = useState(false);
  const [sections, setSections] = useState<SectionRow[]>([newRow()]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [createdId, setCreatedId] = useState<string | null>(null);

  // Phase 1: build-and-bulk-assign. The job is the scope and the ticked
  // applicants are the participant list; the survey of the form above is
  // authored once and assigned to all of them in one request.
  const [target, setTarget] = useState<BuilderTarget>("applicants");
  const [jobs, setJobs] = useState<JobListItem[] | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [jobId, setJobId] = useState("");
  const [applicants, setApplicants] = useState<ApplicantDashboardItem[] | null>(null);
  const [applicantsTotal, setApplicantsTotal] = useState(0);
  const [loadingApplicants, setLoadingApplicants] = useState(false);
  const [applicantsError, setApplicantsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [scheduledFor, setScheduledFor] = useState("");
  const [result, setResult] = useState<JobAssessmentAssignResult | null>(null);

  const updateRow = (key: number, patch: Partial<SectionRow>) =>
    setSections((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  useEffect(() => {
    let cancelled = false;
    recruiterJobApi
      .listJobs()
      .then((loaded) => {
        if (!cancelled) setJobs(loaded);
      })
      .catch((err) => {
        if (!cancelled) setJobsError(getErrorMessage(err, "Failed to load your jobs"));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!jobId) {
      setApplicants(null);
      setApplicantsTotal(0);
      setSelected(new Set());
      return;
    }
    let cancelled = false;
    setLoadingApplicants(true);
    setApplicantsError(null);
    setSelected(new Set());
    recruiterJobApi
      .getApplicantDashboard(jobId, {
        sort_by: "-created_at",
        page: 1,
        page_size: APPLICANT_PAGE_SIZE,
      })
      .then((dashboard) => {
        if (cancelled) return;
        setApplicants(dashboard.items);
        setApplicantsTotal(dashboard.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setApplicantsError(getErrorMessage(err, "Failed to load this job's applicants"));
        setApplicants(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingApplicants(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const selectedCount = selected.size;
  const allSelected = applicants !== null && applicants.length > 0 && selectedCount === applicants.length;

  const scheduledIso = useMemo(() => {
    if (!scheduledFor) return undefined;
    const parsed = new Date(scheduledFor);
    return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
  }, [scheduledFor]);

  function toggleApplicant(applicationId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(applicationId)) next.delete(applicationId);
      else next.add(applicationId);
      return next;
    });
  }

  function toggleAllApplicants() {
    if (!applicants) return;
    setSelected((prev) =>
      prev.size === applicants.length ? new Set() : new Set(applicants.map((a) => a.id)),
    );
  }

  function validate(): boolean {
    setError("");
    if (!title.trim() || title.trim().length < 3) {
      setError("Please provide a title (min 3 characters).");
      return false;
    }
    if (target === "applicants") {
      if (!jobId) {
        setError("Choose the job this assessment is for.");
        return false;
      }
      if (selectedCount === 0) {
        setError("Select at least one applicant to assign this assessment to.");
        return false;
      }
    }
    return true;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setBusy(true);
    try {
      if (target === "applicants") {
        const assigned = await recruiterJobApi.createAndAssignJobAssessment(jobId, {
          title: title.trim(),
          duration_minutes: durationMinutes,
          passing_score: passingScore,
          negative_marking: negativeMarking,
          allowed_attempts: allowedAttempts,
          adaptive,
          sections: sections.map(({ key: _key, ...cfg }) => cfg),
          ...(scheduledIso ? { scheduled_for: scheduledIso } : {}),
          application_ids: Array.from(selected),
        });
        setResult(assigned);
        const parts = [`${assigned.assigned_count} assigned`];
        if (assigned.already_assigned_count > 0) parts.push(`${assigned.already_assigned_count} already assigned`);
        if (assigned.skipped_count > 0) parts.push(`${assigned.skipped_count} skipped`);
        addToast(parts.join(" · "), assigned.assigned_count > 0 ? "success" : "info");
      } else {
        const created = await assessmentApi.generate({
          title: title.trim(),
          duration_minutes: durationMinutes,
          passing_score: passingScore,
          negative_marking: negativeMarking,
          allowed_attempts: allowedAttempts,
          adaptive,
          sections: sections.map(({ key: _key, ...cfg }) => cfg),
        });
        setCreatedId(created.id);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Generation failed - adjust the sections and try again."));
    } finally {
      setBusy(false);
    }
  }

  function resetAll() {
    setResult(null);
    setCreatedId(null);
    setSelected(new Set());
    setScheduledFor("");
  }

  if (createdId) {
    return (
      <div className="mx-auto max-w-xl rounded-xl border border-gray-200 bg-white p-8 text-center shadow-sm">
        <h2 className="text-xl font-bold text-gray-900">Assessment created</h2>
        <p className="mt-2 text-sm text-gray-500">
          Questions were generated, validated and published. Share the take link with candidates:
        </p>
        <code className="mt-3 block break-all rounded-lg bg-gray-50 p-3 text-xs text-gray-700">
          /candidate/assessments/take/{createdId}
        </code>
        <div className="mt-6 flex justify-center gap-3">
          <button
            onClick={() => navigate(`/recruiter/assessments/${createdId}/analytics`)}
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            View Analytics
          </button>
          <Link
            to="/recruiter/assessments"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Back to Library
          </Link>
        </div>
      </div>
    );
  }

  if (result) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-bold text-gray-900">Assessment assigned</h2>
          <p className="mt-1 text-sm text-gray-500">
            <span className="font-medium text-gray-700">{result.assessment_title}</span> was created and
            assigned for <span className="font-medium text-gray-700">{result.job_title}</span>. An
            assessment score is evidence you read before deciding; it never advances an application.
          </p>

          <div className="mt-4 flex flex-wrap gap-4 rounded-lg bg-gray-50 px-4 py-3 text-sm">
            <Summary label="Assigned" value={result.assigned_count} />
            <Summary label="Already assigned" value={result.already_assigned_count} />
            <Summary label="Skipped" value={result.skipped_count} />
            <Summary label="Requested" value={result.requested_count} />
          </div>

          <ul className="mt-4 divide-y divide-gray-100 rounded-lg border border-gray-200">
            {result.items.map((item) => (
              <li
                key={item.application_id}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-gray-900">
                    {item.candidate_name ?? "Unknown applicant"}
                  </p>
                  <p className="truncate text-xs text-gray-500">
                    {item.reason ? JOB_ASSESSMENT_SKIP_LABELS[item.reason] : item.message}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    JOB_ASSESSMENT_OUTCOME_COLORS[item.outcome] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {JOB_ASSESSMENT_OUTCOME_LABELS[item.outcome] ?? item.outcome}
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={resetAll}
              className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
            >
              Build another
            </button>
            <button
              onClick={() => navigate(`/recruiter/jobs/${result.job_id}/applicants`)}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              View applicants
            </button>
            <Link
              to="/recruiter/assessments"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Back to Library
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Assessment Builder</h1>
        <p className="mt-1 text-sm text-gray-500">
          Compose an assessment from AI-generated question sections, then publish it or assign it
          to a job&apos;s applicants.
        </p>
      </div>

      <div className="inline-flex rounded-lg border border-gray-200 p-0.5">
        <button
          type="button"
          onClick={() => setTarget("applicants")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${
            target === "applicants" ? "bg-primary-600 text-white" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          Assign to a job&apos;s applicants
        </button>
        <button
          type="button"
          onClick={() => setTarget("library")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${
            target === "library" ? "bg-primary-600 text-white" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          Publish to library
        </button>
      </div>

      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Basics</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="block md:col-span-3">
            <span className="mb-1 block text-sm font-medium text-gray-700">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Python Engineer Screen"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-gray-700">Duration (minutes)</span>
            <input type="number" min={5} max={480} value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-gray-700">Passing score (%)</span>
            <input type="number" min={0} max={100} value={passingScore}
              onChange={(e) => setPassingScore(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-gray-700">Negative marking</span>
            <input type="number" min={0} max={2} step={0.25} value={negativeMarking}
              onChange={(e) => setNegativeMarking(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-gray-700">Allowed attempts</span>
            <input type="number" min={1} max={10} value={allowedAttempts}
              onChange={(e) => setAllowedAttempts(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
          </label>
          <label className="flex items-center gap-2 pt-6">
            <input type="checkbox" checked={adaptive} onChange={(e) => setAdaptive(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300" />
            <span className="text-sm font-medium text-gray-700">Adaptive difficulty</span>
          </label>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Sections</h2>
        <div className="space-y-3">
          {sections.map((row) => (
            <div key={row.key} className="flex flex-wrap items-end gap-3 rounded-lg bg-gray-50 p-3">
              <label className="min-w-[220px] grow">
                <span className="mb-1 block text-xs font-medium text-gray-600">Question type</span>
                <select value={row.question_type}
                  onChange={(e) => updateRow(row.key, { question_type: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  {QUESTION_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
              <label className="w-24">
                <span className="mb-1 block text-xs font-medium text-gray-600">Count</span>
                <input type="number" min={1} max={50} value={row.count}
                  onChange={(e) => updateRow(row.key, { count: Number(e.target.value) })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              </label>
              <label className="w-32">
                <span className="mb-1 block text-xs font-medium text-gray-600">Difficulty</span>
                <select value={row.difficulty || "mixed"}
                  onChange={(e) => updateRow(row.key, { difficulty: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <button
                onClick={() => setSections((rows) => rows.filter((r) => r.key !== row.key))}
                disabled={sections.length === 1}
                className="rounded-lg px-3 py-2 text-sm text-red-500 hover:bg-red-50 disabled:cursor-not-allowed disabled:text-gray-300"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={() => setSections((rows) => [...rows, newRow()])}
          className="mt-3 rounded-lg border border-dashed border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:border-primary-400 hover:text-primary-600"
        >
          + Add section
        </button>
      </div>

      {target === "applicants" && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-gray-500">Assign to</h2>
          <p className="mb-4 text-xs text-gray-500">
            The job is the scope and the ticked applicants are the participants. Whoever is not yet
            eligible (or is already assigned) is reported per candidate, not silently dropped.
          </p>

          {jobsError ? (
            <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{jobsError}</p>
          ) : (
            <label className="block max-w-md">
              <span className="mb-1 block text-sm font-medium text-gray-700">Job</span>
              <select
                aria-label="Job"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Select a job…</option>
                {(jobs ?? []).map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title} · {job.application_count} applicant
                    {job.application_count === 1 ? "" : "s"}
                  </option>
                ))}
              </select>
            </label>
          )}

          {jobId && (
            <div className="mt-4">
              {loadingApplicants ? (
                <p className="text-sm text-gray-500">Loading applicants…</p>
              ) : applicantsError ? (
                <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{applicantsError}</p>
              ) : applicants && applicants.length === 0 ? (
                <p className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-600">
                  This job has no applicants yet.
                </p>
              ) : applicants ? (
                <>
                  <div className="mb-2 flex items-center justify-between">
                    <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                      <input
                        type="checkbox"
                        aria-label="Select all applicants"
                        checked={allSelected}
                        onChange={toggleAllApplicants}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      Select all
                    </label>
                    <span className="text-xs text-gray-500">
                      {selectedCount} of {applicants.length} selected
                      {applicantsTotal > applicants.length
                        ? ` (showing first ${applicants.length} of ${applicantsTotal})`
                        : ""}
                    </span>
                  </div>
                  <ul className="max-h-80 divide-y divide-gray-100 overflow-y-auto rounded-lg border border-gray-200">
                    {applicants.map((applicant) => (
                      <li key={applicant.id}>
                        <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-gray-50">
                          <input
                            type="checkbox"
                            aria-label={`Select ${applicant.candidate_name || "candidate"}`}
                            checked={selected.has(applicant.id)}
                            onChange={() => toggleApplicant(applicant.id)}
                            className="h-4 w-4 rounded border-gray-300"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-gray-900">
                              {applicant.candidate_name || "Unnamed candidate"}
                            </span>
                            <span className="block truncate text-xs text-gray-500">
                              {applicant.candidate_email || "No email on file"} ·{" "}
                              {applicant.status.replace(/_/g, " ")}
                            </span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>
          )}

          <label className="mt-4 block max-w-xs">
            <span className="mb-1 block text-sm font-medium text-gray-700">
              Scheduled date/time (optional)
            </span>
            <input
              type="datetime-local"
              value={scheduledFor}
              onChange={(e) => setScheduledFor(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <span className="mt-1 block text-xs text-gray-500">
              Leave empty to assign as waiting; set it and every selected candidate sees the same time.
            </span>
          </label>
        </div>
      )}

      <div className="flex justify-end gap-3">
        <Link
          to="/recruiter/assessments"
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </Link>
        <button
          onClick={handleSubmit}
          disabled={busy}
          className="rounded-lg bg-primary-600 px-5 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {busy
            ? "Generating..."
            : target === "applicants"
              ? `Generate & assign to ${selectedCount}`
              : "Generate & Publish"}
        </button>
      </div>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span className="text-gray-500">{label}</span>{" "}
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
