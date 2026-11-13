import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Users } from "lucide-react";

import { hrApi } from "../../api/hrOversight";
import type { HRRecruiterList } from "../../api/hrOversight";
import { DashboardCard } from "../../components/dashboard";
import { useToast } from "../../contexts/ToastContext";
import { applicationStatusLabel, formatRate } from "./hrOversightFormat";

/**
 * Revised Phase 14 -- HR employer (recruiter) monitoring.
 *
 * Reads `/hr/recruiters` in one request. Every row is the same authorized job
 * set the jobs screen shows, rolled up by who owns each job, so a recruiter's
 * numbers are always the sum of the jobs on their row rather than a separately
 * maintained tally that could drift.
 *
 * This screen is read-only and advisory. A low advancement rate is a prompt
 * for a human conversation, not a performance verdict: the rate only counts
 * applications at all once a recruiter has enough volume for it to mean
 * anything, and the backend reports `null` rather than 0% when there is no data.
 */
export function HRRecruitersPage() {
  const { addToast } = useToast();
  const [data, setData] = useState<HRRecruiterList | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    hrApi
      .getRecruiters()
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load recruiters", "error");
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
        <div className="skeleton h-44 w-full" />
        <div className="skeleton h-44 w-full" />
        <div className="skeleton h-44 w-full" />
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load recruiters</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Recruiters</h1>
          <p className="page-subtitle">
            Every employer in your scope, with their live hiring funnel.
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
        {data.total} recruiter{data.total === 1 ? "" : "s"}
      </div>

      {data.recruiters.length === 0 ? (
        <div className="empty-state">
          <Users className="mb-3 h-10 w-10 text-gray-300" />
          <h3 className="text-base font-semibold text-gray-900">No recruiters</h3>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            There are no recruiters with jobs in your scope yet.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.recruiters.map((recruiter) => (
            <div key={recruiter.id} className="card rounded-xl bg-white p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="section-title">{recruiter.full_name}</h2>
                  {recruiter.email && (
                    <p className="text-sm text-gray-500">{recruiter.email}</p>
                  )}
                  {!recruiter.is_active && (
                    <p className="mt-1 text-xs font-medium text-amber-700">
                      This account is inactive.
                    </p>
                  )}
                </div>
                <Link
                  to={`/hr/recruiters/${recruiter.id}`}
                  className="btn-primary btn-sm"
                >
                  View {recruiter.total_job_count} job
                  {recruiter.total_job_count === 1 ? "" : "s"}
                </Link>
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">Applications</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {recruiter.application_count}
                  </dd>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">In pipeline</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {recruiter.open_application_count}
                  </dd>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">Hired</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {recruiter.hired_count}
                  </dd>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                  <dt className="text-xs font-medium text-gray-500">Advancement rate</dt>
                  <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                    {formatRate(recruiter.advancement_rate)}
                  </dd>
                </div>
              </dl>

              {Object.keys(recruiter.applications_by_status).length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-gray-500">Pipeline:</span>
                  {Object.entries(recruiter.applications_by_status).map(
                    ([status, count]) => (
                      <span key={status} className="badge-neutral">
                        {applicationStatusLabel(status)}: {count}
                      </span>
                    ),
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <DashboardCard title="About the advancement rate" className="rounded-xl">
        <p className="text-sm text-gray-500">
          The advancement rate is the share of a recruiter&rsquo;s applications that moved past
          Applied and Under Review, or reached a decision. It is only meaningful once a recruiter
          has a meaningful number of applications, and it is shown as an em dash rather than 0%
          when they have none. A low rate is a prompt for a conversation, not a judgement: the rate
          says nothing about why an application stalled.
        </p>
      </DashboardCard>
    </div>
  );
}
