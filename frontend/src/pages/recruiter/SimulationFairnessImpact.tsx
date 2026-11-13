import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { Button } from "../../components/ui/Button";
import { ScenarioStatusBadge } from "../../components/simulations/ScenarioStatusBadge";
import { useToast } from "../../contexts/ToastContext";
import { simulationApi } from "../../api/simulations";
import {
  METRIC_STATUS_LABELS,
  INSIGHT_TYPE_ICONS,
  formatSelectionRate,
  formatRateChange,
  formatDelta,
  type FairnessImpactResponse,
} from "../../types/fairnessImpact";
import type { SimulationScenario } from "../../types/simulations";

// ─── Helper Components ──────────────────────────────────────────

function StatCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-bold ${color ?? "text-gray-900"}`}
      >
        {value}
      </p>
      {subtitle && (
        <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>
      )}
    </div>
  );
}

function SectionCard({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-gray-200 bg-white p-5 ${className}`}
    >
      <h2 className="mb-3 text-lg font-semibold text-gray-900">{title}</h2>
      {children}
    </div>
  );
}

function InsightItem({
  message,
  type,
}: {
  message: string;
  type: string;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      <span className="mt-0.5 text-base leading-none">
        {INSIGHT_TYPE_ICONS[type] ?? "\u{1F4CB}"}
      </span>
      <p className="text-sm text-gray-700">{message}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    available: "bg-green-100 text-green-800",
    insufficient_sample: "bg-yellow-100 text-yellow-800",
    insufficient_data: "bg-orange-100 text-orange-800",
    no_demographic_data: "bg-gray-100 text-gray-600",
    no_reference_group: "bg-gray-100 text-gray-600",
    identical_rates: "bg-blue-100 text-blue-800",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-600"}`}
    >
      {METRIC_STATUS_LABELS[status] ?? status}
    </span>
  );
}

// ─── Main Component ─────────────────────────────────────────────

export function SimulationFairnessImpact() {
  const { simulationId } = useParams<{ simulationId: string }>();
  const { addToast } = useToast();

  const [scenario, setScenario] = useState<SimulationScenario | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [data, setData] = useState<FairnessImpactResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "overview" | "groups" | "cross-group" | "insights"
  >("overview");

  const fetchData = useCallback(async () => {
    if (!simulationId) return;
    setLoadingData(true);
    try {
      const result = await simulationApi.getFairnessImpact(simulationId);
      setData(result);
    } catch {
      addToast("Failed to load fairness impact analysis", "error");
    } finally {
      setLoadingData(false);
    }
  }, [simulationId, addToast]);

  useEffect(() => {
    const id = simulationId;
    if (!id) return;
    let cancelled = false;
    async function load() {
      try {
        const data = await simulationApi.get(id!);
        if (cancelled) return;
        setScenario(data);
        await fetchData();
      } catch {
        if (!cancelled) setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [simulationId, fetchData]);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  if (notFound || !scenario) {
    return (
      <div className="py-20 text-center">
        <p className="text-gray-500">Simulation not found.</p>
        <button
          onClick={() => window.history.back()}
          className="mt-4 text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          Go back
        </button>
      </div>
    );
  }

  const availableGroups =
    data?.group_metrics.filter((m) => m.metric_status === "available") ?? [];
  const crossGroupAvailable =
    data?.cross_group_metrics.filter((m) => m.metric_status === "available") ??
    [];
  const insufficientGroups =
    data?.group_metrics.filter((m) => m.metric_status === "insufficient_sample") ??
    [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              Fairness Impact
            </h1>
            <ScenarioStatusBadge status={scenario.status} />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            {scenario.name} &mdash; {scenario.job_title} @{" "}
            {scenario.company}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => window.history.back()}
        >
          Back
        </Button>
      </div>

      {/* What-if Banner */}
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
        <p className="text-sm text-amber-800">
          <span className="font-semibold">What-if analysis</span> &mdash;
          These results represent a hypothetical hiring configuration. No live
          hiring data was modified by this simulation.
        </p>
      </div>

      {/* Loading overlay */}
      {loadingData && (
        <div className="flex items-center justify-center py-8">
          <LoadingSpinner size="md" />
          <span className="ml-3 text-sm text-gray-500">
            Loading fairness analysis...
          </span>
        </div>
      )}

      {/* Content */}
      {data && !loadingData && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              label="Total Candidates"
              value={data.total_candidates}
            />
            <StatCard
              label="With Demographic Data"
              value={data.candidates_with_demographic}
              subtitle={`${data.candidates_missing_demographic} missing`}
            />
            <StatCard
              label="Groups Analyzed"
              value={availableGroups.length}
              subtitle={`${insufficientGroups.length} below threshold`}
            />
            <StatCard
              label="Cross-Group Metrics"
              value={crossGroupAvailable.length}
              subtitle={`Ref: ${data.reference_group ?? "N/A"}`}
            />
          </div>

          {/* Tab Navigation */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-1">
            <nav className="flex gap-1">
              {(["overview", "groups", "cross-group", "insights"] as const).map(
                (tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      activeTab === tab
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    {tab === "overview"
                      ? "Overview"
                      : tab === "groups"
                        ? "Group Metrics"
                        : tab === "cross-group"
                          ? "Cross-Group"
                          : "Insights"}
                  </button>
                ),
              )}
            </nav>
          </div>

          {/* Tab Content */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Demographic Coverage */}
              <SectionCard title="Demographic Coverage">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Dimension analyzed
                    </span>
                    <span className="text-sm font-medium text-gray-900 capitalize">
                      {data.group_dimension}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Reference group
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {data.reference_group ?? "None determined"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Minimum group size
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {data.minimum_group_size}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Candidates with demographic data
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {data.candidates_with_demographic} /{" "}
                      {data.total_candidates}
                    </span>
                  </div>
                  {data.candidates_missing_demographic > 0 && (
                    <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2">
                      <p className="text-xs text-yellow-800">
                        {data.candidates_missing_demographic} candidate(s) have
                        no self-reported gender data and are excluded from
                        group-level analysis.
                      </p>
                    </div>
                  )}
                </div>
              </SectionCard>

              {/* Group Selection Rate Comparison */}
              <SectionCard title="Selection Rate by Group">
                {availableGroups.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No groups with sufficient data available.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                          <th className="px-3 py-2">Group</th>
                          <th className="px-3 py-2 text-right">N</th>
                          <th className="px-3 py-2 text-right">Baseline</th>
                          <th className="px-3 py-2 text-right">Simulation</th>
                          <th className="px-3 py-2 text-right">Change</th>
                          <th className="px-3 py-2 text-right">Entered</th>
                          <th className="px-3 py-2 text-right">Exited</th>
                          <th className="px-3 py-2 text-right">Retained</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {availableGroups.map((gm) => (
                          <tr
                            key={gm.group_value}
                            className="hover:bg-gray-50"
                          >
                            <td className="whitespace-nowrap px-3 py-2 font-medium text-gray-900 capitalize">
                              {gm.group_value}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {gm.sample_size}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {formatSelectionRate(gm.baseline_selection_rate)}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {formatSelectionRate(
                                gm.simulation_selection_rate,
                              )}
                            </td>
                            <td
                              className={`whitespace-nowrap px-3 py-2 text-right font-medium ${
                                (gm.selection_rate_change ?? 0) > 0
                                  ? "text-green-600"
                                  : (gm.selection_rate_change ?? 0) < 0
                                    ? "text-red-600"
                                    : "text-gray-600"
                              }`}
                            >
                              {formatRateChange(gm.selection_rate_change)}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-green-600">
                              {gm.entered_selection}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-red-600">
                              {gm.exited_selection}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {gm.retained_selection}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </SectionCard>

              {/* Insufficient Sample Groups */}
              {insufficientGroups.length > 0 && (
                <SectionCard title="Groups Below Minimum Threshold">
                  <div className="space-y-2">
                    {insufficientGroups.map((gm) => (
                      <div
                        key={gm.group_value}
                        className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
                      >
                        <span className="text-sm font-medium text-gray-900 capitalize">
                          {gm.group_value}
                        </span>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-500">
                            N = {gm.sample_size}
                          </span>
                          <StatusBadge status={gm.metric_status} />
                        </div>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              )}
            </div>
          )}

          {activeTab === "groups" && (
            <div className="space-y-6">
              {/* All Groups Detail */}
              <SectionCard title="Group-Level Fairness Metrics">
                {data.group_metrics.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No group metrics available.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {data.group_metrics.map((gm) => (
                      <div
                        key={gm.group_value}
                        className="rounded-lg border border-gray-200 p-4"
                      >
                        <div className="mb-3 flex items-center justify-between">
                          <h3 className="text-base font-semibold text-gray-900 capitalize">
                            {gm.group_value}
                          </h3>
                          <StatusBadge status={gm.metric_status} />
                        </div>
                        {gm.metric_status === "available" ? (
                          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            <div>
                              <p className="text-xs text-gray-500">Eligible</p>
                              <p className="text-sm font-medium text-gray-900">
                                {gm.eligible_count}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">
                                Baseline Selected
                              </p>
                              <p className="text-sm font-medium text-gray-900">
                                {gm.baseline_selected_count} (
                                {formatSelectionRate(
                                  gm.baseline_selection_rate,
                                )}
                                )
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">
                                Simulation Selected
                              </p>
                              <p className="text-sm font-medium text-gray-900">
                                {gm.simulation_selected_count} (
                                {formatSelectionRate(
                                  gm.simulation_selection_rate,
                                )}
                                )
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">
                                Rate Change
                              </p>
                              <p
                                className={`text-sm font-medium ${
                                  (gm.selection_rate_change ?? 0) > 0
                                    ? "text-green-600"
                                    : (gm.selection_rate_change ?? 0) < 0
                                      ? "text-red-600"
                                      : "text-gray-600"
                                }`}
                              >
                                {formatRateChange(gm.selection_rate_change)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Entered</p>
                              <p className="text-sm font-medium text-green-600">
                                {gm.entered_selection}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Exited</p>
                              <p className="text-sm font-medium text-red-600">
                                {gm.exited_selection}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Retained</p>
                              <p className="text-sm font-medium text-gray-900">
                                {gm.retained_selection}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">
                                Sample Size
                              </p>
                              <p className="text-sm font-medium text-gray-900">
                                {gm.sample_size}
                              </p>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">
                            {gm.status_reason}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          )}

          {activeTab === "cross-group" && (
            <div className="space-y-6">
              <SectionCard title="Cross-Group Fairness Metrics">
                {data.cross_group_metrics.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No cross-group metrics available.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {data.cross_group_metrics.map((cm) => (
                      <div
                        key={cm.metric_name}
                        className="rounded-lg border border-gray-200 p-4"
                      >
                        <div className="mb-3 flex items-center justify-between">
                          <h3 className="text-base font-semibold text-gray-900">
                            {cm.metric_label}
                          </h3>
                          <StatusBadge status={cm.metric_status} />
                        </div>
                        {cm.metric_status === "available" ? (
                          <div className="grid grid-cols-3 gap-4">
                            <div>
                              <p className="text-xs text-gray-500">Baseline</p>
                              <p className="text-lg font-bold text-gray-900">
                                {formatDelta(cm.baseline_value)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">
                                Simulation
                              </p>
                              <p className="text-lg font-bold text-gray-900">
                                {formatDelta(cm.simulation_value)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Change</p>
                              <p
                                className={`text-lg font-bold ${
                                  (cm.absolute_change ?? 0) > 0
                                    ? "text-green-600"
                                    : (cm.absolute_change ?? 0) < 0
                                      ? "text-red-600"
                                      : "text-gray-600"
                                }`}
                              >
                                {formatDelta(cm.absolute_change)}
                              </p>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">
                            {cm.status_reason}
                          </p>
                        )}
                        <div className="mt-3 flex gap-4 text-xs text-gray-500">
                          <span>
                            Reference:{" "}
                            <span className="font-medium text-gray-700">
                              {cm.reference_group ?? "N/A"}
                            </span>
                          </span>
                          {cm.groups_compared.length > 0 && (
                            <span>
                              Groups:{" "}
                              <span className="font-medium text-gray-700">
                                {cm.groups_compared.join(", ")}
                              </span>
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>

              {/* Explanation */}
              <SectionCard title="Metric Definitions">
                <div className="space-y-3 text-sm text-gray-600">
                  <div>
                    <span className="font-medium text-gray-900">
                      Statistical Parity Difference:
                    </span>{" "}
                    Maximum absolute difference in selection rates between any
                    group and the reference group. A value of 0 indicates equal
                    selection rates.
                  </div>
                  <div>
                    <span className="font-medium text-gray-900">
                      Disparate Impact Ratio:
                    </span>{" "}
                    Ratio of the lowest group selection rate to the highest group
                    selection rate. Values closer to 1.0 indicate more equal
                    selection rates. Values below 0.8 may indicate potential
                    disparate impact.
                  </div>
                </div>
              </SectionCard>
            </div>
          )}

          {activeTab === "insights" && (
            <div className="space-y-6">
              <SectionCard title="Fairness Impact Insights">
                {data.insights.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No insights generated. This may indicate that demographic
                    data is unavailable or groups are below the minimum size
                    threshold.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {data.insights.map((insight, i) => (
                      <InsightItem
                        key={i}
                        message={insight.message}
                        type={insight.type}
                      />
                    ))}
                  </div>
                )}
              </SectionCard>

              {/* Data Limitations */}
              <SectionCard title="Data Limitations">
                <div className="space-y-2 text-sm text-gray-600">
                  <p>
                    Fairness metrics are calculated using self-reported candidate
                    gender data from candidate profiles. Candidates who have not
                    reported their gender are excluded from group-level analysis.
                  </p>
                  <p>
                    Equal Opportunity Difference is not calculated because
                    ground-truth outcome labels are not available in the
                    simulation dataset.
                  </p>
                  <p>
                    Groups below the configured minimum size (
                    {data.minimum_group_size} candidates) are marked as having
                    insufficient sample size and their metrics are not reported.
                  </p>
                  <p className="font-medium text-gray-800">
                    Simulation fairness results describe the hypothetical
                    configuration represented by the simulation and do not modify
                    or replace live hiring decisions.
                  </p>
                </div>
              </SectionCard>
            </div>
          )}
        </>
      )}
    </div>
  );
}
