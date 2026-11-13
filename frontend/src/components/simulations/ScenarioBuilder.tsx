import type {
  SimulationBaselineConfig,
  SimulationConfiguration,
} from "../../types/simulations";
import { computeClientChanges, simulationConfigFromBaseline } from "../../types/simulations";
import { ScenarioConfiguration, SimulationConfigSummary } from "./ScenarioConfiguration";

interface ScenarioBuilderProps {
  baseline: SimulationBaselineConfig;
  config: SimulationConfiguration;
  onChange: (next: SimulationConfiguration) => void;
  disabled?: boolean;
}

/**
 * Side-by-side baseline-vs-simulation comparison. The left column shows the
 * frozen baseline snapshot of the job's current hiring configuration; the
 * right column is the recruiter's editable proposed simulation config.
 */
export function ScenarioBuilder({ baseline, config, onChange, disabled }: ScenarioBuilderProps) {
  const changes = computeClientChanges(baseline, config);
  const changeCount = changes.total_changes;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card-solid p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink">Baseline configuration</h3>
              <p className="mt-0.5 text-xs text-ink-muted">
                Snapshot of the job&apos;s current hiring setup
              </p>
            </div>
            <span className="badge-neutral">Baseline</span>
          </div>
          <SimulationConfigSummary config={simulationConfigFromBaseline(baseline)} />
        </div>

        <div className="card p-5 ring-1 ring-primary-200/60">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink">Simulation configuration</h3>
              <p className="mt-0.5 text-xs text-ink-muted">
                What-if scenario to test against the baseline
              </p>
            </div>
            <span className="badge-primary">Simulation</span>
          </div>
          <ScenarioConfiguration value={config} onChange={onChange} disabled={disabled} />
        </div>
      </div>

      <div className="card-solid flex items-center justify-between px-4 py-2.5 text-sm">
        <span className="text-ink-muted">Changes vs baseline</span>
        <span
          className={
            changeCount === 0
              ? "font-semibold text-ink-muted"
              : "font-semibold text-primary-700"
          }
        >
          {changeCount === 0 ? "No changes yet" : `${changeCount} change${changeCount === 1 ? "" : "s"}`}
        </span>
      </div>
    </div>
  );
}