import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { ScenarioStatusBadge } from "../../components/simulations/ScenarioStatusBadge";
import { SimulationShortlistPanel } from "../../components/simulations/SimulationShortlistPanel";
import { useToast } from "../../contexts/ToastContext";
import { simulationApi } from "../../api/simulations";
import {
  formatScoreDelta,
  isExecutionActive,
  simulationMetricLabel,
  type SimulationChangeFilter,
  type SimulationExecution,
  type SimulationResultItem,
  type SimulationResultsResponse,
  type SimulationResultsSortBy,
  type SimulationScenario,
  type SimulationSummaryResponse,
} from "../../types/simulations";

const PAGE_SIZE = 20;

const CHANGE_FILTER_OPTIONS: { value: "" | SimulationChangeFilter; label: string }[] = [
  { value: "", label: "All candidates" },
  { value: "improved", label: "Improved score" },
  { value: "declined", label: "Declined score" },
  { value: "entered_shortlist", label: "Entered shortlist" },
  { value: "left_shortlist", label: "Left shortlist" },
  { value: "qualified", label: "Qualified (sim)" },
  { value: "disqualified", label: "Disqualified (sim)" },
];

const SORT_OPTIONS: { value: SimulationResultsSortBy; label: string }[] = [
  { value: "simulation_rank", label: "Simulation rank" },
  { value: "baseline_rank", label: "Baseline rank" },
  { value: "score_change", label: "Score change" },
  { value: "rank_change", label: "Rank change" },
];

function statusChip(status: string) {
  // Spec badge tokens (badge-* variants from the design system).
  const palette: Record<string, string> = {
    qualified: "badge-success",
    not_qualified: "badge-danger",
    shortlisted: "badge-info",
    not_shortlisted: "badge-neutral",
  };
  return (
    <span className={`badge ${palette[status] ?? "badge-neutral"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function ResultRow({ row }: { row: SimulationResultItem }) {
  return (
    <tr>
      <td className="whitespace-nowrap font-medium text-gray-900">
        #{row.simulation_rank}
        <span className="ml-2 text-xs text-gray-400">base #{row.baseline_rank}</span>
      </td>
      <td className="whitespace-nowrap text-gray-900">{row.candidate_name}</td>
      <td className="whitespace-nowrap text-gray-500">{row.baseline_score}</td>
      <td className="whitespace-nowrap font-semibold text-gray-900">
        {row.simulation_score}
      </td>
      <td
        className={`whitespace-nowrap font-medium ${
          row.score_change > 0
            ? "text-emerald-600"
            : row.score_change < 0
              ? "text-red-600"
              : "text-gray-500"
        }`}
      >
        {formatScoreDelta(row.score_change)}
      </td>
      <td
        className={`whitespace-nowrap font-medium ${
          row.rank_change > 0
            ? "text-emerald-600"
            : row.rank_change < 0
              ? "text-red-600"
              : "text-gray-500"
        }`}
      >
        {row.rank_change > 0 ? `+${row.rank_change}` : row.rank_change}
      </td>
      <td className="whitespace-nowrap">{statusChip(row.simulation_status)}</td>
      <td className="whitespace-nowrap">
        {statusChip(row.simulation_shortlisted ? "shortlisted" : "not_shortlisted")}
      </td>
      <td className="max-w-[18rem] truncate text-xs text-gray-500" title={row.reason ?? ""}>
        {row.reason ?? "—"}
      </td>
    </tr>
  );
}

function SummaryCard({
  label,
  baseline,
  simulation,
  deltaLabel,
}: {
  label: string;
  baseline: string | number;
  simulation: string | number;
  deltaLabel: string;
}) {
  return (
    <div className="card p-4">
      <p className="section-label">{label}</p>
      <div className="mt-2 flex items-end justify-between">
        <div className="text-sm text-gray-600">
          Baseline <span className="font-semibold text-gray-900">{baseline}</span>
        </div>
        <div className="text-right">
          <div className="font-display text-lg font-bold text-gray-900">{simulation}</div>
          <div className="text-xs font-semibold text-primary-600">{deltaLabel}</div>
        </div>
      </div>
    </div>
  );
}

export function SimulationResults() {
  const { simulationId } = useParams<{ simulationId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();

  const [scenario, setScenario] = useState<SimulationScenario | null>(null);
  const [executions, setExecutions] = useState<SimulationExecution[]>([]);
  const [summary, setSummary] = useState<SimulationSummaryResponse | null>(null);
  const [results, setResults] = useState<SimulationResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SimulationResultsSortBy>("simulation_rank");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [changeFilter, setChangeFilter] = useState<"" | SimulationChangeFilter>("");

  const selectedExecutionId = searchParams.get("execution_id");

  const latestCompleted = useMemo<SimulationExecution | null>(
    () =>
      executions.filter((e) => e.status === "completed").sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ??
      null,
    [executions],
  );

  const activeExecution = useMemo<SimulationExecution | null>(
    () => executions.find((e) => isExecutionActive(e.status)) ?? null,
    [executions],
  );

  const loadScenario = useCallback(async () => {
    if (!simulationId) return;
    try {
      const data = await simulationApi.get(simulationId);
      setScenario(data);
    } catch {
      setNotFound(true);
    }
  }, [simulationId]);

  const loadExecutions = useCallback(async () => {
    if (!simulationId) return;
    const data = await simulationApi.listExecutions(simulationId);
    setExecutions(data.items);
    return data.items;
  }, [simulationId]);

  const loadSummary = useCallback(
    async (executionId: string | null) => {
      if (!simulationId) return;
      const data = await simulationApi.getSummary(simulationId, executionId ?? undefined);
      setSummary(data);
    },
    [simulationId],
  );

  const loadResults = useCallback(async () => {
    if (!simulationId) return;
    const data = await simulationApi.listResults(simulationId, {
      execution_id: selectedExecutionId ?? undefined,
      page,
      page_size: PAGE_SIZE,
      sort_by: sortBy,
      order,
      change_filter: changeFilter === "" ? undefined : changeFilter,
    });
    setResults(data);
  }, [simulationId, selectedExecutionId, page, sortBy, order, changeFilter]);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    (async () => {
      try {
        await Promise.all([loadScenario(), loadExecutions()]);
      } catch {
        addToast("Failed to load simulation results", "error");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadScenario, loadExecutions, addToast]);

  useEffect(() => {
    if (!simulationId) return;
    void loadSummary(selectedExecutionId);
    void loadResults();
  }, [simulationId, selectedExecutionId, page, sortBy, order, changeFilter, loadSummary, loadResults]);

  // Poll while an execution is queued/running so the page self-refreshes.
  useEffect(() => {
    if (!simulationId || !activeExecution) return;
    const timer = setInterval(async () => {
      try {
        const items = await loadExecutions();
        if (!items?.some((e) => isExecutionActive(e.status))) {
          void loadSummary(selectedExecutionId);
          void loadResults();
        }
      } catch {
        // Keep the current view; the next poll retries.
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [simulationId, activeExecution, loadExecutions, loadSummary, loadResults, selectedExecutionId]);

  function selectExecution(executionId: string) {
    setSearchParams({ execution_id: executionId });
    setPage(1);
  }

  function resetExecutionSelection() {
    searchParams.delete("execution_id");
    setSearchParams(searchParams);
    setPage(1);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <div className="skeleton h-8 w-64" />
          <div className="skeleton h-4 w-48" />
        </div>
        <div className="skeleton h-16 w-full" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-24 w-full" />
          ))}
        </div>
        <div className="skeleton h-72 w-full" />
      </div>
    );
  }

  if (notFound || !scenario) {
    return (
      <div className="empty-state">
        <p className="text-sm text-gray-500">Simulation not found.</p>
        <Link
          to="/recruiter/simulations"
          className="mt-4 inline-block text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          Back to simulations
        </Link>
      </div>
    );
  }

  const selectedExecution =
    executions.find((e) => e.id === selectedExecutionId) ?? (selectedExecutionId ? null : latestCompleted);
  const activeId = activeExecution?.id ?? null;

  return (
    <div className="space-y-6">
      <div className="page-header">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="page-title">{scenario.name} — Results</h1>
            {selectedExecution && <ScenarioStatusBadge status={selectedExecution.status} />}
          </div>
          <p className="page-subtitle">
            {scenario.job_title} · {scenario.company}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {selectedExecutionId && (
            <Button variant="ghost" size="sm" onClick={resetExecutionSelection}>
              Latest run
            </Button>
          )}
          <Link
            to={`/recruiter/simulations/${scenario.id}/impact`}
            className="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            Ranking impact
          </Link>
          <Link
            to={`/recruiter/simulations/${scenario.id}`}
            className="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            Back to scenario
          </Link>
        </div>
      </div>

      <div className="info-banner">
        <span className="font-semibold">What-if analysis.</span> These scores rank candidates under a
        hypothetical configuration. No live hiring data (job, applications, rankings) was created or
        modified by this run — results are stored separately as simulation records.
      </div>

      <SimulationShortlistPanel
        simulationId={scenario.id}
        executionId={
          selectedExecution?.id ?? latestCompleted?.id ?? ""
        }
        hasResults={
          Boolean(results && results.total > 0) &&
          selectedExecution?.status === "completed"
        }
      />

      {activeExecution && (
        <div className="flex items-start gap-2.5 rounded-xl border border-violet-200/70 bg-violet-50/70 px-4 py-3 text-sm font-medium text-violet-700 shadow-xs">
          Run in progress — {activeExecution.progress}% ({activeExecution.processed_candidates}/
          {activeExecution.total_candidates} candidates).
        </div>
      )}

      {executions.length > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-sm text-gray-500">Execution:</span>
          <select
            value={selectedExecution?.id ?? ""}
            onChange={(e) => selectExecution(e.target.value)}
            className="field w-auto py-2"
          >
            <option value="" disabled>
              Select an execution
            </option>
            {executions
              .slice()
              .sort((a, b) => b.created_at.localeCompare(a.created_at))
              .map((execution) => (
                <option key={execution.id} value={execution.id}>
                  {new Date(execution.created_at).toLocaleString()} · {execution.status} ·{" "}
                  {execution.total_candidates} candidates
                </option>
              ))}
          </select>
        </div>
      )}

      {summary && summary.status === "no_execution" ? (
        <div className="empty-state">
          <p className="text-sm text-gray-500">No simulation has been run yet.</p>
          <Link
            to={`/recruiter/simulations/${scenario.id}`}
            className="mt-3 inline-block text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            Run this simulation from the scenario page
          </Link>
        </div>
      ) : summary && selectedExecution ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <SummaryCard
              label="Pass threshold"
              baseline={`${summary.threshold_baseline}%`}
              simulation={`${summary.threshold_simulation}%`}
              deltaLabel={`${formatScoreDelta(summary.threshold_simulation - summary.threshold_baseline)} pts`}
            />
            <SummaryCard
              label="Shortlist size"
              baseline={summary.shortlist_baseline}
              simulation={summary.shortlist_simulation}
              deltaLabel={`${formatScoreDelta(summary.shortlist_simulation - summary.shortlist_baseline)}`}
            />
            <SummaryCard
              label="Candidates evaluated"
              baseline={summary.total_candidates}
              simulation={summary.total_candidates}
              deltaLabel={`${summary.processed_candidates} processed`}
            />
            <SummaryCard
              label="Avg score"
              baseline={summary.summary.average_score?.baseline ?? 0}
              simulation={summary.summary.average_score?.simulation ?? 0}
              deltaLabel={`${formatScoreDelta(summary.summary.average_score?.change ?? 0)} pts`}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="card p-5 lg:col-span-2">
              <h2 className="section-title">Impact metrics</h2>
              <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {summary.metrics.length === 0 ? (
                  <p className="text-sm text-gray-500">No impact metrics recorded for this run.</p>
                ) : (
                  summary.metrics.map((metric) => (
                    <div
                      key={metric.metric}
                      className="rounded-lg border border-gray-100 bg-gray-50/70 px-3 py-2"
                    >
                      <dt className="section-label">
                        {simulationMetricLabel(metric.metric)}
                      </dt>
                      <dd className="mt-1 flex items-baseline gap-2 text-sm">
                        <span className="text-gray-500">
                          {metric.metric.includes("score") && metric.metric !== "average_score"
                            ? metric.simulation_value.toFixed(0)
                            : metric.simulation_value}
                        </span>
                        <span className="text-xs text-gray-400">
                          baseline {metric.baseline_value}
                        </span>
                        <span
                          className={`text-xs font-semibold ${
                            metric.change_value > 0
                              ? "text-emerald-600"
                              : metric.change_value < 0
                                ? "text-red-600"
                                : "text-gray-400"
                          }`}
                        >
                          {formatScoreDelta(metric.change_value)}
                        </span>
                      </dd>
                    </div>
                  ))
                )}
              </dl>
            </div>

            <div className="card p-5">
              <h2 className="section-title">Pool movement</h2>
              <dl className="mt-3 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="text-gray-600">Qualified (baseline → simulation)</dt>
                  <dd className="font-semibold text-gray-900">
                    {summary.summary.qualified?.baseline ?? 0} →{" "}
                    {summary.summary.qualified?.simulation ?? 0}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-gray-600">Shortlisted</dt>
                  <dd className="font-semibold text-gray-900">
                    {summary.summary.shortlisted?.baseline ?? 0} →{" "}
                    {summary.summary.shortlisted?.simulation ?? 0}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-gray-600">Entered shortlist</dt>
                  <dd className="font-semibold text-emerald-600">
                    {summary.summary.pool_movement?.entered_shortlist ?? 0}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-gray-600">Left shortlist</dt>
                  <dd className="font-semibold text-red-600">
                    {summary.summary.pool_movement?.left_shortlist ?? 0}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-gray-600">Improved / declined</dt>
                  <dd className="font-semibold text-gray-900">
                    {summary.summary.score_movement?.improved ?? 0} /{" "}
                    {summary.summary.score_movement?.declined ?? 0}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-gray-600">Top candidate</dt>
                  <dd className="font-semibold text-gray-900">
                    {summary.summary.simulation_top_candidate ?? "—"}
                  </dd>
                </div>
              </dl>
            </div>
          </div>

          {summary.major_movements.length > 0 && (
            <div className="card p-5">
              <h2 className="section-title">Major movers</h2>
              <div className="mt-3 flex flex-col gap-2">
                {summary.major_movements.map((row) => (
                  <div
                    key={row.candidate_id}
                    className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50/70 px-3 py-2 text-sm"
                  >
                    <span className="font-medium text-gray-900">{row.candidate_name}</span>
                    <span className="text-gray-500">
                      {row.baseline_score} → {row.simulation_score}{" "}
                      <span
                        className={`font-semibold ${
                          row.score_change > 0 ? "text-emerald-600" : "text-red-600"
                        }`}
                      >
                        ({formatScoreDelta(row.score_change)})
                      </span>
                    </span>
                    {row.reason && (
                      <span className="max-w-[24rem] truncate text-xs text-gray-500" title={row.reason}>
                        {row.reason}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card overflow-hidden p-0">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4">
              <div>
                <h2 className="section-title">Candidate results</h2>
                <p className="mt-0.5 text-xs text-gray-500">
                  {results ? `${results.total} candidates · page ${results.page}` : "Loading…"}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={changeFilter}
                  onChange={(e) => {
                    setChangeFilter(e.target.value as "" | SimulationChangeFilter);
                    setPage(1);
                  }}
                  aria-label="Filter by change"
                  className="field w-auto py-2"
                >
                  {CHANGE_FILTER_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <select
                  value={sortBy}
                  onChange={(e) => {
                    setSortBy(e.target.value as SimulationResultsSortBy);
                    setPage(1);
                  }}
                  aria-label="Sort results by"
                  className="field w-auto py-2"
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      Sort: {option.label}
                    </option>
                  ))}
                </select>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
                    setPage(1);
                  }}
                >
                  {order === "asc" ? "Asc" : "Desc"}
                </Button>
              </div>
            </div>

            {results && results.items.length > 0 ? (
              <div className="table-wrap rounded-none border-0 shadow-none">
                <table className="data-table">
                  <thead>
                    <tr>
                      {["Rank", "Candidate", "Base score", "Sim score", "Δ score", "Δ rank", "Status", "Shortlist", "Why"].map(
                        (header) => (
                          <th key={header} className="whitespace-nowrap">
                            {header}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {results.items.map((row) => (
                      <ResultRow key={row.candidate_id} row={row} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state my-4">
                <p className="text-sm text-gray-500">
                  {results && results.total === 0
                    ? "No results for this run."
                    : "No candidates match the current filter."}
                </p>
              </div>
            )}

            {results && results.total > 0 && (
              <div className="flex items-center justify-between border-t border-gray-100 px-5 py-3">
                <span className="text-xs text-gray-500">
                  Showing {(results.page - 1) * PAGE_SIZE + 1}–
                  {Math.min(results.page * PAGE_SIZE, results.total)} of {results.total}
                </span>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" disabled={results.page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={results.page * PAGE_SIZE >= results.total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        </>
      ) : null}

      {activeId && <p className="text-xs text-gray-400">Polling active execution #{activeId}…</p>}
    </div>
  );
}