import { Activity } from "lucide-react";

import type { ActivityItem } from "../../types/candidate";

interface ActivityFeedProps {
  activities: ActivityItem[];
}

const typeIcons: Record<string, string> = {
  welcome: "👋",
  profile_updated: "✏️",
  resume_uploaded: "📄",
  avatar_changed: "🖼️",
  new_feature: "✨",
};

export function ActivityFeed({ activities }: ActivityFeedProps) {
  if (activities.length === 0) {
    return (
      <div className="card p-5">
        <h3 className="section-title">Recent Activity</h3>
        <div className="mt-4 flex flex-col items-center rounded-xl border border-dashed border-gray-300/80 bg-white/40 px-4 py-10 text-center">
          <Activity className="mb-2 h-8 w-8 text-gray-300" aria-hidden="true" />
          <p className="text-sm text-gray-500">No recent activity</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <h3 className="section-title">Recent Activity</h3>
      <div className="mt-4 space-y-2">
        {activities.map((item, i) => (
          <div
            key={i}
            className="flex items-start gap-3 rounded-xl p-2 transition-colors hover:bg-primary-50/40"
          >
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-base"
              aria-hidden="true"
            >
              {typeIcons[item.type] || "📌"}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="text-sm font-medium text-gray-900">{item.title}</p>
              <p className="mt-0.5 text-xs text-gray-500">{item.message}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
