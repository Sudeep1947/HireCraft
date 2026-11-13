import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { useToast } from "../../contexts/ToastContext";
import { getMyExplanation } from "../../api/screening";
import type { CandidateExplanation } from "../../types/screening";
import {
  ConfidenceIndicator,
  FeatureImportanceBar,
  FactorList,
  StatBox,
  Badge,
} from "../../components/xai/XAIComponents";

export function CandidateExplainability() {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [explanation, setExplanation] = useState<CandidateExplanation | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const expl = await getMyExplanation();
        setExplanation(expl);
      } catch {
        addToast("No AI explanation available yet. Apply for a job and complete screening first.", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-64" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-24 w-full" />
        </div>
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-48 w-full" />
      </div>
    );

  if (!explanation) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div>
          <h1 className="page-title">My AI Explanation</h1>
          <p className="page-subtitle">Understand how AI evaluates your profile</p>
        </div>
        <div className="empty-state">
          <Sparkles className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm font-semibold text-gray-900">No AI explanation available yet.</p>
          <p className="mt-1.5 text-sm text-gray-500">Apply for a job and complete screening to see your explanation.</p>
        </div>
      </div>
    );
  }

  const recs = explanation.improvement_suggestions;

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">My AI Explanation</h1>
        <p className="page-subtitle">
          Understand how AI evaluates your profile for: {explanation.job_title}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatBox label="Overall Match" value={`${explanation.overall_score}%`} color={explanation.overall_score >= 70 ? "text-emerald-600" : "text-amber-600"} />
        <StatBox label="Strength Level" value={explanation.strength_level} color="text-sky-600" />
        <StatBox label="Matched Skills" value={explanation.matched_skills.length} color="text-violet-600" />
        <StatBox label="Missing Skills" value={explanation.missing_skills.length} color="text-amber-600" />
      </div>

      <div className="card p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="section-title">AI Assessment</h3>
          <ConfidenceIndicator confidence={explanation.confidence} />
        </div>
        <p className="text-sm leading-relaxed text-gray-700">{explanation.reasoning_summary}</p>
      </div>

      <div className="card p-6">
        <h3 className="section-title mb-1">Feature Importance</h3>
        <p className="mb-4 text-xs text-gray-500">How different parts of your profile contributed to the score</p>
        <div className="space-y-3">
          {explanation.feature_importance.map((f) => (
            <FeatureImportanceBar key={f.category} feature={f} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="card p-6">
          <h3 className="section-title mb-3">Strengths</h3>
          <FactorList factors={explanation.positive_factors} type="positive" />
        </div>
        <div className="card p-6">
          <h3 className="section-title mb-3">Areas for Improvement</h3>
          <FactorList factors={explanation.negative_factors} type="negative" />
        </div>
      </div>

      {explanation.matched_skills.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-3">Your Matched Skills</h3>
          <div className="flex flex-wrap gap-2">
            {explanation.matched_skills.map((s, i) => (
              <Badge key={i} label={s} color="bg-emerald-50 text-emerald-700" />
            ))}
          </div>
        </div>
      )}

      {explanation.missing_skills.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-3">Skills to Develop</h3>
          <div className="flex flex-wrap gap-2">
            {explanation.missing_skills.map((s, i) => (
              <Badge key={i} label={s} color="bg-red-50 text-red-700" />
            ))}
          </div>
        </div>
      )}

      <div className="card p-6">
        <h3 className="section-title mb-4">Personalized Recommendations</h3>
        <div className="space-y-5">
          {recs.skill_improvements.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Skills to Acquire</p>
              {recs.skill_improvements.map((s, i) => (
                <div key={i} className="mb-1 flex items-center gap-2 text-sm ml-2">
                  <Badge label={s.priority} color={s.priority === "high" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"} />
                  <span className="font-medium text-gray-900">{s.skill}</span>
                </div>
              ))}
            </div>
          )}
          {recs.certification_recommendations.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Recommended Certifications</p>
              {recs.certification_recommendations.map((c, i) => (
                <div key={i} className="text-sm text-gray-700 ml-2">{c.suggestion}</div>
              ))}
            </div>
          )}
          {recs.resume_improvements.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Resume Tips</p>
              {recs.resume_improvements.map((r, i) => (
                <div key={i} className="text-sm text-gray-700 ml-2">{r}</div>
              ))}
            </div>
          )}
          {recs.project_suggestions.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Project Ideas</p>
              {recs.project_suggestions.map((p, i) => (
                <div key={i} className="text-sm text-gray-700 ml-2">{p}</div>
              ))}
            </div>
          )}
          {recs.interview_preparation.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Interview Preparation</p>
              {recs.interview_preparation.map((t, i) => (
                <div key={i} className="text-sm text-gray-700 ml-2">{t}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="section-title mb-4">Learning Roadmap</h3>
        <div className="space-y-4">
          {recs.skill_improvements.map((s, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-xs font-bold text-white">
                {i + 1}
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Learn {s.skill}</p>
                <p className="text-xs text-gray-500">{s.reason}</p>
              </div>
            </div>
          ))}
          {recs.certification_recommendations.map((c, i) => (
            <div key={`cert-${i}`} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-100 text-xs font-bold text-violet-700">
                {recs.skill_improvements.length + i + 1}
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{c.area}</p>
                <p className="text-xs text-gray-500">{c.suggestion}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
