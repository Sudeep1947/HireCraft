import { AlertTriangle, ShieldCheck } from "lucide-react";

import type {
  FairnessMetricDetail,
  BiasAlert,
} from "../../types/fairness";

// --- Fairness Score Card ---

export function FairnessScoreCard({
  score,
  label = "Overall Fairness",
  size = 120,
}: {
  score: number;
  label?: string;
  size?: number;
}) {
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color =
    score >= 80 ? "#22c55e" : score >= 60 ? "#3b82f6" : score >= 40 ? "#eab308" : "#ef4444";
  const statusText =
    score >= 80 ? "Excellent" : score >= 60 ? "Good" : score >= 40 ? "Needs Improvement" : "Poor";

  return (
    <div className="card card-hover flex flex-col items-center gap-2 p-5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x={size / 2}
          y={size / 2 - 4}
          textAnchor="middle"
          dominantBaseline="central"
          className="font-bold"
          fill={color}
          fontSize={size * 0.22}
        >
          {score}
        </text>
        <text
          x={size / 2}
          y={size / 2 + size * 0.12}
          textAnchor="middle"
          className="text-xs"
          fill="#6b7280"
          fontSize={size * 0.09}
        >
          {statusText}
        </text>
      </svg>
      <span className="text-sm font-semibold text-gray-700">{label}</span>
    </div>
  );
}

// --- Metric Status Badge ---

export function MetricStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    fair: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    good: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    excellent: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    moderate: "bg-amber-50 text-amber-700 ring-amber-200/70",
    concerning: "bg-amber-50 text-amber-700 ring-amber-200/70",
    low: "bg-amber-50 text-amber-700 ring-amber-200/70",
    biased: "bg-red-50 text-red-700 ring-red-200/70",
    poor: "bg-red-50 text-red-700 ring-red-200/70",
    needs_improvement: "bg-orange-50 text-orange-700 ring-orange-200/70",
    high: "bg-red-50 text-red-700 ring-red-200/70",
    medium: "bg-amber-50 text-amber-700 ring-amber-200/70",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset transition-colors ${styles[status] || "bg-gray-100 text-gray-700 ring-gray-200/80"}`}
    >
      {status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
    </span>
  );
}

// --- Fairness Metrics Table ---

export function FairnessMetricsTable({
  metrics,
}: {
  metrics: Record<string, FairnessMetricDetail>;
}) {
  const labels: Record<string, string> = {
    statistical_parity_difference: "Statistical Parity Difference",
    disparate_impact_ratio: "Disparate Impact Ratio",
    equal_opportunity_difference: "Equal Opportunity Difference",
    demographic_parity: "Demographic Parity",
    consistency_score: "Consistency Score",
    composite_fairness_score: "Composite Fairness Score",
  };

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Status</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(metrics).map(([key, detail]) => (
            <tr key={key}>
              <td className="font-medium text-gray-900">{labels[key] || key}</td>
              <td className="font-mono text-sm">
                {typeof detail.value === "number" ? detail.value.toFixed(4) : String(detail.value)}
              </td>
              <td>
                <MetricStatusBadge status={detail.status} />
              </td>
              <td className="max-w-md text-gray-500">{detail.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Bias Alert Panel ---

export function BiasAlertPanel({ alerts }: { alerts: BiasAlert[] }) {
  if (!alerts.length) {
    return (
      <div className="success-banner">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <p>No bias alerts detected. All clear.</p>
      </div>
    );
  }

  const severityColors: Record<string, string> = {
    high: "border-red-200/80 bg-red-50/80",
    medium: "border-amber-200/80 bg-amber-50/80",
    low: "border-sky-200/80 bg-sky-50/80",
  };
  const severityIcons: Record<string, string> = {
    high: "\u26a0",
    medium: "\u26a0",
    low: "\u2139",
  };

  return (
    <div className="space-y-3">
      {alerts.map((alert, i) => (
        <div
          key={i}
          className={`rounded-xl border p-4 shadow-xs transition-shadow hover:shadow-soft ${severityColors[alert.severity] || "border-gray-200 bg-gray-50"}`}
        >
          <div className="flex items-start gap-3">
            <span className="text-lg" aria-hidden="true">
              {severityIcons[alert.severity] || "\u2139"}
            </span>
            <div className="flex-1">
              <div className="mb-1 flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-900">
                  {alert.type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
                <MetricStatusBadge status={alert.severity} />
              </div>
              <p className="mb-1 text-sm text-gray-700">{alert.message}</p>
              <p className="text-xs text-gray-500">{alert.recommendation}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Diversity Stat ---

export function DiversityStat({
  label,
  value,
  color = "blue",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "bg-sky-50 text-sky-700 ring-sky-200/70",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    purple: "bg-violet-50 text-violet-700 ring-violet-200/70",
    orange: "bg-orange-50 text-orange-700 ring-orange-200/70",
  };
  return (
    <div
      className={`rounded-xl p-4 ring-1 ring-inset transition-shadow hover:shadow-soft ${colorMap[color] || colorMap.blue}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide opacity-75">{label}</p>
      <p className="mt-1 font-display text-lg font-bold">{value}</p>
    </div>
  );
}

// --- Severity Count Badges ---

export function SeverityCounts({
  counts,
}: {
  counts: Record<string, number>;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(counts).map(([severity, count]) => (
        <span
          key={severity}
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
            severity === "high"
              ? "bg-red-50 text-red-700 ring-red-200/70"
              : severity === "medium"
                ? "bg-amber-50 text-amber-700 ring-amber-200/70"
                : "bg-sky-50 text-sky-700 ring-sky-200/70"
          }`}
        >
          {severity}: {count}
        </span>
      ))}
    </div>
  );
}

// --- Progress Bar ---

export function FairnessProgressBar({
  value,
  max = 100,
  label,
  color,
}: {
  value: number;
  max?: number;
  label?: string;
  color?: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  const barColor = color || (pct >= 80 ? "#22c55e" : pct >= 60 ? "#3b82f6" : pct >= 40 ? "#eab308" : "#ef4444");

  return (
    <div>
      {label && (
        <div className="mb-1.5 flex justify-between">
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className="text-sm font-semibold text-gray-700">{Math.round(pct)}%</span>
        </div>
      )}
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100 ring-1 ring-inset ring-gray-200/70">
        <div
          className="h-full rounded-full transition-all duration-500 ease-smooth"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>
    </div>
  );
}

// --- Issue List ---

export function IssueList({
  title,
  items,
  color = "gray",
}: {
  title: string;
  items: Array<{ term: string; suggestion: string }>;
  color?: string;
}) {
  if (!items.length) return null;
  const bgColor: Record<string, string> = {
    red: "bg-red-50/80 border-red-200/80",
    yellow: "bg-amber-50/80 border-amber-200/80",
    orange: "bg-orange-50/80 border-orange-200/80",
    gray: "bg-gray-50/80 border-gray-200/80",
  };
  return (
    <div className={`rounded-xl border p-4 shadow-xs ${bgColor[color] || bgColor.gray}`}>
      <h4 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-gray-900">
        <AlertTriangle className="h-3.5 w-3.5 text-gray-400" aria-hidden="true" />
        {title} ({items.length})
      </h4>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="text-sm">
            <span className="font-mono font-medium text-red-700">"{item.term}"</span>
            <span className="ml-2 text-gray-600">- {item.suggestion}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
