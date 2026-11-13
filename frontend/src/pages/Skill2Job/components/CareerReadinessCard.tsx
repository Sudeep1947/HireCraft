import { Target } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function CareerReadinessCard({
  overview,
}: {
  overview: Skill2JobOverview;
}) {
  const score = overview.readiness.score;
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;
  const ringStart = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  const ringEnd = score >= 70 ? "#059669" : score >= 40 ? "#d97706" : "#dc2626";

  return (
    <div className="card p-6">
      <div className="mb-5 flex items-center gap-3">
        <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
          <Target className="h-5 w-5" aria-hidden="true" />
        </span>
        <h2 className="section-title">Career Readiness</h2>
      </div>
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <div className="relative flex-shrink-0">
          <svg width="140" height="140" viewBox="0 0 120 120" aria-hidden="true">
            <defs>
              <linearGradient id="readiness-ring-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={ringStart} />
                <stop offset="100%" stopColor={ringEnd} />
              </linearGradient>
            </defs>
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="#eef0f7"
              strokeWidth="9"
            />
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="url(#readiness-ring-gradient)"
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-display text-3xl font-bold text-gray-900">{score}%</span>
            <span className="text-xs text-gray-500">Job Readiness</span>
          </div>
        </div>
        <div className="grid w-full grid-cols-2 gap-4">
          <div className="rounded-xl border border-gray-100 bg-gray-50/80 p-3 text-center shadow-xs">
            <div className="font-display text-2xl font-bold text-gray-900">
              {overview.skills.total}
            </div>
            <div className="text-xs text-gray-500">Skills Identified</div>
          </div>
          <div className="rounded-xl border border-red-100 bg-red-50/70 p-3 text-center shadow-xs">
            <div className="font-display text-2xl font-bold text-red-600">
              {overview.skill_gaps.critical}
            </div>
            <div className="text-xs text-gray-500">Critical Gaps</div>
          </div>
          <div className="rounded-xl border border-primary-100 bg-primary-50/70 p-3 text-center shadow-xs">
            <div className="font-display text-2xl font-bold text-primary-600">
              {overview.jobs.relevant_count}
            </div>
            <div className="text-xs text-gray-500">Relevant Jobs</div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50/80 p-3 text-center shadow-xs">
            <div className="font-display text-2xl font-bold text-gray-900">
              {overview.skill_gaps.total}
            </div>
            <div className="text-xs text-gray-500">Skills to Learn</div>
          </div>
        </div>
      </div>
    </div>
  );
}
