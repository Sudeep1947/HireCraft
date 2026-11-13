import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "../ui/Button";
import { LoadingSpinner } from "../ui/LoadingSpinner";
import { simulationApi } from "../../api/simulations";
import { useToast } from "../../contexts/ToastContext";
import type {
  SimulationResultItem,
  SimulationShortlistApplyResponse,
} from "../../types/simulations";

const MAX_CANDIDATES = 500;
const PAGE_SIZE = 100;

type PanelStep = "closed" | "review" | "confirming";

interface SimulationShortlistPanelProps {
  simulationId: string;
  /** The execution whose hypothetical results the shortlist is chosen from. */
  executionId: string;
  hasResults: boolean;
}

export function SimulationShortlistPanel({
  simulationId,
  executionId,
  hasResults,
}: SimulationShortlistPanelProps) {
  const { addToast } = useToast();

  const [step, setStep] = useState<PanelStep>("closed");
  const [candidates, setCandidates] = useState<SimulationResultItem[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState<SimulationShortlistApplyResponse | null>(null);

  const selectedCount = selected.size;

  const preflight = useCallback(async () => {
    setLoadingCandidates(true);
    setLoadError(null);
    try {
      const rows: SimulationResultItem[] = [];
      let page = 1;
      let total = 0;
      do {
        const res = await simulationApi.listResults(simulationId, {
          execution_id: executionId,
          page,
          page_size: PAGE_SIZE,
          sort_by: "simulation_rank",
          order: "asc",
        });
        rows.push(...res.items);
        total = res.total;
        page += 1;
      } while (rows.length < total && rows.length < MAX_CANDIDATES);

      setCandidates(rows);
      setSelected(
        new Set(
          rows.filter((row) => row.simulation_shortlisted).map((row) => row.candidate_id),
        ),
      );
    } catch {
      setLoadError("Could not load candidates for the shortlist.");
    } finally {
      setLoadingCandidates(false);
    }
  }, [simulationId, executionId]);

  useEffect(() => {
    if (step === "review" && candidates.length === 0 && !loadError && !loadingCandidates) {
      void preflight();
    }
  }, [step, candidates.length, loadError, loadingCandidates, preflight]);

  function openReview() {
    setApplied(null);
    setCandidates([]);
    setSelected(new Set());
    setLoadError(null);
    setStep("review");
  }

  function closePanel() {
    setStep("closed");
    setCandidates([]);
    setSelected(new Set());
  }

  function toggleCandidate(candidateId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(candidateId)) {
        next.delete(candidateId);
      } else {
        next.add(candidateId);
      }
      return next;
    });
  }

  async function confirmApply() {
    if (selectedCount === 0) return;
    setApplying(true);
    try {
      const result = await simulationApi.applyShortlist(simulationId, {
        candidate_ids: [...selected],
        execution_id: executionId,
      });
      setApplied(result);
      setStep("closed");
      if (result.updated.length > 0) {
        addToast(
          `Shortlist applied: ${result.updated.length} candidate${result.updated.length === 1 ? "" : "s"} updated on the live pipeline.`,
          "success",
        );
      } else if (result.skipped.length > 0) {
        addToast("No changes needed — the selected candidates were already shortlisted.", "info");
      }
    } catch (error) {
      const userMessage = (error as { userMessage?: string })?.userMessage;
      addToast(
        userMessage ??
          "Could not apply the shortlist. The live applications may have changed since this simulation ran.",
        "error",
      );
    } finally {
      setApplying(false);
    }
  }

  const summaryText = useMemo(() => {
    if (!applied) return null;
    return `Applied from execution #${applied.execution_id.slice(0, 8)} — ${applied.updated.length} updated, ${applied.skipped.length} already shortlisted.`;
  }, [applied]);

  if (!hasResults) return null;

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="section-title">Optional shortlist</h2>
          <p className="mt-0.5 text-sm text-ink-muted">
            This simulation is hypothetical. Moving candidates onto the live
            shortlist is optional and only happens when you explicitly confirm.
            {summaryText ? ` ${summaryText}` : ""}
          </p>
        </div>
        {!applied && (
          <Button variant="secondary" size="sm" onClick={openReview}>
            Shortlist Candidates
          </Button>
        )}
        {applied && (
          <span className="badge-success">Shortlist applied</span>
        )}
      </div>

      {step !== "closed" && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
          data-testid="shortlist-dialog"
        >
          <div className="card-solid max-h-[90vh] w-full max-w-2xl animate-scale-in overflow-hidden rounded-2xl p-0 shadow-elevated">
            <div className="flex items-start justify-between border-b border-slate-200/70 px-5 py-4">
              <div>
                <h3 className="text-lg font-semibold text-ink">
                  {step === "confirming" ? "Confirm shortlist" : "Choose candidates"}
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  Changes are applied to the live application pipeline only after
                  you confirm. The simulation results are never overwritten.
                </p>
              </div>
              <button
                onClick={closePanel}
                disabled={applying}
                aria-label="Close"
                className="rounded-lg p-1 text-ink-subtle transition-colors duration-200 hover:bg-surface-muted hover:text-ink-muted focus-visible:ring-2 focus-visible:ring-primary-500/60 focus-visible:outline-none"
              >
                &times;
              </button>
            </div>

            <div className="max-h-[50vh] overflow-y-auto px-5 py-4">
              {loadingCandidates ? (
                <div className="flex justify-center py-8">
                  <LoadingSpinner size="md" />
                </div>
              ) : loadError ? (
                <div className="error-banner my-4 justify-center" role="alert">
                  {loadError}
                </div>
              ) : candidates.length === 0 ? (
                <p className="py-8 text-center text-sm text-ink-muted">
                  No candidates are available for this hypothetical shortlist.
                </p>
              ) : (
                <ul className="divide-y divide-slate-200/70">
                  {candidates.map((row) => (
                    <li key={row.candidate_id} className="flex items-center gap-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(row.candidate_id)}
                        onChange={() => toggleCandidate(row.candidate_id)}
                        disabled={applying}
                        aria-label={`Select ${row.candidate_name}`}
                        className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                      />
                      <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-ink">
                          #{row.simulation_rank} · {row.candidate_name}
                        </span>
                        <span className="shrink-0 text-sm text-ink-muted">
                          {row.simulation_score}
                          <span className="ml-2 text-xs text-ink-subtle">sim</span>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-slate-200/70 px-5 py-3">
              <span className="text-sm text-ink-muted">
                {selectedCount} selected
                {selectedCount > 0 ? " — these are set to Shortlisted" : ""}
              </span>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={closePanel} disabled={applying}>
                  Cancel
                </Button>
                {step === "confirming" ? (
                  <>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setStep("review")}
                      disabled={applying}
                    >
                      Back
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      isLoading={applying}
                      disabled={selectedCount === 0}
                      onClick={() => void confirmApply()}
                    >
                      Apply Shortlist ({selectedCount})
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={selectedCount === 0 || loadingCandidates}
                    onClick={() => setStep("confirming")}
                  >
                    Continue
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}