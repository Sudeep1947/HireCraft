import type { SimulationValidationResponse } from "../../types/simulations";

function sectionLabel(field: string): string {
  if (field.startsWith("scoring_weights")) return "Scoring weights";
  if (field.startsWith("requirements")) return "Requirements";
  if (field === "threshold") return "Pass threshold";
  if (field === "shortlist_size") return "Shortlist size";
  return "Configuration";
}

interface ValidationPanelProps {
  validation: SimulationValidationResponse | null;
  loading?: boolean;
}

export function ValidationPanel({ validation, loading }: ValidationPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200/70 bg-surface-muted/80 px-4 py-3 text-sm text-ink-muted shadow-xs">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-primary-600" aria-hidden="true" />
        Validating configuration…
      </div>
    );
  }

  if (!validation) return null;

  if (validation.valid) {
    return (
      <div className="success-banner">
        <span className="mt-0.5 text-base leading-none font-bold" aria-hidden="true">&#10003;</span>
        <div>
          <p className="font-semibold">Configuration is valid</p>
          <p className="mt-0.5 text-xs text-emerald-700/90">
            The scenario can be promoted to <span className="font-semibold">ready</span>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="error-banner">
      <p className="font-semibold">
        Configuration needs attention ({validation.errors.length} issue
        {validation.errors.length === 1 ? "" : "s"})
      </p>
      <ul className="mt-2 space-y-1.5">
        {validation.errors.map((issue, index) => (
          <li key={`${issue.field}-${index}`} className="flex items-start gap-2">
            <span className="mt-0.5 text-rose-400">&#8226;</span>
            <span>
              <span className="mr-1.5 inline-flex rounded bg-rose-100 px-1.5 py-0.5 text-xs font-semibold text-rose-700">
                {sectionLabel(issue.field)}
              </span>
              {issue.message}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}