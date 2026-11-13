import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Sparkles, TrendingUp } from "lucide-react";

import { useToast } from "../../contexts/ToastContext";
import { getMyAISummary, getMyScores } from "../../api/screening";
import type { CandidateAISummary, ScreeningResult } from "../../types/screening";

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`badge ${color}`}>{label}</span>;
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card p-6">
      <h3 className="section-title mb-4">{title}</h3>
      {children}
    </div>
  );
}

export function CandidateAIDashboard() {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<CandidateAISummary | null>(null);
  const [scores, setScores] = useState<ScreeningResult[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [sum, sc] = await Promise.all([
          getMyAISummary(),
          getMyScores(),
        ]);
        setSummary(sum);
        setScores(sc);
      } catch {
        addToast("Failed to load AI dashboard", "error");
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
        <div className="skeleton h-32 w-full" />
        <div className="skeleton h-48 w-full" />
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">My AI Dashboard</h1>
        <p className="page-subtitle">AI-powered insights about your profile and job matches</p>
      </div>

      {summary && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
            <div className="card card-hover p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Experience Level</p>
              <p className="mt-1.5 font-display text-lg font-bold text-sky-600">{summary.experience_level}</p>
            </div>
            <div className="card card-hover p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Technical Expertise</p>
              <p className="mt-1.5 font-display text-lg font-bold text-violet-600">{summary.technical_expertise}</p>
            </div>
            <div className="card card-hover p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Leadership Potential</p>
              <p className="mt-1.5 font-display text-lg font-bold text-emerald-600">{summary.leadership_potential}</p>
            </div>
            <div className="card card-hover p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Learning Ability</p>
              <p className="mt-1.5 font-display text-lg font-bold text-amber-600">{summary.learning_ability}</p>
            </div>
          </div>

          <InfoCard title="Professional Summary">
            <p className="text-sm leading-relaxed text-gray-700">{summary.professional_summary}</p>
          </InfoCard>

          {summary.top_skills.length > 0 && (
            <InfoCard title="Top Skills">
              <div className="space-y-2.5">
                {summary.top_skills.map((s) => (
                  <div key={s.skill} className="flex items-center gap-3">
                    <span className="w-32 shrink-0 text-sm text-gray-700">{s.skill}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          s.relevance >= 80
                            ? "bg-gradient-to-r from-emerald-400 to-emerald-600"
                            : s.relevance >= 60
                              ? "bg-gradient-to-r from-sky-400 to-primary-500"
                              : "bg-gradient-to-r from-amber-400 to-amber-600"
                        }`}
                        style={{ width: `${s.relevance}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-xs font-semibold text-gray-600">{s.relevance}%</span>
                  </div>
                ))}
              </div>
            </InfoCard>
          )}

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <InfoCard title="Strengths">
              <ul className="space-y-2">
                {summary.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" /> {s}
                  </li>
                ))}
              </ul>
            </InfoCard>
            <InfoCard title="Areas for Improvement">
              <ul className="space-y-2">
                {summary.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" /> {w}
                  </li>
                ))}
              </ul>
            </InfoCard>
          </div>

          <InfoCard title="Career Highlights">
            <ul className="space-y-2">
              {summary.career_highlights.map((h, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-sky-500" aria-hidden="true" /> {h}
                </li>
              ))}
            </ul>
          </InfoCard>

          <InfoCard title="Risk Assessment">
            <ul className="space-y-2">
              {summary.risk_factors.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" /> {r}
                </li>
              ))}
            </ul>
          </InfoCard>

          {summary.education_summary.length > 0 && (
            <InfoCard title="Education">
              <div className="flex flex-wrap gap-2">
                {summary.education_summary.map((e, i) => (
                  <Badge key={i} label={e} color="badge-info" />
                ))}
              </div>
            </InfoCard>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="card p-5 text-center">
              <p className="font-display text-3xl font-bold text-gradient">{summary.certification_count}</p>
              <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Certifications</p>
            </div>
            <div className="card p-5 text-center">
              <p className="font-display text-3xl font-bold text-gradient">{summary.project_count}</p>
              <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Projects</p>
            </div>
          </div>
        </>
      )}

      {scores.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-4">My Job Match Scores</h3>
          <div className="space-y-3">
            {scores.map((s) => {
              const scoreColor =
                s.overall_match_score >= 80 ? "bg-emerald-500" :
                s.overall_match_score >= 60 ? "bg-primary-500" :
                s.overall_match_score >= 40 ? "bg-amber-500" : "bg-red-500";
              return (
                <div key={s.id} className="flex flex-col gap-3 rounded-xl border border-gray-200/70 bg-gray-50/60 p-3.5 sm:flex-row sm:items-center sm:gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900">Job: {s.job_id.slice(0, 8)}...</p>
                    <div className="mt-1.5 flex items-center gap-3">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
                        <div className={`h-full rounded-full transition-all duration-500 ${scoreColor}`} style={{ width: `${s.overall_match_score}%` }} />
                      </div>
                      <span className="text-sm font-bold text-gray-700">{s.overall_match_score}%</span>
                    </div>
                  </div>
                  <span className={`shrink-0 self-start sm:self-auto ${
                    s.strength_level === "excellent" ? "badge-success" :
                    s.strength_level === "good" ? "badge-info" :
                    s.strength_level === "average" ? "badge-warning" :
                    "badge-danger"
                  }`}>
                    {s.strength_level}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
