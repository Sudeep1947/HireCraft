import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useToast } from "../../contexts/ToastContext";
import { getRecruiterAIDashboard, getTopCandidates } from "../../api/screening";
import type { RecruiterDashboardSummary, TopCandidatesResponse } from "../../types/screening";

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#0ea5e9" : score >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="6" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`} />
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
        className="font-bold" fill={color} fontSize={size * 0.25}>
        {score}
      </text>
    </svg>
  );
}

function StatBox({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="card card-hover p-5">
      <p className="section-label">{label}</p>
      <p className={`mt-1.5 font-display text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

export function RecruiterAIInsights() {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<RecruiterDashboardSummary | null>(null);
  const [topCandidates, setTopCandidates] = useState<TopCandidatesResponse | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [dash, top] = await Promise.all([
          getRecruiterAIDashboard(),
          getTopCandidates(undefined, 5),
        ]);
        setDashboard(dash);
        setTopCandidates(top);
      } catch {
        addToast("Failed to load AI insights", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);

  if (loading)
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading AI insights">
        <div className="skeleton h-9 w-72" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-4 w-20" />
              <div className="skeleton mt-2 h-8 w-16" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="skeleton h-80 w-full" />
          <div className="skeleton h-80 w-full" />
        </div>
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">AI Hiring Intelligence</h1>
        <p className="page-subtitle">Comprehensive AI-powered insights across your recruitment pipeline</p>
      </div>

      {dashboard && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatBox label="Total Jobs" value={dashboard.total_jobs} color="text-sky-600" />
            <StatBox label="Applications" value={dashboard.total_applications} color="text-violet-600" />
            <StatBox label="AI Screened" value={dashboard.total_screened} color="text-emerald-600" />
            <StatBox label="Avg Score" value={`${dashboard.average_score}%`} color={dashboard.average_score >= 70 ? "text-emerald-600" : "text-amber-600"} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="card p-6">
              <h3 className="section-title mb-4">Job Pipeline Overview</h3>
              <div className="space-y-3">
                {dashboard.job_summaries.map((job) => (
                  <Link
                    key={job.job_id}
                    to={`/recruiter/jobs/${job.job_id}/rankings`}
                    className="flex items-center justify-between rounded-xl border border-gray-100 p-3 transition-colors hover:bg-primary-50/40"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-gray-900">{job.job_title}</p>
                      <p className="text-xs text-gray-500">{job.applicant_count} applicants &middot; {job.screened_count} screened</p>
                    </div>
                    <div className="flex items-center gap-3">
                      {job.top_candidate_name && (
                        <div className="hidden text-right sm:block">
                          <p className="text-xs text-gray-500">Top: {job.top_candidate_name}</p>
                          <p className="text-xs font-bold text-emerald-600">{job.top_candidate_score}%</p>
                        </div>
                      )}
                      <ScoreRing score={job.average_score} size={48} />
                    </div>
                  </Link>
                ))}
                {dashboard.job_summaries.length === 0 && (
                  <p className="py-4 text-center text-sm text-gray-500">No jobs created yet</p>
                )}
              </div>
            </div>

            <div className="card p-6">
              <h3 className="section-title mb-4">Recent Candidate Activity</h3>
              <div className="space-y-3">
                {dashboard.recent_rankings.map((r, i) => (
                  <div key={i} className="flex items-center justify-between rounded-xl border border-gray-100 p-3">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{r.candidate_name}</p>
                      <p className="text-xs text-gray-500">{r.job_title}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-gray-400">#{r.rank}</span>
                      <span className={`badge ${
                        r.score >= 80 ? "badge-success" :
                        r.score >= 60 ? "badge-info" :
                        r.score >= 40 ? "badge-warning" :
                        "badge-danger"
                      }`}>
                        {r.score}%
                      </span>
                      {r.rank_change > 0 && <span className="text-xs text-emerald-600">+{r.rank_change}</span>}
                      {r.rank_change < 0 && <span className="text-xs text-red-500">{r.rank_change}</span>}
                    </div>
                  </div>
                ))}
                {dashboard.recent_rankings.length === 0 && (
                  <p className="py-4 text-center text-sm text-gray-500">No recent activity</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {topCandidates && topCandidates.candidates.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-4">Top Candidates Across All Jobs</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Candidate</th>
                  <th className="text-center">Score</th>
                  <th className="text-center">Level</th>
                  <th className="text-center">Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {topCandidates.candidates.map((c, i) => (
                  <tr key={i}>
                    <td className="font-bold text-gray-400">#{c.rank}</td>
                    <td>
                      <p className="font-medium text-gray-900">{c.candidate_name}</p>
                      <p className="text-xs text-gray-500">{c.candidate_email}</p>
                    </td>
                    <td className="text-center">
                      <span className={`badge ${
                        c.overall_score >= 80 ? "badge-success" :
                        c.overall_score >= 60 ? "badge-info" :
                        c.overall_score >= 40 ? "badge-warning" :
                        "badge-danger"
                      }`}>
                        {c.overall_score}%
                      </span>
                    </td>
                    <td className="text-center">
                      <span className={`text-xs font-medium capitalize ${
                        c.strength_level === "excellent" ? "text-emerald-600" :
                        c.strength_level === "good" ? "text-sky-600" :
                        c.strength_level === "average" ? "text-amber-600" : "text-red-600"
                      }`}>
                        {c.strength_level}
                      </span>
                    </td>
                    <td className="text-center">
                      <span className={`text-xs font-medium ${
                        c.recommendation === "strongly_recommend" ? "text-emerald-700" :
                        c.recommendation === "recommend" ? "text-sky-700" :
                        c.recommendation === "consider" ? "text-amber-700" : "text-red-700"
                      }`}>
                        {c.recommendation.replace(/_/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase())}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
