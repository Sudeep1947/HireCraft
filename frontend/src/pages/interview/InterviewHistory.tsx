import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { interviewApi } from "../../api/interview";
import { STATUS_COLORS } from "../../types/interview";
import type { InterviewListItem } from "../../types/interview";

/** Live, recruiter-scheduled interviews are joinable straight from this list:
 *  the server still decides the actual join window when the button is pressed
 *  (and again on the room page), so this only decides whether to offer it. */
function isJoinable(iv: InterviewListItem): boolean {
  return (
    iv.interview_type === "recruiter_scheduled" &&
    (iv.status === "scheduled" || iv.status === "in_progress")
  );
}

function formatScheduled(iv: InterviewListItem): string | null {
  if (!iv.scheduled_at) return null;
  const parsed = new Date(iv.scheduled_at);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function InterviewHistory() {
  const navigate = useNavigate();
  const [interviews, setInterviews] = useState<InterviewListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        // The endpoint returns only the logged-in candidate's own interviews;
        // there is no way to ask for someone else's, and no meeting ID to
        // type — opening one is just this navigation.
        const result = await interviewApi.listInterviews();
        setInterviews(result.items);
      } catch {
        setError("Failed to load interview history");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (error) return <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Interview History</h1>
        <p className="mt-1 text-sm text-gray-500">View all your past and upcoming interviews</p>
      </div>

      {interviews.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-12 text-center shadow-sm">
          <p className="text-gray-500">No interviews yet. Start a mock interview to begin!</p>
          <button
            onClick={() => navigate("/candidate/mock-interview")}
            className="mt-4 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Start Mock Interview
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {interviews.map((iv) => {
            const when = formatScheduled(iv);
            return (
              <div
                key={iv.id}
                onClick={() => navigate(`/candidate/interviews/${iv.id}`)}
                className="cursor-pointer rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-gray-900">{iv.job_title || "Interview"}</h3>
                    <p className="text-sm text-gray-500">
                      {iv.interview_type === "mock" ? "Mock Interview" : "Scheduled Interview"}
                      {iv.recruiter_name ? ` · with ${iv.recruiter_name}` : ""}
                      {" · "}
                      {iv.questions_answered}/{iv.total_questions} questions answered
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {iv.overall_score !== null && (
                      <span className="text-lg font-bold text-primary-600">{iv.overall_score}</span>
                    )}
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[iv.status] || "bg-gray-100 text-gray-500"}`}>
                      {iv.status.replace("_", " ")}
                    </span>
                  </div>
                </div>

                <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-gray-400">
                    {when ? (
                      <>
                        {when}
                        {iv.duration_minutes ? ` · ${iv.duration_minutes} minutes` : ""}
                      </>
                    ) : (
                      new Date(iv.created_at).toLocaleDateString()
                    )}
                  </p>

                  {isJoinable(iv) ? (
                    <button
                      onClick={(event) => {
                        // The row itself navigates to the detail page; this
                        // button goes straight to the live room instead.
                        event.stopPropagation();
                        navigate(`/interviews/${iv.id}/room`);
                      }}
                      className="rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700"
                    >
                      Join Interview
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
