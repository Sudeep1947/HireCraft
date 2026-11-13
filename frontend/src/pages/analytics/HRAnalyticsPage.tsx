import { useEffect, useState } from "react";

import { analyticsApi } from "../../api/analytics";
import { KPICard } from "../../components/analytics/KPICard";
import { ChartCard } from "../../components/analytics/ChartCard";
import { DistributionBar } from "../../components/analytics/DistributionBar";
import { StatusBreakdownChart } from "../../components/analytics/StatusBreakdownChart";
import { Users, BarChart3 } from "lucide-react";
import type { HRAnalytics } from "../../types/analytics";

export function HRAnalyticsPage() {
  const [data, setData] = useState<HRAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyticsApi
      .getHRAnalytics()
      .then(setData)
      .catch(() => setError("Failed to load analytics"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-8 w-56" />
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
          <h1 className="page-title">HR Analytics</h1>
          <p className="page-subtitle">
            Headcount, hiring funnel, and recruiter performance across the org.
          </p>
        </div>
        <span className="badge-primary self-start">
          <Users className="h-3.5 w-3.5" aria-hidden="true" /> People ops
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KPICard label="Headcount" value={data.total_headcount} color="blue" />
        <KPICard label="Open Positions" value={data.open_positions} color="green" />
        <KPICard label="Avg Time to Hire" value={data.avg_time_to_hire} unit="days" color="yellow" />
        <KPICard label="Diversity Index" value={data.diversity_index.toFixed(2)} color="purple" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard data={data.headcount_trend} type="line" />
        <StatusBreakdownChart data={data.hiring_funnel} title="Hiring Funnel" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <DistributionBar data={data.department_distribution} title="Department Distribution" />
        <DistributionBar data={data.gender_distribution} title="Gender Distribution" />
      </div>

      <div className="card p-5">
        <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
          <span className="rounded-lg bg-primary-50 p-1.5 text-primary-600">
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
          </span>
          Recruiter Performance
        </h4>
        <div className="space-y-4">
          {data.recruiter_performance.map((r) => (
            <div key={r.label} className="flex items-center gap-3">
              <span className="w-24 shrink-0 truncate text-sm text-gray-700">{r.label}</span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-primary-500 to-violet-500 transition-all duration-500 ease-smooth"
                  style={{ width: `${r.value}%` }}
                />
              </div>
              <span className="w-12 shrink-0 text-right text-sm font-semibold text-gray-600">
                {r.value}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
