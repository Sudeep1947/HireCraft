import { Brain, Briefcase, Loader2, Sparkles } from "lucide-react";
import type { Skill2JobOverview } from "../../../types/skill2job";

export default function CareerHero({
  overview,
  onAnalyze,
  analyzing,
}: {
  overview: Skill2JobOverview | null;
  onAnalyze: () => void;
  analyzing: boolean;
}) {
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="panel-dark relative overflow-hidden p-6 sm:p-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(70%_60%_at_85%_0%,rgba(255,255,255,0.18),transparent)]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -left-20 -bottom-24 h-64 w-64 rounded-full bg-white/10 blur-3xl"
        aria-hidden="true"
      />
      <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="space-y-3">
          <p className="section-label flex items-center gap-1.5 text-primary-200">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            Skill2Job Career Intelligence
          </p>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
            {greeting}
          </h1>
          <p className="max-w-xl text-lg text-primary-100">
            Turn your skills into your next opportunity.
          </p>
          <p className="max-w-lg text-sm leading-relaxed text-primary-200">
            Skill2Job analyzes your profile, discovers relevant local jobs,
            identifies the skills you're missing, and creates a measurable path
            toward job readiness.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={onAnalyze}
              disabled={analyzing}
              className="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-primary-700 shadow-lg transition-all duration-200 hover:bg-primary-50 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60 active:scale-[0.98]"
            >
              {analyzing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Brain className="h-4 w-4" />
              )}
              {analyzing ? "Analyzing..." : "Analyze My Profile"}
            </button>
            <button
              onClick={() =>
                document
                  .getElementById("local-opportunities")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
              className="inline-flex items-center gap-2 rounded-lg border border-white/30 px-5 py-2.5 text-sm font-semibold text-white transition-all duration-200 hover:bg-white/10 active:scale-[0.98]"
            >
              <Briefcase className="h-4 w-4" />
              Explore Local Jobs
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-3 md:text-right">
          <div className="rounded-xl border border-white/15 bg-white/10 px-5 py-3 backdrop-blur">
            <div className="text-xs text-primary-200">Profile completeness</div>
            <div className="font-display text-3xl font-bold text-white">
              {overview?.profile.completeness ?? 0}%
            </div>
          </div>
          {overview?.last_analyzed && (
            <div className="rounded-xl border border-white/15 bg-white/10 px-5 py-3 backdrop-blur">
              <div className="text-xs text-primary-200">Last analyzed</div>
              <div className="text-sm font-semibold text-white">
                {new Date(overview.last_analyzed).toLocaleDateString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                  day: "numeric",
                  month: "short",
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
