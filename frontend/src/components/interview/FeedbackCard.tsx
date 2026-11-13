import type { InterviewEvaluation } from "../../types/interview";

export function FeedbackCard({ evaluation }: { evaluation: InterviewEvaluation }) {
  const scoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-600";
    if (score >= 60) return "text-sky-600";
    if (score >= 40) return "text-amber-600";
    return "text-rose-600";
  };

  const metrics = [
    { label: "Technical Accuracy", value: evaluation.technical_accuracy },
    { label: "Completeness", value: evaluation.completeness },
    { label: "Communication", value: evaluation.communication },
    { label: "Problem Solving", value: evaluation.problem_solving },
    { label: "Confidence", value: evaluation.confidence },
    { label: "Relevance", value: evaluation.relevance },
  ];

  return (
    <div className="rounded-xl border border-slate-200/70 bg-white p-5 shadow-soft">
      <div className="mb-4 flex items-center justify-between">
        <h4 className="font-semibold text-ink">AI Evaluation</h4>
        <span className={`text-2xl font-bold ${scoreColor(evaluation.overall_score)}`}>
          {evaluation.overall_score}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-lg bg-surface-muted p-2.5 text-center">
            <p className={`text-lg font-bold ${scoreColor(m.value)}`}>{m.value}</p>
            <p className="text-[10px] text-ink-muted">{m.label}</p>
          </div>
        ))}
      </div>

      {evaluation.feedback && (
        <div className="mb-3 rounded-lg bg-sky-50 p-3">
          <p className="text-sm text-sky-800">{evaluation.feedback}</p>
        </div>
      )}

      {evaluation.improvement_suggestions && evaluation.improvement_suggestions.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-xs font-medium text-ink">Improvement Suggestions</p>
          <ul className="space-y-1">
            {evaluation.improvement_suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-muted">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {evaluation.follow_up_questions && evaluation.follow_up_questions.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-ink">Suggested Follow-up</p>
          <ul className="space-y-1">
            {evaluation.follow_up_questions.map((q, i) => (
              <li key={i} className="text-sm italic text-ink-muted">"{q}"</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
