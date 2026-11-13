/**
 * Phase 12 recruiter assessment panel.
 *
 * Assigns an existing assessment to the selected application and shows the
 * assessment evidence recorded against it.
 *
 * Like the Phase 8 decision panel and the Phase 11 interview panel, this
 * component holds no rule table of its own. Which assessments may be assigned,
 * whether an assignment is possible at all, and why an action is unavailable all
 * come from `GET /assessments/applications/{id}/assessment/options`, so the rules
 * live only on the backend and a button the UI offers is an action the API will
 * accept. A disabled button is given the server's reason as its title rather than
 * being silently hidden, so a recruiter can tell "not available yet" from
 * "broken".
 *
 * An assessment result is evidence the recruiter reads *before* deciding. Nothing
 * here selects, rejects, shortlists or ranks the candidate: the decision panel
 * above stays the only thing that advances or ends an application. `passed` is the
 * assessment's own configured threshold, and the copy below says so wherever it
 * is rendered.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { applicationAssessmentApi } from "../../api/applicationAssessment";
import { useToast } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/error";
import { Button } from "../ui/Button";
import {
  ASSESSMENT_MODE_LABELS,
  ASSESSMENT_REASON_LABELS,
  ATTEMPT_STATUS_COLORS,
  ATTEMPT_STATUS_LABELS,
  type ApplicationAssessmentEvidence,
  type ApplicationAssessmentOptions,
  type AssessmentActionReason,
  type AttemptStatus,
} from "../../types/applicationAssessment";

interface ApplicationAssessmentPanelProps {
  applicationId: string;
}

function formatWhen(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function reasonText(
  reason: AssessmentActionReason | null,
): string | undefined {
  return reason ? ASSESSMENT_REASON_LABELS[reason] : undefined;
}

function statusLabel(status: AttemptStatus): string {
  return ATTEMPT_STATUS_LABELS[status] ?? status.replace(/_/g, " ");
}

/** Round a score for display without turning a null into a zero. */
function formatScore(score: number | null): string {
  if (score === null) return "Not graded";
  return `${Math.round(score)}%`;
}

export function ApplicationAssessmentPanel({
  applicationId,
}: ApplicationAssessmentPanelProps) {
  const { addToast } = useToast();
  const [options, setOptions] = useState<ApplicationAssessmentOptions | null>(null);
  const [evidence, setEvidence] = useState<ApplicationAssessmentEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      // Both are needed: the options say what may be done, the evidence says what
      // has happened. Fetched together so the panel is never rendered from one
      // without the other.
      const [loadedOptions, loadedEvidence] = await Promise.all([
        applicationAssessmentApi.getOptions(applicationId),
        applicationAssessmentApi.getEvidence(applicationId),
      ]);
      setOptions(loadedOptions);
      setEvidence(loadedEvidence);
    } catch (err) {
      setLoadError(getErrorMessage(err, "Failed to load assessment details"));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    setLoading(true);
    // Clear the previous applicant's evidence so a fast switch between two
    // applicants cannot briefly show one applicant's assessment for the other.
    setOptions(null);
    setEvidence(null);
    setAssigning(false);
    setSelectedAssessmentId("");
    void load();
  }, [load]);

  async function assign(assessmentId: string, key: string) {
    setPending(key);
    try {
      const result = await applicationAssessmentApi.assign(applicationId, {
        assessment_id: assessmentId,
        // Only present when a time was actually chosen, so a recruiter who does
        // not schedule sends exactly the body this panel has always sent.
        ...(scheduledFor
          ? { scheduled_for: new Date(scheduledFor).toISOString() }
          : {}),
      });
      // `already_assigned` is a normal outcome, not a failure: it is what a
      // double-click or a retried request returns, and the message already says
      // the assessment is assigned. Reporting it as success keeps a harmless
      // retry from looking like something went wrong.
      addToast(result.message, "success");
      setAssigning(false);
      setSelectedAssessmentId("");
      setScheduledFor("");
      await load();
    } catch (err) {
      addToast(getErrorMessage(err, "Failed to assign assessment"), "error");
      // Reload anyway: a 409 means our view of the state is stale, and leaving a
      // button enabled that the server just refused is worse than a round trip.
      await load();
    } finally {
      setPending(null);
    }
  }

  if (loading) {
    return (
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-ink">Assessment</h3>
        <div className="skeleton mt-3 h-4 w-1/3" />
        <div className="skeleton mt-2 h-4 w-1/2" />
        <p className="mt-3 text-sm text-ink-muted">Loading assessment details…</p>
      </div>
    );
  }

  if (loadError || !options) {
    return (
      <div className="error-banner flex-col items-start p-6">
        <h3 className="text-sm font-semibold text-red-900">Assessment</h3>
        <p className="mt-2 text-sm text-red-700">{loadError}</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => {
            setLoading(true);
            void load();
          }}
        >
          Try again
        </Button>
      </div>
    );
  }

  // Only entries that are not already live on this application are offered. The
  // server marks the live ones `already_assigned` and keeps them visible so the
  // recruiter can see the full picture, but offering them again would be offering
  // a duplicate.
  const assignable = options.available.filter((a) => !a.already_assigned);
  const busy = pending !== null;
  const actionByAttempt = new Map(
    options.actions.map((a) => [a.attempt_id, a]),
  );

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">Assessment</h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            An assessment score is evidence you read before deciding. It never
            shortlists or rejects on its own — the decision above stays yours.
          </p>
        </div>
        <span className="badge-neutral">
          {options.current_status.replace(/_/g, " ")}
        </span>
      </div>

      {/* Assignment */}
      <div className="mt-4">
        {options.can_assign ? (
          <>
            {!assigning ? (
              <Button
                onClick={() => {
                  setAssigning(true);
                  // Default to the first genuinely assignable row so the common
                  // case is one click, while leaving the choice explicit.
                  setSelectedAssessmentId(assignable[0]?.assessment_id ?? "");
                }}
              >
                Assign assessment
              </Button>
            ) : assignable.length === 0 ? (
              <p className="rounded-md bg-gray-100 px-3 py-2 text-sm text-ink-muted">
                No published assessments are available for this job yet. Publish an
                assessment and it will appear here.
              </p>
            ) : (
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                <label htmlFor="assessment-picker" className="field-label">
                  Assessment to assign
                </label>
                <select
                  id="assessment-picker"
                  value={selectedAssessmentId}
                  onChange={(e) => setSelectedAssessmentId(e.target.value)}
                  className="field"
                >
                  {assignable.map((assessment) => (
                    <option key={assessment.assessment_id} value={assessment.assessment_id}>
                      {assessment.title} · {assessment.duration_minutes} min ·{" "}
                      {assessment.question_count} questions
                    </option>
                  ))}
                </select>

                <label
                  htmlFor="assessment-scheduled-for"
                  className="field-label mt-3"
                >
                  Scheduled date/time (optional)
                </label>
                <input
                  id="assessment-scheduled-for"
                  type="datetime-local"
                  value={scheduledFor}
                  onChange={(e) => setScheduledFor(e.target.value)}
                  className="field"
                />
                <p className="mt-1 text-xs text-ink-muted">
                  Leave this empty and the assessment is assigned as waiting for the
                  candidate. Set it and the candidate sees the time you chose.
                </p>

                {/* Real metadata from the assessment row, so the recruiter is
                    choosing from what the assessment actually contains. */}
                {(() => {
                  const chosen = assignable.find(
                    (a) => a.assessment_id === selectedAssessmentId,
                  );
                  if (!chosen) return null;
                  return (
                    <div
                      className="mt-3 rounded-xl border border-gray-200 bg-white p-3 text-sm"
                      data-testid="assessment-preview"
                    >
                      {chosen.description ? (
                        <p className="text-ink">{chosen.description}</p>
                      ) : null}
                      <p className="mt-2 text-xs text-ink-muted">
                        {ASSESSMENT_MODE_LABELS[chosen.mode] ?? chosen.mode} ·{" "}
                        {chosen.duration_minutes} minutes ·{" "}
                        {chosen.question_count} questions · pass mark{" "}
                        {chosen.passing_score}%
                        {chosen.adaptive ? " · adaptive" : ""} ·{" "}
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

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    onClick={() =>
                      void assign(
                        selectedAssessmentId,
                        `assign:${selectedAssessmentId}`,
                      )
                    }
                    disabled={!selectedAssessmentId || busy}
                  >
                    {pending === `assign:${selectedAssessmentId}`
                      ? "Assigning…"
                      : "Confirm assignment"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setAssigning(false)}
                    disabled={busy}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="mt-4 rounded-xl bg-gray-100 px-3 py-2 text-sm text-ink-muted">
            {reasonText(options.assign_unavailable_reason) ??
              "An assessment cannot be assigned to this application."}
          </p>
        )}
      </div>

      {/* Evidence summary */}
      {evidence && evidence.attempt_count > 0 && (
        <div className="mt-4 flex flex-wrap gap-4 border-t border-gray-200 pt-4 text-sm">
          <div>
            <span className="text-ink-muted">Attempts</span>{" "}
            <span className="font-medium text-ink">
              {evidence.attempt_count}
            </span>
          </div>
          <div>
            <span className="text-ink-muted">Completed</span>{" "}
            <span className="font-medium text-ink">
              {evidence.completed_count}
            </span>
          </div>
          <div>
            <span className="text-ink-muted">Average score</span>{" "}
            <span className="font-medium text-ink">
              {evidence.average_overall_score !== null
                ? `${Math.round(evidence.average_overall_score)}%`
                : "—"}
            </span>
          </div>
        </div>
      )}

      {/* Attempts */}
      {evidence && evidence.attempts.length > 0 && (
        <ul className="mt-4 space-y-3">
          {evidence.attempts.map((attempt) => {
            const action = actionByAttempt.get(attempt.attempt_id);
            const assignedAt = formatWhen(attempt.scheduled_for_hint);
            const completedAt = formatWhen(attempt.completed_at);
            return (
              <li
                key={attempt.attempt_id}
                className="rounded-xl border border-gray-200 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      data-testid={`attempt-status-${attempt.attempt_id}`}
                      className={`badge ${ATTEMPT_STATUS_COLORS[attempt.status] ?? "badge-neutral"}`}
                    >
                      {statusLabel(attempt.status)}
                    </span>
                    <span className="text-sm font-medium text-ink">
                      {attempt.assessment_title}
                    </span>
                    <span className="text-xs text-ink-muted">
                      Attempt {attempt.attempt_number} ·{" "}
                      {ASSESSMENT_MODE_LABELS[attempt.mode] ?? attempt.mode}
                    </span>
                  </div>
                  <span className="text-sm text-ink">
                    Score{" "}
                    <span
                      className={`font-medium ${
                        attempt.overall_score === null
                          ? "text-ink-muted"
                          : "text-ink"
                      }`}
                    >
                      {formatScore(attempt.overall_score)}
                    </span>
                  </span>
                </div>

                <p className="mt-1 text-xs text-ink-muted">
                  {attempt.questions_answered}/{attempt.questions_total} answered
                  {assignedAt ? <> · assigned {assignedAt}</> : null}
                  {completedAt ? <> · completed {completedAt}</> : null}
                </p>

                {/* The pass mark is the assessment's own threshold. Labelled as
                    such, so a green "passed" cannot be misread as a hiring
                    signal. The threshold is required for the sentence to read
                    correctly, so an attempt graded without a recorded threshold
                    says nothing rather than printing a hole in the copy. */}
                {attempt.passed !== null && attempt.passed_threshold !== null ? (
                  <p className="mt-1 text-xs text-ink-muted">
                    {attempt.passed ? "Above" : "Below"} this assessment&apos;s pass
                    mark of {attempt.passed_threshold}%.
                  </p>
                ) : null}

                {attempt.summary_text ? (
                  <p className="mt-2 rounded-md bg-sky-50 p-2 text-xs text-sky-800">
                    {attempt.summary_text}
                  </p>
                ) : null}

                {attempt.section_scores.length > 0 ? (
                  <dl
                    className="mt-2 grid gap-1 text-xs sm:grid-cols-2"
                    data-testid="assessment-section-scores"
                  >
                    {attempt.section_scores.map((section, index) => {
                      const label =
                        section.section ?? section.question_type ?? "Section";
                      return (
                        <div key={`${label}-${index}`} className="flex justify-between">
                          <dt className="text-ink-muted">{label}</dt>
                          <dd className="font-medium text-ink">
                            {typeof section.percentage === "number"
                              ? `${Math.round(section.percentage)}%`
                              : "—"}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                ) : null}

                {(attempt.strong_skills.length > 0 ||
                  attempt.weak_skills.length > 0) && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {attempt.strong_skills.map((skill) => (
                      <span key={`strong-${skill}`} className="badge-success">
                        {skill}
                      </span>
                    ))}
                    {attempt.weak_skills.map((skill) => (
                      <span key={`weak-${skill}`} className="badge-warning">
                        {skill}
                      </span>
                    ))}
                  </div>
                )}

                {attempt.integrity_flag_count > 0 && (
                  <p className="mt-2 text-xs text-amber-700">
                    {attempt.integrity_flag_count} integrity{" "}
                    {attempt.integrity_flag_count === 1 ? "event" : "events"}{" "}
                    recorded. Open the detailed result to review them.
                  </p>
                )}

                <div className="mt-2 flex flex-wrap gap-2">
                  {attempt.status === "completed" && attempt.overall_score !== null ? (
                    <Link
                      to={`/recruiter/assessments/results/${attempt.attempt_id}`}
                      className="chip"
                    >
                      View detailed result
                    </Link>
                  ) : null}
                  {action?.can_reassign ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        void assign(
                          attempt.assessment_id,
                          `reassign:${attempt.attempt_id}`,
                        )
                      }
                    >
                      {pending === `reassign:${attempt.attempt_id}`
                        ? "Assigning…"
                        : "Assign a retake"}
                    </Button>
                  ) : action ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled
                      title={reasonText(action.reassign_unavailable_reason)}
                    >
                      Assign a retake
                    </Button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {evidence && evidence.attempt_count === 0 && (
        <p className="mt-4 text-sm text-ink-muted">
          No assessment assigned to this application yet.
        </p>
      )}
    </div>
  );
}

export default ApplicationAssessmentPanel;
