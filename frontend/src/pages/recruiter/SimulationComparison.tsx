import { useEffect, useState } from "react";
import { simulationApi } from "../../api/simulations";
import type { SimulationScenarioListItem } from "../../types/simulations";
import type {
  MultiScenarioComparisonResponse,
  CandidateComparison,
  ScenarioMetadata,
} from "../../types/simulationComparison";
import {
  CHANGE_TYPE_COLORS,
  REQUIREMENT_COLORS,
  formatWeight,
  formatScoreChange,
  getRankColor,
} from "../../types/simulationComparison";

type Tab =
  | "select"
  | "overview"
  | "configuration"
  | "candidates"
  | "ranking"
  | "requirements"
  | "fairness"
  | "explainability"
  | "skills"
  | "insights";

export function SimulationComparison() {
  const [scenarios, setScenarios] = useState<SimulationScenarioListItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<MultiScenarioComparisonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("select");
  const [listLoading, setListLoading] = useState(true);

  useEffect(() => {
    setListLoading(true);
    simulationApi
      .list()
      .then((res) => {
        const completed = (res.items || []).filter(
          (s: SimulationScenarioListItem) => s.status === "completed" || s.status === "ready",
        );
        setScenarios(completed);
      })
      .catch(console.error)
      .finally(() => setListLoading(false));
  }, []);

  const toggleSelection = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 5) return prev;
      return [...prev, id];
    });
  };

  const handleCompare = async () => {
    if (selectedIds.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const result = await simulationApi.compareScenarios({
        scenario_ids: selectedIds,
      });
      setComparison(result);
      setActiveTab("overview");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to compare scenarios";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const resetComparison = () => {
    setComparison(null);
    setActiveTab("select");
    setError(null);
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Multi-Scenario Comparison
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Compare multiple completed simulation scenarios side-by-side.
          </p>
        </div>
        {comparison && (
          <button
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            onClick={resetComparison}
          >
            New comparison
          </button>
        )}
      </div>

      {/* What-if banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          <strong>What-if analysis</strong> &mdash; This comparison aggregates
          and contrasts persisted outputs from completed simulations. No live
          hiring data was modified.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Scenario Selection */}
      {activeTab === "select" && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              Select Scenarios (2–5)
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Choose completed scenarios belonging to the same job to compare.
            </p>
            {listLoading ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
              </div>
            ) : scenarios.length === 0 ? (
              <p className="text-gray-500 text-sm py-4">
                No completed scenarios available. Run a simulation first.
              </p>
            ) : (
              <div className="grid gap-3">
                {scenarios.map((s) => (
                  <label
                    key={s.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedIds.includes(s.id)
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(s.id)}
                      onChange={() => toggleSelection(s.id)}
                      className="h-4 w-4 text-blue-600 rounded"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {s.name}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {s.job_title || "Job"} &middot; {s.company || ""}
                      </p>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        s.status === "completed"
                          ? "bg-green-100 text-green-700"
                          : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {s.status}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={selectedIds.length < 2 || loading}
              onClick={handleCompare}
            >
              {loading ? "Comparing..." : `Compare ${selectedIds.length} scenarios`}
            </button>
            {selectedIds.length > 0 && (
              <span className="text-sm text-gray-500">
                {selectedIds.length} selected
              </span>
            )}
          </div>
        </div>
      )}

      {/* Comparison Dashboard */}
      {comparison && activeTab !== "select" && (
        <ComparisonDashboard
          comparison={comparison}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />
      )}

      {/* Loading state while comparing */}
      {loading && !comparison && (
        <div className="flex flex-col items-center justify-center h-64 space-y-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          <p className="text-sm text-gray-500">
            Preparing scenario comparison...
          </p>
        </div>
      )}
    </div>
  );
}

/* ─── Comparison Dashboard ────────────────────────────────────── */

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "configuration", label: "Configuration" },
  { key: "candidates", label: "Candidates" },
  { key: "ranking", label: "Ranking" },
  { key: "requirements", label: "Requirements" },
  { key: "fairness", label: "Fairness" },
  { key: "explainability", label: "Explainability" },
  { key: "skills", label: "Skills" },
  { key: "insights", label: "Insights" },
];

function ComparisonDashboard({
  comparison,
  activeTab,
  onTabChange,
}: {
  comparison: MultiScenarioComparisonResponse;
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}) {
  const { scenarios } = comparison;

  return (
    <div className="space-y-6">
      {/* Scenario headers */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${scenarios.length}, minmax(0, 1fr))` }}>
        {scenarios.map((s) => (
          <ScenarioCard key={s.scenario_id} scenario={s} />
        ))}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-6 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={`py-2 px-1 border-b-2 text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.key
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
              onClick={() => onTabChange(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewTab comparison={comparison} />}
      {activeTab === "configuration" && <ConfigurationTab comparison={comparison} />}
      {activeTab === "candidates" && <CandidatesTab comparison={comparison} />}
      {activeTab === "ranking" && <RankingTab comparison={comparison} />}
      {activeTab === "requirements" && <RequirementsTab comparison={comparison} />}
      {activeTab === "fairness" && <FairnessTab comparison={comparison} />}
      {activeTab === "explainability" && <ExplainabilityTab comparison={comparison} />}
      {activeTab === "skills" && <SkillsTab comparison={comparison} />}
      {activeTab === "insights" && <InsightsTab comparison={comparison} />}
    </div>
  );
}

/* ─── Scenario Card ───────────────────────────────────────────── */

function ScenarioCard({ scenario }: { scenario: ScenarioMetadata }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <p className="text-sm font-semibold text-gray-900 truncate">
        {scenario.name}
      </p>
      <p className="text-xs text-gray-500 truncate">
        {scenario.job_title}
        {scenario.company && ` \u00B7 ${scenario.company}`}
      </p>
      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
        <span>{scenario.total_candidates} candidates</span>
        <span
          className={`px-1.5 py-0.5 rounded-full ${
            scenario.status === "completed"
              ? "bg-green-100 text-green-700"
              : "bg-gray-100 text-gray-600"
          }`}
        >
          {scenario.status}
        </span>
      </div>
    </div>
  );
}

/* ─── Overview Tab ────────────────────────────────────────────── */

function OverviewTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { scenarios, candidate_pool, ranking_comparison, insights } = comparison;

  return (
    <div className="space-y-6">
      {/* Candidate pool */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Candidate Pool
        </h3>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-gray-500">Common candidates</p>
            <p className="font-medium">{candidate_pool.common_candidates}</p>
          </div>
          <div>
            <p className="text-gray-500">Total unique</p>
            <p className="font-medium">{candidate_pool.total_unique}</p>
          </div>
          <div>
            <p className="text-gray-500">Identical pools</p>
            <p className="font-medium">
              {candidate_pool.identical_pools ? "Yes" : "No"}
            </p>
          </div>
        </div>
      </div>

      {/* Ranking distributions */}
      {ranking_comparison.distributions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Ranking Summary
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 text-gray-500 font-medium">Metric</th>
                  {scenarios.map((s) => (
                    <th key={s.scenario_id} className="text-right py-2 text-gray-500 font-medium px-3">
                      {s.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-gray-50">
                  <td className="py-2 text-gray-600">Candidates</td>
                  {ranking_comparison.distributions.map((d) => (
                    <td key={d.scenario_id} className="py-2 text-right px-3 font-medium">
                      {d.total_candidates}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-50">
                  <td className="py-2 text-gray-600">Avg Score</td>
                  {ranking_comparison.distributions.map((d) => (
                    <td key={d.scenario_id} className="py-2 text-right px-3">
                      {d.avg_score}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-50">
                  <td className="py-2 text-gray-600">Qualified</td>
                  {ranking_comparison.distributions.map((d) => (
                    <td key={d.scenario_id} className="py-2 text-right px-3">
                      {d.qualified_count}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2 text-gray-600">Shortlisted</td>
                  {ranking_comparison.distributions.map((d) => (
                    <td key={d.scenario_id} className="py-2 text-right px-3">
                      {d.shortlisted_count}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Insights */}
      {insights.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Insights</h3>
          <ul className="space-y-2">
            {insights.map((ins, i) => (
              <li key={i} className="text-sm text-gray-700">
                &bull; {ins.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ─── Configuration Tab ───────────────────────────────────────── */

function ConfigurationTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { scenarios, configuration_comparison: config } = comparison;

  return (
    <div className="space-y-6">
      {/* Scoring Weights */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Scoring Weights
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 text-gray-500 font-medium">Weight</th>
                {scenarios.map((s) => (
                  <th key={s.scenario_id} className="text-right py-2 text-gray-500 font-medium px-3">
                    {s.name}
                  </th>
                ))}
                <th className="text-right py-2 text-gray-500 font-medium px-3">
                  Spread
                </th>
              </tr>
            </thead>
            <tbody>
              {config.weights.map((w) => (
                <tr key={w.weight_name} className="border-b border-gray-50">
                  <td className="py-2 text-gray-600">{w.weight_label}</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario_id} className="py-2 text-right px-3 font-medium">
                      {formatWeight(w.values[s.scenario_id] || 0)}
                    </td>
                  ))}
                  <td className="py-2 text-right px-3 text-gray-500">
                    {w.range_spread > 0
                      ? `${Math.round(w.range_spread * 100)} pp`
                      : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Threshold & Shortlist */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Threshold &amp; Shortlist
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 text-gray-500 font-medium">Setting</th>
                {scenarios.map((s) => (
                  <th key={s.scenario_id} className="text-right py-2 text-gray-500 font-medium px-3">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-50">
                <td className="py-2 text-gray-600">Threshold</td>
                {scenarios.map((s) => (
                  <td key={s.scenario_id} className="py-2 text-right px-3 font-medium">
                    {config.threshold.values[s.scenario_id] ?? "\u2014"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="py-2 text-gray-600">Shortlist Size</td>
                {scenarios.map((s) => (
                  <td key={s.scenario_id} className="py-2 text-right px-3 font-medium">
                    {config.shortlist_size.values[s.scenario_id] ?? "\u2014"}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Skill Requirements */}
      {config.skill_requirements.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Skill Requirements
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 text-gray-500 font-medium">Skill</th>
                  {scenarios.map((s) => (
                    <th key={s.scenario_id} className="text-center py-2 text-gray-500 font-medium px-3">
                      {s.name}
                    </th>
                  ))}
                  <th className="text-center py-2 text-gray-500 font-medium px-3">
                    Change
                  </th>
                </tr>
              </thead>
              <tbody>
                {config.skill_requirements.map((sr) => (
                  <tr key={sr.skill_name} className="border-b border-gray-50">
                    <td className="py-2 font-medium text-gray-900">
                      {sr.skill_name}
                    </td>
                    {scenarios.map((s) => (
                      <td key={s.scenario_id} className="py-2 text-center px-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            REQUIREMENT_COLORS[sr.values[s.scenario_id]] || ""
                          }`}
                        >
                          {sr.values[s.scenario_id] || "N/A"}
                        </span>
                      </td>
                    ))}
                    <td className="py-2 text-center px-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          CHANGE_TYPE_COLORS[sr.change_type] || ""
                        }`}
                      >
                        {sr.change_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Candidates Tab ──────────────────────────────────────────── */

function CandidatesTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { scenarios, candidate_comparison: candidates } = comparison;
  const [search, setSearch] = useState("");

  const filtered = candidates.filter(
    (c) =>
      !search ||
      c.candidate_name.toLowerCase().includes(search.toLowerCase()),
  );

  if (candidates.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No common candidates across scenarios.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <input
        type="text"
        placeholder="Search candidates..."
        className="border border-gray-300 rounded-md px-3 py-1.5 text-sm w-full max-w-sm"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-500">
                Candidate
              </th>
              <th className="px-3 py-2 text-right font-medium text-gray-500">
                Baseline Rank
              </th>
              {scenarios.map((s) => (
                <th key={s.scenario_id} className="px-3 py-2 text-right font-medium text-gray-500">
                  {s.name} (Rank)
                </th>
              ))}
              <th className="px-3 py-2 text-right font-medium text-gray-500">
                Rank Movement
              </th>
              <th className="px-3 py-2 text-center font-medium text-gray-500">
                Shortlisted
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.slice(0, 50).map((c) => (
              <CandidateRow key={c.candidate_id} candidate={c} scenarios={scenarios} />
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > 50 && (
        <p className="text-xs text-gray-400 text-center">
          Showing 50 of {filtered.length} candidates
        </p>
      )}
    </div>
  );
}

function CandidateRow({
  candidate,
  scenarios,
}: {
  candidate: CandidateComparison;
  scenarios: ScenarioMetadata[];
}) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-3 py-2 font-medium text-gray-900">
        {candidate.candidate_name}
      </td>
      <td className="px-3 py-2 text-right text-gray-600">
        #{candidate.baseline_rank}
      </td>
      {scenarios.map((s) => {
        const outcome = candidate.scenarios.find(
          (o) => o.scenario_id === s.scenario_id,
        );
        return (
          <td key={s.scenario_id} className="px-3 py-2 text-right">
            {outcome ? (
              <span className={`font-medium ${getRankColor(outcome.rank_change)}`}>
                #{outcome.simulation_rank}
                <span className="text-xs ml-1">
                  ({formatScoreChange(outcome.rank_change)})
                </span>
              </span>
            ) : (
              "\u2014"
            )}
          </td>
        );
      })}
      <td
        className={`px-3 py-2 text-right font-medium ${getRankColor(candidate.max_rank_movement)}`}
      >
        {candidate.rank_range_min}–{candidate.rank_range_max}
      </td>
      <td className="px-3 py-2 text-center">
        <span className="text-sm">
          {candidate.shortlisted_count}/{scenarios.length}
        </span>
      </td>
    </tr>
  );
}

/* ─── Ranking Tab ─────────────────────────────────────────────── */

function RankingTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { scenarios, ranking_comparison: ranking } = comparison;

  return (
    <div className="space-y-6">
      {/* Distributions */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Score Distributions
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 text-gray-500 font-medium">Metric</th>
                {scenarios.map((s) => (
                  <th key={s.scenario_id} className="text-right py-2 text-gray-500 font-medium px-3">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ranking.distributions.map((d) => (
                <tr key={d.scenario_id} className="border-b border-gray-50">
                  <td className="py-2 text-gray-600">
                    {scenarios.find((s) => s.scenario_id === d.scenario_id)?.name}
                  </td>
                  <td className="py-2 text-right px-3">Avg: {d.avg_score}</td>
                  <td className="py-2 text-right px-3">Median: {d.median_score}</td>
                  <td className="py-2 text-right px-3">Qualified: {d.qualified_count}</td>
                  <td className="py-2 text-right px-3">Shortlisted: {d.shortlisted_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Shortlist Overlaps */}
      {ranking.pairwise_overlaps.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Shortlist Overlap
          </h3>
          <div className="space-y-3">
            {ranking.pairwise_overlaps.map((o, i) => {
              const nameA = scenarios.find((s) => s.scenario_id === o.scenario_a_id)?.name || "A";
              const nameB = scenarios.find((s) => s.scenario_id === o.scenario_b_id)?.name || "B";
              return (
                <div key={i} className="flex items-center gap-4 text-sm">
                  <span className="font-medium text-gray-700 w-48 truncate">
                    {nameA} &harr; {nameB}
                  </span>
                  <span className="text-gray-600">
                    Common: {o.common_count}
                  </span>
                  <span className="text-gray-600">
                    Only {nameA}: {o.only_a_count}
                  </span>
                  <span className="text-gray-600">
                    Only {nameB}: {o.only_b_count}
                  </span>
                  <span className="text-gray-500">
                    Jaccard: {Math.round(o.jaccard_similarity * 100)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Requirements Tab ────────────────────────────────────────── */

function RequirementsTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { scenarios, requirement_comparison: reqs } = comparison;
  const changed = reqs.items.filter((item) => item.is_changed);

  return (
    <div className="space-y-4">
      {changed.length === 0 ? (
        <div className="text-center py-8 text-gray-500 text-sm">
          No requirement differences across scenarios.
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Changed Requirements ({changed.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 text-gray-500 font-medium">Requirement</th>
                  {scenarios.map((s) => (
                    <th key={s.scenario_id} className="text-center py-2 text-gray-500 font-medium px-3">
                      {s.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {changed.map((item) => (
                  <tr key={item.requirement_name} className="border-b border-gray-50">
                    <td className="py-2 font-medium text-gray-900">
                      {item.requirement_name}
                    </td>
                    {scenarios.map((s) => (
                      <td key={s.scenario_id} className="py-2 text-center px-3">
                        <span className="text-sm text-gray-600">
                          {item.values[s.scenario_id] || "N/A"}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Fairness Tab ────────────────────────────────────────────── */

function FairnessTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { fairness_comparison: fairness } = comparison;

  if (!fairness.any_available) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        Fairness comparison unavailable for these scenarios.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Fairness Metrics
      </h3>
      <div className="space-y-2">
        {fairness.scenarios.map((s) => (
          <div key={s.scenario_id} className="flex items-center gap-3 text-sm">
            <span className="font-medium text-gray-700 w-48 truncate">
              {s.scenario_id}
            </span>
            {s.available ? (
              <span className="text-green-600">Available</span>
            ) : (
              <span className="text-gray-400">{s.unavailable_reason}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Explainability Tab ──────────────────────────────────────── */

function ExplainabilityTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { explainability_comparison: xai } = comparison;

  if (!xai.any_available) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        Explainability comparison unavailable for these scenarios.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Explainability Metrics
      </h3>
      <div className="space-y-2">
        {xai.scenarios.map((s) => (
          <div key={s.scenario_id} className="flex items-center gap-3 text-sm">
            <span className="font-medium text-gray-700 w-48 truncate">
              {s.scenario_id}
            </span>
            {s.available ? (
              <span className="text-gray-600">
                Candidates with changes: {s.candidates_with_changes}
              </span>
            ) : (
              <span className="text-gray-400">Unavailable</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Skills Tab ──────────────────────────────────────────────── */

function SkillsTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { skill_comparison: skills } = comparison;

  if (!skills.any_available) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        Skill comparison unavailable for these scenarios.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Skill Impact Comparison
      </h3>
      <div className="space-y-2">
        {skills.scenarios.map((s) => (
          <div key={s.scenario_id} className="flex items-center gap-3 text-sm">
            <span className="font-medium text-gray-700 w-48 truncate">
              {s.scenario_id}
            </span>
            {s.available ? (
              <span className="text-gray-600">
                Skills analyzed: {s.total_skills_analyzed}, Affected: {s.candidates_affected}
              </span>
            ) : (
              <span className="text-gray-400">Unavailable</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Insights Tab ────────────────────────────────────────────── */

function InsightsTab({ comparison }: { comparison: MultiScenarioComparisonResponse }) {
  const { insights } = comparison;

  if (insights.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No insights generated for this comparison.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Comparison Insights
      </h3>
      <ul className="space-y-2">
        {insights.map((ins, i) => (
          <li key={i} className="text-sm text-gray-700">
            &bull; {ins.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
