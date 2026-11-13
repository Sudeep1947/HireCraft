import type { AgentInfo, ToolExecutionResponse, ProviderInfo } from "../../types/agent";

interface Props {
  agents: AgentInfo[];
  toolExecutions: ToolExecutionResponse[];
  agentUsed: string;
  processingTimeMs: number;
  providers: ProviderInfo[];
}

export function AgentInfoPanel({ agents, toolExecutions, agentUsed, processingTimeMs, providers }: Props) {
  return (
    <div className="flex h-full w-72 shrink-0 flex-col overflow-y-auto border-l border-slate-200/70 bg-surface-muted/80 backdrop-blur-sm">
      <div className="border-b border-slate-200/70 p-3">
        <h3 className="section-label">Agent Status</h3>
      </div>

      {agentUsed && (
        <div className="border-b border-slate-200/70 p-3">
          <div className="mb-1 text-xs font-medium text-ink-muted">Active Agent</div>
          <div className="rounded-lg bg-gradient-to-br from-primary-50 to-violet-50 px-3 py-2 text-sm font-semibold capitalize text-primary-700 ring-1 ring-inset ring-primary-200/60">
            {agentUsed.replace("_", " ")} Agent
          </div>
          {processingTimeMs > 0 && (
            <div className="mt-1.5 text-xs text-ink-subtle">Response time: {processingTimeMs}ms</div>
          )}
        </div>
      )}

      {providers.length > 0 && (
        <div className="border-b border-slate-200/70 p-3">
          <div className="section-label mb-2">LLM Providers</div>
          <div className="space-y-1.5">
            {providers.map((p) => (
              <div
                key={p.name}
                className="rounded-lg border border-slate-200/70 bg-white/80 px-2.5 py-2 transition-colors hover:border-primary-200"
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      p.status === "healthy"
                        ? "bg-emerald-500"
                        : p.status === "degraded"
                          ? "bg-amber-500"
                          : "bg-rose-500"
                    }`}
                  />
                  <span className="text-xs font-medium capitalize">{p.name}</span>
                  <span className="ml-auto text-xs font-semibold text-ink-muted">
                    {(p.success_rate * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-subtle">{p.model}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {toolExecutions.length > 0 && (
        <div className="border-b border-slate-200/70 p-3">
          <div className="section-label mb-2">Tools Used ({toolExecutions.length})</div>
          <div className="space-y-1.5">
            {toolExecutions.map((te) => (
              <div key={te.id} className="rounded-lg border border-slate-200/70 bg-white/80 px-2.5 py-2">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${te.status === "completed" ? "bg-emerald-500" : "bg-rose-500"}`}
                  />
                  <span className="text-xs font-medium">{te.tool_name}</span>
                </div>
                <div className="mt-0.5 text-xs text-ink-subtle">{te.execution_time_ms}ms</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="p-3">
        <div className="section-label mb-2">Available Agents ({agents.length})</div>
        <div className="space-y-2">
          {agents.map((a) => (
            <div
              key={a.type}
              className="rounded-lg border border-slate-200/70 bg-white/80 p-2.5 transition-colors hover:border-primary-200"
            >
              <div className="text-xs font-semibold capitalize text-ink">
                {a.type.replace("_", " ")}
              </div>
              <div className="mt-0.5 text-xs text-ink-muted">{a.description}</div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {a.capabilities.slice(0, 3).map((cap) => (
                  <span
                    key={cap}
                    className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px] font-medium text-ink-muted"
                  >
                    {cap.replace(/_/g, " ")}
                  </span>
                ))}
                {a.capabilities.length > 3 && (
                  <span className="text-xs text-ink-subtle">+{a.capabilities.length - 3}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
