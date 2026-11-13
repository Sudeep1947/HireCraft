import { useEffect, useState } from "react";
import { ArrowRight, GraduationCap } from "lucide-react";
import { skill2jobApi } from "../../../api/skill2job";
import type { TrainingModule, TrainingPlan, TrainingProgress } from "../../../types/skill2job";

export function LearningSection() {
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [progress, setProgress] = useState<TrainingProgress | null>(null);

  async function refresh() {
    try {
      const [p, pr] = await Promise.all([
        skill2jobApi.getTrainingPlan(),
        skill2jobApi.getTrainingProgress(),
      ]);
      setPlan(p);
      setProgress(pr);
    } catch {
      setPlan(null);
      setProgress(null);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function complete(m: TrainingModule) {
    await skill2jobApi.completeModule(m.module_key);
    await refresh();
  }

  const completedKeys = new Set(progress?.items.map((i) => i.module_key) ?? []);

  return (
    <div className="space-y-6">
      <section className="card p-6">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
              <GraduationCap className="h-5 w-5" aria-hidden="true" />
            </span>
            Training Plan
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            A grounded learning plan built only from official provider resources that target your
            real skill gaps. Mark modules complete to track your progress.
          </p>
        </div>
      </section>

      {plan && plan.modules.length > 0 && (
        <section className="card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900">Learning Modules</h3>
            <span className="badge badge-neutral">{plan.version}</span>
          </div>
          <ul className="mt-4 divide-y divide-gray-100">
            {plan.modules.map((m) => {
              const done = completedKeys.has(m.module_key);
              return (
                <li key={m.module_key} className="flex items-center justify-between gap-4 py-3 transition-colors hover:bg-gray-50/60">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-gray-900">
                      {m.title}
                      {done && <span className="badge badge-success ml-2">done</span>}
                    </p>
                    <p className="text-xs text-gray-500">
                      {m.skill} · {m.provider} · {m.resource_type}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {m.url && (
                      <a
                        href={m.url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-secondary btn-sm inline-flex items-center gap-1"
                      >
                        Open resource <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                      </a>
                    )}
                    {!done && (
                      <button
                        type="button"
                        onClick={() => complete(m)}
                        className="btn-primary btn-sm"
                      >
                        Mark complete
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {plan && plan.modules.length === 0 && (
        <div className="empty-state">
          <GraduationCap className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm text-gray-500">No training plan yet — run the pipeline or matching to surface skill gaps.</p>
        </div>
      )}
    </div>
  );
}
