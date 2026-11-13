import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Inbox, Lock } from "lucide-react";

import { hrApi } from "../../api/hrOversight";
import type { HRApplicationList } from "../../api/hrOversight";
import { useToast } from "../../contexts/ToastContext";
import {
  applicationStatusBadgeClass,
  applicationStatusLabel,
  formatDateTime,
} from "./hrOversightFormat";

/**
 * Revised Phase 14 -- applications for one job (step 3 of 3).
 *
 * The backend authorizes the job in the path before listing anything, so a
 * cross-tenant HR user is refused rather than shown an empty list. Each row is
 * the same `JobApplication` the recruiter and the candidate see, carrying the
 * current status; opening one gives the read-only HR drill-down.
 *
 * `?status=` is a server-side filter, not a client-side one. Clicking a stage on
 * the jobs screen or the organization funnel lands here with the stage in the
 * URL, so the result stays a link someone can share and reload, and the count
 * shown still comes from the same authorized query the plain list uses.
 */
export function HRJobApplicationsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [searchParams] = useSearchParams();
  const { addToast } = useToast();
  const [data, setData] = useState<HRApplicationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [denied, setDenied] = useState(false);

  const status = searchParams.get("status");

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    setLoading(true);
    hrApi
      .getJobApplications(jobId, status ?? undefined)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((error: unknown) => {
        if (!active) return;
        const code = (error as { response?: { status?: number } }).response?.status;
        if (code === 403 || code === 404) {
          setDenied(true);
        } else {
          setLoadFailed(true);
          addToast("Failed to load applications", "error");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [jobId, status, addToast]);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-9 w-48" />
          <div className="skeleton h-4 w-72 max-w-full" />
        </div>
        <div className="skeleton h-8 w-full" />
        <div className="skeleton h-72 w-full" />
      </div>
    );
  }

  if (denied) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="page-header">
          <div>
            <h1 className="page-title">Applications</h1>
            <p className="page-subtitle">Access denied</p>
          </div>
        </div>
        <div className="empty-state">
          <Lock className="mb-3 h-10 w-10 text-gray-300" />
          <h3 className="text-base font-semibold text-gray-900">Not available</h3>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            You do not have access to this job, or it no longer exists.
          </p>
        </div>
        <Link to="/hr/jobs" className="btn-secondary btn-md">
          Back to jobs
        </Link>
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load applications</span>
        </div>
      </div>
    );
  }

  const filtered = data.status_filter !== null;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Applications</h1>
          <p className="page-subtitle">
            {data.total} application{data.total === 1 ? "" : "s"} for this job
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/hr/jobs" className="btn-secondary btn-md">
            Back to Jobs
          </Link>
        </div>
      </div>

      {filtered && (
        <div className="info-banner">
          <span className="font-semibold">
            Filtered to {applicationStatusLabel(data.status_filter!)}
          </span>
          {/* Clearing the filter is a link, not a hidden button, so the unfiltered
              list stays reachable even with JavaScript state in play. */}
          <Link
            to={`/hr/jobs/${jobId}/applications`}
            className="font-medium text-primary-700 underline underline-offset-2 transition-colors hover:text-primary-800"
          >
            Show all statuses
          </Link>
        </div>
      )}

      {data.applications.length === 0 ? (
        <div className="empty-state">
          <Inbox className="mb-3 h-10 w-10 text-gray-300" />
          <h3 className="text-base font-semibold text-gray-900">No applications</h3>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            {filtered
              ? `This job has no applications in ${applicationStatusLabel(
                  data.status_filter!,
                )} right now.`
              : "This job has no applications yet."}
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Status</th>
                <th>Applied</th>
                <th>Recruiter</th>
                <th>Evidence</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {data.applications.map((application) => (
                <tr key={application.id}>
                  <td>
                    <p className="font-medium text-gray-900">{application.candidate_name}</p>
                    {application.job_title && (
                      <p className="text-xs text-gray-500">{application.job_title}</p>
                    )}
                  </td>
                  <td>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${applicationStatusBadgeClass(
                        application.status,
                      )}`}
                    >
                      {applicationStatusLabel(application.status)}
                    </span>
                  </td>
                  <td className="text-gray-600">{formatDateTime(application.applied_at)}</td>
                  <td className="text-gray-600">
                    {application.recruiter_name ?? "Unassigned"}
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {application.has_interview && (
                        <span className="badge-info">Interview</span>
                      )}
                      {application.has_assessment && (
                        <span className="badge-primary">Assessment</span>
                      )}
                      {!application.has_interview && !application.has_assessment && (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </div>
                  </td>
                  <td className="text-right">
                    <Link
                      to={`/hr/applications/${application.id}`}
                      className="btn-secondary btn-sm"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-gray-500">
        Status shown is the live application status. HR oversight is read-only; the recruiter
        records decisions.
      </p>
    </div>
  );
}
