import type { SkillGapAnalysis } from "../../types/screening";

interface SkillGapReportProps {
  skillGap: SkillGapAnalysis;
}

export function SkillGapReport({ skillGap }: SkillGapReportProps) {
  const readiness = skillGap.interview_readiness_score;
  const readinessColor =
    readiness >= 80 ? "text-emerald-600" : readiness >= 60 ? "text-sky-600" : readiness >= 40 ? "text-amber-600" : "text-rose-600";
  const readinessBg =
    readiness >= 80 ? "bg-emerald-50 ring-emerald-200/70" : readiness >= 60 ? "bg-sky-50 ring-sky-200/70" : readiness >= 40 ? "bg-amber-50 ring-amber-200/70" : "bg-rose-50 ring-rose-200/70";

  return (
    <div className="card p-6">
      <div className="mb-5 flex items-center justify-between">
        <h3 className="section-title">Skill Gap Analysis</h3>
        <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 ring-1 ring-inset ${readinessBg}`}>
          <span className={`text-sm font-bold ${readinessColor}`}>{readiness}%</span>
          <span className="text-xs text-ink-muted">Interview Ready</span>
        </div>
      </div>

      {skillGap.missing_required_skills && skillGap.missing_required_skills.length > 0 && (
        <div className="mb-5">
          <h4 className="mb-2 text-sm font-medium text-rose-600">Missing Required Skills</h4>
          <div className="flex flex-wrap gap-1.5">
            {skillGap.missing_required_skills.map((s) => (
              <span key={s} className="badge badge-danger">{s}</span>
            ))}
          </div>
        </div>
      )}

      {skillGap.missing_preferred_skills && skillGap.missing_preferred_skills.length > 0 && (
        <div className="mb-5">
          <h4 className="mb-2 text-sm font-medium text-amber-600">Missing Preferred Skills</h4>
          <div className="flex flex-wrap gap-1.5">
            {skillGap.missing_preferred_skills.map((s) => (
              <span key={s} className="badge badge-warning">{s}</span>
            ))}
          </div>
        </div>
      )}

      {(skillGap.experience_gap_description || skillGap.education_gap_description || skillGap.certification_gap_description) && (
        <div className="mb-5 space-y-2">
          <h4 className="text-sm font-medium text-ink">Gaps</h4>
          {skillGap.experience_gap_description && (
            <div className="flex items-start gap-2 text-sm text-ink-muted">
              <span className="mt-0.5 text-amber-500">!</span> {skillGap.experience_gap_description}
            </div>
          )}
          {skillGap.education_gap_description && (
            <div className="flex items-start gap-2 text-sm text-ink-muted">
              <span className="mt-0.5 text-amber-500">!</span> {skillGap.education_gap_description}
            </div>
          )}
          {skillGap.certification_gap_description && (
            <div className="flex items-start gap-2 text-sm text-ink-muted">
              <span className="mt-0.5 text-amber-500">!</span> {skillGap.certification_gap_description}
            </div>
          )}
        </div>
      )}

      {skillGap.skill_suggestions && skillGap.skill_suggestions.length > 0 && (
        <div className="mb-5">
          <h4 className="mb-2 text-sm font-medium text-sky-600">Skill Suggestions</h4>
          <ul className="space-y-1.5">
            {skillGap.skill_suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-muted">
                <span className="mt-0.5 text-sky-500">&#x2022;</span> {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {skillGap.improvement_suggestions && skillGap.improvement_suggestions.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-emerald-600">Improvement Suggestions</h4>
          <ul className="space-y-1.5">
            {skillGap.improvement_suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-muted">
                <span className="mt-0.5 text-emerald-500">&#x2713;</span> {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
