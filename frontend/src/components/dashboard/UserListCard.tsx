interface UserListItem {
  id: string;
  name: string;
  subtitle?: string;
  score?: number;
  badge?: { label: string; color: string };
}

interface UserListCardProps {
  title: string;
  users: UserListItem[];
  emptyMessage?: string;
  action?: { label: string; href: string };
}

export function UserListCard({ title, users, emptyMessage = "No data available", action }: UserListCardProps) {
  return (
    <div className="card p-6 border border-slate-100 rounded-2xl bg-white shadow-xs">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-bold text-slate-900">{title}</h2>
        {action && (
          <a
            href={action.href}
            className="shrink-0 text-xs font-semibold text-blue-600 transition-colors hover:text-blue-700"
          >
            {action.label} →
          </a>
        )}
      </div>
      {users.length > 0 ? (
        <div className="space-y-2">
          {users.map((user) => (
            <div
              key={user.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/50 p-3 transition-colors hover:border-blue-100 hover:bg-blue-50/30"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-800">{user.name}</p>
                {user.subtitle && <p className="truncate text-xs text-slate-400 font-mono mt-0.5">{user.subtitle}</p>}
              </div>
              {user.score !== undefined && (
                <span
                  className={`ml-3 shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold ${
                    user.score >= 80
                      ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-500/20"
                      : user.score >= 60
                        ? "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-500/20"
                        : "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-500/20"
                  }`}
                >
                  {user.score}%
                </span>
              )}
              {user.badge && (
                <span
                  className={`ml-3 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${user.badge.color}`}
                >
                  {user.badge.label}
                </span>
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
