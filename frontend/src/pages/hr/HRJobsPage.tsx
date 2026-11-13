import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Briefcase } from "lucide-react";

import { hrApi } from "../../api/hrOversight";
import type { HRJobList } from "../../api/hrOversight";
import { useToast } from "../../contexts/ToastContext";
import { applicationStatusLabel, formatDateTime } from "./hrOversightFormat";

/**
 * Revised Phase 14 -- HR job drill-down (step 2 of 3).
 *
 * Lists the jobs this HR user is entitled to read, each with its recruiter and
 * its real per-status application counts, and links onward to that job's
 * applications. The recruiter relationship is the platform's existing
 * `Job.recruiter_id` -- no new association is invented here.
 */
export function HRJobsPage() {
  const { addToast } = useToast();
  const [data, setData] = useState<HRJobList | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    hrApi
      .getJobs()
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load jobs", "error");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [addToast]);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-9 w-40" />
          <div className="skeleton h-4 w-80 max-w-full" />
        </div>
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-40 w-full" />
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load jobs</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Jobs</h1>
          <p className="page-subtitle">
            Every job in your scope, with its live application funnel.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/hr/oversight" className="btn-secondary btn-md">
            Back to Overview
          </Link>
        </div>
      </div>

      <div className="info-banner">
        Scope: {data.is_platform_scope ? "Platform-wide (all organizations)" : "Your organizations"} ·{" "}
        {data.total} job{data.total === 1 ? "" : "s"}
      </div>

      {data.jobs.length === 0 ? (
        <div className="empty-state">
          <Briefcase className="mb-3 h-10 w-10 text-gray-300" />
          <h3 className="text-base font-semibold text-gray-900">No jobs</h3>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            There are no jobs in your scope yet.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.jobs.map((job) => (
            <div key={job.id} className="card rounded-xl p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="section-title">{job.title}</h2>
                  <p className="text-sm text-gray-500">
                    {job.company}
                    {job.department ? ` · ${job.department}` : ""}
                    {job.location ? ` · ${job.location}` : ""}
                  </p>
                  <p className="mt-1 text-sm text-gray-600">
                    Recruiter:{" "}
                    <span className="font-medium">{job.recruiter_name ?? "Unassigned"}</span>
                  </p>
                </div>
                <Link
                  to={`/hr/jobs/${job.id}/applications`}
                  className="btn-primary btn-sm"
                >
                  View {job.application_count} application
                  {job.application_count === 1 ? "" : "s"}
                </Link>
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">Total</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {job.application_count}
                  </dd>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">In pipeline</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {job.open_application_count}
                  </dd>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">Hired</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {job.hired_count}
                  </dd>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">Posted</dt>
                  <dd className="mt-0.5 text-sm text-gray-700">
                    {formatDateTime(job.created_at)}
                  </dd>
                </div>
              </dl>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-gray-500">Status:</span>
                <span className="badge-neutral capitalize">{job.status}</span>
                {/*
                  Each funnel stage links to the applications behind that one
                  stage on this job, so a count on this screen is always one
                  click from the records that produced it.
                */}
                {Object.entries(job.applications_by_status).map(([status, count]) => (
                  <Link
                    key={status}
                    to={`/hr/jobs/${job.id}/applications?status=${status}`}
                    className="chip"
                  >
                    {applicationStatusLabel(status)}: {count}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-500">
        Open a job to review the applications behind its funnel. HR cannot change application
        state from these screens.
      </p>
    </div>
  );
}

/** Small helper reused by the applications page header. */
export function jobStatusCaption(status: string): string {
  return applicationStatusLabel(status);
}
