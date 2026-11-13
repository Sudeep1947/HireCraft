import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { candidateJobApi } from "../../api/jobs";
import type { JobListItem } from "../../types/jobs";

export function SavedJobs() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [savedJobs, setSavedJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await candidateJobApi.getSavedJobs();
        setSavedJobs(data);
      } catch {
        addToast("Failed to load saved jobs", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);

  async function handleUnsave(jobId: string) {
    try {
      await candidateJobApi.unsaveJob(jobId);
      setSavedJobs(savedJobs.filter((j) => j.id !== jobId));
      addToast("Job removed from saved list", "success");
    } catch {
      addToast("Failed to unsave job", "error");
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="animate-fade-up space-y-6">
      <div className="page-header">
        <h1 className="page-title">Saved Jobs</h1>
        <p className="page-subtitle">Jobs you've saved for later</p>
      </div>

      {savedJobs.length === 0 ? (
        <div className="empty-state">
          <p className="text-gray-500">No saved jobs yet.</p>
          <button
            onClick={() => navigate("/candidate/jobs")}
            className="btn-ghost mt-4"
          >
            Browse jobs
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {savedJobs.map((job) => (
            <div key={job.id} className="card transition-shadow hover:shadow-md">
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
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    onClick={() => navigate(`/candidate/jobs/${job.id}`)}
                    className="btn-primary"
                  >
                    Apply
                  </button>
                  <button
                    onClick={() => handleUnsave(job.id)}
                    className="btn-secondary"
                  >
                    Unsave
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
