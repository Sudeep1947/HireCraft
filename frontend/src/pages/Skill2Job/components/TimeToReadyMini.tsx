import { Clock, DollarSign } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function TimeToReadyMini({ overview }: { overview: Skill2JobOverview }) {
  const items = overview.time_to_ready?.items ?? [];

  if (items.length === 0) {
    return (
      <div className="card p-6">
        <div className="mb-3 flex items-center gap-3">
          <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
            <Clock className="h-5 w-5" aria-hidden="true" />
          </span>
          <h2 className="section-title">Time to Ready</h2>
        </div>
        <p className="text-sm text-gray-500">Select a target job to see your preparation timeline.</p>
      </div>
    );
  }

  const top = items[0];

  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
          <Clock className="h-5 w-5" aria-hidden="true" />
        </span>
        <h2 className="section-title">Time to Ready</h2>
      </div>
      <div className="mb-4 rounded-xl border border-primary-100 bg-primary-50/60 p-3">
        <div className="section-label text-primary-600">Target Job</div>
        <div className="mt-0.5 font-semibold text-gray-900">{top.job_title}</div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50/80 p-3 shadow-xs">
          <span className="rounded-lg bg-white p-2 text-primary-600 shadow-xs">
            <Clock className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <div className="text-xs text-gray-500">Estimated Time</div>
            <div className="font-display font-bold text-gray-900">{top.estimated_weeks} weeks</div>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50/80 p-3 shadow-xs">
          <span className="rounded-lg bg-white p-2 text-emerald-600 shadow-xs">
            <DollarSign className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <div className="text-xs text-gray-500">Estimated Cost</div>
            <div className="font-display font-bold text-gray-900">
              {top.currency ?? "USD"} {top.estimated_cost}
            </div>
          </div>
        </div>
      </div>
      <div className="mt-4">
        <div className="section-label mb-2">
          Skills to Learn · {top.missing_skills_count} gap(s)
        </div>
        <div className="space-y-1">
          {items.slice(0, 3).map((item) => (
            <div
              key={item.job_id}
              className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-gray-50"
            >
              <span className="truncate text-gray-700">{item.job_title}</span>
              <span className="ml-2 flex-shrink-0 text-xs text-gray-400">{item.estimated_weeks} weeks</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
