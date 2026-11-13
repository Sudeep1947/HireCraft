import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { hrApi } from "../../api/hrOversight";
import type { HRRecruiterDetail } from "../../api/hrOversight";
import { DashboardCard } from "../../components/dashboard";
import { useToast } from "../../contexts/ToastContext";
import {
  applicationStatusLabel,
  formatDateTime,
  formatRate,
} from "./hrOversightFormat";

/**
 * Revised Phase 14 -- one recruiter's oversight drill-down.
 *
 * A single request returns the recruiter aggregate and the jobs behind it, so the
 * screen can prove that the roll-up equals the sum of its parts rather than
 * asking the reader to trust a total.
 *
 * The backend answers 404 both for an unknown recruiter id and for one outside
 * the caller's organizations, so this screen reports "not available in your
 * scope" and never reveals whether an id exists in another tenant.
 */
export function HRRecruiterDetailPage() {
  const { recruiterId } = useParams<{ recruiterId: string }>();
  const { addToast } = useToast();
  const [data, setData] = useState<HRRecruiterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (!recruiterId) return;
    let active = true;
    setLoading(true);
    hrApi
      .getRecruiter(recruiterId)
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load recruiter", "error");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [recruiterId, addToast]);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-9 w-48" />
          <div className="skeleton h-4 w-64" />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((tile) => (
            <div key={tile} className="skeleton h-20" />
          ))}
        </div>
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>This recruiter is not available in your scope.</span>
        </div>
      </div>
    );
  }

  const { recruiter, jobs } = data;
  const sumOfJobs = jobs.reduce((total, job) => total + job.application_count, 0);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">{recruiter.full_name}</h1>
          <p className="page-subtitle">{recruiter.email ?? "No email on record"}</p>
        </div>
        <div className="flex gap-2">
          <Link to="/hr/recruiters" className="btn-secondary btn-md">
            Back to Recruiters
          </Link>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card rounded-xl p-4">
          <dt className="text-xs font-medium text-gray-500">Open jobs</dt>
          <dd className="mt-0.5 font-display text-xl font-bold text-gray-900">
            {recruiter.open_job_count}
          </dd>
        </div>
        <div className="card rounded-xl p-4">
          <dt className="text-xs font-medium text-gray-500">Applications</dt>
          <dd className="mt-0.5 font-display text-xl font-bold text-gray-900">
            {recruiter.application_count}
          </dd>
        </div>
        <div className="card rounded-xl p-4">
          <dt className="text-xs font-medium text-gray-500">Hired</dt>
          <dd className="mt-0.5 font-display text-xl font-bold text-gray-900">
            {recruiter.hired_count}
          </dd>
        </div>
        <div className="card rounded-xl p-4">
          <dt className="text-xs font-medium text-gray-500">Advancement rate</dt>
          <dd className="mt-0.5 font-display text-xl font-bold text-gray-900">
            {formatRate(recruiter.advancement_rate)}
          </dd>
        </div>
      </dl>

      <DashboardCard title={`Jobs (${jobs.length})`} className="rounded-xl">
        {/*
          The roll-up is checked against the rows beneath it. If the aggregate
          and its parts ever disagreed, the screen would say so rather than
          quietly presenting a total that nothing supports.
        */}
        {sumOfJobs !== recruiter.application_count && (
          <div className="mb-3 rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-700 shadow-xs">
            The totals above do not match the jobs listed below ({sumOfJobs} vs{" "}
            {recruiter.application_count}). Reload before relying on these figures.
          </div>
        )}

        {jobs.length === 0 ? (
          <p className="text-sm text-gray-500">No jobs are in scope.</p>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="rounded-xl border border-gray-200 bg-gray-50/60 p-4 transition-colors hover:border-primary-200"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">{job.title}</h3>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {job.company}
                      {job.department ? ` · ${job.department}` : ""} · Posted{" "}
                      {formatDateTime(job.created_at)}
                    </p>
                  </div>
                  <Link
                    to={`/hr/jobs/${job.id}/applications`}
                    className="text-sm font-medium text-primary-600 transition-colors hover:text-primary-700"
                  >
                    View applications
                  </Link>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(job.applications_by_status).map(
                    ([status, count]) => (
                      <Link
                        key={status}
                        to={`/hr/jobs/${job.id}/applications?status=${status}`}
                        className="chip"
                      >
                        {applicationStatusLabel(status)}: {count}
                      </Link>
                    ),
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </DashboardCard>

      <p className="text-xs text-gray-500">
        HR oversight is read-only. Application status, decisions, interviews and assessments stay
        with the recruiter who owns the job.
      </p>
    </div>
  );
}
