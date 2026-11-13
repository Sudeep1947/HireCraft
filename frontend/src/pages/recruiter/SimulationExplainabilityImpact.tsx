import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { Button } from "../../components/ui/Button";
import { ScenarioStatusBadge } from "../../components/simulations/ScenarioStatusBadge";
import { useToast } from "../../contexts/ToastContext";
import { simulationApi } from "../../api/simulations";
import {
  IMPACT_TYPE_LABELS,
  IMPACT_TYPE_COLORS,
  INSIGHT_TYPE_ICONS,
  formatContribution,
  formatWeight,
  formatScoreChange,
  getScoreColor,
  getContributionColor,
  type ExplainabilityImpactResponse,
  type CandidateExplainabilityImpact,
} from "../../types/explainabilityImpact";
import type { SimulationScenario } from "../../types/simulations";

// ─── Helper Components ──────────────────────────────────────────

function StatCard({
  label,
  value,
  subtitle,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
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

function ImpactBadge({ impactType }: { impactType: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${IMPACT_TYPE_COLORS[impactType] ?? "bg-gray-100 text-gray-600"}`}
    >
      {IMPACT_TYPE_LABELS[impactType] ?? impactType}
    </span>
  );
}

function ContributionBar({
  feature,
  baseline,
  simulation,
}: {
  feature: string;
  baseline: number;
  simulation: number;
}) {
  const maxVal = Math.max(Math.abs(baseline), Math.abs(simulation), 1);
  const bWidth = (Math.abs(baseline) / maxVal) * 100;
  const sWidth = (Math.abs(simulation) / maxVal) * 100;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-gray-700">{feature}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-16 text-right text-xs text-gray-500">Base</span>
        <div className="h-3 flex-1 overflow-hidden rounded bg-gray-100">
          <div
            className={`h-full rounded ${baseline >= 0 ? "bg-blue-400" : "bg-red-300"}`}
            style={{ width: `${bWidth}%` }}
          />
        </div>
        <span className="w-14 text-xs text-gray-600">
          {formatContribution(baseline)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-16 text-right text-xs text-gray-500">Sim</span>
        <div className="h-3 flex-1 overflow-hidden rounded bg-gray-100">
          <div
            className={`h-full rounded ${simulation >= 0 ? "bg-green-400" : "bg-red-400"}`}
            style={{ width: `${sWidth}%` }}
          />
        </div>
        <span className="w-14 text-xs text-gray-600">
          {formatContribution(simulation)}
        </span>
      </div>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────

export function SimulationExplainabilityImpact() {
  const { simulationId } = useParams<{ simulationId: string }>();
  const { addToast } = useToast();

  const [scenario, setScenario] = useState<SimulationScenario | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [data, setData] = useState<ExplainabilityImpactResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "overview" | "weights" | "candidates" | "insights"
  >("overview");
  const [selectedCandidate, setSelectedCandidate] =
    useState<CandidateExplainabilityImpact | null>(null);

  const fetchData = useCallback(async () => {
    if (!simulationId) return;
    setLoadingData(true);
    try {
      const result = await simulationApi.getExplainabilityImpact(simulationId);
      setData(result);
    } catch {
      addToast("Failed to load explainability impact analysis", "error");
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

  const changedCandidates =
    data?.candidates.filter((c) => c.impact_type === "score_changed") ?? [];
  const rankOnlyCandidates =
    data?.candidates.filter((c) => c.impact_type === "rank_only_changed") ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              Explainability Impact
            </h1>
            <ScenarioStatusBadge status={scenario.status} />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            {scenario.name} &mdash; {scenario.job_title} @ {scenario.company}
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
          These explanations compare candidate scoring factors under a
          hypothetical configuration. No live hiring data was modified by this
          simulation.
        </p>
      </div>

      {/* Loading overlay */}
      {loadingData && (
        <div className="flex items-center justify-center py-8">
          <LoadingSpinner size="md" />
          <span className="ml-3 text-sm text-gray-500">
            Loading explainability analysis...
          </span>
        </div>
      )}

      {/* Content */}
      {data && !loadingData && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              label="Candidates Analyzed"
              value={data.summary.total_candidates}
            />
            <StatCard
              label="Score Changes"
              value={data.summary.candidates_with_score_changes}
              subtitle={`Avg: ${data.summary.average_score_change > 0 ? "+" : ""}${data.summary.average_score_change}`}
            />
            <StatCard
              label="Rank Changes"
              value={data.summary.candidates_with_rank_changes}
            />
            <StatCard
              label="Unchanged"
              value={data.summary.candidates_unchanged}
            />
          </div>

          {/* Tab Navigation */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-1">
            <nav className="flex gap-1">
              {(
                ["overview", "weights", "candidates", "insights"] as const
              ).map((tab) => (
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
                    : tab === "weights"
                      ? "Weight Changes"
                      : tab === "candidates"
                        ? "Candidates"
                        : "Insights"}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Score Change Summary */}
              <SectionCard title="Score Change Summary">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Candidates with score changes
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {data.summary.candidates_with_score_changes} /{" "}
                      {data.summary.total_candidates}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Average score change
                    </span>
                    <span
                      className={`text-sm font-medium ${getScoreColor(data.summary.average_score_change)}`}
                    >
                      {data.summary.average_score_change > 0 ? "+" : ""}
                      {data.summary.average_score_change}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Largest increase
                    </span>
                    <span className="text-sm font-medium text-green-600">
                      +{data.summary.largest_score_increase}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      Largest decrease
                    </span>
                    <span className="text-sm font-medium text-red-600">
                      {data.summary.largest_score_decrease}
                    </span>
                  </div>
                </div>
              </SectionCard>

              {/* Top Score Changes */}
              {changedCandidates.length > 0 && (
                <SectionCard title="Largest Score Changes">
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                          <th className="px-3 py-2">Candidate</th>
                          <th className="px-3 py-2 text-right">Baseline</th>
                          <th className="px-3 py-2 text-right">Simulation</th>
                          <th className="px-3 py-2 text-right">Change</th>
                          <th className="px-3 py-2 text-right">Rank</th>
                          <th className="px-3 py-2">Type</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {changedCandidates.slice(0, 10).map((c) => (
                          <tr
                            key={c.candidate_id}
                            className="cursor-pointer hover:bg-gray-50"
                            onClick={() => {
                              setSelectedCandidate(c);
                              setActiveTab("candidates");
                            }}
                          >
                            <td className="whitespace-nowrap px-3 py-2 font-medium text-gray-900">
                              {c.candidate_name}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {c.baseline_score}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {c.simulation_score}
                            </td>
                            <td
                              className={`whitespace-nowrap px-3 py-2 text-right font-medium ${getScoreColor(c.score_change)}`}
                            >
                              {formatScoreChange(c.score_change)}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              #{c.baseline_rank} &rarr; #{c.simulation_rank}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2">
                              <ImpactBadge impactType={c.impact_type} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}

              {/* Rank-Only Changes */}
              {rankOnlyCandidates.length > 0 && (
                <SectionCard title="Rank-Only Changes (Score Unchanged)">
                  <p className="mb-3 text-sm text-gray-500">
                    These candidates had rank changes without score changes,
                    due to changes in relative ordering of other candidates.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                          <th className="px-3 py-2">Candidate</th>
                          <th className="px-3 py-2 text-right">Score</th>
                          <th className="px-3 py-2 text-right">Rank</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {rankOnlyCandidates.slice(0, 10).map((c) => (
                          <tr key={c.candidate_id} className="hover:bg-gray-50">
                            <td className="whitespace-nowrap px-3 py-2 font-medium text-gray-900">
                              {c.candidate_name}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              {c.baseline_score} (unchanged)
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                              #{c.baseline_rank} &rarr; #{c.simulation_rank}(
                              {c.rank_change > 0 ? "+" : ""}
                              {c.rank_change})
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

          {activeTab === "weights" && (
            <div className="space-y-6">
              <SectionCard title="Scoring Weight Changes">
                <p className="mb-4 text-sm text-gray-500">
                  Changes to scoring weights between baseline and simulation
                  configurations. These weight changes drive the per-dimension
                  contribution changes visible in candidate details.
                </p>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                        <th className="px-3 py-2">Feature</th>
                        <th className="px-3 py-2 text-right">Baseline</th>
                        <th className="px-3 py-2 text-right">Simulation</th>
                        <th className="px-3 py-2 text-right">Change</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {data.weight_changes.map((wc) => (
                        <tr key={wc.feature} className="hover:bg-gray-50">
                          <td className="whitespace-nowrap px-3 py-2 font-medium text-gray-900">
                            {wc.feature_label}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                            {formatWeight(wc.baseline_weight)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                            {formatWeight(wc.simulation_weight)}
                          </td>
                          <td
                            className={`whitespace-nowrap px-3 py-2 text-right font-medium ${getScoreColor(wc.weight_change * 100)}`}
                          >
                            {wc.weight_change !== 0
                              ? `${wc.weight_change > 0 ? "+" : ""}${(wc.weight_change * 100).toFixed(1)} pp`
                              : "0 pp"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            </div>
          )}

          {activeTab === "candidates" && (
            <div className="space-y-6">
              {/* Candidate Selector */}
              <SectionCard title="Candidate Detail">
                <div className="mb-4">
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    Select a candidate
                  </label>
                  <select
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    value={selectedCandidate?.candidate_id ?? ""}
                    onChange={(e) => {
                      const c = data.candidates.find(
                        (cand) => cand.candidate_id === e.target.value,
                      );
                      setSelectedCandidate(c ?? null);
                    }}
                  >
                    <option value="">-- Select a candidate --</option>
                    {data.candidates.map((c) => (
                      <option key={c.candidate_id} value={c.candidate_id}>
                        {c.candidate_name} (
                        {formatScoreChange(c.score_change)} pts, Rank{" "}
                        {c.rank_change > 0 ? "+" : ""}
                        {c.rank_change})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedCandidate ? (
                  <CandidateDetail candidate={selectedCandidate} />
                ) : (
                  <p className="text-sm text-gray-500">
                    Select a candidate above to view their explainability
                    impact details.
                  </p>
                )}
              </SectionCard>
            </div>
          )}

          {activeTab === "insights" && (
            <div className="space-y-6">
              <SectionCard title="Explainability Impact Insights">
                {data.insights.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No insights generated.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {data.insights.map((insight, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
                      >
                        <span className="mt-0.5 text-base leading-none">
                          {INSIGHT_TYPE_ICONS[insight.type] ?? "\u{1F4CB}"}
                        </span>
                        <p className="text-sm text-gray-700">
                          {insight.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Candidate Detail Sub-Component ─────────────────────────────

function CandidateDetail({
  candidate,
}: {
  candidate: CandidateExplainabilityImpact;
}) {
  return (
    <div className="space-y-5">
      {/* Score & Rank Summary */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-gray-200 p-3">
          <p className="text-xs text-gray-500">Baseline Score</p>
          <p className="text-lg font-bold text-gray-900">
            {candidate.baseline_score}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 p-3">
          <p className="text-xs text-gray-500">Simulation Score</p>
          <p className="text-lg font-bold text-gray-900">
            {candidate.simulation_score}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 p-3">
          <p className="text-xs text-gray-500">Score Change</p>
          <p
            className={`text-lg font-bold ${getScoreColor(candidate.score_change)}`}
          >
            {formatScoreChange(candidate.score_change)}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 p-3">
          <p className="text-xs text-gray-500">Rank Change</p>
          <p
            className={`text-lg font-bold ${getScoreColor(candidate.rank_change)}`}
          >
            #{candidate.baseline_rank} &rarr; #{candidate.simulation_rank}(
            {candidate.rank_change > 0 ? "+" : ""}
            {candidate.rank_change})
          </p>
        </div>
      </div>

      {/* Impact Type */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600">Impact type:</span>
        <ImpactBadge impactType={candidate.impact_type} />
        {candidate.impact_type === "rank_only_changed" && (
          <span className="text-xs text-gray-500">
            Score unchanged. Rank changed due to changes in relative ordering
            of other candidates.
          </span>
        )}
        {candidate.impact_type === "threshold_only" && (
          <span className="text-xs text-gray-500">
            Score and contributions unchanged. Qualification status changed
            due to threshold adjustment.
          </span>
        )}
      </div>

      {/* Reason */}
      {candidate.reason && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
          <p className="text-sm text-blue-800">{candidate.reason}</p>
        </div>
      )}

      {/* Feature Contribution Comparison */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-900">
          Feature Contribution Comparison
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2">Feature</th>
                <th className="px-3 py-2 text-right">Weight (B)</th>
                <th className="px-3 py-2 text-right">Weight (S)</th>
                <th className="px-3 py-2 text-right">Score (B)</th>
                <th className="px-3 py-2 text-right">Score (S)</th>
                <th className="px-3 py-2 text-right">Contribution (B)</th>
                <th className="px-3 py-2 text-right">Contribution (S)</th>
                <th className="px-3 py-2 text-right">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {candidate.feature_contributions.map((fc) => (
                <tr key={fc.feature} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-3 py-2 font-medium text-gray-900">
                    {fc.feature_label}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                    {formatWeight(fc.baseline_weight)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                    {formatWeight(fc.simulation_weight)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                    {fc.baseline_dimension_score}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                    {fc.simulation_dimension_score}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                    {formatContribution(fc.baseline_contribution)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                    {formatContribution(fc.simulation_contribution)}
                  </td>
                  <td
                    className={`whitespace-nowrap px-3 py-2 text-right font-medium ${getContributionColor(fc.contribution_change)}`}
                  >
                    {formatContribution(fc.contribution_change)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Contribution Visualization */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-900">
          Contribution Visualization
        </h3>
        <div className="space-y-4">
          {candidate.feature_contributions
            .filter(
              (fc) =>
                fc.baseline_contribution !== 0 ||
                fc.simulation_contribution !== 0,
            )
            .sort(
              (a, b) =>
                Math.abs(b.contribution_change) -
                Math.abs(a.contribution_change),
            )
            .map((fc) => (
              <ContributionBar
                key={fc.feature}
                feature={fc.feature_label}
                baseline={fc.baseline_contribution}
                simulation={fc.simulation_contribution}
              />
            ))}
        </div>
      </div>

      {/* Top Changes */}
      <div className="grid grid-cols-2 gap-4">
        {candidate.top_positive_changes.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-green-700">
              Largest Positive Changes
            </h3>
            <div className="space-y-1">
              {candidate.top_positive_changes.map((fc) => (
                <div
                  key={fc.feature}
                  className="flex items-center justify-between rounded-lg bg-green-50 px-3 py-1.5"
                >
                  <span className="text-sm text-gray-700">
                    {fc.feature_label}
                  </span>
                  <span className="text-sm font-medium text-green-600">
                    {formatContribution(fc.contribution_change)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        {candidate.top_negative_changes.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-red-700">
              Largest Negative Changes
            </h3>
            <div className="space-y-1">
              {candidate.top_negative_changes.map((fc) => (
                <div
                  key={fc.feature}
                  className="flex items-center justify-between rounded-lg bg-red-50 px-3 py-1.5"
                >
                  <span className="text-sm text-gray-700">
                    {fc.feature_label}
                  </span>
                  <span className="text-sm font-medium text-red-600">
                    {formatContribution(fc.contribution_change)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
