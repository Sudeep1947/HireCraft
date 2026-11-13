import { AlertTriangle, BarChart3 } from "lucide-react";
import type { Skill2JobOverview, OverviewGapItem } from "../../../types/skill2job";
import { priorityColor } from "./helpers";

function GapRow({ gap }: { gap: OverviewGapItem }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-100 py-3 last:border-0">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex-shrink-0 rounded-lg bg-amber-50 p-1.5 text-amber-600">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <span className="block truncate font-semibold text-gray-900">{gap.skill}</span>
          <p className="text-xs text-gray-500">Required by {gap.count} relevant job{gap.count !== 1 ? "s" : ""}</p>
        </div>
      </div>
      <span className={`inline-flex flex-shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${priorityColor(gap.priority)}`}>
        {gap.priority}
      </span>
    </div>
  );
}

export default function SkillGapIntelligence({ overview }: { overview: Skill2JobOverview }) {
  const gaps = overview.skill_gaps.items;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="section-title flex items-center gap-2">
          <span className="rounded-xl bg-primary-50 p-2 text-primary-600">
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
          </span>
          Your Skill Gaps
        </h2>
        <span className="text-sm text-gray-500">{overview.skill_gaps.total} gaps identified</span>
      </div>
      {gaps.length === 0 ? (
        <div className="card p-6 text-center">
          <span className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-500">
            <BarChart3 className="h-5 w-5" aria-hidden="true" />
          </span>
          <p className="text-sm text-gray-500">No significant skill gaps detected.</p>
        </div>
      ) : (
        <div className="card p-5">
          {gaps.slice(0, 8).map((g) => <GapRow key={g.skill} gap={g} />)}
        </div>
      )}
    </div>
  );
}
