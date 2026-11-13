import { Unlock, Zap } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function OpportunityUnlockCard({ overview }: { overview: Skill2JobOverview }) {
  const opp = overview.opportunity_unlock;
  return (
    <div className="card p-6">
      <div className="mb-5 flex items-center gap-3">
        <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
          <Unlock className="h-5 w-5" aria-hidden="true" />
        </span>
        <h2 className="section-title">What Could You Unlock?</h2>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-gray-100 bg-gray-50/80 p-4 text-center shadow-xs">
          <div className="section-label mb-1">Current Profile</div>
          <div className="font-display text-2xl font-bold text-gray-900">{overview.jobs.relevant_count}</div>
          <div className="text-xs text-gray-500">relevant jobs</div>
        </div>
        <div className="panel-brand p-4 text-center shadow-xs">
          <div className="section-label mb-1 text-primary-600">Potential</div>
          <div className="font-display text-2xl font-bold text-primary-700">{opp.potential}</div>
          <div className="text-xs text-primary-600">more opportunities</div>
        </div>
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/70 p-4 text-center shadow-xs">
          <div className="section-label mb-1 text-emerald-600">Unlocked</div>
          <div className="font-display text-2xl font-bold text-emerald-700">{opp.unlocked_count}</div>
          <div className="text-xs text-emerald-600">newly accessible</div>
        </div>
      </div>
      {opp.top_roles && opp.top_roles.length > 0 && (
        <div className="mt-5">
          <div className="section-label mb-2">Top Roles You Could Unlock</div>
          <div className="flex flex-wrap gap-2">
            {opp.top_roles.slice(0, 3).map((r, i) => (
              <span key={i} className="badge-primary">
                <Zap className="h-3 w-3" aria-hidden="true" />{String(r.title || r.role || "Role")}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
