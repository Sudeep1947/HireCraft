import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { Button } from "../../components/ui/Button";
import {
  ScenarioConfiguration,
  SimulationConfigSummary,
} from "../../components/simulations/ScenarioConfiguration";
import { ScenarioStatusBadge } from "../../components/simulations/ScenarioStatusBadge";
import { ChangesSection } from "../../components/simulations/ChangesSection";
import { ValidationPanel } from "../../components/simulations/ValidationPanel";
import { useToast } from "../../contexts/ToastContext";
import { simulationApi } from "../../api/simulations";
import { simulationReportApi } from "../../api/simulationReports";
import {
  canRunSimulation,
  computeClientChanges,
  createDefaultSimulationConfiguration,
  isExecutionActive,
  isSimulationEditable,
  simulationConfigFromBaseline,
  validateSimulationConfig,
  type SimulationBaselineConfig,
  type SimulationChangesResponse,
  type SimulationConfiguration,
  type SimulationExecution,
  type SimulationScenario,
  type SimulationSummaryAggregate,
  type SimulationSummaryResponse,
} from "../../types/simulations";

export function SimulationDetails() {
  const { simulationId } = useParams<{ simulationId: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [scenario, setScenario] = useState<SimulationScenario | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftConfig, setDraftConfig] = useState<SimulationConfiguration | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [changes, setChanges] = useState<SimulationChangesResponse | null>(null);
  const [executions, setExecutions] = useState<SimulationExecution[]>([]);
  const [summary, setSummary] = useState<SimulationSummaryResponse | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  const draftValidation = useMemo(() => validateSimulationConfig(draftConfig), [draftConfig]);
  const liveChanges = useMemo(
    () =>
      scenario && editing && draftConfig
        ? computeClientChanges(scenario.baseline_config, draftConfig)
        : null,
    [scenario, editing, draftConfig],
  );

  const activeExecution = useMemo<SimulationExecution | null>(
    () => executions.find((e) => isExecutionActive(e.status)) ?? null,
    [executions],
  );

  async function refreshExecutionsAndSummary(scenarioId: string) {
    try {
      const list = await simulationApi.listExecutions(scenarioId);
      setExecutions(list.items);
      const latestCompleted = list.items
        .filter((e) => e.status === "completed")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
      if (latestCompleted) {
        setSummary(await simulationApi.getSummary(scenarioId, latestCompleted.id));
      }
    } catch {
      // Executions are a progressive enhancement; the page still renders without them.
    }
  }

  useEffect(() => {
    const id = simulationId;
    if (!id) return;
    let cancelled = false;
    async function load() {
      try {
        const data = await simulationApi.get(id!);
        if (cancelled) return;
        setScenario(data);
        setDraftConfig(data.simulation_config);
        try {
          const diff = await simulationApi.getChanges(data.id);
          if (!cancelled) setChanges(diff);
        } catch {
          // Diff is a progressive enhancement; the page still renders without it.
        }
        if (!cancelled) await refreshExecutionsAndSummary(data.id);
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
  }, [simulationId]);

  // Poll while a run is queued/running so status + results update live.
  useEffect(() => {
    if (!scenario || !activeExecution) return;
    const timer = setInterval(async () => {
      try {
        const list = await simulationApi.listExecutions(scenario.id);
        setExecutions(list.items);
        const stillActive = list.items.some((e) => isExecutionActive(e.status));
        if (!stillActive) {
          setScenario(await simulationApi.get(scenario.id));
          await refreshExecutionsAndSummary(scenario.id);
        }
      } catch {
        // Keep the current view; the next poll retries.
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [scenario, activeExecution]);

  async function handleRun() {
    if (!scenario) return;
    setRunning(true);
    try {
      const execution = await simulationApi.run(scenario.id);
      addToast(
        execution.status === "completed"
          ? `Run completed — ${execution.total_candidates} candidates evaluated`
          : `Simulation queued (${execution.status})`,
        execution.status === "failed" ? "error" : "success",
      );
      await refreshExecutionsAndSummary(scenario.id);
      if (execution.status !== "completed") {
        setScenario(await simulationApi.get(scenario.id));
      }
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "";
      addToast(
        detail ? `Run rejected: ${detail}` : "Failed to start simulation run",
        "error",
      );
    } finally {
      setRunning(false);
    }
  }

  async function handleCancelExecution(execution: SimulationExecution) {
    if (!scenario) return;
    setSaving(true);
    try {
      await simulationApi.cancelExecution(scenario.id, execution.id);
      addToast("Execution cancelled", "success");
      await refreshExecutionsAndSummary(scenario.id);
    } catch {
      addToast("Failed to cancel execution", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerateReport() {
    if (!scenario) return;
    setGeneratingReport(true);
    try {
      const report = await simulationReportApi.create({
        report_type: "simulation",
        simulation_id: scenario.id,
        title: `${scenario.name} — Simulation Report`,
        include: {
          include_candidate_details: true,
          include_fairness: true,
          include_explainability: true,
          include_skill_impact: true,
          include_ranking: true,
          include_requirements: true,
          include_threshold: true,
          include_shortlist: true,
          include_limitations: true,
          include_audit: true,
        },
      });
      addToast("Report generated successfully", "success");
      navigate(`/simulations/reports/${report.id}`);
    } catch {
      addToast("Failed to generate report", "error");
    } finally {
      setGeneratingReport(false);
    }
  }

  async function applyUpdate(patch: Parameters<typeof simulationApi.update>[1]) {
    if (!scenario) return;
    setSaving(true);
    try {
      const updated = await simulationApi.update(scenario.id, patch);
      setScenario(updated);
      setDraftConfig(updated.simulation_config);
      setEditing(false);
      try {
        setChanges(await simulationApi.getChanges(updated.id));
      } catch {
        // Keep stale diff; not critical.
      }
      addToast("Simulation updated", "success");
    } catch {
      addToast("Failed to update simulation", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveDraft() {
    if (!draftConfig) return;
    await applyUpdate({ simulation_config: draftConfig });
  }

  async function handleValidateAndPromote() {
    if (!draftConfig) return;
    if (!draftValidation.valid) {
      addToast(
        `${draftValidation.errors.length} validation issue(s) — fix before marking ready`,
        "error",
      );
      return;
    }
    // The backend re-validates authoritatively when applying the ready status.
    await applyUpdate({ simulation_config: draftConfig, status: "ready" });
  }

  async function handleMarkReady() {
    if (!scenario) return;
    setSaving(true);
    try {
      const validation = await simulationApi.validate(scenario.id);
      if (!validation.valid) {
        addToast(
          `${validation.errors.length} validation issue(s) — fix before marking ready`,
          "error",
        );
        return;
      }
      await applyUpdate({ status: "ready" });
    } catch {
      addToast("Failed to update simulation", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!scenario) return;
    setSaving(true);
    try {
      await simulationApi.remove(scenario.id);
      addToast("Simulation deleted", "success");
      navigate("/recruiter/simulations");
    } catch {
      addToast("Failed to delete simulation", "error");
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  if (notFound || !scenario) {
    return (
      <div className="py-20 text-center">
        <p className="text-gray-500">Simulation not found.</p>
        <button
          onClick={() => navigate("/recruiter/simulations")}
          className="mt-4 text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          Back to simulations
        </button>
      </div>
    );
  }

  const editable = isSimulationEditable(scenario.status);
  const simulationConfig = scenario.simulation_config;
  const baselineConfigRef: SimulationBaselineConfig = scenario.baseline_config;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{scenario.name}</h1>
            <ScenarioStatusBadge status={scenario.status} />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            {scenario.job_title} · {scenario.company} · created by {scenario.created_by_name} ·
            config v{scenario.config_version}
          </p>
          {scenario.description && (
            <p className="mt-2 max-w-3xl text-sm text-gray-600">{scenario.description}</p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          {canRunSimulation(scenario.status) && !editing && (
            <Button onClick={handleRun} isLoading={running}>
              {activeExecution ? "Run Again" : "Run Simulation"}
            </Button>
          )}
          {scenario.status === "completed" && (
            <Button
              variant="secondary"
              onClick={handleGenerateReport}
              isLoading={generatingReport}
            >
              Generate Report
            </Button>
          )}
          {editable && !editing && (
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit Configuration
            </Button>
          )}
          {editable && (
            <Button variant="danger" onClick={handleDelete} isLoading={saving}>
              Delete
            </Button>
          )}
          {scenario.status === "draft" && !editing && (
            <Button onClick={handleMarkReady} isLoading={saving}>
              Mark Ready
            </Button>
          )}
          {scenario.status === "cancelled" && !editing && (
            <Button
              onClick={() => applyUpdate({ status: "draft" })}
              isLoading={saving}
            >
              Return to Draft
            </Button>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-4 rounded-xl border border-gray-200 bg-white p-5 sm:grid-cols-4">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Config version
          </dt>
          <dd className="mt-1 text-lg font-bold text-gray-900">{scenario.config_version}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Created</dt>
          <dd className="mt-1 text-sm text-gray-900">
            {new Date(scenario.created_at).toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Last update</dt>
          <dd className="mt-1 text-sm text-gray-900">
            {new Date(scenario.updated_at).toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Completed</dt>
          <dd className="mt-1 text-sm text-gray-900">
            {scenario.completed_at ? new Date(scenario.completed_at).toLocaleString() : "—"}
          </dd>
        </div>
      </dl>

      {!editable && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          Scenario configuration is locked in <span className="font-semibold">{scenario.status}</span>.
          You can still run a what-if simulation against the current baseline.
        </div>
      )}

      {baselineConfigRef && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="mt-0.5 text-base leading-none">&#9888;</span>
          <div>
            <p className="font-semibold">Sandbox Scenario</p>
            <p className="mt-0.5 text-xs text-amber-700">
              No changes have been made to the live hiring process. The job &quot;
              {baselineConfigRef.title}&quot; is unaffected — this configuration is purely a
              &quot;what-if&quot;.
            </p>
          </div>
        </div>
      )}

      {editing ? (
        <div className="rounded-xl border border-primary-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Scenario Builder</h2>
              <p className="mt-0.5 text-sm text-gray-500">
                Changes bump the config version and are audited.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button variant="secondary" onClick={handleSaveDraft} isLoading={saving}>
                Save as Draft
              </Button>
              <Button onClick={handleValidateAndPromote} isLoading={saving}>
                Validate &amp; Mark Ready
              </Button>
            </div>
          </div>
          <ValidationPanel validation={draftValidation} />
          {draftConfig ? (
            <div className="mt-4">
              <ScenarioConfiguration value={draftConfig} onChange={setDraftConfig} />
            </div>
          ) : (
            <div className="mt-4">
              <ScenarioConfiguration
                value={createDefaultSimulationConfiguration(
                  scenario.simulation_config?.requirements,
                )}
                onChange={setDraftConfig}
              />
            </div>
          )}
          {liveChanges && (
            <div className="mt-6 border-t border-gray-100 pt-5">
              <ChangesSection changes={liveChanges} title="Review changes vs baseline" />
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-5">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Baseline configuration</h2>
              <p className="mb-3 text-xs text-gray-500">
                Frozen snapshot of the job&apos;s screening setup when the scenario was created.
              </p>
              <SimulationConfigSummary
                config={baselineConfigRef ? simulationConfigFromBaseline(baselineConfigRef) : null}
              />
            </div>
            <div className="rounded-xl border border-primary-200 bg-white p-5">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Simulation configuration</h2>
              <p className="mb-3 text-xs text-gray-500">
                The proposed &quot;what-if&quot; configuration to compare against the baseline.
              </p>
              {simulationConfig ? (
                <SimulationConfigSummary config={simulationConfig} />
              ) : (
                <p className="text-sm text-gray-500">No simulation configuration recorded.</p>
              )}
            </div>
          </div>
          {changes && (
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <ChangesSection changes={changes} title="Changes vs baseline" />
            </div>
          )}
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Run history</h2>
                <p className="mt-0.5 text-sm text-gray-500">
                  Deterministic what-if executions against the current baseline — live hiring data
                  is never modified.
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate(`/recruiter/simulations/${scenario.id}/results`)}
                disabled={!summary}
              >
                View full results
              </Button>
            </div>
            {activeExecution && (
              <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                <LoadingSpinner size="sm" />
                <span className="font-medium">
                  Run {activeExecution.status} ({activeExecution.processed_candidates}/
                  {activeExecution.total_candidates} scored) — results update as candidates are
                  evaluated.
                </span>
                {executions.some((e) => canRunSimulation(e.status)) &&
                  (activeExecution.status === "queued" || activeExecution.status === "running") && (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="ml-auto"
                      onClick={() => handleCancelExecution(activeExecution)}
                      isLoading={saving}
                    >
                      Cancel
                    </Button>
                  )}
              </div>
            )}
            {executions.length === 0 ? (
              <p className="py-6 text-center text-sm text-gray-500">
                No runs yet — hit &quot;Run Simulation&quot; to evaluate current candidates against
                this configuration.
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {executions.map((execution) => (
                  <div
                    key={execution.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-100 bg-gray-50 px-4 py-3"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-900">
                          {execution.status === "completed"
                            ? "Run completed"
                            : `Run ${execution.status}`}
                        </span>
                        <span className="text-sm text-gray-500">
                          {new Date(execution.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="mt-0.5 text-xs text-gray-500">
                        {execution.processed_candidates}/{execution.total_candidates} candidates ·{" "}
                        {execution.progress}%
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {isExecutionActive(execution.status) ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                            execution.status === "completed"
                              ? "bg-green-100 text-green-700"
                              : execution.status === "failed"
                                ? "bg-red-100 text-red-700"
                                : execution.status === "cancelled"
                                  ? "bg-gray-200 text-gray-700"
                                  : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          {execution.status}
                        </span>
                      )}
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/results`)
                  }
                >
                  View full results
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/impact`)
                  }
                >
                  Ranking impact
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/requirement-impact`)
                  }
                >
                  Requirement impact
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/threshold-shortlist`)
                  }
                >
                  Threshold &amp; Shortlist
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/fairness-impact`)
                  }
                >
                  Fairness Impact
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/explainability-impact`)
                  }
                >
                  Explainability Impact
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    navigate(`/recruiter/simulations/${scenario.id}/skill-impact`)
                  }
                >
                  Skill Impact
                </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {summary && (
              <div className="mt-5 border-t border-gray-100 pt-4">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {[
                    {
                      label: "Threshold",
                      value: `${summary.threshold_simulation.toFixed(2)}% (base ${summary.threshold_baseline.toFixed(2)}%)`,
                    },
                    {
                      label: "Shortlist size",
                      value: `${summary.shortlist_simulation} (base ${summary.shortlist_baseline})`,
                    },
                    {
                      label: "Candidates",
                      value: summary.total_candidates,
                    },
                    {
                      label: "Average score",
                      value: (summary.summary as SimulationSummaryAggregate)?.average_score?.simulation?.toFixed(2) ?? "—",
                    },
                  ].map((item) => (
                    <div key={item.label}>
                      <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                        {item.label}
                      </dt>
                      <dd className="mt-1 text-sm font-bold text-gray-900">{item.value}</dd>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}