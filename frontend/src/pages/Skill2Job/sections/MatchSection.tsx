import { useEffect, useState } from "react";
import { Play, Target } from "lucide-react";
import { skill2jobApi } from "../../../api/skill2job";
import type { JobMatchEntry } from "../../../types/skill2job";

export function MatchSection() {
  const [matches, setMatches] = useState<JobMatchEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [ran, setRan] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const res = await skill2jobApi.runMatching({ limit: 10 });
      setMatches(res);
      setRan(true);
    } catch {
      setRan(false);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    skill2jobApi
      .getMatches(10)
      .then(setMatches)
      .catch(() => undefined);
  }, []);

  return (
    <section className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
              <Target className="h-5 w-5" aria-hidden="true" />
            </span>
            Semantic Job Matching
          </h2>
          <p className="mt-1 max-w-xl text-sm text-gray-500">
            Scores the catalog against your profile using the existing MatchingEngine (skills,
            experience, education, projects, certifications, location, employment type).
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={run}
          className="btn-primary"
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {busy ? "Scoring…" : "Run matching"}
        </button>
      </div>

      {ran && matches.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">No matches computed. Ensure your profile has skills and the catalog is seeded.</p>
      )}
      {matches.length === 0 && !ran ? (
        <p className="mt-4 text-sm text-gray-500">
          No persisted matches yet. Press “Run matching” to score your profile against the catalog.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-gray-100">
          {matches.map((m) => (
            <li key={m.job_id} className="flex items-start justify-between gap-4 py-4 transition-colors hover:bg-gray-50/60">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-gray-900">{m.title}</p>
                <p className="text-xs text-gray-500">{m.company} · {m.location ?? "Remote"}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.matched_skills.slice(0, 6).map((s) => (
                    <span key={s} className="badge badge-success">
                      {s}
                    </span>
                  ))}
                  {m.missing_required.slice(0, 4).map((s) => (
                    <span key={s} className="badge badge-danger">
                      missing {s}
                    </span>
                  ))}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-display text-2xl font-extrabold text-primary-700">{m.overall_score}</p>
                <p className="text-xs text-gray-400">{m.strength_level}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
