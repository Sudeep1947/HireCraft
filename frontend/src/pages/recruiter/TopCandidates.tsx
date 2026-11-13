import { useEffect, useState } from "react";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { getTopCandidates } from "../../api/screening";
import type { TopCandidatesResponse, TopCandidateItem } from "../../types/screening";

function RankBadge({ rank }: { rank: number }) {
  if (rank <= 3) {
    const colors = [
      "bg-amber-100 text-amber-800 ring-amber-300/60",
      "bg-gray-100 text-gray-700 ring-gray-300/60",
      "bg-orange-100 text-orange-800 ring-orange-300/60",
    ];
    return (
      <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ring-1 ring-inset ${colors[rank - 1]}`}>
        {rank}
      </span>
    );
  }
  return <span className="text-sm font-bold text-gray-400">#{rank}</span>;
}

function CandidateCard({ candidate }: { candidate: TopCandidateItem }) {
  const scoreColor =
    candidate.overall_score >= 80 ? "text-emerald-600" :
    candidate.overall_score >= 60 ? "text-sky-600" :
    candidate.overall_score >= 40 ? "text-amber-600" : "text-red-600";

  const levelColor =
    candidate.strength_level === "excellent" ? "badge-success" :
    candidate.strength_level === "good" ? "badge-info" :
    candidate.strength_level === "average" ? "badge-warning" :
    "badge-danger";

  const recLabel = candidate.recommendation.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const recColor =
    candidate.recommendation === "strongly_recommend" ? "text-emerald-700" :
    candidate.recommendation === "recommend" ? "text-sky-700" :
    candidate.recommendation === "consider" ? "text-amber-700" : "text-red-700";

  return (
    <div className="card card-hover p-5">
      <div className="flex items-start gap-4">
        <RankBadge rank={candidate.rank} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-gray-900">{candidate.candidate_name}</h3>
              <p className="truncate text-sm text-gray-500">{candidate.candidate_email}</p>
            </div>
            <div className="text-right">
              <p className={`font-display text-2xl font-bold ${scoreColor}`}>{candidate.overall_score}%</p>
              {candidate.rank_change !== 0 && (
                <p className={`text-xs font-medium ${candidate.rank_change > 0 ? "text-emerald-600" : "text-red-500"}`}>
                  {candidate.rank_change > 0 ? `+${candidate.rank_change}` : candidate.rank_change} positions
                </p>
              )}
            </div>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <span className={levelColor}>
              {candidate.strength_level}
            </span>
            <span className={`text-xs font-medium ${recColor}`}>{recLabel}</span>
          </div>

          <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
            <span>Skills: {candidate.skill_match}%</span>
            <span>Experience: {candidate.experience_match}%</span>
          </div>

          {candidate.matched_skills.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {candidate.matched_skills.slice(0, 6).map((s) => (
                <span key={s} className="badge badge-success">{s}</span>
              ))}
              {candidate.matched_skills.length > 6 && (
                <span className="badge badge-neutral">
                  +{candidate.matched_skills.length - 6} more
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function TopCandidatesPage() {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<TopCandidatesResponse | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const result = await getTopCandidates(undefined, 20);
        setData(result);
      } catch {
        addToast("Failed to load top candidates", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">Top Candidates</h1>
        <p className="page-subtitle">AI-ranked best-fit candidates across your job postings</p>
      </div>

      {data && data.candidates.length > 0 ? (
        <div className="space-y-3">
          {data.candidates.map((c) => (
            <CandidateCard key={`${c.candidate_id}-${c.candidate_name}`} candidate={c} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
          </svg>
          <h3 className="text-base font-semibold text-gray-900">No candidates ranked yet</h3>
          <p className="mt-1 text-sm text-gray-500">No candidates have been ranked yet. Run AI screening on your job postings first.</p>
        </div>
      )}
    </div>
  );
}
