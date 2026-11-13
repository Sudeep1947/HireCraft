import type {
  CandidateRequirementImpactDetail,
  ChangedRequirementStatus,
} from "../../types/requirementImpact";
import {
  QUALIFICATION_CHANGE_LABELS,
  SHORTLIST_CHANGE_LABELS,
  formatSatisfactionStatus,
} from "../../types/requirementImpact";

interface CandidateRequirementDetailProps {
  candidate: CandidateRequirementImpactDetail;
  onClose: () => void;
}

function SatisfactionBadge({ status }: { status: ChangedRequirementStatus["baseline_status"] }) {
  const colors = {
    SATISFIED: "badge-success",
    MISSING: "badge-danger",
    NOT_APPLICABLE: "badge-neutral",
  };
  return (
    <span className={colors[status]}>
      {formatSatisfactionStatus(status)}
    </span>
  );
}

function QualificationBadge({ change }: { change: string }) {
  const colors: Record<string, string> = {
    newly_qualified: "badge-success",
    newly_disqualified: "badge-danger",
    remained_qualified: "badge-info",
    remained_unqualified: "badge-neutral",
  };
  return (
    <span className={colors[change] || "badge-neutral"}>
      {QUALIFICATION_CHANGE_LABELS[change as keyof typeof QUALIFICATION_CHANGE_LABELS] || change}
    </span>
  );
}

function ShortlistBadge({ change }: { change: string }) {
  const colors: Record<string, string> = {
    entered: "badge-success",
    left: "badge-danger",
    retained: "badge-info",
    never_shortlisted: "badge-neutral",
  };
  return (
    <span className={colors[change] || "badge-neutral"}>
      {SHORTLIST_CHANGE_LABELS[change as keyof typeof SHORTLIST_CHANGE_LABELS] || change}
    </span>
  );
}

export function CandidateRequirementDetail({ candidate, onClose }: CandidateRequirementDetailProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
      <div className="card-solid mx-4 max-h-[90vh] w-full max-w-2xl animate-scale-in overflow-y-auto p-0">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200/70 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-ink">{candidate.candidate_name}</h2>
            <p className="mt-0.5 text-sm text-ink-muted">Requirement Impact Detail</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-2 text-ink-subtle transition-colors duration-200 hover:bg-surface-muted hover:text-ink-muted focus-visible:ring-2 focus-visible:ring-primary-500/60 focus-visible:outline-none"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Score & Rank Changes */}
        <div className="grid grid-cols-2 gap-4 border-b border-slate-200/70 px-6 py-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">Score</dt>
            <dd className="mt-1 text-lg font-bold text-ink">
              {candidate.simulation_score}
              <span className="ml-1 text-sm text-ink-muted">
                (base {candidate.baseline_score})
              </span>
            </dd>
            <dd
              className={`text-xs font-medium ${
                candidate.score_change > 0
                  ? "text-emerald-600"
                  : candidate.score_change < 0
                    ? "text-rose-600"
                    : "text-ink-muted"
              }`}
            >
              {candidate.score_change > 0 ? "+" : ""}
              {candidate.score_change} change
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">Rank</dt>
            <dd className="mt-1 text-lg font-bold text-ink">
              #{candidate.simulation_rank}
              <span className="ml-1 text-sm text-ink-muted">
                (base #{candidate.baseline_rank})
              </span>
            </dd>
            <dd
              className={`text-xs font-medium ${
                candidate.rank_change > 0
                  ? "text-emerald-600"
                  : candidate.rank_change < 0
                    ? "text-rose-600"
                    : "text-ink-muted"
              }`}
            >
              {candidate.rank_change > 0 ? "+" : ""}
              {candidate.rank_change} change
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">Qualification</dt>
            <dd className="mt-1">
              <QualificationBadge change={candidate.qualification_change} />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">Shortlist</dt>
            <dd className="mt-1">
              <ShortlistBadge change={candidate.shortlist_change} />
            </dd>
          </div>
        </div>

        {/* Affected Requirements */}
        <div className="px-6 py-4">
          <h3 className="text-sm font-semibold text-ink">Changed Requirements</h3>
          {candidate.affected_requirements.length === 0 ? (
            <p className="mt-2 text-sm text-ink-muted">
              No requirement changes affected this candidate&apos;s satisfaction status.
            </p>
          ) : (
            <div className="mt-3 space-y-3">
              {candidate.affected_requirements.map((req, idx) => (
                <div
                  key={`${req.requirement_type}-${req.requirement_name}-${idx}`}
                  className="rounded-xl border border-slate-200/70 bg-surface-muted/70 p-4"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-ink">{req.requirement_name}</span>
                      <span className="ml-2 text-xs text-ink-muted capitalize">({req.requirement_type})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <SatisfactionBadge status={req.baseline_status} />
                      <svg className="h-4 w-4 text-ink-subtle" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                      </svg>
                      <SatisfactionBadge status={req.simulation_status} />
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-ink-muted">
                    {req.baseline_satisfied === req.simulation_satisfied
                      ? "Satisfaction status unchanged"
                      : req.simulation_satisfied
                        ? "Candidate now satisfies this requirement"
                        : "Candidate no longer satisfies this requirement"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Explanation */}
        {candidate.explanation && (
          <div className="border-t border-slate-200/70 px-6 py-4">
            <h3 className="text-sm font-semibold text-ink">Analysis</h3>
            <p className="mt-2 text-sm text-ink-muted">{candidate.explanation}</p>
          </div>
        )}
      </div>
    </div>
  );
}
