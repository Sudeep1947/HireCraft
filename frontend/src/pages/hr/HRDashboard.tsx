import { useEffect, useState } from "react";

import { useToast } from "../../contexts/ToastContext";
import { useAuth } from "../../hooks/useAuth";
import { dashboardApi } from "../../api/dashboard";
import type { HRDashboardData } from "../../api/dashboard";
import {
  StatCard,
  DashboardCard,
  PipelineCard,
  ActivityCard,
  QuickActions,
  InfoRow,
} from "../../components/dashboard";

const SvgIcons = {
  positions: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A18.18 18.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
  ),
  candidates: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  ),
  recruiters: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
    </svg>
  ),
  time: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
};

export function HRDashboard() {
  const { user } = useAuth();
  const { addToast } = useToast();
  const [data, setData] = useState<HRDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi
      .getHR()
      .then(setData)
      .catch(() => addToast("Failed to load dashboard", "error"))
      .finally(() => setLoading(false));
  }, [addToast]);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-9 w-52" />
          <div className="skeleton h-4 w-56" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((tile) => (
            <div key={tile} className="skeleton h-32" />
          ))}
        </div>
        <div className="skeleton h-56 w-full" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="skeleton h-72" />
          <div className="skeleton h-72" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load dashboard</span>
        </div>
      </div>
    );
  }

  const deptHiring = data.department_hiring.map((d) => ({
    id: (d as Record<string, unknown>).department as string,
    name: (d as Record<string, unknown>).department as string,
    subtitle: `${(d as Record<string, unknown>).count as number} positions`,
    badge: {
      label: "Active",
      color: "bg-green-100 text-green-700",
    },
  }));

  const activityItems = data.recent_activity.slice(0, 5).map((a) => ({
    id: String(Math.random()),
    title: (a as Record<string, unknown>).action as string || "Activity",
    description: (a as Record<string, unknown>).description as string || "",
    time: (a as Record<string, unknown>).time as string || "",
    type: "info" as const,
  }));

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">HR Dashboard</h1>
          <p className="page-subtitle">{`Welcome back, ${user?.full_name ?? "HR Manager"}`}</p>
        </div>
        <div className="flex gap-2">
          <a href="/hr/pipeline" className="btn-primary btn-md">
            View Pipeline
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Open Positions" value={data.open_positions} color="primary" icon={SvgIcons.positions} />
        <StatCard title="Total Candidates" value={data.total_candidates} color="green" icon={SvgIcons.candidates} />
        <StatCard title="Recruiters" value={data.total_recruiters} color="blue" icon={SvgIcons.recruiters} />
        <StatCard
          title="Avg Time to Hire"
          value={data.time_to_hire_avg > 0 ? `${data.time_to_hire_avg.toFixed(1)}d` : "N/A"}
          color="purple"
          icon={SvgIcons.time}
        />
      </div>

      <PipelineCard
        title="Hiring Funnel"
        stages={data.hiring_funnel}
        color="purple"
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DashboardCard title="Department Hiring" className="rounded-xl">
          {deptHiring.length > 0 ? (
            <div className="space-y-2">
              {deptHiring.map((dept) => (
                <div
                  key={dept.id}
                  className="flex items-center justify-between rounded-xl border border-gray-100 bg-gray-50/70 p-3"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-700">{dept.name}</p>
                    <p className="text-xs text-gray-500">{dept.subtitle}</p>
                  </div>
                  <span className={`badge-success ${dept.badge.color}`}>{dept.badge.label}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No department data available.</p>
          )}
        </DashboardCard>

        <ActivityCard
          title="Recent Activity"
          items={activityItems}
          emptyMessage="No recent activity."
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <DashboardCard title="Recruitment Overview" className="rounded-xl">
          <InfoRow
            items={[
              { label: "Open Positions", value: data.open_positions },
              { label: "Total Candidates", value: data.total_candidates },
              { label: "Active Recruiters", value: data.total_recruiters },
              { label: "Avg Time to Hire", value: data.time_to_hire_avg > 0 ? `${data.time_to_hire_avg.toFixed(1)} days` : "N/A" },
            ]}
          />
        </DashboardCard>

        <QuickActions
          title="Quick Actions"
          actions={[
            { label: "View recruitment pipeline", href: "/hr/pipeline" },
            { label: "Review pending applications", href: "/hr/pipeline" },
          ]}
        />
      </div>
    </div>
  );
}
