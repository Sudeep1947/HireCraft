"""Response contracts for the HR oversight surface (Revised Phase 14).

Design notes:
- These are *read-only oversight* contracts. Nothing here can transition an
  application, record a decision, schedule an interview or assign an
  assessment. The write surface stays with the recruiter; HR is a
  read-only, organization-scoped oversight layer over the same
  ``JobApplication`` rows.
- ``applications_by_status`` is a plain ``dict`` keyed by the canonical
  ``ApplicationStatus`` values rather than a fixed field per state, so a new
  lifecycle status does not require a schema change here. The named counters in
  ``HROverviewCounts`` are the stable subset the HR overview contract
  guarantees.
- ``is_platform_scope`` is explicit in the payload. A platform admin gets a
  cross-tenant view; every other caller is scoped to their organizations. The
  frontend uses this to label the screen honestly rather than implying an
  org-scoped number is platform-wide or vice versa.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HROverviewCounts(BaseModel):
    """Stable counters for the HR overview.

    ``applications`` counts every application on jobs the caller may read.
    The per-status counters are intentionally a named subset of the funnel that
    the brief calls out (open jobs, total applications, statuses, interviews,
    assessments, selected, rejected, hired); the full funnel is carried by
    ``applications_by_status`` so nothing is lost.

    Two counters are deliberately narrow so a number is never presented as
    something it is not: ``assessments_assigned`` counts only attempts still in
    ``assigned`` state (``assessment_attempts`` is the all-status total), and
    ``offered`` counts the canonical ``offered`` status on its own rather than a
    derived "closed" total. The full breakdown of both is always available in
    ``assessments_by_status`` and ``applications_by_status``.
    """

    open_positions: int = 0
    total_applications: int = 0
    distinct_candidates: int = 0
    distinct_recruiters: int = 0
    shortlisted: int = 0
    interview_scheduled: int = 0
    interview_scheduled_total: int = 0
    assessments_assigned: int = 0
    assessment_attempts: int = 0
    selected: int = 0
    offered: int = 0
    rejected: int = 0
    hired: int = 0
    withdrawn: int = 0


class HROverviewResponse(BaseModel):
    organization_ids: list[uuid.UUID] = Field(default_factory=list)
    is_platform_scope: bool = False
    counts: HROverviewCounts = Field(default_factory=HROverviewCounts)
    applications_by_status: dict[str, int] = Field(default_factory=dict)
    interviews_by_status: dict[str, int] = Field(default_factory=dict)
    assessments_by_status: dict[str, int] = Field(default_factory=dict)


class HRJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    description: str | None = None
    department: str | None = None
    location: str | None = None
    status: str
    organization_id: uuid.UUID | None = None
    recruiter_id: uuid.UUID
    recruiter_name: str | None = None
    created_at: datetime | None = None
    application_count: int = 0
    applications_by_status: dict[str, int] = Field(default_factory=dict)
    hired_count: int = 0
    open_application_count: int = 0


class HRJobListResponse(BaseModel):
    is_platform_scope: bool = False
    total: int = 0
    jobs: list[HRJobSummary] = Field(default_factory=list)


class HRCandidateView(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None = None
    is_active: bool = True
    account_status: str | None = None
    has_resume: bool = False
    avatar_url: str | None = None
    phone: str | None = None
    location: str | None = None
    resume_url: str | None = None
    resume_filename: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    bio: str | None = None
    current_role: str | None = None


class HRApplicationSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str | None = None
    candidate_id: uuid.UUID
    candidate_name: str
    status: str
    is_terminal: bool = False
    screening_status: str | None = None
    applied_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: uuid.UUID | None = None
    recruiter_id: uuid.UUID
    recruiter_name: str | None = None
    has_interview: bool = False
    has_assessment: bool = False


class HRApplicationListResponse(BaseModel):
    job_id: uuid.UUID
    # Echoes the applied funnel-stage filter so the UI can label the result
    # honestly instead of assuming an unfiltered list.
    status_filter: str | None = None
    total: int = 0
    applications: list[HRApplicationSummary] = Field(default_factory=list)


class HRDecisionView(BaseModel):
    status: str
    is_terminal: bool = False
    decision_reason: str | None = None
    decision_reason_code: str | None = None
    decision_comment: str | None = None
    decided_at: datetime | None = None
    decided_by: uuid.UUID | None = None
    decided_by_name: str | None = None


class HRScreeningSummary(BaseModel):
    status: str
    attempts: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class HRTimelineEvent(BaseModel):
    """One composed timeline entry.

    Built only from rows the platform already wrote -- ``application_status_history``
    for status moves, and the application-linked interview/assessment records for
    the evidence events. No synthetic or inferred entries are ever added, so an
    empty gap in the timeline means "nothing was recorded", not "we made it up".
    """

    id: uuid.UUID
    source: str
    event: str
    at: datetime | None = None
    from_status: str | None = None
    to_status: str | None = None
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    detail: str | None = None


class HRApplicationDetail(BaseModel):
    """The single HR drill-down payload.

    One request returns the whole oversight view, because the brief forbids
    nested-request waterfalls for a read path. The sub-payloads are the
    *already-projected* outputs of the existing services where one exists
    (explainability, fairness, interview, assessment); they are re-used as-is
    rather than recomputed by new HR-specific logic.
    """

    id: uuid.UUID
    status: str
    is_terminal: bool = False
    job: HRJobSummary
    candidate: HRCandidateView
    decision: HRDecisionView
    screening: HRScreeningSummary
    applied_at: datetime | None = None
    cover_letter_available: bool = False
    explainability: dict[str, Any] | None = None
    fairness: dict[str, Any] | None = None
    interview: dict[str, Any] | None = None
    assessment: dict[str, Any] | None = None
    timeline: list[HRTimelineEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recruiter (employer) monitoring
# ---------------------------------------------------------------------------
# The counterpart of the job list: the same authorized job ids, rolled up by the
# recruiter who owns them. It is a grouping of *existing* rows, not a second
# source of truth, so a recruiter's numbers always equal the sum of the jobs
# shown on their row.


class HRRecruiterSummary(BaseModel):
    """One recruiter's real funnel, aggregated over the jobs HR may read."""

    id: uuid.UUID
    full_name: str
    email: str | None = None
    is_active: bool = True
    open_job_count: int = 0
    total_job_count: int = 0
    application_count: int = 0
    open_application_count: int = 0
    applications_by_status: dict[str, int] = Field(default_factory=dict)
    hired_count: int = 0
    # 0.0 when the recruiter has no applications: a ratio is undefined rather
    # than zero, so the UI can say "no applications yet" instead of showing a
    # recruiter with 0% performance.
    advancement_rate: float | None = None
    job_ids: list[uuid.UUID] = Field(default_factory=list)


class HRRecruiterListResponse(BaseModel):
    is_platform_scope: bool = False
    total: int = 0
    recruiters: list[HRRecruiterSummary] = Field(default_factory=list)


class HRRecruiterDetail(BaseModel):
    """A recruiter plus the jobs behind the aggregate, for one drill-down call."""

    recruiter: HRRecruiterSummary
    jobs: list[HRJobSummary] = Field(default_factory=list)


class HRStageJobCount(BaseModel):
    """How many applications one job holds in a single funnel stage."""

    job_id: uuid.UUID
    job_title: str
    recruiter_id: uuid.UUID
    recruiter_name: str | None = None
    count: int = 0


class HRStageDrilldownResponse(BaseModel):
    """The records behind one funnel bar, grouped by job.

    The overview funnel is organization-wide, so drilling into a single stage
    cannot list every application flat: a popular stage can hold thousands of
    rows across many jobs. This groups them by job instead, which answers "where
    is this stage?" in one aggregate query and keeps every job row a link to the
    stage-filtered application list the recruiter's own drill-down uses.
    """

    status: str
    total: int = 0
    jobs: list[HRStageJobCount] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Attention center
# ---------------------------------------------------------------------------
# Deterministic, explainable "needs a human look" items. Each item names the
# rule that produced it and carries enough ids for the UI to link straight to the
# underlying record. `reason` is a factual statement of the measured condition
# (e.g. "no status change for 12 days"), never a recommendation about a
# candidate.


class HRAttentionItem(BaseModel):
    rule: str
    severity: str
    reason: str
    subject_type: str
    subject_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    recruiter_id: uuid.UUID | None = None
    job_title: str | None = None
    recruiter_name: str | None = None
    status: str | None = None
    measured_value: float | None = None
    threshold_value: float | None = None


class HRAttentionResponse(BaseModel):
    is_platform_scope: bool = False
    # The thresholds actually applied, echoed so the screen explains itself
    # instead of showing numbers whose basis is invisible.
    thresholds: dict[str, float] = Field(default_factory=dict)
    # How many items qualified in total, before the cap.
    total_flagged: int = 0
    # How many are actually returned (<= hr_attention_max_items).
    items: list[HRAttentionItem] = Field(default_factory=list)
    # True when qualifying items were dropped by the cap, so the UI can say so
    # rather than implying this is everything.
    truncated: bool = False


# ---------------------------------------------------------------------------
# Hiring quality
# ---------------------------------------------------------------------------
# An organization-scoped roll-up that reports *coverage* of the existing
# quality signals. It deliberately reports how much evidence exists rather than
# inventing a composite "hiring quality score": the underlying screening,
# explainability and fairness modules own those judgments.


class HRQualityCoverage(BaseModel):
    total_applications: int = 0
    screening_by_status: dict[str, int] = Field(default_factory=dict)
    # Share of applications that reached each milestone. None when the
    # denominator is zero, so "no applications" never reads as 0% conversion.
    screening_rate: float | None = None
    interview_rate: float | None = None
    decision_rate: float | None = None
    hire_rate: float | None = None


class HRFairnessAlert(BaseModel):
    """A fairness condition that crossed the configured review threshold.

    ``job_id`` is optional because the platform's fairness engine reports both
    organization-wide metrics and per-job ones; the org-level metric is not
    attributable to a single job and must not be presented as if it were.
    """

    job_id: uuid.UUID | None = None
    job_title: str | None = None
    metric: str
    observed_value: float
    threshold_value: float
    detail: str | None = None


class HRHiringQualityResponse(BaseModel):
    is_platform_scope: bool = False
    organization_ids: list[uuid.UUID] = Field(default_factory=list)
    coverage: HRQualityCoverage = Field(default_factory=HRQualityCoverage)
    fairness_alerts: list[HRFairnessAlert] = Field(default_factory=list)
    fairness_gap_threshold: float = 0.8

    # Deliberately no `unexplained_decisions` / evidence-gap counter here.
    # Explainability is derived on demand from `ScreeningResult` scores, and
    # there is no cheap, authoritative definition of an "unexplained decision"
    # to count here. Shipping a field that was always 0 would report "no
    # evidence gaps" for a check that never ran, which is worse than not
    # reporting the number at all. The per-application explainability block
    # remains available on the application drill-down, where it is real.


class HRInterviewItem(BaseModel):
    id: uuid.UUID | None = None
    application_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    candidate_email: str | None = None
    job_id: uuid.UUID
    job_title: str
    organization_id: uuid.UUID | None = None
    organization_name: str | None = None
    stage: str = "hr"
    status: str = "pending_schedule"
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    room_id: str | None = None
    interviewer_id: uuid.UUID | None = None
    interviewer_name: str | None = None
    recruiter_name: str | None = None
    recruiter_score: int | None = None
    recruiter_recommendation: str | None = None
    recruiter_notes: str | None = None
    hr_score: int | None = None
    hr_recommendation: str | None = None
    hr_notes: str | None = None
    application_status: str
    advanced_to_hr_at: datetime | None = None
    candidate_avatar_url: str | None = None
    is_terminal: bool = False


class HRInterviewListResponse(BaseModel):
    items: list[HRInterviewItem] = Field(default_factory=list)
    total: int = 0
