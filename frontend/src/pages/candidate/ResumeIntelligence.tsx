import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Check, X } from "lucide-react";
import { candidateApi } from "../../api/candidate";
import type {
  ResumeIntelligenceReport,
  ResumeCompareReport,
} from "../../types/candidate";

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-600";
}

function scoreBg(score: number): string {
  if (score >= 80) return "bg-gradient-to-r from-emerald-400 to-emerald-600";
  if (score >= 60) return "bg-gradient-to-r from-amber-400 to-amber-600";
  return "bg-gradient-to-r from-red-400 to-red-600";
}

export function ResumeIntelligence() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<ResumeIntelligenceReport | null>(null);
  const [compare, setCompare] = useState<ResumeCompareReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("scores");
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    if (!id) { setLoading(false); setError("No resume ID"); return; }
    async function load() {
      try {
        const [r, c] = await Promise.all([
          candidateApi.getResumeIntelligence(id!),
          candidateApi.compareResumeIntelligence(id!).catch(() => null),
        ]);
        if (!cancelledRef.current) {
          setReport(r);
          setCompare(c);
        }
      } catch { if (!cancelledRef.current) setError("Failed to load resume intelligence"); }
      finally { if (!cancelledRef.current) setLoading(false); }
    }
    load();
    return () => { cancelledRef.current = true; };
  }, [id]);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-64" />
        <div className="skeleton h-10 w-full" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="skeleton h-28 w-full" />
          <div className="skeleton h-28 w-full" />
          <div className="skeleton h-28 w-full" />
        </div>
      </div>
    );
  if (error || !report)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="error-banner">{error || "No report available"}</div>
      </div>
    );

  const { scores, strengths, weaknesses, ats_report, skill_analysis, keyword_analysis, recommendations, industry_keywords } = report;

  const tabs = [
    { key: "scores", label: "Scores" },
    { key: "ats", label: "ATS Report" },
    { key: "skills", label: "Skills" },
    { key: "keywords", label: "Keywords" },
    { key: "recommendations", label: "Recommendations" },
    { key: "compare", label: "Compare" },
  ];

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div className="min-w-0">
          <h1 className="page-title">Resume Intelligence</h1>
          <p className="page-subtitle truncate">{report.filename}</p>
        </div>
        <button onClick={() => navigate(`/candidate/resume/${id}`)} className="btn-secondary btn-md shrink-0">&larr; Back to Resume</button>
      </div>

      <div className="card-solid flex flex-wrap gap-1.5 p-1.5" role="tablist" aria-label="Resume intelligence sections">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`nav-link ${tab === t.key ? "nav-link-active" : ""}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "scores" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(["overall", "completeness", "readability", "professionalism", "keyword_optimization", "ats_compatibility"] as const).map((key) => {
              const s = scores[key];
              return (
                <div key={key} className="card card-hover p-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-gray-500">{s.label}</span>
                    <span className={`font-display text-2xl font-bold ${scoreColor(s.score)}`}>{s.score}</span>
                  </div>
                  <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-100">
                    <div className={`h-full rounded-full transition-all duration-500 ${scoreBg(s.score)}`} style={{ width: `${s.score}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-gray-400">{s.description}</p>
                </div>
              );
            })}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Strengths</h3>
              {strengths.length === 0 ? <p className="text-sm text-gray-500">No strengths identified yet</p> : (
                <ul className="space-y-2">
                  {strengths.map((s, i) => <li key={i} className="flex items-start gap-2 text-sm text-gray-600"><Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />{s}</li>)}
                </ul>
              )}
            </div>
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Weaknesses</h3>
              {weaknesses.length === 0 ? <p className="text-sm text-gray-500">No weaknesses identified</p> : (
                <ul className="space-y-2">
                  {weaknesses.map((w, i) => <li key={i} className="flex items-start gap-2 text-sm text-gray-600"><X className="mt-0.5 h-4 w-4 shrink-0 text-red-500" aria-hidden="true" />{w}</li>)}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === "ats" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="card p-4 text-center"><p className="font-display text-2xl font-bold text-gray-900">{ats_report.section_count}/5</p><p className="mt-1 text-xs font-medium text-gray-500">Sections</p></div>
            <div className="card p-4 text-center"><p className="font-display text-2xl font-bold text-gray-900">{ats_report.action_verb_count}</p><p className="mt-1 text-xs font-medium text-gray-500">Action Verbs</p></div>
            <div className="card p-4 text-center"><p className="font-display text-2xl font-bold text-gray-900">{ats_report.quantifiable_achievements}</p><p className="mt-1 text-xs font-medium text-gray-500">Quantified Items</p></div>
            <div className="card p-4 text-center"><p className={`font-display text-2xl font-bold ${ats_report.has_email && ats_report.has_phone ? "text-emerald-600" : "text-red-600"}`}>{ats_report.has_email && ats_report.has_phone ? "Yes" : "No"}</p><p className="mt-1 text-xs font-medium text-gray-500">Contact Info</p></div>
          </div>

          {ats_report.formatting_issues.length > 0 && (
            <div className="rounded-xl border border-red-200/80 bg-red-50/80 p-4 shadow-xs"><h4 className="mb-2 text-sm font-semibold text-red-800">Formatting Issues</h4><ul className="space-y-1">{ats_report.formatting_issues.map((issue, i) => <li key={i} className="text-sm text-red-700">&bull; {issue}</li>)}</ul></div>
          )}

          <div className="card p-5">
            <h3 className="mb-3 text-sm font-semibold text-gray-900">Section Validation</h3>
            <div className="space-y-2">
              {Object.entries(ats_report.sections_valid).map(([section, valid]) => (
                <div key={section} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                  <span className="text-sm capitalize text-gray-700">{section.replace(/_/g, " ")}</span>
                  {valid ? <span className="text-xs font-semibold text-emerald-600">Present</span> : <span className="text-xs font-semibold text-red-500">Missing</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "skills" && (
        <div className="space-y-6">
          <div className="card p-5">
            <div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold text-gray-900">Skills ({skill_analysis.total_skills})</h3></div>
            <div className="flex flex-wrap gap-2">
              {skill_analysis.skill_names.map((s, i) => <span key={i} className="badge-primary">{s}</span>)}
              {skill_analysis.skill_names.length === 0 && <p className="text-sm text-gray-500">No skills extracted</p>}
            </div>
          </div>

          {Object.keys(skill_analysis.categorized).length > 0 && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Categorized</h3>
              <div className="space-y-3">
                {Object.entries(skill_analysis.categorized).map(([cat, skills]) => (
                  <div key={cat}><p className="section-label mb-1.5">{cat.replace(/_/g, " ")}</p><div className="flex flex-wrap gap-1.5">{skills.map((s, i) => <span key={i} className="badge-neutral">{s}</span>)}</div></div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {skill_analysis.missing_essential.length > 0 && (
              <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 p-4 shadow-xs"><h4 className="mb-2 text-sm font-semibold text-amber-800">Missing Essential Skills</h4><div className="flex flex-wrap gap-1.5">{skill_analysis.missing_essential.map((s, i) => <span key={i} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">{s}</span>)}</div></div>
            )}
            {skill_analysis.duplicates.length > 0 && (
              <div className="rounded-xl border border-red-200/80 bg-red-50/80 p-4 shadow-xs"><h4 className="mb-2 text-sm font-semibold text-red-800">Duplicate Skills</h4><div className="flex flex-wrap gap-1.5">{skill_analysis.duplicates.map((s, i) => <span key={i} className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">{s}</span>)}</div></div>
            )}
          </div>

          {skill_analysis.suggestions.length > 0 && (
            <div className="info-banner block"><h4 className="mb-2 text-sm font-semibold text-primary-800">Trending Skills to Consider</h4><div className="flex flex-wrap gap-1.5">{skill_analysis.suggestions.map((s, i) => <span key={i} className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-medium text-primary-700">{s}</span>)}</div></div>
          )}

          {Object.keys(industry_keywords).length > 0 && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Industry Keywords</h3>
              <div className="space-y-3">
                {Object.entries(industry_keywords).map(([cat, data]) => (
                  <div key={cat} className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                    <p className="section-label mb-1.5">{cat.replace(/_/g, " ")}</p>
                    {data.matched.length > 0 && <div className="mb-2"><p className="text-xs text-gray-400">Matched:</p><div className="mt-1 flex flex-wrap gap-1">{data.matched.map((kw, i) => <span key={i} className="badge-success">{kw}</span>)}</div></div>}
                    {data.suggested.length > 0 && <div><p className="text-xs text-gray-400">Suggested:</p><div className="mt-1 flex flex-wrap gap-1">{data.suggested.map((kw, i) => <span key={i} className="badge-info">{kw}</span>)}</div></div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "keywords" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="card p-4 text-center"><p className="font-display text-2xl font-bold text-gray-900">{keyword_analysis.matched_action_keywords}/{keyword_analysis.total_action_keywords}</p><p className="mt-1 text-xs font-medium text-gray-500">Keywords Matched</p></div>
            <div className="card p-4 text-center"><p className="font-display text-2xl font-bold text-gray-900">{Object.keys(keyword_analysis.keyword_density).length}</p><p className="mt-1 text-xs font-medium text-gray-500">Unique Keywords</p></div>
            <div className="card p-4 text-center"><p className="font-display text-2xl font-bold text-gray-900">{Object.values(keyword_analysis.keyword_density).reduce((a, b) => a + b, 0)}</p><p className="mt-1 text-xs font-medium text-gray-500">Total Mentions</p></div>
          </div>

          {keyword_analysis.action_keywords_found.length > 0 && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Found Keywords</h3>
              <div className="max-h-64 space-y-1 overflow-y-auto">
                {Object.entries(keyword_analysis.keyword_density).sort(([, a], [, b]) => b - a).map(([kw, count]) => (
                  <div key={kw} className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-primary-50/40"><span className="capitalize text-gray-700">{kw}</span><span className="text-xs font-medium text-gray-400">{count}x</span></div>
                ))}
              </div>
            </div>
          )}

          {keyword_analysis.action_keywords_missing.length > 0 && (
            <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 p-4 shadow-xs"><h4 className="mb-2 text-sm font-semibold text-amber-800">Missing Keywords</h4><div className="flex flex-wrap gap-1.5">{keyword_analysis.action_keywords_missing.map((kw, i) => <span key={i} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">{kw}</span>)}</div></div>
          )}
        </div>
      )}

      {tab === "recommendations" && (
        <div className="space-y-4">
          {recommendations.length === 0 ? <p className="text-sm text-gray-500">No recommendations</p> : (
            recommendations.map((r, i) => (
              <div key={i} className={r.priority === "high" ? "rounded-xl border border-amber-200/80 bg-amber-50/80 p-4 shadow-xs" : "card p-4"}>
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${r.priority === "high" ? "bg-amber-100 text-amber-700" : "bg-primary-50 text-primary-700"}`}>{i + 1}</span>
                  <div><p className="text-sm text-gray-700">{r.text}</p></div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "compare" && (
        <div className="space-y-6">
          {compare ? (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="card p-5">
                  <h3 className="mb-3 text-sm font-semibold text-gray-900">Current (v{compare.current.version})</h3>
                  <div className="space-y-2">{(["overall", "completeness", "readability", "professionalism", "keyword_optimization", "ats_compatibility"] as const).map((key) => {
                    const s = compare.current.scores[key];
                    const change = compare.score_changes[key];
                    return <div key={key} className="flex items-center justify-between text-sm"><span className="text-gray-500">{s.label}</span><span className="font-medium text-gray-900">{s.score}{change !== undefined && <span className={`ml-2 text-xs font-semibold ${change >= 0 ? "text-emerald-600" : "text-red-600"}`}>{change >= 0 ? "+" : ""}{change}</span>}</span></div>;
                  })}</div>
                  <p className="mt-3 text-xs text-gray-400">{compare.current.total_skills} skills</p>
                </div>
                {compare.previous && (
                  <div className="card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-gray-900">Previous (v{compare.previous.version})</h3>
                    <div className="space-y-2">{(["overall", "completeness", "readability", "professionalism", "keyword_optimization", "ats_compatibility"] as const).map((key) => {
                      const s = compare.previous!.scores[key];
                      return <div key={key} className="flex items-center justify-between text-sm"><span className="text-gray-500">{s.label}</span><span className="font-medium text-gray-900">{s.score}</span></div>;
                    })}</div>
                    <p className="mt-3 text-xs text-gray-400">{compare.previous.total_skills} skills</p>
                  </div>
                )}
              </div>
              {compare.skills_added.length > 0 && (
                <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/80 p-4 shadow-xs"><h4 className="mb-2 text-sm font-semibold text-emerald-800">Skills Added</h4><div className="flex flex-wrap gap-1.5">{compare.skills_added.map((s, i) => <span key={i} className="badge-success">{s}</span>)}</div></div>
              )}
              {compare.skills_removed.length > 0 && (
                <div className="rounded-xl border border-red-200/80 bg-red-50/80 p-4 shadow-xs"><h4 className="mb-2 text-sm font-semibold text-red-800">Skills Removed</h4><div className="flex flex-wrap gap-1.5">{compare.skills_removed.map((s, i) => <span key={i} className="badge-danger">{s}</span>)}</div></div>
              )}
              {!compare.previous && <p className="text-sm text-gray-500">Only one version available. Upload another resume to compare.</p>}
            </>
          ) : <p className="text-sm text-gray-500">Comparison data not available.</p>}
        </div>
      )}
    </div>
  );
}
