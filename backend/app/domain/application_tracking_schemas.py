"""Phase 9 candidate application tracking contracts.

This module is the candidate-facing *tracking* surface: where an application is,
how it got there, and what the candidate is told at each step. It is a read
projection only. Nothing here creates, advances, or decides an application.

Three properties are load-bearing:

1. **No new lifecycle.** Every status rendered by this contract is a member of
   the existing ``ApplicationStatus`` enum. ``PROGRESS_STAGES`` is an ordered
   *display* of the hiring funnel the lifecycle service already enforces
   (``STAFF_TRANSITIONS``); it introduces no state, grants no permission, and is
   not consulted when a transition is validated. ``REJECTED`` and ``WITHDRAWN``
   are terminal outcomes, not steps, so they are reported as the current stage
   rather than inserted into the progress path.

2. **No invented history.** ``CandidateApplicationStage.reached`` is true only
   when a row for that status exists in ``application_status_history``. A stage
   the application has not actually been through is reported as not reached
   instead of being presented as a pending promise, and a status that never
   appears in the record is never listed at all.

3. **Candidate-safe allowlist.** The response carries no internal note, no
   recruiter identity, no free-text transition reason, no history metadata, no
   screening score, no AI recommendation, no ranking position, no fairness
   context, no other candidate's data and no audit trail. Candidate wording comes
   from the single reviewed projection in
   :mod:`app.domain.application_decision_schemas`, so the tracking view and the
   decision view can never disagree about what the candidate was told.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.application_decision_schemas import (
    CandidateApplicationDecisionResponse,
)
from app.domain.application_interview_schemas import (
    CandidateApplicationInterviewView,
)
from app.domain.enums import ApplicationStatus

# The hiring funnel as the lifecycle service already defines it, used purely to
# render progress. Sourced from the same ordered statuses the
# ApplicationStatusHistory rows will contain; it is a presentation list, not a
# transition table.
PROGRESS_STAGES: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.APPLIED,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.INTERVIEW_SCHEDULED,
    # Phase 11: shown as a distinct step so a candidate can see the interview
    # actually happened, separate from being scheduled for one.
    ApplicationStatus.INTERVIEWED,
    # Phase 13: shown as its own step between the interview and the offer, so a
    # selected candidate can see they were chosen before any offer is extended.
    ApplicationStatus.SELECTED,
    ApplicationStatus.OFFERED,
    ApplicationStatus.HIRED,
)


class CandidateApplicationStage(BaseModel):
    """One step of the candidate's progress through the funnel.

    ``reached`` reflects the immutable history, not a projection of what might
    happen next.
    """

    status: ApplicationStatus
    status_label: str
    reached: bool
    is_current: bool


class CandidateApplicationTimelineEvent(BaseModel):
    """One real status change, projected for a candidate.

    ``occurred_at`` is the recorded ``changed_at`` of the history row. The
    recorder's identity, the free-text reason, the internal comment and the row
    metadata are deliberately absent: a candidate sees that their status changed
    and the approved wording for it, nothing about how staff recorded it.
    """

    status: ApplicationStatus
    status_label: str
    from_status: ApplicationStatus | None = None
    occurred_at: datetime
    is_current: bool = False
    message: str | None = None


class CandidateApplicationTrackResponse(BaseModel):
    """Everything a candidate may see about tracking one application.

    Deliberately excludes: ``decision_comment`` (private recruiter note),
    ``decided_by`` and any staff identity, ``decision_reason`` free text,
    history comments and metadata, screening error text, screening scores, AI
    recommendations, ranking position, fairness context, protected attributes,
    and audit data.
    """

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company: str
    location: str = ""
    employment_type: str = ""

    status: ApplicationStatus
    status_label: str
    is_decision_final: bool
    # Server-derived from CANDIDATE_TRANSITIONS, so the UI never re-implements
    # the rule for when a candidate may still withdraw.
    can_withdraw: bool

    applied_at: datetime
    last_status_change_at: datetime | None = None
    decided_at: datetime | None = None
    status_changed: bool = Field(
        default=False,
        description=(
            "False when the latest history row is a deliberate no-transition "
            "record (for example 'keep under review'), so the UI can say the "
            "application is still under review rather than 'updated'."
        ),
    )

    screening_status: str = "not_started"
    screening_completed_at: datetime | None = None
    # A boolean affordance instead of the screening error text: the candidate is
    # told a match explanation exists, and reads the curated explanation on its
    # own page rather than an internal failure string.
    has_match_explanation: bool = False

    decision: CandidateApplicationDecisionResponse | None = None
    # Phase 11: the interview attached to this application, as an explicit
    # allowlist. Carrying it on the tracking response means the candidate sees
    # their interview schedule and stage in the same request that renders their
    # timeline, so the two can never disagree. It contains no scorecard, no
    # evaluation and no recommendation.
    interview: CandidateApplicationInterviewView | None = None
    stages: list[CandidateApplicationStage] = Field(default_factory=list)
    timeline: list[CandidateApplicationTimelineEvent] = Field(default_factory=list)
