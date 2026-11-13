import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { ApplicationFairnessContextCard } from "../../components/screening/ApplicationFairnessContextCard";
import { getApplicationScreeningDetail } from "../../api/screening";
import { getErrorMessage } from "../../utils/error";
import type {
  ApplicationScreeningDetailResponse,
  EvidenceGapInsight,
  FitRequirementResult,
  HiringRecommendation,
  JobContextBlock,
  MatchStatus,
  ReviewFlag,
  ScreeningDimensionScore,
  ScreeningQuestionSuggestion,
  SkillAssessment,
  StrengthInsight,
  StrengthLevel,
} from "../../types/screening";

const STATUS_LABELS: Record<string, string> = {
  applied: "Applied",
  under_review: "Under Review",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview Scheduled",
  interviewed: "Interviewed",
  offered: "Offered",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const SCREENING_STATE_LABELS: Record<string, string> = {
  not_started: "Not screened",
  queued: "Queued",
  processing: "Running",
  running: "Running",
  completed: "Screened",
  failed: "Failed",
  skipped: "Skipped",
};

const SCREENING_STATE_STYLES: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-700",
  queued: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  skipped: "bg-gray-100 text-gray-600",
};

const RECOMMENDATION_LABELS: Record<HiringRecommendation, string> = {
  strongly_recommend: "Strongly Recommend",
  recommend: "Recommend",
  consider: "Consider",
  not_recommended: "Not Recommended",
};

const RECOMMENDATION_STYLES: Record<HiringRecommendation, string> = {
  strongly_recommend: "bg-green-100 text-green-800",
  recommend: "bg-blue-100 text-blue-800",
  consider: "bg-yellow-100 text-yellow-800",
  not_recommended: "bg-red-100 text-red-800",
};

const STRENGTH_LABELS: Record<StrengthLevel, string> = {
  excellent: "Excellent",
  good: "Good",
  average: "Average",
  low: "Low",
};

const MATCH_STATUS_LABELS: Record<MatchStatus, string> = {
  match: "Met",
  partial: "Partial",
  gap: "Gap",
  unknown: "Unknown",
};

const MATCH_STATUS_STYLES: Record<MatchStatus, string> = {
  match: "bg-green-100 text-green-800",
  partial: "bg-yellow-100 text-yellow-800",
  gap: "bg-red-100 text-red-800",
  unknown: "bg-gray-100 text-gray-700",
};

const SKILL_DEPTH_LABELS: Record<string, string> = {
  expert_level_evidence: "Expert-level evidence",
  strong: "Strong evidence",
  moderate: "Moderate evidence",
  limited: "Limited evidence",
  mention_only: "Mention only",
  no_evidence: "No evidence",
};

const cardClass = "rounded-lg border bg-white p-5";
const sectionTitleClass = "text-sm font-semibold text-gray-900";
const hintClass = "mt-0.5 text-xs text-gray-500";

function formatDate(value: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function scoreBarColor(score: number): string {
  if (score >= 80) return "bg-green-500";
  if (score >= 60) return "bg-yellow-500";
  if (score >= 40) return "bg-orange-500";
  return "bg-red-500";
}

function SectionCard({
  title,
  hint,
  action,
  children,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className={cardClass}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className={sectionTitleClass}>{title}</h3>
          {hint && <p className={hintClass}>{hint}</p>}
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function UnavailableSection({ reason }: { reason: string | null }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-600">
      <p className="font-medium text-gray-700">Not available</p>
      <p className="mt-1">{reason || "No stored data is available for this application."}</p>
    </div>
  );
}

function ChipList({ items, tone }: { items: string[]; tone: "green" | "red" | "gray" }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-500">None recorded</p>;
  }
  const toneClass =
    tone === "green"
      ? "bg-green-50 text-green-800"
      : tone === "red"
        ? "bg-red-50 text-red-800"
        : "bg-gray-100 text-gray-700";
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li key={item} className={`rounded-full px-2.5 py-1 text-xs font-medium ${toneClass}`}>
          {item}
        </li>
      ))}
    </ul>
  );
}

function RequirementRow({ requirement }: { requirement: FitRequirementResult }) {
  return (
    <li className="border-t py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900">{requirement.requirement}</p>
          <p className="text-xs text-gray-500">
            {[requirement.requirement_type, requirement.level, requirement.category]
              .filter(Boolean)
              .join(" &middot; ")}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              MATCH_STATUS_STYLES[requirement.status] ?? "bg-gray-100 text-gray-700"
            }`}
          >
            {MATCH_STATUS_LABELS[requirement.status] ?? requirement.status}
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
            {(requirement.evidence_strength ?? "none").replace(/_/g, " ")}
          </span>
        </div>
      </div>
      {requirement.reason && <p className="mt-1 text-xs text-gray-600">{requirement.reason}</p>}
      {requirement.evidence && requirement.evidence.length > 0 && (
        <ul className="mt-2 space-y-1">
          {requirement.evidence.map((item, index) => (
            <li key={`${item.source}-${index}`} className="text-xs text-gray-600">
              <span className="font-medium text-gray-700">{item.source.replace(/_/g, " ")}</span>
              {item.quote ? <span> &mdash; &ldquo;{item.quote}&rdquo;</span> : null}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function SkillRow({ assessment }: { assessment: SkillAssessment }) {
  return (
    <li className="border-t py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-gray-900">{assessment.skill}</p>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
          {SKILL_DEPTH_LABELS[assessment.depth] ?? assessment.depth}
        </span>
      </div>
      {assessment.reason && <p className="mt-1 text-xs text-gray-600">{assessment.reason}</p>}
    </li>
  );
}

function StrengthRow({ insight }: { insight: StrengthInsight }) {
  return (
    <li className="border-t py-3 first:border-t-0 first:pt-0">
      <p className="text-sm font-medium text-gray-900">{insight.title}</p>
      {insight.reason && <p className="mt-1 text-xs text-gray-600">{insight.reason}</p>}
    </li>
  );
}

function GapRow({ gap }: { gap: EvidenceGapInsight }) {
  return (
    <li className="border-t py-3 first:border-t-0 first:pt-0">
      <p className="text-sm font-medium text-gray-900">{gap.skill}</p>
      <p className="mt-0.5 text-xs text-gray-500">
        {SKILL_DEPTH_LABELS[gap.current_depth] ?? gap.current_depth}
      </p>
      {gap.note && <p className="mt-1 text-xs text-gray-600">{gap.note}</p>}
    </li>
  );
}

function FlagRow({ flag }: { flag: ReviewFlag }) {
  return (
    <li className="border-t py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-gray-900">{flag.title}</p>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            flag.severity === "warning" ? "bg-yellow-100 text-yellow-800" : "bg-gray-100 text-gray-700"
          }`}
        >
          {flag.severity}
        </span>
      </div>
      {flag.description && <p className="mt-1 text-xs text-gray-600">{flag.description}</p>}
      {flag.possible_explanation && (
        <p className="mt-1 text-xs text-gray-500">{flag.possible_explanation}</p>
      )}
    </li>
  );
}

function QuestionList({ questions }: { questions: ScreeningQuestionSuggestion[] }) {
  if (!questions || questions.length === 0) {
    return <p className="text-sm text-gray-500">None recorded</p>;
  }
  return (
    <ol className="list-decimal space-y-2 pl-5">
      {questions.map((question, index) => (
        <li key={`${question.topic}-${index}`} className="text-sm text-gray-700">
          <span className="font-medium text-gray-900">{question.question}</span>
          <span className="block text-xs text-gray-500">{question.reason}</span>
        </li>
      ))}
    </ol>
  );
}

function BreakdownList({ items }: { items: ScreeningDimensionScore[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-500">No stored dimension scores for this application.</p>;
  }
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.key}>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-700">{item.label}</span>
            <span className="font-semibold text-gray-900">{item.score}</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full ${scoreBarColor(item.score)}`}
              style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function JobContextSection({ context }: { context: JobContextBlock }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-gray-50 p-3 text-sm text-gray-700">
        <p>{context.summary.text}</p>
        <p className="mt-1 text-xs text-gray-500">
          {context.summary.source.replace(/_/g, " ")} &middot; {context.summary.disclaimer}
        </p>
      </div>
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Requirement gaps
        </h4>
        <div className="mt-2">
          <ChipList items={context.requirement_gaps ?? []} tone="red" />
        </div>
      </div>
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Not enough information
        </h4>
        <div className="mt-2">
          <ChipList items={context.requirement_unknown ?? []} tone="gray" />
        </div>
      </div>
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Suggested questions
        </h4>
        <div className="mt-2">
          <QuestionList questions={context.additional_questions ?? []} />
        </div>
      </div>
    </div>
  );
}

function ScreeningStateBanner({ detail }: { detail: ApplicationScreeningDetailResponse }) {
  const state = detail.application.screening.effective_status;
  const { error, attempts, task_id: taskId } = detail.application.screening;

  if (state === "completed" && detail.screening_result) return null;

  const tone =
    state === "failed"
      ? "border-red-200 bg-red-50 text-red-800"
      : "border-blue-200 bg-blue-50 text-blue-800";
  const headline =
    state === "failed"
      ? "Screening failed"
      : state === "queued"
        ? "Screening is queued"
        : state === "processing" || state === "running"
          ? "Screening is running"
          : "Not screened yet";

  return (
    <div className={`rounded-lg border p-4 ${tone}`}>
      <p className="text-sm font-semibold">{headline}</p>
      <p className="mt-1 text-sm">
        {error
          ? error
          : "No screening score exists for this application yet. Scores appear here once screening completes."}
      </p>
      <p className="mt-2 text-xs">
        Attempts: {attempts}
        {taskId ? ` \u00b7 Task ${taskId}` : ""}
      </p>
    </div>
  );
}

export function RecruiterScreeningDetail() {
  const { jobId, applicationId } = useParams<{
    jobId: string;
    applicationId: string;
  }>();
  const [detail, setDetail] = useState<ApplicationScreeningDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError(null);
    setAccessDenied(null);
    try {
      const data = await getApplicationScreeningDetail(applicationId);
      setDetail(data);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        setAccessDenied(getErrorMessage(err, "You do not have access to this application."));
      } else {
        setError(getErrorMessage(err, "Failed to load screening details."));
      }
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  if (accessDenied) {
    return (
      <div className="mx-auto max-w-2xl py-12 text-center">
        <div className="rounded-lg border border-red-200 bg-red-50 p-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">Access denied</p>
          <p className="mt-2 text-sm text-red-700">{accessDenied}</p>
          <Link
            to={`/recruiter/jobs/${jobId}/applicants`}
            className="mt-5 inline-block rounded-lg border border-primary-600 px-3 py-1.5 text-sm font-medium text-primary-600 hover:bg-primary-50"
          >
            Back to applicants
          </Link>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="mx-auto max-w-2xl py-12 text-center">
        <div className="rounded-lg border border-red-200 bg-red-50 p-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Could not load screening detail
          </p>
          <p className="mt-2 text-sm text-red-700">
            {error || "An unexpected error occurred while loading this application."}
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Button variant="secondary" onClick={() => void load()}>
              Try again
            </Button>
            <Link
              to={`/recruiter/jobs/${jobId}/applicants`}
              className="inline-flex items-center rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Back to applicants
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const { application, candidate, job, screening_result: screening, freshness } = detail;
  const screeningState = application.screening.effective_status;
  const fit = detail.fit;
  const evidence = detail.evidence_intelligence;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <Link
            to={`/recruiter/jobs/${jobId}/applicants`}
            className="text-xs font-medium text-primary-600 hover:underline"
          >
            &larr; Back to applicants
          </Link>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">{candidate.name || "Candidate"}</h1>
          <p className="text-sm text-gray-500">
            {job.title} &middot; {job.company}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-800">
            {STATUS_LABELS[application.status] || application.status.replace(/_/g, " ")}
          </span>
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
              SCREENING_STATE_STYLES[screeningState] ?? "bg-gray-100 text-gray-800"
            }`}
          >
            Screening: {SCREENING_STATE_LABELS[screeningState] ?? screeningState.replace(/_/g, " ")}
          </span>
          <Link
            to={`/recruiter/jobs/${jobId}/applicants/${application.id}/explanation`}
            className="inline-flex items-center rounded-lg border border-primary-600 px-2.5 py-1.5 text-sm font-medium text-primary-600 hover:bg-primary-50"
          >
            Why this score?
          </Link>
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
        </div>
      </div>

      <ScreeningStateBanner detail={detail} />

      {freshness.resume_matches_application === false && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
          The candidate has uploaded a newer resume since this screening ran. The stored scores below
          describe the earlier resume.
        </div>
      )}

      <SectionCard title="Stored screening result" hint="Values exactly as recorded by the screening engine.">
        {screening ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-4xl font-bold text-gray-900">{screening.overall_match_score}</span>
              <span className="text-sm text-gray-500">overall match</span>
              <span
                className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                  RECOMMENDATION_STYLES[screening.recommendation] ?? "bg-gray-100 text-gray-800"
                }`}
              >
                {RECOMMENDATION_LABELS[screening.recommendation] ?? screening.recommendation}
              </span>
              <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
                Strength: {STRENGTH_LABELS[screening.strength_level] ?? screening.strength_level}
              </span>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Matched skills
                </h4>
                <div className="mt-2">
                  <ChipList items={screening.matched_skills ?? []} tone="green" />
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Missing required skills
                </h4>
                <div className="mt-2">
                  <ChipList items={screening.missing_required_skills ?? []} tone="red" />
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Missing preferred skills
                </h4>
                <div className="mt-2">
                  <ChipList items={screening.missing_preferred_skills ?? []} tone="gray" />
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Recorded strengths
                </h4>
                <div className="mt-2">
                  <ChipList items={screening.strengths ?? []} tone="green" />
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Recorded weaknesses
                </h4>
                <div className="mt-2">
                  <ChipList items={screening.weaknesses ?? []} tone="red" />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">No stored screening result for this application.</p>
        )}
      </SectionCard>

      <SectionCard title="Match breakdown" hint="Per-dimension scores as stored; no weights are implied.">
        <BreakdownList items={detail.match_breakdown} />
      </SectionCard>

      <SectionCard
        title="Requirement-level matching"
        hint={
          detail.fit_section.available
            ? "Evidence-grounded fit analysis for this job and candidate."
            : undefined
        }
      >
        {fit ? (
          <div className="space-y-4">
            <div className="rounded-lg border bg-gray-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-2xl font-bold text-gray-900">{fit.overall.score}</span>
                <span className="text-sm text-gray-500">fit score</span>
                <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-700">
                  {fit.overall.classification.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-2 text-sm text-gray-700">{fit.overall.summary}</p>
            </div>
            <ul className="space-y-0">
              {fit.requirements.map((requirement, index) => (
                <RequirementRow key={`${requirement.requirement}-${index}`} requirement={requirement} />
              ))}
            </ul>
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Supported
                </h4>
                <div className="mt-2">
                  <ChipList items={fit.skill_gaps.strengths ?? []} tone="green" />
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Gaps</h4>
                <div className="mt-2">
                  <ChipList items={fit.skill_gaps.gaps ?? []} tone="red" />
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  No evidence
                </h4>
                <div className="mt-2">
                  <ChipList items={fit.skill_gaps.unknown ?? []} tone="gray" />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <UnavailableSection reason={detail.fit_section.reason} />
        )}
      </SectionCard>

      <SectionCard
        title="Evidence intelligence"
        hint={
          evidence
            ? `Snapshot: ${evidence.snapshot.total_experience_years ?? "--"} years experience, ${evidence.snapshot.project_count} projects, ${evidence.snapshot.certification_count} certifications.`
            : undefined
        }
      >
        {evidence ? (
          <div className="space-y-5">
            <div className="rounded-lg border bg-gray-50 p-3 text-sm text-gray-700">
              <p>{evidence.summary.text}</p>
              <p className="mt-1 text-xs text-gray-500">
                {evidence.summary.source.replace(/_/g, " ")} &middot; {evidence.summary.disclaimer}
              </p>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Strengths</h4>
              <ul className="mt-1">
                {evidence.strengths.length === 0 ? (
                  <li className="py-2 text-sm text-gray-500">None recorded</li>
                ) : (
                  evidence.strengths.map((insight, index) => (
                    <StrengthRow key={`${insight.title}-${index}`} insight={insight} />
                  ))
                )}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Skill depth
              </h4>
              <ul className="mt-1">
                {evidence.skill_assessments.length === 0 ? (
                  <li className="py-2 text-sm text-gray-500">None recorded</li>
                ) : (
                  evidence.skill_assessments.map((assessment, index) => (
                    <SkillRow key={`${assessment.skill}-${index}`} assessment={assessment} />
                  ))
                )}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Evidence gaps
              </h4>
              <ul className="mt-1">
                {evidence.evidence_gaps.length === 0 ? (
                  <li className="py-2 text-sm text-gray-500">None recorded</li>
                ) : (
                  evidence.evidence_gaps.map((gap, index) => (
                    <GapRow key={`${gap.skill}-${index}`} gap={gap} />
                  ))
                )}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Review flags
              </h4>
              <ul className="mt-1">
                {evidence.review_flags.length === 0 ? (
                  <li className="py-2 text-sm text-gray-500">None recorded</li>
                ) : (
                  evidence.review_flags.map((flag, index) => (
                    <FlagRow key={`${flag.flag_type}-${index}`} flag={flag} />
                  ))
                )}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Suggested screening questions
              </h4>
              <div className="mt-2">
                <QuestionList questions={evidence.screening_questions} />
              </div>
            </div>
          </div>
        ) : (
          <UnavailableSection reason={detail.evidence_intelligence_section.reason} />
        )}
      </SectionCard>

      <SectionCard title="Job context" hint="How this candidate aligns with this specific job.">
        {detail.job_context ? (
          <JobContextSection context={detail.job_context} />
        ) : (
          <UnavailableSection reason={detail.job_context_section.reason} />
        )}
      </SectionCard>

      <SectionCard title="Data freshness and limitations">
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">Screened at</dt>
            <dd className="text-sm text-gray-800">{formatDate(freshness.screened_at)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Resume on file
            </dt>
            <dd className="text-sm text-gray-800">
              {candidate.has_resume ? "Yes" : "No"}
              {freshness.screening_resume_id ? " (screened resume on file)" : ""}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Fit engine version
            </dt>
            <dd className="text-sm text-gray-800">{freshness.fit_engine_version || "Not recorded"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Evidence engine version
            </dt>
            <dd className="text-sm text-gray-800">
              {freshness.evidence_engine_version || "Not recorded"}
            </dd>
          </div>
        </dl>
        {detail.limitations.length > 0 && (
          <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-gray-500">
            {detail.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* Fairness follows explainability deliberately: the recruiter reads why
          this candidate scored as they did first, then whether the job's
          screened population shows a measured disparity. The two are reported
          side by side and never combined. */}
      <ApplicationFairnessContextCard
        applicationId={application.id}
        jobId={job.id}
      />
    </div>
  );
}
