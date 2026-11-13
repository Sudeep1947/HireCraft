import { useEffect, useState } from "react";
import { Briefcase, RefreshCw } from "lucide-react";
import { skill2jobApi } from "../../../api/skill2job";
import type { CuratedJob, CuratedJobCounts } from "../../../types/skill2job";
import { SnapshotStat } from "./shared";

export function JobsSection() {
  const [jobs, setJobs] = useState<CuratedJob[]>([]);
  const [counts, setCounts] = useState<CuratedJobCounts | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const [cat, cnt] = await Promise.all([
        skill2jobApi.getCatalog({ limit: 12 }),
        skill2jobApi.getJobCounts(),
      ]);
      setJobs(cat.jobs);
      setCounts(cnt);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
              <Briefcase className="h-5 w-5" aria-hidden="true" />
            </span>
            Curated Local Job Catalog
          </h2>
          <p className="mt-1 text-sm text-gray-500">Real local openings served by the job intelligence endpoint.</p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={load}
          className="btn-secondary"
        >
          <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {counts && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SnapshotStat label="Total jobs" value={counts.total} />
          <SnapshotStat label="Remote" value={counts.remote} />
          <SnapshotStat label="On-site" value={counts.on_site} />
          <div className="rounded-xl border border-gray-100 bg-gray-50/80 p-3 shadow-xs">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Top location</p>
            <p className="mt-0.5 text-sm font-bold text-gray-800">{counts.top_locations[0]?.location ?? "—"}</p>
          </div>
        </div>
      )}

      {failed ? (
        <p className="mt-4 text-sm text-gray-500">No job catalog available yet.</p>
      ) : (
        <ul className="mt-4 divide-y divide-gray-100">
          {jobs.map((j) => (
            <li key={j.id} className="flex items-start justify-between gap-4 py-4 transition-colors hover:bg-gray-50/60">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-gray-900">{j.title}</p>
                <p className="text-xs text-gray-500">
                  {j.company} · {j.location ?? "Remote"} · {j.remote_type ?? "job"}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {j.required_skills.slice(0, 8).map((s) => (
                    <span key={s} className="badge badge-neutral">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-sm font-extrabold text-primary-700">{j.salary_range ?? "—"}</p>
                <p className="text-xs text-gray-400">{j.experience_required ?? ""}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
