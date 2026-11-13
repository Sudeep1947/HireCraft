/**
 * After the call ends: the interviewer's record of what happened.
 *
 * Reached from the video page when the recruiter or HR ends (or leaves) an
 * application-linked interview.
 *
 * For Recruiters:
 * 1. Complete the interview & save feedback (technical, communication, problem solving)
 * 2. Advance to HR or reject candidate.
 *
 * For HR:
 * 1. Structured HR Evaluation (1–5 scale: Communication, Technical, Problem Solving,
 *    Teamwork, Overall performance, Strengths, Weaknesses, HR comments, Final recommendation)
 *    with "Save Draft" and "Submit Feedback".
 * 2. Final HR Decision:
 *    - Hire Candidate (moves to Hired)
 *    - Reject Candidate (with reason)
 *    - Keep on Hold (pending review)
 *    - Request Additional Interview (follow-up round)
 *    with a confirmation dialog before recording.
 */

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Clock, CalendarPlus } from "lucide-react";
import { Button } from "../ui/Button";
import { interviewApi } from "../../api/interview";
import { hrDecisionApi } from "../../api/hrOversight";
import { getServerErrorMessage } from "../../utils/error";
import {
  HIRING_RECOMMENDATION_LABELS,
  type HiringRecommendation,
  type RejectionReason,
} from "../../types/interview";

/** The Phase 8 controlled rejection vocabulary */
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

interface InterviewEndPanelProps {
  applicationId: string;
  interviewId: string;
  stage?: string;
  /** Called once the interview is recorded, whatever the decision. */
  onComplete?: () => void;
  className?: string;
}

type Step = "notes" | "decision" | "done";

const RATING_FIELDS = [
  { key: "technical_skills", label: "Technical skills" },
  { key: "communication", label: "Communication" },
  { key: "problem_solving", label: "Problem solving" },
] as const;

function ratingInputClasses() {
  return "mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-ink focus:border-primary-400 focus:outline-none";
}

export function InterviewEndPanel({
  applicationId,
  interviewId,
  stage,
  onComplete,
  className = "",
}: InterviewEndPanelProps) {
  const isHr = stage === "hr";
  const [step, setStep] = useState<Step>("notes");

  // Recruiter ratings (0-100)
  const [ratings, setRatings] = useState<Record<string, number>>({
    technical_skills: 50,
    communication: 50,
    problem_solving: 50,
  });
  const [notes, setNotes] = useState("");

  // HR Evaluation state (1-5 scale)
  const [hrComm, setHrComm] = useState<number>(4);
  const [hrTech, setHrTech] = useState<number>(4);
  const [hrProblem, setHrProblem] = useState<number>(4);
  const [hrTeamwork, setHrTeamwork] = useState<number>(4);
  const [hrOverall, setHrOverall] = useState<number>(4);
  const [hrStrengths, setHrStrengths] = useState<string>("");
  const [hrWeaknesses, setHrWeaknesses] = useState<string>("");
  const [hrComments, setHrComments] = useState<string>("");
  const [hrRecommendation, setHrRecommendation] = useState<HiringRecommendation>("recommend");
  const [draftNotice, setDraftNotice] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Recruiter Decision
  const [recruiterDecision, setRecruiterDecision] = useState<"advance" | "reject">("advance");

  // HR Decision: 4 choices
  const [hrDecision, setHrDecision] = useState<"hire" | "reject" | "keep_on_hold" | "additional_interview">("hire");
  const [additionalDate, setAdditionalDate] = useState<string>("");
  const [additionalDuration, setAdditionalDuration] = useState<number>(45);
  const [additionalNotes, setAdditionalNotes] = useState<string>("");

  const [rejectionReason, setRejectionReason] = useState<RejectionReason>("failed_interview");
  const [rejectionNote, setRejectionNote] = useState("");
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [doneDecisionText, setDoneDecisionText] = useState("");

  // Load draft for HR if available
  useEffect(() => {
    if (isHr) {
      const draftKey = `hr_eval_draft_${interviewId || applicationId}`;
      try {
        const saved = localStorage.getItem(draftKey);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed.hrComm) setHrComm(parsed.hrComm);
          if (parsed.hrTech) setHrTech(parsed.hrTech);
          if (parsed.hrProblem) setHrProblem(parsed.hrProblem);
          if (parsed.hrTeamwork) setHrTeamwork(parsed.hrTeamwork);
          if (parsed.hrOverall) setHrOverall(parsed.hrOverall);
          if (parsed.hrStrengths) setHrStrengths(parsed.hrStrengths);
          if (parsed.hrWeaknesses) setHrWeaknesses(parsed.hrWeaknesses);
          if (parsed.hrComments) setHrComments(parsed.hrComments);
          if (parsed.hrRecommendation) setHrRecommendation(parsed.hrRecommendation);
          setDraftNotice("Restored draft evaluation from local storage.");
        }
      } catch {
        // ignore draft load errors
      }
    }
  }, [isHr, interviewId, applicationId]);

  const handleSaveHrDraft = () => {
    const draftKey = `hr_eval_draft_${interviewId || applicationId}`;
    const draftData = {
      hrComm,
      hrTech,
      hrProblem,
      hrTeamwork,
      hrOverall,
      hrStrengths,
      hrWeaknesses,
      hrComments,
      hrRecommendation,
      savedAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem(draftKey, JSON.stringify(draftData));
      setDraftNotice(`Draft saved locally at ${new Date().toLocaleTimeString()}.`);
    } catch {
      setDraftNotice("Unable to save draft locally.");
    }
  };

  const recruiterRecommendation: HiringRecommendation =
    ratings.technical_skills >= 75 && ratings.problem_solving >= 70
      ? "strongly_recommend"
      : ratings.technical_skills >= 55 || ratings.problem_solving >= 55
        ? "recommend"
        : ratings.technical_skills >= 40 || ratings.problem_solving >= 40
          ? "consider"
          : "not_recommended";

  const saveFeedback = async () => {
    setSaving(true);
    setError(null);
    try {
      await interviewApi.completeApplicationInterview(applicationId, interviewId);
      if (isHr) {
        // Map 1-5 scale to standard 20-100 scale for backend scorecard storage
        await interviewApi.saveApplicationInterviewFeedback(
          applicationId,
          interviewId,
          {
            communication: hrComm * 20,
            technical_skills: hrTech * 20,
            problem_solving: hrProblem * 20,
            teamwork: hrTeamwork * 20,
            overall_score: hrOverall * 20,
            strengths: hrStrengths.trim() || undefined,
            concerns: hrWeaknesses.trim() || undefined,
            recruiter_notes: hrComments.trim() || undefined,
            recommendation: hrRecommendation,
          },
        );
        // Clear draft on successful submit
        try {
          localStorage.removeItem(`hr_eval_draft_${interviewId || applicationId}`);
        } catch {
          // ignore
        }
      } else {
        await interviewApi.saveApplicationInterviewFeedback(
          applicationId,
          interviewId,
          {
            technical_skills: ratings.technical_skills,
            communication: ratings.communication,
            problem_solving: ratings.problem_solving,
            recommendation: recruiterRecommendation,
            recruiter_notes: notes.trim() ? notes.trim() : undefined,
          },
        );
      }
      setStep("decision");
      onComplete?.();
    } catch (err) {
      setError(
        getServerErrorMessage(err, "The interview feedback could not be saved."),
      );
    } finally {
      setSaving(false);
    }
  };

  const applyDecision = async () => {
    setDeciding(true);
    setError(null);
    try {
      if (isHr) {
        if (hrDecision === "hire") {
          await hrDecisionApi.recordDecision(applicationId, {
            decision: "hire",
            internal_note: rejectionNote.trim() || undefined,
          });
          setDoneDecisionText("Candidate hired successfully. Status updated to Hired, and notifications have been sent to candidate, recruiter, and organization admin.");
        } else if (hrDecision === "reject") {
          await hrDecisionApi.recordDecision(applicationId, {
            decision: "reject",
            rejection_reason: rejectionReason,
            internal_note: rejectionNote.trim() || undefined,
          });
          setDoneDecisionText("Candidate application rejected. Candidate notified with approved respectful wording.");
        } else if (hrDecision === "keep_on_hold") {
          await hrDecisionApi.recordDecision(applicationId, {
            decision: "keep_under_review",
            internal_note: rejectionNote.trim() || undefined,
          });
          setDoneDecisionText("Candidate kept on hold under active review for future consideration.");
        } else if (hrDecision === "additional_interview") {
          await hrDecisionApi.requestAdditionalInterview(applicationId, {
            scheduled_at: additionalDate ? new Date(additionalDate).toISOString() : undefined,
            duration_minutes: additionalDuration,
            notes: additionalNotes.trim() || undefined,
          });
          setDoneDecisionText("Additional HR interview round requested and recorded successfully.");
        }
      } else {
        if (recruiterDecision === "advance") {
          await interviewApi.advanceApplicationToHr(applicationId, {
            note: "Advanced after the recruiter interview",
          });
          setDoneDecisionText("The candidate has been advanced for further review. No time has been picked for them — scheduling the next round stays a separate, explicit action.");
        } else {
          await interviewApi.rejectApplicationFromInterview(applicationId, {
            rejection_reason: rejectionReason,
            internal_note: rejectionNote.trim() ? rejectionNote.trim() : undefined,
          });
          setDoneDecisionText("The candidate has been rejected and will be notified with the approved wording. Your internal note stays with the hiring team.");
        }
      }
      setConfirmModalOpen(false);
      setStep("done");
    } catch (err) {
      setError(
        getServerErrorMessage(err, "The decision could not be applied."),
      );
    } finally {
      setDeciding(false);
    }
  };

  if (step === "done") {
    return (
      <section
        className={`rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 ${className}`}
        data-testid="interview-end-panel"
      >
        <h2 className="text-sm font-semibold text-ink">
          {isHr ? "HR decision recorded" : "Interview recorded"}
        </h2>
        <p className="mt-1 text-sm text-ink">{doneDecisionText}</p>
        {isHr && (
          <div className="mt-4 flex flex-wrap gap-2.5">
            <a
              href="/hr/dashboard"
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 transition"
            >
              Go to HR Dashboard
            </a>
            <a
              href={`/hr/applications/${applicationId}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-emerald-800 shadow-xs hover:bg-emerald-50 transition"
            >
              View Candidate &amp; Hiring Report
            </a>
          </div>
        )}
      </section>
    );
  }

  if (step === "decision") {
    return (
      <section
        className={`rounded-xl border border-slate-200/70 bg-white p-5 ${className}`}
        data-testid="interview-end-panel"
      >
        <h2 className="text-sm font-semibold text-ink">
          {isHr ? "Final HR Hiring Decision" : "Overall recommendation"}
        </h2>
        <p className="mt-1 text-xs text-ink-muted">
          {isHr
            ? "Your evaluation feedback has been saved. Select the final decision for this candidate."
            : `Your feedback is saved (${HIRING_RECOMMENDATION_LABELS[recruiterRecommendation]}). Choose the outcome for this candidate's application.`}
        </p>

        {isHr ? (
          /* ── HR 4 Decisions (Hire, Reject, Hold, Additional Interview) ── */
          <fieldset className="mt-4 space-y-3">
            <legend className="sr-only">HR Final Decision</legend>

            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${hrDecision === "hire" ? "border-emerald-500 bg-emerald-50/40" : "border-slate-200 hover:bg-slate-50"}`}>
              <input
                type="radio"
                name="hr-decision"
                value="hire"
                checked={hrDecision === "hire"}
                onChange={() => setHrDecision("hire")}
                className="mt-1 accent-emerald-600"
              />
              <div>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-900">
                  <CheckCircle className="h-4 w-4 text-emerald-600" />
                  Hire Candidate
                </span>
                <span className="block text-xs text-slate-600 mt-0.5">
                  Move the candidate to Hired status. Candidate, recruiter, and organization admin will be notified.
                </span>
              </div>
            </label>

            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${hrDecision === "reject" ? "border-rose-500 bg-rose-50/40" : "border-slate-200 hover:bg-slate-50"}`}>
              <input
                type="radio"
                name="hr-decision"
                value="reject"
                checked={hrDecision === "reject"}
                onChange={() => setHrDecision("reject")}
                className="mt-1 accent-rose-600"
              />
              <div>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-rose-900">
                  <XCircle className="h-4 w-4 text-rose-600" />
                  Reject Candidate
                </span>
                <span className="block text-xs text-slate-600 mt-0.5">
                  Reject the application with a formal reason code and notify the candidate.
                </span>
              </div>
            </label>

            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${hrDecision === "keep_on_hold" ? "border-amber-500 bg-amber-50/40" : "border-slate-200 hover:bg-slate-50"}`}>
              <input
                type="radio"
                name="hr-decision"
                value="keep_on_hold"
                checked={hrDecision === "keep_on_hold"}
                onChange={() => setHrDecision("keep_on_hold")}
                className="mt-1 accent-amber-600"
              />
              <div>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-amber-900">
                  <Clock className="h-4 w-4 text-amber-600" />
                  Keep on Hold
                </span>
                <span className="block text-xs text-slate-600 mt-0.5">
                  Keep application active and under review for a future hiring decision.
                </span>
              </div>
            </label>

            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${hrDecision === "additional_interview" ? "border-indigo-500 bg-indigo-50/40" : "border-slate-200 hover:bg-slate-50"}`}>
              <input
                type="radio"
                name="hr-decision"
                value="additional_interview"
                checked={hrDecision === "additional_interview"}
                onChange={() => setHrDecision("additional_interview")}
                className="mt-1 accent-indigo-600"
              />
              <div>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-indigo-900">
                  <CalendarPlus className="h-4 w-4 text-indigo-600" />
                  Request Additional Interview
                </span>
                <span className="block text-xs text-slate-600 mt-0.5">
                  Schedule another follow-up HR evaluation round.
                </span>
              </div>
            </label>
          </fieldset>
        ) : (
          /* ── Recruiter Decision: Advance or Reject ── */
          <fieldset className="mt-3 space-y-2">
            <legend className="sr-only">Decision</legend>
            <label className="flex cursor-pointer items-start gap-2 text-sm text-ink">
              <input
                type="radio"
                name="decision"
                value="advance"
                checked={recruiterDecision === "advance"}
                onChange={() => setRecruiterDecision("advance")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Advance for further review</span>
                <span className="block text-xs text-ink-muted">
                  Marks the candidate HR-round-eligible. It picks no time and
                  makes no hiring decision.
                </span>
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-2 text-sm text-ink">
              <input
                type="radio"
                name="decision"
                value="reject"
                checked={recruiterDecision === "reject"}
                onChange={() => setRecruiterDecision("reject")}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Reject candidate</span>
                <span className="block text-xs text-ink-muted">
                  Ends their application for this job with the approved reason
                  vocabulary.
                </span>
              </span>
            </label>
          </fieldset>
        )}

        {/* Rejection Details */}
        {(isHr ? hrDecision === "reject" : recruiterDecision === "reject") && (
          <div className="mt-3 rounded-lg bg-slate-50 p-3">
            <label className="text-xs font-medium text-ink" htmlFor="rejection-reason">
              Rejection reason
            </label>
            <select
              id="rejection-reason"
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value as RejectionReason)}
              className={ratingInputClasses()}
            >
              {REJECTION_REASONS.map((reason) => (
                <option key={reason} value={reason}>
                  {REJECTION_REASON_LABELS[reason]}
                </option>
              ))}
            </select>
            <label className="mt-2 block text-xs font-medium text-ink" htmlFor="rejection-note">
              Internal note (never shown to the candidate)
            </label>
            <textarea
              id="rejection-note"
              value={rejectionNote}
              onChange={(e) => setRejectionNote(e.target.value)}
              rows={2}
              maxLength={2000}
              className={ratingInputClasses()}
              placeholder="Context for the hiring team only"
            />
          </div>
        )}

        {/* Additional Interview Details for HR */}
        {isHr && hrDecision === "additional_interview" && (
          <div className="mt-3 rounded-lg bg-indigo-50/60 border border-indigo-100 p-3.5 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-indigo-950">Scheduled Date &amp; Time (Optional)</label>
                <input
                  type="datetime-local"
                  value={additionalDate}
                  onChange={(e) => setAdditionalDate(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-indigo-950">Duration (Minutes)</label>
                <select
                  value={additionalDuration}
                  onChange={(e) => setAdditionalDuration(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                >
                  <option value={30}>30 minutes</option>
                  <option value={45}>45 minutes</option>
                  <option value={60}>60 minutes</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-indigo-950">Notes / Focus Areas for Next Round</label>
              <textarea
                value={additionalNotes}
                onChange={(e) => setAdditionalNotes(e.target.value)}
                rows={2}
                placeholder="Specific topics or competencies to re-evaluate..."
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-ink focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Optional Internal Note for Hire & Hold */}
        {isHr && (hrDecision === "hire" || hrDecision === "keep_on_hold") && (
          <div className="mt-3 rounded-lg bg-slate-50 p-3">
            <label className="block text-xs font-medium text-ink">
              Internal Hiring Note (Optional)
            </label>
            <textarea
              value={rejectionNote}
              onChange={(e) => setRejectionNote(e.target.value)}
              rows={2}
              maxLength={2000}
              className={ratingInputClasses()}
              placeholder="Internal record notes..."
            />
          </div>
        )}

        {error ? <p className="mt-3 text-sm text-rose-700">{error}</p> : null}

        <div className="mt-4 flex items-center gap-2">
          {isHr ? (
            <Button
              size="sm"
              variant={hrDecision === "reject" ? "danger" : "primary"}
              onClick={() => setConfirmModalOpen(true)}
              isLoading={deciding}
            >
              {hrDecision === "hire"
                ? "Confirm Hire Decision"
                : hrDecision === "reject"
                  ? "Confirm Rejection"
                  : hrDecision === "keep_on_hold"
                    ? "Keep on Hold"
                    : "Schedule Additional Round"}
            </Button>
          ) : (
            <Button
              size="sm"
              variant={recruiterDecision === "reject" ? "danger" : "primary"}
              onClick={() => void applyDecision()}
              isLoading={deciding}
            >
              {recruiterDecision === "reject" ? "Reject candidate" : "Advance candidate"}
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setStep("notes")}>
            Back to feedback
          </Button>
        </div>

        {/* Confirmation Modal for HR Decision */}
        {confirmModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl animate-fade-in space-y-4">
              <h3 className="text-base font-bold text-gray-900 border-b pb-2">
                {hrDecision === "hire"
                  ? "Confirm Hire Candidate"
                  : hrDecision === "reject"
                    ? "Confirm Candidate Rejection"
                    : hrDecision === "keep_on_hold"
                      ? "Confirm Keep on Hold"
                      : "Confirm Additional Interview"}
              </h3>
              <p className="text-sm text-gray-600">
                {hrDecision === "hire"
                  ? "Are you sure you want to hire this candidate? This will transition the application status to Hired and notify candidate, recruiter, and organization admin."
                  : hrDecision === "reject"
                    ? "Are you sure you want to reject this candidate? A formal notification will be sent."
                    : hrDecision === "keep_on_hold"
                      ? "Keep this candidate's application on hold under active review for future consideration?"
                      : "Schedule an additional HR evaluation interview round for this candidate?"}
              </p>
              <div className="flex justify-end gap-2 pt-2 border-t">
                <Button variant="ghost" onClick={() => setConfirmModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant={hrDecision === "reject" ? "danger" : "primary"}
                  onClick={() => void applyDecision()}
                  isLoading={deciding}
                >
                  Confirm &amp; Execute
                </Button>
              </div>
            </div>
          </div>
        )}
      </section>
    );
  }

  // ── Step 1: Evaluation Notes & Ratings ──
  return (
    <section
      className={`rounded-xl border border-slate-200/70 bg-white p-5 ${className}`}
      data-testid="interview-end-panel"
    >
      <h2 className="text-sm font-semibold text-ink">
        {isHr ? "HR Interview Evaluation" : "Interview feedback"}
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        {isHr
          ? "Evaluate the candidate across core competencies using the 1–5 scale. Save drafts as needed or submit feedback to record final decisions."
          : "The interview is recorded as completed. Your ratings and notes below are hiring-team evidence — the candidate never sees them."}
      </p>

      {draftNotice && (
        <div className="mt-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-1.5 text-xs text-blue-800 flex items-center justify-between">
          <span>{draftNotice}</span>
          <button
            type="button"
            onClick={() => setDraftNotice(null)}
            className="text-blue-500 hover:text-blue-700 font-bold ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {isHr ? (
        /* ── HR 1-5 Scale Evaluation ── */
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {/* Communication Skills */}
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-1.5">
                <span>Communication skills</span>
                <span className="text-purple-700 font-bold">{hrComm}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setHrComm(val)}
                    className={`flex-1 py-1 rounded text-xs font-bold transition ${hrComm === val ? "bg-purple-600 text-white" : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"}`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Technical Knowledge */}
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-1.5">
                <span>Technical knowledge</span>
                <span className="text-purple-700 font-bold">{hrTech}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setHrTech(val)}
                    className={`flex-1 py-1 rounded text-xs font-bold transition ${hrTech === val ? "bg-purple-600 text-white" : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"}`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Problem Solving */}
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-1.5">
                <span>Problem-solving</span>
                <span className="text-purple-700 font-bold">{hrProblem}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setHrProblem(val)}
                    className={`flex-1 py-1 rounded text-xs font-bold transition ${hrProblem === val ? "bg-purple-600 text-white" : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"}`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Teamwork */}
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-1.5">
                <span>Teamwork</span>
                <span className="text-purple-700 font-bold">{hrTeamwork}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setHrTeamwork(val)}
                    className={`flex-1 py-1 rounded text-xs font-bold transition ${hrTeamwork === val ? "bg-purple-600 text-white" : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"}`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Overall Performance */}
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50/50 sm:col-span-2 lg:col-span-2">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-1.5">
                <span>Overall performance</span>
                <span className="text-purple-700 font-bold">{hrOverall}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setHrOverall(val)}
                    className={`flex-1 py-1 rounded text-xs font-bold transition ${hrOverall === val ? "bg-purple-600 text-white" : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"}`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Strengths & Weaknesses */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-700">Observed Strengths</label>
              <textarea
                value={hrStrengths}
                onChange={(e) => setHrStrengths(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Key strengths, culture match, technical competency..."
                className={ratingInputClasses()}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700">Observed Weaknesses / Gaps</label>
              <textarea
                value={hrWeaknesses}
                onChange={(e) => setHrWeaknesses(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Identified skill gaps, hesitation, or concerns..."
                className={ratingInputClasses()}
              />
            </div>
          </div>

          {/* Comments & Recommendation */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-700">Final Recommendation</label>
              <select
                value={hrRecommendation}
                onChange={(e) => setHrRecommendation(e.target.value as HiringRecommendation)}
                className={ratingInputClasses()}
              >
                <option value="strongly_recommend">Strongly Recommend</option>
                <option value="recommend">Recommend</option>
                <option value="consider">Consider / Borderline</option>
                <option value="not_recommended">Not Recommended</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700">HR Comments</label>
              <textarea
                value={hrComments}
                onChange={(e) => setHrComments(e.target.value)}
                rows={2}
                maxLength={3000}
                placeholder="Qualitative notes and summary of discussion..."
                className={ratingInputClasses()}
              />
            </div>
          </div>
        </div>
      ) : (
        /* ── Recruiter Evaluation ── */
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {RATING_FIELDS.map(({ key, label }) => (
              <div key={key}>
                <label
                  htmlFor={`rating-${key}`}
                  className="flex items-center justify-between text-xs font-medium text-ink"
                >
                  {label}
                  <span className="text-ink-muted">{ratings[key]}</span>
                </label>
                <input
                  id={`rating-${key}`}
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={ratings[key]}
                  onChange={(e) =>
                    setRatings((current) => ({
                      ...current,
                      [key]: Number(e.target.value),
                    }))
                  }
                  className="mt-1 w-full"
                />
              </div>
            ))}
          </div>

          <div className="mt-3">
            <p className="text-xs font-medium text-ink">
              Recommendation:{" "}
              <span className="font-semibold">
                {HIRING_RECOMMENDATION_LABELS[recruiterRecommendation]}
              </span>
            </p>
            <p className="text-xs text-ink-muted">
              Derived from your ratings; it is saved with the feedback and is never
              shown to the candidate.
            </p>
          </div>

          <div className="mt-3">
            <label
              htmlFor="recruiter-notes"
              className="text-xs font-medium text-ink"
            >
              Notes (internal — not shown to the candidate)
            </label>
            <textarea
              id="recruiter-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              maxLength={5000}
              placeholder="What you observed: strengths, gaps, follow-ups…"
              className={ratingInputClasses()}
            />
          </div>
        </>
      )}

      {error ? <p className="mt-3 text-sm text-rose-700">{error}</p> : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {isHr ? (
          <>
            <Button
              size="sm"
              variant="outline"
              type="button"
              onClick={handleSaveHrDraft}
            >
              Save Draft
            </Button>
            <Button
              size="sm"
              onClick={() => void saveFeedback()}
              isLoading={saving}
            >
              Submit Feedback
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            onClick={() => void saveFeedback()}
            isLoading={saving}
          >
            Complete interview &amp; save feedback
          </Button>
        )}
      </div>
    </section>
  );
}
