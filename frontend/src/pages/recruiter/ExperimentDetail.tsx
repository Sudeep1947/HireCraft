import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { Button } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { experimentApi } from "../../api/experiments";
import type {
  ExperimentResponse,
  SensitivityAnalysisResponse,
  RobustnessAnalysisResponse,
  StabilityAnalysisResponse,
  CandidateStabilityMetrics,
} from "../../types/simulationExperiments";
import {
  EXPERIMENT_TYPE_LABELS,
  STATUS_COLORS,
  SENSITIVITY_DIMENSION_LABELS,
} from "../../types/simulationExperiments";

type Tab =
  | "overview"
  | "sensitivity"
  | "robustness"
  | "stability"
  | "fairness"
  | "candidates"
  | "reproducibility";

export function ExperimentDetail() {
  const { experimentId } = useParams<{ experimentId: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [experiment, setExperiment] = useState<ExperimentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [executing, setExecuting] = useState(false);
  const [sensitivity, setSensitivity] = useState<SensitivityAnalysisResponse | null>(null);
  const [robustness, setRobustness] = useState<RobustnessAnalysisResponse | null>(null);
  const [stability, setStability] = useState<StabilityAnalysisResponse | null>(null);

  const fetchExperiment = useCallback(async () => {
    if (!experimentId) return;
    setLoading(true);
    try {
      const data = await experimentApi.get(experimentId);
      setExperiment(data);
    } catch {
      addToast("Failed to load experiment", "error");
    } finally {
      setLoading(false);
    }
  }, [experimentId, addToast]);

  useEffect(() => {
    fetchExperiment();
  }, [fetchExperiment]);

  const loadAnalysis = useCallback(async () => {
    if (!experimentId || !experiment) return;
    if (experiment.status !== "completed") return;
    try {
      const [s, r, st] = await Promise.all([
        experimentApi.getSensitivity(experimentId),
        experimentApi.getRobustness(experimentId),
        experimentApi.getStability(experimentId),
      ]);
      setSensitivity(s);
      setRobustness(r);
      setStability(st);
    } catch {
      // Analysis endpoints may return partial data
    }
  }, [experimentId, experiment]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis]);

  async function handleExecute() {
    if (!experimentId) return;
    setExecuting(true);
    try {
      await experimentApi.execute(experimentId);
      addToast("Experiment queued for execution", "success");
      await fetchExperiment();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to execute experiment";
      addToast(msg, "error");
    } finally {
      setExecuting(false);
    }
  }

  async function handleCancel() {
    if (!experimentId) return;
    try {
      await experimentApi.cancel(experimentId);
      addToast("Experiment cancelled", "success");
      await fetchExperiment();
    } catch {
      addToast("Failed to cancel experiment", "error");
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 animate-fade-up">
        <div className="skeleton h-8 w-64" />
        <div className="skeleton h-4 w-48" />
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }
  if (!experiment)
    return (
      <div className="empty-state animate-fade-up">
        <p className="text-sm text-gray-500">Experiment not found.</p>
      </div>
    );

  const progress = experiment.total_configurations
    ? Math.round(
        (experiment.completed_configurations / experiment.total_configurations) * 100,
      )
    : 0;

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "sensitivity", label: "Sensitivity" },
    { key: "robustness", label: "Robustness" },
    { key: "stability", label: "Stability" },
    { key: "fairness", label: "Fairness" },
    { key: "candidates", label: "Candidates" },
    { key: "reproducibility", label: "Reproducibility" },
  ];

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <button
          className="mb-2 text-sm font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
          onClick={() => navigate("/simulations/research")}
        >
          ← Back to Research
        </button>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="page-title">{experiment.name}</h1>
              <span
                className={`badge ${
                  STATUS_COLORS[experiment.status] || "bg-gray-100 text-gray-700"
                }`}
              >
                {experiment.status}
              </span>
            </div>
            <p className="page-subtitle">
              {EXPERIMENT_TYPE_LABELS[experiment.experiment_type] ||
                experiment.experiment_type}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {experiment.status === "draft" && (
              <Button onClick={handleExecute} isLoading={executing}>
                Execute Experiment
              </Button>
            )}
            {(experiment.status === "running" || experiment.status === "queued") && (
              <Button variant="secondary" onClick={handleCancel}>
                Cancel
              </Button>
            )}
            {experiment.status === "completed" && (
              <Button onClick={() => navigate(`/simulations/reports`)}>
                Generate Report
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-800 shadow-xs">
        <strong>Advanced What-if Analysis:</strong> This experiment evaluates
        hypothetical configurations. It does not modify live hiring data.
      </div>

      {/* Progress bar */}
      {experiment.status === "running" && (
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-gray-600">
              Configurations: {experiment.completed_configurations} /{" "}
              {experiment.total_configurations}
            </span>
            <span className="text-gray-500">{progress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-primary-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Sidebar Tabs */}
        <nav className="w-full flex-shrink-0 lg:w-48" aria-label="Experiment sections">
          <ul className="flex gap-1 overflow-x-auto lg:block lg:space-y-1 lg:overflow-visible">
            {tabs.map((t) => (
              <li key={t.key} className="shrink-0">
                <button
                  onClick={() => setActiveTab(t.key)}
                  aria-current={activeTab === t.key ? "page" : undefined}
                  className={`nav-link block w-full text-left ${
                    activeTab === t.key ? "nav-link-active" : ""
                  }`}
                >
                  {t.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Content */}
        <div className="min-w-0 flex-1 space-y-6">
          {/* Overview */}
          {activeTab === "overview" && (
            <>
              <SectionCard title="Experiment Information">
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <InfoItem label="Name" value={experiment.name} />
                  <InfoItem label="Type" value={EXPERIMENT_TYPE_LABELS[experiment.experiment_type] || experiment.experiment_type} />
                  <InfoItem label="Status" value={experiment.status} />
                  <InfoItem label="Configurations" value={`${experiment.completed_configurations} / ${experiment.total_configurations}`} />
                  {experiment.failed_configurations > 0 && (
                    <InfoItem label="Failed" value={String(experiment.failed_configurations)} />
                  )}
                  <InfoItem label="Created" value={new Date(experiment.created_at).toLocaleString()} />
                  {experiment.completed_at && (
                    <InfoItem label="Completed" value={new Date(experiment.completed_at).toLocaleString()} />
                  )}
                </dl>
                {experiment.description && (
                  <p className="mt-3 text-sm text-gray-600">{experiment.description}</p>
                )}
              </SectionCard>

              {experiment.research_question && (
                <SectionCard title="Research Question">
                  <p className="text-sm text-gray-700">{experiment.research_question}</p>
                </SectionCard>
              )}

              {experiment.hypothesis && (
                <SectionCard title="Hypothesis">
                  <p className="text-sm text-gray-700">{experiment.hypothesis}</p>
                </SectionCard>
              )}

              <SectionCard title="Parameter Space">
                <div className="space-y-2">
                  {Object.entries(experiment.parameter_ranges).map(([dim, data]) => (
                    <div key={dim} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">
                        {SENSITIVITY_DIMENSION_LABELS[dim] || dim}
                      </span>
                      <span className="font-medium text-gray-900">
                        {(data as { values?: unknown[]; count?: number }).values?.join(", ") ||
                          `${(data as { count?: number }).count} values`}
                      </span>
                    </div>
                  ))}
                </div>
              </SectionCard>

              {experiment.error_message && (
                <SectionCard title="Error">
                  <p className="text-sm text-red-600">{experiment.error_message}</p>
                </SectionCard>
              )}
            </>
          )}

          {/* Sensitivity */}
          {activeTab === "sensitivity" && (
            <>
              {sensitivity ? (
                <>
                  <SectionCard title="Sensitivity Analysis">
                    <div className="mb-4 text-sm text-gray-500">
                      Analyzes how metrics change across parameter values.
                    </div>
                    {sensitivity.curves.length === 0 ? (
                      <p className="text-sm text-gray-500">
                        No sensitivity data available. Complete the experiment first.
                      </p>
                    ) : (
                      <div className="space-y-4">
                        {sensitivity.curves.map((curve) => (
                          <div key={curve.dimension} className="rounded-xl border border-gray-200/70 bg-gray-50/60 p-4">
                            <div className="mb-2 flex items-center justify-between">
                              <span className="text-sm font-medium text-gray-900">
                                {SENSITIVITY_DIMENSION_LABELS[curve.dimension] || curve.dimension}
                              </span>
                              <span
                                className={`text-xs font-medium ${
                                  curve.direction === "increasing"
                                    ? "text-emerald-600"
                                    : curve.direction === "decreasing"
                                      ? "text-red-600"
                                      : "text-gray-500"
                                }`}
                              >
                                {curve.direction}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <span>Range: {curve.min_value} — {curve.max_value}</span>
                              <span>Spread: {curve.range_spread}</span>
                              <span>{curve.points.length} data points</span>
                            </div>
                            <div className="mt-2 flex gap-1">
                              {curve.points.map((pt, i) => (
                                <div
                                  key={i}
                                  className="flex-1 rounded bg-primary-100"
                                  style={{
                                    height: `${Math.max(4, (pt.metric_value / Math.max(curve.max_value, 1)) * 40)}px`,
                                  }}
                                  title={`${pt.parameter_value} → ${pt.metric_value}`}
                                />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </SectionCard>
                </>
              ) : (
                <SectionCard title="Sensitivity Analysis">
                  <LoadingSpinner size="sm" />
                </SectionCard>
              )}
            </>
          )}

          {/* Robustness */}
          {activeTab === "robustness" && (
            <>
              {robustness ? (
                <>
                  <SectionCard title="Robustness Profile">
                    <div className="mb-4 text-sm text-gray-500">
                      Shows how outcomes vary under controlled perturbations.
                    </div>
                    {robustness.profiles.length === 0 ? (
                      <p className="text-sm text-gray-500">
                        No robustness data available.
                      </p>
                    ) : (
                      <div className="table-wrap rounded-none border-0 shadow-none">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Parameter</th>
                              <th>Range Tested</th>
                              <th className="text-right">Rank Variation</th>
                              <th className="text-right">Shortlist Variation</th>
                            </tr>
                          </thead>
                          <tbody>
                            {robustness.profiles.map((p) => (
                              <tr key={p.parameter}>
                                <td className="font-medium text-gray-900">
                                  {SENSITIVITY_DIMENSION_LABELS[p.parameter] || p.parameter}
                                </td>
                                <td className="text-gray-600">{p.range_tested}</td>
                                <td className="text-right">{p.rank_variation}</td>
                                <td className="text-right">{p.shortlist_variation}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </SectionCard>
                </>
              ) : (
                <SectionCard title="Robustness Analysis">
                  <LoadingSpinner size="sm" />
                </SectionCard>
              )}
            </>
          )}

          {/* Stability */}
          {activeTab === "stability" && (
            <>
              {stability ? (
                <>
                  <SectionCard title="Ranking Stability">
                    <div className="text-sm">
                      <div className="mb-2 flex items-center gap-2">
                        <span className="text-gray-500">Level:</span>
                        <span
                          className={`font-medium ${
                            stability.ranking_stability.stability_level === "high"
                              ? "text-emerald-600"
                              : stability.ranking_stability.stability_level === "moderate"
                                ? "text-amber-600"
                                : "text-red-600"
                          }`}
                        >
                          {String(stability.ranking_stability.stability_level || "N/A")}
                        </span>
                      </div>
                      {stability.ranking_stability.avg_rank_variance !== undefined && (
                        <p className="text-gray-600">
                          Average rank variance:{" "}
                          {String(stability.ranking_stability.avg_rank_variance)}
                        </p>
                      )}
                    </div>
                  </SectionCard>

                  <SectionCard title="Shortlist Stability">
                    <div className="text-sm">
                      <div className="mb-2 flex items-center gap-2">
                        <span className="text-gray-500">Level:</span>
                        <span
                          className={`font-medium ${
                            stability.shortlist_stability.stability_level === "high"
                              ? "text-emerald-600"
                              : stability.shortlist_stability.stability_level === "moderate"
                                ? "text-amber-600"
                                : "text-red-600"
                          }`}
                        >
                          {String(stability.shortlist_stability.stability_level || "N/A")}
                        </span>
                      </div>
                      {stability.shortlist_stability.avg_jaccard_similarity !== undefined && (
                        <p className="text-gray-600">
                          Average Jaccard similarity:{" "}
                          {String(stability.shortlist_stability.avg_jaccard_similarity)}
                        </p>
                      )}
                    </div>
                  </SectionCard>
                </>
              ) : (
                <SectionCard title="Stability Analysis">
                  <LoadingSpinner size="sm" />
                </SectionCard>
              )}
            </>
          )}

          {/* Fairness */}
          {activeTab === "fairness" && (
            <SectionCard title="Fairness Sensitivity">
              <p className="text-sm text-gray-500">
                Fairness metric sensitivity is computed when demographic data is
                available in the simulation results.
              </p>
            </SectionCard>
          )}

          {/* Candidates */}
          {activeTab === "candidates" && (
            <SectionCard title="Candidate Stability">
              {stability?.candidate_stability &&
              stability.candidate_stability.length > 0 ? (
                <div className="table-wrap rounded-none border-0 shadow-none">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Candidate</th>
                        <th className="text-right">Appearance</th>
                        <th className="text-right">Shortlist Freq</th>
                        <th className="text-right">Rank Range</th>
                        <th className="text-right">Rank Variance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stability.candidate_stability
                        .slice(0, 20)
                        .map((c: CandidateStabilityMetrics) => (
                          <tr key={c.candidate_id}>
                            <td className="font-medium text-gray-900">
                              {c.candidate_name}
                            </td>
                            <td className="text-right text-gray-600">
                              {(c.appearance_frequency * 100).toFixed(0)}%
                            </td>
                            <td className="text-right text-gray-600">
                              {(c.shortlist_frequency * 100).toFixed(0)}%
                            </td>
                            <td className="text-right text-gray-600">
                              {c.rank_range_min}–{c.rank_range_max}
                            </td>
                            <td className="text-right">{c.rank_variance}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No candidate stability data available.
                </p>
              )}
            </SectionCard>
          )}

          {/* Reproducibility */}
          {activeTab === "reproducibility" && (
            <SectionCard title="Reproducibility Metadata">
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <InfoItem label="Experiment Version" value={experiment.experiment_version} />
                <InfoItem label="Random Seed" value={experiment.random_seed != null ? String(experiment.random_seed) : "None (deterministic)"} />
                <InfoItem label="Base Scenario ID" value={experiment.base_scenario_id} />
                <InfoItem label="Job ID" value={experiment.job_id} />
                <InfoItem label="Total Configurations" value={String(experiment.total_configurations)} />
                <InfoItem label="Created At" value={new Date(experiment.created_at).toISOString()} />
              </dl>
              <div className="mt-4 rounded-xl bg-gray-50/80 p-3 text-xs leading-relaxed text-gray-600">
                <strong>Methodology:</strong> This experiment generates
                hypothetical simulation configurations by varying the specified
                parameters around the base scenario. Each configuration is
                evaluated using the existing simulation engine. All results
                describe observed simulation outputs and do not establish
                causal relationships or statistical significance.
              </div>
            </SectionCard>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card p-6">
      <h3 className="section-title mb-4">{title}</h3>
      {children}
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-900">{value}</dd>
    </div>
  );
}
