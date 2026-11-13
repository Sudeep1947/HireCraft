/**
 * Phase 9 candidate application detail.
 *
 * Everything rendered here is the candidate-safe tracking projection the server
 * builds from the application row and its immutable status history: the progress
 * stages the application actually reached, the real timeline of status changes,
 * and the same reviewed decision wording the decision endpoint returns.
 *
 * The page deliberately holds no lifecycle logic. It does not compute which
 * stages exist, which come next, or whether the application can be withdrawn --
 * `stages`, `timeline` and `can_withdraw` all come from the API, so the client
 * cannot disagree with the server about the application's state.
 */

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { IdentifierGrid } from "../../components/ui/IdentifierField";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { CandidateApplicationAssessmentCard } from "../../components/candidate/CandidateApplicationAssessmentCard";
import { InterviewRoomPanel } from "../../components/interview/InterviewRoomPanel";
import { useToast } from "../../contexts/ToastContext";
import { candidateJobApi } from "../../api/jobs";
import { getErrorMessage } from "../../utils/error";
import { formatDate as utilsFormatDate } from "../../utils/dateTime";
import type { CandidateApplicationTrack } from "../../types/jobs";

const SCREENING_LABELS: Record<string, string> = {
  not_started: "Not started",
  queued: "Queued",
  running: "In progress",
  completed: "Complete",
  failed: "Could not run",
  skipped: "Skipped",
};

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const res = utilsFormatDate(value, "");
  return res || null;
}

function stageClasses(stage: CandidateApplicationTrack["stages"][number]): string {
  if (stage.is_current) return "border-indigo-500 bg-indigo-50 text-indigo-800";
  if (stage.reached) return "border-emerald-300 bg-emerald-50 text-emerald-800";
  return "border-gray-200 bg-gray-50 text-gray-500";
}

const INTERVIEW_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function CandidateApplicationDetail() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [track, setTrack] = useState<CandidateApplicationTrack | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);

  const load = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError(null);
    setUnavailable(null);
    try {
      setTrack(await candidateJobApi.getMyApplicationTrack(applicationId));
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        // A 404 covers both "no such application" and "not yours"; the server
        // answers identically, so the page cannot be used to probe ids.
        setUnavailable("This application does not exist or is not available for your account.");
      } else {
        setError(getErrorMessage(err, "Failed to load this application."));
      }
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleWithdraw() {
    if (!track || !window.confirm("Withdraw this application?")) return;
    setWithdrawing(true);
    try {
      await candidateJobApi.withdrawApplication(track.application_id);
      addToast("Application withdrawn", "success");
      // Re-read the tracking view so the stage list, timeline and decision all
      // come from the server rather than being patched locally.
      await load();
    } catch {
      addToast("Failed to withdraw application", "error");
    } finally {
      setWithdrawing(false);
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  if (unavailable) {
    return (
      <div className="mx-auto max-w-2xl animate-fade-up py-12">
        <div className="flex flex-col items-center justify-center rounded-[8px] border border-gray-200 bg-white p-8 text-center shadow-xs">
          <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">
            Application unavailable
          </p>
          <p className="mt-2 text-sm text-gray-700">{unavailable}</p>
          <Button variant="secondary" className="rounded-[6px] mt-5" onClick={() => navigate("/candidate/applications")}>
            Back to my applications
          </Button>
        </div>
      </div>
    );
  }

  if (error || !track) {
    return (
      <div className="mx-auto max-w-2xl animate-fade-up py-12">
        <div className="flex flex-col items-center gap-3 rounded-[8px] border border-red-200 bg-red-50/90 p-8 text-center shadow-xs">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Could not load this application
          </p>
          <p className="text-sm text-red-700">
            {error || "An unexpected error occurred while loading this application."}
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="secondary" className="rounded-[6px]" onClick={() => void load()}>
              Try again
            </Button>
            <Button variant="ghost" className="rounded-[6px]" onClick={() => navigate("/candidate/applications")}>
              Back to my applications
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const appliedDate = formatDate(track.applied_at);
  const lastChangeDate = formatDate(track.last_status_change_at);
  const screeningLabel = SCREENING_LABELS[track.screening_status] ?? track.screening_status;

  return (
    <div className="animate-fade-up space-y-6">
      <div>
        <Link
          to="/candidate/applications"
          className="text-xs font-medium text-indigo-600 hover:underline"
        >
          &larr; Back to my applications
        </Link>
        <div className="mt-1 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="page-title">
              {track.job_title || "Position no longer listed"}
            </h1>
            <p className="text-sm text-gray-500">
              {[track.company, track.location].filter(Boolean).join(" · ")}
            </p>
            <p className="mt-1 text-xs text-gray-400">
              {appliedDate ? `Applied ${appliedDate}` : "Application date unavailable"}
              {lastChangeDate ? ` · Last update ${lastChangeDate}` : ""}
            </p>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <span className="badge-neutral">
              {track.status_label}
            </span>
            {track.can_withdraw ? (
              <Button
                variant="danger"
                size="sm"
                className="rounded-[6px]"
                isLoading={withdrawing}
                onClick={() => void handleWithdraw()}
              >
                Withdraw
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      {track.is_decision_final ? (
        <p className="rounded-[6px] border border-gray-200 bg-gray-50/80 px-3.5 py-2 text-xs text-gray-600">
          This application has reached a final outcome and is no longer changing.
        </p>
      ) : null}

      {/* The approved decision wording, identical to the one the decision
          endpoint and the candidate notification carry. */}
      {track.decision?.candidate_message ? (
        <section className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs">
          <h2 className="section-title">Where things stand</h2>
          <p className="mt-1 text-sm text-gray-700">{track.decision.candidate_message}</p>
          {formatDate(track.decision.decided_at) ? (
            <p className="mt-1 text-xs text-gray-500">
              Recorded {formatDate(track.decision.decided_at)}
            </p>
          ) : null}
        </section>
      ) : null}

      {/* This application's reference, so the candidate can quote it when they
          contact the hiring team. It is their own record, so it carries nothing
          the candidate could not already see on this page. The candidate's own
          account ID is not shown here: this page is about one application, and
          the account identifier lives with the profile, where a candidate looks
          for it when they need to identify themselves rather than a specific
          application. */}
      <section
        className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs"
        data-testid="candidate-application-identifiers"
      >
        <h2 className="section-title">References</h2>
        <IdentifierGrid
          className="mt-2"
          columns={2}
          items={[
            {
              label: "Application ID",
              value: track.application_id,
              hint: "Your reference for this application.",
            },
            { label: "Job ID", value: track.job_id, copyable: false },
            {
              label: "Interview ID",
              value: track.interview?.interview_id ?? null,
              hint: "The interview on this application, if one is scheduled.",
            },
          ]}
        />
      </section>

      {track.interview ? (
        <section
          className="rounded-[8px] border border-indigo-200/80 bg-indigo-50/30 p-5 shadow-xs"
          data-testid="candidate-interview"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="section-title">Your interview</h2>
            {track.interview.status ? (
              <span className="badge-neutral">
                {INTERVIEW_STATUS_LABELS[track.interview.status] ??
                  track.interview.status}
              </span>
            ) : null}
          </div>

          <p className="mt-1 text-sm text-gray-700">
            {track.interview.message ??
              "Your interview details will appear here."}
          </p>

          {formatDate(track.interview.scheduled_at) ? (
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-gray-500">
                  {track.interview.has_completed ? "Interviewed" : "Scheduled for"}
                </dt>
                <dd className="font-medium text-gray-900">
                  {formatDate(
                    track.interview.has_completed
                      ? track.interview.completed_at
                      : track.interview.scheduled_at,
                  )}
                </dd>
              </div>
              {track.interview.duration_minutes ? (
                <div>
                  <dt className="text-xs text-gray-500">Duration</dt>
                  <dd className="font-medium text-gray-900">
                    {track.interview.duration_minutes} minutes
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          {/* The room, reached by the interview id already shown above. Same
              component the recruiter sees, so the two sides cannot disagree
              about when the window opens or who has arrived. Without it this card
              is a schedule notice, not a way to attend.

              Gated on an actual interview id: the tracking payload types it as
              nullable, so a linked interview with no id yet would otherwise send
              the panel to /interview/null. */}
          {track.interview.interview_id ? (
            <div className="mt-4">
              <InterviewRoomPanel interviewId={track.interview.interview_id} className="rounded-[8px] border-slate-200" />
            </div>
          ) : null}

          <p className="mt-3 text-xs text-gray-500">
            This page shows when your interview is scheduled. Scores, notes and
            the hiring decision are not shown here.
          </p>
        </section>
      ) : null}

      {/* Phase 12: the assessment a recruiter assigned to this application, and
          the one action that applies to it right now. A separate request from the
          tracking payload because the assessment is candidate-allowlisted data —
          it is not part of the application timeline projection. */}
      <CandidateApplicationAssessmentCard applicationId={track.application_id} />

      {track.stages.length > 0 ? (
        <section className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs">
          <h2 className="section-title">Progress</h2>
          <p className="mt-1 text-xs text-gray-500">
            These are the stages your application has actually reached, in the order they were recorded.
          </p>
          <ol className="mt-3 flex flex-wrap gap-2">
            {track.stages.map((stage) => (
              <li
                key={stage.status}
                data-testid={`stage-${stage.status}`}
                aria-current={stage.is_current ? "step" : undefined}
                className={`rounded-[6px] border px-3 py-1.5 text-xs font-medium transition-colors ${stageClasses(stage)}`}
              >
                {stage.status_label}
                {stage.is_current ? " · current" : ""}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs">
        <h2 className="section-title">Activity</h2>
        {track.timeline.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">No status updates recorded yet.</p>
        ) : (
          <ol className="mt-3 space-y-4">
            {track.timeline.map((event, index) => {
              const occurred = formatDate(event.occurred_at);
              return (
                <li
                  key={`${event.status}-${index}`}
                  className="relative border-l-2 border-indigo-200 pl-4"
                >
                  <span
                    className={`absolute -left-[5px] top-1.5 h-2 w-2 rounded-full ${
                      event.is_current ? "bg-indigo-500" : "bg-gray-300"
                    }`}
                  />
                  <p className="text-sm font-medium text-gray-900">
                    {event.status_label}
                    {event.is_current ? (
                      <span className="ml-2 text-xs font-normal text-indigo-700">current</span>
                    ) : null}
                  </p>
                  {occurred ? <p className="text-xs text-gray-500">{occurred}</p> : null}
                  {event.message ? (
                    <p className="mt-1 text-sm text-gray-600">{event.message}</p>
                  ) : null}
                </li>
              );
            })}
          </ol>
        )}
      </section>

      <section className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs">
        <h2 className="section-title">Profile match</h2>
        <p className="mt-1 text-xs text-gray-500">
          Profile matching is automated decision support. It never changes your
          application status or decides an outcome.
        </p>
        <p className="mt-2 text-sm text-gray-700">Screening: {screeningLabel}</p>
        {track.has_match_explanation ? (
          <Button
            variant="secondary"
            size="sm"
            className="rounded-[6px] mt-3"
            onClick={() => navigate(`/candidate/applications/${track.application_id}/explanation`)}
          >
            How does my profile match?
          </Button>
        ) : (
          <p className="mt-2 text-xs text-gray-500">
            A match explanation is not available for this application yet.
          </p>
        )}
      </section>
    </div>
  );
}
