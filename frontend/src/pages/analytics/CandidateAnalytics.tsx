import { useEffect, useState } from "react";

import { analyticsApi } from "../../api/analytics";
import { KPICard } from "../../components/analytics/KPICard";
import { ChartCard } from "../../components/analytics/ChartCard";
import { DistributionBar } from "../../components/analytics/DistributionBar";
import { StatusBreakdownChart } from "../../components/analytics/StatusBreakdownChart";
import { TrendingUp, Target } from "lucide-react";
import type { CandidatePerformance } from "../../types/analytics";

export function CandidateAnalytics() {
  const [data, setData] = useState<CandidatePerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyticsApi
      .getCandidatePerformance()
      .then(setData)
      .catch(() => setError("Failed to load analytics"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-8 w-64" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-28 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="skeleton h-64 w-full" />
          <div className="skeleton h-64 w-full" />
        </div>
      </div>
    );
  }
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">My Performance Analytics</h1>
          <p className="page-subtitle">
            Your scores, skill match, and application outcomes over time.
          </p>
        </div>
        <span className="badge-primary self-start">
          <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" /> Live
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KPICard label="Overall Score" value={data.overall_score} unit="/100" color="primary" />
        <KPICard label="Skill Match" value={data.skill_match_pct} unit="%" color="green" />
        <KPICard label="Interview Avg" value={data.interview_avg_score} unit="/100" color="blue" />
        <KPICard label="Rank Percentile" value={`P${data.rank_percentile.toFixed(0)}`} color="purple" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard data={data.score_trend} type="line" />
        <StatusBreakdownChart data={data.applications_by_status} title="Applications by Status" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <DistributionBar data={data.strongest_skills} title="Top Skills" />
        <div className="card p-5">
          <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-amber-50 p-1.5 text-amber-600">
              <Target className="h-4 w-4" aria-hidden="true" />
            </span>
            Improvement Areas
          </h4>
          <ul className="space-y-2">
            {data.improvement_areas.map((area) => (
              <li
                key={area}
                className="flex items-center gap-2.5 rounded-lg bg-amber-50/60 px-3 py-2 text-sm text-gray-700 ring-1 ring-inset ring-amber-200/50"
              >
                <span className="h-2 w-2 shrink-0 rounded-full bg-amber-400" />
                {area}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
