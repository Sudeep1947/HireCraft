import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { recruiterJobApi } from "../../api/jobs";
import type { Job, JobApplication } from "../../types/jobs";

export function RecruiterJobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [job, setJob] = useState<Job | null>(null);
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    async function load() {
      try {
        const [jobData, appData] = await Promise.all([
          recruiterJobApi.getJob(id!),
          recruiterJobApi.getApplications(id!),
        ]);
        setJob(jobData);
        setApplications(appData);
      } catch {
        addToast("Failed to load job details", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, addToast]);

  async function handleStatusChange(status: string) {
    if (!id) return;
    try {
      const updated = await recruiterJobApi.changeStatus(id, status);
      setJob(updated);
      addToast(`Job status updated to ${status.replace(/_/g, " ")}`, "success");
    } catch {
      addToast("Failed to update job status", "error");
    }
  }

  async function handleDelete() {
    if (!id || !window.confirm("Delete this job posting?")) return;
    try {
      await recruiterJobApi.deleteJob(id);
      addToast("Job deleted", "success");
      navigate("/recruiter/jobs");
    } catch {
      addToast("Failed to delete job", "error");
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (!job)
    return (
      <div className="empty-state mt-10">
        <p className="text-gray-500">Job not found</p>
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <button onClick={() => navigate("/recruiter/jobs")} className="btn-ghost btn-sm -ml-3 mb-2 text-primary-600 hover:text-primary-700">
            &larr; Back to Jobs
          </button>
          <h1 className="page-title">{job.title}</h1>
          <p className="page-subtitle">{job.company} · {job.location} · {job.employment_type.replace(/_/g, " ")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`badge ${
            job.status === "published" ? "badge-success" :
            job.status === "draft" ? "badge-warning" :
            "badge-neutral"
          }`}>
            {job.status}
          </span>
          <button onClick={() => navigate(`/recruiter/jobs/${id}/edit`)} className="btn-secondary btn-sm">
            Edit
          </button>
          <button onClick={handleDelete} className="btn-secondary btn-sm border-red-200 text-red-600 hover:border-red-300 hover:bg-red-50 hover:text-red-700">
            Delete
          </button>
          <button onClick={() => navigate(`/recruiter/jobs/${id}/applicants`)} className="btn-primary btn-sm">
            Screening dashboard
          </button>
        </div>
      </div>

      {job.status === "draft" && (
        <div className="flex items-start gap-2.5 rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-800 shadow-xs" role="status">
          <p className="text-sm">This job is in draft mode. <button onClick={() => handleStatusChange("published")} className="font-medium underline">Publish now</button></p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card p-6">
            <h2 className="section-title mb-3">Description</h2>
            <p className="whitespace-pre-wrap text-sm text-gray-700">{job.description}</p>
          </div>

          {job.benefits && (
            <div className="card p-6">
              <h2 className="section-title mb-3">Benefits</h2>
              <p className="whitespace-pre-wrap text-sm text-gray-700">{job.benefits}</p>
            </div>
          )}

          <div className="card p-6">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="section-title">Applicants ({applications.length})</h2>
              <button
                onClick={() => navigate(`/recruiter/jobs/${id}/applicants`)}
                className="btn-secondary btn-sm"
              >
                Open screening dashboard
              </button>
            </div>
            {applications.length === 0 ? (
              <p className="text-sm text-gray-500">No applications yet.</p>
            ) : (
              <div className="space-y-3">
                {applications.map((app) => (
                  <div key={app.id} className="rounded-xl border border-gray-200 bg-gray-50/50 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">{app.candidate_name}</p>
                        <p className="text-xs text-gray-500">{app.candidate_email}</p>
                      </div>
                      <span className={`badge ${
                        app.status === "applied" ? "badge-info" :
                        app.status === "shortlisted" ? "badge-primary" :
                        app.status === "rejected" ? "badge-danger" :
                        app.status === "hired" ? "badge-success" :
                        "badge-neutral"
                      }`}>
                        {app.status.replace(/_/g, " ")}
                      </span>
                    </div>
                    {app.cover_letter && (
                      <p className="mt-2 text-xs text-gray-600 line-clamp-2">{app.cover_letter}</p>
                    )}
                    <button
                      onClick={() => navigate(`/recruiter/jobs/${id}/applicants?application=${app.id}`)}
                      className="mt-2 text-xs font-medium text-primary-600 hover:text-primary-700"
                    >
                      View Details
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-5">
            <h3 className="mb-3 text-sm font-semibold text-gray-900">Job Details</h3>
            <dl className="space-y-2.5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-gray-500">Department</dt>
                <dd className="font-medium text-gray-900">{job.department || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-gray-500">Experience</dt>
                <dd className="font-medium text-gray-900">{job.experience_required || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-gray-500">Education</dt>
                <dd className="font-medium text-gray-900">{job.education_required || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-gray-500">Salary</dt>
                <dd className="font-medium text-gray-900">
                  {job.salary_min && job.salary_max ? `${job.salary_currency} ${job.salary_min.toLocaleString()} - ${job.salary_max.toLocaleString()}` : "Not specified"}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-gray-500">Deadline</dt>
                <dd className="font-medium text-gray-900">{job.application_deadline || "None"}</dd>
              </div>
            </dl>
          </div>

          <div className="card p-5">
            <h3 className="mb-3 text-sm font-semibold text-gray-900">Required Skills</h3>
            <div className="flex flex-wrap gap-2">
              {job.required_skills.map((s) => (
                <span key={s} className="badge badge-primary">{s}</span>
              ))}
              {job.required_skills.length === 0 && <span className="text-xs text-gray-400">None</span>}
            </div>
          </div>

          {job.preferred_skills && job.preferred_skills.length > 0 && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Preferred Skills</h3>
              <div className="flex flex-wrap gap-2">
                {job.preferred_skills.map((s) => (
                  <span key={s} className="badge badge-neutral">{s}</span>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-gray-900">Actions</h3>
            {job.status === "published" && (
              <button onClick={() => handleStatusChange("closed")} className="btn-secondary btn-md w-full">
                Close Job
              </button>
            )}
            {job.status === "closed" && (
              <button onClick={() => handleStatusChange("published")} className="btn-primary btn-md w-full">
                Reopen Job
              </button>
            )}
            {job.status !== "archived" && (
              <button onClick={() => handleStatusChange("archived")} className="btn-secondary btn-md w-full">
                Archive
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
