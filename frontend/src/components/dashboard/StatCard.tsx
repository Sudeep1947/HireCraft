interface StatCardProps {
  title: string;
  value: number | string;
  icon?: React.ReactNode;
  color?: "primary" | "green" | "blue" | "purple" | "amber" | "red" | "indigo";
  trend?: { value: number; isPositive: boolean };
  subtitle?: string;
}

const colorMap = {
  primary: { bg: "bg-blue-50", text: "text-blue-600", icon: "text-blue-600" },
  green: { bg: "bg-emerald-50", text: "text-emerald-600", icon: "text-emerald-600" },
  blue: { bg: "bg-cyan-50", text: "text-cyan-600", icon: "text-cyan-600" },
  purple: { bg: "bg-purple-50", text: "text-purple-600", icon: "text-purple-600" },
  amber: { bg: "bg-amber-50", text: "text-amber-600", icon: "text-amber-600" },
  red: { bg: "bg-rose-50", text: "text-rose-600", icon: "text-rose-600" },
  indigo: { bg: "bg-indigo-50", text: "text-indigo-600", icon: "text-indigo-600" },
};

export function StatCard({ title, value, icon, color = "primary", trend, subtitle }: StatCardProps) {
  const colors = colorMap[color];

  return (
    <div className="card card-hover p-5 border border-slate-100 rounded-2xl bg-white shadow-xs">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="truncate text-xs font-medium text-slate-500">{title}</p>
          <div className="mt-1 flex items-baseline justify-between gap-2">
            <span className="font-display text-2xl font-bold text-slate-900">{value}</span>
            {trend && (
              <span className={`text-xs font-semibold ${trend.isPositive ? "text-emerald-600" : "text-rose-600"}`}>
                {trend.isPositive ? "↑ " : "↓ "}{trend.value}%
              </span>
            )}
          </div>
          {subtitle ? (
            <p className="mt-0.5 text-[10px] text-slate-400">{subtitle}</p>
          ) : (
            <p className="mt-0.5 text-[10px] text-slate-400">vs. last 7 days</p>
          )}
        </div>
        {icon && (
          <div className={`${colors.bg} flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ml-3`}>
            <div className={colors.icon}>{icon}</div>
          </div>
        )}
      </div>
    </div>
  );
}
