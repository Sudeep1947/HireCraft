import { PieChart } from "lucide-react";

import type { StatusBreakdown } from "../../types/analytics";

interface Props {
  data: StatusBreakdown[];
  title: string;
}

const STATUS_COLORS: Record<string, string> = {
  applied: "bg-sky-50 text-sky-700 ring-sky-200/70",
  under_review: "bg-amber-50 text-amber-700 ring-amber-200/70",
  shortlisted: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
  interview_scheduled: "bg-violet-50 text-violet-700 ring-violet-200/70",
  interviewed: "bg-teal-50 text-teal-700 ring-teal-200/70",
  rejected: "bg-red-50 text-red-700 ring-red-200/70",
  offered: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
  hired: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
  withdrawn: "bg-gray-100 text-gray-700 ring-gray-200/80",
  draft: "bg-gray-100 text-gray-600 ring-gray-200/80",
  published: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
  closed: "bg-red-50 text-red-700 ring-red-200/70",
  archived: "bg-gray-100 text-gray-500 ring-gray-200/80",
};

export function StatusBreakdownChart({ data, title }: Props) {
  return (
    <div className="card relative overflow-hidden p-5">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-br from-primary-500/10 to-transparent"
      />
      <div className="relative mb-4 flex items-center justify-between gap-2">
        <h4 className="section-title flex items-center gap-2 text-sm">
          <span className="rounded-lg bg-primary-50 p-1.5 text-primary-600">
            <PieChart className="h-4 w-4" aria-hidden="true" />
          </span>
          {title}
        </h4>
        <span className="section-label">{data.length} stages</span>
      </div>

      <div className="relative space-y-3">
        {data.map((s) => (
          <div key={s.status} className="flex items-center gap-3">
            <span
              className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset transition-colors ${STATUS_COLORS[s.status] || "bg-gray-100 text-gray-700 ring-gray-200/80"}`}
            >
              {s.status.replace(/_/g, " ")}
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary-500 to-violet-500 transition-all duration-500 ease-smooth"
                style={{ width: `${s.percentage}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right text-xs font-semibold text-gray-600">
              {s.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
