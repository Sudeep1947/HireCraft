import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { MatchScoreCard } from "../../components/screening/MatchScoreCard";
import { ApplicationDecisionPanel } from "../../components/screening/ApplicationDecisionPanel";
import { ApplicationInterviewPanel } from "../../components/screening/ApplicationInterviewPanel";
import { ApplicationAssessmentPanel } from "../../components/screening/ApplicationAssessmentPanel";
import {
  JobBulkAssessmentPanel,
  type BulkAssignSelection,
} from "../../components/screening/JobBulkAssessmentPanel";
import { ApplicationIdentityCard } from "../../components/ui/ApplicationIdentityCard";
import { useToast } from "../../contexts/ToastContext";
import { recruiterJobApi } from "../../api/jobs";
import { screenApplication } from "../../api/screening";
import { getErrorMessage } from "../../utils/error";
import type {
  ApplicantDashboardItem,
  ApplicantDashboardQuery,
  ApplicantDashboardResponse,
  ApplicantDashboardSort,
  ApplicantScreeningStatus,
  ApplicantSummary,
} from "../../types/jobs";
import type { HiringRecommendation, StrengthLevel } from "../../types/screening";
import type {
  ApplicationDecisionOptions,
  ApplicationDecisionResult,
} from "../../types/applicationDecision";
import type {
  ApplicationInterviewScheduleResult,
  ApplicationStatus,
} from "../../types/interview";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 350;
const DEFAULT_SORT: ApplicantDashboardSort = "-created_at";

// NOTE: there is deliberately no client-side transition table here. Which
// decisions are legal, and whether an application is final, come from the
// server via `GET /applications/{id}/decision-options`, so the lifecycle rules
// cannot drift between client and backend.

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

const SCREENING_STATUS_LABELS: Record<ApplicantScreeningStatus, string> = {
  not_started: "Not Screened",
  queued: "Queued",
  running: "Running",
  completed: "Screened",
  failed: "Failed",
  skipped: "Skipped",
};

const SCREENING_STATUS_STYLES: Record<ApplicantScreeningStatus, string> = {
  not_started: "bg-gray-100 text-gray-700",
  queued: "bg-yellow-100 text-yellow-800",
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

const STRENGTH_STYLES: Record<StrengthLevel, string> = {
  excellent: "bg-green-100 text-green-800",
  good: "bg-blue-100 text-blue-800",
  average: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

const SORT_OPTIONS: Array<{ value: ApplicantDashboardSort; label: string }> = [
  { value: "-created_at", label: "Newest applied" },
  { value: "created_at", label: "Oldest applied" },
  { value: "-overall_match_score", label: "Highest match score" },
  { value: "overall_match_score", label: "Lowest match score" },
  { value: "candidate_name", label: "Candidate name (A-Z)" },
  { value: "-candidate_name", label: "Candidate name (Z-A)" },
  { value: "status", label: "Application status" },
  { value: "-status", label: "Application status (reverse)" },
];

const selectClass =
  "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400";

// Statuses the server treats as final. Used only as a pre-load fallback while
// the authoritative decision options load; it encodes no allowed transitions.
const FINAL_APPLICATION_STATUSES = new Set([
  "rejected",
  "withdrawn",
  "offered",
  "hired",
]);

function statusBadgeClass(status: string): string {
  switch (status) {
    case "applied":
      return "bg-blue-100 text-blue-800";
    case "under_review":
      return "bg-yellow-100 text-yellow-800";
    case "shortlisted":
      return "bg-purple-100 text-purple-800";
    case "interview_scheduled":
      return "bg-purple-100 text-purple-800";
    case "interviewed":
      return "bg-teal-100 text-teal-800";
    case "offered":
      return "bg-indigo-100 text-indigo-800";
    case "hired":
      return "bg-green-100 text-green-800";
    case "rejected":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

function scoreTextClass(score: number): string {
  if (score >= 80) return "text-green-700";
  if (score >= 60) return "text-blue-700";
  if (score >= 40) return "text-yellow-700";
  return "text-red-700";
}

function applicantName(item: ApplicantDashboardItem): string {
  return item.candidate_name || "Unnamed candidate";
}

function parseScoreInput(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > 100) return null;
  return parsed;
}

export function RecruiterJobApplicants() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();
  const requestedSelection = searchParams.get("application");

  const [data, setData] = useState<ApplicantDashboardResponse | null>(null);
  const [summary, setSummary] = useState<ApplicantSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [screeningAppId, setScreeningAppId] = useState<string | null>(null);
  const [screeningError, setScreeningError] = useState<{ appId: string; message: string } | null>(null);
  // Server-provided decision affordances for the selected application.
  const [decisionOptions, setDecisionOptions] = useState<ApplicationDecisionOptions | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [applicationStatus, setApplicationStatus] = useState("");
  const [screeningStatus, setScreeningStatus] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [minScoreQuery, setMinScoreQuery] = useState("");
  const [maxScoreQuery, setMaxScoreQuery] = useState("");
  const [sortBy, setSortBy] = useState<ApplicantDashboardSort>(DEFAULT_SORT);
  const [page, setPage] = useState(1);

  // Phase 1 bulk assignment: an application id -> candidate name snapshot for
  // every row the recruiter has ticked. The name is captured at selection time
  // so the confirmation panel can name each candidate even though the dashboard
  // result set may be replaced underneath it by a refresh or a page change.
  const [assignSelection, setAssignSelection] = useState<Map<string, string>>(new Map());
  const [bulkPanelOpen, setBulkPanelOpen] = useState(false);

  const requestIdRef = useRef(0);

  const minScoreValue = parseScoreInput(minScoreQuery);
  const maxScoreValue = parseScoreInput(maxScoreQuery);
  const scoreRangeInverted = minScoreValue !== null && maxScoreValue !== null && minScoreValue > maxScoreValue;

  const query = useMemo<ApplicantDashboardQuery>(() => {
    const next: ApplicantDashboardQuery = { sort_by: sortBy, page, page_size: PAGE_SIZE };
    if (search) next.q = search;
    if (applicationStatus) next.application_status = applicationStatus;
    if (screeningStatus) next.screening_status = screeningStatus as ApplicantScreeningStatus;
    if (recommendation) next.recommendation = recommendation as HiringRecommendation;
    if (!scoreRangeInverted) {
      if (minScoreValue !== null) next.min_score = minScoreValue;
      if (maxScoreValue !== null) next.max_score = maxScoreValue;
    }
    return next;
  }, [
    search,
    applicationStatus,
    screeningStatus,
    recommendation,
    minScoreValue,
    maxScoreValue,
    scoreRangeInverted,
    sortBy,
    page,
  ]);

  const applyResponse = useCallback(
    (result: ApplicantDashboardResponse) => {
      setData(result);
      setSummary(result.summary);
      setLoadError(null);
      setAccessDenied(null);
      const maxPage = Math.max(1, result.total_pages);
      if (page > maxPage) setPage(maxPage);
    },
    [page],
  );

  const loadDashboard = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!id) return;
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;
      if (options?.silent) setRefreshing(true);
      else setLoading(true);
      try {
        const result = await recruiterJobApi.getApplicantDashboard(id, query);
        if (requestId !== requestIdRef.current) return;
        applyResponse(result);
      } catch (err) {
        if (requestId !== requestIdRef.current) return;
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 403) {
          setAccessDenied(getErrorMessage(err, "You do not have permission to view applicants for this job."));
        } else if (status === 404) {
          setLoadError("This job could not be found. It may have been deleted.");
        } else {
          setLoadError(getErrorMessage(err, "Failed to load applicants."));
        }
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [id, query, applyResponse],
  );

  const loadDashboardRef = useRef(loadDashboard);
  loadDashboardRef.current = loadDashboard;

  const previousJobIdRef = useRef(id);
  const skipNextLoadRef = useRef(false);

  useEffect(() => {
    if (previousJobIdRef.current === id) return;
    previousJobIdRef.current = id;
    skipNextLoadRef.current = true;
    requestIdRef.current += 1;
    setData(null);
    setSummary(null);
    setLoadError(null);
    setAccessDenied(null);
    setRefreshing(false);
    setLoading(true);
    setSelectedId(null);
    setNoteText("");
    setSavingNote(false);
    setScreeningAppId(null);
    setScreeningError(null);
    setSearchInput("");
    setSearch("");
    setApplicationStatus("");
    setScreeningStatus("");
    setRecommendation("");
    setMinScore("");
    setMaxScore("");
    setMinScoreQuery("");
    setMaxScoreQuery("");
    setSortBy(DEFAULT_SORT);
    setPage(1);
    setAssignSelection(new Map());
    setBulkPanelOpen(false);
  }, [id]);

  useEffect(() => {
    if (skipNextLoadRef.current) {
      skipNextLoadRef.current = false;
      return;
    }
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setMinScoreQuery(minScore.trim());
      setMaxScoreQuery(maxScore.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchInput, minScore, maxScore]);

  const items = useMemo(() => data?.items ?? [], [data]);
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 0;
  const pageSize = data?.page_size ?? PAGE_SIZE;

  useEffect(() => {
    if (!requestedSelection) return;
    if (items.length === 0) return;
    setSelectedId(items.some((item) => item.id === requestedSelection) ? requestedSelection : null);
  }, [requestedSelection, items]);

  // Clear the previous applicant's decision affordances when the selection
  // changes, so a stale status can never be shown for a new selection.
  useEffect(() => {
    setDecisionOptions(null);
  }, [selectedId]);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );

  const selectionItems = useMemo<BulkAssignSelection[]>(
    () =>
      Array.from(assignSelection, ([applicationId, candidateName]) => ({
        applicationId,
        candidateName,
      })),
    [assignSelection],
  );
  const allOnPageSelected = items.length > 0 && items.every((item) => assignSelection.has(item.id));

  const screeningResult = selected?.screening_result ?? null;
  const screeningState: ApplicantScreeningStatus = selected?.effective_screening_status ?? "not_started";
  const effectiveScore = selected?.overall_match_score ?? screeningResult?.overall_match_score ?? null;
  const effectiveRecommendation = selected?.recommendation ?? screeningResult?.recommendation ?? null;
  const effectiveStrength = selected?.strength_level ?? screeningResult?.strength_level ?? null;
  const isScreeningInFlight = screeningState === "queued" || screeningState === "running";
  // Whether an application is final is reported by the server, not assumed
  // from a client-side transition table. Until that request resolves we fall
  // back to the row's own status so screening controls never flash back on for
  // an already-final application.
  const isTerminalApplication =
    selected !== null &&
    (decisionOptions?.application_id === selected.id
      ? decisionOptions.status_is_final
      : FINAL_APPLICATION_STATUSES.has(selected.status));
  const canRunScreening =
    selected !== null && screeningResult === null && !isScreeningInFlight && !isTerminalApplication;
  const isRunningThis = screeningAppId !== null && screeningAppId === selected?.id;
  const activeScreeningError =
    screeningError && screeningError.appId === selected?.id
      ? screeningError.message
      : (selected?.screening_error ?? null);

  const selectionMissing =
    Boolean(requestedSelection) &&
    !loading &&
    !loadError &&
    !accessDenied &&
    data !== null &&
    !items.some((item) => item.id === requestedSelection);

  const minScoreOutOfRange = minScore.trim() !== "" && parseScoreInput(minScore) === null;
  const maxScoreOutOfRange = maxScore.trim() !== "" && parseScoreInput(maxScore) === null;
  const scoreRangeInvalid =
    minScore.trim() !== "" &&
    maxScore.trim() !== "" &&
    Number(minScore) > Number(maxScore);

  const hasActiveFilters =
    searchInput.trim() !== "" ||
    applicationStatus !== "" ||
    screeningStatus !== "" ||
    recommendation !== "" ||
    minScore !== "" ||
    maxScore !== "" ||
    sortBy !== DEFAULT_SORT;

  const totalApplicants = summary?.total_applicants ?? total;
  const inProgressCount = (summary?.queued ?? 0) + (summary?.running ?? 0);

  function patchItem(appId: string, patch: Partial<ApplicantDashboardItem>) {
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        items: prev.items.map((item) => (item.id === appId ? { ...item, ...patch } : item)),
      };
    });
  }

  function selectApplicant(appId: string) {
    setSelectedId(appId);
    setScreeningError(null);
    setNoteText("");
    const next = new URLSearchParams(searchParams);
    next.set("application", appId);
    setSearchParams(next, { replace: true });
  }

  function toggleAssignSelection(appId: string, candidateName: string) {
    setAssignSelection((prev) => {
      const next = new Map(prev);
      if (next.has(appId)) next.delete(appId);
      else next.set(appId, candidateName);
      return next;
    });
  }

  function toggleSelectAllOnPage() {
    setAssignSelection((prev) => {
      const next = new Map(prev);
      const allSelected = items.length > 0 && items.every((item) => next.has(item.id));
      if (allSelected) {
        for (const item of items) next.delete(item.id);
      } else {
        for (const item of items) next.set(item.id, applicantName(item));
      }
      return next;
    });
  }

  function clearAssignSelection() {
    setAssignSelection(new Map());
    setBulkPanelOpen(false);
  }

  function clearFilters() {
    setSearchInput("");
    setSearch("");
    setApplicationStatus("");
    setScreeningStatus("");
    setRecommendation("");
    setMinScore("");
    setMaxScore("");
    setMinScoreQuery("");
    setMaxScoreQuery("");
    setSortBy(DEFAULT_SORT);
    setPage(1);
  }

  async function handleDecisionMade(result: ApplicationDecisionResult) {
    if (selectedId === null) return;
    // Reflect the committed decision immediately, then reconcile with the
    // server so the row, the status filters and the counts all agree.
    patchItem(selectedId, { status: result.status });
    await loadDashboardRef.current({ silent: true });
  }

  async function handleInterviewStatusChanged(
    result: ApplicationInterviewScheduleResult,
  ) {
    if (selectedId === null) return;
    // Scheduling or completing an interview moves the application, so the row and
    // the status counts are now stale. Reconciling with the server rather than
    // trusting the local patch keeps the filters honest, since the status decides
    // which tab the row appears under.
    patchItem(selectedId, { status: result.application_status });
    await loadDashboardRef.current({ silent: true });
  }

  async function handleInterviewApplicationStatusChanged(status: ApplicationStatus) {
    if (selectedId === null) return;
    // Rejecting from the interview panel returns a smaller result than a schedule
    // call, but it still moves the application, so reconcile the same way.
    patchItem(selectedId, { status });
    await loadDashboardRef.current({ silent: true });
  }

  async function handleAddNote(appId: string) {
    if (!noteText.trim()) return;
    setSavingNote(true);
    try {
      const note = await recruiterJobApi.addNote(appId, noteText);
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          items: prev.items.map((item) =>
            item.id === appId
              ? { ...item, recruiter_notes: [...(item.recruiter_notes || []), note] }
              : item,
          ),
        };
      });
      setNoteText("");
      addToast("Note added", "success");
    } catch (err) {
      addToast(getErrorMessage(err, "Failed to add note"), "error");
    } finally {
      setSavingNote(false);
    }
  }

  async function handleRunScreening(appId: string) {
    if (screeningAppId) return;
    setScreeningAppId(appId);
    setScreeningError(null);
    patchItem(appId, { effective_screening_status: "queued" });
    try {
      const result = await screenApplication(appId);
      patchItem(appId, {
        effective_screening_status: "completed",
        screening_error: null,
        screening_result: result,
        overall_match_score: result.overall_match_score,
        recommendation: result.recommendation,
        strength_level: result.strength_level,
        screening_completed_at: new Date().toISOString(),
      });
      addToast("Screening completed", "success");
      await loadDashboardRef.current({ silent: true });
    } catch (err) {
      const message = getErrorMessage(err, "Failed to run screening for this applicant.");
      setScreeningError({ appId, message });
      patchItem(appId, { effective_screening_status: "failed", screening_error: message });
      addToast(message, "error");
      await loadDashboardRef.current({ silent: true });
    } finally {
      setScreeningAppId(null);
    }
  }

  if (loading && !data) return <LoadingSpinner size="lg" className="mt-20" />;

  if (accessDenied) {
    return (
      <div className="mx-auto max-w-2xl py-12 text-center">
        <div className="rounded-lg border border-red-200 bg-red-50 p-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">Access denied</p>
          <p className="mt-2 text-sm text-red-700">{accessDenied}</p>
          <Button variant="secondary" className="mt-5" onClick={() => loadDashboard()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-2xl py-12 text-center">
        <div className="rounded-lg border border-red-200 bg-red-50 p-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">Could not load applicants</p>
          <p className="mt-2 text-sm text-red-700">
            {loadError ?? "An unexpected error occurred while loading this job."}
          </p>
          <Button variant="secondary" className="mt-5" onClick={() => loadDashboard()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  const statCards = [
    { label: "Total applicants", value: String(totalApplicants), hint: `${total} match current filters` },
    {
      label: "Screened",
      value: String(summary?.total_screened ?? 0),
      hint: `${summary?.high_match_count ?? 0} high match`,
    },
    {
      label: "Not screened",
      value: String(summary?.not_screened ?? 0),
      hint: `${summary?.queued ?? 0} queued`,
    },
    {
      label: "In progress",
      value: String(inProgressCount),
      hint: `${summary?.running ?? 0} running`,
    },
    {
      label: "Average score",
      value: summary?.average_score !== null && summary?.average_score !== undefined
        ? summary.average_score.toFixed(1)
        : "--",
      hint: `${summary?.total_screened ?? 0} scored`,
    },
    {
      label: "Failed",
      value: String(summary?.failed ?? 0),
      hint: `${summary?.skipped ?? 0} skipped`,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900">Applicants for {data.job.title}</h1>
          <p className="text-sm text-gray-500">
            {totalApplicants} total applicants &middot; {summary?.total_screened ?? 0} screened
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {refreshing && <LoadingSpinner size="sm" />}
          <Button variant="secondary" size="sm" onClick={() => loadDashboard({ silent: true })}>
            Refresh
          </Button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {loadError}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {statCards.map((card) => (
          <div key={card.label} className="rounded-lg border bg-white px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{card.label}</p>
            <p className="mt-1 text-xl font-bold text-gray-900">{card.value}</p>
            <p className="mt-0.5 truncate text-xs text-gray-400">{card.hint}</p>
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-white p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            id="applicant-search"
            label="Search"
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Name or email"
          />
          <div className="space-y-1">
            <label htmlFor="filter-application-status" className="block text-sm font-medium text-gray-700">
              Application status
            </label>
            <select
              id="filter-application-status"
              value={applicationStatus}
              onChange={(e) => {
                setApplicationStatus(e.target.value);
                setPage(1);
              }}
              className={selectClass}
            >
              <option value="">All statuses</option>
              {Object.keys(STATUS_LABELS).map((value) => (
                <option key={value} value={value}>
                  {STATUS_LABELS[value]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="filter-screening-status" className="block text-sm font-medium text-gray-700">
              Screening status
            </label>
            <select
              id="filter-screening-status"
              value={screeningStatus}
              onChange={(e) => {
                setScreeningStatus(e.target.value);
                setPage(1);
              }}
              className={selectClass}
            >
              <option value="">All screening states</option>
              {(Object.keys(SCREENING_STATUS_LABELS) as ApplicantScreeningStatus[]).map((value) => (
                <option key={value} value={value}>
                  {SCREENING_STATUS_LABELS[value]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="filter-recommendation" className="block text-sm font-medium text-gray-700">
              Recommendation
            </label>
            <select
              id="filter-recommendation"
              value={recommendation}
              onChange={(e) => {
                setRecommendation(e.target.value);
                setPage(1);
              }}
              className={selectClass}
            >
              <option value="">All recommendations</option>
              {(Object.keys(RECOMMENDATION_LABELS) as HiringRecommendation[]).map((value) => (
                <option key={value} value={value}>
                  {RECOMMENDATION_LABELS[value]}
                </option>
              ))}
            </select>
          </div>
          <Input
            id="filter-min-score"
            label="Min match score"
            type="number"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => {
              setMinScore(e.target.value);
              setPage(1);
            }}
            placeholder="0"
            className={scoreRangeInvalid || minScoreOutOfRange ? "border-red-300" : ""}
            error={
              minScoreOutOfRange
                ? "Enter a whole number between 0 and 100"
                : scoreRangeInvalid
                  ? "Minimum cannot exceed maximum"
                  : undefined
            }
          />
          <Input
            id="filter-max-score"
            label="Max match score"
            type="number"
            min={0}
            max={100}
            value={maxScore}
            onChange={(e) => {
              setMaxScore(e.target.value);
              setPage(1);
            }}
            placeholder="100"
            className={scoreRangeInvalid || maxScoreOutOfRange ? "border-red-300" : ""}
            error={
              maxScoreOutOfRange
                ? "Enter a whole number between 0 and 100"
                : scoreRangeInvalid
                  ? "Minimum cannot exceed maximum"
                  : undefined
            }
          />
          <div className="space-y-1">
            <label htmlFor="filter-sort" className="block text-sm font-medium text-gray-700">
              Sort by
            </label>
            <select
              id="filter-sort"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as ApplicantDashboardSort);
                setPage(1);
              }}
              className={selectClass}
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <Button variant="secondary" onClick={clearFilters} disabled={!hasActiveFilters} className="w-full">
              Clear filters
            </Button>
          </div>
        </div>
      </div>

      {selectionItems.length > 0 && (
        <div className="flex flex-col gap-2 rounded-lg border border-primary-200 bg-primary-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-medium text-primary-900">
            {selectionItems.length} applicant{selectionItems.length === 1 ? "" : "s"} selected
          </p>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={clearAssignSelection}>
              Clear selection
            </Button>
            <Button size="sm" onClick={() => setBulkPanelOpen(true)}>
              Bulk assign assessment
            </Button>
          </div>
        </div>
      )}

      {bulkPanelOpen && selectionItems.length > 0 && (
        <JobBulkAssessmentPanel
          jobId={id ?? data.job.id}
          selection={selectionItems}
          onClose={clearAssignSelection}
        />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <div className="rounded-lg border bg-white">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div className="flex items-center gap-2">
                {items.length > 0 && (
                  <input
                    type="checkbox"
                    aria-label="Select all applicants on this page"
                    checked={allOnPageSelected}
                    onChange={toggleSelectAllOnPage}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                )}
                <h2 className="font-semibold text-gray-900">Applicants</h2>
              </div>
              <span className="text-xs text-gray-500">
                {total === 0 ? "0" : `${rangeStart}-${rangeEnd}`} of {total}
              </span>
            </div>
            <div className="divide-y lg:max-h-[640px] lg:overflow-y-auto">
              {items.length === 0 ? (
                <div className="px-4 py-10 text-center">
                  <p className="text-sm text-gray-500">
                    {totalApplicants > 0
                      ? "No applicants match the current filters."
                      : "No applicants yet."}
                  </p>
                  {hasActiveFilters && (
                    <Button variant="ghost" size="sm" className="mt-3" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  )}
                </div>
              ) : (
                items.map((item) => {
                  const isSelected = item.id === selectedId;
                  return (
                    <div
                      key={item.id}
                      className={`flex items-start gap-2 px-4 py-3 transition-colors hover:bg-gray-50 ${
                        isSelected ? "bg-primary-50" : ""
                      }`}
                    >
                      <input
                        type="checkbox"
                        aria-label={`Select ${applicantName(item)}`}
                        checked={assignSelection.has(item.id)}
                        onChange={() => toggleAssignSelection(item.id, applicantName(item))}
                        className="mt-0.5 h-4 w-4 shrink-0 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      <button
                        onClick={() => selectApplicant(item.id)}
                        className="min-w-0 flex-1 text-left"
                      >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-gray-900">{applicantName(item)}</p>
                          <p className="truncate text-xs text-gray-500">{item.candidate_email || "No email on file"}</p>
                        </div>
                        {item.overall_match_score !== null && (
                          <span
                            className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${scoreTextClass(
                              item.overall_match_score,
                            )}`}
                          >
                            {item.overall_match_score}
                          </span>
                        )}
                      </div>
                      {/* A compact, labelled handle on the two identifiers that
                          identify this row, so the recruiter can correlate a
                          record with a candidate without opening it. Kept to one
                          short line each: the full values and their copy
                          buttons are in the detail pane, and a UUID repeated at
                          full length down a list of twenty would be unreadable
                          and impossible to scan. */}
                      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
                        <span className="min-w-0">
                          <span className="text-gray-400">Candidate ID </span>
                          <code className="font-mono" title={item.candidate_id}>
                            {item.candidate_id.slice(0, 8)}…
                          </code>
                        </span>
                        <span className="min-w-0">
                          <span className="text-gray-400">Application ID </span>
                          <code className="font-mono" title={item.id}>
                            {item.id.slice(0, 8)}…
                          </code>
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(
                            item.status,
                          )}`}
                        >
                          {STATUS_LABELS[item.status] || item.status.replace(/_/g, " ")}
                        </span>
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                            SCREENING_STATUS_STYLES[item.effective_screening_status] ??
                            "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {SCREENING_STATUS_LABELS[item.effective_screening_status] ??
                            item.effective_screening_status.replace(/_/g, " ")}
                        </span>
                      </div>
                    </button>
                    </div>
                  );
                })
              )}
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t px-4 py-3">
                <span className="text-xs text-gray-500">
                  Page {page} of {totalPages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                    disabled={page <= 1 || refreshing}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                    disabled={page >= totalPages || refreshing}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2">
          {selected ? (
            <div className="space-y-4">
              <div className="rounded-lg border bg-white p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold text-gray-900">{applicantName(selected)}</h2>
                    <p className="truncate text-sm text-gray-500">
                      {selected.candidate_email || "No email on file"}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(
                          selected.status,
                        )}`}
                      >
                        {STATUS_LABELS[selected.status] || selected.status.replace(/_/g, " ")}
                      </span>
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                          SCREENING_STATUS_STYLES[screeningState] ?? "bg-gray-100 text-gray-800"
                        }`}
                      >
                        Screening: {SCREENING_STATUS_LABELS[screeningState] ?? screeningState}
                      </span>
                      {effectiveRecommendation && (
                        <span
                          className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                            RECOMMENDATION_STYLES[effectiveRecommendation]
                          }`}
                        >
                          {RECOMMENDATION_LABELS[effectiveRecommendation]}
                        </span>
                      )}
                      {effectiveStrength && (
                        <span
                          className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                            STRENGTH_STYLES[effectiveStrength]
                          }`}
                        >
                          {STRENGTH_LABELS[effectiveStrength]}
                        </span>
                      )}
                      {effectiveScore !== null && (
                        <span
                          className={`inline-flex items-center rounded-full bg-gray-100 px-2.5 py-1 text-xs font-bold ${scoreTextClass(
                            effectiveScore,
                          )}`}
                        >
                          Match {effectiveScore}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
                    <Link
                      to={`/recruiter/jobs/${id}/applicants/${selected.id}/screening`}
                      className="rounded-lg border border-gray-300 px-3 py-1.5 text-center text-sm font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Screening detail
                    </Link>
                    <Link
                      to={`/recruiter/jobs/${id}/candidates/${selected.candidate_id}/fit`}
                      className="rounded-lg border border-primary-600 px-3 py-1.5 text-center text-sm font-medium text-primary-600 hover:bg-primary-50"
                    >
                      View Job Fit
                    </Link>
                  </div>
                </div>

                {selected.cover_letter && (
                  <div className="mt-5 border-t pt-4">
                    <h3 className="text-sm font-semibold text-gray-900">Cover Letter</h3>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{selected.cover_letter}</p>
                  </div>
                )}
              </div>

              {/* The identifiers for this applicant, labelled and copyable.
                  Previously this page held both `candidate_id` and the
                  application `id` and displayed neither, so a recruiter who
                  needed either -- to schedule an interview, to answer a
                  question, or to paste into a support ticket -- had no way to
                  read one from the screen. Both are already in the loaded
                  applicant record, so nothing extra is requested. */}
              <ApplicationIdentityCard
                candidateName={applicantName(selected)}
                candidateEmail={selected.candidate_email}
                candidateId={selected.candidate_id}
                applicationId={selected.id}
                jobTitle={selected.job_title || data?.job?.title}
                jobId={selected.job_id || id}
                applicationStatus={selected.status}
                statusLabel={STATUS_LABELS[selected.status] || selected.status.replace(/_/g, " ")}
              />

              {/* Phase 8: the recruiter's explicit decision. Rejecting requires a
                  structured reason and previews the candidate-facing wording;
                  the internal note stays private. */}
            <ApplicationDecisionPanel
              key={selected.id}
              applicationId={selected.id}
              onDecisionMade={handleDecisionMade}
              onOptionsLoaded={setDecisionOptions}
            />

            {/* Phase 11: schedule and manage this applicant's interview. Mounted
                below the decision panel on purpose — the interview is evidence
                for that decision, not a substitute for it. */}
            <ApplicationInterviewPanel
              key={`interview-${selected.id}`}
              applicationId={selected.id}
              onStatusChanged={handleInterviewStatusChanged}
              onApplicationStatusChanged={handleInterviewApplicationStatusChanged}
            />

            {/* Phase 12: assign an existing assessment to this applicant and read
                the resulting evidence. Mounted below the decision and interview
                panels on the same principle — an assessment score is evidence for
                that decision, not a substitute for it. */}
            <ApplicationAssessmentPanel
              key={`assessment-${selected.id}`}
              applicationId={selected.id}
            />


              <div className="rounded-lg border bg-white p-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">Screening</h3>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {screeningResult
                        ? `Completed ${new Date(
                            selected.screening_completed_at ?? screeningResult.created_at,
                          ).toLocaleString()}`
                        : SCREENING_STATUS_LABELS[screeningState] ?? screeningState}
                    </p>
                  </div>
                  {canRunScreening && (
                    <Button
                      size="sm"
                      onClick={() => handleRunScreening(selected.id)}
                      isLoading={isRunningThis}
                      disabled={screeningAppId !== null}
                    >
                      Run screening
                    </Button>
                  )}
                </div>

                {activeScreeningError && (
                  <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-red-700">Screening error</p>
                    <p className="mt-1 break-words text-sm text-red-700">{activeScreeningError}</p>
                  </div>
                )}

                <div className="mt-4">
                  {screeningResult ? (
                    <MatchScoreCard screening={screeningResult} />
                  ) : isScreeningInFlight ? (
                    <div className="rounded-lg border-2 border-dashed border-gray-300 px-4 py-8 text-center">
                      <LoadingSpinner size="md" />
                      <p className="mt-3 text-sm text-gray-500">
                        Screening is {screeningState === "queued" ? "queued" : "running"}. Results appear here once it
                        finishes.
                      </p>
                    </div>
                  ) : (
                    <div className="rounded-lg border-2 border-dashed border-gray-300 px-4 py-8 text-center">
                      <p className="text-sm text-gray-500">
                        {isTerminalApplication
                          ? "This application reached a final status, so screening can no longer be started."
                          : screeningState === "skipped"
                            ? "Screening was skipped for this application."
                            : "No screening result for this applicant yet."}
                      </p>
                      {canRunScreening && (
                        <p className="mt-1 text-xs text-gray-400">
                          Run screening to generate a match score, skill gaps and strengths.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border bg-white p-6">
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Recruiter Notes</h3>
                <div className="mb-4 space-y-2">
                  {(selected.recruiter_notes || []).length === 0 && (
                    <p className="text-sm text-gray-400">No notes yet</p>
                  )}
                  {(selected.recruiter_notes || []).map((note) => (
                    <div key={note.id} className="rounded-lg bg-gray-50 p-3 text-sm">
                      <p className="text-gray-700">{note.note}</p>
                      <p className="mt-1 text-xs text-gray-400">{new Date(note.created_at).toLocaleString()}</p>
                    </div>
                  ))}
                </div>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <textarea
                    aria-label="Add a recruiter note"
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Add a note..."
                    rows={2}
                    className="block flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                  <Button
                    onClick={() => handleAddNote(selected.id)}
                    disabled={!noteText.trim()}
                    isLoading={savingNote}
                    className="self-end"
                  >
                    Add Note
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {selectionMissing && (
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
                  The applicant from this link is not in the current result set. Clear the filters or change the page to
                  view their details.
                </div>
              )}
              <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
                <p className="text-gray-500">Select an applicant to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
