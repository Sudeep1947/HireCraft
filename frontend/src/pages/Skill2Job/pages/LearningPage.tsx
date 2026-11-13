import { useEffect, useState, useCallback } from "react";
import {
  GraduationCap,
  Clock,
  IndianRupee,
  TrendingUp,
  Zap,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import { skill2jobApi } from "../../../api/skill2job";
import type {
  LearningPlanForJob,
  OverviewTimeToReadyItem,
} from "../../../types/skill2job";

const HOURS_OPTIONS = [5, 10, 15, 20, 30, 40];
const MODES = ["fastest", "balanced", "lowest_cost", "free_only"] as const;
const MODE_LABELS: Record<string, string> = {
  fastest: "Fastest",
  balanced: "Balanced",
  lowest_cost: "Lowest Cost",
  free_only: "Free Only",
};

export default function LearningPage() {
  const [matchedJobs, setMatchedJobs] = useState<OverviewTimeToReadyItem[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [hoursPerWeek, setHoursPerWeek] = useState(10);
  const [mode, setMode] = useState<string>("fastest");
  const [plan, setPlan] = useState<LearningPlanForJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [jobsLoading, setJobsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setJobsLoading(true);
        const jobs = await skill2jobApi.compareJobs();
        if (!cancelled) {
          setMatchedJobs(jobs);
          if (jobs.length > 0 && selectedJobId === null) {
            setSelectedJobId(jobs[0].job_id);
          }
        }
      } catch {
        if (!cancelled) setError("Failed to load matched jobs.");
      } finally {
        if (!cancelled) setJobsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const fetchPlan = useCallback(async () => {
    if (selectedJobId === null) return;
    setLoading(true);
    setError(null);
    setPlan(null);
    try {
      const freeOnly = mode === "free_only";
      const res = await skill2jobApi.getLearningPlanForJob(selectedJobId, {
        hours_per_week: hoursPerWeek,
        free_only: freeOnly,
        optimization_mode: freeOnly ? undefined : mode,
      });
      setPlan(res);
    } catch {
      setError("Failed to load learning plan.");
    } finally {
      setLoading(false);
    }
  }, [selectedJobId, hoursPerWeek, mode]);

  useEffect(() => {
    if (selectedJobId !== null) fetchPlan();
  }, [selectedJobId, fetchPlan]);

  const toggleStep = (idx: number) => {
    setExpandedStep((prev) => (prev === idx ? null : idx));
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <span className="section-label">Learn</span>
          <h1 className="page-title mt-1 flex items-center gap-3">
            <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
              <GraduationCap className="h-5 w-5" aria-hidden="true" />
            </span>
            Learning Plan
          </h1>
        </div>
      </div>

      {/* Controls */}
      <div className="card p-6 space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[220px]">
            <label className="field-label" htmlFor="learning-target-job">
              Target Job
            </label>
            {jobsLoading ? (
              <div className="skeleton mt-1.5 h-10 w-full" />
            ) : matchedJobs.length === 0 ? (
              <p className="text-sm text-gray-500">No matched jobs found.</p>
            ) : (
              <select
                id="learning-target-job"
                value={selectedJobId ?? ""}
                onChange={(e) => {
                  setSelectedJobId(e.target.value);
                  setExpandedStep(null);
                }}
                className="field"
              >
                {matchedJobs.map((j) => (
                  <option key={j.job_id} value={j.job_id}>
                    {j.job_title} — {j.missing_skills_count} gaps, ~{j.estimated_weeks}w
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="w-40">
            <label className="field-label" htmlFor="learning-hours">
              Hours / Week
            </label>
            <select
              id="learning-hours"
              value={hoursPerWeek}
              onChange={(e) => setHoursPerWeek(Number(e.target.value))}
              className="field"
            >
              {HOURS_OPTIONS.map((h) => (
                <option key={h} value={h}>
                  {h}h
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                setExpandedStep(null);
              }}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
                mode === m
                  ? "bg-brand-gradient text-white shadow-glow-sm"
                  : "border border-gray-200 bg-white text-gray-600 shadow-xs hover:border-primary-300 hover:text-primary-700"
              }`}
            >
              {MODE_LABELS[m] ?? m}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-16">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="error-banner" role="alert">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && !plan && matchedJobs.length > 0 && (
        <p className="py-12 text-center text-sm text-gray-400">
          Select a job and configure options to see your learning plan.
        </p>
      )}

      {/* Plan Content */}
      {!loading && !error && plan && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryCard
              icon={<TrendingUp className="h-5 w-5 text-primary-600" />}
              label="Readiness"
              value={`${Math.round(plan.current_readiness)}%`}
            />
            <SummaryCard
              icon={<Clock className="h-5 w-5 text-sky-600" />}
              label="Est. Weeks"
              value={String(plan.total_weeks)}
            />
            <SummaryCard
              icon={<IndianRupee className="h-5 w-5 text-emerald-600" />}
              label="Est. Cost"
              value={`₹${plan.total_cost.toLocaleString()}`}
            />
            <SummaryCard
              icon={<GraduationCap className="h-5 w-5 text-amber-600" />}
              label="Jobs Unlocked"
              value={`${plan.opportunity_unlock.current_jobs} → ${plan.opportunity_unlock.projected_jobs}`}
            />
          </div>

          {/* Free Only Comparison */}
          {mode !== "free_only" && plan.free_only_path && (
            <div className="panel-brand p-6">
              <h2 className="mb-4 font-display text-lg font-semibold tracking-tight text-gray-900">
                Free Only Path
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Weeks</p>
                  <p className="font-semibold text-gray-900">{plan.free_only_path.weeks}</p>
                </div>
                <div>
                  <p className="text-gray-500">Hours</p>
                  <p className="font-semibold text-gray-900">{plan.free_only_path.hours}</p>
                </div>
                <div>
                  <p className="text-gray-500">Cost</p>
                  <p className="font-semibold text-emerald-600">₹{plan.free_only_path.cost.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-gray-500">Coverage</p>
                  <p className="font-semibold text-gray-900">{Math.round(plan.free_only_path.coverage_pct)}%</p>
                </div>
              </div>
              {plan.free_only_path.remaining_gaps.length > 0 && (
                <p className="mt-3 text-sm text-amber-700">
                  Remaining gaps (free): {plan.free_only_path.remaining_gaps.join(", ")}
                </p>
              )}
            </div>
          )}

          {/* Missing Skills */}
          {plan.missing_skills.length > 0 && (
            <div className="card p-6">
              <h2 className="mb-4 font-display text-lg font-semibold tracking-tight text-gray-900">
                Missing Skills
              </h2>
              <div className="flex flex-wrap gap-2">
                {plan.missing_skills.map((skill) => (
                  <span
                    key={skill.skill}
                    className={`badge ${
                      skill.priority === "high"
                        ? "badge-danger"
                        : skill.priority === "medium"
                        ? "badge-warning"
                        : "badge-neutral"
                    }`}
                  >
                    {skill.skill}
                    <span className="ml-1 text-xs opacity-70">
                      ({skill.priority})
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Learning Steps */}
          {plan.learning_plan.length === 0 ? (
            <div className="empty-state">
              <Zap className="mb-3 h-10 w-10 text-primary-400" aria-hidden="true" />
              <p className="font-medium text-gray-900">
                You are already well-matched for this role!
              </p>
              <p className="mt-1 text-sm text-gray-500">
                No additional learning steps recommended.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <h2 className="font-display text-lg font-semibold tracking-tight text-gray-900">
                Learning Steps
              </h2>
              {plan.learning_plan.map((step, idx) => {
                const isOpen = expandedStep === idx;
                return (
                  <div
                    key={idx}
                    className="card card-hover overflow-hidden"
                  >
                    <button
                      onClick={() => toggleStep(idx)}
                      className="flex w-full items-center gap-4 p-5 text-left transition-colors hover:bg-gray-50"
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-sm font-bold text-white">
                        {step.step_number}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="truncate font-medium text-gray-900">
                          {step.resource_title}
                        </p>
                        <p className="text-sm text-gray-500">
                          {step.resource_provider} &middot; {step.weeks}w
                          {step.cost > 0
                            ? ` · ₹${step.cost.toLocaleString()}`
                            : " · Free"}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {step.is_free && (
                          <span className="badge badge-success">
                            Free
                          </span>
                        )}
                        {step.can_parallel && (
                          <span className="badge badge-info">
                            Parallel
                          </span>
                        )}
                        {isOpen ? (
                          <ChevronUp className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-gray-400" />
                        )}
                      </div>
                    </button>

                    {isOpen && (
                      <div className="space-y-3 border-t border-gray-100 px-5 pb-5 pt-4">
                        {step.explanation && (
                          <p className="text-sm leading-relaxed text-gray-600">
                            {step.explanation}
                          </p>
                        )}
                        {step.resource_url && (
                          <a
                            href={step.resource_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700"
                          >
                            Open Resource
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center gap-2">
        {icon}
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className="font-display text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
