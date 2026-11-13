import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { candidateJobApi } from "../../api/jobs";
import type { CandidateJobDashboard, JobSearchResult } from "../../types/jobs";

export function JobPortal() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [dashboard, setDashboard] = useState<CandidateJobDashboard | null>(null);
  const [searchResult, setSearchResult] = useState<JobSearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [q, setQ] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [location, setLocation] = useState("");
  const [page, setPage] = useState(1);

  async function doSearch(pageNum = 1) {
    setSearching(true);
    try {
      const result = await candidateJobApi.searchJobs({
        q: q || undefined,
        employment_type: employmentType || undefined,
        location: location || undefined,
        page: pageNum,
        page_size: 10,
      });
      setSearchResult(result);
      setPage(pageNum);
    } catch {
      addToast("Failed to search jobs", "error");
    } finally {
      setSearching(false);
    }
  }

  useEffect(() => {
    async function load() {
      try {
        const [dash] = await Promise.all([
          candidateJobApi.getDashboard(),
        ]);
        setDashboard(dash);
      } catch {
        addToast("Failed to load job dashboard", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
    doSearch();
  }, []);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="animate-fade-up space-y-6">
      <div className="page-header">
        <h1 className="page-title">Job Portal</h1>
        <p className="page-subtitle">Browse and apply for jobs</p>
      </div>

      {dashboard && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-[8px] border border-gray-200 bg-white p-4 shadow-xs">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Applications</p>
            <p className="mt-1 text-2xl font-bold tracking-tight text-indigo-600">{dashboard.total_applications}</p>
          </div>
          <div className="rounded-[8px] border border-gray-200 bg-white p-4 shadow-xs">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Saved Jobs</p>
            <p className="mt-1 text-2xl font-bold tracking-tight text-yellow-600">{dashboard.saved_jobs}</p>
          </div>
          <div className="rounded-[8px] border border-gray-200 bg-white p-4 shadow-xs">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Active Applications</p>
            <p className="mt-1 text-2xl font-bold tracking-tight text-green-600">{dashboard.status_breakdown?.applied || 0}</p>
          </div>
        </div>
      )}

      <div className="rounded-[8px] border border-gray-200 bg-white p-4 shadow-xs">
        <div className="flex flex-wrap gap-3">
          <input
            className="min-w-40 flex-1 rounded-[6px] border border-gray-300 bg-white px-3.5 py-2 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            placeholder="Search jobs..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
          />
          <select
            className="w-auto rounded-[6px] border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            value={employmentType}
            onChange={(e) => setEmploymentType(e.target.value)}
            aria-label="Employment type"
          >
            <option value="">All Types</option>
            <option value="full_time">Full Time</option>
            <option value="part_time">Part Time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
            <option value="freelance">Freelance</option>
          </select>
          <input
            className="w-48 rounded-[6px] border border-gray-300 bg-white px-3.5 py-2 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            placeholder="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
          />
          <button onClick={() => doSearch()} disabled={searching} className="btn-primary rounded-[6px]">
            {searching ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {searchResult && searchResult.items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-[8px] border border-dashed border-gray-300 bg-white/70 px-6 py-12 text-center">
          <p className="text-gray-500">No jobs found matching your criteria.</p>
        </div>
      )}

      {searchResult && searchResult.items.length > 0 && (
        <div className="space-y-3">
          {searchResult.items.map((job) => (
            <div key={job.id} className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs transition-all hover:border-indigo-200 hover:shadow-sm">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex-1">
                  <h3
                    className="cursor-pointer text-lg font-semibold text-indigo-600 transition-colors hover:text-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                    onClick={() => navigate(`/candidate/jobs/${job.id}`)}
                  >
                    {job.title}
                  </h3>
                  <p className="text-sm text-gray-600">{job.company} · {job.location}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="badge-info">
                      {job.employment_type.replace(/_/g, " ")}
                    </span>
                    {job.salary_min && job.salary_max && (
                      <span className="badge-success">
                        {job.salary_currency} {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                      </span>
                    )}
                    {job.application_deadline && (
                      <span className="badge-warning">
                        Deadline: {job.application_deadline}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col gap-2">
                  <button
                    onClick={() => navigate(`/candidate/jobs/${job.id}`)}
                    className="btn-primary rounded-[6px]"
                  >
                    Apply
                  </button>
                  <button
                    onClick={() => navigate(`/candidate/mock-interview?jobId=${job.id}`)}
                    className="btn-secondary rounded-[6px]"
                  >
                    Mock Interview
                  </button>
                </div>
              </div>
            </div>
          ))}

          {searchResult.total_pages > 1 && (
            <div className="flex justify-center gap-2">
              {Array.from({ length: searchResult.total_pages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => doSearch(p)}
                  aria-current={page === p ? "page" : undefined}
                  className={page === p ? "btn-primary rounded-[6px] px-3 py-1" : "btn-ghost rounded-[6px] border border-gray-200 bg-white px-3 py-1"}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
