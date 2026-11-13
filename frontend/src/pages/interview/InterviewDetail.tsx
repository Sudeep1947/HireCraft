import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { IdentifierGrid } from "../../components/ui/IdentifierField";
import { QuestionCard } from "../../components/interview/QuestionCard";
import { FeedbackCard } from "../../components/interview/FeedbackCard";
import { ScorecardView } from "../../components/interview/ScorecardView";
import { InterviewTimeline } from "../../components/interview/InterviewTimeline";
import { interviewApi } from "../../api/interview";
import { useAuth } from "../../hooks/useAuth";
import { STATUS_COLORS } from "../../types/interview";
import type { InterviewDetail } from "../../types/interview";

const TIMELINE_STEPS = ["scheduled", "in_progress", "completed"];

export function InterviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [interview, setInterview] = useState<InterviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Staff see the full identity of the record; a candidate sees their own
  // interview and application references. This mirrors the server's narrowing
  // of the rest of the payload rather than widening it.
  const isStaff = Boolean(
    user?.roles?.some((role) => ["recruiter", "hr", "hr_manager", "organization_admin", "admin", "super_admin"].includes(role)),
  );

  useEffect(() => {
    if (!id) return;
    async function load() {
      try {
        const result = await interviewApi.getInterviewDetail(id!);
        setInterview(result);
      } catch {
        setError("Failed to load interview details");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (error) return <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">{error}</div>;
  if (!interview) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate(-1)} className="mb-2 text-sm text-primary-600 hover:text-primary-700">
            ← Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{interview.job_title || "Interview"}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {interview.candidate_name} · {interview.interview_type === "mock" ? "Mock" : "Scheduled"}
          </p>
        </div>
        <span className={`inline-flex rounded-full px-3 py-1 text-sm font-medium ${STATUS_COLORS[interview.status] || "bg-gray-100 text-gray-500"}`}>
          {interview.status.replace("_", " ")}
        </span>
      </div>

      <InterviewTimeline steps={TIMELINE_STEPS} currentStatus={interview.status} />

      {/* The four identifiers of this interview, labelled. The page is reached
          for both the candidate and the recruiter, so the fields are chosen by
          role: a candidate sees their own interview, application and job
          reference, while the candidate and recruiter account identifiers are
          only listed for staff. Nothing shown here is a score, a note or a
          decision -- these are names for the record, and the server has already
          narrowed the rest of this payload for the role. */}
      <section
        className="rounded-lg border border-gray-200 bg-white p-4"
        data-testid="interview-identifiers"
      >
        <h2 className="text-sm font-semibold text-gray-900">Identifiers</h2>
        <IdentifierGrid
          className="mt-2"
          columns={2}
          items={[
            { label: "Interview ID", value: interview.id, copyable: true },
            { label: "Job ID", value: interview.job_id, copyable: true },
            {
              label: "Application ID",
              value: interview.application_id,
              hint: interview.application_id
                ? "The application this interview was scheduled from."
                : undefined,
              copyable: true,
            },
            ...(isStaff
              ? [
                  {
                    label: "Candidate ID",
                    value: interview.candidate_id,
                    copyable: true,
                  },
                ]
              : []),
            ...(isStaff && interview.recruiter_id
              ? [
                  {
                    label: "Recruiter ID",
                    value: interview.recruiter_id,
                    copyable: true,
                  },
                ]
              : []),
          ]}
        />
        {isStaff && !interview.application_id ? (
          <p className="mt-2 text-xs text-gray-500">
            This interview is not linked to an application — it is a practice
            interview, or it predates application-driven scheduling.
          </p>
        ) : null}
      </section>

      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg bg-gray-50 p-3 text-center">
          <p className="text-lg font-bold text-gray-900">{interview.questions_answered}/{interview.total_questions}</p>
          <p className="text-xs text-gray-500">Questions</p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 text-center">
          <p className="text-lg font-bold text-gray-900">{interview.duration_minutes || "—"}</p>
          <p className="text-xs text-gray-500">Minutes</p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 text-center">
          <p className="text-lg font-bold text-gray-900">
            {interview.scorecard?.overall_score || "—"}
          </p>
          <p className="text-xs text-gray-500">Score</p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 text-center">
          <p className="text-lg font-bold text-gray-900">
            {interview.scorecard?.hiring_confidence ? `${interview.scorecard.hiring_confidence}%` : "—"}
          </p>
          <p className="text-xs text-gray-500">Confidence</p>
        </div>
      </div>

      {interview.scorecard && <ScorecardView scorecard={interview.scorecard} />}

      <div>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Questions & Answers</h2>
        <div className="space-y-4">
          {interview.questions.map((qa, idx) => (
            <div key={qa.id} className="space-y-3">
              <QuestionCard question={qa} index={idx} />
              {qa.answer && (
                <div className="ml-4 rounded-lg border border-gray-100 bg-gray-50 p-4">
                  <p className="mb-2 text-xs font-medium text-gray-500">Answer</p>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{qa.answer.answer_text}</p>
                  {qa.answer.time_taken_seconds && (
                    <p className="mt-2 text-xs text-gray-400">
                      Time: {Math.floor(qa.answer.time_taken_seconds / 60)}m {qa.answer.time_taken_seconds % 60}s
                    </p>
                  )}
                </div>
              )}
              {qa.answer?.evaluation && <FeedbackCard evaluation={qa.answer.evaluation} />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
