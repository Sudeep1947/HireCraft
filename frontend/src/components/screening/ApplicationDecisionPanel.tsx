/**
 * Phase 8 recruiter decision panel.
 *
 * Renders the decisions the server says are available for this application, so
 * the transition rules live only on the backend. Rejecting opens a confirmation
 * modal that requires a structured reason, keeps the internal note separate and
 * private, and previews the exact wording the candidate will receive.
 *
 * The screening score, recommendation and fairness context are shown as context
 * only: nothing here is derived from them, and this component never decides on
 * the recruiter's behalf.
 */

import { useCallback, useEffect, useState } from "react";
import { recruiterJobApi } from "../../api/jobs";
import { Button } from "../ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/error";
import type {
  ApplicationDecisionOptions,
  ApplicationDecisionResult,
  ApplicationDecisionType,
  RejectionReasonValue,
} from "../../types/applicationDecision";

interface ApplicationDecisionPanelProps {
  applicationId: string;
  /** Called after a decision is committed so the page can refresh. */
  onDecisionMade: (result: ApplicationDecisionResult) => void;
  /**
   * Reports the server's decision affordances upwards, so the page can learn
   * from the backend whether the application is final instead of keeping its
   * own copy of the lifecycle rules.
   */
  onOptionsLoaded?: (options: ApplicationDecisionOptions) => void;
}

const DECISION_VARIANTS: Record<
  ApplicationDecisionType,
  { variant: "primary" | "secondary" | "danger"; className?: string }
> = {
  keep_under_review: { variant: "secondary" },
  // Positive outcome: green, which the shared variants do not cover.
  shortlist: {
    variant: "primary",
    className: "bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500",
  },
  reject: { variant: "danger" },
  // Phase 13: the final positive decision. Visually distinct from a shortlist
  // so it reads as the bigger commitment it is.
  select: {
    variant: "primary",
    className: "bg-emerald-700 hover:bg-emerald-800 focus:ring-emerald-600",
  },
  hire: {
    variant: "primary",
    className: "bg-emerald-700 hover:bg-emerald-800 focus:ring-emerald-600",
  },
};

export function ApplicationDecisionPanel({
  applicationId,
  onDecisionMade,
  onOptionsLoaded,
}: ApplicationDecisionPanelProps) {
  const { addToast } = useToast();
  const [options, setOptions] = useState<ApplicationDecisionOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState<ApplicationDecisionType | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<RejectionReasonValue | "">("");
  const [internalNote, setInternalNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  // Phase 13: selecting is a final, high-impact decision, so it gets the same
  // deliberate two-step confirmation as rejecting instead of firing on click.
  const [selecting, setSelecting] = useState(false);
  const [selectConfirming, setSelectConfirming] = useState(false);
  const [selectNote, setSelectNote] = useState("");

  const loadOptions = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await recruiterJobApi.getApplicationDecisionOptions(applicationId);
      setOptions(data);
      onOptionsLoaded?.(data);
    } catch (err) {
      setLoadError(getErrorMessage(err, "Failed to load decision options"));
    } finally {
      setLoading(false);
    }
    // onOptionsLoaded is intentionally not a dependency: the parent passes an
    // inline callback and including it would re-fetch on every parent render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId]);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  async function submit(
    decision: ApplicationDecisionType,
    extra?: { rejectionReason?: RejectionReasonValue; internalNote?: string },
  ) {
    setPending(decision);
    try {
      const result = await recruiterJobApi.recordApplicationDecision(
        applicationId,
        decision,
        extra,
      );
      addToast(
        decision === "reject"
          ? "Application rejected"
          : decision === "hire"
            ? "Candidate hired"
            : decision === "select"
              ? "Candidate selected"
              : decision === "shortlist"
                ? "Application shortlisted"
                : "Review decision recorded",
        "success",
      );
      setRejecting(false);
      setConfirming(false);
      setReason("");
      setInternalNote("");
      setSelecting(false);
      setSelectConfirming(false);
      setSelectNote("");
      onDecisionMade(result);
      await loadOptions();
    } catch (err) {
      addToast(getErrorMessage(err, "Failed to record decision"), "error");
    } finally {
      setPending(null);
    }
  }

  function openDecision(decision: ApplicationDecisionType) {
    if (decision === "reject") {
      setRejecting(true);
      setConfirming(false);
      setReason("");
      setInternalNote("");
      return;
    }
    // Phase 13: selecting opens a confirmation step first. It is a final
    // decision about a person, so it must never be one click away.
    if (decision === "select") {
      setSelecting(true);
      setSelectConfirming(false);
      setSelectNote("");
      return;
    }
    void submit(decision);
  }

  if (loading) {
    return (
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-ink">Decision</h3>
        <div className="skeleton mt-3 h-4 w-1/3" />
        <div className="skeleton mt-2 h-4 w-1/2" />
        <p className="mt-3 text-sm text-ink-muted">Loading available decisions…</p>
      </div>
    );
  }

  if (loadError || !options) {
    return (
      <div className="error-banner flex-col p-6">
        <h3 className="text-sm font-semibold text-red-900">Decision</h3>
        <p className="mt-2 text-sm text-red-700">{loadError}</p>
      </div>
    );
  }

  const selectedReason = options.rejection_reasons.find((r) => r.value === reason);
  // Phase 13: the server supplies the wording a selection would send, so the
  // confirmation previews the real message rather than a local guess.
  const selectOption = options.options.find((o) => o.decision === "select");
  const canConfirm = reason !== "" && !pending;

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">Decision</h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            Your decision is recorded against this application. Scores and
            fairness metrics are context only and never decide for you.
          </p>
        </div>
        <span className="badge-neutral">
          {options.current_status.replace(/_/g, " ")}
        </span>
      </div>

      {options.status_is_final ? (
        <p className="mt-4 rounded-md bg-gray-100 px-3 py-2 text-sm text-ink-muted">
          This application reached a final status, so no further decision can be
          recorded.
        </p>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {options.options.map((option) => {
            const style = (option.decision && DECISION_VARIANTS[option.decision]) || {
              variant: "secondary" as const,
              className: "",
            };
            return (
              <Button
                key={option.decision}
                variant={style?.variant ?? "secondary"}
                className={style?.className ?? ""}
                onClick={() => openDecision(option.decision)}
                disabled={!option.available || pending !== null}
                title={option.unavailable_reason ?? option.description}
              >
                {pending === option.decision ? "Saving…" : option.label}
              </Button>
            );
          })}
        </div>
      )}

      {!options.status_is_final &&
        options.options.some((o) => !o.available && o.unavailable_reason) && (
          <ul className="mt-3 space-y-1 text-xs text-ink-muted">
            {options.options
              .filter((o) => !o.available && o.unavailable_reason)
              .map((o) => (
                <li key={o.decision}>
                  {o.label}: {o.unavailable_reason}
                </li>
              ))}
          </ul>
        )}
      {rejecting && (
        <div className="mt-5 rounded-lg border border-rose-200 bg-rose-50/60 p-4">
          <h4 className="text-sm font-semibold text-rose-900">
            Reject this application
          </h4>
          <p className="mt-1 text-xs text-rose-800">
            A reason is required. The candidate sees the approved wording for
            the reason you choose; your internal note stays private.
          </p>

          <div className="mt-4">
            <label htmlFor="decision-reason" className="field-label">
              Rejection reason (required)
            </label>
            <select
              id="decision-reason"
              aria-label="Rejection reason"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value as RejectionReasonValue | "");
                setConfirming(false);
              }}
              className="field mt-1"
            >
              <option value="">Select a reason…</option>
              {options.rejection_reasons.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-4">
            <label htmlFor="decision-internal-note" className="field-label">
              Internal note (private, never shown to the candidate)
            </label>
            <textarea
              id="decision-internal-note"
              aria-label="Internal note"
              rows={3}
              value={internalNote}
              onChange={(e) => setInternalNote(e.target.value)}
              placeholder="Context for your team. The candidate never sees this."
              className="field mt-1"
            />
          </div>

          {selectedReason && (
            <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <p className="text-xs font-semibold text-ink">
                The candidate will see:
              </p>
              <p className="mt-1 text-sm text-ink">
                {selectedReason.candidate_message}
              </p>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {!confirming ? (
              <>
                <Button
                  onClick={() => setConfirming(true)}
                  disabled={!canConfirm}
                  variant="danger"
                >
                  Review rejection
                </Button>
                <Button onClick={() => setRejecting(false)} variant="ghost">
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <p className="w-full text-xs font-medium text-rose-800">
                  Confirm: this moves the application to Rejected and notifies
                  the candidate.
                </p>
                <Button
                  onClick={() =>
                    void submit("reject", {
                      rejectionReason: reason as RejectionReasonValue,
                      internalNote: internalNote.trim() || undefined,
                    })
                  }
                  disabled={!canConfirm}
                  variant="danger"
                >
                  {pending === "reject" ? "Rejecting…" : "Confirm rejection"}
                </Button>
                <Button onClick={() => setConfirming(false)} variant="ghost">
                  Back
                </Button>
              </>
            )}
          </div>
        </div>
      )}
      {selecting && (
        <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50/60 p-4">
          <h4 className="text-sm font-semibold text-emerald-900">
            Select this candidate
          </h4>
          <p className="mt-1 text-xs text-emerald-800">
            This records your choice for this role. It is your decision alone:
            no score, assessment result or interview rating can make it for you.
          </p>
          <p className="mt-2 rounded-md bg-white/70 px-3 py-2 text-xs text-emerald-900">
            Selecting is not the same as being hired. The offer still has to be
            extended and accepted, and the candidate can still withdraw.
          </p>

          {selectOption?.candidate_message && (
            <div className="mt-4 rounded-xl border border-gray-200 bg-white p-3">
              <p className="text-xs font-semibold text-ink">
                The candidate will see:
              </p>
              <p className="mt-1 text-sm text-ink">
                {selectOption.candidate_message}
              </p>
            </div>
          )}

          <div className="mt-4">
            <label htmlFor="select-internal-note" className="field-label">
              Internal note (optional, private, never shown to the candidate)
            </label>
            <textarea
              id="select-internal-note"
              aria-label="Select internal note"
              rows={2}
              value={selectNote}
              onChange={(e) => {
                setSelectNote(e.target.value);
                setSelectConfirming(false);
              }}
              placeholder="Why you chose this candidate. The candidate never sees this."
              className="field mt-1"
            />
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {!selectConfirming ? (
              <>
                <Button
                  onClick={() => setSelectConfirming(true)}
                  disabled={pending !== null}
                  variant="primary"
                  className="bg-emerald-700 hover:bg-emerald-800 focus:ring-emerald-600"
                >
                  Review selection
                </Button>
                <Button onClick={() => setSelecting(false)} variant="ghost">
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <p className="w-full text-xs font-medium text-emerald-900">
                  Confirm: this moves the application to Selected and notifies
                  the candidate.
                </p>
                <Button
                  onClick={() =>
                    void submit(
                      "select",
                      selectNote.trim()
                        ? { internalNote: selectNote.trim() }
                        : undefined,
                    )
                  }
                  disabled={pending !== null}
                  variant="primary"
                  className="bg-emerald-700 hover:bg-emerald-800 focus:ring-emerald-600"
                >
                  {pending === "select" ? "Selecting…" : "Confirm selection"}
                </Button>
                <Button
                  onClick={() => setSelectConfirming(false)}
                  variant="ghost"
                >
                  Back
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ApplicationDecisionPanel;
