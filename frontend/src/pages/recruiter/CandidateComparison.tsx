import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";

import { useToast } from "../../contexts/ToastContext";
import { compareCandidates } from "../../api/screening";
import type { CandidateComparisonResponse } from "../../types/screening";

function ScoreBarVisual({ label, scoreA, scoreB }: { label: string; scoreA: number; scoreB: number }) {
  const colorA = scoreA >= 80 ? "bg-emerald-500" : scoreA >= 60 ? "bg-sky-500" : scoreA >= 40 ? "bg-amber-500" : "bg-red-500";
  const colorB = scoreB >= 80 ? "bg-emerald-500" : scoreB >= 60 ? "bg-sky-500" : scoreB >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1">
      <p className="text-center text-xs font-medium text-gray-500">{label}</p>
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
          <div className={`h-full rounded-full ${colorA}`} style={{ width: `${scoreA}%` }} />
        </div>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
          <div className={`h-full rounded-full ${colorB}`} style={{ width: `${scoreB}%` }} />
        </div>
      </div>
    </div>
  );
}

export function CandidateComparison() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [comparison, setComparison] = useState<CandidateComparisonResponse | null>(null);

  const candidateIds = searchParams.get("ids")?.split(",") || [];

  useEffect(() => {
    if (!id || candidateIds.length < 2) {
      setLoading(false);
      return;
    }
    async function load() {
      try {
        const data = await compareCandidates(id!, candidateIds);
        setComparison(data);
      } catch {
        addToast("Failed to load comparison", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, candidateIds.join(","), addToast]);

  if (loading)
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading comparison">
        <div className="skeleton h-9 w-72" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="skeleton h-96 w-full" />
          <div className="skeleton h-96 w-full" />
        </div>
      </div>
    );

  if (!comparison || comparison.candidates.length < 2) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="btn-ghost btn-sm -ml-3 text-gray-500 hover:text-gray-700">&larr; Back</button>
          <h1 className="page-title">Candidate Comparison</h1>
        </div>
        <div className="empty-state">
          <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
          </svg>
          <h3 className="text-base font-semibold text-gray-900">Nothing to compare yet</h3>
          <p className="mt-1 text-sm text-gray-500">Select at least 2 candidates to compare from the rankings page.</p>
        </div>
      </div>
    );
  }

  const [a, b] = comparison.candidates;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="btn-ghost btn-sm -ml-3 text-gray-500 hover:text-gray-700">&larr; Back</button>
        <div>
          <h1 className="page-title">Candidate Comparison</h1>
          <p className="page-subtitle">{comparison.job_title}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {[a, b].map((c, idx) => (
          <div key={c.candidate_id} className="card p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <span className="section-label">{idx === 0 ? "Candidate A" : "Candidate B"}</span>
                <h3 className="text-lg font-semibold text-gray-900">{c.candidate_name}</h3>
                <p className="text-sm text-gray-500">{c.candidate_email}</p>
              </div>
              <span className={`badge ${
                c.overall_match_score >= 80 ? "badge-success" :
                c.overall_match_score >= 60 ? "badge-info" :
                c.overall_match_score >= 40 ? "badge-warning" :
                "badge-danger"
              } px-3 py-1 text-sm`}>
                {c.overall_match_score}%
              </span>
            </div>

            <div className="mb-4 space-y-1.5">
              {[
                { label: "Skills", score: c.skill_match_score },
                { label: "Experience", score: c.experience_match_score },
                { label: "Education", score: c.education_match_score },
                { label: "Projects", score: c.project_match_score },
                { label: "Certifications", score: c.certification_match_score },
              ].map(({ label, score }) => (
                <div key={label} className="flex items-center gap-2">
                  <span className="w-24 shrink-0 text-xs text-gray-500">{label}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={`h-full rounded-full ${
                        score >= 80 ? "bg-emerald-500" : score >= 60 ? "bg-sky-500" : score >= 40 ? "bg-amber-500" : "bg-red-500"
                      }`}
                      style={{ width: `${score}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs font-medium text-gray-700">{score}%</span>
                </div>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap gap-1.5">
              {c.matched_skills?.map((s: string) => (
                <span key={s} className="badge badge-success">{s}</span>
              ))}
            </div>
            {c.missing_required_skills && c.missing_required_skills.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {c.missing_required_skills.map((s: string) => (
                  <span key={s} className="badge badge-danger">{s}</span>
                ))}
              </div>
            )}
            <p className={`text-sm font-medium ${
              c.recommendation === "strongly_recommend" || c.recommendation === "recommend"
                ? "text-emerald-700" : c.recommendation === "consider" ? "text-amber-700" : "text-red-700"
            }`}>
              {c.recommendation.replace(/_/g, " ").replace(/\b\w/g, (ch: string) => ch.toUpperCase())}
            </p>
          </div>
        ))}
      </div>

      <div className="card p-6">
        <h3 className="section-title mb-4">Head-to-Head</h3>
        <div className="space-y-2">
          {[
            { label: "Overall", scoreA: a.overall_match_score, scoreB: b.overall_match_score },
            { label: "Skills", scoreA: a.skill_match_score, scoreB: b.skill_match_score },
            { label: "Experience", scoreA: a.experience_match_score, scoreB: b.experience_match_score },
            { label: "Education", scoreA: a.education_match_score, scoreB: b.education_match_score },
            { label: "Projects", scoreA: a.project_match_score, scoreB: b.project_match_score },
            { label: "Certifications", scoreA: a.certification_match_score, scoreB: b.certification_match_score },
          ].map((item) => (
            <ScoreBarVisual key={item.label} label={item.label} scoreA={item.scoreA} scoreB={item.scoreB} />
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
          <span className="font-medium">{a.candidate_name}</span>
          <span className="font-medium">{b.candidate_name}</span>
        </div>
      </div>
    </div>
  );
}
