import { Link } from "react-router-dom";

interface PipelineCardProps {
  title: string;
  stages: Record<string, number>;
  action?: { label: string; href: string };
  color?: "blue" | "purple" | "green";
  stageHref?: (stage: string) => string;
  stageLabel?: (stage: string) => string;
}

const stageColors = {
  blue: ["bg-blue-600 text-blue-600", "bg-blue-50/60"],
  purple: ["bg-purple-600 text-purple-600", "bg-purple-50/60"],
  green: ["bg-emerald-600 text-emerald-600", "bg-emerald-50/60"],
};

export function PipelineCard({
  title,
  stages,
  action,
  color = "blue",
  stageHref,
  stageLabel,
}: PipelineCardProps) {
  const entries = Object.entries(stages);
  const colors = stageColors[color];

  return (
    <div className="card p-6 border border-slate-100 rounded-2xl bg-white shadow-xs">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-bold text-slate-900">{title}</h2>
        {action && (
          <Link
            to={action.href}
            className="text-xs font-semibold text-blue-600 transition-colors hover:text-blue-700"
          >
            {action.label} →
          </Link>
        )}
      </div>
      {entries.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {entries.map(([stage, count]) => {
            const label = stageLabel ? stageLabel(stage) : stage.replace(/_/g, " ");
            const body = (
              <>
                <p className={`font-display text-2xl font-bold ${colors[0].split(" ")[1]}`}>{count}</p>
                <p className="mt-1 text-xs font-medium text-slate-500 capitalize">{label}</p>
              </>
            );
            const href = stageHref?.(stage);
            if (href) {
              return (
                <Link
                  key={stage}
                  to={href}
                  className={`rounded-xl p-3 text-center transition-all hover:ring-2 hover:ring-blue-300 ${colors[1]}`}
                  aria-label={`${label}: ${count}. View these applications`}
                >
                  {body}
                </Link>
              );
            }
            return (
              <div key={stage} className={`rounded-xl p-3 text-center ${colors[1]}`}>
                {body}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-slate-400">No pipeline data available.</p>
      )}
    </div>
  );
}
