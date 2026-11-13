import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Gauge,
  Play,
  RefreshCw,
  Server,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { skill2jobApi } from "../../api/skill2job";
import type {
  PipelineTraceSummary,
  Skill2JobCapabilities,
  Skill2JobHealth,
} from "../../types/skill2job";

function extractErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "response" in err) {
    const data = (err as any).response?.data;
    const msg = data?.error?.message ?? data?.detail;
    if (typeof msg === "string" && msg.trim()) return msg;
    if (Array.isArray(msg) && msg.length > 0) {
      const first = msg[0];
      if (typeof first === "object" && first !== null) {
        return first.msg || first.message || first.detail || JSON.stringify(first);
      }
      return String(first);
    }
  }
  return fallback;
}

export function Skill2JobDiagnostics() {
  const [health, setHealth] = useState<Skill2JobHealth | null>(null);
  const [capabilities, setCapabilities] = useState<Skill2JobCapabilities | null>(null);
  const [traces, setTraces] = useState<PipelineTraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const [h, c, t] = await Promise.all([
        skill2jobApi.getHealth(),
        skill2jobApi.getCapabilities(),
        skill2jobApi.getPipelineTraces(),
      ]);
      setHealth(h);
      setCapabilities(c);
      setTraces(Array.isArray(t) ? t : ((t as any)?.items ?? []));
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to load Skill2Job diagnostics."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function runPipeline() {
    setRunning(true);
    setError("");
    try {
      await skill2jobApi.runPipeline();
      await load(true);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Pipeline run failed."));
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-24 w-full" />
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="skeleton h-32 w-full" />
          <div className="skeleton h-32 w-full" />
        </div>
        <div className="skeleton h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="panel-brand flex flex-wrap items-center justify-between gap-4 p-6">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <span className="rounded-lg bg-white/80 p-1.5 text-primary-600 shadow-xs">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </span>
            Skill2Job Diagnostics (Admin)
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Internal implementation status, capabilities, and pipeline execution traces. Hidden from
            candidates; access is restricted to super_admin/admin.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={runPipeline}
            disabled={running}
            className="btn-primary btn-md"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            {running ? "Running pipeline…" : "Run full pipeline"}
          </button>
          <button
            type="button"
            onClick={() => load(true)}
            disabled={refreshing || loading || running}
            className="btn-secondary btn-md"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h3 className="section-title mb-3 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-emerald-50 p-1.5 text-emerald-600">
              <Server className="h-4 w-4" aria-hidden="true" />
            </span>
            Health
          </h3>
          <p className="text-sm text-gray-600">
            Module:{" "}
            <span className="rounded-md bg-gray-100 px-1.5 py-0.5 font-semibold text-gray-800">
              {health?.module ?? "—"}
            </span>{" "}
            · Status:{" "}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${
                health?.status === "ok" || health?.status === "healthy" || health?.status === "available"
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200/70"
                  : "bg-amber-50 text-amber-700 ring-amber-200/70"
              }`}
            >
              {health?.status ?? "unknown"}
            </span>
          </p>
        </section>

        <section className="card p-5">
          <h3 className="section-title mb-3 flex items-center gap-2 text-sm">
            <span className="rounded-lg bg-primary-50 p-1.5 text-primary-600">
              <Gauge className="h-4 w-4" aria-hidden="true" />
            </span>
            Capabilities
          </h3>
          <ul className="divide-y divide-gray-100">
            {capabilities?.capabilities.map((c) => (
              <li key={c.key} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800">{c.label}</p>
                  <p className="text-xs text-gray-400">
                    phase {c.phase} &middot; {c.key}
                  </p>
                </div>
                <span
                  className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${
                    c.status === "available"
                      ? "bg-emerald-50 text-emerald-700 ring-emerald-200/70"
                      : "bg-gray-100 text-gray-500 ring-gray-200/80"
                  }`}
                >
                  {c.status}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="card p-5">
        <h3 className="section-title mb-3 flex items-center gap-2 text-sm">
          <span className="rounded-lg bg-violet-50 p-1.5 text-violet-600">
            <Workflow className="h-4 w-4" aria-hidden="true" />
          </span>
          Pipeline Executions
        </h3>
        {traces.length === 0 ? (
          <div className="empty-state">
            <Workflow className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
            <h4 className="text-base font-semibold text-gray-900">
              No pipeline runs recorded yet.
            </h4>
            <p className="mt-1 text-sm text-gray-500">
              Run the full pipeline to populate execution traces.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {traces.map((t) => (
              <li key={t.run_id} className="flex items-center justify-between gap-4 py-2.5">
                <span className="flex min-w-0 items-center gap-2 text-xs text-gray-500">
                  <Activity className="h-3.5 w-3.5 shrink-0 text-primary-500" aria-hidden="true" />
                  <code className="truncate font-mono">{t.run_id}</code>
                </span>
                <span className="shrink-0 text-xs text-gray-400">
                  {t.steps} steps
                  {t.created_at ? ` · ${new Date(t.created_at).toLocaleString()}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
