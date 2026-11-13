import { useState, useEffect } from "react";
import { getMyFairness } from "../../api/fairness";
import { FairnessScoreCard, FairnessProgressBar } from "../../components/fairness/FairnessComponents";
import type { CandidateFairness } from "../../types/fairness";

export function CandidateFairness() {
  const [data, setData] = useState<CandidateFairness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const result = await getMyFairness();
        setData(result);
      } catch {
        setError("Failed to load fairness data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-72" />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div className="skeleton h-48 w-full" />
          <div className="skeleton h-48 w-full" />
          <div className="skeleton h-48 w-full" />
        </div>
        <div className="skeleton h-44 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="error-banner">{error || "No data available."}</div>
      </div>
    );
  }

  const statusColor =
    data.fairness_status === "evaluated"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : "bg-amber-50 text-amber-800 border-amber-200";

  return (
    <div className="mx-auto max-w-4xl space-y-8 animate-fade-up">
      <div>
        <h1 className="page-title">Fairness & Transparency</h1>
        <p className="page-subtitle">
          View your fairness status and how AI evaluates candidates.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <div className="flex justify-center">
          <FairnessScoreCard
            score={data.average_score || 0}
            label="Your Average Score"
          />
        </div>
        <div className="space-y-4">
          <div className="card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Status</p>
            <span className={`mt-1.5 inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${statusColor}`}>
              {data.fairness_status === "evaluated" ? "Evaluated" : "Pending"}
            </span>
          </div>
          <div className="card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Total Evaluations</p>
            <p className="mt-1 font-display text-2xl font-bold text-gray-900">{data.total_evaluations}</p>
          </div>
        </div>
        <div className="space-y-4">
          <div className="card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Bias Checks</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {data.bias_checks_completed ? "Completed" : "Not Yet Completed"}
            </p>
          </div>
          <div className="card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Last Evaluation</p>
            <p className="mt-1 text-sm text-gray-700">
              {data.last_evaluation_date
                ? new Date(data.last_evaluation_date).toLocaleDateString()
                : "N/A"}
            </p>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="section-title mb-4">Evaluation Transparency</h2>
        <div className="space-y-3">
          {data.transparency_summary.map((item, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
              <p className="text-sm text-gray-700">{item}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="section-title mb-4">Protected Attributes</h2>
        <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/80 p-4 shadow-xs">
          <p className="text-sm font-semibold text-emerald-800">
            No protected attributes are used in AI evaluations.
          </p>
          <p className="mt-1 text-sm text-emerald-700">
            Your gender, age, ethnicity, religion, nationality, disability status,
            sexual orientation, and marital status are never used in scoring decisions.
            All evaluations are based purely on skills, experience, and qualifications.
          </p>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="section-title mb-4">Your Rights</h2>
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-500" />
            <div>
              <p className="text-sm font-semibold text-gray-900">Appeal / Review Request</p>
              <p className="text-sm text-gray-600">
                You can request a human review of any AI-powered decision.
                Contact your recruiter or HR team to submit an appeal.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-500" />
            <div>
              <p className="text-sm font-semibold text-gray-900">Data Transparency</p>
              <p className="text-sm text-gray-600">
                You can request a copy of the data used in your evaluation at any time.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-500" />
            <div>
              <p className="text-sm font-semibold text-gray-900">Fair Evaluation</p>
              <p className="text-sm text-gray-600">
                All candidates are evaluated using the same criteria.
                Our fairness engine continuously monitors for bias.
              </p>
            </div>
          </div>
        </div>
      </div>

      {data.total_evaluations > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-4">Score Overview</h2>
          <FairnessProgressBar value={data.average_score} label="Average Match Score" />
        </div>
      )}
    </div>
  );
}
