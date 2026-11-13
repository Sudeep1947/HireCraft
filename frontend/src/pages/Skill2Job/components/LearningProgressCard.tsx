import { BookOpen, CheckCircle2 } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function LearningProgressCard({ overview }: { overview: Skill2JobOverview }) {
  const progress = overview.learning_progress;
  const total = progress.total_modules;
  const completed = progress.completed;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
          <BookOpen className="h-5 w-5" aria-hidden="true" />
        </span>
        <h2 className="section-title">Learning Progress</h2>
      </div>
      {total === 0 ? (
        <div className="empty-state py-10">
          <BookOpen className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm font-medium text-gray-700">You haven&apos;t started your learning plan yet.</p>
          <p className="mt-1 text-xs text-gray-500">Select a target job to generate your learning path.</p>
        </div>
      ) : (
        <>
          <div className="mb-4">
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className="text-gray-600">Overall Progress</span>
              <span className="font-display font-bold text-gray-900">{pct}%</span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-brand-gradient transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-1.5 text-xs text-gray-400">{completed}/{total} modules completed</div>
          </div>
          <div className="space-y-1">
            {progress.items.slice(0, 4).map((item) => (
              <div
                key={item.module_key}
                className="flex items-center justify-between gap-3 rounded-lg border-b border-gray-100 py-2 last:border-0 last:rounded-none"
              >
                <div className="flex min-w-0 items-center gap-2">
                  {item.status === "completed" ? (
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-500" aria-hidden="true" />
                  ) : (
                    <div className="h-4 w-4 flex-shrink-0 rounded-full border-2 border-gray-300" aria-hidden="true" />
                  )}
                  <span className="truncate text-sm text-gray-700">{item.title || item.skill}</span>
                </div>
                <span className="flex-shrink-0 text-xs text-gray-400">{item.provider}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
