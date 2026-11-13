/**
 * Phase 12 candidate assessment card.
 *
 * Shows the assessment a recruiter assigned to one of the candidate's
 * applications, and the single action that applies to it right now: start it,
 * continue it, or read the result.
 *
 * Like the candidate interview section it sits beside, this component holds no
 * lifecycle logic of its own. `can_start`, `can_continue` and the wording all
 * come from `GET /assessments/applications/{id}/assessment`, so the client cannot
 * offer a start for an attempt the server would refuse, and it cannot show an
 * empty card that implies an assessment is waiting when none is.
 *
 * It links into the platform's existing assessment experience
 * (`/candidate/assessments/take/:assessmentId` and the result page) rather than
 * reimplementing question rendering, the timer, autosave, the coding environment
 * or integrity monitoring. The backend reuses the same attempt row for a
 * recruiter-assigned task, so the candidate's Start button works exactly as it
 * always did.
 *
 * What is shown is the server's allowlist, and nothing more: no recruiter
 * identity, no notes, no other candidates' results, no protected attributes, no
 * internal fairness math, and none of the platform's private
 * `recommendation`/`readiness_level` labels, which read as a hiring verdict.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applicationAssessmentApi } from "../../api/applicationAssessment";
import { getErrorMessage } from "../../utils/error";
import { Button } from "../ui/Button";
import {
  ATTEMPT_STATUS_LABELS,
  type AttemptStatus,
  type CandidateApplicationAssessmentView,
} from "../../types/applicationAssessment";

interface CandidateApplicationAssessmentCardProps {
  applicationId: string;
}

function formatDateTime(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function CandidateApplicationAssessmentCard({
  applicationId,
}: CandidateApplicationAssessmentCardProps) {
  const navigate = useNavigate();
  const [view, setView] = useState<CandidateApplicationAssessmentView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setView(await applicationAssessmentApi.getMyApplicationAssessment(applicationId));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load your assessment"));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    setLoading(true);
    setView(null);
    void load();
  }, [load]);

  if (loading) {
    return (
      <section
        className="rounded-[8px] border border-gray-200 bg-white p-4 shadow-xs"
        data-testid="candidate-assessment-loading"
        aria-busy="true"
      >
        <h2 className="text-sm font-semibold text-ink">Assessment</h2>
        <div className="skeleton mt-2 h-4 w-40" aria-hidden="true" />
        <p className="mt-1 text-sm text-ink-muted">Loading your assessment…</p>
      </section>
    );
  }

  // A failure here is worth surfacing rather than hiding: the candidate has been
  // told an assessment exists, so silently rendering nothing would leave them
  // with no way to reach it and no idea why.
  if (error || !view) {
    return (
      <section
        className="flex flex-col gap-0 rounded-[8px] border border-red-200 bg-red-50/90 p-4 shadow-xs"
        data-testid="candidate-assessment-error"
      >
        <h2 className="text-sm font-semibold text-red-900">Assessment</h2>
        <p className="mt-1 text-sm text-red-700">
          {error ?? "Your assessment could not be loaded."}
        </p>
        <Button
          variant="secondary"
          size="sm"
          className="rounded-[6px] mt-3 self-start"
          onClick={() => {
            setLoading(true);
            void load();
          }}
        >
          Try again
        </Button>
      </section>
    );
  }

  // Empty state: no assessment is assigned. Rendered as nothing rather than an
  // empty card, so an application that never received an assessment does not
  // imply one is waiting. The parent page decides whether this section appears.
  if (!view.has_assessment) {
    return (
      <section
        className="rounded-[8px] border border-gray-200 bg-white p-4 shadow-xs"
        data-testid="candidate-assessment-empty"
      >
        <h2 className="text-sm font-semibold text-ink">Assessment</h2>
        <p className="mt-1 text-sm text-ink-muted">No assessment assigned</p>
      </section>
    );
  }

  const status = view.status as AttemptStatus | null;
  const expiresAt = formatDateTime(view.expires_at);
  const submittedAt = formatDateTime(view.submitted_at);
  const scheduledAt = formatDateTime(view.scheduled_at);
  const isFinished = status === "completed" || status === "expired" || status === "abandoned";

  // One call to action, chosen by the server. A candidate who has finished is
  // sent to the result instead of a start button that would fail. Computed as a
  // plain route rather than a closure so the narrowed `view` stays narrowed.
  // A start uses the link the API returned so the page and any notification
  // point at the same place; a resume adds the attempt to the base link.
  const actionTarget: string | null =
    view.can_start && view.assessment_id
      ? (view.assessment_link ?? `/candidate/assessments/take/${view.assessment_id}`)
      : view.can_continue && view.assessment_id && view.attempt_id
        ? `/candidate/assessments/take/${view.assessment_id}?resume=${view.attempt_id}`
        : isFinished && view.attempt_id
          ? `/candidate/assessments/results/${view.attempt_id}`
          : null;

  const actionLabel = view.can_start
    ? "Start assessment"
    : view.can_continue
      ? "Continue assessment"
      : "View your result";

  return (
    <section
      className="rounded-[8px] border border-primary-200/70 bg-primary-50/30 p-5 shadow-xs"
      data-testid="candidate-assessment"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Your assessment</h2>
        {status ? (
          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-ink-muted ring-1 ring-primary-100">
            {ATTEMPT_STATUS_LABELS[status] ?? status.replace(/_/g, " ")}
          </span>
        ) : null}
      </div>

      {view.assessment_title ? (
        <p className="mt-1 text-sm font-medium text-ink">
          {view.assessment_title}
        </p>
      ) : null}

      {view.job_title ? (
        <p className="mt-0.5 text-xs text-ink-muted">For {view.job_title}</p>
      ) : null}

      {scheduledAt ? (
        <p className="mt-0.5 text-xs text-ink-muted">Scheduled {scheduledAt}</p>
      ) : null}

      <p className="mt-1 text-sm text-ink-muted">
        {view.message ?? "Your assessment details will appear here."}
      </p>

      {(expiresAt || submittedAt) && (
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {submittedAt ? (
            <div>
              <dt className="text-xs text-ink-subtle">Submitted</dt>
              <dd className="font-medium text-ink">{submittedAt}</dd>
            </div>
          ) : null}
          {expiresAt ? (
            <div>
              <dt className="text-xs text-ink-subtle">Time remaining until</dt>
              <dd className="font-medium text-ink">{expiresAt}</dd>
            </div>
          ) : null}
        </dl>
      )}

      {/* The authoritative score, once there is one. Null until the attempt is
          graded, and never rendered as a zero. */}
      {view.overall_score !== null && view.overall_score !== undefined ? (
        <div className="mt-3">
          <span className="text-xs text-ink-subtle">Your score</span>
          <span className="ml-2 font-display text-lg font-bold text-ink">
            {Math.round(view.overall_score)}%
          </span>
        </div>
      ) : null}

      {view.summary_text ? (
        <p className="mt-2.5 rounded-[6px] border border-primary-100 bg-white p-3 text-sm text-ink-muted">
          {view.summary_text}
        </p>
      ) : null}

      {view.strong_skills.length > 0 && (
        <div className="mt-3">
          <span className="text-xs text-ink-subtle">Strengths shown in this assessment</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {view.strong_skills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700 ring-1 ring-inset ring-emerald-200/60"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {view.recommended_topics.length > 0 && (
        <div className="mt-2">
          <span className="text-xs text-ink-subtle">Topics to practise</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {view.recommended_topics.map((topic) => (
              <span
                key={topic}
                className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-700 ring-1 ring-inset ring-amber-200/60"
              >
                {topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {actionTarget ? (
        <Button size="sm" className="rounded-[6px] mt-4" onClick={() => navigate(actionTarget)}>
          {actionLabel}
        </Button>
      ) : null}

      <p className="mt-3 text-xs text-ink-subtle">
        This assessment is part of the hiring process. It provides one piece of
        evidence for the team; the final decision is made by the hiring team.
      </p>
    </section>
  );
}

export default CandidateApplicationAssessmentCard;
