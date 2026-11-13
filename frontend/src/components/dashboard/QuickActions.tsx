import { Link } from "react-router-dom";

interface QuickAction {
  label: string;
  href: string;
  icon?: React.ReactNode;
}

interface QuickActionsProps {
  title?: string;
  actions: QuickAction[];
}

export function QuickActions({ title = "Quick Actions", actions }: QuickActionsProps) {
  return (
    <div className="card p-6 border border-slate-100 rounded-2xl bg-white shadow-xs">
      <h2 className="text-base font-bold text-slate-900 mb-4">{title}</h2>
      <div className="space-y-2">
        {actions.map((action) => (
          <Link
            key={action.href}
            to={action.href}
            className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 px-4 py-3 text-sm font-semibold text-slate-700 transition-all hover:border-blue-200 hover:bg-blue-50/30 hover:text-blue-600 group"
          >
            <div className="flex items-center gap-3">
              {action.icon && <span className="text-slate-400 group-hover:text-blue-600 transition-colors">{action.icon}</span>}
              <span>{action.label}</span>
            </div>
            <svg className="h-4 w-4 text-slate-300 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            </svg>
          </Link>
        ))}
      </div>
    </div>
  );
}
