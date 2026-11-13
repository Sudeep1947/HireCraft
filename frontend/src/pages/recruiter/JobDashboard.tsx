import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useToast } from "../../contexts/ToastContext";
import { recruiterJobApi } from "../../api/jobs";
import type { JobListItem, RecruiterDashboard } from "../../types/jobs";

export function RecruiterJobDashboard() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [dashboard, setDashboard] = useState<RecruiterDashboard | null>(null);
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [dash, jobList] = await Promise.all([
          recruiterJobApi.getDashboard(),
          recruiterJobApi.listJobs(),
        ]);
        setDashboard(dash);
        setJobs(jobList);
      } catch {
        addToast("Failed to load job dashboard", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up" aria-busy="true" aria-label="Loading job dashboard">
        <div className="skeleton h-9 w-56" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-4 w-24" />
              <div className="skeleton mt-2 h-8 w-16" />
            </div>
          ))}
        </div>
        <div className="skeleton h-64 w-full" />
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Job Management</h1>
          <p className="page-subtitle">Create and manage job postings</p>
        </div>
        <button
          onClick={() => navigate("/recruiter/jobs/create")}
          className="btn-primary btn-md"
        >
          Post New Job
        </button>
      </div>

      {dashboard && (
        <div className="grid grid-cols-1 gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card card-hover p-5">
            <p className="text-sm font-medium text-gray-500">Total Jobs</p>
            <p className="mt-1.5 kpi-value">{dashboard.total_jobs}</p>
          </div>
          <div className="card card-hover p-5">
            <p className="text-sm font-medium text-gray-500">Published</p>
            <p className="mt-1.5 font-display text-3xl font-bold tracking-tight text-emerald-600">{dashboard.published_jobs}</p>
          </div>
          <div className="card card-hover p-5">
            <p className="text-sm font-medium text-gray-500">Drafts</p>
            <p className="mt-1.5 font-display text-3xl font-bold tracking-tight text-amber-600">{dashboard.draft_jobs}</p>
          </div>
          <div className="card card-hover p-5">
            <p className="text-sm font-medium text-gray-500">Total Applications</p>
            <p className="mt-1.5 font-display text-3xl font-bold tracking-tight text-primary-600">{dashboard.total_applications}</p>
          </div>
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="empty-state">
          <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
          <p className="text-gray-500">No job postings yet.</p>
          <button
            onClick={() => navigate("/recruiter/jobs/create")}
            className="btn-secondary btn-sm mt-4"
          >
            Create your first job posting
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Applications</th>
                <th>Deadline</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <div className="font-medium text-gray-900">{job.title}</div>
                    <div className="text-sm text-gray-500">{job.company} · {job.location}</div>
                  </td>
                  <td>
                    <span className={`badge ${
                      job.status === "published" ? "badge-success" :
                      job.status === "draft" ? "badge-warning" :
                      "badge-neutral"
                    }`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="text-gray-500">{job.application_count}</td>
                  <td className="text-gray-500">
                    {job.application_deadline || "No deadline"}
                  </td>
                  <td className="text-right">
                    <button
                      onClick={() => navigate(`/recruiter/jobs/${job.id}`)}
                      className="text-sm font-medium text-primary-600 hover:text-primary-700"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dashboard && dashboard.recent_applications.length > 0 && (
        <div>
          <h2 className="section-title mb-3">Recent Applications</h2>
          <div className="space-y-2">
            {dashboard.recent_applications.map((app) => (
              <div key={app.id} className="card p-4 text-sm">
                <span className="font-medium text-gray-900">{app.candidate_name}</span>
                <span className="text-gray-500"> applied for </span>
                <span className="font-medium text-gray-900">{app.job_title}</span>
                <span className={`badge ml-2 ${
                  app.status === "applied" ? "badge-info" :
                  app.status === "shortlisted" ? "badge-primary" :
                  "badge-neutral"
                }`}>
                  {app.status.replace(/_/g, " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
