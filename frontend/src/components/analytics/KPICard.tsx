interface Props {
  label: string;
  value: number | string;
  unit?: string;
  changePct?: number;
  icon?: string;
  color?: string;
}

export function KPICard({ label, value, unit = "", changePct, color = "primary" }: Props) {
  const colorMap: Record<string, string> = {
    primary: "bg-primary-50 text-primary-700 ring-primary-200/70",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    yellow: "bg-amber-50 text-amber-700 ring-amber-200/70",
    red: "bg-red-50 text-red-700 ring-red-200/70",
    blue: "bg-sky-50 text-sky-700 ring-sky-200/70",
    purple: "bg-violet-50 text-violet-700 ring-violet-200/70",
  };
  const dotMap: Record<string, string> = {
    primary: "bg-primary-500",
    green: "bg-emerald-500",
    yellow: "bg-amber-500",
    red: "bg-red-500",
    blue: "bg-sky-500",
    purple: "bg-violet-500",
  };

  return (
    <div className="card card-hover relative overflow-hidden p-5">
      <div
        aria-hidden="true"
        className={`absolute right-0 top-0 h-24 w-24 -translate-y-8 translate-x-8 rounded-full opacity-40 blur-2xl ${dotMap[color] || dotMap.primary}`}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="section-label truncate">{label}</p>
          <div className="mt-2 flex items-baseline gap-1">
            <span
              className={`font-display text-2xl font-bold tracking-tight ${colorMap[color] || colorMap.primary} rounded-lg px-1.5 py-0.5`}
            >
              {typeof value === "number" ? value.toLocaleString() : value}
            </span>
            {unit && <span className="text-sm text-gray-400">{unit}</span>}
          </div>
          {changePct !== undefined && (
            <p
              className={`mt-1.5 text-xs font-medium ${changePct >= 0 ? "text-emerald-600" : "text-red-600"}`}
            >
              {changePct >= 0 ? "+" : ""}
              {changePct.toFixed(1)}% vs last period
            </p>
          )}
        </div>
        <span
          aria-hidden="true"
          className={`h-2 w-2 shrink-0 rounded-full ${dotMap[color] || dotMap.primary}`}
        />
      </div>
    </div>
  );
}
