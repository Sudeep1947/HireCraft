import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { Button } from "../../components/ui/Button";
import { ScenarioStatusBadge } from "../../components/simulations/ScenarioStatusBadge";
import { useToast } from "../../contexts/ToastContext";
import { simulationApi } from "../../api/simulations";
import {
  QUALIFICATION_CHANGE_LABELS,
  SHORTLIST_CHANGE_LABELS,
  formatImpactDelta,
  type CombinedThresholdShortlistResponse,
} from "../../types/thresholdShortlist";
import type {
  SimulationScenario,
} from "../../types/simulations";

// ─── Helper Components ─────────────────────────────────────────────

function StatCard({
  label,
  value,
  delta,
  deltaLabel,
  positive,
}: {
  label: string;
  value: string | number;
  delta?: number;
  deltaLabel?: string;
  positive?: boolean;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
      {delta !== undefined && (
        <p
          className={`mt-0.5 text-xs font-medium ${
            positive === true
              ? "text-green-600"
              : positive === false
                ? "text-red-600"
                : "text-gray-500"
          }`}
        >
          {deltaLabel ?? formatImpactDelta(delta)}
        </p>
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
    <div className={`rounded-xl border border-gray-200 bg-white p-5 ${className}`}>
      <h2 className="mb-3 text-lg font-semibold text-gray-900">{title}</h2>
      {children}
    </div>
  );
}

function InsightItem({ message, type }: { message: string; type: string }) {
  const icons: Record<string, string> = {
    threshold_change: "\u2696",
    qualification_impact: "\u2705",
    boundary: "\u2728",
    sensitivity: "\u{1F4CA}",
    shortlist_change: "\u{1F4CB}",
    composition: "\u{1F504}",
  };
  return (
    <div className="flex items-start gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      <span className="mt-0.5 text-base leading-none">{icons[type] ?? "\u{1F4CB}"}</span>
      <p className="text-sm text-gray-700">{message}</p>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────

export function SimulationThresholdShortlist() {
  const { simulationId } = useParams<{ simulationId: string }>();
  const { addToast } = useToast();

  const [scenario, setScenario] = useState<SimulationScenario | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [data, setData] = useState<CombinedThresholdShortlistResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "threshold" | "shortlist" | "candidates">("overview");

  const fetchData = useCallback(async () => {
    if (!simulationId) return;
    setLoadingData(true);
    try {
      const result = await simulationApi.getCombinedThresholdShortlistImpact(simulationId);
      setData(result);
    } catch {
      addToast("Failed to load threshold & shortlist impact analysis", "error");
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
    return () => { cancelled = true; };
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

  const threshold = data?.threshold_impact;
  const shortlist = data?.shortlist_impact;
  const matrix = data?.combined_matrix;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">Threshold & Shortlist Impact</h1>
            <ScenarioStatusBadge status={scenario.status} />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            {scenario.name} &middot; {scenario.job_title} &middot; {scenario.company}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.history.back()}
          >
            Back to simulation
          </Button>
        </div>
      </div>

      {/* Sandbox Warning */}
      <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <span className="mt-0.5 text-base leading-none">&#9888;</span>
        <div>
          <p className="font-semibold">Sandbox Analysis</p>
          <p className="mt-0.5 text-xs text-amber-700">
            This analysis is read-only. No changes have been made to the live hiring process,
            candidate rankings, or shortlist.
          </p>
        </div>
      </div>

      {/* Loading overlay */}
      {loadingData && (
        <div className="flex items-center justify-center py-8">
          <LoadingSpinner size="md" />
          <span className="ml-3 text-sm text-gray-500">Loading impact analysis...</span>
        </div>
      )}

      {data && (
        <>
          {/* Tab Navigation */}
          <div className="flex gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1">
            {(["overview", "threshold", "shortlist", "candidates"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {tab === "overview" && "Overview"}
                {tab === "threshold" && "Threshold"}
                {tab === "shortlist" && "Shortlist"}
                {tab === "candidates" && `Candidates (${data.total_affected_candidates})`}
              </button>
            ))}
          </div>

          {/* Overview Tab */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard
                  label="Threshold"
                  value={`${threshold?.simulation_threshold ?? 0}%`}
                  delta={threshold?.threshold_change ?? 0}
                  deltaLabel={`from ${threshold?.baseline_threshold ?? 0}%`}
                />
                <StatCard
                  label="Qualified"
                  value={threshold?.simulation_qualified_count ?? 0}
                  delta={threshold?.qualified_change ?? 0}
                  positive={(threshold?.qualified_change ?? 0) > 0}
                />
                <StatCard
                  label="Shortlist Size"
                  value={shortlist?.simulation_shortlist_size ?? 0}
                  delta={shortlist?.shortlist_change ?? 0}
                  deltaLabel={`from ${shortlist?.baseline_shortlist_size ?? 0}`}
                />
                <StatCard
                  label="Shortlisted"
                  value={shortlist?.actual_simulation_shortlisted ?? 0}
                  delta={(shortlist?.actual_simulation_shortlisted ?? 0) - (shortlist?.actual_baseline_shortlisted ?? 0)}
                  positive={(shortlist?.actual_simulation_shortlisted ?? 0) > (shortlist?.actual_baseline_shortlisted ?? 0)}
                />
              </div>

              {/* Combined Matrix */}
              <SectionCard title="Shortlist Composition">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-center">
                    <p className="text-2xl font-bold text-green-700">{matrix?.retained ?? 0}</p>
                    <p className="text-xs font-medium text-green-600">Retained</p>
                  </div>
                  <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700">{matrix?.entered ?? 0}</p>
                    <p className="text-xs font-medium text-blue-600">Entered</p>
                  </div>
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-center">
                    <p className="text-2xl font-bold text-red-700">{matrix?.exited ?? 0}</p>
                    <p className="text-xs font-medium text-red-600">Exited</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-center">
                    <p className="text-2xl font-bold text-gray-700">{matrix?.remained_outside ?? 0}</p>
                    <p className="text-xs font-medium text-gray-600">Remained Outside</p>
                  </div>
                </div>
              </SectionCard>

              {/* Insights */}
              {data.insights.length > 0 && (
                <SectionCard title="Key Insights">
                  <div className="flex flex-col gap-2">
                    {data.insights.map((insight, i) => (
                      <InsightItem key={i} message={insight.message} type={insight.type} />
                    ))}
                  </div>
                </SectionCard>
              )}
            </div>
          )}

          {/* Threshold Tab */}
          {activeTab === "threshold" && threshold && (
            <div className="space-y-6">
              <SectionCard title="Threshold Impact">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatCard
                    label="Baseline"
                    value={`${threshold.baseline_threshold}%`}
                  />
                  <StatCard
                    label="Simulated"
                    value={`${threshold.simulation_threshold}%`}
                    delta={threshold.threshold_change}
                  />
                  <StatCard
                    label="Newly Qualified"
                    value={threshold.newly_qualified_count}
                    positive={threshold.newly_qualified_count > 0}
                  />
                  <StatCard
                    label="Newly Disqualified"
                    value={threshold.newly_disqualified_count}
                    positive={false}
                  />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <StatCard
                    label="Retention Rate"
                    value={threshold.qualification_retention_rate !== null ? `${(threshold.qualification_retention_rate * 100).toFixed(1)}%` : "N/A"}
                  />
                  <StatCard
                    label="Percentage Qualified"
                    value={`${threshold.percentage_qualified_after}%`}
                    delta={threshold.percentage_qualified_after - threshold.percentage_qualified_before}
                    deltaLabel="change"
                    positive={threshold.percentage_qualified_after > threshold.percentage_qualified_before}
                  />
                  <StatCard
                    label="Total Candidates"
                    value={threshold.total_candidates}
                  />
                </div>
              </SectionCard>

              {/* Sensitivity Chart */}
              {threshold.sensitivity_data.length > 0 && (
                <SectionCard title="Threshold Sensitivity">
                  <p className="mb-3 text-sm text-gray-500">
                    How the number of qualified candidates changes across different thresholds.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Threshold</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Qualified</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {threshold.sensitivity_data.map((point) => (
                          <tr
                            key={point.threshold}
                            className={`border-b border-gray-100 ${
                              point.threshold === threshold.simulation_threshold
                                ? "bg-primary-50 font-semibold"
                                : ""
                            }`}
                          >
                            <td className="px-3 py-2 text-gray-900">{point.threshold}%</td>
                            <td className="px-3 py-2 text-right text-gray-900">{point.qualified_count}</td>
                            <td className="px-3 py-2 text-right text-gray-500">{point.percentage_qualified}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}

              {/* Score Distribution */}
              {threshold.score_distribution.length > 0 && (
                <SectionCard title="Score Distribution">
                  <p className="mb-3 text-sm text-gray-500">
                    Candidate scores around the threshold boundary.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Score Band</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Candidates</th>
                        </tr>
                      </thead>
                      <tbody>
                        {threshold.score_distribution.map((band) => (
                          <tr
                            key={band.label}
                            className={`border-b border-gray-100 ${
                              band.is_threshold_band ? "bg-amber-50 font-semibold" : ""
                            }`}
                          >
                            <td className="px-3 py-2 text-gray-900">
                              {band.label}
                              {band.is_threshold_band && (
                                <span className="ml-2 text-xs text-amber-600">(threshold)</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right text-gray-900">{band.candidate_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}

              {/* Boundary Candidates */}
              {threshold.boundary_candidates.length > 0 && (
                <SectionCard title="Threshold Boundary Candidates">
                  <p className="mb-3 text-sm text-gray-500">
                    Candidates within {threshold.boundary_range} points of the threshold.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Candidate</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Score</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Distance</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Qualified</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Change</th>
                        </tr>
                      </thead>
                      <tbody>
                        {threshold.boundary_candidates.map((c) => (
                          <tr key={c.candidate_id} className="border-b border-gray-100">
                            <td className="px-3 py-2 text-gray-900">{c.candidate_name}</td>
                            <td className="px-3 py-2 text-right text-gray-900">{c.score}</td>
                            <td className="px-3 py-2 text-right text-gray-500">{c.distance_from_threshold}</td>
                            <td className="px-3 py-2 text-center">
                              <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                                c.qualified ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                              }`}>
                                {c.qualified ? "Yes" : "No"}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-center text-sm text-gray-600">
                              {QUALIFICATION_CHANGE_LABELS[c.qualification_change] ?? c.qualification_change}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}
            </div>
          )}

          {/* Shortlist Tab */}
          {activeTab === "shortlist" && shortlist && (
            <div className="space-y-6">
              <SectionCard title="Shortlist Impact">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatCard
                    label="Baseline Size"
                    value={shortlist.baseline_shortlist_size}
                  />
                  <StatCard
                    label="Simulated Size"
                    value={shortlist.simulation_shortlist_size}
                    delta={shortlist.shortlist_change}
                  />
                  <StatCard
                    label="Retained"
                    value={shortlist.retained_count}
                    positive
                  />
                  <StatCard
                    label="Entered"
                    value={shortlist.entered_count}
                    positive={shortlist.entered_count > 0}
                  />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatCard
                    label="Exited"
                    value={shortlist.exited_count}
                    positive={false}
                  />
                  <StatCard
                    label="Overlap (Jaccard)"
                    value={`${(shortlist.jaccard_similarity * 100).toFixed(1)}%`}
                  />
                  <StatCard
                    label="Retention Rate"
                    value={`${(shortlist.retention_rate * 100).toFixed(1)}%`}
                  />
                  <StatCard
                    label="Turnover Rate"
                    value={`${(shortlist.turnover_rate * 100).toFixed(1)}%`}
                  />
                </div>
              </SectionCard>

              {/* Sensitivity */}
              {shortlist.sensitivity_data.length > 0 && (
                <SectionCard title="Shortlist Sensitivity">
                  <p className="mb-3 text-sm text-gray-500">
                    How shortlist composition changes across different sizes.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Size</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Overlap</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Newly Included</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Overlap %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shortlist.sensitivity_data.map((point) => (
                          <tr
                            key={point.shortlist_size}
                            className={`border-b border-gray-100 ${
                              point.shortlist_size === shortlist.simulation_shortlist_size
                                ? "bg-primary-50 font-semibold"
                                : ""
                            }`}
                          >
                            <td className="px-3 py-2 text-gray-900">{point.shortlist_size}</td>
                            <td className="px-3 py-2 text-right text-gray-900">{point.overlap_with_baseline}</td>
                            <td className="px-3 py-2 text-right text-gray-900">{point.newly_included}</td>
                            <td className="px-3 py-2 text-right text-gray-500">{point.overlap_percentage}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}

              {/* Boundary Candidates */}
              {shortlist.boundary_candidates.length > 0 && (
                <SectionCard title="Shortlist Boundary Candidates">
                  <p className="mb-3 text-sm text-gray-500">
                    Candidates near the shortlist boundary.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Candidate</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Rank</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Score</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Baseline</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Simulated</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Change</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shortlist.boundary_candidates.map((c) => (
                          <tr key={c.candidate_id} className="border-b border-gray-100">
                            <td className="px-3 py-2 text-gray-900">{c.candidate_name}</td>
                            <td className="px-3 py-2 text-right text-gray-900">#{c.rank}</td>
                            <td className="px-3 py-2 text-right text-gray-900">{c.score}</td>
                            <td className="px-3 py-2 text-center">
                              <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                                c.baseline_shortlisted ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                              }`}>
                                {c.baseline_shortlisted ? "Yes" : "No"}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                                c.simulation_shortlisted ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                              }`}>
                                {c.simulation_shortlisted ? "Yes" : "No"}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-center text-sm text-gray-600">
                              {SHORTLIST_CHANGE_LABELS[c.shortlist_change] ?? c.shortlist_change}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}
            </div>
          )}

          {/* Candidates Tab */}
          {activeTab === "candidates" && (
            <div className="space-y-6">
              {data.candidate_impacts.length === 0 ? (
                <SectionCard title="Affected Candidates">
                  <p className="py-6 text-center text-sm text-gray-500">
                    No candidates were affected by the threshold or shortlist changes.
                  </p>
                </SectionCard>
              ) : (
                <SectionCard title="Affected Candidates">
                  <p className="mb-3 text-sm text-gray-500">
                    Candidates whose qualification or shortlist status changed.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Candidate</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Score</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-500">Rank</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Qualification</th>
                          <th className="px-3 py-2 text-center font-medium text-gray-500">Shortlist</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-500">Explanation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.candidate_impacts.map((c) => (
                          <tr key={c.candidate_id} className="border-b border-gray-100">
                            <td className="px-3 py-2 text-gray-900">{c.candidate_name}</td>
                            <td className="px-3 py-2 text-right text-gray-900">
                              {c.simulation_score}
                              {c.score_change !== 0 && (
                                <span className={`ml-1 text-xs ${c.score_change > 0 ? "text-green-600" : "text-red-600"}`}>
                                  ({c.score_change > 0 ? "+" : ""}{c.score_change})
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right text-gray-900">
                              #{c.simulation_rank}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                                c.qualification_change === "newly_qualified"
                                  ? "bg-green-100 text-green-700"
                                  : c.qualification_change === "newly_disqualified"
                                    ? "bg-red-100 text-red-700"
                                    : "bg-gray-100 text-gray-600"
                              }`}>
                                {QUALIFICATION_CHANGE_LABELS[c.qualification_change] ?? c.qualification_change}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                                c.shortlist_change === "entered"
                                  ? "bg-blue-100 text-blue-700"
                                  : c.shortlist_change === "exited"
                                    ? "bg-red-100 text-red-700"
                                    : c.shortlist_change === "retained"
                                      ? "bg-green-100 text-green-700"
                                      : "bg-gray-100 text-gray-600"
                              }`}>
                                {SHORTLIST_CHANGE_LABELS[c.shortlist_change] ?? c.shortlist_change}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-600 max-w-xs truncate">
                              {c.explanation}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}