import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FlaskConical } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { experimentApi } from "../../api/experiments";
import { simulationApi } from "../../api/simulations";
import type { SimulationScenarioListItem } from "../../types/simulations";
import type {
  ExperimentType,
  ParameterRange,
} from "../../types/simulationExperiments";
import {
  SENSITIVITY_DIMENSION_LABELS,
} from "../../types/simulationExperiments";

const EXPERIMENT_TYPES: { value: ExperimentType; label: string; description: string }[] = [
  { value: "threshold_sweep", label: "Threshold Sweep", description: "Test how qualification changes across threshold values" },
  { value: "weight_sweep", label: "Weight Sweep", description: "Test how rankings change as scoring weights vary" },
  { value: "shortlist_sweep", label: "Shortlist Sweep", description: "Test how shortlists change across shortlist sizes" },
  { value: "one_parameter_sensitivity", label: "One-Parameter Sensitivity", description: "Analyze sensitivity to a single parameter" },
  { value: "multi_parameter_sensitivity", label: "Multi-Parameter Sensitivity", description: "Analyze sensitivity across multiple parameters" },
  { value: "robustness_test", label: "Robustness Test", description: "Test strategy stability under perturbations" },
  { value: "fairness_sensitivity", label: "Fairness Sensitivity", description: "Analyze fairness metric changes across configurations" },
  { value: "ranking_stability", label: "Ranking Stability", description: "Analyze candidate ranking stability" },
];

function getDefaultRanges(type: ExperimentType): ParameterRange[] {
  switch (type) {
    case "threshold_sweep":
      return [{ dimension: "threshold", start: 65, end: 85, step: 5 }];
    case "weight_sweep":
      return [{ dimension: "experience_weight", start: 0.15, end: 0.45, step: 0.05 }];
    case "shortlist_sweep":
      return [{ dimension: "shortlist_size", start: 5, end: 25, step: 5 }];
    case "robustness_test":
      return [
        { dimension: "threshold", start: 65, end: 80, step: 5 },
        { dimension: "experience_weight", start: 0.20, end: 0.35, step: 0.05 },
      ];
    case "multi_parameter_sensitivity":
      return [
        { dimension: "threshold", start: 65, end: 80, step: 5 },
        { dimension: "experience_weight", start: 0.20, end: 0.35, step: 0.05 },
      ];
    default:
      return [{ dimension: "threshold", start: 65, end: 85, step: 5 }];
  }
}

export function CreateExperiment() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [scenarios, setScenarios] = useState<SimulationScenarioListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [researchQuestion, setResearchQuestion] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [experimentType, setExperimentType] = useState<ExperimentType>("threshold_sweep");
  const [parameterRanges, setParameterRanges] = useState<ParameterRange[]>([]);
  const [maxConfigs, setMaxConfigs] = useState(20);

  useEffect(() => {
    simulationApi
      .list()
      .then((res) => {
        const completed = (res.items || []).filter(
          (s: SimulationScenarioListItem) => s.status === "completed" || s.status === "ready",
        );
        setScenarios(completed);
      })
      .catch(() => addToast("Failed to load scenarios", "error"))
      .finally(() => setLoading(false));
  }, [addToast]);

  useEffect(() => {
    setParameterRanges(getDefaultRanges(experimentType));
  }, [experimentType]);

  const estimateCount = useCallback(() => {
    let total = 1;
    for (const pr of parameterRanges) {
      if (pr.values) {
        total *= pr.values.length;
      } else if (pr.start !== undefined && pr.end !== undefined && pr.step !== undefined && pr.step > 0) {
        total *= Math.floor((pr.end - pr.start) / pr.step) + 1;
      }
    }
    return total;
  }, [parameterRanges]);

  const handleCreate = async () => {
    if (!name.trim() || !selectedScenarioId) return;
    setCreating(true);
    try {
      const experiment = await experimentApi.create({
        name: name.trim(),
        description: description.trim() || undefined,
        research_question: researchQuestion.trim() || undefined,
        hypothesis: hypothesis.trim() || undefined,
        base_scenario_id: selectedScenarioId,
        experiment_type: experimentType,
        parameter_ranges: parameterRanges,
        max_configurations: maxConfigs,
      });
      addToast("Experiment created", "success");
      navigate(`/simulations/research/${experiment.id}`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to create experiment";
      addToast(msg, "error");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4 animate-fade-up">
        <div className="skeleton h-8 w-56" />
        <div className="skeleton h-64 w-full" />
        <div className="skeleton h-48 w-full" />
      </div>
    );
  }

  const estimated = estimateCount();

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <button
          className="mb-2 text-sm font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
          onClick={() => navigate("/simulations/research")}
        >
          ← Back to Research
        </button>
        <h1 className="page-title">New Experiment</h1>
        <p className="page-subtitle">
          Define a controlled parameter experiment over simulation
          configurations.
        </p>
      </div>

      <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-800 shadow-xs">
        <strong>Advanced What-if Analysis:</strong> This experiment evaluates
        hypothetical configurations. It does not modify live hiring data.
      </div>

      {/* Experiment Information */}
      <section className="card p-6">
        <h2 className="section-title mb-4">
          Experiment Information
        </h2>
        <div className="space-y-4">
          <div>
            <label className="field-label">Name *</label>
            <input
              type="text"
              className="field"
              placeholder="e.g., Threshold Sensitivity Analysis"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Description</label>
            <textarea
              rows={2}
              className="field"
              placeholder="What does this experiment investigate?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Research Question</label>
            <input
              type="text"
              className="field"
              placeholder="e.g., How sensitive is candidate ranking to threshold changes?"
              value={researchQuestion}
              onChange={(e) => setResearchQuestion(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Hypothesis (optional)</label>
            <textarea
              rows={2}
              className="field"
              placeholder="What do you expect to observe?"
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
            />
          </div>
        </div>
      </section>

      {/* Base Scenario */}
      <section className="card p-6">
        <h2 className="section-title mb-4">Base Scenario</h2>
        <select
          className="field"
          value={selectedScenarioId}
          onChange={(e) => setSelectedScenarioId(e.target.value)}
        >
          <option value="">Select a completed scenario...</option>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — {s.job_title}
            </option>
          ))}
        </select>
      </section>

      {/* Experiment Type */}
      <section className="card p-6">
        <h2 className="section-title mb-4">Experiment Type</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {EXPERIMENT_TYPES.map((t) => (
            <button
              key={t.value}
              className={`rounded-xl border p-3 text-left transition-all duration-200 focus-visible:ring-2 focus-visible:ring-primary-500/60 focus-visible:outline-none ${
                experimentType === t.value
                  ? "border-primary-400 bg-primary-50/70 shadow-glow-sm"
                  : "border-gray-200 bg-white/70 hover:border-primary-300 hover:bg-white"
              }`}
              onClick={() => setExperimentType(t.value)}
            >
              <div className="text-sm font-medium text-gray-900">{t.label}</div>
              <div className="mt-1 text-xs text-gray-500">{t.description}</div>
            </button>
          ))}
        </div>
      </section>

      {/* Parameter Configuration */}
      <section className="card p-6">
        <h2 className="section-title mb-4">
          Parameter Configuration
        </h2>
        <div className="space-y-4">
          {parameterRanges.map((pr, idx) => (
            <div key={idx} className="rounded-xl border border-gray-200/70 bg-gray-50/60 p-4">
              <div className="mb-2 text-sm font-medium text-gray-900">
                {SENSITIVITY_DIMENSION_LABELS[pr.dimension] || pr.dimension}
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="field-label text-xs">Start</label>
                  <input
                    type="number"
                    className="field"
                    value={pr.start ?? ""}
                    onChange={(e) => {
                      const ranges = [...parameterRanges];
                      ranges[idx] = { ...ranges[idx], start: Number(e.target.value) };
                      setParameterRanges(ranges);
                    }}
                  />
                </div>
                <div>
                  <label className="field-label text-xs">End</label>
                  <input
                    type="number"
                    className="field"
                    value={pr.end ?? ""}
                    onChange={(e) => {
                      const ranges = [...parameterRanges];
                      ranges[idx] = { ...ranges[idx], end: Number(e.target.value) };
                      setParameterRanges(ranges);
                    }}
                  />
                </div>
                <div>
                  <label className="field-label text-xs">Step</label>
                  <input
                    type="number"
                    className="field"
                    value={pr.step ?? ""}
                    onChange={(e) => {
                      const ranges = [...parameterRanges];
                      ranges[idx] = { ...ranges[idx], step: Number(e.target.value) };
                      setParameterRanges(ranges);
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <label className="field-label">
            Max Configurations
          </label>
          <input
            type="number"
            className="field w-32"
            value={maxConfigs}
            min={2}
            max={50}
            onChange={(e) => setMaxConfigs(Number(e.target.value))}
          />
        </div>
      </section>

      {/* Review */}
      <section className="card p-6">
        <h2 className="section-title mb-4">Review</h2>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-gray-500">Configurations to generate</dt>
            <dd className="font-medium text-gray-900">{estimated}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Max allowed</dt>
            <dd className="font-medium text-gray-900">{maxConfigs}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Parameter dimensions</dt>
            <dd className="font-medium text-gray-900">{parameterRanges.length}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Estimated workload</dt>
            <dd className="font-medium text-gray-900">
              {estimated <= 10 ? "Low" : estimated <= 30 ? "Moderate" : "High"}
            </dd>
          </div>
        </dl>
        {estimated > maxConfigs && (
          <p className="error-banner mt-3" role="alert">
            The estimated configurations ({estimated}) exceed the max limit ({maxConfigs}).
            Reduce the parameter range.
          </p>
        )}
      </section>

      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={() => navigate("/simulations/research")}
        >
          Cancel
        </Button>
        <Button
          onClick={handleCreate}
          isLoading={creating}
          disabled={!name.trim() || !selectedScenarioId || estimated > maxConfigs}
        >
          <FlaskConical className="h-4 w-4" aria-hidden="true" />
          Create Experiment
        </Button>
      </div>
    </div>
  );
}
