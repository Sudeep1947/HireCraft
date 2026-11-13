import type { ChartData as ChartDataType } from "../../types/analytics";

interface Props {
  data: ChartDataType;
  height?: number;
  type?: "bar" | "line";
}

const COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4"];

export function ChartCard({ data, height = 200, type = "bar" }: Props) {
  const maxVal = Math.max(
    ...data.datasets.flatMap((ds) => ds.data),
    1,
  );

  const hasData =
    maxVal > 1 ||
    data.datasets.some((ds) => ds.data.some((v) => v > 0));

  const plotHeight = height - 24;
  const COLORS_LEN = COLORS.length;

  return (
    <div className="card p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {data.datasets.map((ds, i) => (
          <span key={ds.label} className="flex items-center gap-1.5 text-xs font-medium text-ink-muted">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: ds.color || COLORS[i % COLORS_LEN] }}
            />
            {ds.label}
          </span>
        ))}
      </div>
      {!hasData ? (
        <div
          className="flex items-center justify-center text-sm text-ink-subtle"
          style={{ height }}
        >
          No analytics data available yet.
        </div>
      ) : (
        <div className="flex items-end gap-1" style={{ height }}>
          {data.labels.map((label, li) => (
            <div key={label} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="flex w-full items-end gap-px"
                style={{ height: plotHeight }}
              >
                {data.datasets.map((ds, di) => {
                  const index = li;
                  const val = ds.data[index] ?? 0;
                  const color = ds.color || COLORS[di % COLORS_LEN];
                  const barHeight = Math.round((val / Math.max(maxVal, 1)) * plotHeight);
                  const isLine = type === "line";
                  return (
                    <div key={ds.label} className="flex-1">
                      <div
                        className="w-full rounded-t transition-all"
                        style={{
                          height: barHeight,
                          backgroundColor: color,
                          opacity: isLine ? 0.8 : 1,
                        }}
                        title={`${ds.label}: ${val}`}
                      />
                    </div>
                  );
                })}
              </div>
              <span className="w-full truncate text-center text-[10px] text-ink-subtle">
                {label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
