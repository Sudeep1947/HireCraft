import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { getMyApplicationExplanation } from "../../api/screening";
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
  screeningStateLabel,
  screeningStateStyle,
} from "../../components/screening/ExplanationSections";
import type {
  CandidateApplicationExplanation,
  ExplanationFactor,
  ExplanationFeature,
  ExplanationRequirement,
} from "../../types/screening";

/**
 * Candidate-facing "How your profile matches this role" for one application.
 *
 * This component is typed against the candidate projection only. The candidate
 * response has no field for an internal recommendation, a dimension weight, a
 * fit formula, an evidence review flag, a suggested interview question, a
 * fairness signal, a ranking or any other candidate's data, so there is
 * nothing here that could render internal information even if the server were
 * to send extra fields.
 *
 * The overall score shown is the same stored screening score the recruiter sees.
 * It is never recomputed here.
 */

const MATCH_STATUS_LABELS: Record<string, string> = {
  match: "Met",
  partial: "Partially met",
  gap: "Not evidenced",
  unknown: "Not enough information",
};

const MATCH_STATUS_STYLES: Record<string, string> = {
  match: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
  partial: "bg-amber-50 text-amber-700 ring-amber-200/70",
  gap: "bg-red-50 text-red-700 ring-red-200/70",
  unknown: "bg-gray-100 text-gray-600 ring-gray-200/80",
};

const SUGGESTION_CATEGORY_LABELS: Record<string, string> = {
  skill: "Skill",
  certification: "Certification",
  project: "Project",
  resume: "Resume",
  interview: "Interview",
};

const APPLICATION_STATUS_LABELS: Record<string, string> = {
  applied: "Applied",
  under_review: "Under review",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview scheduled",
  interviewed: "Interview completed",
  offered: "Offered",
  hired: "Hired",
  rejected: "Not progressing",
  withdrawn: "Withdrawn",
};

function ScoreCard({ explanation }: { explanation: CandidateApplicationExplanation }) {
  const { score } = explanation;

  if (score.overall_score === null) {
    return (
      <ExplanationUnavailable
        reason="Your application has not been screened yet, so there is no match result to show."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-display text-4xl font-bold text-gradient">{score.overall_score}</span>
        <span className="text-sm text-gray-500">overall match with this role</span>
        {score.match_classification && (
          <span className="badge-neutral">
            {score.match_classification.replace(/_/g, " ")}
          </span>
        )}
      </div>
      {score.match_score !== null && (
        <p className="text-sm text-gray-600">
          Role alignment score: <span className="font-semibold text-gray-900">{score.match_score}</span>
        </p>
      )}
      {score.match_summary && <p className="text-sm text-gray-700">{score.match_summary}</p>}
      <p className="text-xs text-gray-500">
        Calculated on {formatExplanationDate(score.screened_at)} from the resume you had submitted at
        that time.
      </p>
    </div>
  );
}

function FeatureList({ features }: { features: ExplanationFeature[] }) {
  if (features.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No factor breakdown is available for your application.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-gray-100">
      {features.map((feature, index) => (
        <li key={`${feature.category}-${index}`} className="py-3 first:pt-0 last:pb-0">
          <div className="flex items-center gap-3">
            <span className="w-40 shrink-0 text-sm text-gray-700">{feature.label}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full rounded-full ${contributionBarColor(feature.impact)}`}
                style={{ width: `${Math.max(0, Math.min(100, feature.contribution_pct))}%` }}
              />
            </div>
            <span className="w-14 shrink-0 text-right text-xs font-bold text-gray-900">
              {feature.contribution_pct}%
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-600">{feature.impact_description}</p>
        </li>
      ))}
    </ul>
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
        <li key={`${factor.category}-${index}`} className="rounded-xl border border-gray-200 bg-white/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                tone === "positive" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"
              }`}
            >
              {factor.category.replace(/_/g, " ")}
            </span>
            {!factor.evidence_available && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                No quote available
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
    return (
      <p className="text-sm text-gray-500">
        This role has no recorded requirements to compare against.
      </p>
    );
  }
  return (
    <ul className="space-y-0">
      {requirements.map((requirement, index) => (
        <li key={`${requirement.requirement}-${index}`} className="border-t border-gray-100 py-3 first:border-t-0 first:pt-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="min-w-0 text-sm font-medium text-gray-900">{requirement.requirement}</p>
            <span
              className={`badge shrink-0 ${
                MATCH_STATUS_STYLES[requirement.status] ?? "bg-gray-100 text-gray-600 ring-gray-200/80"
              }`}
            >
              {MATCH_STATUS_LABELS[requirement.status] ?? requirement.status.replace(/_/g, " ")}
            </span>
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

export function CandidateApplicationExplanationPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const [explanation, setExplanation] = useState<CandidateApplicationExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError(null);
    setUnavailable(null);
    try {
      const data = await getMyApplicationExplanation(applicationId);
      setExplanation(data);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        setUnavailable(
          "This explanation does not exist or is not available for your account.",
        );
      } else {
        setError(getErrorMessage(err, "Failed to load your match explanation."));
      }
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-80" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-48 w-full" />
      </div>
    );

  if (unavailable) {
    return (
      <div className="mx-auto max-w-2xl py-12 animate-fade-in">
        <div className="empty-state px-6 py-12">
          <ShieldAlert className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">
            Explanation unavailable
          </p>
          <p className="mt-2 text-sm text-gray-700">{unavailable}</p>
          <Link
            to="/candidate/applications"
            className="btn-secondary btn-sm mt-5"
          >
            Back to my applications
          </Link>
        </div>
      </div>
    );
  }

  if (error || !explanation) {
    return (
      <div className="mx-auto max-w-2xl py-12 animate-fade-in">
        <div className="rounded-xl border border-red-200/80 bg-red-50/80 p-8 text-center shadow-xs">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Could not load your match explanation
          </p>
          <p className="mt-2 text-sm text-red-700">
            {error || "An unexpected error occurred while loading this explanation."}
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Button variant="secondary" onClick={() => void load()}>
              Try again
            </Button>
            <Link
              to="/candidate/applications"
              className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 shadow-xs transition-all duration-200 hover:border-primary-300 hover:text-primary-700 hover:shadow-md"
            >
              Back to my applications
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Only the curated candidate-safe fields are rendered here. The raw
  // `skill_alignment` buckets are intentionally left out: `matched_skills` and
  // `areas_with_limited_evidence` are the fields chosen to be shown to a
  // candidate, and rendering the internal gap buckets would widen the surface
  // beyond what the projection was designed to expose.
  const { application, job, screening_state: screeningState } = explanation;
  const hasScore = explanation.score.overall_score !== null;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div className="min-w-0">
          <Link
            to="/candidate/applications"
            className="text-xs font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700 hover:underline"
          >
            &larr; Back to my applications
          </Link>
          <h1 className="page-title mt-1">How your profile matches this role</h1>
          <p className="page-subtitle">
            {job.title} &middot; {job.company}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="badge-neutral">
            {APPLICATION_STATUS_LABELS[application.status] ??
              application.status.replace(/_/g, " ")}
          </span>
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${screeningStateStyle(
              screeningState.effective_status,
            )}`}
          >
            Screening: {screeningStateLabel(screeningState.effective_status)}
          </span>
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
        </div>
      </div>

      <div className="info-banner">
        {explanation.screening_notice}
      </div>

      {!hasScore && (
        <ExplanationPendingNotice
          state={screeningState.effective_status}
          message={screeningState.message}
        />
      )}

      <ExplanationCard
        title="Your match result"
        hint="The result recorded when your application was screened. It is not recalculated here."
      >
        <ScoreCard explanation={explanation} />
      </ExplanationCard>

      <ExplanationCard title="Skills that matched this role">
        <ExplanationChips
          items={explanation.matched_skills}
          tone="green"
          emptyLabel="No skills were recorded as matching this role."
        />
      </ExplanationCard>

      <ExplanationCard
        title="What affected your result"
        hint="Each area's share of your overall match, based on the evidence in your resume."
      >
        <FeatureList features={explanation.feature_importance} />
      </ExplanationCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <ExplanationCard title="Where your experience aligned">
          <FactorList
            factors={explanation.aligned_areas}
            tone="positive"
            emptyLabel="No strongly aligned areas were identified."
          />
        </ExplanationCard>
        <ExplanationCard title="Where evidence was limited">
          <FactorList
            factors={explanation.limited_areas}
            tone="negative"
            emptyLabel="No areas with limited evidence were identified."
          />
        </ExplanationCard>
      </div>

      <ExplanationCard
        title="This role's requirements"
        hint="How the requirements in the job description compared with your resume evidence."
      >
        <RequirementList requirements={explanation.requirements} />
      </ExplanationCard>

      {explanation.experience_alignment && (
        <ExplanationCard title="Experience comparison">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="badge-neutral">
                {explanation.experience_alignment.status.replace(/_/g, " ")}
              </span>
              {explanation.experience_alignment.required_years !== null && (
                <span className="text-sm text-gray-600">
                  Role asks for {explanation.experience_alignment.required_years} years
                </span>
              )}
              {explanation.experience_alignment.relevant_years !== null && (
                <span className="text-sm text-gray-600">
                  You have {explanation.experience_alignment.relevant_years} relevant years
                </span>
              )}
            </div>
            {explanation.experience_alignment.reason && (
              <p className="text-sm text-gray-700">{explanation.experience_alignment.reason}</p>
            )}
          </div>
        </ExplanationCard>
      )}

      <ExplanationCard
        title="Evidence gaps"
        hint="Areas where your resume did not provide enough evidence. These are gaps in evidence, not judgements about you."
      >
        {explanation.areas_with_limited_evidence.length > 0 && (
          <div className="mb-4">
            <h4 className="section-label">
              Summary
            </h4>
            <div className="mt-2">
              <ExplanationChips items={explanation.areas_with_limited_evidence} tone="gray" />
            </div>
          </div>
        )}
        {explanation.evidence_gaps.length === 0 ? (
          <p className="text-sm text-gray-500">No evidence gaps were recorded.</p>
        ) : (
          <ul className="space-y-2">
            {explanation.evidence_gaps.map((gap, index) => (
              <li key={`${gap.subject}-${index}`} className="rounded-xl border border-gray-200 bg-white/60 p-3">
                <p className="text-sm font-medium text-gray-900">{gap.subject}</p>
                <p className="text-xs text-gray-500">{gap.category.replace(/_/g, " ")}</p>
                {gap.note && <p className="mt-1 text-xs text-gray-600">{gap.note}</p>}
              </li>
            ))}
          </ul>
        )}
      </ExplanationCard>

      <ExplanationCard
        title="Evidence from your resume"
        hint="Quotes the system used when comparing your profile with this role."
      >
        <ExplanationEvidenceList
          evidence={explanation.resume_evidence}
          emptyLabel="No resume quotes were available."
        />
      </ExplanationCard>

      <ExplanationCard
        title="How to strengthen a future application"
        hint="Suggestions about your profile only. They are not a prediction about this application."
      >
        {explanation.improvement_suggestions.length === 0 ? (
          <p className="text-sm text-gray-500">No suggestions available.</p>
        ) : (
          <ul className="space-y-2">
            {explanation.improvement_suggestions.map((suggestion, index) => (
              <li
                key={`${suggestion.category}-${index}`}
                className="flex flex-wrap items-start gap-2 rounded-xl border border-gray-200 bg-white/60 p-3"
              >
                <span className="badge-info">
                  {SUGGESTION_CATEGORY_LABELS[suggestion.category] ?? suggestion.category}
                </span>
                <div className="min-w-0 flex-1">
                  {suggestion.subject && (
                    <p className="text-sm font-medium text-gray-900">{suggestion.subject}</p>
                  )}
                  <p className="text-sm text-gray-700">{suggestion.text}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </ExplanationCard>

      {explanation.confidence && (
        <ExplanationCard
          title="How much information this was based on"
          hint="A measure of how complete the available evidence was, not a probability of success."
        >
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-display text-2xl font-bold text-gray-900">{explanation.confidence.score}</span>
              <span className="text-sm text-gray-500">
                {explanation.confidence.level.replace(/_/g, " ")}
              </span>
              <span className="badge-neutral">
                {explanation.confidence.data_points_available}/
                {explanation.confidence.data_points_max} data points
              </span>
            </div>
            <p className="text-sm text-gray-700">{explanation.confidence.description}</p>
          </div>
        </ExplanationCard>
      )}

      <ExplanationFreshnessBlock
        freshness={explanation.freshness}
        limitations={explanation.limitations}
      />
    </div>
  );
}
