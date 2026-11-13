import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { sandboxApi } from "../../api/sandbox";
import { simulationApi } from "../../api/simulations";
import type { SimulationScenarioListItem } from "../../types/simulations";
import type {
  SandboxListItem,
  SandboxResponse,
  StrategyListItem,
} from "../../types/sandbox";
import { SANDBOX_PRESETS } from "../../types/sandbox";

export function SandboxDashboard() {
  const navigate = useNavigate();
  const [sandboxes, setSandboxes] = useState<SandboxListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSandbox, setSelectedSandbox] = useState<SandboxResponse | null>(null);
  const [strategies, setStrategies] = useState<StrategyListItem[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [createName, setCreateName] = useState("");
  const [scenarios, setScenarios] = useState<SimulationScenarioListItem[]>([]);

  useEffect(() => {
    loadSandboxes();
  }, []);

  useEffect(() => {
    if (selectedSandbox) {
      loadStrategies(selectedSandbox.id);
    }
  }, [selectedSandbox]);

  const loadSandboxes = async () => {
    setLoading(true);
    try {
      const res = await sandboxApi.list();
      setSandboxes(res.items || []);
    } catch (err) {
      console.error("Failed to load sandboxes", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStrategies = async (sandboxId: string) => {
    setStrategiesLoading(true);
    try {
      const res = await sandboxApi.listStrategies(sandboxId);
      setStrategies(res.items || []);
    } catch (err) {
      console.error("Failed to load strategies", err);
    } finally {
      setStrategiesLoading(false);
    }
  };

  const handleCreateSandbox = async () => {
    if (!createName.trim() || scenarios.length === 0) return;
    setCreating(true);
    try {
      const job_id = scenarios[0].job_id;
      const sandbox = await sandboxApi.create({
        job_id,
        name: createName.trim(),
        description: "Hiring strategy experimentation workspace",
      });
      setSelectedSandbox(sandbox);
      setCreateName("");
      await loadSandboxes();
    } catch (err) {
      console.error("Failed to create sandbox", err);
    } finally {
      setCreating(false);
    }
  };

  const handleCreateFromPreset = async (preset: typeof SANDBOX_PRESETS[0]) => {
    if (!selectedSandbox) return;
    try {
      await sandboxApi.createStrategy(selectedSandbox.id, {
        name: preset.label,
        description: preset.description,
        simulation_config: preset.config,
        tags: [preset.name],
      });
      await loadStrategies(selectedSandbox.id);
    } catch (err) {
      console.error("Failed to create strategy", err);
    }
  };

  const handleDuplicate = async (strategy: StrategyListItem, branch: boolean) => {
    if (!selectedSandbox) return;
    try {
      await sandboxApi.duplicateStrategy(selectedSandbox.id, strategy.id, {
        name: branch ? `${strategy.name} — Branch` : `${strategy.name} (Copy)`,
        branch,
        tags: strategy.tags || [],
      });
      await loadStrategies(selectedSandbox.id);
    } catch (err) {
      console.error("Failed to duplicate strategy", err);
    }
  };

  const handleRun = async (strategy: StrategyListItem) => {
    try {
      await simulationApi.run(strategy.scenario_id);
      if (selectedSandbox) await loadStrategies(selectedSandbox.id);
    } catch (err) {
      console.error("Failed to run simulation", err);
    }
  };

  const handleCompare = async () => {
    if (!selectedSandbox || selectedIds.length < 2) return;
    try {
      const result = await sandboxApi.compare(selectedSandbox.id, {
        strategy_ids: selectedIds,
      });
      // Navigate to comparison view or show results
      console.log("Comparison result:", result);
    } catch (err) {
      console.error("Failed to compare", err);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleOpenSandbox = async (sb: SandboxListItem) => {
    try {
      const full = await sandboxApi.get(sb.id);
      setSelectedSandbox(full);
      setSelectedIds([]);
    } catch (err) {
      console.error("Failed to load sandbox", err);
    }
  };

  const handleArchive = async (sb: SandboxListItem) => {
    if (!confirm(`Archive "${sb.name}"?`)) return;
    try {
      await sandboxApi.archive(sb.id);
      await loadSandboxes();
      if (selectedSandbox?.id === sb.id) setSelectedSandbox(null);
    } catch (err) {
      console.error("Failed to archive", err);
    }
  };

  const handleDeleteStrategy = async (strategy: StrategyListItem) => {
    if (!selectedSandbox || !confirm(`Delete "${strategy.name}"?`)) return;
    try {
      await sandboxApi.removeStrategy(selectedSandbox.id, strategy.id);
      await loadStrategies(selectedSandbox.id);
      setSelectedIds((prev) => prev.filter((x) => x !== strategy.id));
    } catch (err) {
      console.error("Failed to delete strategy", err);
    }
  };

  const handleBackToList = () => {
    setSelectedSandbox(null);
    setStrategies([]);
    setSelectedIds([]);
  };

  // Load available scenarios for creating sandboxes
  useEffect(() => {
    simulationApi.list().then((res) => {
      setScenarios(res.items || []);
    }).catch(console.error);
  }, []);

  // ─── Sandbox List View ───────────────────────────────────────

  if (!selectedSandbox) {
    return (
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Hiring Strategy Sandbox</h1>
            <p className="page-subtitle">
              Experiment with hypothetical hiring strategies in an isolated workspace.
            </p>
          </div>
          <button
            onClick={() => navigate("/simulations/reports")}
            className="btn-secondary"
          >
            View Reports
          </button>
        </div>

        <div className="info-banner">
          <p>
            <strong>What-if Hiring Strategy Sandbox</strong> — All changes are hypothetical.
            They do not modify live jobs, candidates, applications, rankings, or hiring configuration.
          </p>
        </div>

        {/* Create new sandbox */}
        <div className="card p-4">
          <h3 className="section-title">Create New Sandbox</h3>
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              className="field flex-1"
              placeholder="Sandbox name (e.g., Senior Dev — Strategy Lab)"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateSandbox()}
            />
            <button
              className="btn-primary"
              onClick={handleCreateSandbox}
              disabled={creating || !createName.trim() || scenarios.length === 0}
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
          {scenarios.length === 0 && (
            <p className="mt-2 text-xs font-medium text-amber-600">
              No completed simulations found. Run at least one simulation first.
            </p>
          )}
        </div>

        {/* Sandbox list */}
        <div className="space-y-3">
          <h3 className="section-title">Your Sandboxes</h3>
          {loading ? (
            <div className="grid gap-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-24 w-full" />
              ))}
            </div>
          ) : sandboxes.length === 0 ? (
            <div className="empty-state">
              <p className="text-sm text-gray-500">
                No sandboxes yet. Create one to start experimenting.
              </p>
            </div>
          ) : (
            <div className="grid gap-3">
              {sandboxes.map((sb) => (
                <div key={sb.id} className="card card-hover p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-gray-900">{sb.name}</h4>
                      <p className="mt-0.5 text-xs text-gray-500">
                        {sb.job_title}{sb.company ? ` — ${sb.company}` : ""}
                      </p>
                      <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                        <span>{sb.strategy_count} strategies</span>
                        <span>{sb.completed_count} completed</span>
                        <span
                          className={
                            sb.status === "active" ? "badge-success" : "badge-neutral"
                          }
                        >
                          {sb.status}
                        </span>
                      </div>
                    </div>
                    <div className="ml-4 flex items-center gap-2">
                      <button
                        className="btn-ghost btn-sm text-primary-600 hover:text-primary-700"
                        onClick={() => handleOpenSandbox(sb)}
                      >
                        Open
                      </button>
                      <button
                        className="btn-ghost btn-sm"
                        onClick={() => handleArchive(sb)}
                      >
                        Archive
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ─── Sandbox Detail View ─────────────────────────────────────

  const baseline = selectedSandbox.baseline_snapshot as Record<string, unknown>;
  const baselineWeights = (baseline?.scoring_weights || {}) as Record<string, number>;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            className="text-sm text-blue-600 hover:text-blue-800 mb-1"
            onClick={handleBackToList}
          >
            ← Back to Sandboxes
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{selectedSandbox.name}</h1>
          <p className="text-sm text-gray-500">
            {selectedSandbox.job_title}{selectedSandbox.company ? ` — ${selectedSandbox.company}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.length >= 2 && (
            <button
              className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium"
              onClick={handleCompare}
            >
              Compare ({selectedIds.length})
            </button>
          )}
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <p className="text-sm text-blue-800">
          <strong>What-if Hiring Strategy Sandbox</strong> — All changes are hypothetical.
          No live hiring data will be modified.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Strategy Tree */}
        <div className="lg:col-span-2 space-y-4">
          {/* Create from preset */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Create Strategy from Preset</h3>
            <div className="flex flex-wrap gap-2">
              {SANDBOX_PRESETS.map((preset) => (
                <button
                  key={preset.name}
                  className="px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors"
                  onClick={() => handleCreateFromPreset(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Baseline */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Baseline Configuration</h3>
            <div className="grid grid-cols-4 gap-3 text-xs">
              {Object.entries(baselineWeights).map(([key, val]) => (
                <div key={key}>
                  <span className="text-gray-500 capitalize">{key.replace("_", " ")}</span>
                  <p className="font-medium text-gray-900">{(val * 100).toFixed(0)}%</p>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs mt-3 pt-3 border-t border-gray-100">
              <div>
                <span className="text-gray-500">Threshold</span>
                <p className="font-medium text-gray-900">{String(baseline?.threshold || "N/A")}</p>
              </div>
              <div>
                <span className="text-gray-500">Shortlist</span>
                <p className="font-medium text-gray-900">{String(baseline?.shortlist_size || "N/A")}</p>
              </div>
            </div>
          </div>

          {/* Strategies */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
              Strategies ({strategies.length})
            </h3>
            {strategiesLoading ? (
              <div className="flex items-center justify-center h-24">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
              </div>
            ) : strategies.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-sm border border-dashed border-gray-300 rounded-lg">
                No strategies yet. Create one from a preset or use the Scenario Builder.
              </div>
            ) : (
              <div className="space-y-3">
                {strategies.map((s) => (
                  <StrategyCard
                    key={s.id}
                    strategy={s}
                    selected={selectedIds.includes(s.id)}
                    onSelect={() => toggleSelect(s.id)}
                    onDuplicate={(branch) => handleDuplicate(s, branch)}
                    onRun={() => handleRun(s)}
                    onDelete={() => handleDeleteStrategy(s)}
                    onView={() => {
                      window.location.href = `/recruiter/simulations/${s.scenario_id}`;
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Details Panel */}
        <div className="space-y-4">
          {selectedIds.length === 1 ? (
            <StrategyDetailsPanel
              strategy={strategies.find((s) => s.id === selectedIds[0]) || null}
            />
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Quick Actions</h3>
              <div className="space-y-2">
                <a
                  href={`/recruiter/simulations/create?job_id=${selectedSandbox.job_id}`}
                  className="block w-full text-center px-3 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
                >
                  + Create New Strategy
                </a>
                <a
                  href={`/recruiter/simulations/assistant`}
                  className="block w-full text-center px-3 py-2 bg-gray-100 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-200"
                >
                  AI Strategy Assistant
                </a>
                <a
                  href="/simulations/reports"
                  className="block w-full text-center px-3 py-2 bg-gray-100 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-200"
                >
                  View Reports
                </a>
              </div>
            </div>
          )}

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Strategy Tree</h3>
            <StrategyTree strategies={strategies} />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Strategy Card ───────────────────────────────────────────── */

function StrategyCard({
  strategy,
  selected,
  onSelect,
  onDuplicate,
  onRun,
  onDelete,
  onView,
}: {
  strategy: StrategyListItem;
  selected: boolean;
  onSelect: () => void;
  onDuplicate: (branch: boolean) => void;
  onRun: () => void;
  onDelete: () => void;
  onView: () => void;
}) {
  const statusColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700",
    ready: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    running: "bg-yellow-100 text-yellow-700",
    failed: "bg-red-100 text-red-700",
  };

  return (
    <div
      className={`border rounded-lg p-3 transition-colors cursor-pointer ${
        selected ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={selected}
            onChange={onSelect}
            className="h-4 w-4 text-blue-600 rounded"
            onClick={(e) => e.stopPropagation()}
          />
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-medium text-gray-900">{strategy.name}</h4>
              {strategy.branch_name && (
                <span className="text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded-full">
                  branch
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Skills {(strategy.skills_weight * 100).toFixed(0)}% · Experience {(strategy.experience_weight * 100).toFixed(0)}%
              {strategy.threshold ? ` · Threshold ${strategy.threshold}` : ""}
              {strategy.shortlist_size ? ` · Shortlist ${strategy.shortlist_size}` : ""}
            </p>
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[strategy.status] || "bg-gray-100 text-gray-700"}`}>
          {strategy.status}
        </span>
      </div>

      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100">
        <button
          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          onClick={(e) => { e.stopPropagation(); onView(); }}
        >
          View
        </button>
        {strategy.status === "draft" && (
          <button
            className="text-xs text-green-600 hover:text-green-800 font-medium"
            onClick={(e) => { e.stopPropagation(); onRun(); }}
          >
            Run
          </button>
        )}
        <button
          className="text-xs text-gray-500 hover:text-gray-700"
          onClick={(e) => { e.stopPropagation(); onDuplicate(false); }}
        >
          Duplicate
        </button>
        <button
          className="text-xs text-purple-600 hover:text-purple-800"
          onClick={(e) => { e.stopPropagation(); onDuplicate(true); }}
        >
          Branch
        </button>
        <button
          className="text-xs text-red-500 hover:text-red-700 ml-auto"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

/* ─── Strategy Details Panel ─────────────────────────────────── */

function StrategyDetailsPanel({ strategy }: { strategy: StrategyListItem | null }) {
  if (!strategy) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Select a strategy to view details.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-700">{strategy.name}</h3>
        {strategy.branch_name && (
          <p className="text-xs text-purple-600 mt-0.5">Branched from parent</p>
        )}
      </div>

      <div className="space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-500">Skills Weight</span>
          <span className="font-medium">{(strategy.skills_weight * 100).toFixed(0)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Experience Weight</span>
          <span className="font-medium">{(strategy.experience_weight * 100).toFixed(0)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Threshold</span>
          <span className="font-medium">{strategy.threshold}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Shortlist</span>
          <span className="font-medium">{strategy.shortlist_size}</span>
        </div>
      </div>

      <div className="pt-3 border-t border-gray-100 space-y-2 text-xs">
        <h4 className="font-semibold text-gray-700">Results</h4>
        <div className="flex justify-between">
          <span className="text-gray-500">Total Candidates</span>
          <span className="font-medium">{strategy.total_candidates}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Qualified</span>
          <span className="font-medium">{strategy.qualified_candidates}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Shortlisted</span>
          <span className="font-medium">{strategy.shortlisted_candidates}</span>
        </div>
      </div>

      {strategy.tags && strategy.tags.length > 0 && (
        <div className="pt-3 border-t border-gray-100">
          <div className="flex flex-wrap gap-1">
            {strategy.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Strategy Tree ──────────────────────────────────────────── */

function StrategyTree({ strategies }: { strategies: StrategyListItem[] }) {
  if (strategies.length === 0) {
    return <p className="text-xs text-gray-500">No strategies yet.</p>;
  }

  // Build tree structure
  const roots = strategies.filter((s) => !s.parent_strategy_id);
  const children = new Map<string, StrategyListItem[]>();
  for (const s of strategies) {
    if (s.parent_strategy_id) {
      const list = children.get(s.parent_strategy_id) || [];
      list.push(s);
      children.set(s.parent_strategy_id, list);
    }
  }

  const renderNode = (strategy: StrategyListItem, depth: number = 0) => {
    const kids = children.get(strategy.id) || [];
    return (
      <div key={strategy.id} style={{ paddingLeft: depth * 16 }}>
        <div className="flex items-center gap-1 py-1">
          {depth > 0 && <span className="text-gray-300">├─</span>}
          <span className={`text-xs ${strategy.branch_name ? "text-purple-600" : "text-gray-700"}`}>
            {strategy.name}
          </span>
          <span className="text-xs text-gray-400">
            ({strategy.status})
          </span>
        </div>
        {kids.map((kid) => renderNode(kid, depth + 1))}
      </div>
    );
  };

  return (
    <div className="space-y-0">
      {roots.map((root) => renderNode(root))}
    </div>
  );
}
