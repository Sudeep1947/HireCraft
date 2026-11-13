import { useEffect, useState } from "react";

import { analyticsApi } from "../../api/analytics";
import { KPICard } from "../../components/analytics/KPICard";
import { ChartCard } from "../../components/analytics/ChartCard";
import { DistributionBar } from "../../components/analytics/DistributionBar";
import { Rocket, ArrowRight } from "lucide-react";
import type { RecruiterAnalytics } from "../../types/analytics";

export function RecruiterAnalytics() {
  const [data, setData] = useState<RecruiterAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyticsApi
      .getRecruiterAnalytics()
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
          <h1 className="page-title">Recruiter Analytics</h1>
          <p className="page-subtitle">
            Your open roles, applicant pipeline, and sourcing effectiveness.
          </p>
        </div>
        <span className="badge-primary self-start">
          <Rocket className="h-3.5 w-3.5" aria-hidden="true" /> Recruiter view
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KPICard label="Active Jobs" value={data.active_jobs} color="green" />
        <KPICard label="Total Applicants" value={data.total_applicants} color="blue" />
        <KPICard label="Avg Time to Fill" value={data.avg_time_to_fill} unit="days" color="yellow" />
        <KPICard label="Hire Rate" value={`${(data.hire_rate * 100).toFixed(0)}%`} color="primary" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard data={data.applicants_trend} type="line" />
        <DistributionBar data={data.source_effectiveness} title="Source Effectiveness" />
      </div>

      <div className="card p-5">
        <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
          <span className="rounded-lg bg-violet-50 p-1.5 text-violet-600">
            <Rocket className="h-4 w-4" aria-hidden="true" />
          </span>
          Pipeline Velocity
        </h4>
        <div className="flex items-center gap-4">
          {data.pipeline_velocity.map((step, i) => (
            <div key={step.label} className="flex-1 text-center">
              <div className="rounded-xl bg-primary-50/70 px-2 py-3 ring-1 ring-inset ring-primary-100">
                <div className="font-display text-2xl font-bold text-primary-600">{step.value}</div>
                <div className="mt-1 text-xs text-gray-500">{step.label}</div>
              </div>
              {i < data.pipeline_velocity.length - 1 && (
                <ArrowRight
                  className="mx-auto mt-2 h-4 w-4 text-gray-300"
                  aria-hidden="true"
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
