"""Schemas for running an assessment *from an application*.

The direction the hiring workflow actually runs: a recruiter reaches an
application, assigns an assessment to it, and the candidate takes it through the
existing assessment experience. The pre-existing
:class:`~app.domain.assessment_schemas.AssessmentCreateRequest` takes ``job_id``
from the client, which makes it possible to point an assessment at a job the
caller does not own; nothing here accepts ``job_id``, ``candidate_id`` or
``recruiter_id``. The application in the path is the only identity input, and the
server derives the candidate, job and organization from it.

Three properties are load-bearing:

1. **No client-supplied identity.** Only ``assessment_id`` and ``message``-free
   intent. Participants come from the authorized application.
2. **Availability and permissions come from the server.** ``ApplicationAssessmentOptions``
   is the single source of truth for whether an assignment is allowed and why
   not, so a control the UI offers is one the API will accept and one it hides is
   one it will refuse. The catalog is pre-filtered to assessments the caller may
   assign, so the browser never has to reason about tenancy.
3. **A result is evidence, not a verdict.** Nothing in this module moves an
   application status or creates a decision. ``passed`` reports the assessment's
   own configured threshold and says nothing about hiring; the recruiter's
   decision remains the only thing that advances or ends an application.

The ``application_id``/``attempt_id`` pair is the authorization unit. An attempt
id is always verified to belong to the application in the path, so a recruiter
cannot pass an attempt from another application (or another tenant) to reach a
result.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.assessment_schemas import AssessmentSectionConfig
from app.domain.enums import ApplicationStatus, AssessmentMode, AttemptStatus

# A fixed vocabulary so the client can render a sensible message and no internal
# exception text ever reaches the browser.
REASON_APPLICATION_FINAL = "application_is_final"
REASON_APPLICATION_NOT_ELIGIBLE = "application_not_assessable"
REASON_ASSIGNMENT_EXISTS = "assessment_already_assigned"
REASON_ATTEMPT_FINISHED = "assessment_already_finished"
REASON_ASSESSMENT_UNAVAILABLE = "assessment_unavailable"
# The candidate has already used every attempt this assessment allows. Assigning
# it would create an attempt ``start_attempt`` refuses to start, so the request
# is refused at assignment time instead of leaving the candidate with a task they
# cannot do.
REASON_NO_ATTEMPTS_REMAINING = "no_attempts_remaining"
# The attempt has already finished, so its timing is part of the evidence it
# produced and cannot be moved. Rescheduling a finished attempt would mean
# rewriting history, so the panel offers a *new* attempt instead.
REASON_ATTEMPT_NOT_RESCHEDULABLE = "assessment_not_reschedulable"

# Application statuses from which an assessment may be assigned.
#
# An assessment is a step in evaluating a candidate the team already wants to
# keep, so it follows a shortlist and may also be attached before or after an
# interview. Terminal applications are excluded outright.
#
# Note what is *not* here: APPLIED and UNDER_REVIEW. Assigning a graded
# assessment to an unvetted applicant would let one assessment short-circuit the
# screening and review stages, which is the opposite of an evidence-driven
# funnel. This mirrors the interview phase's own SCHEDULABLE_FROM rule.
ASSIGNABLE_FROM: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.INTERVIEWED,
    }
)

# Statuses from which the application can still receive an assessment at all.
# Anything else is refused with a specific reason rather than a generic one.
_ELIGIBLE_FOR_ASSIGNMENT: frozenset[ApplicationStatus] = ASSIGNABLE_FROM


class ApplicationAssessmentAssignRequest(BaseModel):
    """Assign an existing assessment to an application.

    ``extra="forbid"`` so a client cannot smuggle a job, candidate or recruiter
    id into a request whose participants are derived server-side.

    ``scheduled_for`` is the only addition to the original contract, and it is
    still not an identity field: it says *when*, never *who*. Omitting it means
    "schedule it now", which is what every caller sent before the column existed
    and remains the default behaviour, so an existing client is unaffected.
    """

    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID
    #: The date and time the recruiter is scheduling this assessment for. None
    #: means the recruiter did not choose one and the candidate should simply be
    #: told it is waiting; it is not defaulted to "now" here, because a stored
    #: ``now`` would be indistinguishable from a deliberate choice.
    scheduled_for: datetime | None = None


class ApplicationAssessmentRescheduleRequest(BaseModel):
    """Move an existing assignment to a new date and time.

    ``extra="forbid"`` for the same reason as the assign request. Unlike
    ``scheduled_for`` on that request, this one is required: "reschedule" with no
    new time has no meaning, and defaulting it would silently rewrite the
    assignment to the current instant.
    """

    model_config = ConfigDict(extra="forbid")

    scheduled_for: datetime


class ApplicationAssessmentCreateRequest(BaseModel):
    """Author an assessment *for one application* and assign it, in one request.

    The candidate-specific counterpart of
    :class:`~app.domain.assessment_schemas.AssessmentCreateRequest`. It exists so a
    recruiter can go ``select job -> select candidate -> create -> assign`` without
    the creation and the assignment becoming two disconnected round trips through
    two screens.

    Every field here is authored *content* and nothing else is. In particular there
    is **no** ``job_id``, no ``candidate_id``, no ``application_id`` and no
    ``recruiter_id``, and ``extra="forbid"`` means sending one is a 422 rather than
    a silently ignored field. This is the whole point of the class: the pre-existing
    create request takes a client-supplied ``job_id``, so a caller could point an
    assessment at a job they do not own. Here the server derives the job from the
    authorized application, which means the new assessment is scoped to exactly the
    role the candidate applied for and is scoped to no other.

    The fields are otherwise identical to ``AssessmentCreateRequest`` so the
    existing builder UI and the existing ``AssessmentService.create_assessment``
    are reused unchanged. See :meth:`to_create_request`.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = None
    mode: str = "custom"
    duration_minutes: int = Field(45, ge=5, le=480)
    sections: list[AssessmentSectionConfig] = Field(..., min_length=1)
    passing_score: int = Field(60, ge=0, le=100)
    negative_marking: float = Field(0.0, ge=0.0, le=2.0)
    allowed_attempts: int = Field(1, ge=1, le=10)
    adaptive: bool = False
    shuffle_questions: bool = True
    shuffle_options: bool = False
    #: When the candidate is expected to take it. Same meaning and same "absent
    #: means absent" rule as on the assign request -- not an identity field, and
    #: never defaulted to ``now``.
    scheduled_for: datetime | None = None

    def to_create_request(self, job_id: uuid.UUID) -> "AssessmentCreateRequest":
        """Project onto the existing create schema with a server-derived ``job_id``.

        The one place a job id enters this request, and the caller supplies it from
        the authorized application rather than from the client. Every other field
        passes through untouched, so this stays a thin front door onto
        ``AssessmentService.create_assessment`` rather than a second builder.
        """
        from app.domain.assessment_schemas import AssessmentCreateRequest

        return AssessmentCreateRequest(
            title=self.title,
            description=self.description,
            job_id=job_id,
            mode=self.mode,
            duration_minutes=self.duration_minutes,
            sections=self.sections,
            passing_score=self.passing_score,
            negative_marking=self.negative_marking,
            allowed_attempts=self.allowed_attempts,
            adaptive=self.adaptive,
            shuffle_questions=self.shuffle_questions,
            shuffle_options=self.shuffle_options,
        )


class AssignableAssessment(BaseModel):
    """One entry of the catalog a recruiter may assign to this application.

    Every field is read from the existing assessment rows; nothing is invented to
    fill the UI. ``question_count`` is the real count of generated questions and
    ``skills`` the distinct skills those questions exercise, so a recruiter sees
    what the assessment actually contains rather than a label.
    """

    assessment_id: uuid.UUID
    title: str
    description: str | None = None
    mode: AssessmentMode
    status: str
    duration_minutes: int
    question_count: int
    passing_score: int
    allowed_attempts: int
    adaptive: bool
    skills: list[str] = Field(default_factory=list)
    #: True when this assessment is already attached to this application, so the
    #: UI can show it as current rather than offering a duplicate assignment.
    already_assigned: bool = False


class ApplicationAssessmentOptions(BaseModel):
    """Server-authoritative assignment affordances for one application.

    Read by the UI instead of re-implementing the rules, so an action the
    backend would reject is never offered in the first place.
    """

    application_id: uuid.UUID
    current_status: ApplicationStatus
    status_is_final: bool
    can_assign: bool
    assign_unavailable_reason: str | None = None
    has_assessments: bool
    attempt_count: int
    #: Assessments the caller may assign to this application, already filtered by
    #: organization access. Empty when none are reachable, which is a real answer
    #: and not a reason to fall back to an unscoped list.
    available: list[AssignableAssessment] = Field(default_factory=list)


class ApplicationAssessmentAttemptAction(BaseModel):
    """What may be done to one assigned attempt."""

    attempt_id: uuid.UUID
    status: AttemptStatus
    #: A finished attempt is immutable: its answers and result are evidence, so
    #: reopening one would rewrite history. Reassignment is a new attempt.
    can_reassign: bool
    reassign_unavailable_reason: str | None = None
    #: The date and time this attempt is currently scheduled for, so the panel can
    #: prefill a reschedule form with the real current value instead of an empty
    #: box that invites the recruiter to retype it.
    scheduled_for: datetime | None = None
    #: Whether the date and time may be changed. True for a live attempt, which is
    #: the only kind that has a schedule to move: a finished attempt's timing is
    #: part of the evidence it produced, and ``expires_at`` has usually already
    #: been consumed against the clock that started when the candidate began.
    can_reschedule: bool = False
    reschedule_unavailable_reason: str | None = None


class ApplicationAssessmentOptionsWithAttempts(ApplicationAssessmentOptions):
    """Options plus a per-attempt action list, for the assigned case."""

    actions: list[ApplicationAssessmentAttemptAction] = Field(default_factory=list)


class ApplicationAssessmentSummary(BaseModel):
    """One attempt, as evidence on the application.

    ``overall_score``, ``passed`` and ``passed_threshold`` describe the
    assessment's own configured threshold. They are not a hiring signal and must
    not be presented as one.
    """

    attempt_id: uuid.UUID
    assessment_id: uuid.UUID
    assessment_title: str
    mode: AssessmentMode
    status: AttemptStatus
    attempt_number: int
    #: The date and time this assessment is scheduled for. Falls back to the
    #: assignment time for an attempt with no explicit schedule, which is every
    #: attempt created before the column existed and every one a recruiter
    #: assigned without naming a time.
    scheduled_for_hint: datetime | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    questions_total: int = 0
    questions_answered: int = 0
    #: None until the attempt is graded. Never defaulted to 0.0: an ungraded
    #: attempt and a scored zero are very different facts.
    overall_score: float | None = None
    passed_threshold: int | None = None
    #: None when there is no result yet, or when the assessment has no threshold
    #: to compare against.
    passed: bool | None = None
    section_scores: list[dict] = Field(default_factory=list)
    strong_skills: list[str] = Field(default_factory=list)
    weak_skills: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    accuracy: float | None = None
    time_management: float | None = None
    #: Deterministic summary string the platform's own scoring module derives
    #: from the authoritative score. It cannot disagree with the score, because
    #: it is formatted from it.
    summary_text: str | None = None
    #: Count only. The individual events can contain detail a recruiter should
    #: read deliberately, so the count is what the application view carries.
    integrity_flag_count: int = 0


class ApplicationAssessmentEvidence(BaseModel):
    """All assessment evidence for one application, staff-only."""

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    candidate_id: uuid.UUID
    candidate_name: str
    application_status: ApplicationStatus
    attempt_count: int
    completed_count: int
    #: Averaged over completed attempts only, so an attempt nobody has finished
    #: cannot drag the figure down. None until one is completed.
    average_overall_score: float | None = None
    attempts: list[ApplicationAssessmentSummary] = Field(default_factory=list)


class ApplicationAssessmentAssignResult(BaseModel):
    """Outcome of an assignment.

    ``already_assigned`` makes the endpoint idempotent in the sense that matters:
    a double-click or a retried request re-reads the existing assignment and
    reports it instead of creating a second live attempt for one application.

    ``rescheduled`` is the case where the request named a *different* time for an
    assignment that already existed live. That updates the existing row rather
    than creating a second one, so the candidate keeps one attempt with one
    schedule instead of two attempts for the same assessment. ``scheduled_for``
    and ``assessment_link`` are echoed so the caller can render exactly what was
    stored without a second read.
    """

    application_id: uuid.UUID
    attempt_id: uuid.UUID
    assessment_id: uuid.UUID
    assessment_title: str
    attempt_status: AttemptStatus
    already_assigned: bool
    #: True when this request moved an existing assignment to a new time instead of
    #: creating one.
    rescheduled: bool = False
    #: The schedule now stored against the assignment, which on a reschedule is the
    #: new time and on a fresh assignment is whatever was requested.
    scheduled_for: datetime | None = None
    #: The link recorded against the assignment, so the recruiter's confirmation
    #: and the candidate's page quote the same string.
    assessment_link: str | None = None
    message: str


class ApplicationAssessmentCreateResult(BaseModel):
    """Outcome of authoring an assessment for one application and assigning it.

    Returns both halves because the caller did both in one action: the assessment
    that now exists, and the assignment that binds it to this candidate. The
    candidate, job and application ids are echoed from the authorized application
    so the caller can render the confirmed association without a second read --
    they are facts the server derived, not values it accepted.

    ``created_new_assessment`` is the duplicate-protection signal. False means the
    request matched an assessment already live on this application under the same
    title and nothing new was written, which is what a double-click or a retried
    request returns. See
    :meth:`~app.services.assessment.application_assessment_service.ApplicationAssessmentIntegrationService.create_and_assign`.
    """

    application_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    recruiter_id: uuid.UUID
    assessment_id: uuid.UUID
    assessment_title: str
    question_count: int
    created_new_assessment: bool
    assignment: ApplicationAssessmentAssignResult


# ── Phase 1: job-specific, candidate-specific bulk assignment ────────
#
# The single-application flow above answers "assign this to *this* candidate".
# Hiring happens in batches: a recruiter reviews one job's applicants, picks the
# several they want to evaluate, chooses (or authors) one assessment and assigns
# it to all of them at once. Doing that by calling the per-application endpoint
# once per candidate would be N round trips, N transactions and N ways to end up
# half-done.
#
# The same three load-bearing rules still hold, extended to a set of candidates:
#
# 1. **The server derives every participant.** ``job_id`` is in the path and the
#    body carries only ``application_ids``, an ``assessment_id`` and a schedule.
#    Each application is verified to belong to that job before anything is
#    written, so a caller cannot assign an assessment to another tenant's
#    candidate by pasting their application id. There is still no
#    ``candidate_id``/``recruiter_id`` and no client-supplied ``job_id``.
# 2. **One rule, one place.** The per-candidate eligibility gate is exactly
#    :data:`ASSIGNABLE_FROM` and the same ``_assignment_block_reason`` the single
#    application path uses; the catalog is the same SQL-scoped catalog. A batch is
#    never held to a different standard than a single assignment.
# 3. **A result is evidence, not a verdict.** Nothing here moves an application
#    status, shortlists, rejects or notifies a decision. It creates assignments,
#    which are tasks, and stops.
#
# The batch is *partial-success by design*: one ineligible candidate (already
# rejected, not yet shortlisted, out of attempts) must not block assigning the
# rest. Every requested candidate gets one outcome row, and the whole batch is
# written in the request's single transaction, so an unexpected failure leaves no
# assignments behind rather than a silently half-applied batch.

# Outcome vocabulary for one candidate in a batch. Fixed so the UI renders a
# sentence instead of surfacing internal exception text.
OUTCOME_ASSIGNED = "assigned"
OUTCOME_ALREADY_ASSIGNED = "already_assigned"
OUTCOME_SKIPPED = "skipped"

# The application id did not resolve to an application of this job. Reported per
# row rather than as a 404 so a batch that names one stale id still assigns the
# rest; it deliberately does not disclose whether the id exists elsewhere.
REASON_NOT_AN_APPLICANT = "not_an_applicant"

# Upper bound on one batch. A bulk action is a convenience over the per-candidate
# endpoint, not a bulk-import tool; the cap keeps one request from enqueuing an
# unbounded number of notifications and attempts.
MAX_BULK_ASSIGN = 200


class JobAssessmentAssignRequest(BaseModel):
    """Assign an existing assessment to several of one job's applicants.

    ``extra="forbid"`` for the same reason as the single-application request: the
    participants come from the job in the path plus the applications named here,
    never from client-supplied identity fields.

    ``application_ids`` is a ``list`` rather than a ``set`` so the response can be
    correlated with what was sent, but it is de-duplicated server-side: naming the
    same application twice is one attempt, not two.
    """

    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID
    application_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=MAX_BULK_ASSIGN)
    #: Same meaning as on the single-application request: when the candidate is
    #: expected to take it, or ``None`` when the recruiter chose no time.
    scheduled_for: datetime | None = None


class JobAssessmentCreateAndAssignRequest(ApplicationAssessmentCreateRequest):
    """Author one assessment for a job and assign it to several applicants.

    Inherits every authored-content field from
    :class:`ApplicationAssessmentCreateRequest` (and therefore carries no
    ``job_id``/``candidate_id``/``application_id``/``recruiter_id``), and adds the
    one thing the batch needs: the set of applications to assign it to. The job is
    derived from the path and used as the assessment's ``job_id`` server-side, so
    the authored assessment is scoped to exactly this role.
    """

    model_config = ConfigDict(extra="forbid")

    application_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=MAX_BULK_ASSIGN)


class JobAssessmentAssignItem(BaseModel):
    """The outcome for one requested candidate in a batch.

    ``application_id`` is always echoed so the caller can map an outcome back to
    the checkbox that was checked. ``candidate_id``/``candidate_name`` are
    populated when the application resolved; they are absent for a
    ``not_an_applicant`` row, where the id could not be attributed.
    """

    application_id: uuid.UUID
    candidate_id: uuid.UUID | None = None
    candidate_name: str | None = None
    #: ``assigned`` | ``already_assigned`` | ``skipped``.
    outcome: str
    #: The eligibility/limit reason for a ``skipped`` row, or ``None``. Uses the
    #: same vocabulary as the single-application options endpoint.
    reason: str | None = None
    attempt_id: uuid.UUID | None = None
    assessment_id: uuid.UUID
    assessment_title: str
    scheduled_for: datetime | None = None
    assessment_link: str | None = None
    message: str


class JobAssessmentAssignResult(BaseModel):
    """Outcome of a batch assignment: counts plus one row per candidate.

    ``assigned_count`` counts newly created attempts only. ``already_assigned``
    candidates are reported separately because they are a success from the
    recruiter's point of view but wrote nothing, which is exactly the distinction
    a retried request or a double-click turns on.
    """

    job_id: uuid.UUID
    job_title: str
    assessment_id: uuid.UUID
    assessment_title: str
    #: True when this request authored a new assessment (the create-and-assign
    #: path). False when it assigned an existing one.
    created_new_assessment: bool = False
    requested_count: int
    assigned_count: int
    already_assigned_count: int
    skipped_count: int
    items: list[JobAssessmentAssignItem] = Field(default_factory=list)


class JobAssessmentOptions(BaseModel):
    """The assessments a recruiter may assign to a job's applicants.

    Job-scoped counterpart of :class:`ApplicationAssessmentOptions`: the catalog is
    the same SQL-scoped list (this job's assessments plus job-agnostic ones), but
    the caller is the job rather than one application. ``can_assign`` is not a
    single boolean here because eligibility is per candidate, so the batch reports
    it per row instead of pretending one job-level answer exists.
    """

    job_id: uuid.UUID
    job_title: str
    available: list[AssignableAssessment] = Field(default_factory=list)


class CandidateApplicationAssessmentView(BaseModel):
    """The candidate's view of the assessment on their application.

    An explicit allowlist. It carries what the candidate needs in order to start
    and what they are entitled to see afterwards, and deliberately has no:
    recruiter identity, recruiter notes, other candidates' results, protected
    attributes, internal fairness calculations, internal hiring thresholds, or
    the platform's private ``recommendation``/``readiness_level`` grading labels,
    which read as a hiring verdict and are the recruiter's to reach.

    ``summary_text`` is the platform's own deterministic score summary, included
    because it is formatted from the authoritative score and so cannot contradict
    it.
    """

    application_id: uuid.UUID
    attempt_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    assessment_title: str | None = None
    status: AttemptStatus | None = None
    attempt_number: int | None = None
    #: The job this assessment was assigned for, so the candidate sees which role
    #: it belongs to. Application id stays the authorization key; the title is
    #: context only.
    job_id: uuid.UUID | None = None
    job_title: str | None = None
    #: The date and time the recruiter scheduled the assessment for. None when they
    #: did not choose one, which is a real answer: the candidate should be told it
    #: is waiting, not that it is due at some invented moment.
    scheduled_for: datetime | None = None
    #: When the recruiter scheduled the assessment. Not a deadline: the attempt
    #: has none until the candidate starts it.
    scheduled_at: datetime | None = None
    #: The link the candidate opens to take the attempt. The API returns it so the
    #: page and the notification agree instead of each rebuilding a route.
    assessment_link: str | None = None
    has_assessment: bool = False
    #: True once at least one attempt on this application reached a finished
    #: state, so the UI can say the assessment is done even after a later retake.
    has_completed: bool = False
    completed_count: int = 0
    attempt_count: int = 0
    #: Whether this attempt can still be started or continued. Drives the single
    #: call to action in the candidate UI.
    can_start: bool = False
    #: True when the candidate may resume an attempt already in progress.
    can_continue: bool = False
    expires_at: datetime | None = None
    submitted_at: datetime | None = None
    overall_score: float | None = None
    strong_skills: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    summary_text: str | None = None
    message: str | None = None
