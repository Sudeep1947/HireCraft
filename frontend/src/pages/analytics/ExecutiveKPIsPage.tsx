import { useEffect, useState } from "react";

import { analyticsApi } from "../../api/analytics";
import { KPICard } from "../../components/analytics/KPICard";
import { ChartCard } from "../../components/analytics/ChartCard";
import { DistributionBar } from "../../components/analytics/DistributionBar";
import { Briefcase, Building2 } from "lucide-react";
import type { ExecutiveKPIs } from "../../types/analytics";

export function ExecutiveKPIsPage() {
  const [data, setData] = useState<ExecutiveKPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyticsApi
      .getExecutiveKPIs()
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
          <h1 className="page-title">Executive KPIs</h1>
          <p className="page-subtitle">
            Business-level hiring efficiency, cost, and quality indicators.
          </p>
        </div>
        <span className="badge-primary self-start">
          <Briefcase className="h-3.5 w-3.5" aria-hidden="true" /> Leadership view
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KPICard label="Revenue per Hire" value={`$${data.revenue_per_hire.toLocaleString()}`} color="green" />
        <KPICard label="Cost per Hire" value={`$${data.cost_per_hire.toLocaleString()}`} color="yellow" />
        <KPICard label="Quality of Hire" value={data.quality_of_hire.toFixed(1)} unit="/100" color="primary" />
        <KPICard label="Time to Productivity" value={data.time_to_productivity} unit="days" color="blue" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard data={data.hiring_forecast} type="line" />
        <ChartCard data={data.quarterly_trends} />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="card p-5">
          <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-primary-50 p-1.5 text-primary-600">
              <Building2 className="h-4 w-4" aria-hidden="true" />
            </span>
            Department KPIs
          </h4>
          <div className="space-y-4">
            {data.department_kpis.map((d) => (
              <div key={d.label} className="flex items-center gap-3">
                <span className="w-28 shrink-0 truncate text-sm text-gray-700">{d.label}</span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary-500 to-violet-500 transition-all duration-500 ease-smooth"
                    style={{ width: `${d.value}%` }}
                  />
                </div>
                <span className="w-12 shrink-0 text-right text-sm font-semibold text-gray-600">
                  {d.value}%
                </span>
              </div>
            ))}
          </div>
        </div>
        <DistributionBar data={data.risk_indicators} title="Risk Indicators" />
      </div>
    </div>
  );
}
