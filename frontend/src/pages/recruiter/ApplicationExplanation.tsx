import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { getApplicationExplanation } from "../../api/screening";
import { getErrorMessage } from "../../utils/error";
import {
  ExplanationCard,
  ExplanationChips,
  ExplanationEvidenceList,
  ExplanationFreshnessBlock,
  ExplanationPendingNotice,
  ExplanationUnavailable,
  contributionBarColor,
  formatExplanationDate,
  scoreBarColor,
  screeningStateLabel,
  screeningStateStyle,
} from "../../components/screening/ExplanationSections";
import type {
  ExplanationFactor,
  ExplanationFeature,
  ExplanationRecord,
  ExplanationRequirement,
  RecruiterApplicationExplanation,
  RecruiterExplanationFeature,
} from "../../types/screening";

/**
 * Recruiter-facing "Why This Score?" for a single application.
 *
 * Everything on this page comes from one server response built by the
 * application explanation service. The displayed overall score is the stored
 * screening score, so this page can explain the screen but never disagree with
 * it: no score, weight or factor is computed in the browser.
 *
 * This view is recruiter-only and includes internals (dimension weights, the fit
 * formula, evidence review flags, suggested interview questions) that the
 * candidate projection deliberately omits.
 */

const RECOMMENDATION_LABELS: Record<string, string> = {
  strongly_recommend: "Strongly Recommend",
  recommend: "Recommend",
  consider: "Consider",
  not_recommended: "Not Recommended",
};

const RECOMMENDATION_STYLES: Record<string, string> = {
  strongly_recommend: "bg-green-100 text-green-800",
  recommend: "bg-blue-100 text-blue-800",
  consider: "bg-yellow-100 text-yellow-800",
  not_recommended: "bg-red-100 text-red-800",
};

const STRENGTH_LABELS: Record<string, string> = {
  excellent: "Excellent",
  good: "Good",
  average: "Average",
  low: "Low",
};

const MATCH_STATUS_LABELS: Record<string, string> = {
  match: "Met",
  partial: "Partial",
  gap: "Gap",
  unknown: "Unknown",
};

const MATCH_STATUS_STYLES: Record<string, string> = {
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

const SUGGESTION_CATEGORY_LABELS: Record<string, string> = {
  skill: "Skill",
  certification: "Certification",
  project: "Project",
  resume: "Resume",
  interview: "Interview",
};

function recordString(record: ExplanationRecord, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "";
}

function ScoreCard({ explanation }: { explanation: RecruiterApplicationExplanation }) {
  const { score } = explanation;

  if (score.overall_score === null) {
    return (
      <ExplanationUnavailable
        reason="No stored screening result exists, so there is no score to explain."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-4xl font-bold text-gray-900">{score.overall_score}</span>
        <span className="text-sm text-gray-500">overall match</span>
        {score.recommendation && (
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
              RECOMMENDATION_STYLES[score.recommendation] ?? "bg-gray-100 text-gray-800"
            }`}
          >
            {RECOMMENDATION_LABELS[score.recommendation] ?? score.recommendation}
          </span>
        )}
        {score.strength_level && (
          <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
            Strength: {STRENGTH_LABELS[score.strength_level] ?? score.strength_level}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500">
        Source: stored screening result, screened at {formatExplanationDate(score.screened_at)}.
        Copied verbatim &mdash; not recalculated.
      </p>
    </div>
  );
}

function FeatureRow({ feature }: { feature: RecruiterExplanationFeature }) {
  return (
    <li className="py-3">
      <div className="flex items-center gap-3">
        <span className="w-40 shrink-0 text-sm text-gray-700">{feature.label}</span>
        <div className="h-3 flex-1 overflow-hidden rounded-full bg-gray-100">
          <div
            className={`h-full rounded-full ${contributionBarColor(feature.impact)}`}
            style={{ width: `${Math.max(0, Math.min(100, feature.contribution_pct))}%` }}
          />
        </div>
        <span className="w-14 shrink-0 text-right text-xs font-bold text-gray-900">
          {feature.contribution_pct}%
        </span>
        <span className="w-8 shrink-0 text-right text-xs text-gray-500">{feature.score}</span>
        {feature.weight !== null && (
          <span
            data-testid="feature-weight"
            className="w-16 shrink-0 text-right text-xs text-gray-500"
          >
            w {feature.weight}
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-gray-600">{feature.impact_description}</p>
    </li>
  );
}

function FactorList({
  factors,
  tone,
  emptyLabel,
}: {
  factors: ExplanationFactor[];
  tone: "positive" | "negative";
  emptyLabel: string;
}) {
  if (factors.length === 0) return <p className="text-sm text-gray-500">{emptyLabel}</p>;
  return (
    <ul className="space-y-3">
      {factors.map((factor, index) => (
        <li key={`${factor.category}-${index}`} className="rounded-lg border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                tone === "positive" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
              }`}
            >
              {tone === "positive" ? "+" : "-"} {factor.category.replace(/_/g, " ")}
            </span>
            <span className="text-xs text-gray-600">
              score {factor.score} &middot; {factor.contribution_pct}% of result
            </span>
            {!factor.evidence_available && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                No quote
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-gray-700">{factor.reason}</p>
          <div className="mt-2">
            <ExplanationEvidenceList evidence={factor.evidence} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function RequirementList({ requirements }: { requirements: ExplanationRequirement[] }) {
  if (requirements.length === 0) {
    return <p className="text-sm text-gray-500">No requirements are recorded for this role.</p>;
  }
  return (
    <ul className="space-y-0">
      {requirements.map((requirement, index) => (
        <li key={`${requirement.requirement}-${index}`} className="border-t py-3 first:border-t-0 first:pt-0">
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
                {MATCH_STATUS_LABELS[requirement.status] ?? requirement.status.replace(/_/g, " ")}
              </span>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                {requirement.evidence_strength.replace(/_/g, " ")}
              </span>
            </div>
          </div>
          {requirement.reason && (
            <p className="mt-1 text-xs text-gray-600">{requirement.reason}</p>
          )}
          <div className="mt-2">
            <ExplanationEvidenceList evidence={requirement.evidence} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function FitSection({ explanation }: { explanation: RecruiterApplicationExplanation }) {
  if (!explanation.fit.available) {
    return <ExplanationUnavailable reason={explanation.fit.reason} />;
  }
  if (explanation.fit_score === null && explanation.fit_summary === null) {
    return <ExplanationUnavailable reason={explanation.fit.reason} />;
  }

  const weightEntries = Object.entries(explanation.fit_weights);

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-gray-50 p-3">
        <div className="flex flex-wrap items-center gap-2">
          {explanation.fit_score !== null && (
            <>
              <span className="text-2xl font-bold text-gray-900">{explanation.fit_score}</span>
              <span className="text-sm text-gray-500">fit score</span>
            </>
          )}
          {explanation.fit_classification && (
            <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-700">
              {explanation.fit_classification.replace(/_/g, " ")}
            </span>
          )}
        </div>
        {explanation.fit_summary && (
          <p className="mt-2 text-sm text-gray-700">{explanation.fit_summary}</p>
        )}
        {explanation.fit_summary_source && (
          <p className="mt-1 text-xs text-gray-500">
            Summary source: {explanation.fit_summary_source.replace(/_/g, " ")}
          </p>
        )}
      </div>
      {explanation.fit_formula && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Formula</h4>
          <pre className="mt-1 overflow-x-auto rounded bg-gray-900 p-3 text-xs text-gray-100">
            {explanation.fit_formula}
          </pre>
        </div>
      )}
      {weightEntries.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Component weights
          </h4>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            {weightEntries.map(([name, weight]) => (
              <div
                key={name}
                className="flex items-center justify-between rounded border px-3 py-1.5 text-sm"
              >
                <dt className="text-gray-700">{name.replace(/_/g, " ")}</dt>
                <dd className="font-medium text-gray-900">{weight}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

function ReviewFlagList({ flags }: { flags: ExplanationRecord[] }) {
  if (flags.length === 0) return <p className="text-sm text-gray-500">None recorded</p>;
  return (
    <ul className="space-y-2">
      {flags.map((flag, index) => {
        const severity = recordString(flag, "severity") || "info";
        return (
          <li key={`${recordString(flag, "flag_type") || "flag"}-${index}`} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-gray-900">
                {recordString(flag, "title") || recordString(flag, "flag_type") || "Review flag"}
              </p>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  severity === "warning"
                    ? "bg-yellow-100 text-yellow-800"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {severity}
              </span>
            </div>
            {recordString(flag, "description") && (
              <p className="mt-1 text-xs text-gray-600">{recordString(flag, "description")}</p>
            )}
            {recordString(flag, "possible_explanation") && (
              <p className="mt-1 text-xs text-gray-500">
                {recordString(flag, "possible_explanation")}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function ScreeningQuestionList({ questions }: { questions: ExplanationRecord[] }) {
  if (questions.length === 0) return <p className="text-sm text-gray-500">None recorded</p>;
  return (
    <ol className="list-decimal space-y-2 pl-5">
      {questions.map((question, index) => (
        <li key={`${recordString(question, "topic") || "question"}-${index}`} className="text-sm text-gray-700">
          <span className="font-medium text-gray-900">
            {recordString(question, "question") || "Suggested question"}
          </span>
          {recordString(question, "reason") && (
            <span className="block text-xs text-gray-500">{recordString(question, "reason")}</span>
          )}
        </li>
      ))}
    </ol>
  );
}

export function RecruiterApplicationExplanationPage() {
  const { jobId, applicationId } = useParams<{
    jobId: string;
    applicationId: string;
  }>();
  const [explanation, setExplanation] = useState<RecruiterApplicationExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError(null);
    setAccessDenied(null);
    try {
      const data = await getApplicationExplanation(applicationId);
      setExplanation(data);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403 || status === 404) {
        setAccessDenied(
          getErrorMessage(err, "This application does not exist or is not available to you."),
        );
      } else {
        setError(getErrorMessage(err, "Failed to load the score explanation."));
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
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Explanation unavailable
          </p>
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

  if (error || !explanation) {
    return (
      <div className="mx-auto max-w-2xl py-12 text-center">
        <div className="rounded-lg border border-red-200 bg-red-50 p-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Could not load the score explanation
          </p>
          <p className="mt-2 text-sm text-red-700">
            {error || "An unexpected error occurred while loading this explanation."}
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

  const { candidate, job, screening_state: screeningState, skill_alignment: skills } = explanation;
  const hasScore = explanation.score.overall_score !== null;
  const features: ExplanationFeature[] = explanation.feature_importance;

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
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Why this score?</h1>
          <p className="text-sm text-gray-500">
            {candidate.name || "Candidate"} &middot; {job.title} &middot; {job.company}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${screeningStateStyle(
              screeningState.effective_status,
            )}`}
          >
            Screening: {screeningStateLabel(screeningState.effective_status)}
          </span>
          <Link
            to={`/recruiter/jobs/${jobId}/applicants/${applicationId}/screening`}
            className="inline-flex items-center rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Screening detail
          </Link>
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
        </div>
      </div>

      {!hasScore && (
        <ExplanationPendingNotice
          state={screeningState.effective_status}
          message={screeningState.message}
        />
      )}

      <ExplanationCard
        title="Stored screening score"
        hint="The authoritative score this explanation describes. Copied from the screening result, never recalculated."
      >
        <ScoreCard explanation={explanation} />
      </ExplanationCard>

      <ExplanationCard
        title="What drove this score"
        hint={
          hasScore
            ? "Each dimension's share of the overall result, with the engine's configured weight."
            : undefined
        }
      >
        {features.length === 0 ? (
          <p className="text-sm text-gray-500">
            No dimension breakdown is available for this application.
          </p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {features.map((feature, index) => (
              <FeatureRow
                key={`${feature.category}-${index}`}
                feature={feature as RecruiterExplanationFeature}
              />
            ))}
          </ul>
        )}
      </ExplanationCard>

      <ExplanationCard title="Reasoning summary">
        {explanation.reasoning_summary ? (
          <p className="text-sm text-gray-700">{explanation.reasoning_summary}</p>
        ) : (
          <p className="text-sm text-gray-500">No reasoning summary is available.</p>
        )}
      </ExplanationCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <ExplanationCard title="Factors in this candidate's favour">
          <FactorList
            factors={explanation.positive_factors}
            tone="positive"
            emptyLabel="No positive factors identified."
          />
        </ExplanationCard>
        <ExplanationCard title="Factors working against this candidate">
          <FactorList
            factors={explanation.negative_factors}
            tone="negative"
            emptyLabel="No negative factors identified."
          />
        </ExplanationCard>
      </div>

      <ExplanationCard
        title="Confidence in the available evidence"
        hint="Confidence in the data the explanation rests on, not in the candidate."
      >
        {explanation.confidence ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-2xl font-bold text-gray-900">{explanation.confidence.score}</span>
              <span className="text-sm text-gray-500">
                {explanation.confidence.level.replace(/_/g, " ")}
              </span>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                {explanation.confidence.data_points_available}/
                {explanation.confidence.data_points_max} data points
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full ${scoreBarColor(explanation.confidence.score)}`}
                style={{
                  width: `${Math.max(0, Math.min(100, explanation.confidence.data_completeness_pct))}%`,
                }}
              />
            </div>
            <p className="text-sm text-gray-700">{explanation.confidence.description}</p>
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            No confidence value is available for this application.
          </p>
        )}
      </ExplanationCard>

      <ExplanationCard
        title="Skill alignment"
        hint="Matched skills come from the stored screening result; the gap buckets come from the evidence-grounded fit engine."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Matched skills
            </h4>
            <div className="mt-2">
              <ExplanationChips items={skills.matched_skills} tone="green" emptyLabel="None matched" />
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Missing required
            </h4>
            <div className="mt-2">
              <ExplanationChips
                items={skills.missing_required_skills}
                tone="red"
                emptyLabel="None missing"
              />
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Missing preferred
            </h4>
            <div className="mt-2">
              <ExplanationChips items={skills.missing_preferred_skills} tone="gray" />
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Supported by evidence
            </h4>
            <div className="mt-2">
              <ExplanationChips items={skills.supported_skills} tone="green" />
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Partial evidence
            </h4>
            <div className="mt-2">
              <ExplanationChips items={skills.partial_evidence_skills} tone="blue" />
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              No evidence found
            </h4>
            <div className="mt-2">
              <ExplanationChips items={skills.skills_without_evidence} tone="gray" />
            </div>
          </div>
        </div>
      </ExplanationCard>

      <ExplanationCard
        title="Requirement-level matching"
        hint="Each of this role's requirements, with the resume evidence behind the result."
      >
        <RequirementList requirements={explanation.requirements} />
      </ExplanationCard>

      {explanation.experience_alignment && (
        <ExplanationCard title="Experience alignment">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                {explanation.experience_alignment.status.replace(/_/g, " ")}
              </span>
              {explanation.experience_alignment.required_years !== null && (
                <span className="text-sm text-gray-600">
                  Required {explanation.experience_alignment.required_years} years
                </span>
              )}
              {explanation.experience_alignment.relevant_years !== null && (
                <span className="text-sm text-gray-600">
                  Relevant {explanation.experience_alignment.relevant_years} years
                </span>
              )}
              {explanation.experience_alignment.total_years !== null && (
                <span className="text-sm text-gray-600">
                  Total {explanation.experience_alignment.total_years} years
                </span>
              )}
            </div>
            {explanation.experience_alignment.relevance_basis && (
              <p className="text-xs text-gray-500">
                Relevance basis: {explanation.experience_alignment.relevance_basis.replace(/_/g, " ")}
              </p>
            )}
            {explanation.experience_alignment.reason && (
              <p className="text-sm text-gray-700">{explanation.experience_alignment.reason}</p>
            )}
          </div>
        </ExplanationCard>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ExplanationCard title="Evidence-backed strengths">
          {explanation.evidence_strengths.length === 0 ? (
            <p className="text-sm text-gray-500">None recorded.</p>
          ) : (
            <ul className="space-y-2">
              {explanation.evidence_strengths.map((strength, index) => (
                <li key={`${strength.title}-${index}`} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{strength.title}</p>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                      {SKILL_DEPTH_LABELS[strength.depth] ?? strength.depth.replace(/_/g, " ")}
                    </span>
                    {strength.confidence && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                        {strength.confidence.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  {strength.reason && (
                    <p className="mt-1 text-xs text-gray-600">{strength.reason}</p>
                  )}
                  <div className="mt-2">
                    <ExplanationEvidenceList evidence={strength.evidence} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </ExplanationCard>

        <ExplanationCard title="Evidence gaps">
          {explanation.evidence_gaps.length === 0 ? (
            <p className="text-sm text-gray-500">None recorded.</p>
          ) : (
            <ul className="space-y-2">
              {explanation.evidence_gaps.map((gap, index) => (
                <li key={`${gap.subject}-${index}`} className="rounded-lg border p-3">
                  <p className="text-sm font-medium text-gray-900">{gap.subject}</p>
                  <p className="text-xs text-gray-500">{gap.category.replace(/_/g, " ")}</p>
                  {gap.note && <p className="mt-1 text-xs text-gray-600">{gap.note}</p>}
                </li>
              ))}
            </ul>
          )}
        </ExplanationCard>
      </div>

      <ExplanationCard
        title="Improvement suggestions"
        hint="What a stronger, better-evidenced application could look like. These describe the profile, not a hiring decision."
      >
        {explanation.improvement_suggestions.length === 0 ? (
          <p className="text-sm text-gray-500">No suggestions available.</p>
        ) : (
          <ul className="space-y-2">
            {explanation.improvement_suggestions.map((suggestion, index) => (
              <li
                key={`${suggestion.category}-${index}`}
                className="flex flex-wrap items-start gap-2 rounded-lg border p-3"
              >
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                  {SUGGESTION_CATEGORY_LABELS[suggestion.category] ?? suggestion.category}
                </span>
                <div className="min-w-0 flex-1">
                  {suggestion.subject && (
                    <p className="text-sm font-medium text-gray-900">{suggestion.subject}</p>
                  )}
                  <p className="text-sm text-gray-700">{suggestion.text}</p>
                </div>
                {suggestion.priority && (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                    {suggestion.priority.replace(/_/g, " ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </ExplanationCard>

      <ExplanationCard title="Fit analysis" hint="Evidence-grounded fit against this role's requirements.">
        <FitSection explanation={explanation} />
      </ExplanationCard>

      <ExplanationCard
        title="Evidence review flags"
        hint="Internal checks on the quality of the evidence. Not a decision."
      >
        <ReviewFlagList flags={explanation.review_flags} />
      </ExplanationCard>

      <ExplanationCard
        title="Suggested screening questions"
        hint="Questions to resolve the evidence gaps above during review."
      >
        <ScreeningQuestionList questions={explanation.screening_questions} />
      </ExplanationCard>

      <ExplanationFreshnessBlock
        freshness={explanation.freshness}
        limitations={explanation.limitations}
      />

      <p className="text-center text-xs text-gray-500">{explanation.disclaimer}</p>
    </div>
  );
}
