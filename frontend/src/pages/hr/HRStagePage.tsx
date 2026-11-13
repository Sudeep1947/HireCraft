import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Inbox } from "lucide-react";

import { hrApi } from "../../api/hrOversight";
import type { HRStageDrilldown } from "../../api/hrOversight";
import { useToast } from "../../contexts/ToastContext";
import { applicationStatusLabel } from "./hrOversightFormat";

/**
 * Revised Phase 14 -- funnel-stage drill-down.
 *
 * Reached by clicking any bar on the organization-wide application funnel. That
 * funnel spans every job in scope, so one stage can stand for thousands of
 * applications; the backend therefore groups the stage by job rather than
 * flattening it, and each row here links to that job's stage-filtered
 * applications.
 *
 * An unrecognised stage in the URL returns zero rows rather than the whole
 * pipeline, so a stale link shows an empty stage instead of quietly presenting an
 * unfiltered list as though it were one stage.
 */
export function HRStagePage() {
  const { status } = useParams<{ status: string }>();
  const { addToast } = useToast();
  const [data, setData] = useState<HRStageDrilldown | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (!status) return;
    let active = true;
    setLoading(true);
    hrApi
      .getStageDrilldown(status)
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load this funnel stage", "error");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [status, addToast]);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-9 w-64" />
          <div className="skeleton h-4 w-80 max-w-full" />
        </div>
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-24 w-full" />
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load this funnel stage</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">{`${applicationStatusLabel(data.status)} applications`}</h1>
          <p className="page-subtitle">
            Every job in your scope holding applications in this stage.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/hr/oversight" className="btn-secondary btn-md">
            Back to Overview
          </Link>
        </div>
      </div>

      <p className="text-sm text-gray-500">
        {data.total} application{data.total === 1 ? "" : "s"} across {data.jobs.length} job
        {data.jobs.length === 1 ? "" : "s"}
      </p>

      {data.jobs.length === 0 ? (
        <div className="empty-state">
          <Inbox className="mb-3 h-10 w-10 text-gray-300" />
          <h3 className="text-base font-semibold text-gray-900">No applications</h3>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            No application in your scope is in {applicationStatusLabel(data.status)} right now.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.jobs.map((row) => (
            <div
              key={row.job_id}
              className="card rounded-xl p-5 transition-all duration-200 hover:shadow-md"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">{row.job_title}</h2>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {row.recruiter_name ?? "Unassigned"}
                  </p>
                </div>
                <Link
                  to={`/hr/jobs/${row.job_id}/applications?status=${data.status}`}
                  className="btn-primary btn-sm"
                >
                  View {row.count} application{row.count === 1 ? "" : "s"}
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
