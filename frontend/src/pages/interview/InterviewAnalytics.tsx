import { useCallback, useEffect, useState } from "react";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { interviewApi } from "../../api/interview";
import { getServerErrorMessage } from "../../utils/error";
import type { InterviewAnalytics } from "../../types/interview";

export function InterviewAnalyticsPage() {
  const [analytics, setAnalytics] = useState<InterviewAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await interviewApi.getAnalytics();
      setAnalytics(result);
    } catch (err) {
      // The server's own message when it sent one (403, 500 with detail); the
      // generic sentence only when it did not. The failure is shown with a
      // retry, never hidden.
      setError(getServerErrorMessage(err, "Failed to load analytics"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const header = (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Interview Analytics</h1>
      <p className="mt-1 text-sm text-gray-500">Comprehensive interview performance insights</p>
    </div>
  );

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  if (error) {
    return (
      <div className="space-y-6">
        {header}
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
          <p>{error}</p>
          <button
            onClick={load}
            className="mt-3 rounded-lg bg-white px-3 py-1.5 font-medium text-red-700 shadow-sm ring-1 ring-inset ring-red-200 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!analytics) return null;

  // No interviews yet: an honest empty state rather than a wall of zeroes --
  // there is nothing to average, and none of the numbers below would mean
  // anything yet. Every figure on this page comes from the caller's own
  // interview records; nothing here is filled in on their behalf.
  if (analytics.total_interviews === 0) {
    return (
      <div className="space-y-6">
        {header}
        <div className="rounded-xl border border-gray-200 bg-white p-12 text-center shadow-sm">
          <p className="font-medium text-gray-900">No interviews yet</p>
          <p className="mt-1 text-sm text-gray-500">
            Statistics, score distributions and trends appear here once interviews
            have been scheduled and completed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {header}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-xl bg-blue-50 p-4">
          <p className="text-xs font-medium text-blue-600">Total Interviews</p>
          <p className="mt-1 text-2xl font-bold text-blue-900">{analytics.total_interviews}</p>
        </div>
        <div className="rounded-xl bg-green-50 p-4">
          <p className="text-xs font-medium text-green-600">Completion Rate</p>
          <p className="mt-1 text-2xl font-bold text-green-900">{analytics.completion_rate}%</p>
        </div>
        <div className="rounded-xl bg-purple-50 p-4">
          <p className="text-xs font-medium text-purple-600">Average Score</p>
          <p className="mt-1 text-2xl font-bold text-purple-900">{analytics.average_score}</p>
        </div>
        <div className="rounded-xl bg-amber-50 p-4">
          <p className="text-xs font-medium text-amber-600">Median Score</p>
          <p className="mt-1 text-2xl font-bold text-amber-900">{analytics.median_score}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 font-semibold text-gray-900">Score Distribution</h3>
          <div className="space-y-3">
            {Object.entries(analytics.score_distribution).map(([key, count]) => {
              const labels: Record<string, string> = {
                excellent: "Excellent (80+)",
                good: "Good (65-79)",
                average: "Average (45-64)",
                below_average: "Below Average (<45)",
              };
              const colors: Record<string, string> = {
                excellent: "bg-green-500",
                good: "bg-blue-500",
                average: "bg-amber-500",
                below_average: "bg-red-500",
              };
              const total = Object.values(analytics.score_distribution).reduce((a, b) => a + b, 0) || 1;
              return (
                <div key={key}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">{labels[key] || key}</span>
                    <span className="font-medium text-gray-900">{count}</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
                    <div
                      className={`h-full rounded-full ${colors[key] || "bg-gray-400"}`}
                      style={{ width: `${(count / total) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 font-semibold text-gray-900">Category Averages</h3>
          {Object.keys(analytics.category_averages).length === 0 ? (
            <p className="text-sm text-gray-500">No category data yet</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(analytics.category_averages).map(([cat, avg]) => (
                <div key={cat}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize text-gray-600">{cat.replace(/_/g, " ")}</span>
                    <span className="font-medium text-gray-900">{avg}</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
                    <div
                      className="h-full rounded-full bg-primary-500"
                      style={{ width: `${avg}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 font-semibold text-gray-900">Recommendation Breakdown</h3>
          <div className="space-y-2">
            {Object.entries(analytics.recommendation_breakdown).map(([key, count]) => {
              const labels: Record<string, string> = {
                strongly_recommend: "Strongly Recommend",
                recommend: "Recommend",
                consider: "Consider",
                not_recommended: "Not Recommended",
              };
              return (
                <div key={key} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                  <span className="text-sm text-gray-600">{labels[key] || key}</span>
                  <span className="font-semibold text-gray-900">{count}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 font-semibold text-gray-900">Hiring Prediction</h3>
          {Object.keys(analytics.hiring_prediction).length === 0 ? (
            <p className="text-sm text-gray-500">No prediction data yet</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(analytics.hiring_prediction).map(([key, pct]) => {
                const labels: Record<string, string> = {
                  likely_hire_pct: "Likely Hire",
                  needs_review_pct: "Needs Review",
                  unlikely_hire_pct: "Unlikely Hire",
                };
                const colors: Record<string, string> = {
                  likely_hire_pct: "bg-green-500",
                  needs_review_pct: "bg-amber-500",
                  unlikely_hire_pct: "bg-red-500",
                };
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">{labels[key] || key}</span>
                      <span className="font-medium text-gray-900">{pct}%</span>
                    </div>
                    <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
                      <div
                        className={`h-full rounded-full ${colors[key] || "bg-gray-400"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
