/**
 * Phase 11 recruiter interview panel.
 *
 * Schedules and manages an interview for the selected application, and shows the
 * interview evidence recorded against it.
 *
 * Like the Phase 8 decision panel, this component holds no transition table of
 * its own. Which actions exist, and why an action is unavailable, come from
 * `GET /interview/applications/{id}/interviews/options`, so the rules live only
 * on the backend and a button the UI offers is an action the API will accept.
 * A disabled button is given the server's reason as its title rather than being
 * silently hidden, so a recruiter can tell "not available yet" from "broken".
 *
 * Completing an interview records that it happened and moves the application to
 * Interviewed. It is not a hiring decision: nothing here selects, rejects or
 * ranks the candidate, and the score and recommendation below are shown as
 * evidence for the separate decision the recruiter makes in the panel above.
 */

import { useCallback, useEffect, useState } from "react";
import { interviewApi } from "../../api/interview";
import { IdentifierField } from "../ui/IdentifierField";
import { InterviewRoomPanel } from "../interview/InterviewRoomPanel";
import { useToast } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/error";
import { Button } from "../ui/Button";
import {
  HIRING_RECOMMENDATION_LABELS,
  INTERVIEW_REASON_LABELS,
  INTERVIEW_STAGE_LABELS,
  STATUS_COLORS,
  type ApplicationInterviewActionOption,
  type ApplicationInterviewEvidence,
  type ApplicationInterviewOptions,
  type ApplicationInterviewScheduleResult,
  type ApplicationStatus,
  type HiringRecommendation,
  type InterviewActionReason,
  type InterviewStage,
  type RejectionReason,
} from "../../types/interview";

interface ApplicationInterviewPanelProps {
  applicationId: string;
  /**
   * Called after any change that can move the application, so the page can
   * refresh the applicant list. Interview evidence alone does not move the
   * status, so the panel only calls this when the server says it changed.
   */
  onStatusChanged?: (result: ApplicationInterviewScheduleResult) => void;
  /**
   * Called after a stage action (reject) actually moves the application. Kept
   * separate from `onStatusChanged` because those actions return a different,
   * smaller result than a schedule call, and a recorder that re-sorts the list
   * only needs the new status.
   */
  onApplicationStatusChanged?: (status: ApplicationStatus) => void;
}

const STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

const RECOMMENDATION_LABELS: Record<string, string> = {
  strongly_recommend: "Strongly recommend",
  recommend: "Recommend",
  consider: "Consider",
  not_recommended: "Do not recommend",
};

/** The rejection vocabulary the interview-stage reject offers. */
const REJECTION_REASONS: RejectionReason[] = [
  "failed_interview",
  "insufficient_experience",
  "missing_required_skill",
  "low_job_match",
  "position_filled",
  "other",
];

const REJECTION_REASON_LABELS: Record<RejectionReason, string> = {
  failed_interview: "Failed the interview",
  insufficient_experience: "Insufficient experience",
  missing_required_skill: "Missing a required skill",
  low_job_match: "Low job match",
  failed_assessment: "Failed the assessment",
  education_requirement: "Does not meet education requirement",
  position_filled: "Position filled",
  other: "Other",
};

const RECOMMENDATION_OPTIONS: HiringRecommendation[] = [
  "strongly_recommend",
  "recommend",
  "consider",
  "not_recommended",
];

/** Default slot for the schedule form: tomorrow, an hour from now. */
function defaultSlot(): string {
  const when = new Date();
  when.setDate(when.getDate() + 1);
  when.setHours(when.getHours() + 1, 0, 0, 0);
  // datetime-local wants "YYYY-MM-DDTHH:mm" in local time, not an ISO instant.
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}T${pad(when.getHours())}:${pad(when.getMinutes())}`;
}

/**
 * Turn the datetime-local value into the instant the API expects.
 *
 * Returns null for an empty or unparseable value so the caller can refuse the
 * request locally rather than sending "Invalid Date" and surfacing a server error
 * for something the form can catch.
 */
function slotToIso(slot: string): string | null {
  if (!slot) return null;
  const parsed = new Date(slot);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function reasonText(reason: InterviewActionReason | null): string | undefined {
  return reason ? INTERVIEW_REASON_LABELS[reason] : undefined;
}

export function ApplicationInterviewPanel({
  applicationId,
  onStatusChanged,
  onApplicationStatusChanged,
}: ApplicationInterviewPanelProps) {
  const { addToast } = useToast();
  const [options, setOptions] = useState<ApplicationInterviewOptions | null>(null);
  const [evidence, setEvidence] = useState<ApplicationInterviewEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  const [slot, setSlot] = useState(defaultSlot);
  const [duration, setDuration] = useState(60);
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState("medium");
  const [scheduleOpen, setScheduleOpen] = useState(false);
  // Which round the open schedule form targets. Defaults to the recruiter round.
  const [scheduleStage, setScheduleStage] = useState<InterviewStage>("recruiter");
  const [hrInterviewers, setHrInterviewers] = useState<Array<{ id: string; full_name: string; email: string; role: string }>>([]);
  const [selectedInterviewerId, setSelectedInterviewerId] = useState<string>("");
  const [scheduleNotes, setScheduleNotes] = useState<string>("");
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  // Phase 15: advance/reject affordances and their inline confirmation forms.
  const [advanceOpen, setAdvanceOpen] = useState(false);
  const [advanceNote, setAdvanceNote] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] =
    useState<RejectionReason>("failed_interview");
  const [rejectNote, setRejectNote] = useState("");

  // Phase 15: the manual feedback form for one interview, opened on demand.
  const [feedbackForId, setFeedbackForId] = useState<string | null>(null);
  const [fbTechnical, setFbTechnical] = useState(50);
  const [fbCommunication, setFbCommunication] = useState(50);
  const [fbProblem, setFbProblem] = useState(50);
  const [fbRecommendation, setFbRecommendation] =
    useState<HiringRecommendation>("consider");
  const [fbNotes, setFbNotes] = useState("");

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      // Both are needed: the options say what may be done, the evidence says
      // what has happened. Fetched together so the panel is never rendered from
      // one without the other.
      const [loadedOptions, loadedEvidence] = await Promise.all([
        interviewApi.getApplicationInterviewOptions(applicationId),
        interviewApi.getApplicationInterviews(applicationId),
      ]);
      setOptions(loadedOptions);
      setEvidence(loadedEvidence);
    } catch (err) {
      setLoadError(getErrorMessage(err, "Failed to load interview details"));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    setLoading(true);
    // Clear the previous applicant's evidence so a fast switch between two
    // applicants cannot briefly show one applicant's interview for the other.
    setOptions(null);
    setEvidence(null);
    setScheduleOpen(false);
    setReschedulingId(null);
    setCancellingId(null);
    setSlot(defaultSlot());
    setScheduleStage("recruiter");
    setAdvanceOpen(false);
    setAdvanceNote("");
    setRejectOpen(false);
    setRejectReason("failed_interview");
    setRejectNote("");
    setFeedbackForId(null);
    void load();
  }, [load]);

  async function run(
    key: string,
    action: () => Promise<ApplicationInterviewScheduleResult>,
    successMessage: string,
    failureMessage: string,
  ) {
    setPending(key);
    try {
      const result = await action();
      addToast(result.message || successMessage, "success");
      setScheduleOpen(false);
      setReschedulingId(null);
      setCancellingId(null);
      setCancelReason("");
      // Only tell the page when the application actually moved. Rescheduling
      // changes the interview, not the stage, and re-sorting the applicant list
      // for that would be noise.
      if (result.application_status_changed) onStatusChanged?.(result);
      await load();
    } catch (err) {
      addToast(getErrorMessage(err, failureMessage), "error");
      // Reload anyway: a 409 means our view of the state is stale, and leaving
      // a button enabled that the server just refused is worse than a round trip.
      await load();
    } finally {
      setPending(null);
    }
  }

  const openScheduleHr = async () => {
    setScheduleStage("hr");
    setScheduleOpen(true);
    setSlot(defaultSlot());
    try {
      const interviewers = await interviewApi.getHrInterviewers(applicationId);
      setHrInterviewers(interviewers);
      if (interviewers.length > 0) {
        setSelectedInterviewerId(interviewers[0].id);
      }
    } catch {
      // Fallback if loading fails
    }
  };

  async function schedule() {
    const iso = slotToIso(slot);
    if (!iso) {
      addToast("Choose a valid date and time", "error");
      return;
    }
    await run(
      "schedule",
      () =>
        interviewApi.scheduleApplicationInterview(applicationId, {
          scheduled_at: iso,
          duration_minutes: duration,
          question_count: questionCount,
          difficulty,
          stage: scheduleStage,
          interviewer_id: scheduleStage === "hr" && selectedInterviewerId ? selectedInterviewerId : undefined,
          notes: scheduleNotes.trim() ? scheduleNotes.trim() : undefined,
        }),
      scheduleStage === "hr" ? "HR interview scheduled" : "Interview scheduled",
      "Failed to schedule interview",
    );
  }

  async function reschedule(option: ApplicationInterviewActionOption) {
    const iso = slotToIso(slot);
    if (!iso) {
      addToast("Choose a valid date and time", "error");
      return;
    }
    await run(
      `reschedule:${option.interview_id}`,
      () =>
        interviewApi.rescheduleApplicationInterview(
          applicationId,
          option.interview_id,
          { scheduled_at: iso, duration_minutes: duration },
        ),
      "Interview rescheduled",
      "Failed to reschedule interview",
    );
  }

  async function cancel(option: ApplicationInterviewActionOption) {
    await run(
      `cancel:${option.interview_id}`,
      () =>
        interviewApi.cancelApplicationInterview(
          applicationId,
          option.interview_id,
          cancelReason.trim() ? { reason: cancelReason.trim() } : {},
        ),
      "Interview cancelled",
      "Failed to cancel interview",
    );
  }

  async function complete(option: ApplicationInterviewActionOption) {
    await run(
      `complete:${option.interview_id}`,
      () =>
        interviewApi.completeApplicationInterview(
          applicationId,
          option.interview_id,
        ),
      "Interview marked complete",
      "Failed to complete interview",
    );
  }

  /**
   * Advance the candidate to the HR stage.
   *
   * Not routed through `run`: advancing does not move the application status, so
   * it returns the smaller stage-action result and never tells the page to
   * re-sort. A confirmation step guards it, because advancing is a deliberate
   * gate between rounds.
   */
  async function advance() {
    setPending("advance");
    try {
      const result = await interviewApi.advanceApplicationToHr(
        applicationId,
        advanceNote.trim() ? { note: advanceNote.trim() } : {},
      );
      addToast(result.message || "Candidate advanced to the HR stage", "success");
      setAdvanceOpen(false);
      setAdvanceNote("");
      await load();
    } catch (err) {
      addToast(getErrorMessage(err, "Failed to advance candidate"), "error");
      await load();
    } finally {
      setPending(null);
    }
  }

  /**
   * Reject the candidate from the interview stage.
   *
   * Delegates to the same decision service the decision panel uses, so the
   * status change and the candidate wording are identical. The inline form is the
   * confirmation step, and the page is told only when the status actually moved.
   */
  async function reject() {
    setPending("reject");
    try {
      const result = await interviewApi.rejectApplicationFromInterview(
        applicationId,
        {
          rejection_reason: rejectReason,
          ...(rejectNote.trim() ? { internal_note: rejectNote.trim() } : {}),
        },
      );
      addToast(result.message || "Application rejected", "success");
      setRejectOpen(false);
      setRejectNote("");
      if (result.application_status_changed) {
        onApplicationStatusChanged?.(result.application_status);
      }
      await load();
    } catch (err) {
      addToast(getErrorMessage(err, "Failed to reject application"), "error");
      await load();
    } finally {
      setPending(null);
    }
  }

  /** Open (or close) the manual feedback form, prefilling any saved feedback. */
  async function toggleFeedback(interviewId: string) {
    if (feedbackForId === interviewId) {
      setFeedbackForId(null);
      return;
    }
    setFeedbackForId(interviewId);
    // Reset to neutral defaults first so a previous interview's values never
    // bleed into this one, then try to prefill from the server.
    setFbTechnical(50);
    setFbCommunication(50);
    setFbProblem(50);
    setFbRecommendation("consider");
    setFbNotes("");
    try {
      const saved = await interviewApi.getApplicationInterviewFeedback(
        applicationId,
        interviewId,
      );
      setFbTechnical(saved.technical_skills);
      setFbCommunication(saved.communication);
      setFbProblem(saved.problem_solving);
      setFbRecommendation(saved.recommendation);
      setFbNotes(saved.recruiter_notes ?? "");
    } catch {
      // No feedback recorded yet (404), or not readable: a blank form is the
      // right starting point either way.
    }
  }

  async function saveFeedback(interviewId: string) {
    setPending(`feedback:${interviewId}`);
    try {
      await interviewApi.saveApplicationInterviewFeedback(
        applicationId,
        interviewId,
        {
          technical_skills: fbTechnical,
          communication: fbCommunication,
          problem_solving: fbProblem,
          recommendation: fbRecommendation,
          ...(fbNotes.trim() ? { recruiter_notes: fbNotes.trim() } : {}),
        },
      );
      addToast("Interview feedback saved", "success");
      setFeedbackForId(null);
      await load();
    } catch (err) {
      addToast(getErrorMessage(err, "Failed to save feedback"), "error");
    } finally {
      setPending(null);
    }
  }

  if (loading) {
    return (
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-ink">Interview</h3>
        <p className="mt-2 text-sm text-ink-muted">Loading interview details…</p>
      </div>
    );
  }

  if (loadError || !options) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6">
        <h3 className="text-sm font-semibold text-rose-900">Interview</h3>
        <p className="mt-2 text-sm text-rose-700">{loadError}</p>
      </div>
    );
  }

  const optionById = new Map(options.options.map((o) => [o.interview_id, o]));
  const busy = pending !== null;

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">Interview</h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            Scheduling records that an interview happened. It is not a hiring
            decision — the decision above stays yours.
          </p>
        </div>
        <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-ink">
          {options.current_status.replace(/_/g, " ")}
        </span>
      </div>

      {/* No identity block here. This panel is only ever rendered inside the
          applicant view, which already shows the candidate, the application and
          the job identifiers directly above it. Rendering them again produced
          two "Copy candidate ID" controls on one screen, with nothing to tell a
          recruiter which one to use. The schedule form below is keyed by the
          application, so the context it needs is already established. */}

      {/* Schedule. Two stages can be scheduled: the recruiter round whenever the
          application is shortlisted, and the HR round only once the candidate has
          been advanced. The server decides which; this renders its verdict. */}
      <div className="mt-4">
        {!scheduleOpen ? (
          options.can_schedule || options.can_schedule_hr ? (
            <div className="flex flex-wrap gap-2">
              {options.can_schedule ? (
                <Button
                  onClick={() => {
                    setScheduleStage("recruiter");
                    setScheduleOpen(true);
                    setSlot(defaultSlot());
                  }}
                >
                  Schedule interview
                </Button>
              ) : null}
              {options.can_schedule_hr ? (
                <Button
                  variant="secondary"
                  onClick={() => void openScheduleHr()}
                >
                  Schedule HR interview
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="rounded-md bg-gray-100 px-3 py-2 text-sm text-ink-muted">
              {reasonText(options.schedule_unavailable_reason) ??
                reasonText(options.schedule_hr_unavailable_reason) ??
                "An interview cannot be scheduled for this application."}
            </p>
          )
        ) : (
          <div className="rounded-md border border-slate-200/70 bg-gray-100 p-4">
            <p className="mb-3 text-xs font-semibold text-ink">
              {scheduleStage === "hr"
                ? "Scheduling the HR interview"
                : "Scheduling the recruiter interview"}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
                {scheduleStage === "hr" && (
                  <div className="sm:col-span-2">
                    <label
                      htmlFor="interview-interviewer"
                      className="block text-xs font-semibold text-ink"
                    >
                      Assigned HR Interviewer
                    </label>
                    <select
                      id="interview-interviewer"
                      value={selectedInterviewerId}
                      onChange={(e) => setSelectedInterviewerId(e.target.value)}
                      className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800"
                    >
                      {hrInterviewers.length > 0 ? (
                        hrInterviewers.map((hr) => (
                          <option key={hr.id} value={hr.id}>
                            {hr.full_name} ({hr.email}) — {hr.role.replace(/_/g, " ")}
                          </option>
                        ))
                      ) : (
                        <option value="">Default HR Manager</option>
                      )}
                    </select>
                  </div>
                )}
                <div>
                  <label
                    htmlFor="interview-slot"
                    className="block text-xs font-semibold text-ink"
                  >
                    Date &amp; time
                  </label>
                  <input
                    id="interview-slot"
                    type="datetime-local"
                    value={slot}
                    onChange={(e) => setSlot(e.target.value)}
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="interview-duration"
                    className="block text-xs font-semibold text-ink"
                  >
                    Duration (minutes)
                  </label>
                  <input
                    id="interview-duration"
                    type="number"
                    min={15}
                    max={180}
                    step={15}
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="interview-questions"
                    className="block text-xs font-semibold text-ink"
                  >
                    Questions
                  </label>
                  <input
                    id="interview-questions"
                    type="number"
                    min={1}
                    max={50}
                    value={questionCount}
                    onChange={(e) => setQuestionCount(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="interview-difficulty"
                    className="block text-xs font-semibold text-ink"
                  >
                    Difficulty
                  </label>
                  <select
                    id="interview-difficulty"
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value)}
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                    <option value="mixed">Mixed</option>
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label
                    htmlFor="interview-notes"
                    className="block text-xs font-semibold text-ink"
                  >
                    {scheduleStage === "hr" ? "HR Interview Focus Areas / Notes (optional)" : "Interview Notes (optional)"}
                  </label>
                  <textarea
                    id="interview-notes"
                    rows={2}
                    value={scheduleNotes}
                    onChange={(e) => setScheduleNotes(e.target.value)}
                    placeholder="e.g. Cultural fit, communication, team leadership..."
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  onClick={() => void schedule()}
                  disabled={busy}
                >
                  {pending === "schedule" ? "Scheduling…" : "Confirm schedule"}
                </Button>
                <Button variant="ghost" onClick={() => setScheduleOpen(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>

      {/* Evidence summary */}
      {evidence && evidence.interview_count > 0 && (
        <div className="mt-4 flex flex-wrap gap-4 border-t border-slate-200/70 pt-4 text-sm">
          <div>
            <span className="text-ink-muted">Interviews</span>{" "}
            <span className="font-medium text-ink">
              {evidence.interview_count}
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
              {evidence.average_overall_score ?? "—"}
            </span>
          </div>
        </div>
      )}

      {/* Interviews */}
      {evidence && evidence.interviews.length > 0 && (
        <ul className="mt-4 space-y-3">
          {evidence.interviews.map((interview) => {
            const option = optionById.get(interview.id);
            const isHr = interview.stage === "hr";
            return (
              <li
                key={interview.id}
                className="rounded-md border border-slate-200/70 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        isHr
                          ? "bg-purple-100 text-purple-800"
                          : "bg-primary-50 text-primary-700"
                      }`}
                    >
                      {INTERVIEW_STAGE_LABELS[interview.stage]}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_COLORS[interview.status] ?? "bg-gray-100 text-ink"
                      }`}
                    >
                      {STATUS_LABELS[interview.status] ?? interview.status}
                    </span>
                    <span className="text-sm text-ink">
                      {formatWhen(interview.scheduled_at)}
                    </span>
                  </div>
                  {interview.overall_score !== null && (
                    <span className="text-sm text-ink">
                      Score{" "}
                      <span className="font-medium text-ink">
                        {interview.overall_score}
                      </span>
                      {interview.recommendation && (
                        <span className="ml-2 text-xs text-ink-muted">
                          {
                            RECOMMENDATION_LABELS[interview.recommendation] ??
                            interview.recommendation
                          }
                        </span>
                      )}
                    </span>
                  )}
                </div>

                <p className="mt-1 text-xs text-ink-muted">
                  {interview.questions_answered}/{interview.total_questions}{" "}
                  answered
                  {interview.completed_at && (
                    <> · completed {formatWhen(interview.completed_at)}</>
                  )}
                </p>

                {/* The interview's own identifier, kept distinct from the
                    application's above: four UUIDs in one panel are
                    indistinguishable without their labels. */}
                <div className="mt-2">
                  <IdentifierField
                    label="Interview ID"
                    value={interview.id}
                    size="sm"
                    copyable
                  />
                </div>

                {isHr ? (
                  /* HR Stage: Coordination view only.
                     Recruiter can see stage, schedule, interviewer and can coordinate
                     by Rescheduling or Cancelling, but CANNOT join room, complete,
                     or submit evaluation/decision feedback. */
                  <div className="mt-3 space-y-2">
                    <div className="rounded-md bg-purple-50/80 border border-purple-200/70 p-3 text-xs text-purple-900">
                      <p className="font-semibold text-purple-950">HR Stage Interview</p>
                      <p className="mt-0.5 text-purple-800">
                        This interview is conducted, attended, and evaluated by the assigned HR Manager in the HR Oversight section. Recruiter room access, attendance, completion, and feedback forms are restricted to HR.
                      </p>
                    </div>

                    {option && (
                      <div className="flex flex-wrap gap-2 pt-1">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={!option.can_reschedule || busy}
                          title={reasonText(option.reschedule_unavailable_reason)}
                          aria-expanded={reschedulingId === interview.id}
                          onClick={() => {
                            if (reschedulingId === interview.id) {
                              setReschedulingId(null);
                            } else {
                              setReschedulingId(interview.id);
                              setScheduleOpen(false);
                              setCancellingId(null);
                              setSlot(defaultSlot());
                            }
                          }}
                        >
                          {reschedulingId === interview.id
                            ? "Editing time"
                            : "Reschedule"}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={!option.can_cancel || busy}
                          title={reasonText(option.cancel_unavailable_reason)}
                          onClick={() => {
                            setCancellingId(
                              cancellingId === interview.id ? null : interview.id,
                            );
                            setCancelReason("");
                          }}
                        >
                          {pending === `cancel:${interview.id}`
                            ? "Cancelling…"
                            : "Cancel"}
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  /* Recruiter Stage: full interview actions, completion, feedback, room */
                  <>
                    {option && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={!option.can_reschedule || busy}
                          title={reasonText(option.reschedule_unavailable_reason)}
                          // A pure toggle. Saving happens once, from the form this
                          // opens, so there is no second path that commits a time the
                          // recruiter never saw.
                          aria-expanded={reschedulingId === interview.id}
                          onClick={() => {
                            if (reschedulingId === interview.id) {
                              setReschedulingId(null);
                            } else {
                              setReschedulingId(interview.id);
                              setScheduleOpen(false);
                              setCancellingId(null);
                              setSlot(defaultSlot());
                            }
                          }}
                        >
                          {reschedulingId === interview.id
                            ? "Editing time"
                            : "Reschedule"}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={!option.can_complete || busy}
                          title={reasonText(option.complete_unavailable_reason)}
                          onClick={() => void complete(option)}
                        >
                          {pending === `complete:${interview.id}`
                            ? "Completing…"
                            : "Mark complete"}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={!option.can_cancel || busy}
                          title={reasonText(option.cancel_unavailable_reason)}
                          onClick={() => {
                            setCancellingId(
                              cancellingId === interview.id ? null : interview.id,
                            );
                            setCancelReason("");
                          }}
                        >
                          {pending === `cancel:${interview.id}`
                            ? "Cancelling…"
                            : "Cancel"}
                        </Button>
                      </div>
                    )}

                    {/* Manual technical feedback. Staff-only evidence the candidate
                        never receives; the server stores it on the interview's
                        scorecard. It is the interviewer's own judgement, entered by
                        hand, and never influences a decision on its own. */}
                    <div className="mt-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-expanded={feedbackForId === interview.id}
                        onClick={() => void toggleFeedback(interview.id)}
                      >
                        {feedbackForId === interview.id
                          ? "Close feedback"
                          : interview.has_scorecard
                            ? "Edit feedback"
                            : "Record feedback"}
                      </Button>
                    </div>

                    {feedbackForId === interview.id && (
                      <div className="mt-2 rounded-md bg-gray-100 p-3">
                        <div className="grid gap-3 sm:grid-cols-3">
                          <div>
                            <label
                              htmlFor={`fb-technical-${interview.id}`}
                              className="block text-xs font-semibold text-ink"
                            >
                              Technical skills
                            </label>
                            <input
                              id={`fb-technical-${interview.id}`}
                              type="number"
                              min={0}
                              max={100}
                              value={fbTechnical}
                              onChange={(e) => setFbTechnical(Number(e.target.value))}
                              className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                            />
                          </div>
                          <div>
                            <label
                              htmlFor={`fb-communication-${interview.id}`}
                              className="block text-xs font-semibold text-ink"
                            >
                              Communication
                            </label>
                            <input
                              id={`fb-communication-${interview.id}`}
                              type="number"
                              min={0}
                              max={100}
                              value={fbCommunication}
                              onChange={(e) => setFbCommunication(Number(e.target.value))}
                              className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                            />
                          </div>
                          <div>
                            <label
                              htmlFor={`fb-problem-${interview.id}`}
                              className="block text-xs font-semibold text-ink"
                            >
                              Problem solving
                            </label>
                            <input
                              id={`fb-problem-${interview.id}`}
                              type="number"
                              min={0}
                              max={100}
                              value={fbProblem}
                              onChange={(e) => setFbProblem(Number(e.target.value))}
                              className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                            />
                          </div>
                        </div>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <div>
                            <label
                              htmlFor={`fb-recommendation-${interview.id}`}
                              className="block text-xs font-semibold text-ink"
                            >
                              Recommendation
                            </label>
                            <select
                              id={`fb-recommendation-${interview.id}`}
                              value={fbRecommendation}
                              onChange={(e) =>
                                setFbRecommendation(e.target.value as HiringRecommendation)
                              }
                              className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                            >
                              {RECOMMENDATION_OPTIONS.map((value) => (
                                <option key={value} value={value}>
                                  {HIRING_RECOMMENDATION_LABELS[value]}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label
                              htmlFor={`fb-notes-${interview.id}`}
                              className="block text-xs font-semibold text-ink"
                            >
                              Notes (internal)
                            </label>
                            <textarea
                              id={`fb-notes-${interview.id}`}
                              rows={2}
                              value={fbNotes}
                              onChange={(e) => setFbNotes(e.target.value)}
                              className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                            />
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            onClick={() => void saveFeedback(interview.id)}
                            disabled={busy}
                          >
                            {pending === `feedback:${interview.id}`
                              ? "Saving…"
                              : "Save feedback"}
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => setFeedbackForId(null)}
                          >
                            Cancel feedback
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* The room for this interview, addressed by its own id. It
                        carries attendance only -- no decision controls -- so the
                        select/reject UI stays in ApplicationDecisionPanel above,
                        where the Phase 8 rules live. */}
                    <div className="mt-3">
                      <InterviewRoomPanel
                        interviewId={interview.id}
                        onJoined={() => void load()}
                      />
                    </div>
                  </>
                )}

                {/* Reschedule inline form (available for both recruiter & HR coordination) */}
                {reschedulingId === interview.id && option?.can_reschedule && (
                  <div className="mt-2 grid gap-2 rounded-md bg-gray-100 p-3 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor={`reschedule-slot-${interview.id}`}
                        className="block text-xs font-semibold text-ink"
                      >
                        New date &amp; time
                      </label>
                      <input
                        id={`reschedule-slot-${interview.id}`}
                        type="datetime-local"
                        value={slot}
                        onChange={(e) => setSlot(e.target.value)}
                        className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="flex items-end gap-2">
                      <Button
                        onClick={() => void reschedule(option)}
                        disabled={busy}
                      >
                        {pending === `reschedule:${interview.id}`
                          ? "Saving…"
                          : "Save new time"}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => setReschedulingId(null)}
                        disabled={busy}
                      >
                        Keep current time
                      </Button>
                    </div>
                  </div>
                )}

                {/* Cancel inline form (available for both recruiter & HR coordination) */}
                {cancellingId === interview.id && option?.can_cancel && (
                  <div className="mt-2 rounded-md bg-gray-100 p-3">
                    <label
                      htmlFor={`cancel-reason-${interview.id}`}
                      className="block text-xs font-semibold text-ink"
                    >
                      Reason (internal — the candidate is only told it was
                      cancelled)
                    </label>
                    <input
                      id={`cancel-reason-${interview.id}`}
                      type="text"
                      value={cancelReason}
                      onChange={(e) => setCancelReason(e.target.value)}
                      className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button
                        variant="danger"
                        onClick={() => void cancel(option)}
                        disabled={busy}
                      >
                        {pending === `cancel:${interview.id}`
                          ? "Cancelling…"
                          : "Confirm cancellation"}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => setCancellingId(null)}
                      >
                        Keep interview
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {evidence && evidence.interview_count === 0 && (
        <p className="mt-4 text-sm text-ink-muted">
          No interviews recorded for this application yet.
        </p>
      )}

      {/* Stage actions: advance the candidate to the HR round, or reject from
          the interview stage. Both are deliberate decisions, so each requires an
          explicit confirmation step. The server decides when each is available;
          a disabled button carries its reason as a title rather than vanishing. */}
      {!options.status_is_final && (
        <div className="mt-4 border-t border-slate-200/70 pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-ink">Stage actions</h4>
            {options.hr_eligible ? (
              <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700">
                Advanced to HR
              </span>
            ) : null}
          </div>

          <div className="mt-2 flex flex-wrap gap-2">
            {!options.hr_eligible && (
              <Button
                variant="secondary"
                size="sm"
                disabled={!options.can_advance || busy}
                title={reasonText(options.advance_unavailable_reason)}
                aria-expanded={advanceOpen}
                onClick={() => {
                  setAdvanceOpen(true);
                  setRejectOpen(false);
                  setAdvanceNote("");
                }}
              >
                Advance to HR
              </Button>
            )}
            {options.can_reject ? (
              <Button
                variant="danger"
                size="sm"
                disabled={busy}
                aria-expanded={rejectOpen}
                onClick={() => {
                  setRejectOpen(true);
                  setAdvanceOpen(false);
                }}
              >
                Reject candidate
              </Button>
            ) : null}
          </div>

          {advanceOpen && (
            <div className="mt-2 rounded-md bg-gray-100 p-3">
              <p className="text-xs text-ink-muted">
                Advancing marks the candidate eligible for an HR interview. It
                schedules no time and makes no hiring decision — the HR round is
                still scheduled separately.
              </p>
              <label
                htmlFor="advance-note"
                className="mt-2 block text-xs font-semibold text-ink"
              >
                Note (internal, optional)
              </label>
              <input
                id="advance-note"
                type="text"
                value={advanceNote}
                onChange={(e) => setAdvanceNote(e.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <Button onClick={() => void advance()} disabled={busy}>
                  {pending === "advance" ? "Advancing…" : "Confirm advance"}
                </Button>
                <Button variant="ghost" onClick={() => setAdvanceOpen(false)}>
                  Cancel advance
                </Button>
              </div>
            </div>
          )}

          {rejectOpen && (
            <div className="mt-2 rounded-md bg-gray-100 p-3">
              <label
                htmlFor="reject-reason"
                className="block text-xs font-semibold text-ink"
              >
                Rejection reason
              </label>
              <select
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value as RejectionReason)}
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                {REJECTION_REASONS.map((value) => (
                  <option key={value} value={value}>
                    {REJECTION_REASON_LABELS[value]}
                  </option>
                ))}
              </select>
              <label
                htmlFor="reject-note"
                className="mt-2 block text-xs font-semibold text-ink"
              >
                Internal note (optional)
              </label>
              <input
                id="reject-note"
                type="text"
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              />
              <p className="mt-1 text-xs text-ink-muted">
                The candidate sees a message derived from the reason, not your
                note.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  variant="danger"
                  onClick={() => void reject()}
                  disabled={busy}
                >
                  {pending === "reject" ? "Rejecting…" : "Confirm rejection"}
                </Button>
                <Button variant="ghost" onClick={() => setRejectOpen(false)}>
                  Keep candidate
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ApplicationInterviewPanel;
