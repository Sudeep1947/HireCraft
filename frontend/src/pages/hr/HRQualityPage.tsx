import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Scale } from "lucide-react";

import { hrApi } from "../../api/hrOversight";
import type { HRHiringQuality } from "../../api/hrOversight";
import { DashboardCard } from "../../components/dashboard";
import { useToast } from "../../contexts/ToastContext";
import { formatRate } from "./hrOversightFormat";

/**
 * Revised Phase 14 -- organization hiring quality.
 *
 * Reads `/hr/quality` in one request and reports how much real evidence the
 * organization actually has: how many applications reached screening, interview,
 * decision and hire, plus the fairness alerts produced by the platform's own
 * fairness engine.
 *
 * Two deliberate omissions:
 *
 * 1. There is no composite "hiring quality score". Screening fairness and
 *    explainability own those judgements; a number assembled on an oversight
 *    screen would imply an authority this read surface does not have.
 * 2. A rate with no denominator renders as an em dash, not 0%. An organization
 *    with no applications has not converted 0% of them -- there were none, and
 *    printing 0% would read as total failure.
 */
export function HRQualityPage() {
  const { addToast } = useToast();
  const [data, setData] = useState<HRHiringQuality | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    hrApi
      .getHiringQuality()
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load hiring quality", "error");
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
          <div className="skeleton h-9 w-48" />
          <div className="skeleton h-4 w-96 max-w-full" />
        </div>
        <div className="skeleton h-44 w-full" />
        <div className="skeleton h-28 w-full" />
        <div className="skeleton h-44 w-full" />
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load hiring quality</span>
        </div>
      </div>
    );
  }

  const { coverage } = data;
  const screeningEntries = Object.entries(coverage.screening_by_status);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Hiring Quality</h1>
          <p className="page-subtitle">
            How much screening, interview and decision evidence your organizations actually have.
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
        {coverage.total_applications} application
        {coverage.total_applications === 1 ? "" : "s"} in scope
      </div>

      <DashboardCard title="Pipeline coverage" className="rounded-xl">
        {coverage.total_applications === 0 ? (
          <p className="text-sm text-gray-500">
            There are no applications in your scope, so no rate can be calculated. That is a
            different fact from a 0% rate, and it is shown as such.
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
              <dt className="text-xs font-medium text-gray-500">Screened</dt>
              <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                {formatRate(coverage.screening_rate)}
              </dd>
            </div>
            <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
              <dt className="text-xs font-medium text-gray-500">Reached interview</dt>
              <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                {formatRate(coverage.interview_rate)}
              </dd>
            </div>
            <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
              <dt className="text-xs font-medium text-gray-500">Decided</dt>
              <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                {formatRate(coverage.decision_rate)}
              </dd>
            </div>
            <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
              <dt className="text-xs font-medium text-gray-500">Hired</dt>
              <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                {formatRate(coverage.hire_rate)}
              </dd>
            </div>
          </dl>
        )}
        <p className="mt-3 text-xs text-gray-500">
          Each rate is a share of the applications in your scope that reached that stage. They are
          counted from recorded statuses, not inferred from scores.
        </p>
      </DashboardCard>

      {screeningEntries.length > 0 && (
        <DashboardCard title="Screening coverage by state" className="rounded-xl">
          <div className="flex flex-wrap gap-2">
            {screeningEntries.map(([status, count]) => (
              <span key={status} className="badge-neutral">
                {status.replace(/_/g, " ")}: {count}
              </span>
            ))}
          </div>
        </DashboardCard>
      )}

      <DashboardCard title="Fairness review" className="rounded-xl">
        {data.fairness_alerts.length === 0 ? (
          <div className="flex items-start gap-2.5 text-sm text-gray-500">
            <Scale className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
            <p>
              No selection-parity alert is outstanding. This is not a compliance verdict: the
              platform only reports a ratio once screening results exist, and an organization with
              nothing screened has no ratio to judge.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {data.fairness_alerts.map((alert) => (
              <div
                key={`${alert.metric}-${alert.job_id ?? "org"}`}
                className="rounded-xl border border-red-200/80 bg-red-50/80 p-4 shadow-xs"
              >
                <p className="text-sm font-medium text-red-800">
                  {alert.metric.replace(/_/g, " ")} is {alert.observed_value}, below the{" "}
                  {alert.threshold_value} review threshold
                </p>
                {alert.detail && <p className="mt-1 text-sm text-red-700">{alert.detail}</p>}
                {alert.job_id && (
                  <Link
                    to={`/hr/jobs/${alert.job_id}/applications`}
                    className="btn-secondary btn-sm mt-3"
                  >
                    View this job
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-gray-500">
          The ratio comes from the platform&rsquo;s existing fairness engine, so this screen shows
          the same number the fairness reports do. A reading below the floor is a request for human
          review, not a finding of discrimination.
        </p>
      </DashboardCard>
    </div>
  );
}
