import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { interviewApi } from "../../api/interview";
import { STATUS_COLORS } from "../../types/interview";
import type { InterviewListItem, InterviewDashboard } from "../../types/interview";

export function InterviewWorkspace() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<InterviewDashboard | null>(null);
  const [interviews, setInterviews] = useState<InterviewListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [dash, list] = await Promise.all([
          interviewApi.getDashboard(),
          interviewApi.listInterviews(),
        ]);
        setDashboard(dash);
        setInterviews(list.items);
      } catch {
        setError("Failed to load interview data");
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Interview Workspace</h1>
          <p className="mt-1 text-sm text-gray-500">Manage and track all interviews</p>
        </div>
        <button
          onClick={() => navigate("/recruiter/interviews/schedule")}
          className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          Schedule Interview
        </button>
      </div>

      {dashboard && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-xl bg-blue-50 p-4">
            <p className="text-xs font-medium text-blue-600">Total Interviews</p>
            <p className="mt-1 text-2xl font-bold text-blue-900">{dashboard.total_interviews}</p>
          </div>
          <div className="rounded-xl bg-green-50 p-4">
            <p className="text-xs font-medium text-green-600">Upcoming</p>
            <p className="mt-1 text-2xl font-bold text-green-900">{dashboard.upcoming_interviews}</p>
          </div>
          <div className="rounded-xl bg-purple-50 p-4">
            <p className="text-xs font-medium text-purple-600">Completed</p>
            <p className="mt-1 text-2xl font-bold text-purple-900">{dashboard.completed_interviews || 0}</p>
          </div>
          <div className="rounded-xl bg-amber-50 p-4">
            <p className="text-xs font-medium text-amber-600">Avg Score</p>
            <p className="mt-1 text-2xl font-bold text-amber-900">{dashboard.average_score || "—"}</p>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-5 py-3">
          <h2 className="font-semibold text-gray-900">All Interviews</h2>
        </div>
        {interviews.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">No interviews yet</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {interviews.map((iv) => {
              const joinable =
                iv.interview_type === "recruiter_scheduled" &&
                (iv.status === "scheduled" || iv.status === "in_progress");
              return (
                <div
                  key={iv.id}
                  onClick={() => navigate(`/recruiter/interviews/${iv.id}`)}
                  className="flex cursor-pointer items-center justify-between px-5 py-3 transition hover:bg-gray-50"
                >
                  <div>
                    <p className="font-medium text-gray-900">{iv.candidate_name}</p>
                    <p className="text-sm text-gray-500">{iv.job_title} · {iv.interview_type === "mock" ? "Mock" : "Scheduled"}</p>
                    <p className="text-xs text-gray-400">
                      {iv.scheduled_at
                        ? `${new Date(iv.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}${
                            iv.duration_minutes ? ` · ${iv.duration_minutes} minutes` : ""
                          }`
                        : "Not yet scheduled"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {joinable ? (
                      <button
                        onClick={(event) => {
                          // The row opens the detail page; this goes straight
                          // to the live room. The server re-checks the join
                          // window on the room page either way.
                          event.stopPropagation();
                          navigate(`/interviews/${iv.id}/room`);
                        }}
                        className="rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700"
                      >
                        Join Interview
                      </button>
                    ) : null}
                    {iv.overall_score !== null && (
                      <span className="font-bold text-primary-600">{iv.overall_score}</span>
                    )}
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[iv.status] || "bg-gray-100 text-gray-500"}`}>
                      {iv.status.replace("_", " ")}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
