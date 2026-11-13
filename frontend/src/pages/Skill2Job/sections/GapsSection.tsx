import { useEffect, useState } from "react";
import { BookOpen, ListChecks } from "lucide-react";
import { skill2jobApi } from "../../../api/skill2job";
import type { SkillGapAnalysis, SkillGapSummary } from "../../../types/skill2job";
import { SkillsSectionHeader } from "./shared";

export function GapsSection() {
  const [analyses, setAnalyses] = useState<SkillGapAnalysis[]>([]);
  const [summary, setSummary] = useState<SkillGapSummary | null>(null);
  const [busy, setBusy] = useState(false);

  async function analyze() {
    setBusy(true);
    try {
      const [ana, sum] = await Promise.all([
        skill2jobApi.analyzeSkillGaps({ limit: 5 }),
        skill2jobApi.getSkillGapSummary(),
      ]);
      setAnalyses(ana);
      setSummary(sum);
    } catch {
      setAnalyses([]);
      setSummary(null);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    Promise.all([skill2jobApi.getSkillGaps(), skill2jobApi.getSkillGapSummary()])
      .then(([ana, sum]) => {
        setAnalyses(ana);
        setSummary(sum);
      })
      .catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6">
      <SkillsSectionHeader
        icon={ListChecks}
        title="Skill Gap Analysis"
        hint="Per-job missing required skills with provenance, interview readiness, and a transfer-aware teaching plan."
        cta="Analyze gaps"
        onClick={analyze}
        busy={busy}
      />

      {summary && summary.teaching_plan.length > 0 && (
        <section className="card p-6">
          <h3 className="flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
              <BookOpen className="h-5 w-5" aria-hidden="true" />
            </span>
            Teacher-Style Learning Plan
          </h3>
          <ul className="mt-4 space-y-3">
            {summary.teaching_plan.map((step) => (
              <li key={step.skill} className="rounded-xl border border-gray-100 bg-gray-50/60 p-4 shadow-xs">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-bold text-gray-900">{step.skill}</p>
                  <span className={`badge ${
                    step.priority === "high" ? "badge-danger" : step.priority === "medium" ? "badge-warning" : "badge-info"
                  }`}>
                    {step.priority} priority
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">{step.rationale}</p>
                <p className="mt-1 text-xs text-gray-400">
                  Demanded by: {step.jobs_demanding.join(", ")}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {analyses.length > 0 && (
        <section className="card p-6">
          <h3 className="text-lg font-bold text-gray-900">Per-Job Analysis</h3>
          <ul className="mt-4 divide-y divide-gray-100">
            {analyses.map((a) => (
              <li key={a.job_id} className="py-4 transition-colors hover:bg-gray-50/60">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-bold text-gray-900">
                    {a.job_title} <span className="font-normal text-gray-400">· {a.company}</span>
                  </p>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-gray-500">readiness {a.interview_readiness_score}</span>
                    <span className="font-display text-lg font-extrabold text-primary-700">{a.overall_score}</span>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {a.missing_required_skills.map((s) => (
                    <span key={s} className="badge badge-danger">
                      {s}
                    </span>
                  ))}
                  {a.missing_preferred_skills.map((s) => (
                    <span key={s} className="badge badge-warning">
                      bonus · {s}
                    </span>
                  ))}
                </div>
                {a.experience_gap_description && (
                  <p className="mt-2 text-xs text-gray-500">{a.experience_gap_description}</p>
                )}
                {a.gap_items.length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {a.gap_items.slice(0, 6).map((g) => (
                      <li key={g.skill} className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-bold text-gray-800">{g.skill}</p>
                          <div className="flex items-center gap-1.5">
                            <span className={`badge ${
                              g.gap_kind === "evidence_gap" ? "badge-warning" : "badge-danger"
                            }`}>
                              {g.gap_kind === "evidence_gap" ? "evidence gap" : "skill gap"}
                            </span>
                            <span className={`badge ${
                              g.priority === "high" ? "badge-danger" : g.priority === "medium" ? "badge-warning" : "badge-info"
                            }`}>
                              {g.priority}
                            </span>
                          </div>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">{g.evidence_note ?? g.evidence}</p>
                        {g.transferable.length > 0 && (
                          <p className="mt-1 text-[11px] text-gray-400">
                            Transferable from: {g.transferable.join(", ")}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {a.improvement_suggestions.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {a.improvement_suggestions.slice(0, 3).map((s, i) => (
                      <li key={i} className="text-xs text-gray-500">→ {s}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {!busy && analyses.length === 0 && !summary && (
        <div className="empty-state">
          <p className="text-sm text-gray-500">
            No skill-gap analysis yet. Run “Analyze gaps” after matching has computed your profile score.
          </p>
        </div>
      )}
    </div>
  );
}
