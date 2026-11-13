import { CheckCircle2, Calendar, Clock, Briefcase, Building2, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../ui/Button";
import { INTERVIEW_STAGE_LABELS, type InterviewRoomState } from "../../types/interview";

interface CandidateInterviewCompletionProps {
  room: InterviewRoomState;
  jobTitle?: string;
  companyName?: string;
  onRejoin?: () => void;
  canRejoin?: boolean;
}

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    dateStyle: "full",
    timeStyle: "short",
  });
}

export function CandidateInterviewCompletion({
  room,
  jobTitle = "Software Engineer",
  companyName = "HireCraft Partner Organization",
  onRejoin,
  canRejoin = false,
}: CandidateInterviewCompletionProps) {
  const navigate = useNavigate();

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6 animate-fadeIn font-sans">
      <div className="rounded-2xl border border-slate-200/90 bg-white p-8 shadow-sm text-center space-y-5">
        {/* Success Icon */}
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 border border-emerald-100 text-emerald-600 shadow-xs">
          <CheckCircle2 className="h-9 w-9" />
        </div>

        <div>
          <span className="text-xs uppercase font-bold tracking-widest text-emerald-600">
            Session Concluded
          </span>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">
            Thank You for Attending Your Interview
          </h1>
          <p className="text-sm text-slate-600 mt-1.5 max-w-lg mx-auto">
            The interview has ended. Thank you for your time — the hiring team will be in touch with next steps. Your attendance has been recorded in the HireCraft recruitment system.
          </p>
        </div>

        {/* Interview Summary Card */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-5 text-left space-y-3.5 text-xs max-w-md mx-auto">
          <div className="flex items-start gap-2.5">
            <Briefcase className="h-4 w-4 text-indigo-600 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700">Applied Role</span>
              <p className="text-slate-800 font-medium text-sm mt-0.5">{jobTitle}</p>
              <p className="text-slate-500 flex items-center gap-1 mt-0.5">
                <Building2 className="h-3 w-3" />
                {companyName}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Calendar className="h-4 w-4 text-indigo-600 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700">Interview Date & Time</span>
              <p className="text-slate-600 mt-0.5 font-medium">{formatWhen(room.scheduled_at)}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Clock className="h-4 w-4 text-indigo-600 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700">Stage & Duration</span>
              <p className="text-slate-600 mt-0.5 font-medium">
                {INTERVIEW_STAGE_LABELS[room.stage] ?? "Recruiter"} Evaluation • {room.duration_minutes || 60} mins
              </p>
            </div>
          </div>
        </div>

        {/* Next Steps Guidance */}
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-xs text-slate-700 max-w-md mx-auto text-left">
          <p className="font-semibold text-indigo-900">What Happens Next?</p>
          <p className="mt-1 text-slate-600 leading-relaxed">
            The interview team will review your session and record their feedback. You will receive an email notification and status update in your application tracker once the review is finalized.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2 max-w-md mx-auto">
          {canRejoin && onRejoin && (
            <Button
              variant="outline"
              size="md"
              className="flex-1 text-xs"
              onClick={onRejoin}
            >
              Re-enter Call Room
            </Button>
          )}

          <Button
            variant="primary"
            size="md"
            className="flex-1 text-xs gap-1.5 shadow-md shadow-indigo-600/20"
            onClick={() => navigate("/candidate/dashboard")}
          >
            <span>Back to Dashboard</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>

          <Button
            variant="secondary"
            size="md"
            className="flex-1 text-xs"
            onClick={() => navigate("/candidate/my-applications")}
          >
            My Applications
          </Button>
        </div>
      </div>
    </div>
  );
}
