import { useCallback, useEffect, useState } from "react";

import { getApplicationFairnessContext } from "../../api/screening";
import { getErrorMessage } from "../../utils/error";
import type {
  ApplicationFairnessContext,
  FairnessCrossGroupMetric,
  FairnessGroupOutcome,
  FairnessSection,
} from "../../types/screening";

/**
 * Fairness & bias context for the screening being viewed (Phase 7).
 *
 * Presentation only. Every number, status and reason is rendered exactly as the
 * backend returned it: this component does not compute SPD, DI, a rate, a
 * severity band or a pass/fail threshold. That is deliberate -- a metric that
 * changes meaning between the API and the screen is a metric nobody can audit.
 *
 * The framing throughout is "this job's screened population", and the
 * application is shown as a member of it. There is intentionally no fairness
 * score for the individual and no combined fairness/match score.
 */

const cardClass = "card p-5";
const sectionTitleClass = "text-sm font-semibold text-ink";
const hintClass = "mt-0.5 text-xs text-ink-muted";

const SEVERITY_STYLES: Record<string, string> = {
  high: "badge-danger",
  medium: "badge-warning",
  low: "badge-info",
  info: "badge-neutral",
};

const STATUS_STYLES: Record<string, string> = {
  available: "badge-success",
  insufficient_data: "badge-warning",
  insufficient_sample: "badge-warning",
  no_demographic_data: "badge-warning",
  no_screening_data: "badge-neutral",
  no_reference_group: "badge-neutral",
  identical_rates: "badge-success",
  unavailable: "badge-neutral",
};

const ASSESSMENT_LABELS: Record<string, string> = {
  low_bias: "Low bias detected",
  moderate_bias: "Moderate bias detected",
  high_bias: "High bias detected",
  unknown: "Not assessed",
};

function SectionCard({
  title,
  hint,
  right,
  children,
}: {
  title: string;
  hint?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className={cardClass}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className={sectionTitleClass}>{title}</h3>
          {hint ? <p className={hintClass}>{hint}</p> : null}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className={STATUS_STYLES[status] ?? "badge-neutral"}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function SectionUnavailable({ section }: { section: FairnessSection | undefined }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300/80 bg-gray-50 p-4">
      <StatusPill status={section?.status ?? "unavailable"} />
      <p className="mt-2 text-sm text-ink-muted">
        {section?.reason ?? "This analysis is unavailable for the current selection."}
      </p>
    </div>
  );
}

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function GroupRow({ group }: { group: FairnessGroupOutcome }) {
  return (
    <tr className="border-t border-gray-100">
      <td className="py-2 pr-3 text-sm font-medium text-ink">
        {group.group_value}
      </td>
      <td className="py-2 pr-3 text-sm text-ink">{group.sample_size}</td>
      <td className="py-2 pr-3 text-sm text-ink">
        {group.positive_outcome_count ?? "—"}
      </td>
      <td className="py-2 pr-3 text-sm text-ink">
        {formatPercent(group.positive_outcome_rate)}
      </td>
      <td className="py-2 text-sm">
        <StatusPill status={group.metric_status} />
        {group.status_reason ? (
          <p className="mt-1 text-xs text-ink-muted">{group.status_reason}</p>
        ) : null}
      </td>
    </tr>
  );
}

function MetricRow({ metric }: { metric: FairnessCrossGroupMetric }) {
  return (
    <div className="rounded-xl border border-gray-200 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink">{metric.metric_label}</p>
          <p className="text-xs text-ink-muted">
            {metric.reference_group
              ? `Compared against "${metric.reference_group}"`
              : "No reference group available"}
            {metric.groups_compared.length > 0
              ? ` · ${metric.groups_compared.join(", ")}`
              : ""}
          </p>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold text-ink">
            {metric.value === null ? "—" : metric.value.toFixed(2)}
          </p>
          <StatusPill status={metric.metric_status} />
        </div>
      </div>
      {metric.status_reason ? (
        <p className="mt-2 text-xs text-ink-muted">{metric.status_reason}</p>
      ) : null}
    </div>
  );
}

function GroupAnalysis({
  context,
}: {
  context: ApplicationFairnessContext;
}) {
  const analysis = context.group_analysis;
  const section = context.sections.group_analysis;

  if (!analysis || section?.status !== "available") {
    if (analysis) {
      return (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <StatusPill status={analysis.metric_status} />
            {section ? <StatusPill status={section.status} /> : null}
          </div>
          {analysis.status_reason ? (
            <p className="text-sm text-ink-muted">{analysis.status_reason}</p>
          ) : null}
          <CoverageSummary coverage={analysis.coverage} />
          <p className="mt-3 text-xs text-ink-muted">{analysis.methodology}</p>
        </div>
      );
    }
    return <SectionUnavailable section={section} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={analysis.metric_status} />
        {analysis.reference_group ? (
          <span className="text-xs text-ink-muted">
            Reference group: {analysis.reference_group}
          </span>
        ) : null}
      </div>
      <CoverageSummary coverage={analysis.coverage} />

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Screened</th>
              <th>
                At or above {analysis.coverage.positive_outcome_threshold}
              </th>
              <th>Rate</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {analysis.group_outcomes.map((group) => (
              <GroupRow key={group.group_value} group={group} />
            ))}
          </tbody>
        </table>
      </div>

      {analysis.cross_group_metrics.length > 0 ? (
        <div className="space-y-2">
          {analysis.cross_group_metrics.map((metric) => (
            <MetricRow key={metric.metric_name} metric={metric} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-ink-muted">
          No cross-group metric is reported for this population.
        </p>
      )}

      <p className="text-xs text-ink-muted">{analysis.methodology}</p>
      <p className="text-xs text-ink-muted">{analysis.grouping_note}</p>
    </div>
  );
}

function CoverageSummary({
  coverage,
}: {
  coverage: ApplicationFairnessContext["group_analysis"] extends null
    ? never
    : NonNullable<ApplicationFairnessContext["group_analysis"]>["coverage"];
}) {
  return (
    <div className="rounded-xl bg-gray-50 p-3 text-xs text-ink-muted">
      <p>
        <span className="font-medium text-ink">Coverage:</span>{" "}
        {coverage.candidates_with_demographic} of {coverage.population} screened
        candidates supplied a {coverage.group_dimension} value (
        {coverage.demographic_coverage_pct}%).{" "}
        {coverage.candidates_missing_demographic} supplied nothing and are excluded
        from group comparison rather than assigned a value.
      </p>
      <p className="mt-1">
        Attribute source: {coverage.attribute_source.replace(/_/g, " ")}.
        Attributes inferred: {coverage.attributes_inferred ? "yes" : "no"}. Minimum
        group size: {coverage.minimum_group_size}.
      </p>
    </div>
  );
}

export function ApplicationFairnessContextCard({
  applicationId,
  jobId,
}: {
  applicationId: string;
  jobId?: string;
}) {
  const [context, setContext] = useState<ApplicationFairnessContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError(null);
    try {
      setContext(await getApplicationFairnessContext(applicationId));
    } catch (err) {
      setError(
        getErrorMessage(err, "Failed to load fairness context for this job."),
      );
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <SectionCard
        title="Fairness & bias context"
        hint="Comparing screening outcomes across the job's screened population."
      >
        <div className="space-y-3">
          <div className="skeleton h-4 w-2/3" />
          <div className="skeleton h-4 w-1/2" />
          <div className="skeleton h-16 w-full" />
        </div>
        <p className="mt-3 text-sm text-ink-muted">Loading fairness context…</p>
      </SectionCard>
    );
  }

  if (error || !context) {
    return (
      <SectionCard
        title="Fairness & bias context"
        hint="Comparing screening outcomes across the job's screened population."
        right={
          <button
            type="button"
            onClick={() => void load()}
            className="btn-secondary btn-sm"
          >
            Retry
          </button>
        }
      >
        <p className="error-banner" role="alert">
          {error ?? "Fairness context is unavailable for this application."}
        </p>
      </SectionCard>
    );
  }

  const { population, screening_state: screeningState, alerts } = context;
  const jd = context.job_description_bias;

  return (
    <div className="space-y-4">
      <SectionCard
        title="Fairness & bias context"
        hint="Decision support for human review. Read-only, and never combined with the match score."
        right={
          <button
            type="button"
            onClick={() => void load()}
            className="btn-secondary btn-sm"
          >
            Refresh
          </button>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-ink">{population.note}</p>
          <div className="grid gap-2 sm:grid-cols-4">
            <Stat label="Applications" value={population.applications} />
            <Stat label="Screened" value={population.screened} />
            <Stat label="Not screened" value={population.unscreened} />
            <Stat
              label="This application"
              value={population.application_screening_included ? "In population" : "Not included"}
            />
          </div>
          <p className="text-xs text-ink-muted">{screeningState.message}</p>
          {context.score_distribution ? (
            <p className="text-xs text-ink-muted">
              Score distribution: mean {context.score_distribution.average.toFixed(1)},
              range {context.score_distribution.minimum}–{context.score_distribution.maximum},
              median {context.score_distribution.median.toFixed(1)}.{" "}
              {context.score_distribution.note}
            </p>
          ) : null}
          <p className="text-xs text-ink-muted">{context.disclaimer}</p>
        </div>
      </SectionCard>

      <SectionCard
        title="Group comparison"
        hint="Screening outcome rates by self-reported group, with coverage and limitations."
      >
        <GroupAnalysis context={context} />
      </SectionCard>

      {alerts.length > 0 ? (
        <SectionCard title="Review alerts" hint="Signals worth a human look. Not decisions.">
          <ul className="space-y-2">
            {alerts.map((alert, index) => (
              <li
                key={`${alert.type}-${index}`}
                className="rounded-xl border border-gray-200 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-ink">
                    {alert.type.replace(/_/g, " ")}
                  </p>
                  <span
                    className={
                      SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.info
                    }
                  >
                    {alert.severity}
                  </span>
                </div>
                <p className="mt-1 text-sm text-ink">{alert.message}</p>
                <p className="mt-1 text-xs text-ink-muted">{alert.recommendation}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Job description bias"
        hint={jd ? jd.note : "Analysis of the job posting itself."}
      >
        {jd ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-semibold text-ink">{jd.bias_score}</span>
              <span className="text-sm text-ink-muted">
                {ASSESSMENT_LABELS[jd.overall_assessment] ?? jd.overall_assessment}
              </span>
              <span className="text-xs text-ink-muted">
                {jd.total_issues} issue(s) found
              </span>
            </div>
            {jd.findings.length > 0 ? (
              <ul className="space-y-1 text-sm text-ink">
                {jd.findings.map((finding, index) => (
                  <li key={`${finding.term}-${index}`}>
                    <span className="font-medium text-ink">{finding.term}</span>{" "}
                    <span className="text-xs text-ink-muted">
                      ({finding.category.replace(/_/g, " ")})
                    </span>
                    {finding.suggestion ? (
                      <p className="text-xs text-ink-muted">{finding.suggestion}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-muted">No issues found in this posting.</p>
            )}
          </div>
        ) : (
          <SectionUnavailable section={context.sections.job_description_bias} />
        )}
      </SectionCard>

      <SectionCard
        title="Adversarial testing"
        hint="Stability checks against perturbed screening inputs."
      >
        <SectionUnavailable section={context.sections.adversarial} />
        {jobId ? (
          <p className="mt-2 text-xs text-ink-muted">
            <a
              href={`/recruiter/fairness?job_id=${jobId}`}
              className="font-medium text-primary-600 hover:underline"
            >
              Open the fairness dashboard
            </a>{" "}
            to run a test explicitly.
          </p>
        ) : null}
      </SectionCard>

      {context.limitations.length > 0 ? (
        <SectionCard title="Limitations" hint="What this analysis cannot tell you.">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-muted">
            {context.limitations.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </SectionCard>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-gray-50 p-3">
      <p className="text-xs uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="kpi-value mt-1 text-lg">{value}</p>
    </div>
  );
}
