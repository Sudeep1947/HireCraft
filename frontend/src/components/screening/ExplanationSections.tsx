import type {
  ExplanationEvidence,
  ExplanationFreshness,
  ExplanationScreeningState,
} from "../../types/screening";

/**
 * Presentation primitives shared by the recruiter and candidate explanation
 * pages.
 *
 * These render whatever the server sent and nothing else. There is no
 * client-side scoring, weighting or inference here: a dimension, a factor or a
 * score is displayed or it is not present. That is deliberate, because the
 * recruiter and candidate views must both be incapable of disagreeing with the
 * stored screening result.
 */

const cardClass = "card p-5";
const sectionTitleClass = "text-sm font-semibold text-ink";
const hintClass = "mt-0.5 text-xs text-ink-muted";

const SCREENING_STATE_LABELS: Record<string, string> = {
  not_started: "Not screened",
  queued: "Queued",
  running: "Running",
  completed: "Screened",
  failed: "Failed",
  skipped: "Skipped",
  unknown: "Unknown",
};

const SCREENING_STATE_STYLES: Record<string, string> = {
  not_started: "bg-gray-100 text-ink",
  queued: "bg-amber-100 text-amber-800",
  running: "bg-sky-100 text-sky-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  skipped: "bg-gray-100 text-ink-muted",
  unknown: "bg-gray-100 text-ink-muted",
};

export function screeningStateLabel(state: string): string {
  return SCREENING_STATE_LABELS[state] ?? state.replace(/_/g, " ");
}

export function screeningStateStyle(state: string): string {
  return SCREENING_STATE_STYLES[state] ?? "bg-gray-100 text-ink";
}

export function formatExplanationDate(value: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function scoreBarColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-rose-500";
}

export function contributionBarColor(impact: string): string {
  if (impact === "positive") return "bg-emerald-500";
  if (impact === "negative") return "bg-rose-500";
  return "bg-sky-500";
}

export function ExplanationCard({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cardClass}>
      <div>
        <h3 className={sectionTitleClass}>{title}</h3>
        {hint && <p className={hintClass}>{hint}</p>}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

/**
 * A section whose source produced nothing. Absence is always shown with the
 * server's reason rather than replaced by an empty or invented value.
 */
export function ExplanationUnavailable({ reason }: { reason: string | null | undefined }) {
  return (
    <div
      data-testid="explanation-unavailable"
      className="empty-state !px-4 !py-4 text-left"
    >
      <p className="font-medium text-ink">Not available</p>
      <p className="mt-1">{reason || "No data is available for this application."}</p>
    </div>
  );
}

export function ExplanationChips({
  items,
  tone,
  emptyLabel = "None recorded",
}: {
  items: string[];
  tone: "green" | "red" | "gray" | "blue";
  emptyLabel?: string;
}) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-ink-muted">{emptyLabel}</p>;
  }
  const toneClass =
    tone === "green"
      ? "badge-success"
      : tone === "red"
        ? "badge-danger"
        : tone === "blue"
          ? "badge-info"
          : "badge-neutral";
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li key={item} className={toneClass}>
          {item}
        </li>
      ))}
    </ul>
  );
}

/**
 * Verifiable quotes from the candidate's own resume. Sources are limited to
 * resume content; an item with no quote renders as a plain source label
 * rather than an invented citation.
 */
export function ExplanationEvidenceList({
  evidence,
  emptyLabel = "No supporting quote is available.",
}: {
  evidence: ExplanationEvidence[];
  emptyLabel?: string;
}) {
  if (!evidence || evidence.length === 0) {
    return <p className="text-xs text-ink-muted">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-1.5">
      {evidence.map((item, index) => (
        <li key={`${item.source}-${index}`} className="text-xs text-ink-muted">
          <span className="font-medium text-ink">{item.source.replace(/_/g, " ")}</span>
          {item.quote ? <span> &mdash; &ldquo;{item.quote}&rdquo;</span> : null}
          {item.context ? (
            <span className="block text-ink-muted">{item.context}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function ExplanationPendingNotice({
  state,
  message,
}: {
  state: ExplanationScreeningState["effective_status"];
  message: string;
}) {
  const tone =
    state === "failed" ? "error-banner" : "info-banner";
  const headline =
    state === "failed"
      ? "Screening failed"
      : state === "queued"
        ? "Screening is queued"
        : state === "running"
          ? "Screening is running"
          : "Not screened yet";

  return (
    <div className={tone} data-testid="explanation-pending">
      <p className="text-sm font-semibold">{headline}</p>
      <p className="mt-1 text-sm">
        {message ||
          "No screening score exists for this application yet. An explanation appears once screening completes."}
      </p>
    </div>
  );
}

/**
 * Which artifacts the explanation was derived from, plus resume-version drift.
 * A drifted resume is surfaced as a caveat rather than silently explaining a
 * different resume than the one that was screened.
 */
export function ExplanationFreshnessBlock({
  freshness,
  limitations,
}: {
  freshness: ExplanationFreshness;
  limitations: string[];
}) {
  const drifted = freshness.screening_resume_is_current_primary === false;
  const evidenceDrifted = freshness.evidence_resume_is_screening_resume === false;

  return (
    <ExplanationCard title="Data freshness and limitations">
      {drifted && (
        <div
          data-testid="explanation-resume-drift"
          className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
        >
          The candidate has uploaded a newer resume since this screening ran. This explanation
          describes the earlier resume and has not been rescored.
        </div>
      )}
      {evidenceDrifted && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Part of this explanation was derived from a different resume version than the one that
          was screened.
        </div>
      )}
      <dl className="grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Screened at</dt>
          <dd className="text-sm text-ink">{formatExplanationDate(freshness.screened_at)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Explainability method
          </dt>
          <dd className="text-sm text-ink">
            {freshness.explainability_method.replace(/_/g, " ")}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Fit engine version
          </dt>
          <dd className="text-sm text-ink">{freshness.fit_engine_version || "Not recorded"}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Evidence engine version
          </dt>
          <dd className="text-sm text-ink">
            {freshness.evidence_engine_version || "Not recorded"}
          </dd>
        </div>
      </dl>
      {limitations.length > 0 && (
        <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-ink-muted">
          {limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </ExplanationCard>
  );
}
