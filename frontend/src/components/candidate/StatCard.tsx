interface StatCardProps {
  label: string;
  value: string | number;
  icon?: string;
  color?: string;
}

const colorMap: Record<string, { tile: string; value: string }> = {
  blue: { tile: "bg-primary-50 text-primary-600", value: "text-primary-600" },
  green: { tile: "bg-emerald-50 text-emerald-600", value: "text-emerald-600" },
  purple: { tile: "bg-violet-50 text-violet-600", value: "text-violet-600" },
  amber: { tile: "bg-amber-50 text-amber-600", value: "text-amber-600" },
  indigo: { tile: "bg-primary-50 text-primary-600", value: "text-primary-600" },
  rose: { tile: "bg-rose-50 text-rose-600", value: "text-rose-600" },
};

export function StatCard({ label, value, icon, color = "blue" }: StatCardProps) {
  const colors = colorMap[color] || colorMap.blue;

  return (
    <div className="card card-hover p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-gray-500">{label}</p>
          <p className={`mt-1.5 font-display text-2xl font-bold ${colors.value}`}>{value}</p>
        </div>
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl shadow-soft ${colors.tile}`}>
          {icon ? (
            <span className="text-lg leading-none" aria-hidden="true">
              {icon}
            </span>
          ) : (
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
              />
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}
