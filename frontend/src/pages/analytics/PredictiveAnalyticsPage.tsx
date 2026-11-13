import { useEffect, useState } from "react";

import { analyticsApi } from "../../api/analytics";
import { ChartCard } from "../../components/analytics/ChartCard";
import { DistributionBar } from "../../components/analytics/DistributionBar";
import { Sparkles, Gauge } from "lucide-react";
import type { PredictiveAnalytics } from "../../types/analytics";

export function PredictiveAnalyticsPage() {
  const [data, setData] = useState<PredictiveAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyticsApi
      .getPredictions()
      .then(setData)
      .catch(() => setError("Failed to load predictions"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-8 w-64" />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="skeleton h-64 w-full" />
          <div className="skeleton h-64 w-full" />
        </div>
        <div className="skeleton h-40 w-full" />
      </div>
    );
  }
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Predictive Analytics</h1>
          <p className="page-subtitle">
            AI forecasts for demand, attrition risk, skill gaps, and budget.
          </p>
        </div>
        <span className="badge-primary self-start">
          <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
          Confidence: {data.confidence_score.toFixed(0)}%
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard data={data.demand_forecast} type="line" />
        <ChartCard data={data.hiring_timeline} type="line" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="card p-5">
          <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-red-50 p-1.5 text-red-600">
              <Gauge className="h-4 w-4" aria-hidden="true" />
            </span>
            Attrition Risk by Department
          </h4>
          <div className="space-y-4">
            {data.attrition_risk.map((r) => (
              <div key={r.label} className="flex items-center gap-3">
                <span className="w-24 shrink-0 truncate text-sm text-gray-700">{r.label}</span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ease-smooth ${
                      r.value > 60
                        ? "bg-gradient-to-r from-rose-500 to-red-500"
                        : r.value > 40
                          ? "bg-gradient-to-r from-amber-400 to-amber-500"
                          : "bg-gradient-to-r from-emerald-400 to-emerald-500"
                    }`}
                    style={{ width: `${r.value}%` }}
                  />
                </div>
                <span className="w-12 shrink-0 text-right text-sm font-semibold text-gray-600">
                  {r.value.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
        <DistributionBar data={data.skill_gap_forecast} title="Skill Gap Forecast" />
      </div>

      <div className="panel-brand p-5">
        <h4 className="section-title mb-3 flex items-center gap-2 text-sm">
          <span className="rounded-lg bg-white/80 p-1.5 text-primary-600 shadow-xs">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          AI Recommendations
        </h4>
        <ul className="space-y-2">
          {data.recommendations.map((rec, i) => (
            <li
              key={i}
              className="flex items-start gap-2.5 rounded-lg bg-white/70 px-3 py-2 text-sm text-gray-700 ring-1 ring-inset ring-white/60"
            >
              <span className="mt-0.5 font-bold text-primary-500">•</span>
              {rec}
            </li>
          ))}
        </ul>
      </div>

      <ChartCard data={data.budget_projection} />
    </div>
  );
}
