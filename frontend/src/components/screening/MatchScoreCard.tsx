import type { ScreeningResult, StrengthLevel, HiringRecommendation } from "../../types/screening";

const strengthColors: Record<StrengthLevel, string> = {
  excellent: "badge-success",
  good: "badge-info",
  average: "badge-warning",
  low: "badge-danger",
};

const recommendationColors: Record<HiringRecommendation, string> = {
  strongly_recommend: "badge-success",
  recommend: "badge-info",
  consider: "badge-warning",
  not_recommended: "badge-danger",
};

function formatRecommendation(rec: string): string {
  return rec.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  const color =
    score >= 80 ? "bg-emerald-500" : score >= 60 ? "bg-sky-500" : score >= 40 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-xs text-ink-muted shrink-0">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-medium text-ink w-8 text-right">{score}%</span>
    </div>
  );
}

interface MatchScoreCardProps {
  screening: ScreeningResult;
  candidateName?: string;
  jobTitle?: string;
  compact?: boolean;
}

export function MatchScoreCard({ screening, candidateName, jobTitle, compact }: MatchScoreCardProps) {
  const overall = screening.overall_match_score;
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (overall / 100) * circumference;
  const overallColor =
    overall >= 80 ? "#22c55e" : overall >= 60 ? "#3b82f6" : overall >= 40 ? "#eab308" : "#ef4444";

  if (compact) {
    return (
      <div className="card flex items-center gap-3 p-3">
        <svg width="48" height="48" viewBox="0 0 100 100" className="shrink-0">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="40" fill="none" stroke={overallColor} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" transform="rotate(-90 50 50)"
          />
          <text x="50" y="50" textAnchor="middle" dominantBaseline="central"
            className="text-lg font-bold" fill={overallColor}>
            {overall}
          </text>
        </svg>
        <div className="min-w-0">
          {candidateName && <p className="text-sm font-medium text-ink truncate">{candidateName}</p>}
          {jobTitle && <p className="text-xs text-ink-muted truncate">{jobTitle}</p>}
          <span className={`badge mt-1 ${strengthColors[screening.strength_level as StrengthLevel] || "badge-neutral"}`}>
            {screening.strength_level}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          {candidateName && <h3 className="text-lg font-semibold text-ink">{candidateName}</h3>}
          {jobTitle && <p className="text-sm text-ink-muted">{jobTitle}</p>}
        </div>
        <span className={`badge px-3 py-1 ${recommendationColors[screening.recommendation as HiringRecommendation] || "badge-neutral"}`}>
          {formatRecommendation(screening.recommendation)}
        </span>
      </div>

      <div className="flex items-center gap-6 mb-6">
        <div className="relative">
          <svg width="100" height="100" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" strokeWidth="8" />
            <circle
              cx="50" cy="50" r="40" fill="none" stroke={overallColor} strokeWidth="8"
              strokeDasharray={circumference} strokeDashoffset={offset}
              strokeLinecap="round" transform="rotate(-90 50 50)"
            />
            <text x="50" y="46" textAnchor="middle" dominantBaseline="central"
              className="text-2xl font-bold" fill={overallColor}>
              {overall}
            </text>
            <text x="50" y="64" textAnchor="middle" className="text-xs fill-ink-muted">
              Overall
            </text>
          </svg>
        </div>
        <div className="flex-1 space-y-2">
          <ScoreBar label="Skills" score={screening.skill_match_score} />
          <ScoreBar label="Experience" score={screening.experience_match_score} />
          <ScoreBar label="Education" score={screening.education_match_score} />
          <ScoreBar label="Projects" score={screening.project_match_score} />
          <ScoreBar label="Certifications" score={screening.certification_match_score} />
          <ScoreBar label="Location" score={screening.location_match_score} />
          <ScoreBar label="Semantic" score={screening.semantic_match_score} />
        </div>
      </div>

      {screening.matched_skills && screening.matched_skills.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-ink-muted uppercase tracking-wide mb-2">Matched Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {screening.matched_skills.map((s) => (
              <span key={s} className="badge badge-success">{s}</span>
            ))}
          </div>
        </div>
      )}

      {screening.missing_required_skills && screening.missing_required_skills.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-ink-muted uppercase tracking-wide mb-2">Missing Required Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {screening.missing_required_skills.map((s) => (
              <span key={s} className="badge badge-danger">{s}</span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mt-4">
        {screening.strengths && screening.strengths.length > 0 && (
          <div>
            <p className="text-xs font-medium text-emerald-600 uppercase tracking-wide mb-1">Strengths</p>
            <ul className="space-y-1">
              {screening.strengths.map((s, i) => (
                <li key={i} className="text-xs text-ink-muted flex items-start gap-1">
                  <span className="text-emerald-500 mt-0.5">+</span> {s}
                </li>
              ))}
            </ul>
          </div>
        )}
        {screening.weaknesses && screening.weaknesses.length > 0 && (
          <div>
            <p className="text-xs font-medium text-rose-600 uppercase tracking-wide mb-1">Weaknesses</p>
            <ul className="space-y-1">
              {screening.weaknesses.map((w, i) => (
                <li key={i} className="text-xs text-ink-muted flex items-start gap-1">
                  <span className="text-rose-500 mt-0.5">-</span> {w}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
