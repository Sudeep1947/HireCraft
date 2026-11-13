import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { MatchScoreCard } from "../../components/screening/MatchScoreCard";
import { useToast } from "../../contexts/ToastContext";
import { screenJobApplicants, getJobRankings, getScreeningResult } from "../../api/screening";
import { recruiterJobApi } from "../../api/jobs";
import type { JobListItem } from "../../types/jobs";
import type { CandidateRanking, ScreeningResult } from "../../types/screening";

export function RecruiterCandidateRanking() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [activeJobId, setActiveJobId] = useState<string>(id || "");
  const [rankings, setRankings] = useState<CandidateRanking[]>([]);
  const [selectedRanking, setSelectedRanking] = useState<CandidateRanking | null>(null);
  const [selectedScreening, setSelectedScreening] = useState<ScreeningResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [screeningLoading, setScreeningLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());

  // Load jobs if no id provided in url
  useEffect(() => {
    if (id) {
      setActiveJobId(id);
      return;
    }
    recruiterJobApi
      .listJobs()
      .then((items) => {
        setJobs(items);
        if (items.length > 0) {
          setActiveJobId(items[0].id);
        } else {
          setLoading(false);
        }
      })
      .catch(() => {
        addToast("Failed to load jobs", "error");
        setLoading(false);
      });
  }, [id, addToast]);

  useEffect(() => {
    if (!activeJobId) return;
    let active = true;
    setLoading(true);
    setSelectedRanking(null);
    setSelectedScreening(null);
    async function load() {
      try {
        const data = await getJobRankings(activeJobId);
        if (active) setRankings(data.items);
      } catch {
        if (active) addToast("Failed to load rankings", "error");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [activeJobId, addToast]);

  async function handleScreenAll() {
    if (!activeJobId) return;
    setScanning(true);
    try {
      const result = await screenJobApplicants(activeJobId);
      addToast(`Screened ${result.candidates_screened} candidates`, "success");
      const data = await getJobRankings(activeJobId);
      setRankings(data.items);
    } catch {
      addToast("Failed to screen candidates", "error");
    } finally {
      setScanning(false);
    }
  }

  async function handleViewDetails(candidateId: string) {
    if (!activeJobId) return;
    setScreeningLoading(true);
    try {
      const data = await getScreeningResult(activeJobId, candidateId);
      setSelectedScreening(data);
      const ranking = rankings.find((r) => r.candidate_id === candidateId);
      if (ranking) setSelectedRanking(ranking);
    } catch {
      addToast("Failed to load screening details", "error");
    } finally {
      setScreeningLoading(false);
    }
  }

  function toggleCompare(candidateId: string) {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(candidateId)) next.delete(candidateId);
      else if (next.size < 4) next.add(candidateId);
      return next;
    });
  }

  function handleCompare() {
    if (compareIds.size >= 2 && activeJobId) {
      navigate(`/recruiter/jobs/${activeJobId}/compare?ids=${Array.from(compareIds).join(",")}`);
    }
  }

  if (loading)
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading rankings">
        <div className="skeleton h-9 w-64" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="skeleton h-96 w-full lg:col-span-1" />
          <div className="skeleton h-96 w-full lg:col-span-2" />
        </div>
      </div>
    );

  if (!activeJobId) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="page-header">
          <div>
            <h1 className="page-title">Candidate Rankings</h1>
            <p className="page-subtitle">Rank candidates across jobs by AI matching</p>
          </div>
        </div>
        <div className="empty-state">
          <h3 className="text-base font-semibold text-gray-900">No jobs available</h3>
          <p className="mt-1 text-sm text-gray-500">Create a job first to view candidate AI rankings.</p>
          <button
            onClick={() => navigate("/recruiter/jobs/create")}
            className="btn-primary btn-sm mt-4"
          >
            Create Job
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="page-title">Candidate Rankings</h1>
          <p className="page-subtitle">{rankings.length} candidates ranked by AI matching</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {jobs.length > 0 && !id && (
            <div className="flex items-center gap-2">
              <label htmlFor="jobSelect" className="text-xs font-semibold text-gray-500 uppercase">
                Job:
              </label>
              <select
                id="jobSelect"
                value={activeJobId}
                onChange={(e) => setActiveJobId(e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none"
              >
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} {j.company ? `(${j.company})` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
          {compareIds.size >= 2 && (
            <button
              onClick={handleCompare}
              className="btn-secondary btn-md"
            >
              Compare ({compareIds.size})
            </button>
          )}
          <button
            onClick={handleScreenAll}
            disabled={scanning || !activeJobId}
            className="btn-primary btn-md"
          >
            {scanning ? "Screening..." : "Screen All Candidates"}
          </button>
        </div>
      </div>

      {rankings.length === 0 ? (
        <div className="empty-state">
          <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          <h3 className="text-base font-semibold text-gray-900">No candidates screened yet</h3>
          <p className="mt-1 text-sm text-gray-500">No candidates have been screened yet for this job.</p>
          <button
            onClick={handleScreenAll}
            disabled={scanning || !activeJobId}
            className="btn-primary btn-sm mt-4"
          >
            Screen all candidates now
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <div className="card-solid overflow-hidden">
              <div className="border-b border-gray-200 px-4 py-3">
                <h2 className="font-semibold text-gray-900">Ranked Candidates</h2>
              </div>
              <div className="max-h-[600px] divide-y divide-gray-100 overflow-y-auto">
                {rankings.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => handleViewDetails(r.candidate_id)}
                    className={`w-full px-4 py-3 text-left transition-colors hover:bg-primary-50/40 ${selectedRanking?.id === r.id ? "bg-primary-50/80" : ""}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={compareIds.has(r.candidate_id)}
                          onChange={(e) => { e.stopPropagation(); toggleCompare(r.candidate_id); }}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-gray-400">#{r.rank}</span>
                            <p className="text-sm font-medium text-gray-900">{r.candidate_name}</p>
                          </div>
                          <p className="truncate text-xs text-gray-500">{r.candidate_email}</p>
                        </div>
                      </div>
                      <span className={`badge ${
                        r.overall_score >= 80 ? "badge-success" :
                        r.overall_score >= 60 ? "badge-info" :
                        r.overall_score >= 40 ? "badge-warning" :
                        "badge-danger"
                      }`}>
                        {r.overall_score}%
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-2">
            {screeningLoading ? (
              <LoadingSpinner size="md" className="mt-10" />
            ) : selectedScreening ? (
              <MatchScoreCard
                screening={selectedScreening}
                candidateName={selectedRanking?.candidate_name}
              />
            ) : (
              <div className="empty-state">
                <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                </svg>
                <p className="text-sm text-gray-500">Select a candidate to view their screening details</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
