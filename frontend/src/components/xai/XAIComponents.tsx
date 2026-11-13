import type { ConfidenceScore, FeatureImportanceItem, FactorItem } from "../../types/screening";

// ─── Score Ring ─────────────────────────────────────────────────────

export function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color =
    score >= 80 ? "#22c55e" : score >= 60 ? "#3b82f6" : score >= 40 ? "#eab308" : "#ef4444";
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="drop-shadow-sm"
      role="img"
      aria-label={`Score ${score}`}
    >
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="6" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="central"
        className="font-bold"
        fill={color}
        fontSize={size * 0.25}
      >
        {score}
      </text>
    </svg>
  );
}

// ─── Confidence Indicator ───────────────────────────────────────────

export function ConfidenceIndicator({ confidence }: { confidence: ConfidenceScore }) {
  const colorMap: Record<string, string> = {
    very_high: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    high: "bg-sky-50 text-sky-700 ring-sky-200/70",
    medium: "bg-amber-50 text-amber-700 ring-amber-200/70",
    low: "bg-red-50 text-red-700 ring-red-200/70",
  };
  const labelMap: Record<string, string> = {
    very_high: "Very High",
    high: "High",
    medium: "Medium",
    low: "Low",
  };
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ring-1 ring-inset transition-colors ${colorMap[confidence.level] || colorMap.medium}`}
    >
      <div className="h-2 w-2 rounded-full bg-current" />
      {labelMap[confidence.level]} ({confidence.score}%)
    </div>
  );
}

// ─── Feature Importance Bar ─────────────────────────────────────────

export function FeatureImportanceBar({ feature }: { feature: FeatureImportanceItem }) {
  const barColor =
    feature.impact === "positive"
      ? "bg-gradient-to-r from-emerald-400 to-emerald-500"
      : feature.impact === "negative"
        ? "bg-gradient-to-r from-rose-400 to-red-500"
        : "bg-gradient-to-r from-sky-400 to-blue-500";
  const textColor =
    feature.impact === "positive"
      ? "text-emerald-700"
      : feature.impact === "negative"
        ? "text-red-700"
        : "text-sky-700";
  return (
    <div className="flex items-center gap-3 py-0.5">
      <span className="w-36 shrink-0 truncate text-sm text-gray-700">{feature.label}</span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100 ring-1 ring-inset ring-gray-200/70">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-smooth ${barColor}`}
          style={{ width: `${feature.contribution_pct}%` }}
        />
      </div>
      <span className={`w-16 text-right text-xs font-bold ${textColor}`}>
        {feature.contribution_pct}%
      </span>
      <span className="w-8 text-right text-xs font-semibold text-gray-500">{feature.score}</span>
    </div>
  );
}

// ─── Factor List ────────────────────────────────────────────────────

export function FactorList({
  factors,
  type,
}: {
  factors: FactorItem[];
  type: "positive" | "negative";
}) {
  if (factors.length === 0) return <p className="text-sm text-gray-500">None identified</p>;
  return (
    <ul className="space-y-2">
      {factors.map((f, i) => (
        <li
          key={i}
          className={`flex items-start gap-2.5 rounded-lg px-3 py-2 text-sm ring-1 ring-inset transition-colors ${
            type === "positive"
              ? "bg-emerald-50/60 ring-emerald-200/50"
              : "bg-red-50/60 ring-red-200/50"
          }`}
        >
          <span
            className={`mt-0.5 font-bold ${type === "positive" ? "text-emerald-600" : "text-red-600"}`}
          >
            {type === "positive" ? "+" : "-"}
          </span>
          <div>
            <span className="font-semibold text-gray-900">{f.category}</span>
            <span className="ml-1 font-medium text-gray-600">({f.score}%)</span>
            <p className="mt-0.5 text-xs text-gray-500">{f.reason}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ─── Stat Box ───────────────────────────────────────────────────────

export function StatBox({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="card card-hover p-4">
      <p className="section-label truncate">{label}</p>
      <p className={`mt-1.5 font-display text-2xl font-bold tracking-tight ${color}`}>{value}</p>
    </div>
  );
}

// ─── Badge ──────────────────────────────────────────────────────────

export function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${color}`}>
      {label}
    </span>
  );
}

// ─── Score Color Helpers ────────────────────────────────────────────

export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600";
  if (score >= 60) return "text-sky-600";
  if (score >= 40) return "text-amber-600";
  return "text-red-600";
}

export function scoreBgColor(score: number): string {
  if (score >= 80) return "bg-emerald-50 text-emerald-700 ring-emerald-200/70";
  if (score >= 60) return "bg-sky-50 text-sky-700 ring-sky-200/70";
  if (score >= 40) return "bg-amber-50 text-amber-700 ring-amber-200/70";
  return "bg-red-50 text-red-700 ring-red-200/70";
}

export function strengthColor(level: string): string {
  switch (level) {
    case "excellent": return "bg-emerald-50 text-emerald-700 ring-emerald-200/70";
    case "good": return "bg-sky-50 text-sky-700 ring-sky-200/70";
    case "average": return "bg-amber-50 text-amber-700 ring-amber-200/70";
    default: return "bg-red-50 text-red-700 ring-red-200/70";
  }
}

export function recommendationColor(rec: string): string {
  switch (rec) {
    case "strongly_recommend": return "bg-emerald-50 text-emerald-700 ring-emerald-200/70";
    case "recommend": return "bg-sky-50 text-sky-700 ring-sky-200/70";
    case "consider": return "bg-amber-50 text-amber-700 ring-amber-200/70";
    default: return "bg-red-50 text-red-700 ring-red-200/70";
  }
}
