import { ArrowRight, Zap } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function NextActionCard({ overview }: { overview: Skill2JobOverview }) {
  const action = overview.next_action;
  const priorityColors: Record<string, string> = {
    high: "border-l-red-500 bg-red-50/70",
    medium: "border-l-amber-500 bg-amber-50/70",
    low: "border-l-emerald-500 bg-emerald-50/70",
  };
  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
          <Zap className="h-5 w-5" aria-hidden="true" />
        </span>
        <h2 className="section-title">Recommended Next Step</h2>
      </div>
      <div
        className={`rounded-xl border-l-4 p-4 shadow-xs transition-shadow ${priorityColors[action.priority] || "border-l-gray-400 bg-gray-50"}`}
      >
        <div className="font-semibold text-gray-900">{action.action}</div>
        <p className="mt-1 text-sm text-gray-600">{action.description}</p>
        <div className="mt-3">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary-600">
            Take Action <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </span>
        </div>
      </div>
    </div>
  );
}
