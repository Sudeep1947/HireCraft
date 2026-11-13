import type { DataDistribution } from "../../types/analytics";

interface Props {
  data: DataDistribution[];
  title: string;
}

const BAR_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4"];

export function DistributionBar({ data, title }: Props) {
  const total = data.reduce((s, d) => s + d.count, 0) || 1;

  return (
    <div className="card relative overflow-hidden p-5">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-br from-primary-500/10 to-transparent"
      />
      <div className="relative mb-4 flex items-center justify-between gap-2">
        <h4 className="section-title text-sm">{title}</h4>
        <span className="section-label">Total {total}</span>
      </div>

      <div className="relative">
        <div className="flex h-4 w-full overflow-hidden rounded-full bg-gray-100 ring-1 ring-inset ring-gray-200/70">
          {data.map((d, i) => (
            <div
              key={d.label}
              className="h-full transition-all duration-300 ease-smooth hover:brightness-110"
              style={{
                width: `${(d.count / total) * 100}%`,
                backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
              }}
              title={`${d.label}: ${d.count}`}
            />
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {data.map((d, i) => (
            <span
              key={d.label}
              className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-200/80"
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: BAR_COLORS[i % BAR_COLORS.length] }}
              />
              {d.label} ({d.count})
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
