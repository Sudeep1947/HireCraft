interface ActivityItem {
  id?: string | number;
  title: string;
  description?: string;
  time?: string;
  type?: "success" | "info" | "warning" | "error";
}

interface ActivityCardProps {
  title?: string;
  items: ActivityItem[];
  emptyMessage?: string;
}

const typeColors = {
  success: "bg-emerald-500 ring-emerald-100",
  info: "bg-blue-500 ring-blue-100",
  warning: "bg-amber-500 ring-amber-100",
  error: "bg-rose-500 ring-rose-100",
};

export function ActivityCard({ title = "Recent Activity", items, emptyMessage = "No activity yet" }: ActivityCardProps) {
  return (
    <div className="card p-6 border border-slate-100 rounded-2xl bg-white shadow-xs">
      <h2 className="text-base font-bold text-slate-900 mb-4">{title}</h2>
      {items.length > 0 ? (
        <div className="space-y-2.5">
          {items.map((item, i) => (
            <div
              key={item.id ?? i}
              className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/50 p-3 transition-colors hover:border-blue-100 hover:bg-blue-50/30"
            >
              {item.type && (
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ring-4 ${typeColors[item.type]}`}
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-800">{item.title}</p>
                {item.description && (
                  <p className="mt-0.5 truncate text-xs text-slate-500">{item.description}</p>
                )}
              </div>
              {item.time && (
                <span className="shrink-0 whitespace-nowrap text-xs text-slate-400">{item.time}</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-4 py-8 text-center">
          <p className="text-sm text-slate-400">{emptyMessage}</p>
        </div>
      )}
    </div>
  );
}
