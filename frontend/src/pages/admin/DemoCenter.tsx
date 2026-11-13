import { useCallback, useEffect, useRef, useState } from "react";
import { Boxes, Download, History, ListChecks, PlayCircle, Sparkles, Trash2 } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { demoApi } from "../../api/demo";
import type {
  DemoRun,
  DemoRunDetail,
  DemoScenario,
  DemoStatus,
  DemoExport,
  ResumeFormat,
  HiringDifficulty,
} from "../../api/demo";

interface FormState {
  num_candidates: number;
  num_recruiters: number;
  num_hr: number;
  num_jobs: number;
  num_companies: string;
  candidates_per_job: number;
  hiring_difficulty: HiringDifficulty;
  skill_categories: string;
  include_screening: boolean;
  include_interviews: boolean;
  include_reports: boolean;
  include_agent_indexing: boolean;
  resume_format: ResumeFormat;
  seed: string;
  companies: string;
  job_titles: string;
}

const DEFAULT_FORM: FormState = {
  num_candidates: 20,
  num_recruiters: 3,
  num_hr: 1,
  num_jobs: 5,
  num_companies: "",
  candidates_per_job: 8,
  hiring_difficulty: "medium",
  skill_categories: "",
  include_screening: true,
  include_interviews: true,
  include_reports: true,
  include_agent_indexing: true,
  resume_format: "mixed",
  seed: "",
  companies: "",
  job_titles: "",
};

const RESUME_FORMATS: ResumeFormat[] = ["pdf", "docx", "txt", "mixed"];

const HIRING_DIFFICULTIES: HiringDifficulty[] = ["easy", "medium", "hard"];

const SKILL_CATEGORY_OPTIONS = [
  { value: "engineering", label: "Engineering" },
  { value: "data_ai", label: "Data & AI" },
  { value: "cloud_devops", label: "Cloud & DevOps" },
  { value: "healthcare", label: "Healthcare" },
  { value: "finance", label: "Finance" },
  { value: "government", label: "Government" },
  { value: "support_operations", label: "Support & Operations" },
];

const STATUS_STYLES: Record<string, string> = {
  queued: "badge-warning",
  running: "badge-info",
  completed: "badge-success",
  failed: "badge-danger",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function StageLabel({ stage }: { stage: string | null }) {
  const map: Record<string, string> = {
    start: "Starting",
    companies: "Companies",
    recruiters: "Recruiters",
    hr: "HR Users",
    candidates: "Candidates",
    jobs: "Jobs",
    applications: "Applications",
    screening: "Screening",
    interviews: "Interviews",
    decisions: "Hiring Decisions",
    reports: "Reports",
    agent_indexing: "Agent Indexing",
    completed: "Completed",
  };
  return <span>{stage ? map[stage] ?? stage : "—"}</span>;
}

export function DemoCenter() {
  const { addToast } = useToast();
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<DemoRunDetail | null>(null);
  const [exportData, setExportData] = useState<DemoExport | null>(null);
  const [exporting, setExporting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState<string>("");
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadStatus = useCallback(
    async (showError = true) => {
      try {
        const data = await demoApi.getStatus();
        setStatus(data);
        return data;
      } catch {
        if (showError) addToast("Failed to load demo status", "error");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [addToast],
  );

  const isActive = (run: DemoRun | null) =>
    !!run && (run.status === "queued" || run.status === "running");

  useEffect(() => {
    demoApi
      .getScenarios()
      .then((data) => {
        setScenarios(data);
        if (data.length > 0) {
          setSelectedScenario(data[0].slug);
          applyScenario(data[0].slug, data);
        }
      })
      .catch(() => addToast("Failed to load demo scenarios", "error"));
    void loadStatus();
  }, [addToast, loadStatus]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  useEffect(() => {
    if (isActive(status?.latest_run ?? null)) {
      stopPolling();
      pollRef.current = window.setTimeout(async () => {
        const data = await loadStatus(false);
        if (data?.latest_run) {
          setDetail((prev) =>
            prev && prev.run.id === data.latest_run!.id
              ? { ...prev, run: data.latest_run! }
              : prev,
          );
        }
      }, 2000);
    }
  }, [status, loadStatus, stopPolling]);

  const applyScenario = (slug: string, list?: DemoScenario[]) => {
    setSelectedScenario(slug);
    const scenario = (list ?? scenarios).find((s) => s.slug === slug);
    if (!scenario?.config) return;
    const c = scenario.config as Record<string, unknown>;
    const next = { ...DEFAULT_FORM };
    if (typeof c.num_candidates === "number") next.num_candidates = c.num_candidates;
    if (typeof c.num_recruiters === "number") next.num_recruiters = c.num_recruiters;
    if (typeof c.num_hr === "number") next.num_hr = c.num_hr;
    if (typeof c.num_jobs === "number") next.num_jobs = c.num_jobs;
    if (typeof c.num_companies === "number") next.num_companies = String(c.num_companies);
    if (typeof c.candidates_per_job === "number") next.candidates_per_job = c.candidates_per_job;
    if (typeof c.hiring_difficulty === "string" && HIRING_DIFFICULTIES.includes(c.hiring_difficulty as HiringDifficulty)) {
      next.hiring_difficulty = c.hiring_difficulty as HiringDifficulty;
    }
    if (Array.isArray(c.skill_categories)) {
      next.skill_categories = (c.skill_categories as string[]).join(", ");
    }
    if (typeof c.include_screening === "boolean") next.include_screening = c.include_screening;
    if (typeof c.include_interviews === "boolean") next.include_interviews = c.include_interviews;
    if (typeof c.include_reports === "boolean") next.include_reports = c.include_reports;
    if (typeof c.include_agent_indexing === "boolean") next.include_agent_indexing = c.include_agent_indexing;
    if (typeof c.resume_format === "string") next.resume_format = c.resume_format as ResumeFormat;
    setForm(next);
  };

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const startRun = async () => {
    const seed = form.seed.trim() === "" ? null : Number(form.seed);
    const skillCategories = form.skill_categories
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 8);
    const body = {
      num_candidates: form.num_candidates,
      num_recruiters: form.num_recruiters,
      num_hr: form.num_hr,
      num_jobs: form.num_jobs,
      num_companies: form.num_companies.trim() === "" ? null : Number(form.num_companies),
      candidates_per_job: form.candidates_per_job,
      hiring_difficulty: form.hiring_difficulty,
      skill_categories: skillCategories,
      include_screening: form.include_screening,
      include_interviews: form.include_interviews,
      include_reports: form.include_reports,
      include_agent_indexing: form.include_agent_indexing,
      resume_format: form.resume_format,
      seed,
    };
    try {
      const run = selectedScenario
        ? await demoApi.generate({ ...body, scenario_slug: selectedScenario })
        : await demoApi.generateCustom({
            ...body,
            companies: form.companies.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 20),
            job_titles: form.job_titles.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 50),
          });
      addToast("Demo generation started", "success");
      setDetail(null);
      void loadStatus();
      if (run.id) {
        demoApi
          .getRunDetail(run.id)
          .then(setDetail)
          .catch(() => undefined);
      }
    } catch {
      addToast("Failed to start demo generation", "error");
    }
  };

  const handleReset = async () => {
    if (!window.confirm("This will delete ALL demo-generated data. Continue?")) return;
    setResetting(true);
    try {
      const res = await demoApi.reset();
      addToast(res.message || "Demo dataset reset", "success");
      setDetail(null);
      setExportData(null);
      void loadStatus();
    } catch {
      addToast("Failed to reset demo dataset", "error");
    } finally {
      setResetting(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const data = await demoApi.export();
      setExportData(data);
      addToast("Demo dataset exported", "success");
    } catch {
      addToast("Failed to export demo dataset", "error");
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (!status)
    return <div className="error-banner mt-10 mx-auto max-w-xl">Failed to load demo platform</div>;

  const latest = status.latest_run;
  const running = isActive(latest);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">AI Demo Center</h1>
          <p className="page-subtitle">
            Generate realistic demo data and simulate the full recruitment pipeline.
          </p>
        </div>
        <span className="badge-primary self-start">
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Sandbox
        </span>
      </div>

      {latest && (
        <div className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className={STATUS_STYLES[latest.status] ?? "badge-neutral"}>
                {statusLabel(latest.status)}
              </span>
              <span className="text-sm font-medium text-gray-700">
                <StageLabel stage={latest.current_stage} />
              </span>
              <span className="text-sm text-gray-500">{formatDate(latest.created_at)}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-2 w-40 overflow-hidden rounded-full bg-gray-100">
                <div
                  className={`h-full rounded-full bg-gradient-to-r from-primary-500 to-violet-500 transition-all duration-500 ease-smooth ${running ? "animate-pulse" : ""}`}
                  style={{ width: `${latest.progress}%` }}
                />
              </div>
              <span className="text-sm font-semibold text-gray-700">{latest.progress}%</span>
            </div>
          </div>
          {latest.stage_message && (
            <p className="mt-3 text-xs text-gray-500">{latest.stage_message}</p>
          )}
          {latest.error && <p className="error-banner mt-3 text-xs">{latest.error}</p>}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {[
          { label: "Companies", value: status.totals.companies ?? 0 },
          { label: "Candidates", value: status.totals.candidates ?? 0 },
          { label: "Jobs", value: status.totals.jobs ?? 0 },
          { label: "Applications", value: status.totals.applications ?? 0 },
          { label: "Screenings", value: status.totals.screenings ?? 0 },
          { label: "Interviews", value: status.totals.interviews ?? 0 },
          { label: "Offers", value: status.totals.offers ?? 0 },
          { label: "Hired", value: status.totals.hired ?? 0 },
          { label: "Resumes", value: status.totals.resumes ?? 0 },
          { label: "Reports", value: status.totals.reports ?? 0 },
          { label: "Users", value: status.totals.users ?? 0 },
          { label: "Runs", value: status.runs.length },
        ].map((item) => (
          <div key={item.label} className="card card-hover p-4">
            <p className="text-xs font-medium text-gray-500">{item.label}</p>
            <p className="mt-1 font-display text-2xl font-bold tracking-tight text-gray-900">
              {item.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="section-title flex items-center gap-2 text-base">
            <span className="rounded-lg bg-primary-50 p-1.5 text-primary-600">
              <PlayCircle className="h-4 w-4" aria-hidden="true" />
            </span>
            Start Generation
          </h2>
          <p className="mt-1 text-xs text-gray-500">
            Choose a scenario for a preset configuration, or leave it empty and customize below.
          </p>

          <div className="mt-4 space-y-4">
            <div>
              <label className="field-label" htmlFor="demo-scenario">
                Scenario
              </label>
              <select
                id="demo-scenario"
                className="field"
                value={selectedScenario}
                onChange={(e) => applyScenario(e.target.value)}
              >
                <option value="">Custom configuration</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </select>
              {selectedScenario &&
                (() => {
                  const scenario = scenarios.find((s) => s.slug === selectedScenario);
                  if (!scenario) return null;
                  return (
                    <p className="mt-1.5 text-xs text-gray-500">
                      {scenario.description}
                      {scenario.tags && scenario.tags.length > 0 && (
                        <span className="ml-2 text-gray-400">
                          {scenario.tags.map((t) => `#${t}`).join(" ")}
                        </span>
                      )}
                    </p>
                  );
                })()}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Candidates"
                type="number"
                min={1}
                max={100}
                value={form.num_candidates}
                onChange={(e) => set("num_candidates", Number(e.target.value))}
              />
              <Input
                label="Recruiters"
                type="number"
                min={0}
                max={20}
                value={form.num_recruiters}
                onChange={(e) => set("num_recruiters", Number(e.target.value))}
              />
              <Input
                label="HR Users"
                type="number"
                min={0}
                max={10}
                value={form.num_hr}
                onChange={(e) => set("num_hr", Number(e.target.value))}
              />
              <Input
                label="Jobs"
                type="number"
                min={1}
                max={30}
                value={form.num_jobs}
                onChange={(e) => set("num_jobs", Number(e.target.value))}
              />
              <Input
                label="Candidates per job"
                type="number"
                min={1}
                max={100}
                value={form.candidates_per_job}
                onChange={(e) => set("candidates_per_job", Number(e.target.value))}
              />
              <Input
                label="Companies (blank = auto)"
                type="number"
                min={1}
                max={20}
                value={form.num_companies}
                onChange={(e) => set("num_companies", e.target.value)}
              />
              <div>
                <label className="field-label" htmlFor="demo-difficulty">
                  Hiring difficulty
                </label>
                <select
                  id="demo-difficulty"
                  className="field"
                  value={form.hiring_difficulty}
                  onChange={(e) => set("hiring_difficulty", e.target.value as HiringDifficulty)}
                >
                  {HIRING_DIFFICULTIES.map((d) => (
                    <option key={d} value={d}>
                      {d.charAt(0).toUpperCase() + d.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <span className="field-label">Skill categories</span>
                <div className="mt-1 flex flex-wrap gap-2">
                  {SKILL_CATEGORY_OPTIONS.map((opt) => {
                    const selected = form.skill_categories
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean)
                      .includes(opt.value);
                    return (
                      <label
                        key={opt.value}
                        className={`chip cursor-pointer ${selected ? "border-primary-300 bg-primary-50 text-primary-700" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={(e) => {
                            const current = form.skill_categories
                              .split(",")
                              .map((s) => s.trim())
                              .filter(Boolean);
                            const next = e.target.checked
                              ? [...current, opt.value]
                              : current.filter((c) => c !== opt.value);
                            set("skill_categories", next.join(", "));
                          }}
                          className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                        {opt.label}
                      </label>
                    );
                  })}
                </div>
                <p className="mt-1.5 text-xs text-gray-400">
                  Leave empty to use the general technical skill pool.
                </p>
              </div>
              <div>
                <label className="field-label" htmlFor="demo-resume-format">
                  Resume format
                </label>
                <select
                  id="demo-resume-format"
                  className="field"
                  value={form.resume_format}
                  onChange={(e) => set("resume_format", e.target.value as ResumeFormat)}
                >
                  {RESUME_FORMATS.map((fmt) => (
                    <option key={fmt} value={fmt}>
                      {fmt.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="Seed (optional)"
                type="number"
                min={0}
                placeholder="Random"
                value={form.seed}
                onChange={(e) => set("seed", e.target.value)}
              />
            </div>

            {!selectedScenario && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input
                  label="Companies (comma separated)"
                  placeholder="Acme Corp, Globex, Initech"
                  value={form.companies}
                  onChange={(e) => set("companies", e.target.value)}
                />
                <Input
                  label="Job titles (comma separated)"
                  placeholder="Software Engineer, Data Analyst, Designer"
                  value={form.job_titles}
                  onChange={(e) => set("job_titles", e.target.value)}
                />
              </div>
            )}

            <div className="space-y-2">
              {[
                { key: "include_screening" as const, label: "Run AI screening" },
                { key: "include_interviews" as const, label: "Simulate interviews" },
                { key: "include_reports" as const, label: "Generate analytics reports" },
                { key: "include_agent_indexing" as const, label: "Index agent knowledge" },
              ].map((item) => (
                <label
                  key={item.key}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-gray-700 transition-colors hover:bg-primary-50/50"
                >
                  <input
                    type="checkbox"
                    checked={form[item.key]}
                    onChange={(e) => set(item.key, e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  {item.label}
                </label>
              ))}
            </div>

            <Button onClick={() => void startRun()} disabled={running} isLoading={running} className="w-full">
              {running ? "Generating..." : "Start Demo Generation"}
            </Button>
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-5">
            <h2 className="section-title flex items-center gap-2 text-base">
              <span className="rounded-lg bg-violet-50 p-1.5 text-violet-600">
                <History className="h-4 w-4" aria-hidden="true" />
              </span>
              Run History
            </h2>
            {status.runs.length === 0 ? (
              <div className="empty-state mt-3">
                <History className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
                <h3 className="text-base font-semibold text-gray-900">No demo runs yet.</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Start a generation to see the run history here.
                </p>
              </div>
            ) : (
              <div className="mt-3 space-y-2">
                {status.runs.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => {
                      demoApi
                        .getRunDetail(run.id)
                        .then(setDetail)
                        .catch(() => addToast("Failed to load run details", "error"));
                    }}
                    className="flex w-full items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white/70 px-3 py-2.5 text-left text-sm transition-all duration-200 hover:border-primary-300 hover:bg-primary-50/50 hover:shadow-soft"
                  >
                    <span className="flex items-center gap-2">
                      <span className={STATUS_STYLES[run.status] ?? "badge-neutral"}>
                        {statusLabel(run.status)}
                      </span>
                      <span className="text-gray-700">
                        <StageLabel stage={run.current_stage} />
                      </span>
                    </span>
                    <span className="text-xs text-gray-400">{formatDate(run.created_at)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="card p-5">
            <h2 className="section-title flex items-center gap-2 text-base">
              <span className="rounded-lg bg-sky-50 p-1.5 text-sky-600">
                <ListChecks className="h-4 w-4" aria-hidden="true" />
              </span>
              Current Run Events
            </h2>
            {!detail ? (
              <p className="mt-3 text-sm text-gray-500">
                {running ? "Loading run events..." : "Select a run to view its events."}
              </p>
            ) : (
              <>
                <div className="mt-2 flex items-center gap-2 text-sm text-gray-600">
                  <span className="font-semibold">{detail.run.progress}%</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                    <div
                      className={`h-full rounded-full bg-gradient-to-r from-primary-500 to-violet-500 transition-all duration-500 ease-smooth ${isActive(detail.run) ? "animate-pulse" : ""}`}
                      style={{ width: `${detail.run.progress}%` }}
                    />
                  </span>
                  <StageLabel stage={detail.run.current_stage} />
                </div>
                <ul className="mt-4 max-h-64 space-y-1 overflow-y-auto text-sm">
                  {detail.events.length === 0 ? (
                    <li className="text-gray-500">No events recorded yet.</li>
                  ) : (
                    detail.events.map((event) => (
                      <li
                        key={event.id}
                        className="flex items-start gap-2.5 border-b border-gray-100 py-2 last:border-0"
                      >
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-400" />
                        <div>
                          <p className="text-gray-700">{event.message}</p>
                          {event.details && (
                            <p className="mt-0.5 text-xs text-gray-400">
                              {JSON.stringify(event.details)}
                            </p>
                          )}
                        </div>
                      </li>
                    ))
                  )}
                </ul>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
        <div>
          <h2 className="section-title flex items-center gap-2 text-base">
            <span className="rounded-lg bg-red-50 p-1.5 text-red-600">
              <Boxes className="h-4 w-4" aria-hidden="true" />
            </span>
            Dataset Tools
          </h2>
          <p className="mt-1 text-xs text-gray-500">
            Export the current demo dataset as JSON, or wipe all demo-generated data.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => void handleExport()} isLoading={exporting}>
            <Download className="h-4 w-4" aria-hidden="true" />
            {exporting ? "Exporting..." : "Export Dataset"}
          </Button>
          <Button variant="danger" onClick={() => void handleReset()} isLoading={resetting}>
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {resetting ? "Resetting..." : "Reset Demo Data"}
          </Button>
        </div>
      </div>

      {exportData && (
        <div className="card p-5">
          <h2 className="section-title text-base">Export Preview</h2>
          <p className="mt-1 text-xs text-gray-500">
            Generated {formatDate(exportData.generated_at)}.{" "}
            {exportData.summary && typeof exportData.summary === "object"
              ? Object.entries(exportData.summary)
                  .map(([k, v]) => `${k}: ${String(v)}`)
                  .join(" · ")
              : ""}
          </p>
          <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-gray-950 p-4 font-mono text-xs text-gray-100">
            {JSON.stringify(exportData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
