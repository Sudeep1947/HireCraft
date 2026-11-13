"""Phase 11 application-driven interview contracts.

These are the schemas for scheduling and reviewing an interview *from an
application*, which is the direction the hiring workflow actually runs. The
legacy :class:`~app.domain.interview_schemas.InterviewScheduleRequest` takes
``job_id`` and ``candidate_id`` from the client, which makes it possible to
schedule an interview for a candidate who never applied; nothing here accepts
either field.

Three properties are load-bearing:

1. **No client-supplied identity.** Every request below carries only a time and
   the interview's own configuration. The job, the candidate, the recruiter and
   the organization are all derived from the ``application_id`` in the path by
   the server. A caller cannot point the workflow at a different candidate or a
   different tenant's job, because it never gets to say who.

2. **The server owns affordances.** ``can_schedule``/``can_reschedule``/
   ``can_cancel``/``can_complete`` and their ``*_reason`` strings are computed
   from the lifecycle transition maps, so the UI cannot offer an action the
   backend would reject. ``reason`` is a controlled vocabulary, never a raw
   exception string.

3. **The candidate view is an explicit allowlist.**
   :class:`CandidateApplicationInterviewView` carries scheduling and status
   facts only. It has no scorecard, no evaluation, no per-answer feedback, no
   recommendation, no recruiter identity, no recruiter notes, no fairness or
   protected-attribute data, and no other candidate's information. Interview
   intelligence is decision *evidence* for staff; showing a candidate their own
   automated score or recommendation would be an unvalidated hiring signal, so
   the fields simply do not exist on this model.

The ``application_id``/``interview_id`` pair is the authorization unit. The
interview id is always verified to belong to the application in the path, so a
recruiter cannot pass an interview from another application (or another tenant)
to reach its scorecard.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    ApplicationStatus,
    HiringRecommendation,
    InterviewStage,
    InterviewStatus,
    InterviewType,
    RejectionReason,
)

# ── Controlled reasons a scheduling action is unavailable ───────────────────
# A fixed vocabulary so the client can render a sensible message and no internal
# exception text ever reaches the browser.
REASON_TERMINAL = "application_is_final"
REASON_NOT_SHORTLISTED = "application_not_shortlisted"
REASON_ALREADY_SCHEDULED = "interview_already_scheduled"
REASON_INTERVIEW_FINAL = "interview_already_finished"
# Phase 15: HR-stage and advancement affordance reasons. Kept in the same
# controlled vocabulary as the scheduling reasons above so the UI renders one
# kind of string for every closed action.
REASON_NOT_ADVANCED = "candidate_not_advanced_to_hr"
REASON_ALREADY_ADVANCED = "candidate_already_advanced_to_hr"
REASON_HR_ALREADY_SCHEDULED = "hr_interview_already_scheduled"
REASON_RECRUITER_INTERVIEW_INCOMPLETE = "recruiter_interview_not_completed"

# Application statuses from which scheduling is permitted. Mirrors the funnel:
# an interview follows a shortlist. Derived from the lifecycle transitions so
# this cannot drift from the authoritative map.
SCHEDULABLE_FROM: frozenset[ApplicationStatus] = frozenset(
    {ApplicationStatus.SHORTLISTED}
)


# ── Requests ────────────────────────────────────────────────────────────────

# Every request below rejects unknown fields. Silently ignoring a
# ``candidate_id`` or ``job_id`` sent to a participant-free endpoint would be
# worse than a 422: the client would believe it had chosen the interview's
# participants when the server quietly derived different ones. Failing loudly
# means a caller that thinks it can address a specific candidate or job finds out
# it cannot, rather than scheduling against the application in the path.
_REQUEST_CONFIG = ConfigDict(extra="forbid")


class ApplicationInterviewScheduleRequest(BaseModel):
    """Schedule an interview for an application.

    Deliberately has no ``job_id`` or ``candidate_id``: the application in the
    path is the only input that identifies the participants. An optional
    ``interviewer_id`` can be supplied when scheduling an HR interview to assign
    a specific authorized HR manager.
    """

    model_config = _REQUEST_CONFIG

    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=180)
    categories: list[str] = Field(default=["technical", "behavioral"])
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|mixed)$")
    question_count: int = Field(default=10, ge=1, le=50)
    # Phase 15: which round this interview is. Defaults to the first-round
    # recruiter interview, so every existing caller keeps its behaviour. An
    # ``hr`` stage is only accepted for a candidate who has been advanced.
    stage: InterviewStage = InterviewStage.RECRUITER
    # Phase 15 HR interview assignment & focus notes
    interviewer_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    focus_areas: list[str] | None = None


class ApplicationInterviewRescheduleRequest(BaseModel):
    """Move an existing scheduled interview to a new time.

    Keeps the same interview record so its questions, answers and evaluations
    are preserved, which is why rescheduling is a mutation of the interview and
    not a fresh schedule. Only the time and duration may change; the
    participants are not negotiable.
    """

    model_config = _REQUEST_CONFIG

    scheduled_at: datetime
    duration_minutes: int | None = Field(default=None, ge=15, le=180)


class ApplicationInterviewCancelRequest(BaseModel):
    """Cancel a scheduled interview.

    ``reason`` is internal: it is recorded on the audit trail and is never shown
    to the candidate, who only learns that the interview was cancelled.
    """

    model_config = _REQUEST_CONFIG

    reason: str | None = Field(default=None, max_length=500)


class ApplicationInterviewCompleteRequest(BaseModel):
    """Mark an interview as completed and record the stage it reached.

    ``completed_at`` is optional; the server defaults to now. No field here can
    express a hiring outcome -- the recruiter's decision remains a separate,
    explicit act through the Phase 8 decision endpoints.
    """

    model_config = _REQUEST_CONFIG

    completed_at: datetime | None = None


# ── Recruiter-facing: interview summary ─────────────────────────────────────

class ApplicationInterviewSummary(BaseModel):
    """One interview linked to an application, for the recruiter evidence list.

    Includes the scorecard aggregate because this is staff-only evidence. The
    per-answer evaluations and the full question/answer graph are intentionally
    *not* inlined here; they are fetched on demand from the existing interview
    detail and scorecard endpoints, so listing interviews stays cheap.
    """

    id: uuid.UUID
    application_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    interview_type: InterviewType = InterviewType.RECRUITER_SCHEDULED

    @field_validator("interview_type", mode="before")
    @classmethod
    def _coerce_interview_type(cls, v: object) -> InterviewType:
        if isinstance(v, InterviewType):
            return v
        return InterviewType.from_value(str(v) if v is not None else None) or InterviewType.RECRUITER_SCHEDULED

    @field_validator("stage", mode="before")
    @classmethod
    def _coerce_stage(cls, v: object) -> InterviewStage:
        if isinstance(v, InterviewStage):
            return v
        if not v:
            return InterviewStage.RECRUITER
        val_str = str(v).lower()
        if "hr" in val_str:
            return InterviewStage.HR
        return InterviewStage.RECRUITER

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: object) -> InterviewStatus:
        if isinstance(v, InterviewStatus):
            return v
        if not v:
            return InterviewStatus.SCHEDULED
        parsed = InterviewStatus.from_value(str(v).lower())
        return parsed or InterviewStatus.SCHEDULED
    # Phase 15: which hiring round this is, so the evidence list can show a
    # recruiter round and an HR round as two distinct entries.
    stage: InterviewStage = InterviewStage.RECRUITER
    status: InterviewStatus
    scheduled_at: datetime | None = None
    rescheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_minutes: int | None = None
    total_questions: int = 0
    questions_answered: int = 0
    has_scorecard: bool = False
    overall_score: int | None = None
    recommendation: str | None = None
    recruiter_id: uuid.UUID | None = None
    recruiter_name: str | None = None
    room_id: str | None = None
    notes: str | None = None
    created_at: datetime


class ApplicationInterviewScheduleResult(BaseModel):
    """Outcome of scheduling, rescheduling, cancelling or completing."""

    application_id: uuid.UUID
    interview_id: uuid.UUID
    interview_status: InterviewStatus
    # The application's status after the action. Scheduling moves it to
    # ``interview_scheduled``; cancelling and rescheduling deliberately leave it
    # alone (see the service docstring).
    application_status: ApplicationStatus
    application_status_changed: bool = False
    message: str = ""


# ── Recruiter-facing: affordances ───────────────────────────────────────────

class ApplicationInterviewActionOption(BaseModel):
    """Per-interview action affordances.

    One entry per linked interview, so a recruiter sees exactly which of their
    interviews can still be moved, cancelled or completed. ``*_reason`` uses the
    controlled vocabulary above, never a raw exception string.
    """

    interview_id: uuid.UUID
    status: InterviewStatus
    can_reschedule: bool
    reschedule_unavailable_reason: str | None = None
    can_cancel: bool
    # Present whenever cancel is closed, so the UI can explain *why* rather than
    # rendering a dead button.
    cancel_unavailable_reason: str | None = None
    can_complete: bool
    complete_unavailable_reason: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: object) -> InterviewStatus:
        if isinstance(v, InterviewStatus):
            return v
        if not v:
            return InterviewStatus.SCHEDULED
        parsed = InterviewStatus.from_value(str(v).lower())
        return parsed or InterviewStatus.SCHEDULED


class ApplicationInterviewOptions(BaseModel):
    """Server-authoritative interview affordances for one application.

    The UI renders these instead of hardcoding a transition table, so the
    lifecycle rules stay the single source of truth.
    """

    application_id: uuid.UUID
    current_status: ApplicationStatus
    status_is_final: bool
    # True only when the application is in a schedulable state and has no
    # interview that is still scheduled or in progress. A retried request that
    # would create a duplicate is therefore blocked here, not silently allowed.
    can_schedule: bool
    schedule_unavailable_reason: str | None = None
    has_interviews: bool
    active_interview_id: uuid.UUID | None = None
    options: list[ApplicationInterviewActionOption] = Field(default_factory=list)
    # ── Phase 15: HR stage + advancement affordances ────────────────
    # True once the recruiter has advanced the candidate to the HR stage. HR
    # scheduling is only offered when this is set, so advancing is the single
    # gate between the recruiter round and the HR round.
    hr_eligible: bool = False
    # True once a recruiter-stage interview on this application reached
    # ``completed``. Advancing waits for this, so a candidate cannot be sent to
    # HR before the first round actually happened.
    recruiter_stage_complete: bool = False
    can_advance: bool = False
    advance_unavailable_reason: str | None = None
    can_schedule_hr: bool = False
    schedule_hr_unavailable_reason: str | None = None
    can_reject: bool = False
    reject_unavailable_reason: str | None = None


# ── Recruiter-facing: evidence bundle ───────────────────────────────────────

class ApplicationInterviewEvidence(BaseModel):
    """Everything staff may read about an application's interview evidence.

    Reuses the existing scorecard/evaluation records rather than duplicating
    them: this is an index over interviews, not a second intelligence system.
    """

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    candidate_id: uuid.UUID
    candidate_name: str
    application_status: ApplicationStatus
    interview_count: int = 0
    completed_count: int = 0
    # Present once at least one linked interview is complete. An average over
    # completed interviews only, so a scheduled-but-unanswered interview cannot
    # drag the figure down.
    average_overall_score: float | None = None
    interviews: list[ApplicationInterviewSummary] = Field(default_factory=list)
    # Phase 15: whether the candidate has been advanced to the HR stage, so the
    # evidence panel can show the round the candidate is in without a second call.
    hr_eligible: bool = False
    advanced_to_hr_at: datetime | None = None


# ── Recruiter-facing: interview feedback ────────────────────────────────────

class ApplicationInterviewFeedbackRequest(BaseModel):
    """Manual technical/HR feedback an interviewer records against an interview.

    Distinct from the automated per-answer evaluation: this is the interviewer's
    own judgement, entered by hand. It is stored on the existing
    ``InterviewScorecard`` record for the interview, so it reuses the same staff
    artifact rather than introducing a second feedback store.
    """

    model_config = ConfigDict(extra="ignore")

    technical_skills: int = Field(ge=0, le=100)
    communication: int = Field(ge=0, le=100)
    problem_solving: int = Field(ge=0, le=100)
    teamwork: int | None = Field(default=None, ge=0, le=100)
    leadership: int | None = Field(default=None, ge=0, le=100)
    culture_fit: int | None = Field(default=None, ge=0, le=100)
    # Optional: when omitted the server averages the ratings above, so the
    # interviewer does not have to repeat themselves.
    overall_score: int | None = Field(default=None, ge=0, le=100)
    hiring_confidence: int = Field(default=50, ge=0, le=100)
    recommendation: HiringRecommendation = HiringRecommendation.CONSIDER
    recruiter_notes: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=5000)
    strengths: str | None = Field(default=None, max_length=2000)
    concerns: str | None = Field(default=None, max_length=2000)

    @field_validator("recommendation", mode="before")
    @classmethod
    def _coerce_rec(cls, v: object) -> HiringRecommendation:
        if isinstance(v, HiringRecommendation):
            return v
        return HiringRecommendation.from_value(str(v) if v is not None else None) or HiringRecommendation.CONSIDER

    @model_validator(mode="before")
    @classmethod
    def _map_notes(cls, data: object) -> object:
        if isinstance(data, dict):
            if "notes" in data and not data.get("recruiter_notes"):
                data["recruiter_notes"] = data["notes"]
        return data


class ApplicationInterviewFeedback(BaseModel):
    """Staff-only projection of a recorded interview feedback/scorecard."""

    interview_id: uuid.UUID
    application_id: uuid.UUID
    technical_skills: int
    communication: int
    problem_solving: int
    teamwork: int | None = None
    leadership: int | None = None
    culture_fit: int | None = None
    overall_score: int
    hiring_confidence: int
    recommendation: HiringRecommendation
    recruiter_notes: str | None = None
    strengths: str | None = None
    concerns: str | None = None
    created_at: datetime
    updated_at: datetime


class HRInterviewerOption(BaseModel):
    """An authorized HR interviewer in the organization available for assignment."""

    id: uuid.UUID
    full_name: str
    email: str
    role: str


# ── Recruiter-facing: stage actions (advance / reject) ──────────────────────

class ApplicationInterviewAdvanceRequest(BaseModel):
    """Advance a candidate to the HR interview stage.

    Carries only an optional internal note. It deliberately cannot express an HR
    interview time: advancing makes the candidate *eligible* to be scheduled by
    HR, and the recruiter (or HR) still chooses the time explicitly afterwards.
    """

    model_config = _REQUEST_CONFIG

    note: str | None = Field(default=None, max_length=2000)


class ApplicationInterviewRejectRequest(BaseModel):
    """Reject a candidate from the interview stage.

    ``rejection_reason`` uses the same controlled Phase 8 vocabulary the decision
    endpoints use, so the candidate-facing wording is derived from a code and
    never from recruiter prose. ``internal_note`` is recorded for staff only.
    """

    model_config = _REQUEST_CONFIG

    rejection_reason: RejectionReason
    internal_note: str | None = Field(default=None, max_length=2000)


class ApplicationInterviewStageActionResult(BaseModel):
    """Outcome of advancing or rejecting from the interview stage."""

    application_id: uuid.UUID
    application_status: ApplicationStatus
    application_status_changed: bool = False
    hr_eligible: bool = False
    candidate_message: str | None = None
    message: str = ""


# ── Candidate view (explicit allowlist) ─────────────────────────────────────

class CandidateApplicationInterviewView(BaseModel):
    """What a candidate may see about their application's interview.

    Deliberately excludes: scorecard scores, recommendation, hiring confidence,
    per-answer evaluations and feedback, recruiter identity, recruiter notes,
    AI summaries, fairness context, protected attributes, and any other
    candidate's data. An automated interview score is decision support for the
    hiring team and is not validated as a signal the candidate should be shown,
    so it is not represented here at all.
    """

    application_id: uuid.UUID
    # Only the interview facts a candidate needs to attend and to follow along.
    interview_id: uuid.UUID | None = None
    status: InterviewStatus | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    completed_at: datetime | None = None
    # The next interview still to attend, when several are linked.
    next_upcoming_at: datetime | None = None
    # True once at least one linked interview reached ``completed``, so the UI
    # can show an "interview completed" step even after later rounds.
    has_completed: bool = False
    interview_count: int = 0
    # Approved candidate wording for the current stage. Never built from
    # recruiter prose.
    message: str | None = None
