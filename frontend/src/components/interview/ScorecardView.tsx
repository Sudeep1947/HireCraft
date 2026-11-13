import type { InterviewScorecard } from "../../types/interview";

const DIMENSIONS = [
  { key: "technical_skills", label: "Technical Skills" },
  { key: "communication", label: "Communication" },
  { key: "problem_solving", label: "Problem Solving" },
  { key: "teamwork", label: "Teamwork" },
  { key: "leadership", label: "Leadership" },
  { key: "culture_fit", label: "Culture Fit" },
  { key: "learning_ability", label: "Learning Ability" },
] as const;

const RECOMMENDATION_LABELS: Record<string, string> = {
  strongly_recommend: "Strongly Recommend",
  recommend: "Recommend",
  consider: "Consider",
  not_recommended: "Not Recommended",
};

const RECOMMENDATION_COLORS: Record<string, string> = {
  strongly_recommend: "text-emerald-700 bg-emerald-50",
  recommend: "text-sky-700 bg-sky-50",
  consider: "text-amber-700 bg-amber-50",
  not_recommended: "text-rose-700 bg-rose-50",
};

export function ScorecardView({ scorecard }: { scorecard: InterviewScorecard }) {
  const getScoreColor = (score: number) => {
    if (score >= 80) return "bg-emerald-500";
    if (score >= 60) return "bg-sky-500";
    if (score >= 40) return "bg-amber-500";
    return "bg-rose-500";
  };

  const getScoreTextColor = (score: number) => {
    if (score >= 80) return "text-emerald-700";
    if (score >= 60) return "text-sky-700";
    if (score >= 40) return "text-amber-700";
    return "text-rose-700";
  };

  return (
    <div className="space-y-6 rounded-xl border border-slate-200/70 bg-white p-6 shadow-soft">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink">Interview Scorecard</h3>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${RECOMMENDATION_COLORS[scorecard.recommendation] || "bg-surface-muted text-ink-muted"}`}>
          {RECOMMENDATION_LABELS[scorecard.recommendation] || scorecard.recommendation}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg bg-surface-muted p-4 text-center">
          <p className="text-2xl font-bold text-ink">{scorecard.overall_score}</p>
          <p className="text-xs text-ink-muted">Overall Score</p>
        </div>
        <div className="rounded-lg bg-surface-muted p-4 text-center">
          <p className="text-2xl font-bold text-ink">{scorecard.hiring_confidence}%</p>
          <p className="text-xs text-ink-muted">Hiring Confidence</p>
        </div>
        <div className="rounded-lg bg-surface-muted p-4 text-center">
          <p className="text-2xl font-bold text-ink">{scorecard.technical_skills}</p>
          <p className="text-xs text-ink-muted">Technical Skills</p>
        </div>
        <div className="rounded-lg bg-surface-muted p-4 text-center">
          <p className="text-2xl font-bold text-ink">{scorecard.communication}</p>
          <p className="text-xs text-ink-muted">Communication</p>
        </div>
      </div>

      <div className="space-y-3">
        {DIMENSIONS.map((dim) => {
          const score = scorecard[dim.key as keyof InterviewScorecard] as number;
          return (
            <div key={dim.key} className="flex items-center gap-3">
              <span className="w-36 text-sm text-ink-muted">{dim.label}</span>
              <div className="flex-1">
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className={`h-full rounded-full transition-all ${getScoreColor(score)}`}
                    style={{ width: `${score}%` }}
                  />
                </div>
              </div>
              <span className={`w-10 text-right text-sm font-semibold ${getScoreTextColor(score)}`}>
                {score}
              </span>
            </div>
          );
        })}
      </div>

      {scorecard.ai_summary && (
        <div className="rounded-lg bg-sky-50 p-4">
          <p className="text-sm font-medium text-sky-900">AI Summary</p>
          <p className="mt-1 text-sm text-sky-700">{scorecard.ai_summary}</p>
        </div>
      )}

      {scorecard.recruiter_notes && (
        <div className="rounded-lg bg-surface-muted p-4">
          <p className="text-sm font-medium text-ink">Recruiter Notes</p>
          <p className="mt-1 text-sm text-ink">{scorecard.recruiter_notes}</p>
        </div>
      )}
    </div>
  );
}
