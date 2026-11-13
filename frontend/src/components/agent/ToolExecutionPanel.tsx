import type { ToolExecutionResponse } from "../../types/agent";

interface Props {
  executions: ToolExecutionResponse[];
}

export function ToolExecutionPanel({ executions }: Props) {
  if (executions.length === 0) return null;

  return (
    <div className="border-t border-slate-200/70 bg-surface-muted/80 p-3 backdrop-blur-sm">
      <div className="section-label mb-2">Tool Executions</div>
      <div className="space-y-2">
        {executions.map((te) => (
          <div key={te.id} className="rounded-lg border border-slate-200/70 bg-white/80 p-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${
                    te.status === "completed"
                      ? "bg-emerald-500"
                      : te.status === "failed"
                        ? "bg-rose-500"
                        : "bg-amber-500 animate-pulse-soft"
                  }`}
                />
                <span className="text-xs font-semibold text-ink">{te.tool_name}</span>
              </div>
              <span className="text-xs text-ink-subtle">{te.execution_time_ms}ms</span>
            </div>
            {te.status === "completed" && te.result && (
              <pre className="mt-1.5 max-h-20 overflow-y-auto rounded-lg bg-ink/90 p-2 font-mono text-[11px] leading-relaxed text-slate-100">
                {JSON.stringify(te.result, null, 2).slice(0, 300)}
              </pre>
            )}
            {te.status === "failed" && te.error && (
              <div className="mt-1.5 text-xs font-medium text-rose-500">{te.error}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
