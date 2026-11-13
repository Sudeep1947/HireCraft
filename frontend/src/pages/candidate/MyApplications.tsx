import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { IdentifierGrid } from "../../components/ui/IdentifierField";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { candidateJobApi } from "../../api/jobs";
import { getErrorMessage } from "../../utils/error";
import { formatDate } from "../../utils/dateTime";
import type { JobApplication } from "../../types/jobs";
import type { CandidateApplicationDecision } from "../../types/applicationDecision";

export function MyApplications() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [decisions, setDecisions] = useState<CandidateApplicationDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // One request for the decision projections, not one per application.
      const [data, decisionData] = await Promise.all([
        candidateJobApi.getMyApplications(),
        candidateJobApi.getMyApplicationDecisions(),
      ]);
      setApplications(data);
      setDecisions(decisionData);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load applications"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const decisionByApplication = useMemo(() => {
    const map = new Map<string, CandidateApplicationDecision>();
    for (const decision of decisions) map.set(decision.application_id, decision);
    return map;
  }, [decisions]);

  // The filter options are derived from the applications the server actually
  // returned, and their wording comes from the server's status label. The page
  // holds no status vocabulary of its own, so it cannot offer a stage the
  // lifecycle does not have or spell one the way the API does not.
  const statusOptions = useMemo(() => {
    const counts = new Map<string, number>();
    const firstIdByStatus = new Map<string, string>();
    for (const application of applications) {
      if (!firstIdByStatus.has(application.status)) {
        firstIdByStatus.set(application.status, application.id);
      }
      counts.set(application.status, (counts.get(application.status) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([status, count]) => ({
        status,
        count,
        label:
          decisionByApplication.get(firstIdByStatus.get(status)!)?.status_label ??
          status.replace(/_/g, " "),
      }));
  }, [applications, decisionByApplication]);

  const visibleApplications = useMemo(
    () =>
      statusFilter
        ? applications.filter((application) => application.status === statusFilter)
        : applications,
    [applications, statusFilter],
  );

  async function handleWithdraw(id: string) {
    if (!window.confirm("Withdraw this application?")) return;
    try {
      await candidateJobApi.withdrawApplication(id);
      setApplications(applications.map((a) => (a.id === id ? { ...a, status: "withdrawn" } : a)));
      // Re-read the decision projection so the row reflects the new outcome.
      try {
        setDecisions(await candidateJobApi.getMyApplicationDecisions());
      } catch {
        // The withdrawal succeeded; a stale label is not worth an error toast.
      }
      addToast("Application withdrawn", "success");
    } catch {
      addToast("Failed to withdraw application", "error");
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  if (error) {
    return (
      <div className="mx-auto max-w-2xl animate-fade-up py-12">
        <div className="flex flex-col items-center gap-3 rounded-[8px] border border-red-200 bg-red-50/90 p-8 text-center shadow-xs">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Could not load your applications
          </p>
          <p className="text-sm text-red-700">{error}</p>
          <Button variant="secondary" className="rounded-[6px]" onClick={() => void load()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    applied: "badge-info",
    under_review: "badge-warning",
    shortlisted: "badge-info",
    interview_scheduled: "badge-info",
    interviewed: "badge-info",
    offered: "badge-success",
    hired: "badge-success",
    rejected: "badge-danger",
    withdrawn: "badge-neutral",
  };

  const screeningColors: Record<string, string> = {
    not_started: "badge-neutral",
    queued: "badge-warning",
    running: "badge-info",
    completed: "badge-success",
    failed: "badge-danger",
    skipped: "badge-neutral",
  };

  return (
    <div className="animate-fade-up space-y-6">
      <div className="page-header">
        <h1 className="page-title">My Applications</h1>
        <p className="page-subtitle">Track your job applications</p>
      </div>

      {applications.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-[8px] border border-dashed border-gray-300 bg-white/70 px-6 py-12 text-center">
          <p className="text-gray-500">No applications yet.</p>
          <button
            onClick={() => navigate("/candidate/jobs")}
            className="btn-secondary rounded-[6px] mt-4"
          >
            Browse jobs
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {statusOptions.length > 1 ? (
            <div className="flex items-center gap-2">
              <label htmlFor="application-status-filter" className="text-sm font-medium text-gray-600">
                Filter by status
              </label>
              <select
                id="application-status-filter"
                aria-label="Filter by status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="w-auto rounded-[6px] border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">All statuses</option>
                {statusOptions.map((option) => (
                  <option key={option.status} value={option.status}>
                    {option.label} ({option.count})
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {visibleApplications.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-[8px] border border-dashed border-gray-300 bg-white/70 px-6 py-12 text-center">
              <p className="text-sm text-gray-500">No applications match this status.</p>
              <button
                onClick={() => setStatusFilter("")}
                className="btn-secondary rounded-[6px] mt-3"
              >
                Show all applications
              </button>
            </div>
          ) : (
            visibleApplications.map((app) => {
            const decision = decisionByApplication.get(app.id) ?? null;
            return (
            <div key={app.id} className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-xs transition-all hover:border-indigo-200 hover:shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{app.job_title || "Unknown Position"}</h3>
                  <p className="text-sm text-gray-500">{app.company}{app.location ? ` · ${app.location}` : ""}</p>
                  <p className="mt-1 text-xs text-gray-400">Applied: {formatDate(app.created_at)}</p>
                  {app.screening_status ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className={screeningColors[app.screening_status] || "badge-neutral"}>
                        Screening: {app.screening_status.replace(/_/g, " ")}
                      </span>
                      {app.screening_status === "failed" && app.screening_error && (
                        <span className="text-xs text-red-500">Profile incomplete — add skills to improve your match</span>
                      )}
                    </div>
                  ) : null}
                </div>
                <div className="flex flex-col items-start gap-2 sm:items-end">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={statusColors[app.status] || "badge-neutral"}>
                    {decision?.status_label ?? app.status.replace(/_/g, " ")}
                  </span>
                  {app.status === "applied" || app.status === "under_review" ? (
                    <button onClick={() => handleWithdraw(app.id)} className="rounded-[4px] px-2 py-1 text-xs font-medium text-red-600 hover:text-red-700 hover:bg-red-50">
                      Withdraw
                    </button>
                  ) : null}
                </div>
                {app.screening_status === "completed" ? (
                  <button
                    onClick={() => navigate(`/candidate/applications/${app.id}/explanation`)}
                    className="btn-ghost rounded-[6px] px-2 py-1 text-xs text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50/60"
                  >
                    How does my profile match?
                  </button>
                ) : null}
                </div>
              </div>
              {/* Phase 8: the candidate's decision outcome. This is the approved
                  wording for the recorded reason; the recruiter's internal note,
                  score, ranking and fairness data are never sent here. */}
              {decision?.candidate_message ? (
                <div className="mt-3 rounded-[6px] border border-indigo-100 bg-indigo-50/40 px-3.5 py-2.5">
                  <p className="text-sm text-gray-700">{decision.candidate_message}</p>
                  {decision.decided_at ? (
                    <p className="mt-1 text-xs text-gray-500">
                      Updated {formatDate(decision.decided_at)}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {app.cover_letter && (
                <p className="mt-2 text-sm text-gray-600 line-clamp-2">{app.cover_letter}</p>
              )}
              {/* The application reference and status & activity action footer */}
              <div className="mt-4 border-t border-gray-100 pt-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <IdentifierGrid
                    columns={2}
                    items={[
                      {
                        label: "Application ID",
                        value: app.id,
                        hint: "Your reference for this application.",
                      },
                      { label: "Job ID", value: app.job_id, copyable: false },
                    ]}
                  />
                  <button
                    onClick={() => navigate(`/candidate/applications/${app.id}`)}
                    className="btn-secondary rounded-[6px] shrink-0 self-start sm:self-center px-3 py-1.5 text-xs font-semibold"
                  >
                    View status &amp; activity &rarr;
                  </button>
                </div>
              </div>
            </div>
            );
            })
          )}
        </div>
      )}
    </div>
  );
}
