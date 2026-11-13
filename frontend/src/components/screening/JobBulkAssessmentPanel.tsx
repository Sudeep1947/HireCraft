/**
 * Phase 1 bulk assessment assignment panel.
 *
 * The batch counterpart of `ApplicationAssessmentPanel`. A recruiter who has
 * ticked several of a job's applicants in the applicant list opens this panel,
 * picks one assessment (existing, or authored here and scoped to this job) and
 * assigns it to everyone selected in one request.
 *
 * Three things are deliberate:
 *
 * 1. **The job is the scope, the selection is the participant list.** The panel
 *    only ever sends the job id and the application ids that were ticked; it
 *    never names a candidate. The server derives everyone and refuses a body that
 *    carries an identity field, so this UI cannot aim an assessment at anyone the
 *    recruiter did not select.
 * 2. **Partial success is reported, not hidden.** The response is per candidate:
 *    `assigned`, `already_assigned`, or `skipped` with a reason. A single
 *    ineligible applicant never fails the batch, and the panel renders exactly
 *    who got it and why the rest did not.
 * 3. **An assessment is evidence, not a verdict.** Assigning one never
 *    shortlists, rejects or ranks anyone; the copy below says so, and the
 *    decision panel on the applicant page stays the only thing that advances an
 *    application.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { recruiterJobApi } from "../../api/jobs";
import { useToast } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/error";
import { Button } from "../ui/Button";
import { ASSESSMENT_MODE_LABELS, type AssignableAssessment } from "../../types/applicationAssessment";
import type { AssessmentSectionConfig } from "../../types/assessment";
import {
  JOB_ASSESSMENT_OUTCOME_COLORS,
  JOB_ASSESSMENT_OUTCOME_LABELS,
  type JobAssessmentAssignResult,
  type JobAssessmentOptions,
} from "../../types/jobAssessment";

/** One ticked applicant, carried as a snapshot so a filter change cannot drop it. */
export interface BulkAssignSelection {
  applicationId: string;
  candidateName: string;
}

interface JobBulkAssessmentPanelProps {
  jobId: string;
  selection: BulkAssignSelection[];
  onClose: () => void;
  onAssigned?: (result: JobAssessmentAssignResult) => void;
}

type Mode = "existing" | "new";

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

interface SectionRow extends AssessmentSectionConfig {
  key: number;
}

let sectionKey = 0;
function newSection(type = "mcq"): SectionRow {
  sectionKey += 1;
  return { key: sectionKey, question_type: type, count: 5, difficulty: "mixed" };
}

function chips(selection: BulkAssignSelection[]): string {
  return selection.map((item) => item.candidateName).join(", ");
}

export function JobBulkAssessmentPanel({
  jobId,
  selection,
  onClose,
  onAssigned,
}: JobBulkAssessmentPanelProps) {
  const { addToast } = useToast();

  const [options, setOptions] = useState<JobAssessmentOptions | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("existing");
  const [selectedAssessmentId, setSelectedAssessmentId] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");

  // Create-and-assign form state.
  const [title, setTitle] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(45);
  const [passingScore, setPassingScore] = useState(60);
  const [negativeMarking, setNegativeMarking] = useState(0);
  const [allowedAttempts, setAllowedAttempts] = useState(1);
  const [sections, setSections] = useState<SectionRow[]>([newSection()]);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<JobAssessmentAssignResult | null>(null);

  const available = useMemo(
    () => (options?.available ?? []).filter((a: AssignableAssessment) => !a.already_assigned),
    [options],
  );

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true);
    setOptionsError(null);
    try {
      const loaded = await recruiterJobApi.getJobAssessmentOptions(jobId);
      setOptions(loaded);
      // Default to the first assignable row so the common case is one click,
      // while leaving the choice explicit.
      setSelectedAssessmentId((prev) => prev || loaded.available[0]?.assessment_id || "");
    } catch (err) {
      setOptionsError(getErrorMessage(err, "Failed to load assessments for this job"));
    } finally {
      setLoadingOptions(false);
    }
  }, [jobId]);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  const updateSection = (key: number, patch: Partial<SectionRow>) =>
    setSections((rows) => rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));

  const applicationIds = selection.map((item) => item.applicationId);
  const scheduledIso = scheduledFor ? new Date(scheduledFor).toISOString() : undefined;

  async function submit() {
    setSubmitError(null);
    if (applicationIds.length === 0) {
      setSubmitError("Select at least one applicant.");
      return;
    }
    if (mode === "existing" && !selectedAssessmentId) {
      setSubmitError("Choose an assessment to assign.");
      return;
    }
    if (mode === "new" && title.trim().length < 3) {
      setSubmitError("Give the new assessment a title of at least 3 characters.");
      return;
    }

    setSubmitting(true);
    try {
      const assigned =
        mode === "existing"
          ? await recruiterJobApi.assignJobAssessment(jobId, {
              assessment_id: selectedAssessmentId,
              application_ids: applicationIds,
              ...(scheduledIso ? { scheduled_for: scheduledIso } : {}),
            })
          : await recruiterJobApi.createAndAssignJobAssessment(jobId, {
              title: title.trim(),
              duration_minutes: durationMinutes,
              passing_score: passingScore,
              negative_marking: negativeMarking,
              allowed_attempts: allowedAttempts,
              sections: sections.map(({ key: _key, ...cfg }) => cfg),
              ...(scheduledIso ? { scheduled_for: scheduledIso } : {}),
              application_ids: applicationIds,
            });

      setResult(assigned);
      onAssigned?.(assigned);

      const parts = [`${assigned.assigned_count} assigned`];
      if (assigned.already_assigned_count > 0) {
        parts.push(`${assigned.already_assigned_count} already assigned`);
      }
      if (assigned.skipped_count > 0) {
        parts.push(`${assigned.skipped_count} skipped`);
      }
      addToast(parts.join(" · "), assigned.assigned_count > 0 ? "success" : "info");
    } catch (err) {
      setSubmitError(getErrorMessage(err, "Failed to assign the assessment."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card border-primary-200 p-6 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">
            Assign an assessment to {applicationIds.length}{" "}
            {applicationIds.length === 1 ? "applicant" : "applicants"}
          </h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            An assessment score is evidence you read before deciding. Assigning one
            never shortlists, rejects or ranks anyone — that stays your call.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} disabled={submitting}>
          Close
        </Button>
      </div>

      <p className="mt-3 rounded-md bg-gray-100 px-3 py-2 text-xs text-ink-muted">
        <span className="font-medium text-ink">Selected: </span>
        {chips(selection)}
      </p>

      {result ? (
        <AssignmentReport result={result} onClose={onClose} />
      ) : loadingOptions ? (
        <p className="mt-4 text-sm text-ink-muted">Loading assessments…</p>
      ) : optionsError ? (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3">
          <p className="text-sm text-rose-700">{optionsError}</p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => void loadOptions()}
          >
            Try again
          </Button>
        </div>
      ) : (
        <>
          <div className="mt-4 inline-flex rounded-lg border border-slate-200/70 p-0.5">
            <button
              type="button"
              onClick={() => setMode("existing")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                mode === "existing" ? "bg-primary-600 text-white" : "text-ink-muted hover:bg-gray-100"
              }`}
            >
              Use an existing assessment
            </button>
            <button
              type="button"
              onClick={() => setMode("new")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                mode === "new" ? "bg-primary-600 text-white" : "text-ink-muted hover:bg-gray-100"
              }`}
            >
              Create a new one
            </button>
          </div>

          {submitError && (
            <div className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-600">{submitError}</div>
          )}

          {mode === "existing" ? (
            <div className="mt-4">
              {available.length === 0 ? (
                <p className="rounded-md bg-gray-100 px-3 py-2 text-sm text-ink-muted">
                  No published assessments are available for this job yet. Use
                  &ldquo;Create a new one&rdquo; to author one now, or publish an
                  assessment in the library and it will appear here.
                </p>
              ) : (
                <>
                  <label
                    htmlFor="bulk-assessment-picker"
                    className="block text-xs font-semibold text-ink"
                  >
                    Assessment to assign
                  </label>
                  <select
                    id="bulk-assessment-picker"
                    value={selectedAssessmentId}
                    onChange={(e) => setSelectedAssessmentId(e.target.value)}
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    {available.map((assessment) => (
                      <option key={assessment.assessment_id} value={assessment.assessment_id}>
                        {assessment.title} · {assessment.duration_minutes} min ·{" "}
                        {assessment.question_count} questions
                      </option>
                    ))}
                  </select>

                  {(() => {
                    const chosen = available.find((a) => a.assessment_id === selectedAssessmentId);
                    if (!chosen) return null;
                    return (
                      <div className="mt-3 rounded-md bg-gray-100 p-3 text-sm">
                        {chosen.description ? (
                          <p className="text-ink">{chosen.description}</p>
                        ) : null}
                        <p className="mt-2 text-xs text-ink-muted">
                          {ASSESSMENT_MODE_LABELS[chosen.mode] ?? chosen.mode} ·{" "}
                          {chosen.duration_minutes} minutes · {chosen.question_count} questions ·
                          pass mark {chosen.passing_score}%{chosen.adaptive ? " · adaptive" : ""} ·{" "}
                          {chosen.allowed_attempts}{" "}
                          {chosen.allowed_attempts === 1 ? "attempt" : "attempts"} allowed
                        </p>
                        {chosen.skills.length > 0 ? (
                          <p className="mt-2 text-xs text-ink-muted">
                            Skills: {chosen.skills.join(", ")}
                          </p>
                        ) : null}
                      </div>
                    );
                  })()}
                </>
              )}
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="rounded-lg border border-slate-200/70 p-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <label className="block md:col-span-3">
                    <span className="mb-1 block text-sm font-medium text-ink">Title</span>
                    <input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. Senior Python Engineer Screen"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-ink">
                      Duration (minutes)
                    </span>
                    <input
                      type="number"
                      min={5}
                      max={480}
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-ink">
                      Passing score (%)
                    </span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={passingScore}
                      onChange={(e) => setPassingScore(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-ink">
                      Negative marking
                    </span>
                    <input
                      type="number"
                      min={0}
                      max={2}
                      step={0.25}
                      value={negativeMarking}
                      onChange={(e) => setNegativeMarking(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-ink">
                      Allowed attempts
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={allowedAttempts}
                      onChange={(e) => setAllowedAttempts(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </label>
                </div>
              </div>

              <div className="rounded-lg border border-slate-200/70 p-4">
                <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  Sections
                </h4>
                <div className="space-y-3">
                  {sections.map((row) => (
                    <div
                      key={row.key}
                      className="flex flex-wrap items-end gap-3 rounded-lg bg-gray-100 p-3"
                    >
                      <label className="min-w-[220px] grow">
                        <span className="mb-1 block text-xs font-medium text-ink-muted">
                          Question type
                        </span>
                        <select
                          value={row.question_type}
                          onChange={(e) => updateSection(row.key, { question_type: e.target.value })}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        >
                          {QUESTION_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="w-24">
                        <span className="mb-1 block text-xs font-medium text-ink-muted">Count</span>
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={row.count}
                          onChange={(e) => updateSection(row.key, { count: Number(e.target.value) })}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        />
                      </label>
                      <label className="w-32">
                        <span className="mb-1 block text-xs font-medium text-ink-muted">
                          Difficulty
                        </span>
                        <select
                          value={row.difficulty || "mixed"}
                          onChange={(e) => updateSection(row.key, { difficulty: e.target.value })}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        >
                          {DIFFICULTIES.map((d) => (
                            <option key={d} value={d}>
                              {d}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        onClick={() => setSections((rows) => rows.filter((r) => r.key !== row.key))}
                        disabled={sections.length === 1}
                        className="rounded-lg px-3 py-2 text-sm text-rose-500 hover:bg-rose-50 disabled:cursor-not-allowed disabled:text-ink-subtle"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setSections((rows) => [...rows, newSection()])}
                  className="mt-3 rounded-lg border border-dashed border-slate-300 px-4 py-2 text-sm font-medium text-ink-muted hover:border-primary-400 hover:text-primary-600"
                >
                  + Add section
                </button>
              </div>
            </div>
          )}

          <label
            htmlFor="bulk-assessment-scheduled-for"
            className="mt-4 block text-xs font-semibold text-ink"
          >
            Scheduled date/time (optional)
          </label>
          <input
            id="bulk-assessment-scheduled-for"
            type="datetime-local"
            value={scheduledFor}
            onChange={(e) => setScheduledFor(e.target.value)}
            className="mt-1 block w-full max-w-xs rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-ink-muted">
            Leave this empty and the assessment is assigned as waiting for each
            candidate. Set it and every selected candidate sees the same time.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => void submit()} isLoading={submitting} disabled={submitting}>
              {mode === "existing"
                ? `Assign to ${applicationIds.length}`
                : `Create & assign to ${applicationIds.length}`}
            </Button>
            <Button variant="ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/** The per-candidate outcome of a batch, so a partial success is never silent. */
function AssignmentReport({
  result,
  onClose,
}: {
  result: JobAssessmentAssignResult;
  onClose: () => void;
}) {
  return (
    <div className="mt-4">
      <div className="flex flex-wrap gap-4 rounded-lg bg-gray-100 px-4 py-3 text-sm">
        <Summary label="Assigned" value={result.assigned_count} />
        <Summary label="Already assigned" value={result.already_assigned_count} />
        <Summary label="Skipped" value={result.skipped_count} />
        <Summary label="Requested" value={result.requested_count} />
      </div>

      <p className="mt-2 text-xs text-ink-muted">
        {result.created_new_assessment ? "New assessment" : "Assessment"}:{" "}
        <span className="font-medium text-ink">{result.assessment_title}</span>
      </p>

      <ul className="mt-3 divide-y divide-slate-200/70 rounded-lg border border-slate-200/70">
        {result.items.map((item) => (
          <li
            key={item.application_id}
            className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">
                {item.candidate_name ?? "Unknown applicant"}
              </p>
              <p className="truncate text-xs text-ink-muted">{item.message}</p>
            </div>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                JOB_ASSESSMENT_OUTCOME_COLORS[item.outcome] ?? "bg-gray-100 text-ink"
              }`}
            >
              {JOB_ASSESSMENT_OUTCOME_LABELS[item.outcome] ?? item.outcome}
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex gap-2">
        <Button onClick={onClose}>Done</Button>
      </div>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span className="text-ink-muted">{label}</span>{" "}
      <span className="font-medium text-ink">{value}</span>
    </div>
  );
}

export default JobBulkAssessmentPanel;
