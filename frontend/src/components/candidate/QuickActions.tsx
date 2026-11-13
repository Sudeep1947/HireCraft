import { useNavigate } from "react-router-dom";

interface QuickAction {
  label: string;
  path: string;
  description: string;
  icon: string;
  disabled?: boolean;
}

const actions: QuickAction[] = [
  { label: "Complete Profile", path: "/candidate/profile", description: "Fill in your details", icon: "👤" },
  { label: "Upload Resume", path: "#", description: "Coming soon", icon: "📄", disabled: true },
  { label: "Search Jobs", path: "#", description: "Coming soon", icon: "🔍", disabled: true },
  { label: "Career Insights", path: "#", description: "Coming soon", icon: "📊", disabled: true },
];

export function QuickActions() {
  const navigate = useNavigate();

  return (
    <div className="card p-5">
      <h3 className="section-title">Quick Actions</h3>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={() => !action.disabled && navigate(action.path)}
            disabled={action.disabled}
            className={`flex flex-col items-center gap-1 rounded-xl border p-3 text-center transition-all duration-200 ${
              action.disabled
                ? "cursor-not-allowed border-gray-200 bg-gray-50 text-gray-400"
                : "border-gray-200 bg-white/70 text-gray-700 shadow-xs hover:border-primary-300 hover:bg-primary-50/50 hover:text-primary-700 hover:shadow-md"
            }`}
          >
            <span className="text-xl" aria-hidden="true">
              {action.icon}
            </span>
            <span className="text-sm font-medium">{action.label}</span>
            <span className="text-xs text-gray-400">{action.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
