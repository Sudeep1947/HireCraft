import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { IdentifierField } from "../../components/ui/IdentifierField";
import { assessmentApi } from "../../api/assessment";
import type { AttemptListItem } from "../../types/assessment";

const STATUS_STYLES: Record<string, string> = {
  assigned: "bg-amber-100 text-amber-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  expired: "bg-yellow-100 text-yellow-700",
};

/** Date and time a recruiter scheduled an assessment for, or null. */
function formatWhen(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function MyAssessments() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AttemptListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [joinId, setJoinId] = useState("");

  useEffect(() => {
    assessmentApi
      .myAttempts()
      .then((res) => setItems(res.items))
      .catch(() => setError("Failed to load your assessments"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (error) return <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Assessments</h1>
        <p className="mt-1 text-sm text-gray-500">
          Your assessment attempts and results
        </p>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <label className="block text-sm font-medium text-gray-700">
          Start a new assessment
          <p className="mb-2 text-xs font-normal text-gray-500">
            Paste the assessment link or ID your recruiter shared with you.
          </p>
        </label>
        <div className="flex gap-2">
          <input
            value={joinId}
            onChange={(e) => {
              const v = e.target.value.trim();
              const match = v.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
              setJoinId(match ? match[0] : v);
            }}
            placeholder="e.g. 6f1c2a3e-... or full take URL"
            className="grow rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
          />
          <button
            onClick={() => joinId && navigate(`/candidate/assessments/take/${joinId}`)}
            disabled={!joinId}
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40"
          >
            Start
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-12 text-center shadow-sm">
          <p className="text-gray-500">No attempts yet. Start an assessment above.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {["Assessment", "Status", "Score", "Result"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((it) => (
                <tr key={it.attempt_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{it.assessment_title}</p>
                    <p className="text-xs capitalize text-gray-500">{it.mode}</p>
                    {it.job_title ? (
                      <p className="text-xs text-gray-500">For {it.job_title}</p>
                    ) : null}
                    {formatWhen(it.scheduled_at) ? (
                      <p className="text-xs text-gray-500">
                        Scheduled {formatWhen(it.scheduled_at)}
                      </p>
                    ) : null}
                    {it.status === "assigned" && it.assessment_link ? (
                      <IdentifierField
                        label="Assessment link"
                        value={it.assessment_link}
                        copyable
                        size="sm"
                        className="mt-1"
                      />
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[it.status] || "bg-gray-100 text-gray-500"}`}>
                      {it.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-gray-700">
                    {it.overall_score !== null ? `${Math.round(it.overall_score)}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {it.status === "assigned" ? (
                      <button
                        onClick={() =>
                          navigate(
                            it.assessment_link ?? `/candidate/assessments/take/${it.assessment_id}`,
                          )
                        }
                        className="rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700"
                      >
                        Start assessment
                      </button>
                    ) : it.status === "in_progress" ? (
                      <button
                        onClick={() => navigate(`/candidate/assessments/take/${it.assessment_id}?resume=${it.attempt_id}`)}
                        className="rounded-lg bg-primary-50 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-100"
                      >
                        Resume
                      </button>
                    ) : it.submitted_at ? (
                      <button
                        onClick={() => navigate(`/candidate/assessments/results/${it.attempt_id}`)}
                        className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      >
                        View result
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
