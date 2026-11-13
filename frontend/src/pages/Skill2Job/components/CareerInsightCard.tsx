import { Sparkles, Eye } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function CareerInsightCard({ overview }: { overview: Skill2JobOverview }) {
  const insight = overview.career_insight;
  return (
    <div className="card relative overflow-hidden p-6">
      <div
        className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-brand-gradient-soft blur-2xl"
        aria-hidden="true"
      />
      <div className="relative mb-4 flex items-center gap-3">
        <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </span>
        <h2 className="section-title">AI Career Insight</h2>
      </div>
      <p className="relative mb-4 text-sm leading-relaxed text-gray-700">{insight.text}</p>
      {insight.evidence.length > 0 && (
        <div className="relative flex flex-wrap gap-2">
          {insight.evidence.map((e, i) => (
            <span key={i} className="badge-primary">
              <Eye className="h-3 w-3" aria-hidden="true" />{e}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
