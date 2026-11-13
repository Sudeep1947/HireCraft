import { useEffect, useState } from "react";

import { analyticsApi } from "../../api/analytics";
import { KPICard } from "../../components/analytics/KPICard";
import { ChartCard } from "../../components/analytics/ChartCard";
import { DistributionBar } from "../../components/analytics/DistributionBar";
import { ShieldCheck, Server, HardDrive, Activity } from "lucide-react";
import type { AdminAnalytics } from "../../types/analytics";

export function AdminAnalyticsPage() {
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyticsApi
      .getAdminAnalytics()
      .then(setData)
      .catch(() => setError("Failed to load analytics"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-8 w-72" />
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
          <h1 className="page-title">System Administration Analytics</h1>
          <p className="page-subtitle">
            Platform health, security events, and infrastructure load at a glance.
          </p>
        </div>
        <span className="badge-primary self-start">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Super admin
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KPICard label="Total Users" value={data.total_users} color="blue" />
        <KPICard label="Active Users" value={data.active_users} color="green" />
        <KPICard label="System Health" value={`${data.system_health_score}%`} color="green" />
        <KPICard label="API Calls Today" value={data.api_calls_today} color="purple" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard data={data.users_trend} type="line" />
        <DistributionBar data={data.users_by_role} title="Users by Role" />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="card p-5">
          <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-red-50 p-1.5 text-red-600">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </span>
            Security Events
          </h4>
          <div className="space-y-2">
            {data.security_events.map((e) => (
              <div
                key={e.label}
                className="flex items-center justify-between rounded-lg bg-gray-50/80 px-3 py-2 text-sm transition-colors hover:bg-primary-50/50"
              >
                <span className="text-gray-600">{e.label}</span>
                <span className="font-semibold text-gray-800">{e.value}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-5">
          <h4 className="section-title mb-4 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-amber-50 p-1.5 text-amber-600">
              <Activity className="h-4 w-4" aria-hidden="true" />
            </span>
            System Load
          </h4>
          <div className="space-y-4">
            {data.system_load.map((l) => (
              <div key={l.label} className="flex items-center gap-3">
                <span className="w-16 text-sm text-gray-700">{l.label}</span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ease-smooth ${
                      l.value > 80
                        ? "bg-gradient-to-r from-rose-500 to-red-500"
                        : l.value > 60
                          ? "bg-gradient-to-r from-amber-400 to-amber-500"
                          : "bg-gradient-to-r from-emerald-400 to-emerald-500"
                    }`}
                    style={{ width: `${l.value}%` }}
                  />
                </div>
                <span className="w-12 text-right text-sm font-semibold text-gray-600">
                  {l.value}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel-brand flex items-center gap-4 p-5">
        <span className="rounded-xl bg-white/80 p-2.5 text-primary-600 shadow-xs">
          <HardDrive className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h4 className="text-sm font-semibold text-gray-900">Storage</h4>
          <p className="text-sm text-gray-500">Used: {data.storage_used_mb} MB</p>
        </div>
        <Server className="ml-auto h-5 w-5 text-primary-400" aria-hidden="true" />
      </div>
    </div>
  );
}
