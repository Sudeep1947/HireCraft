import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { hrApi } from "../../api/hrOversight";
import type { HRAttention, HRAttentionItem } from "../../api/hrOversight";
import { DashboardCard } from "../../components/dashboard";
import { useToast } from "../../contexts/ToastContext";
import {
  applicationStatusLabel,
  attentionRuleLabel,
  attentionSeverityBadgeClass,
  attentionThresholdLabel,
} from "./hrOversightFormat";

/**
 * Revised Phase 14 -- the HR attention center.
 *
 * Reads `/hr/attention` in one request. Every row is produced by a named,
 * deterministic rule measured against a threshold the backend echoes back, so
 * this screen can explain *why* an item is here instead of asking the reader to
 * trust an unexplained alert.
 *
 * What this is not: nothing on this screen decides anything. A listed item means
 * "a person should look at this", and the recruiter-owned write surface is the
 * only thing that can change an application. The rule text is deliberately
 * factual about the measured condition and never speculates about a candidate.
 */
export function HRAttentionPage() {
  const { addToast } = useToast();
  const [data, setData] = useState<HRAttention | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    hrApi
      .getAttention()
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load attention items", "error");
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
          <div className="skeleton h-9 w-56" />
          <div className="skeleton h-4 w-96 max-w-full" />
        </div>
        <div className="skeleton h-32 w-full" />
        <div className="skeleton h-28 w-full" />
        <div className="skeleton h-28 w-full" />
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load attention items</span>
        </div>
      </div>
    );
  }

  const thresholds = Object.entries(data.thresholds);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Needs Attention</h1>
          <p className="page-subtitle">
            Deterministic signals about stalled, failing or under-moving hiring activity.
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
        {data.total_flagged} item{data.total_flagged === 1 ? "" : "s"} flagged
      </div>

      <DashboardCard title="Thresholds in force" className="rounded-xl">
        {thresholds.length === 0 ? (
          <p className="text-sm text-gray-500">No thresholds were reported.</p>
        ) : (
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {thresholds.map(([key, value]) => (
              <div
                key={key}
                className="rounded-xl border border-gray-100 bg-gray-50/70 p-3"
              >
                <dt className="text-xs font-medium text-gray-500">
                  {attentionThresholdLabel(key)}
                </dt>
                <dd className="mt-0.5 font-display text-lg font-bold text-gray-900">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        )}
        <p className="mt-3 text-xs text-gray-500">
          These are the exact thresholds the backend applied. They are configured centrally, so a
          rule never fires against a number that is hidden in the UI.
        </p>
      </DashboardCard>

      {data.items.length === 0 ? (
        <div className="empty-state">
          <CheckCircle2 className="mb-3 h-10 w-10 text-emerald-300" />
          <h3 className="text-base font-semibold text-gray-900">Nothing flagged</h3>
          <p className="mt-1 max-w-md text-sm text-gray-500">
            No application, recruiter or organization crossed a threshold in your scope. This is
            the result of the rules above, not an absence of checks.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.items.map((item, index) => (
            <AttentionRow
              key={`${item.rule}-${item.subject_id ?? "org"}-${index}`}
              item={item}
            />
          ))}
        </div>
      )}

      {data.truncated && (
        <div className="flex items-start gap-2.5 rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-700 shadow-xs">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {data.total_flagged} items qualified but only {data.items.length} are shown. Narrow
            your scope to review the rest.
          </span>
        </div>
      )}

      <p className="text-xs text-gray-500">
        A flagged item is a prompt for a person to look, never a decision. HR cannot change
        application status, record a decision, schedule an interview or assign an assessment from
        this surface.
      </p>
    </div>
  );
}

function AttentionRow({ item }: { item: HRAttentionItem }) {
  return (
    <div className="card rounded-xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${attentionSeverityBadgeClass(
                item.severity,
              )}`}
            >
              {item.severity}
            </span>
            <span className="text-sm font-semibold text-gray-900">
              {attentionRuleLabel(item.rule)}
            </span>
            {item.status && (
              <span className="badge-neutral">
                {applicationStatusLabel(item.status)}
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-gray-700">{item.reason}</p>
          <p className="mt-1 text-xs text-gray-500">
            {item.job_title ? `Job: ${item.job_title}` : "Organization-wide"}
            {item.recruiter_name ? ` · Recruiter: ${item.recruiter_name}` : ""}
          </p>
          {item.measured_value !== null && item.threshold_value !== null && (
            <p className="mt-1 text-xs text-gray-500">
              Measured {item.measured_value} against a threshold of {item.threshold_value}.
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col gap-1.5">
          {item.application_id && (
            <Link
              to={`/hr/applications/${item.application_id}`}
              className="btn-secondary btn-sm"
            >
              View application
            </Link>
          )}
          {item.job_id && !item.application_id && (
            <Link to={`/hr/jobs/${item.job_id}/applications`} className="btn-secondary btn-sm">
              View job
            </Link>
          )}
          {item.recruiter_id && item.subject_type === "recruiter" && (
            <Link
              to={`/hr/recruiters/${item.recruiter_id}`}
              className="btn-secondary btn-sm"
            >
              View recruiter
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
