"""Phase 12: run the existing assessment engine from an application.

The phase brief models this as ``Application 1--N Assignment 1--N Attempt -- 1
Result``. This module implements the *first* half of that idea on top of the
tables the platform already has, and changes nothing about the second half:

- There is no ``application_assignments`` table. An assignment is a
  ``CandidateAssessment`` row in ``assigned`` state -- the status and the model
  default that already existed and that no code path ever wrote. A recruiter
  creates it; the candidate starts it; ``AssessmentService.start_attempt`` now
  resumes it. One attempt counter, one place that enforces
  ``allowed_attempts``, one result per attempt, and the existing
  start/answer/code/submit/grade path works unchanged.
- Grading, scoring, question generation, integrity capture, the attempt state
  machine and the result contract are **not** reimplemented. This module is the
  application-driven front door onto them.

Three rules the whole module is built around.

1. **The server derives the participants.** ``application_id`` in the path is the
   only identity input; candidate, job and organization come from the authorized
   application. The request body carries an ``assessment_id`` and nothing else,
   with ``extra="forbid"``. This closes the gap where
   :class:`~app.domain.assessment_schemas.AssessmentCreateRequest` accepts a
   client-supplied ``job_id``, which lets a caller point an assessment at a job
   they do not own.

2. **A result is evidence, not a verdict.** Nothing here calls
   ``transition_application``. A passing score does not shortlist, a failing one
   does not reject, and ``RejectionReason.FAILED_ASSESSMENT`` stays unwired. An
   assessment is evidence the recruiter reads before deciding, and the decision
   remains the recruiter's. ``passed`` is reported because it is the assessment's
   own configured threshold and the candidate is entitled to it -- it is not a
   hiring signal, and the copy that renders it says so.

3. **Availability is computed once, server-side, and reused.** The eligibility
   rules, the assignable catalog and the per-attempt actions are projected by
   :meth:`get_options`, and the mutating methods re-derive the same
   conditions rather than trusting the client or the projection. A control the UI
   offers is one the API accepts; a control the API would refuse is not offered.
   In particular the catalog is filtered in SQL, so the browser never receives a
   row it could not have used -- including rows from another organization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.domain.application_assessment_schemas import (
    ASSIGNABLE_FROM,
    OUTCOME_ALREADY_ASSIGNED,
    OUTCOME_ASSIGNED,
    OUTCOME_SKIPPED,
    REASON_APPLICATION_FINAL,
    REASON_APPLICATION_NOT_ELIGIBLE,
    REASON_ASSIGNMENT_EXISTS,
    REASON_ATTEMPT_FINISHED,
    REASON_ATTEMPT_NOT_RESCHEDULABLE,
    REASON_NOT_AN_APPLICANT,
    REASON_NO_ATTEMPTS_REMAINING,
    ApplicationAssessmentAssignRequest,
    ApplicationAssessmentAssignResult,
    ApplicationAssessmentAttemptAction,
    ApplicationAssessmentCreateRequest,
    ApplicationAssessmentCreateResult,
    ApplicationAssessmentEvidence,
    ApplicationAssessmentOptionsWithAttempts,
    ApplicationAssessmentRescheduleRequest,
    ApplicationAssessmentSummary,
    AssignableAssessment,
    CandidateApplicationAssessmentView,
    JobAssessmentAssignItem,
    JobAssessmentAssignRequest,
    JobAssessmentAssignResult,
    JobAssessmentCreateAndAssignRequest,
    JobAssessmentOptions,
)
from app.domain.enums import (
    ApplicationStatus,
    AssessmentMode,
    AttemptStatus,
    AuditEventType,
)
from app.domain.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentResult,
    CandidateAnswer,
    CandidateAssessment,
    Job,
    JobApplication,
    User,
)
from app.services.applications.application_lifecycle_service import (
    TERMINAL_STATUSES,
    ApplicationLifecycleService,
)
from app.services.assessment.assessment_service import (
    AssessmentService,
    candidate_take_link,
    resolve_take_link,
)
from app.services.audit_service import AuditService
from app.services.screening.access import (
    JobAccessDeniedError,
    JobNotFoundError,
    authorize_application_ownership,
    authorize_job_access,
)

logger = get_logger(__name__)


def _mode(value: str | None) -> AssessmentMode:
    """Coerce a stored ``Assessment.mode`` to the enum, or ``CUSTOM``.

    ``AssessmentMode`` has no ``from_value`` helper, and a mode string is
    user-supplied through the builder, so an unrecognized value is a real
    possibility. It degrades to ``CUSTOM`` -- a display-only field on a summary --
    rather than raising and failing the whole evidence payload over one row.
    """
    try:
        return AssessmentMode(value) if value else AssessmentMode.CUSTOM
    except ValueError:
        return AssessmentMode.CUSTOM


def _aware(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive timestamp read back from SQLite.

    Mirrors ``assessment_service._aware``. The column is timezone-aware, but
    SQLite hands back naive datetimes; comparing a naive value against
    ``datetime.now(timezone.utc)`` raises, so every expiry comparison in this
    module goes through here.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _utc(value: datetime | None) -> datetime | None:
    """Normalize an incoming schedule to aware UTC for storage.

    A client may legitimately send a naive local time or an offset-aware one, and
    the column is ``DateTime(timezone=True)``. Storing whatever arrived would make
    two schedules that name the same instant compare unequal whenever one carried
    an offset and the other did not -- and SQLite drops the offset on the way in
    anyway, so the value read back would not match the value written. Normalizing
    once, here, means "is this the same schedule?" is answerable later.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        # A naive time is read as UTC rather than guessed at: there is no
        # defensible way to attach the *server's* local zone to a recruiter's
        # wall-clock time, and inventing one would silently shift the schedule.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _same_instant(a: datetime | None, b: datetime | None) -> bool:
    """Whether two stored/request schedules name the same moment.

    Both sides go through :func:`_utc` first, and SQLite hands back naive values,
    so comparing them directly would be comparing an aware value with a naive one
    and raise. Truncating to whole seconds absorbs the sub-second precision SQLite
    drops on a round trip, so an unchanged schedule is not reported as a change
    just because the database cannot store the microseconds it was given.
    """
    left, right = _utc(a), _utc(b)
    if left is None or right is None:
        return left is right
    return left.replace(microsecond=0) == right.replace(microsecond=0)


def _effective_schedule(attempt: CandidateAssessment) -> datetime | None:
    """What to show as this attempt's schedule.

    The chosen ``scheduled_for`` when there is one, otherwise the assignment time.
    The fallback is what keeps every attempt created before migration 0029 -- and
    every assignment a recruiter made without naming a time -- rendering exactly as
    it did before the column existed.
    """
    return _aware(attempt.scheduled_for) or _aware(attempt.assigned_at)


class ApplicationAssessmentIntegrationService:
    """Application-driven assignment and evidence over the existing engine."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lifecycle = ApplicationLifecycleService(session)
        self.assessment_service = AssessmentService(session)
        self.audit = AuditService(session)

    # ── Reads ───────────────────────────────────────────────────────

    async def get_options(
        self, application_id: uuid.UUID, actor: User,
    ) -> ApplicationAssessmentOptionsWithAttempts:
        """Server-authoritative assignment affordances for one application.

        Recruiter-only, via the same staff-access check the mutating path uses,
        so a read cannot drift from a write. The catalog is filtered in SQL to
        what this application may actually be assigned, and each entry reports
        whether it is already live on the application.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        attempts = await self._attempts_for_application(application_id)

        is_final = status in TERMINAL_STATUSES
        can_assign = self._assignment_block_reason(status, is_final) is None

        # An assessment with a live attempt is "already assigned", not
        # "unavailable": the catalog entry stays visible so the recruiter sees
        # what the application already has.
        live_by_assessment = {
            at.assessment_id: at
            for at in attempts
            if at.status not in AttemptStatus.finished()
        }
        assigned_ids = set(live_by_assessment.keys())

        catalog: list[AssignableAssessment] = []
        for assessment, question_count, skills in await self._assignable_catalog(
            job_id=app.job_id, excluded_ids=assigned_ids,
        ):
            catalog.append(
                AssignableAssessment(
                    assessment_id=assessment.id,
                    title=assessment.title,
                    description=assessment.description,
                    mode=_mode(assessment.mode),
                    status=assessment.status,
                    duration_minutes=assessment.duration_minutes,
                    question_count=question_count,
                    passing_score=assessment.passing_score,
                    allowed_attempts=assessment.allowed_attempts,
                    adaptive=bool(assessment.adaptive),
                    skills=skills,
                    already_assigned=False,
                )
            )

        # Entries already live on this application, so the recruiter can see the
        # full picture without a second request.
        for assessment_id, attempt in live_by_assessment.items():
            assessment = await self.session.get(Assessment, assessment_id)
            if assessment is None:
                continue
            catalog.append(
                AssignableAssessment(
                    assessment_id=assessment.id,
                    title=assessment.title,
                    description=assessment.description,
                    mode=_mode(assessment.mode),
                    status=assessment.status,
                    duration_minutes=assessment.duration_minutes,
                    question_count=0,
                    passing_score=assessment.passing_score,
                    allowed_attempts=assessment.allowed_attempts,
                    adaptive=bool(assessment.adaptive),
                    skills=[],
                    already_assigned=True,
                )
            )

        actions: list[ApplicationAssessmentAttemptAction] = []
        for attempt in attempts:
            finished = attempt.status in AttemptStatus.finished()
            can_reassign = False
            reassign_reason = REASON_ATTEMPT_FINISHED
            if finished and can_assign:
                # A finished attempt may be retaken as a *new* attempt, provided
                # the assessment still has attempts left for this candidate.
                if await self._attempts_remaining(
                    attempt.assessment_id, app.candidate_id,
                ) >= 1:
                    can_reassign = True
                    reassign_reason = None
            elif not finished:
                reassign_reason = REASON_ASSIGNMENT_EXISTS
            # A schedule can be moved only while the attempt is still live. A
            # finished attempt's timing is part of the evidence it produced, and
            # its duration clock has usually already been consumed, so the time it
            # was taken is a historical fact rather than a plan.
            can_reschedule = not finished
            actions.append(
                ApplicationAssessmentAttemptAction(
                    attempt_id=attempt.id,
                    status=(
                        AttemptStatus.from_value(attempt.status)
                        or AttemptStatus.COMPLETED
                    ),
                    can_reassign=can_reassign,
                    reassign_unavailable_reason=reassign_reason,
                    scheduled_for=_effective_schedule(attempt),
                    can_reschedule=can_reschedule,
                    reschedule_unavailable_reason=(
                        None if can_reschedule
                        else REASON_ATTEMPT_NOT_RESCHEDULABLE
                    ),
                )
            )

        return ApplicationAssessmentOptionsWithAttempts(
            application_id=app.id,
            current_status=status,
            status_is_final=is_final,
            can_assign=can_assign,
            assign_unavailable_reason=self._assignment_block_reason(status, is_final),
            has_assessments=bool(attempts),
            attempt_count=len(attempts),
            available=catalog,
            actions=actions,
        )

    async def get_evidence(
        self, application_id: uuid.UUID, actor: User,
    ) -> ApplicationAssessmentEvidence:
        """All assessment evidence for an application, staff-only.

        Raises ``NotFoundError`` for an unknown application and ``ForbiddenError``
        when the actor has no staff access, so a cross-tenant caller cannot
        distinguish "does not exist" from "not yours".
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        attempts = await self._attempts_for_application(application_id)
        summaries = await self._summaries(attempts)

        scores = [
            s.overall_score for s in summaries
            if s.overall_score is not None and s.status == AttemptStatus.COMPLETED
        ]
        candidate = await self.session.get(User, app.candidate_id)
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        return ApplicationAssessmentEvidence(
            application_id=app.id,
            job_id=app.job_id,
            job_title=job.title if job else "",
            candidate_id=app.candidate_id,
            candidate_name=candidate.full_name if candidate else "",
            application_status=status,
            attempt_count=len(summaries),
            completed_count=sum(
                1 for s in summaries if s.status == AttemptStatus.COMPLETED
            ),
            # Averaged over completed attempts only, so an attempt nobody has
            # finished cannot drag the figure down. None, never 0.0, until one is
            # actually completed.
            average_overall_score=(
                round(sum(scores) / len(scores), 1) if scores else None
            ),
            attempts=summaries,
        )

    async def get_candidate_view(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID,
    ) -> CandidateApplicationAssessmentView:
        """The candidate's allowlisted view of the assessment on their application.

        Ownership is proven by ``authorize_application_ownership``, which raises
        the same ``ApplicationAccessDeniedError`` for "no such application" and
        "not yours" -- the indistinguishable 404 the brief requires, so
        application ids cannot be probed for existence by a candidate.
        """
        candidate = await self.session.get(User, candidate_id)
        if candidate is None:
            raise NotFoundError("Application not found")
        app = await authorize_application_ownership(
            self.session, application_id, candidate,
        )
        attempts = await self._attempts_for_application(application_id)
        if not attempts:
            return CandidateApplicationAssessmentView(
                application_id=app.id, has_assessment=False,
            )

        # Newest first, so the card reflects the attempt a candidate is expected
        # to act on rather than a historical one.
        ordered = sorted(
            attempts,
            key=lambda at: (at.assigned_at or at.created_at or at.started_at),
            reverse=True,
        )
        latest = ordered[0]
        now = datetime.now(timezone.utc)
        status = AttemptStatus.from_value(latest.status) or AttemptStatus.COMPLETED
        expires_at = _aware(latest.expires_at)
        is_expired = bool(expires_at and now >= expires_at)

        summaries = await self._summaries([latest])
        summary = summaries[0]

        finished_count = sum(
            1 for at in attempts if at.status in AttemptStatus.finished()
        )
        job = await self.session.get(Job, app.job_id) if app.job_id else None

        message: str | None = None
        if status == AttemptStatus.ASSIGNED:
            message = "You have been assigned an assessment. Complete it when you are ready."
        elif status == AttemptStatus.IN_PROGRESS:
            message = "Your assessment is in progress. Continue where you left off."
        elif status == AttemptStatus.COMPLETED:
            message = "Your assessment has been submitted. Your result is available."
        elif status == AttemptStatus.EXPIRED:
            message = "Your assessment time expired before it was submitted."
        elif status == AttemptStatus.ABANDONED:
            message = "Your assessment attempt was closed."

        return CandidateApplicationAssessmentView(
            application_id=app.id,
            attempt_id=latest.id,
            assessment_id=latest.assessment_id,
            assessment_title=summary.assessment_title,
            status=status,
            attempt_number=latest.attempt_number,
            job_id=app.job_id,
            job_title=job.title if job else None,
            scheduled_for=_aware(latest.scheduled_for),
            scheduled_at=_aware(latest.assigned_at),
            # The link the assignment issued, falling back to the derived route for
            # rows that predate migration 0029. Identical in practice, but reading
            # the stored value is what lets the page, the notification and the
            # database be quoted as the same thing.
            assessment_link=resolve_take_link(
                latest.assessment_link, latest.assessment_id,
            ),
            has_assessment=True,
            has_completed=bool(finished_count),
            completed_count=finished_count,
            attempt_count=len(attempts),
            # An assigned attempt is startable; an in-progress one is resumable.
            # A finished one offers neither, because there is nothing to do and
            # the result is shown instead.
            can_start=status == AttemptStatus.ASSIGNED and not is_expired,
            can_continue=status == AttemptStatus.IN_PROGRESS and not is_expired,
            expires_at=expires_at,
            submitted_at=_aware(latest.submitted_at),
            # The authoritative score, and the skills/topics/summary the platform
            # derives from it. No ``recommendation`` and no ``readiness_level``:
            # those are the platform's internal hiring-ish labels, they read as a
            # verdict, and the recruiter's decision is the only verdict.
            overall_score=summary.overall_score,
            strong_skills=summary.strong_skills,
            recommended_topics=summary.recommended_topics,
            summary_text=summary.summary_text,
            message=message,
        )

    # ── Writes ──────────────────────────────────────────────────────

    async def assign(
        self,
        application_id: uuid.UUID,
        body: ApplicationAssessmentAssignRequest,
        actor: User,
    ) -> ApplicationAssessmentAssignResult:
        """Assign an assessment to an application.

        Idempotent in the sense that matters: while an attempt for this
        assessment is still live on this application, a second request re-reads
        it and reports ``already_assigned`` instead of creating a second live
        attempt. A retried request is therefore harmless, and one application
        never ends up with two open attempts at the same assessment.

        The one case that is *not* a no-op is a repeat that names a **different**
        time. That is a reschedule, so the existing row's ``scheduled_for`` is
        updated and ``rescheduled`` comes back true. Creating a second attempt
        instead would leave the candidate with two open attempts at one assessment
        where they had asked to move one, and updating is the only outcome that
        keeps "one application, one live attempt per assessment" true.

        A repeat that omits ``scheduled_for``, or names the time already stored,
        is still a pure no-op -- which is what keeps an ordinary double-click and
        an ordinary retry behaving exactly as they did before scheduling existed.
        """
        app, _job = await self.lifecycle.authorize_staff_access(application_id, actor)
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        is_final = status in TERMINAL_STATUSES

        # Re-derived here rather than trusted from the options projection: this
        # is the authoritative gate.
        blocked = self._assignment_block_reason(status, is_final)
        if blocked is not None:
            raise ConflictError(
                "This application cannot be assigned an assessment",
                extra={
                    "application_id": str(application_id),
                    "status": status.value,
                    "reason": blocked,
                },
            )

        assessment = await self._load_assignable_assessment(
            body.assessment_id, app.job_id,
        )

        attempts = await self._attempts_for_application(application_id)
        for attempt in attempts:
            if (
                attempt.assessment_id == assessment.id
                and attempt.status not in AttemptStatus.finished()
            ):
                if (
                    body.scheduled_for is not None
                    and not _same_instant(attempt.scheduled_for, body.scheduled_for)
                ):
                    return await self._apply_reschedule(
                        app, attempt, assessment, body.scheduled_for, actor,
                    )
                return ApplicationAssessmentAssignResult(
                    application_id=app.id,
                    attempt_id=attempt.id,
                    assessment_id=assessment.id,
                    assessment_title=assessment.title,
                    attempt_status=(
                        AttemptStatus.from_value(attempt.status)
                        or AttemptStatus.ASSIGNED
                    ),
                    already_assigned=True,
                    scheduled_for=_aware(attempt.scheduled_for),
                    assessment_link=resolve_take_link(
                        attempt.assessment_link, attempt.assessment_id,
                    ),
                    message=(
                        f"{assessment.title} is already assigned to this application."
                    ),
                )

        # Refuse rather than assign something unstartable. ``start_attempt``
        # enforces ``allowed_attempts`` against every attempt this candidate has
        # for this assessment, so an exhausted candidate would be handed an
        # assignment that fails the moment they open it.
        if await self._attempts_remaining(assessment.id, app.candidate_id) < 1:
            raise ConflictError(
                "This candidate has already used every allowed attempt for this "
                "assessment",
                extra={
                    "application_id": str(application_id),
                    "assessment_id": str(assessment.id),
                    "reason": REASON_NO_ATTEMPTS_REMAINING,
                },
            )

        now = datetime.now(timezone.utc)
        attempt = CandidateAssessment(
            application_id=app.id,
            assessment_id=assessment.id,
            candidate_id=app.candidate_id,
            # MAX, not COUNT+1: the unique constraint is
            # (assessment_id, candidate_id, attempt_number), and attempts are not
            # contiguous -- a self-started attempt, an expired one and a retake
            # all leave gaps. COUNT would collide with an existing row.
            attempt_number=await self._next_attempt_number(
                assessment.id, app.candidate_id,
            ),
            status=AttemptStatus.ASSIGNED.value,
            assigned_by=actor.id,
            assigned_at=now,
            # The time the recruiter chose, stored only if they chose one. Left
            # NULL otherwise rather than defaulted to ``now``: "no time was
            # chosen" and "due immediately" are different facts, and collapsing
            # them is what made this indistinguishable from the assignment
            # timestamp to begin with.
            scheduled_for=_utc(body.scheduled_for),
            # The link issued with this assignment, written from the same helper
            # every reader uses so the recorded value and the derived one cannot
            # drift apart.
            assessment_link=candidate_take_link(assessment.id),
            question_order=None,
            integrity_events=[],
            current_index=0,
        )
        self.session.add(attempt)
        await self.session.flush()

        await self.audit.log(
            AuditEventType.ASSESSMENT_ASSIGNED,
            action="assign_assessment",
            user_id=actor.id,
            organization_id=_job.organization_id if _job else None,
            resource_type="job_application",
            resource_id=str(app.id),
            details={
                "attempt_id": str(attempt.id),
                "assessment_id": str(assessment.id),
                "assessment_title": assessment.title,
                "candidate_id": str(app.candidate_id),
                "job_id": str(app.job_id),
                # The chosen schedule, so the audit trail records when the
                # assessment was actually for rather than only when it was asked
                # for. Absent, not null, when the recruiter named no time.
                **(
                    {"scheduled_for": _utc(body.scheduled_for).isoformat()}
                    if body.scheduled_for is not None else {}
                ),
            },
        )

        return ApplicationAssessmentAssignResult(
            application_id=app.id,
            attempt_id=attempt.id,
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            attempt_status=AttemptStatus.ASSIGNED,
            already_assigned=False,
            scheduled_for=_utc(body.scheduled_for),
            assessment_link=attempt.assessment_link,
            message=(
                f"{assessment.title} has been assigned. The candidate has been "
                "notified."
            ),
        )

    async def reschedule(
        self,
        application_id: uuid.UUID,
        attempt_id: uuid.UUID,
        body: ApplicationAssessmentRescheduleRequest,
        actor: User,
    ) -> ApplicationAssessmentAssignResult:
        """Move an existing assignment to a new date and time.

        Updates the existing attempt rather than creating a second one, which is
        the whole point: rescheduling is a change to a plan the candidate already
        has, and minting a new attempt would leave them holding two open attempts
        at one assessment and quietly reset their attempt counter.

        The attempt is verified to belong to the application in the path, and the
        application to the actor, so neither id can be borrowed from another
        application or another tenant.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        attempt = await self.session.get(CandidateAssessment, attempt_id)
        # One indistinguishable failure for "no such attempt" and "not on this
        # application", so an attempt id cannot be probed across applications.
        if attempt is None or attempt.application_id != app.id:
            raise NotFoundError("Assigned assessment not found")

        assessment = await self.session.get(Assessment, attempt.assessment_id)
        if assessment is None:
            raise NotFoundError("Assessment not found")

        if attempt.status in AttemptStatus.finished():
            raise ConflictError(
                "This assessment has already been completed, so its schedule can "
                "no longer be changed",
                extra={
                    "attempt_id": str(attempt_id),
                    "status": attempt.status,
                    "reason": REASON_ATTEMPT_NOT_RESCHEDULABLE,
                },
            )

        # A reschedule to the time already stored is not a change. Reporting it as
        # one would tell the candidate their assessment had moved when it had not,
        # which is the same class of mistake as defaulting an absent schedule to
        # "now". The row is left untouched and the caller gets the same
        # already-assigned answer ``assign`` gives for a repeat.
        if _same_instant(attempt.scheduled_for, body.scheduled_for):
            return ApplicationAssessmentAssignResult(
                application_id=app.id,
                attempt_id=attempt.id,
                assessment_id=assessment.id,
                assessment_title=assessment.title,
                attempt_status=(
                    AttemptStatus.from_value(attempt.status)
                    or AttemptStatus.ASSIGNED
                ),
                already_assigned=True,
                rescheduled=False,
                scheduled_for=_aware(attempt.scheduled_for),
                assessment_link=resolve_take_link(
                    attempt.assessment_link, attempt.assessment_id,
                ),
                message=(
                    f"{assessment.title} is already scheduled for that time."
                ),
            )

        return await self._apply_reschedule(
            app, attempt, assessment, body.scheduled_for, actor,
        )

    async def _apply_reschedule(
        self,
        app: JobApplication,
        attempt: CandidateAssessment,
        assessment: Assessment,
        scheduled_for: datetime,
        actor: User,
    ) -> ApplicationAssessmentAssignResult:
        """Write a new schedule onto a live assignment and report the outcome.

        Shared by the explicit reschedule endpoint and by ``assign`` when it is
        handed a live assignment together with a different time, so both verbs
        produce one identical row update, one audit event and one notification
        rather than two subtly different implementations of the same change.
        """
        previous = _aware(attempt.scheduled_for)
        attempt.scheduled_for = _utc(scheduled_for)
        # The link is re-issued rather than assumed current. It is derived from the
        # assessment id, which cannot change for an existing attempt, so this is
        # normally a no-op -- but it means a row that predates migration 0029
        # acquires its link on first reschedule instead of staying without one.
        attempt.assessment_link = resolve_take_link(
            attempt.assessment_link, attempt.assessment_id,
        )
        await self.session.flush()

        job = await self.session.get(Job, app.job_id) if app.job_id else None
        await self.audit.log(
            AuditEventType.ASSESSMENT_RESCHEDULED,
            action="reschedule_assessment",
            user_id=actor.id,
            organization_id=job.organization_id if job else None,
            resource_type="job_application",
            resource_id=str(app.id),
            details={
                "attempt_id": str(attempt.id),
                "assessment_id": str(assessment.id),
                "assessment_title": assessment.title,
                "candidate_id": str(app.candidate_id),
                "job_id": str(app.job_id),
                "previous_scheduled_for": previous.isoformat() if previous else None,
                "scheduled_for": _utc(scheduled_for).isoformat(),
            },
        )

        return ApplicationAssessmentAssignResult(
            application_id=app.id,
            attempt_id=attempt.id,
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            attempt_status=(
                AttemptStatus.from_value(attempt.status) or AttemptStatus.ASSIGNED
            ),
            already_assigned=True,
            rescheduled=True,
            scheduled_for=_aware(attempt.scheduled_for),
            assessment_link=attempt.assessment_link,
            message=(
                f"{assessment.title} has been rescheduled. The candidate has been "
                "notified of the new time."
            ),
        )

    # ── Rules ───────────────────────────────────────────────────────

    @staticmethod
    def _assignment_block_reason(
        status: ApplicationStatus, is_final: bool,
    ) -> str | None:
        """Why this application cannot receive an assessment, or ``None``.

        Terminal first, so a rejected or withdrawn application gets the specific
        "finalized" reason rather than the vaguer eligibility one.
        """
        if is_final or status in TERMINAL_STATUSES:
            return REASON_APPLICATION_FINAL
        if status not in ASSIGNABLE_FROM:
            return REASON_APPLICATION_NOT_ELIGIBLE
        return None

    async def _load_assignable_assessment(
        self, assessment_id: uuid.UUID, job_id: uuid.UUID,
    ) -> Assessment:
        """Load an assessment that may be assigned to this application, or 404.

        The scope check is here and not only in the catalog projection, so a
        caller cannot post an ``assessment_id`` for a job it does not own and get
        past the UI.

        A single ``NotFoundError`` covers every rejection -- wrong job, another
        organization's job, draft status, no questions -- so the response does not
        disclose whether some other tenant's assessment id exists. An assessment
        the caller could not have reached from the catalog is indistinguishable
        from one that does not exist.
        """
        assessment = await self.session.get(Assessment, assessment_id)
        if assessment is None:
            raise NotFoundError("Assessment not found")
        if assessment.status != "published":
            raise NotFoundError("Assessment not found")
        if assessment.job_id is not None and assessment.job_id != job_id:
            raise NotFoundError("Assessment not found")

        has_questions = await self.session.scalar(
            select(func.count())
            .select_from(AssessmentQuestion)
            .where(AssessmentQuestion.assessment_id == assessment_id)
        )
        if not has_questions:
            # ``start_attempt`` raises on an empty assessment, so offering one
            # would be offering a task that cannot be performed.
            raise NotFoundError("Assessment not found")
        return assessment

    async def _assignable_catalog(
        self, *, job_id: uuid.UUID,
        excluded_ids: set[uuid.UUID],
    ) -> list[tuple[Assessment, int, list[str]]]:
        """Published assessments assignable to this application, in two queries.

        **Scoping.** ``Assessment`` has a nullable ``job_id`` and *no*
        ``organization_id``, so the catalog is scoped by the application instead
        of by tenant: an assessment is offered when it is scoped to this
        application's own job, or when it is job-agnostic (``job_id IS NULL``).

        The job-agnostic case is the one honest gap in the data model. Such an
        assessment carries no organization marker, so it cannot be proven to
        belong to any tenant and is treated as platform-shared -- the same
        reading the existing unscoped ``GET /assessments`` already implies. A
        job-scoped assessment is always restricted to the application's own job,
        so a recruiter can neither assign nor see a colleague's private
        assessment for this application.

        Assessments from the actor's *other* jobs are deliberately excluded even
        when the actor can access them: the assessment has to be relevant to the
        application it is assigned to, and a job-A assessment on a job-B
        application is nonsense the recruiter would then have to explain to the
        candidate.

        The per-assessment question count and skill list are the expensive part,
        so they are aggregated in SQL for the whole catalog rather than queried
        per assessment (N+1). ``excluded_ids`` are already live on the
        application; the caller returns those separately, marked
        ``already_assigned``.
        """
        stmt = (
            select(Assessment)
            .where(Assessment.status == "published")
            .where(or_(Assessment.job_id.is_(None), Assessment.job_id == job_id))
            .order_by(Assessment.title)
        )
        if excluded_ids:
            stmt = stmt.where(Assessment.id.not_in(excluded_ids))
        rows = (await self.session.execute(stmt)).scalars().all()
        if not rows:
            return []

        by_id = {a.id: a for a in rows}
        ids = list(by_id.keys())

        counts = dict((await self.session.execute(
            select(AssessmentQuestion.assessment_id, func.count())
            .where(AssessmentQuestion.assessment_id.in_(ids))
            .group_by(AssessmentQuestion.assessment_id)
        )).all())

        skill_rows = (await self.session.execute(
            select(AssessmentQuestion.assessment_id, AssessmentQuestion.skill)
            .where(AssessmentQuestion.assessment_id.in_(ids))
            .where(AssessmentQuestion.skill.is_not(None))
            .distinct()
            .order_by(AssessmentQuestion.skill)
        )).all()
        skills: dict[uuid.UUID, list[str]] = {}
        for assessment_id, skill in skill_rows:
            if skill:
                skills.setdefault(assessment_id, []).append(str(skill))

        return [
            (by_id[assessment_id], int(counts.get(assessment_id, 0)),
             skills.get(assessment_id, []))
            for assessment_id in by_id
            # An assessment with no questions is excluded here as well as at
            # write time, so the catalog never shows one.
            if counts.get(assessment_id, 0) > 0
        ]

    async def _attempts_for_application(
        self, application_id: uuid.UUID,
    ) -> list[CandidateAssessment]:
        return list((await self.session.execute(
            select(CandidateAssessment)
            .where(CandidateAssessment.application_id == application_id)
            .order_by(CandidateAssessment.created_at)
        )).scalars().all())

    async def _next_attempt_number(
        self, assessment_id: uuid.UUID, candidate_id: uuid.UUID,
    ) -> int:
        """Next attempt number for this (assessment, candidate) pair.

        ``MAX + 1`` over every attempt, not ``COUNT + 1``, because the number is
        the last component of a unique constraint and attempt numbers are not
        contiguous: expired, abandoned and self-started attempts all leave gaps
        that a count would walk back into.
        """
        current = await self.session.scalar(
            select(func.max(CandidateAssessment.attempt_number))
            .where(CandidateAssessment.assessment_id == assessment_id)
            .where(CandidateAssessment.candidate_id == candidate_id)
        )
        return int(current or 0) + 1

    async def _attempts_remaining(
        self, assessment_id: uuid.UUID, candidate_id: uuid.UUID,
    ) -> int:
        """How many more attempts this candidate may start on this assessment.

        Plain ``allowed - used``. The caller then asks "is at least one left?",
        which is exactly the question of whether a new row can be created -- so
        there is no ``extra_used`` adjustment to get wrong. (An earlier version
        folded the pending attempt into the arithmetic and ended up refusing the
        assignment precisely when exactly one attempt was available.)
        """
        assessment = await self.session.get(Assessment, assessment_id)
        allowed = int(assessment.allowed_attempts) if assessment else 0
        used = await self.session.scalar(
            select(func.count())
            .select_from(CandidateAssessment)
            .where(CandidateAssessment.assessment_id == assessment_id)
            .where(CandidateAssessment.candidate_id == candidate_id)
        )
        return allowed - int(used or 0)

    async def _summaries(
        self, attempts: list[CandidateAssessment],
    ) -> list[ApplicationAssessmentSummary]:
        """Build the evidence projection for a set of attempts in fixed queries.

        The counts, results and question totals are fetched for the whole set at
        once; a loop of per-attempt queries would issue 3N of them, which is the
        kind of thing that is fine in a test with two attempts and falls over on a
        real application history.
        """
        if not attempts:
            return []

        attempt_ids = [at.id for at in attempts]
        assessment_ids = {at.assessment_id for at in attempts}

        assessments = {
            a.id: a for a in (await self.session.execute(
                select(Assessment).where(Assessment.id.in_(assessment_ids))
            )).scalars().all()
        }
        results = {
            r.attempt_id: r for r in (await self.session.execute(
                select(AssessmentResult).where(AssessmentResult.attempt_id.in_(attempt_ids))
            )).scalars().all()
        }
        question_totals = dict((await self.session.execute(
            select(AssessmentQuestion.assessment_id, func.count())
            .where(AssessmentQuestion.assessment_id.in_(assessment_ids))
            .group_by(AssessmentQuestion.assessment_id)
        )).all())
        answered_counts = dict((await self.session.execute(
            select(CandidateAnswer.attempt_id, func.count())
            .where(CandidateAnswer.attempt_id.in_(attempt_ids))
            .group_by(CandidateAnswer.attempt_id)
        )).all())

        summaries: list[ApplicationAssessmentSummary] = []
        for attempt in attempts:
            assessment = assessments.get(attempt.assessment_id)
            result = results.get(attempt.id)
            status = AttemptStatus.from_value(attempt.status) or AttemptStatus.COMPLETED
            has_result = result is not None and status == AttemptStatus.COMPLETED
            summaries.append(
                ApplicationAssessmentSummary(
                    attempt_id=attempt.id,
                    assessment_id=attempt.assessment_id,
                    assessment_title=assessment.title if assessment else "",
                    mode=_mode(assessment.mode if assessment else None),
                    status=status,
                    attempt_number=attempt.attempt_number,
                    # The chosen schedule, falling back to the assignment time so an
                    # attempt with no explicit schedule still shows when it was
                    # given to the candidate rather than showing nothing.
                    scheduled_for_hint=_effective_schedule(attempt),
                    started_at=_aware(attempt.started_at),
                    expires_at=_aware(attempt.expires_at),
                    submitted_at=_aware(attempt.submitted_at),
                    completed_at=(
                        _aware(result.created_at) if has_result
                        else _aware(attempt.submitted_at)
                    ),
                    questions_total=int(question_totals.get(attempt.assessment_id, 0)),
                    questions_answered=int(answered_counts.get(attempt.id, 0)),
                    # None until graded. A scored zero and an ungraded attempt are
                    # very different facts and must not look alike.
                    overall_score=(result.overall_score if has_result else None),
                    passed_threshold=assessment.passing_score if assessment else None,
                    passed=(
                        bool(result.overall_score >= assessment.passing_score)
                        if has_result and assessment else None
                    ),
                    section_scores=list(result.section_scores or []) if has_result else [],
                    strong_skills=list(result.strong_skills or []) if has_result else [],
                    weak_skills=list(result.weak_skills or []) if has_result else [],
                    recommended_topics=(
                        list(result.recommended_topics or []) if has_result else []
                    ),
                    accuracy=(result.accuracy if has_result else None),
                    time_management=(result.time_management if has_result else None),
                    # The platform's deterministic summary, formatted from the
                    # score above, so it cannot disagree with it.
                    summary_text=(result.ai_summary if has_result else None),
                    integrity_flag_count=len(attempt.integrity_events or []),
                )
            )
        return summaries

    async def create_and_assign(
        self,
        application_id: uuid.UUID,
        body: "ApplicationAssessmentCreateRequest",
        actor: User,
    ) -> "ApplicationAssessmentCreateResult":
        """Author a candidate-specific assessment for this application and assign it."""
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)

        create_req = body.to_create_request(job.id)
        assessment = await self.assessment_service.create_assessment(
            recruiter_id=actor.id,
            req=create_req,
        )

        assign_req = ApplicationAssessmentAssignRequest(
            assessment_id=assessment.id,
            scheduled_for=body.scheduled_for,
        )
        assign_result = await self.assign(application_id, assign_req, actor)

        question_count = await self.session.scalar(
            select(func.count()).select_from(AssessmentQuestion)
            .where(AssessmentQuestion.assessment_id == assessment.id)
        ) or 0

        return ApplicationAssessmentCreateResult(
            application_id=app.id,
            job_id=job.id,
            candidate_id=app.candidate_id,
            recruiter_id=actor.id,
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            question_count=int(question_count),
            created_new_assessment=True,
            assignment=assign_result,
        )

    # ── Phase 1: job-scoped bulk assignment ─────────────────────────

    async def get_job_assessment_options(
        self, job_id: uuid.UUID, actor: User,
    ) -> JobAssessmentOptions:
        """The assessments this recruiter may assign to a job's applicants.

        The job-scoped counterpart of :meth:`get_options`, built from the same
        SQL-scoped catalog so the bulk screen and the per-application panel can
        never offer different assessments. There is no single ``can_assign`` here:
        eligibility is per candidate, so it is decided per row at write time
        rather than guessed at the job level.
        """
        job = await self._authorize_job(job_id, actor)
        catalog: list[AssignableAssessment] = []
        for assessment, question_count, skills in await self._assignable_catalog(
            job_id=job.id, excluded_ids=set(),
        ):
            catalog.append(
                AssignableAssessment(
                    assessment_id=assessment.id,
                    title=assessment.title,
                    description=assessment.description,
                    mode=_mode(assessment.mode),
                    status=assessment.status,
                    duration_minutes=assessment.duration_minutes,
                    question_count=question_count,
                    passing_score=assessment.passing_score,
                    allowed_attempts=assessment.allowed_attempts,
                    adaptive=bool(assessment.adaptive),
                    skills=skills,
                    already_assigned=False,
                )
            )
        return JobAssessmentOptions(
            job_id=job.id, job_title=job.title, available=catalog,
        )

    async def assign_to_job_applicants(
        self,
        job_id: uuid.UUID,
        body: JobAssessmentAssignRequest,
        actor: User,
    ) -> JobAssessmentAssignResult:
        """Assign an existing assessment to several of one job's applicants.

        The assessment is resolved through the same
        :meth:`_load_assignable_assessment` the single-application path uses, so a
        job-scoped assessment from another role, a draft, or an empty assessment is
        the same indistinguishable 404 here as there.
        """
        job = await self._authorize_job(job_id, actor)
        assessment = await self._load_assignable_assessment(
            body.assessment_id, job.id,
        )
        return await self._assign_many(
            job, assessment, body.application_ids, body.scheduled_for, actor,
            created_new_assessment=False,
        )

    async def create_and_assign_to_job_applicants(
        self,
        job_id: uuid.UUID,
        body: JobAssessmentCreateAndAssignRequest,
        actor: User,
    ) -> JobAssessmentAssignResult:
        """Author one assessment for a job and assign it to several applicants.

        The assessment is created once, scoped to the job in the path (never a
        client-supplied ``job_id``), and then assigned to every eligible selected
        candidate through the same :meth:`_assign_many` the existing-assessment
        path uses, so both entry points produce identical assignments.
        """
        job = await self._authorize_job(job_id, actor)
        assessment = await self.assessment_service.create_assessment(
            recruiter_id=actor.id,
            req=body.to_create_request(job.id),
        )
        return await self._assign_many(
            job, assessment, body.application_ids, body.scheduled_for, actor,
            created_new_assessment=True,
        )

    async def _authorize_job(self, job_id: uuid.UUID, actor: User) -> Job:
        """Resolve a job and require staff access, in this module's error vocabulary.

        Delegates to the shared :func:`authorize_job_access` (the job's owner, or an
        active staff member of its organization), so job scoping keeps one
        implementation, then re-raises into the ``NotFoundError`` / ``ForbiddenError``
        this module already uses so the global handlers emit the same 404/403 the
        rest of the assessment API emits.
        """
        try:
            return await authorize_job_access(self.session, job_id, actor)
        except JobNotFoundError as exc:
            raise NotFoundError("Job not found") from exc
        except JobAccessDeniedError as exc:
            raise ForbiddenError(
                "You do not have access to this job",
                extra={"job_id": str(job_id)},
            ) from exc

    async def _assign_many(
        self,
        job: Job,
        assessment: Assessment,
        application_ids: list[uuid.UUID],
        scheduled_for: datetime | None,
        actor: User,
        *,
        created_new_assessment: bool,
    ) -> JobAssessmentAssignResult:
        """Assign one assessment to a set of a job's applications, per candidate.

        Every requested candidate gets exactly one outcome row and the whole batch
        shares the request's transaction. A candidate is *assigned* when they
        belong to this job, are past the pre-assessment gate, have attempts left
        and hold no live attempt at this assessment; *already_assigned* when a live
        attempt already exists; *skipped* with a reason otherwise. An application
        id that is not this job's is reported as ``not_an_applicant`` rather than
        failing the batch, and nothing here changes an application status.

        The set queries are batched (applications, names, live attempts, per-
        candidate usage) so a 200-candidate batch is a fixed number of reads rather
        than 4N.
        """
        # De-duplicated and ordered: naming the same application twice is one
        # attempt, not two, and the response stays correlated with the request.
        unique_ids = list(dict.fromkeys(application_ids))

        applications = {
            app.id: app
            for app in (await self.session.execute(
                select(JobApplication)
                .where(JobApplication.job_id == job.id)
                .where(JobApplication.id.in_(unique_ids))
            )).scalars().all()
        }

        candidate_ids = [app.candidate_id for app in applications.values()]
        names: dict[uuid.UUID, str] = {}
        if candidate_ids:
            names = {
                user.id: user.full_name
                for user in (await self.session.execute(
                    select(User).where(User.id.in_(candidate_ids))
                )).scalars().all()
            }

        # Live attempts already holding this assessment on these applications.
        live_by_app: dict[uuid.UUID, CandidateAssessment] = {}
        if applications:
            holding = (await self.session.execute(
                select(CandidateAssessment)
                .where(CandidateAssessment.application_id.in_(list(applications.keys())))
                .where(CandidateAssessment.assessment_id == assessment.id)
            )).scalars().all()
            for attempt in holding:
                if attempt.status not in AttemptStatus.finished():
                    live_by_app[attempt.application_id] = attempt

        # Each candidate's overall usage of this assessment, for the attempt-limit
        # check and the next attempt number, in one grouped query.
        used: dict[uuid.UUID, int] = {}
        highest: dict[uuid.UUID, int] = {}
        if candidate_ids:
            for candidate_id, count, max_number in (await self.session.execute(
                select(
                    CandidateAssessment.candidate_id,
                    func.count(),
                    func.max(CandidateAssessment.attempt_number),
                )
                .where(CandidateAssessment.assessment_id == assessment.id)
                .where(CandidateAssessment.candidate_id.in_(candidate_ids))
                .group_by(CandidateAssessment.candidate_id)
            )).all():
                used[candidate_id] = int(count or 0)
                highest[candidate_id] = int(max_number or 0)

        allowed = int(assessment.allowed_attempts)
        now = datetime.now(timezone.utc)
        link = candidate_take_link(assessment.id)
        items: list[JobAssessmentAssignItem] = []

        for application_id in unique_ids:
            app = applications.get(application_id)
            if app is None:
                items.append(JobAssessmentAssignItem(
                    application_id=application_id,
                    outcome=OUTCOME_SKIPPED,
                    reason=REASON_NOT_AN_APPLICANT,
                    assessment_id=assessment.id,
                    assessment_title=assessment.title,
                    message="This candidate has not applied to this job.",
                ))
                continue

            status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
            blocked = self._assignment_block_reason(status, status in TERMINAL_STATUSES)
            if blocked is not None:
                items.append(JobAssessmentAssignItem(
                    application_id=app.id,
                    candidate_id=app.candidate_id,
                    candidate_name=names.get(app.candidate_id),
                    outcome=OUTCOME_SKIPPED,
                    reason=blocked,
                    assessment_id=assessment.id,
                    assessment_title=assessment.title,
                    message=self._skip_message(blocked),
                ))
                continue

            live = live_by_app.get(app.id)
            if live is not None:
                items.append(JobAssessmentAssignItem(
                    application_id=app.id,
                    candidate_id=app.candidate_id,
                    candidate_name=names.get(app.candidate_id),
                    outcome=OUTCOME_ALREADY_ASSIGNED,
                    attempt_id=live.id,
                    assessment_id=assessment.id,
                    assessment_title=assessment.title,
                    scheduled_for=_aware(live.scheduled_for),
                    assessment_link=resolve_take_link(
                        live.assessment_link, live.assessment_id,
                    ),
                    message=(
                        f"{assessment.title} is already assigned to this candidate."
                    ),
                ))
                continue

            if allowed - used.get(app.candidate_id, 0) < 1:
                items.append(JobAssessmentAssignItem(
                    application_id=app.id,
                    candidate_id=app.candidate_id,
                    candidate_name=names.get(app.candidate_id),
                    outcome=OUTCOME_SKIPPED,
                    reason=REASON_NO_ATTEMPTS_REMAINING,
                    assessment_id=assessment.id,
                    assessment_title=assessment.title,
                    message=(
                        "This candidate has already used every allowed attempt "
                        "for this assessment."
                    ),
                ))
                continue

            attempt = CandidateAssessment(
                application_id=app.id,
                assessment_id=assessment.id,
                candidate_id=app.candidate_id,
                attempt_number=highest.get(app.candidate_id, 0) + 1,
                status=AttemptStatus.ASSIGNED.value,
                assigned_by=actor.id,
                assigned_at=now,
                scheduled_for=_utc(scheduled_for),
                assessment_link=link,
                question_order=None,
                integrity_events=[],
                current_index=0,
            )
            self.session.add(attempt)
            await self.session.flush()

            # A candidate is assigned at most once per batch, but the tallies are
            # kept current anyway so a future duplicate could never reuse a number.
            used[app.candidate_id] = used.get(app.candidate_id, 0) + 1
            highest[app.candidate_id] = attempt.attempt_number

            await self.audit.log(
                AuditEventType.ASSESSMENT_ASSIGNED,
                action="bulk_assign_assessment",
                user_id=actor.id,
                organization_id=job.organization_id,
                resource_type="job_application",
                resource_id=str(app.id),
                details={
                    "attempt_id": str(attempt.id),
                    "assessment_id": str(assessment.id),
                    "assessment_title": assessment.title,
                    "candidate_id": str(app.candidate_id),
                    "job_id": str(job.id),
                    "batch_size": len(unique_ids),
                    **(
                        {"scheduled_for": _utc(scheduled_for).isoformat()}
                        if scheduled_for is not None else {}
                    ),
                },
            )

            items.append(JobAssessmentAssignItem(
                application_id=app.id,
                candidate_id=app.candidate_id,
                candidate_name=names.get(app.candidate_id),
                outcome=OUTCOME_ASSIGNED,
                attempt_id=attempt.id,
                assessment_id=assessment.id,
                assessment_title=assessment.title,
                scheduled_for=_utc(scheduled_for),
                assessment_link=link,
                message=(
                    f"{assessment.title} has been assigned to this candidate."
                ),
            ))

        return JobAssessmentAssignResult(
            job_id=job.id,
            job_title=job.title,
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            created_new_assessment=created_new_assessment,
            requested_count=len(unique_ids),
            assigned_count=sum(
                1 for item in items if item.outcome == OUTCOME_ASSIGNED
            ),
            already_assigned_count=sum(
                1 for item in items if item.outcome == OUTCOME_ALREADY_ASSIGNED
            ),
            skipped_count=sum(
                1 for item in items if item.outcome == OUTCOME_SKIPPED
            ),
            items=items,
        )

    @staticmethod
    def _skip_message(reason: str | None) -> str:
        """A candidate-facing-safe sentence for a skipped row.

        Mirrors the eligibility vocabulary so the recruiter sees *why* the same way
        the single-application options endpoint reports it. No exception text and
        no internal identifier.
        """
        if reason == REASON_APPLICATION_FINAL:
            return (
                "This application is already finalized, so it cannot be assigned "
                "an assessment."
            )
        if reason == REASON_APPLICATION_NOT_ELIGIBLE:
            return (
                "This candidate must be shortlisted before an assessment can be "
                "assigned."
            )
        return "This candidate cannot be assigned this assessment."
