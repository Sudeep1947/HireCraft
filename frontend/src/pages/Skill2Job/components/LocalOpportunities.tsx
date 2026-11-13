import { Briefcase, ArrowRight, CheckCircle2, AlertTriangle } from "lucide-react";
import type { Skill2JobOverview, OverviewTopMatch } from "../../../types/skill2job";
import { formatRecommendation } from "./helpers";

function JobCard({ match, onViewGap }: { match: OverviewTopMatch; onViewGap: () => void }) {
  const scoreColor = match.overall_score >= 80 ? "text-emerald-600" : match.overall_score >= 60 ? "text-primary-600" : "text-amber-600";
  const barColor =
    match.overall_score >= 80
      ? "bg-gradient-to-br from-emerald-400 to-emerald-600"
      : match.overall_score >= 60
      ? "bg-brand-gradient"
      : "bg-gradient-to-br from-amber-400 to-amber-600";
  const recommendationCls =
    match.recommendation === "strongly_recommend"
      ? "badge-success"
      : match.recommendation === "recommend"
      ? "badge-info"
      : "badge-warning";
  return (
    <div className="card card-hover w-[320px] flex-shrink-0 p-5 md:w-auto">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-gray-900">{match.title}</h3>
          <p className="mt-0.5 truncate text-sm text-gray-500">{match.company && `${match.company} \u00b7 `}{match.location || "Remote"}</p>
        </div>
        <div className={`font-display text-2xl font-bold ${scoreColor}`}>{match.overall_score}%</div>
      </div>
      <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${match.overall_score}%` }}
        />
      </div>
      {match.matched_skills.length > 0 && (
        <div className="mb-2">
          <div className="section-label mb-1.5">Matched Skills</div>
          <div className="flex flex-wrap gap-1">
            {match.matched_skills.slice(0, 5).map((s) => (
              <span key={s} className="badge-success">
                <CheckCircle2 className="h-3 w-3" aria-hidden="true" />{s}
              </span>
            ))}
          </div>
        </div>
      )}
      {match.missing_required.length > 0 && (
        <div className="mb-3">
          <div className="section-label mb-1.5">Missing Skills</div>
          <div className="flex flex-wrap gap-1">
            {match.missing_required.slice(0, 3).map((s) => (
              <span key={s} className="badge-warning">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />{s}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="flex items-center justify-between border-t border-gray-100 pt-3">
        <span className={recommendationCls}>
          {formatRecommendation(match.recommendation)}
        </span>
        <button
          onClick={onViewGap}
          className="inline-flex items-center gap-1 rounded px-1 text-xs font-semibold text-primary-600 transition-colors hover:text-primary-700"
        >
          Analyze Gap <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export default function LocalOpportunities({ overview, onViewGap }: { overview: Skill2JobOverview; onViewGap: () => void }) {
  const matches = overview.jobs.top_matches;
  return (
    <div id="local-opportunities">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="section-title flex items-center gap-2">
          <span className="rounded-xl bg-primary-50 p-2 text-primary-600">
            <Briefcase className="h-4 w-4" aria-hidden="true" />
          </span>
          Local Opportunities
        </h2>
        <span className="text-sm text-gray-500">{overview.jobs.relevant_count} relevant jobs found</span>
      </div>
      {matches.length === 0 ? (
        <div className="empty-state">
          <Briefcase className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-base font-semibold text-gray-900">No matching jobs yet</p>
          <p className="mt-1 text-sm text-gray-500">Upload your resume or complete your profile to discover opportunities.</p>
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 md:grid md:grid-cols-2 md:overflow-visible lg:grid-cols-3">
          {matches.map((m) => <JobCard key={m.job_id} match={m} onViewGap={onViewGap} />)}
        </div>
      )}
    </div>
  );
}
