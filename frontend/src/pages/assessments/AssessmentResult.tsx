import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { assessmentApi } from "../../api/assessment";
import type { ResultResponse } from "../../types/assessment";

const RECOMMENDATION_STYLES: Record<string, string> = {
  strong_hire: "bg-green-100 text-green-800",
  hire: "bg-emerald-100 text-emerald-800",
  consider: "bg-yellow-100 text-yellow-800",
  reject: "bg-red-100 text-red-700",
};

function scoreColor(pct: number): string {
  if (pct >= 85) return "text-green-600";
  if (pct >= 70) return "text-emerald-600";
  if (pct >= 60) return "text-yellow-600";
  return "text-red-500";
}

export interface AssessmentResultProps {
  /**
   * Who is reading this. Defaults to the candidate, which keeps this page's
   * original behaviour and copy exactly as it was.
   *
   * Phase 12 reuses this same component for a recruiter reaching an attempt's
   * result from the application, rather than building a second result page. The
   * only difference is tone: "congratulations" is addressed to a candidate, and
   * a recruiter reading the same result needs to be told it is evidence rather
   * than an outcome. The data, the scoring and the layout are identical.
   */
  audience?: "candidate" | "staff";
}

export function AssessmentResult({ audience = "candidate" }: AssessmentResultProps = {}) {
  const { attemptId } = useParams<{ attemptId: string }>();
  const [result, setResult] = useState<ResultResponse | null>(null);
  const [error, setError] = useState("");
  const isStaff = audience === "staff";

  useEffect(() => {
    if (!attemptId) return;
    assessmentApi
      .result(attemptId)
      .then(setResult)
      .catch(() => setError("Result not available for this attempt."));
  }, [attemptId]);

  if (error) return <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">{error}</div>;
  if (!result) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="space-y-6">
      {/* Overall */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Assessment Result</h1>
            <p className="mt-1 text-sm capitalize text-gray-500">
              Status: {result.status} · Readiness: {result.readiness_level.replace(/_/g, " ")}
            </p>
          </div>
          <span className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${RECOMMENDATION_STYLES[result.recommendation] || "bg-gray-100"}`}>
            {result.recommendation.replace(/_/g, " ")}
          </span>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-5">
          {[
            { label: "Overall", value: `${Math.round(result.overall_score)}%` },
            { label: "Pass mark", value: `${result.passing_score}%` },
            { label: "Accuracy", value: `${Math.round(result.accuracy)}%` },
            { label: "Time mgmt", value: `${Math.round(result.time_management)}%` },
            { label: "Integrity flags", value: String(result.integrity_flags) },
          ].map((kpi) => (
            <div key={kpi.label} className="rounded-lg bg-gray-50 p-4 text-center">
              <p className={`text-xl font-bold ${kpi.label === "Overall" ? scoreColor(result.overall_score) : "text-gray-800"}`}>
                {kpi.value}
              </p>
              <p className="mt-1 text-xs text-gray-500">{kpi.label}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-center text-sm font-semibold">
          {result.passed ? (
            <span className="text-green-600">
              {isStaff
                ? `Above this assessment's pass mark (${result.passing_score}%).`
                : "Passed — congratulations!"}
            </span>
          ) : (
            <span className="text-red-500">
              {isStaff
                ? `Below this assessment's pass mark (${result.passing_score}%).`
                : "Below the passing score."}
            </span>
          )}
        </p>

        {/* A recruiter is reading evidence, not an outcome. The pass mark is the
            assessment's own configured threshold and decides nothing about
            hiring, so say so on the page rather than letting a green "passed"
            badge stand in for a decision the recruiter has not made. */}
        {isStaff ? (
          <p className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
            This is the assessment result as evidence for your review. Passing this
            assessment does not shortlist a candidate and failing it does not reject
            one — the hiring decision stays yours.
          </p>
        ) : null}

        {result.ai_summary && (
          <p className="mt-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-800">{result.ai_summary}</p>
        )}
      </div>

      {/* Section scores */}
      {result.section_scores.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Section breakdown</h2>
          <div className="space-y-3">
            {result.section_scores.map((s) => (
              <div key={s.section}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="font-medium text-gray-700">{s.section}</span>
                  <span className="text-gray-500">{Math.round(s.percentage)}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={`h-full rounded-full ${s.percentage >= 70 ? "bg-green-500" : s.percentage >= 50 ? "bg-yellow-400" : "bg-red-400"}`}
                    style={{ width: `${Math.min(s.percentage, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Strong skills</h2>
          {result.strong_skills.length === 0 ? (
            <p className="text-sm text-gray-400">None flagged yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {result.strong_skills.map((s) => (
                <span key={s} className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium capitalize text-green-800">{s}</span>
              ))}
            </div>
          )}
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Focus areas</h2>
          {result.weak_skills.length === 0 && result.recommended_topics.length === 0 ? (
            <p className="text-sm text-gray-400">
              {isStaff ? "None flagged." : "Nothing flagged — great balance."}
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {[...new Set([...result.weak_skills, ...result.recommended_topics])].map((s) => (
                <span key={s} className="rounded-full bg-orange-100 px-3 py-1 text-xs font-medium text-orange-800">{s}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Per question */}
      {result.per_question.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {["Type", "Skill", "Difficulty", "Score", "Correct"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {result.per_question.map((q, i) => (
                <tr key={`${q.question_id}-${i}`}>
                  <td className="px-4 py-2.5 text-sm capitalize text-gray-700">{q.type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2.5 text-sm capitalize text-gray-600">{q.skill}</td>
                  <td className="px-4 py-2.5 text-sm capitalize text-gray-600">{q.difficulty}</td>
                  <td className={`px-4 py-2.5 text-sm font-semibold ${scoreColor(q.score_pct)}`}>{Math.round(q.score_pct)}%</td>
                  <td className="px-4 py-2.5 text-sm">
                    {q.is_correct === null ? <span className="text-gray-400">partial</span> : q.is_correct ? "✓" : "✗"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
