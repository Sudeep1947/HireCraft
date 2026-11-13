"""Phase 11 application-driven interview integration.

Connects the existing Interview Intelligence system to the application-centric
hiring workflow, so an interview is scheduled *from an application* and its
evidence lives on that application instead of being re-discovered by matching a
candidate against a job.

Design notes:

- **The application is the only input.** The job, candidate, recruiter and
  organization are derived from the ``application_id`` in the path. No method
  here accepts a client-supplied job or candidate id, so a recruiter cannot
  schedule an interview against somebody else's application or another tenant's
  job. ``(job_id, candidate_id)`` is never trusted from the request; it is read
  off the loaded application row.

- **Authorization is the existing one.** Staff access is resolved through
  :meth:`ApplicationLifecycleService.authorize_staff_access`, the same
  job-owner-or-active-org-staff rule the decision endpoints use, and candidate
  access through ``authorize_application_ownership``. A recruiter from another
  organization gets a 403, not an empty result. An interview id is always looked
  up *scoped to the application*, so an interview from another application can
  never be read or mutated through this service.

- **The lifecycle service stays authoritative.** Scheduling drives
  ``SHORTLISTED -> INTERVIEW_SCHEDULED`` and completion drives
  ``INTERVIEW_SCHEDULED -> INTERVIEWED`` through
  :meth:`ApplicationLifecycleService.transition_application`, which owns the
  transition table, the compare-and-swap update, the immutable history row and
  the status audit event. This service never writes a status directly.

- **No automated hiring decision.** Interview scores, evaluations and
  scorecard recommendations are evidence only. Nothing in this module selects,
  rejects or ranks a candidate, and ``INTERVIEWED`` is a factual stage. Final
  selection stays with the Phase 8 decision endpoints and the recruiter.

- **Cancellation does not move the application.** A cancelled interview leaves
  the application at ``INTERVIEW_SCHEDULED``, because cancelling is not a
  decision about the candidate: the recruiter reschedules the same interview
  (which reuses the row and its questions) or takes a separate, explicit
  action. Silently dropping the application back to ``SHORTLISTED`` would
  contradict the candidate's own timeline, and rejecting is explicitly not this
  module's call to make.

- **Reuse, not duplication.** Questions, evaluation, scorecards and mock
  sessions all come from :class:`InterviewService` and its engines. This module
  adds the application link, the affordance projection, the candidate-safe view
  and the audit records.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.application_decision_schemas import (
    ApplicationDecisionCreate,
    candidate_status_message,
)
from app.domain.application_interview_schemas import (
    REASON_ALREADY_ADVANCED,
    REASON_ALREADY_SCHEDULED,
    REASON_HR_ALREADY_SCHEDULED,
    REASON_INTERVIEW_FINAL,
    REASON_NOT_ADVANCED,
    REASON_NOT_SHORTLISTED,
    REASON_RECRUITER_INTERVIEW_INCOMPLETE,
    REASON_TERMINAL,
    SCHEDULABLE_FROM,
    ApplicationInterviewActionOption,
    ApplicationInterviewAdvanceRequest,
    ApplicationInterviewCancelRequest,
    ApplicationInterviewCompleteRequest,
    ApplicationInterviewEvidence,
    ApplicationInterviewFeedback,
    ApplicationInterviewFeedbackRequest,
    ApplicationInterviewOptions,
    ApplicationInterviewRejectRequest,
    ApplicationInterviewRescheduleRequest,
    ApplicationInterviewScheduleRequest,
    ApplicationInterviewScheduleResult,
    ApplicationInterviewStageActionResult,
    ApplicationInterviewSummary,
    CandidateApplicationInterviewView,
    HRInterviewerOption,
)
from app.domain.enums import (
    ApplicationDecisionType,
    ApplicationStatus,
    AuditEventType,
    HiringRecommendation,
    InterviewStage,
    InterviewStatus,
    InterviewType,
)
from app.domain.models import Interview, Job, JobApplication, OrganizationMembership, User
from app.repositories.interview.interview import (
    InterviewRepository,
    InterviewScorecardRepository,
)
from app.services.applications.application_decision_service import (
    ApplicationDecisionService,
)
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
    STAFF_TRANSITIONS,
    TERMINAL_STATUSES,
)
from app.services.audit_service import AuditService
from app.services.interview.interview_service import InterviewService
from app.services.screening.access import authorize_application_ownership

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")

# What may be done to an interview in each state.
#
# One table, read by both the affordance projection and the mutating methods, so
# the UI can never offer an action the service would reject, nor hide one it
# would allow. The three sets differ on purpose:
#
# - A cancelled interview can be rescheduled, which reopens the same row and its
#   questions rather than creating a second interview for the application.
# - It cannot be cancelled again (it already is) and cannot be completed,
#   because nothing was held.
# - An in-progress interview is completable: it is the normal end state of an
#   interview that was started, and refusing to complete it would leave the
#   application stuck at INTERVIEW_SCHEDULED with no way forward.
# - A completed interview is immutable. Its questions, answers and evaluations
#   are evidence, so reopening one would rewrite history.
_RESCHEDULABLE_STATUSES = frozenset(
    {InterviewStatus.SCHEDULED, InterviewStatus.IN_PROGRESS, InterviewStatus.CANCELLED},
)
_CANCELLABLE_STATUSES = frozenset(
    {InterviewStatus.SCHEDULED, InterviewStatus.IN_PROGRESS},
)
_COMPLETABLE_STATUSES = frozenset(
    {InterviewStatus.SCHEDULED, InterviewStatus.IN_PROGRESS},
)


class ApplicationInterviewIntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lifecycle = ApplicationLifecycleService(session)
        self.decisions = ApplicationDecisionService(session)
        self.interviews = InterviewService(session)
        self.interview_repo = InterviewRepository(session)
        self.scorecard_repo = InterviewScorecardRepository(session)
        self.audit = AuditService(session)

    # ── Reads ───────────────────────────────────────────────────────

    async def get_evidence(
        self, application_id: uuid.UUID, actor: User,
    ) -> ApplicationInterviewEvidence:
        """Return the interview evidence for an application, staff-only.

        Raises ``NotFoundError`` for an unknown application and ``ForbiddenError``
        when ``actor`` has no staff access, so a cross-tenant caller cannot
        distinguish "does not exist" from "not yours" for a job they can see.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        interviews = await self.interview_repo.list_by_application(application_id)

        # Batch-fetch recruiter/interviewer records to avoid lazy-loading MissingGreenlet
        recruiter_ids = {iv.recruiter_id for iv in interviews if iv.recruiter_id}
        recruiters_by_id: dict[uuid.UUID, User] = {}
        if recruiter_ids:
            recruiter_stmt = select(User).where(User.id.in_(recruiter_ids))
            res = await self.session.execute(recruiter_stmt)
            for u in res.scalars():
                recruiters_by_id[u.id] = u

        summaries: list[ApplicationInterviewSummary] = []
        scores: list[int] = []
        for interview in interviews:
            scorecard = await self.scorecard_repo.get_by_interview(interview.id)
            # A scorecard can be filed against a scheduled interview, so the
            # average is restricted to completed ones, as the contract promises.
            # Otherwise an interview nobody has taken yet would drag it down.
            if (
                scorecard is not None
                and interview.status == InterviewStatus.COMPLETED.value
            ):
                scores.append(scorecard.overall_score)
            recruiter_user = recruiters_by_id.get(interview.recruiter_id) if interview.recruiter_id else None
            recruiter_name = recruiter_user.full_name if recruiter_user else None
            summaries.append(self._to_summary(interview, scorecard, recruiter_name=recruiter_name))

        candidate = await self.session.get(User, app.candidate_id)
        return ApplicationInterviewEvidence(
            application_id=app.id,
            job_id=app.job_id,
            job_title=job.title if job else "",
            candidate_id=app.candidate_id,
            candidate_name=candidate.full_name if candidate else "",
            application_status=ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED,
            interview_count=len(summaries),
            completed_count=sum(
                1 for iv in interviews
                if iv.status == InterviewStatus.COMPLETED.value
            ),
            average_overall_score=(
                round(sum(scores) / len(scores), 1) if scores else None
            ),
            interviews=summaries,
            hr_eligible=app.advanced_to_hr_at is not None,
            advanced_to_hr_at=app.advanced_to_hr_at,
        )

    async def get_options(
        self, application_id: uuid.UUID, actor: User,
    ) -> ApplicationInterviewOptions:
        """Server-authoritative interview affordances for one application.

        The UI renders this instead of re-implementing the rules, so an action
        the backend would reject is never offered in the first place.
        """
        app, _ = await self.lifecycle.authorize_staff_access(application_id, actor)
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        interviews = await self.interview_repo.list_by_application(application_id)
        active = await self.interview_repo.get_active_by_application(application_id)

        is_final = status in TERMINAL_STATUSES
        schedule_reason = self._schedule_block_reason(status, is_final, active)
        can_schedule = schedule_reason is None

        # Phase 15 stage affordances. ``recruiter_stage_complete`` reads the
        # linked interviews, so advancing waits for an actual completed
        # recruiter-round interview rather than for a status alone.
        hr_eligible = app.advanced_to_hr_at is not None
        recruiter_stage_complete = any(
            iv.status == InterviewStatus.COMPLETED.value
            and (InterviewStage.from_value(iv.stage) or InterviewStage.RECRUITER)
            is InterviewStage.RECRUITER
            for iv in interviews
        )
        advance_reason = self._advance_block_reason(
            is_final, hr_eligible, recruiter_stage_complete,
        )
        schedule_hr_reason = self._schedule_hr_block_reason(
            status, is_final, hr_eligible, active,
        )
        reject_reason = self._reject_block_reason(status, is_final)

        options: list[ApplicationInterviewActionOption] = []
        for interview in interviews:
            interview_status = InterviewStatus.from_value(interview.status)
            # An unrecognized stored status is treated as finished: unknown states
            # are not offered any action, rather than guessing.
            can_reschedule, can_cancel, can_complete = self._allowed_actions(
                interview_status,
            )
            options.append(
                ApplicationInterviewActionOption(
                    interview_id=interview.id,
                    status=interview_status or InterviewStatus.COMPLETED,
                    can_reschedule=can_reschedule,
                    reschedule_unavailable_reason=(
                        None if can_reschedule else REASON_INTERVIEW_FINAL
                    ),
                    can_cancel=can_cancel,
                    cancel_unavailable_reason=(
                        None if can_cancel else REASON_INTERVIEW_FINAL
                    ),
                    can_complete=can_complete,
                    complete_unavailable_reason=(
                        None if can_complete else REASON_INTERVIEW_FINAL
                    ),
                )
            )

        return ApplicationInterviewOptions(
            application_id=app.id,
            current_status=status,
            status_is_final=is_final,
            can_schedule=can_schedule,
            schedule_unavailable_reason=schedule_reason,
            has_interviews=bool(interviews),
            active_interview_id=active.id if active else None,
            hr_eligible=hr_eligible,
            recruiter_stage_complete=recruiter_stage_complete,
            can_advance=advance_reason is None,
            advance_unavailable_reason=advance_reason,
            can_schedule_hr=schedule_hr_reason is None,
            schedule_hr_unavailable_reason=schedule_hr_reason,
            can_reject=reject_reason is None,
            reject_unavailable_reason=reject_reason,
            options=options,
        )

    async def get_candidate_view(
        self, application_id: uuid.UUID, candidate: User,
    ) -> CandidateApplicationInterviewView:
        """Return the candidate-safe interview projection for an application.

        An explicit allowlist: no scorecard, no evaluation, no recommendation, no
        recruiter identity or notes, no fairness data. Ownership is resolved
        through ``authorize_application_ownership``, which raises the identical
        error for "not yours" and "does not exist" so application ids cannot be
        probed.
        """
        app = await authorize_application_ownership(
            self.session, application_id, candidate,
        )
        job = await self.session.get(Job, app.job_id)
        job_title = job.title if job else ""
        interviews = await self.interview_repo.list_by_application(application_id)

        upcoming = [
            iv for iv in interviews
            if iv.status in (InterviewStatus.SCHEDULED.value, InterviewStatus.IN_PROGRESS.value)
        ]
        # Prefer the next interview still to attend; otherwise the most recent
        # one, so the card stays populated after the interview happens.
        focus = upcoming[0] if upcoming else (interviews[-1] if interviews else None)
        has_completed = any(
            iv.status == InterviewStatus.COMPLETED.value for iv in interviews
        )

        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        return CandidateApplicationInterviewView(
            application_id=app.id,
            interview_id=focus.id if focus else None,
            status=focus.status if focus else None,
            scheduled_at=focus.scheduled_at if focus else None,
            duration_minutes=focus.duration_minutes if focus else None,
            completed_at=focus.completed_at if focus else None,
            next_upcoming_at=upcoming[0].scheduled_at if upcoming else None,
            has_completed=has_completed,
            interview_count=len(interviews),
            message=candidate_status_message(
                status, job_title, reason=None,
            ),
        )

    # ── Writes ──────────────────────────────────────────────────────

    async def schedule(
        self,
        application_id: uuid.UUID,
        body: ApplicationInterviewScheduleRequest,
        actor: User,
    ) -> ApplicationInterviewScheduleResult:
        """Schedule an interview for an application and advance its status.

        Idempotent in the sense that matters: a second request while an interview
        is still scheduled or in progress is rejected with a 409 rather than
        creating a duplicate interview, so a double-click or a retried request
        cannot produce two live interviews for one application.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        if not job:
            raise NotFoundError("Job not found")

        stage = body.stage if body.stage is not None else InterviewStage.RECRUITER
        is_hr = stage is InterviewStage.HR

        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        if status in TERMINAL_STATUSES:
            raise ConflictError(
                "This application is finalized and cannot be scheduled",
                extra={"application_id": str(application_id), "status": status.value},
            )

        active = await self.interview_repo.get_active_by_application(application_id)
        if active is not None:
            raise ConflictError(
                "This application already has an interview that is scheduled or "
                "in progress",
                extra={
                    "application_id": str(application_id),
                    "interview_id": str(active.id),
                },
            )

        interviewer_to_assign = actor.id
        if is_hr:
            # A second-round interview is only permitted once the recruiter has
            # advanced the candidate. Advancing records eligibility; it does not
            # choose a time, so the schedule still has to be supplied here.
            if app.advanced_to_hr_at is None:
                raise ConflictError(
                    "The candidate must be advanced to the HR stage before an HR "
                    "interview can be scheduled",
                    extra={"application_id": str(application_id)},
                )
            if body.interviewer_id is not None:
                interviewer_user = await self.session.get(User, body.interviewer_id)
                if interviewer_user is None:
                    raise NotFoundError(
                        "Assigned HR interviewer not found",
                        extra={"interviewer_id": str(body.interviewer_id)},
                    )
                interviewer_to_assign = interviewer_user.id
        elif status not in SCHEDULABLE_FROM:
            raise ConflictError(
                "An interview can only be scheduled for a shortlisted application",
                extra={
                    "application_id": str(application_id),
                    "status": status.value,
                },
            )

        # The interview is created before any status flips so that a rejected
        # transition cannot leave a schedule attached to an application that was
        # never moved. All writes share the caller's transaction, so a failure in
        # either rolls both back.
        interview = await self.interviews.schedule_interview(
            job_id=app.job_id,
            candidate_id=app.candidate_id,
            recruiter_id=interviewer_to_assign,
            scheduled_at=body.scheduled_at,
            duration_minutes=body.duration_minutes,
            categories=body.categories,
            difficulty=body.difficulty,
            question_count=body.question_count,
            application_id=app.id,
            stage=stage.value,
        )

        if body.notes:
            existing_sc = await self.scorecard_repo.get_by_interview(interview.id)
            if existing_sc is not None:
                await self.scorecard_repo.update(existing_sc.id, recruiter_notes=body.notes)
            else:
                await self.scorecard_repo.create(
                    interview_id=interview.id,
                    recruiter_notes=body.notes,
                )

        previous_status = status
        application_status_changed = False
        if not is_hr:
            # A first-round interview advances the application to
            # INTERVIEW_SCHEDULED. An HR round deliberately does not: the
            # candidate is already past that stage, and forcing the status
            # backwards would contradict their own timeline.
            await self.lifecycle.transition_application(
                application_id,
                ApplicationStatus.INTERVIEW_SCHEDULED.value,
                actor,
                reason="Interview scheduled",
                metadata={"interview_id": str(interview.id), "stage": stage.value},
            )
            application_status_changed = True
            result_status = ApplicationStatus.INTERVIEW_SCHEDULED
        else:
            result_status = status

        await self._audit_interview(
            AuditEventType.INTERVIEW_SCHEDULED,
            action="interview_scheduled",
            interview=interview,
            app=app,
            job=job,
            actor=actor,
            details={
                "scheduled_at": body.scheduled_at.isoformat(),
                "duration_minutes": body.duration_minutes,
                "question_count": body.question_count,
                "difficulty": body.difficulty,
                "categories": list(body.categories),
                "stage": stage.value,
                "previous_application_status": previous_status.value,
            },
        )
        await self.session.flush()

        return ApplicationInterviewScheduleResult(
            application_id=app.id,
            interview_id=interview.id,
            interview_status=InterviewStatus.SCHEDULED,
            application_status=result_status,
            application_status_changed=application_status_changed,
            message=(
                "HR interview scheduled successfully"
                if is_hr
                else "Interview scheduled successfully"
            ),
        )

    async def reschedule(
        self,
        application_id: uuid.UUID,
        interview_id: uuid.UUID,
        body: ApplicationInterviewRescheduleRequest,
        actor: User,
    ) -> ApplicationInterviewScheduleResult:
        """Move a scheduled interview to a new time, keeping its records.

        The existing interview row is reused so its generated questions and any
        answers/evaluations survive the change, and so history shows one
        interview that moved rather than two interviews.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        interview = await self._require_linked_interview(application_id, interview_id)
        interview_status = InterviewStatus.from_value(interview.status)

        can_reschedule, _, _ = self._allowed_actions(interview_status)
        if not can_reschedule:
            raise ConflictError(
                "This interview has already finished and can no longer be moved",
                extra={
                    "interview_id": str(interview.id),
                    "status": interview.status,
                },
            )

        previous_time = interview.scheduled_at
        previous_duration = interview.duration_minutes
        previous_status = interview_status
        interview.scheduled_at = body.scheduled_at
        # Phase 15: mark the move so the room can tell "rescheduled and waiting"
        # from a first schedule. Set only on an explicit reschedule and never
        # cleared by anything else.
        interview.rescheduled_at = datetime.now(timezone.utc)
        if body.duration_minutes is not None:
            interview.duration_minutes = body.duration_minutes
        # Rescheduling a cancelled interview reopens it on the same row, so its
        # generated questions are reused instead of a second interview being
        # created for this application.
        reopened = previous_status is InterviewStatus.CANCELLED
        if reopened:
            interview.status = InterviewStatus.SCHEDULED.value

        await self._audit_interview(
            AuditEventType.INTERVIEW_RESCHEDULED,
            action="interview_rescheduled",
            interview=interview,
            app=app,
            job=job,
            actor=actor,
            details={
                "previous_scheduled_at": (
                    previous_time.isoformat() if previous_time else None
                ),
                "scheduled_at": body.scheduled_at.isoformat(),
                "previous_duration_minutes": previous_duration,
                "duration_minutes": interview.duration_minutes,
                "previous_interview_status": (
                    previous_status.value if previous_status else None
                ),
                "reopened_from_cancelled": reopened,
            },
        )
        await self.session.flush()

        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        return ApplicationInterviewScheduleResult(
            application_id=app.id,
            interview_id=interview.id,
            interview_status=InterviewStatus.from_value(interview.status)
            or InterviewStatus.SCHEDULED,
            application_status=status,
            # Rescheduling is a change to the interview only. The application
            # stays at INTERVIEW_SCHEDULED, including when a cancellation is
            # undone, because it never left that stage.
            application_status_changed=False,
            message=(
                "Interview rescheduled successfully"
                if not reopened
                else "Interview reopened and rescheduled"
            ),
        )

    async def cancel(
        self,
        application_id: uuid.UUID,
        interview_id: uuid.UUID,
        body: ApplicationInterviewCancelRequest,
        actor: User,
    ) -> ApplicationInterviewScheduleResult:
        """Cancel a scheduled interview.

        Deliberately leaves the application at ``INTERVIEW_SCHEDULED``: a
        cancellation is not a decision about the candidate. The recruiter
        reschedules the same interview or acts separately, and no rejection is
        inferred from a cancellation.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        interview = await self._require_linked_interview(application_id, interview_id)
        interview_status = InterviewStatus.from_value(interview.status)

        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        if interview_status is InterviewStatus.CANCELLED:
            # Idempotent: cancelling an already-cancelled interview is a no-op
            # rather than an error, so a retried request is safe.
            return ApplicationInterviewScheduleResult(
                application_id=app.id,
                interview_id=interview.id,
                interview_status=InterviewStatus.CANCELLED,
                application_status=status,
                application_status_changed=False,
                message="Interview is already cancelled",
            )

        _, can_cancel, _ = self._allowed_actions(interview_status)
        if not can_cancel:
            raise ConflictError(
                "This interview can no longer be cancelled",
                extra={
                    "interview_id": str(interview.id),
                    "status": interview.status,
                },
            )

        interview.status = InterviewStatus.CANCELLED.value

        await self._audit_interview(
            AuditEventType.INTERVIEW_CANCELLED,
            action="interview_cancelled",
            interview=interview,
            app=app,
            job=job,
            actor=actor,
            details={
                "previous_interview_status": (
                    interview_status.value if interview_status else None
                ),
                # Internal only: never forwarded to the candidate notification.
                "reason": body.reason,
            },
        )
        await self.session.flush()

        return ApplicationInterviewScheduleResult(
            application_id=app.id,
            interview_id=interview.id,
            interview_status=InterviewStatus.CANCELLED,
            application_status=status,
            application_status_changed=False,
            message="Interview cancelled",
        )

    async def complete(
        self,
        application_id: uuid.UUID,
        interview_id: uuid.UUID,
        body: ApplicationInterviewCompleteRequest,
        actor: User,
    ) -> ApplicationInterviewScheduleResult:
        """Mark an interview completed and record the INTERVIEWED stage.

        This is a factual record that the interview happened, triggered by a
        recruiter. No score, evaluation or recommendation is read here, and none
        can influence the outcome: the application simply advances one stage and
        the recruiter decides what it means.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        interview = await self._require_linked_interview(application_id, interview_id)
        interview_status = InterviewStatus.from_value(interview.status)

        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        if interview_status is InterviewStatus.COMPLETED:
            return ApplicationInterviewScheduleResult(
                application_id=app.id,
                interview_id=interview.id,
                interview_status=InterviewStatus.COMPLETED,
                application_status=status,
                application_status_changed=False,
                message="Interview is already completed",
            )
        if interview_status is InterviewStatus.CANCELLED:
            raise ConflictError(
                "A cancelled interview cannot be completed; reschedule it or "
                "schedule a new one",
                extra={"interview_id": str(interview.id)},
            )

        _, _, can_complete = self._allowed_actions(interview_status)
        if not can_complete:
            raise ConflictError(
                "This interview cannot be completed from its current state",
                extra={
                    "interview_id": str(interview.id),
                    "status": interview.status,
                },
            )

        completed_at = body.completed_at or datetime.now(timezone.utc)
        interview.completed_at = completed_at
        interview.status = InterviewStatus.COMPLETED.value

        # Advance the application only when the lifecycle actually permits it.
        # If a recruiter has already moved on (e.g. to offered/rejected) the
        # interview completion is still recorded; the status is left alone
        # rather than forced backwards by an interview action.
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        status_changed = False
        if status == ApplicationStatus.INTERVIEW_SCHEDULED:
            await self.lifecycle.transition_application(
                application_id,
                ApplicationStatus.INTERVIEWED.value,
                actor,
                reason="Interview completed",
                metadata={"interview_id": str(interview.id)},
            )
            status_changed = True
            status = ApplicationStatus.INTERVIEWED

        await self._audit_interview(
            AuditEventType.INTERVIEW_COMPLETED,
            action="interview_completed",
            interview=interview,
            app=app,
            job=job,
            actor=actor,
            details={
                "completed_at": completed_at.isoformat(),
                "questions_answered": interview.questions_answered,
                "total_questions": interview.total_questions,
                "application_status_after": status.value,
            },
        )
        await self.session.flush()

        return ApplicationInterviewScheduleResult(
            application_id=app.id,
            interview_id=interview.id,
            interview_status=InterviewStatus.COMPLETED,
            application_status=status,
            application_status_changed=status_changed,
            message="Interview completed successfully",
        )

    # ── Internals ───────────────────────────────────────────────────

    async def save_feedback(
        self,
        application_id: uuid.UUID,
        interview_id: uuid.UUID,
        body: ApplicationInterviewFeedbackRequest,
        actor: User,
    ) -> ApplicationInterviewFeedback:
        """Record the recruiter's/interviewer's manual feedback for an interview.

        Stored on the existing ``InterviewScorecard`` for the interview (one per
        interview, upserted) rather than a new store, so the manual judgement and
        the automated evaluation live on the same staff artifact. The ratings
        are written verbatim -- this is their assessment, not a recomputation --
        and no score here can reach the lifecycle: selection and rejection remain
        separate, explicit actions.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        interview = await self._require_linked_interview(application_id, interview_id)

        ratings = [body.technical_skills, body.communication, body.problem_solving]
        if body.teamwork is not None:
            ratings.append(body.teamwork)
        if body.leadership is not None:
            ratings.append(body.leadership)
        if body.culture_fit is not None:
            ratings.append(body.culture_fit)

        overall = (
            body.overall_score
            if body.overall_score is not None
            else round(sum(ratings) / len(ratings))
        )

        notes_text = body.recruiter_notes or ""
        if body.strengths or body.concerns:
            parts = []
            if body.strengths:
                parts.append(f"Strengths: {body.strengths}")
            if body.concerns:
                parts.append(f"Concerns: {body.concerns}")
            if notes_text:
                parts.append(f"Notes: {notes_text}")
            notes_text = "\n\n".join(parts)

        values = {
            "technical_skills": body.technical_skills,
            "communication": body.communication,
            "problem_solving": body.problem_solving,
            "teamwork": body.teamwork if body.teamwork is not None else 0,
            "leadership": body.leadership if body.leadership is not None else 0,
            "culture_fit": body.culture_fit if body.culture_fit is not None else 0,
            "overall_score": overall,
            "hiring_confidence": body.hiring_confidence,
            "recommendation": body.recommendation.value,
            "recruiter_notes": notes_text,
        }

        existing = await self.scorecard_repo.get_by_interview(interview_id)
        if existing is not None:
            scorecard = await self.scorecard_repo.update(existing.id, **values)
        else:
            scorecard = await self.scorecard_repo.create(
                interview_id=interview_id, **values,
            )

        organization_id = job.organization_id if job else None
        await self.audit.log(
            event_type=AuditEventType.INTERVIEW_FEEDBACK_RECORDED,
            action="interview_feedback_recorded",
            user_id=actor.id,
            organization_id=organization_id,
            resource_type="interview",
            resource_id=str(interview.id),
            details={
                "application_id": str(app.id),
                "job_id": str(app.job_id),
                "candidate_id": str(app.candidate_id),
                "stage": interview.stage,
                "overall_score": overall,
                "recommendation": body.recommendation.value,
            },
        )
        await self.session.flush()
        return self._to_feedback(interview, scorecard)

    async def get_feedback(
        self,
        application_id: uuid.UUID,
        interview_id: uuid.UUID,
        actor: User,
    ) -> ApplicationInterviewFeedback:
        """Return the manual feedback recorded for one interview, staff-only."""
        await self.lifecycle.authorize_staff_access(application_id, actor)
        interview = await self._require_linked_interview(application_id, interview_id)
        scorecard = await self.scorecard_repo.get_by_interview(interview_id)
        if scorecard is None:
            raise NotFoundError(
                "No feedback has been recorded for this interview",
                extra={"interview_id": str(interview_id)},
            )
        return self._to_feedback(interview, scorecard)

    async def advance_to_hr(
        self,
        application_id: uuid.UUID,
        body: ApplicationInterviewAdvanceRequest,
        actor: User,
    ) -> ApplicationInterviewStageActionResult:
        """Mark the candidate eligible for an HR interview round.

        Records eligibility and who granted it, and writes an immutable history
        and audit record. It changes no application status, invents no HR
        interview time, creates no room and makes no decision about the
        candidate: the HR interview still has to be scheduled explicitly, and the
        final decision still belongs to the Phase 8 decision endpoints.
        """
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        is_final = status in TERMINAL_STATUSES
        interviews = await self.interview_repo.list_by_application(application_id)
        recruiter_stage_complete = any(
            iv.status == InterviewStatus.COMPLETED.value
            and (InterviewStage.from_value(iv.stage) or InterviewStage.RECRUITER)
            is InterviewStage.RECRUITER
            for iv in interviews
        )
        hr_eligible = app.advanced_to_hr_at is not None

        reason = self._advance_block_reason(
            is_final, hr_eligible, recruiter_stage_complete,
        )
        if reason is not None:
            raise ConflictError(
                self._stage_action_message(reason),
                extra={
                    "application_id": str(application_id),
                    "reason": reason,
                },
            )

        now = datetime.now(timezone.utc)
        app.advanced_to_hr_at = now
        app.advanced_to_hr_by = actor.id

        # A non-transitioning history + audit record: advancing is a deliberate
        # staff decision that does not move the status, written through the same
        # authoritative lifecycle service as every other decision.
        await self.lifecycle.record_review_decision(
            application_id,
            actor,
            decision="advance_to_hr",
            comment=body.note,
            metadata={"advanced_to_hr": True},
        )
        organization_id = job.organization_id if job else None
        await self.audit.log(
            event_type=AuditEventType.APPLICATION_ADVANCED_TO_HR,
            action="application_advanced_to_hr",
            user_id=actor.id,
            organization_id=organization_id,
            resource_type="job_application",
            resource_id=str(application_id),
            details={
                "job_id": str(app.job_id),
                "candidate_id": str(app.candidate_id),
                "status": status.value,
            },
        )
        await self.session.flush()

        return ApplicationInterviewStageActionResult(
            application_id=app.id,
            application_status=status,
            application_status_changed=False,
            hr_eligible=True,
            candidate_message=None,
            message="Candidate advanced to the HR interview stage",
        )

    async def reject(
        self,
        application_id: uuid.UUID,
        body: ApplicationInterviewRejectRequest,
        actor: User,
    ) -> ApplicationInterviewStageActionResult:
        """Reject a candidate from the interview stage.

        Delegates the status change, the structured reason, the immutable history
        and the candidate-safe wording to the Phase 8 decision service, so a
        rejection from the interview panel is the same act as a rejection from the
        decision panel and the two can never diverge. The candidate message comes
        from the single reviewed projection.
        """
        app, _ = await self.lifecycle.authorize_staff_access(application_id, actor)
        status = ApplicationStatus.from_value(app.status) or ApplicationStatus.APPLIED
        reason = self._reject_block_reason(status, status in TERMINAL_STATUSES)
        if reason is not None:
            raise ConflictError(
                self._stage_action_message(reason),
                extra={
                    "application_id": str(application_id),
                    "reason": reason,
                },
            )

        result = await self.decisions.record_decision(
            application_id,
            ApplicationDecisionCreate(
                decision=ApplicationDecisionType.REJECT,
                rejection_reason=body.rejection_reason,
                internal_note=body.internal_note,
            ),
            actor,
        )
        await self.session.flush()

        return ApplicationInterviewStageActionResult(
            application_id=application_id,
            application_status=result.status,
            application_status_changed=result.changed_status,
            hr_eligible=app.advanced_to_hr_at is not None,
            candidate_message=result.candidate_message,
            message="Application rejected",
        )

    @staticmethod
    def _advance_block_reason(
        is_final: bool, hr_eligible: bool, recruiter_stage_complete: bool,
    ) -> str | None:
        if is_final:
            return REASON_TERMINAL
        if hr_eligible:
            return REASON_ALREADY_ADVANCED
        if not recruiter_stage_complete:
            return REASON_RECRUITER_INTERVIEW_INCOMPLETE
        return None

    @staticmethod
    def _schedule_hr_block_reason(
        status: ApplicationStatus,
        is_final: bool,
        hr_eligible: bool,
        active: Interview | None,
    ) -> str | None:
        if is_final:
            return REASON_TERMINAL
        if not hr_eligible:
            return REASON_NOT_ADVANCED
        if active is not None:
            return REASON_HR_ALREADY_SCHEDULED if (
                InterviewStage.from_value(active.stage) is InterviewStage.HR
            ) else REASON_ALREADY_SCHEDULED
        return None

    @staticmethod
    def _reject_block_reason(
        status: ApplicationStatus, is_final: bool,
    ) -> str | None:
        if is_final:
            return REASON_TERMINAL
        if ApplicationStatus.REJECTED not in STAFF_TRANSITIONS.get(status, set()):
            return REASON_TERMINAL
        return None

    @staticmethod
    def _stage_action_message(reason: str) -> str:
        return {
            REASON_TERMINAL: "This application is finalized and cannot be changed",
            REASON_ALREADY_ADVANCED: (
                "This candidate has already been advanced to the HR stage"
            ),
            REASON_RECRUITER_INTERVIEW_INCOMPLETE: (
                "The recruiter interview must be completed before advancing to HR"
            ),
            REASON_NOT_ADVANCED: (
                "The candidate must be advanced to the HR stage first"
            ),
            REASON_HR_ALREADY_SCHEDULED: (
                "This candidate already has an HR interview scheduled"
            ),
            REASON_ALREADY_SCHEDULED: (
                "This application already has an interview that is scheduled or "
                "in progress"
            ),
        }.get(reason, "This action is not available right now")

    @staticmethod
    def _allowed_actions(
        status: InterviewStatus | None,
    ) -> tuple[bool, bool, bool]:
        """Return ``(can_reschedule, can_cancel, can_complete)`` for a status.

        ``None`` (an unrecognized stored value) permits nothing, so an unexpected
        state cannot be mutated on a guess.
        """
        if status is None:
            return False, False, False
        return (
            status in _RESCHEDULABLE_STATUSES,
            status in _CANCELLABLE_STATUSES,
            status in _COMPLETABLE_STATUSES,
        )

    @staticmethod
    def _schedule_block_reason(
        status: ApplicationStatus,
        is_final: bool,
        active: Interview | None,
    ) -> str | None:
        if is_final:
            return REASON_TERMINAL
        if active is not None:
            return REASON_ALREADY_SCHEDULED
        if status not in SCHEDULABLE_FROM:
            return REASON_NOT_SHORTLISTED
        return None

    async def _require_linked_interview(
        self, application_id: uuid.UUID, interview_id: uuid.UUID,
    ) -> Interview:
        """Load an interview only if it belongs to this application.

        Authorization has already run, so this is a scoping check, not an
        access check. An interview belonging to another application (or one with
        no application at all) is reported as not found on this path, so an
        interview id cannot be used to reach across applications.
        """
        interview = await self.interview_repo.get_by_application(
            application_id, interview_id,
        )
        if interview is None:
            raise NotFoundError(
                "Interview not found for this application",
                extra={
                    "application_id": str(application_id),
                    "interview_id": str(interview_id),
                },
            )
        return interview

    @staticmethod
    def _to_summary(
        interview: Interview,
        scorecard,
        recruiter_name: str | None = None,
    ) -> ApplicationInterviewSummary:
        if recruiter_name is None:
            # Safely check if recruiter relationship is loaded in instance dict without triggering lazy I/O
            state = inspect(interview)
            if "recruiter" in state.dict:
                recruiter_obj = state.dict["recruiter"]
                if recruiter_obj is not None:
                    recruiter_name = getattr(recruiter_obj, "full_name", None)

        return ApplicationInterviewSummary(
            id=interview.id,
            application_id=interview.application_id,
            job_id=interview.job_id,
            candidate_id=interview.candidate_id,
            interview_type=InterviewType.from_value(interview.interview_type) or InterviewType.RECRUITER_SCHEDULED,
            stage=InterviewStage.from_value(interview.stage) or InterviewStage.default(),
            status=interview.status,
            scheduled_at=interview.scheduled_at,
            rescheduled_at=interview.rescheduled_at,
            started_at=interview.started_at,
            completed_at=interview.completed_at,
            duration_minutes=interview.duration_minutes,
            total_questions=interview.total_questions or 0,
            questions_answered=interview.questions_answered or 0,
            has_scorecard=scorecard is not None,
            overall_score=scorecard.overall_score if scorecard else None,
            recommendation=scorecard.recommendation if scorecard else None,
            recruiter_id=interview.recruiter_id,
            recruiter_name=recruiter_name,
            room_id=interview.room_id,
            notes=scorecard.recruiter_notes if scorecard else None,
            created_at=interview.created_at,
        )

    @staticmethod
    def _to_feedback(interview: Interview, scorecard) -> ApplicationInterviewFeedback:
        notes = scorecard.recruiter_notes or ""
        strengths = None
        concerns = None
        if "Strengths: " in notes:
            try:
                part = notes.split("Strengths: ", 1)[1]
                strengths = part.split("\n\n")[0].strip()
            except Exception:
                pass
        if "Concerns: " in notes:
            try:
                part = notes.split("Concerns: ", 1)[1]
                concerns = part.split("\n\n")[0].strip()
            except Exception:
                pass

        return ApplicationInterviewFeedback(
            interview_id=interview.id,
            application_id=interview.application_id,
            technical_skills=scorecard.technical_skills,
            communication=scorecard.communication,
            problem_solving=scorecard.problem_solving,
            teamwork=getattr(scorecard, "teamwork", 0),
            leadership=getattr(scorecard, "leadership", 0),
            culture_fit=getattr(scorecard, "culture_fit", 0),
            overall_score=scorecard.overall_score,
            hiring_confidence=scorecard.hiring_confidence,
            recommendation=(
                HiringRecommendation.from_value(scorecard.recommendation)
                or HiringRecommendation.CONSIDER
            ),
            recruiter_notes=scorecard.recruiter_notes,
            strengths=strengths,
            concerns=concerns,
            created_at=scorecard.created_at,
            updated_at=scorecard.updated_at,
        )

    async def get_hr_interviewers(
        self, application_id: uuid.UUID, actor: User,
    ) -> list[HRInterviewerOption]:
        """List active HR managers / organization staff for the application's organization."""
        app, job = await self.lifecycle.authorize_staff_access(application_id, actor)
        candidates_map: dict[uuid.UUID, HRInterviewerOption] = {}
        if job and job.organization_id:
            query = (
                select(OrganizationMembership, User)
                .join(User, OrganizationMembership.user_id == User.id)
                .where(
                    OrganizationMembership.organization_id == job.organization_id,
                    OrganizationMembership.status == "active",
                    OrganizationMembership.role.in_(["hr_manager", "organization_admin", "owner", "hr"]),
                )
            )
            res = await self.session.execute(query)
            for mem, usr in res.all():
                candidates_map[usr.id] = HRInterviewerOption(
                    id=usr.id,
                    full_name=usr.full_name,
                    email=usr.email,
                    role=mem.role,
                )

        if not candidates_map:
            from app.domain.models import Role, UserRole
            query = (
                select(User, Role.name)
                .join(UserRole, User.id == UserRole.user_id)
                .join(Role, UserRole.role_id == Role.id)
                .where(Role.name.in_(["hr", "hr_manager", "admin", "recruiter"]))
            )
            res = await self.session.execute(query)
            for usr, role_name in res.all():
                if usr.id not in candidates_map:
                    candidates_map[usr.id] = HRInterviewerOption(
                        id=usr.id,
                        full_name=usr.full_name,
                        email=usr.email,
                        role=role_name,
                    )

        if actor.id not in candidates_map:
            actor_roles: set[str] = set()
            actor_state = inspect(actor)
            if "roles" in actor_state.dict and actor_state.dict["roles"]:
                for ur in actor_state.dict["roles"]:
                    ur_state = inspect(ur)
                    if "role" in ur_state.dict and ur_state.dict["role"]:
                        actor_roles.add(ur_state.dict["role"].name)
            candidates_map[actor.id] = HRInterviewerOption(
                id=actor.id,
                full_name=actor.full_name,
                email=actor.email,
                role="hr_manager" if "hr_manager" in actor_roles or "hr" in actor_roles else "recruiter",
            )

        return list(candidates_map.values())

    async def _audit_interview(
        self,
        event_type: AuditEventType,
        *,
        action: str,
        interview: Interview,
        app: JobApplication,
        job: Job | None,
        actor: User,
        details: dict,
    ) -> None:
        """Record an interview lifecycle event.

        Separate from ``APPLICATION_STATUS_CHANGED``, which the lifecycle service
        already wrote for the status flip. The event is scoped to the
        organization via the job, and names the application so the trail links
        the interview to the hiring record it belongs to.
        """
        organization_id = job.organization_id if job else None
        await self.audit.log(
            event_type=event_type,
            action=action,
            user_id=actor.id,
            organization_id=organization_id,
            resource_type="interview",
            resource_id=str(interview.id),
            details={
                "application_id": str(app.id),
                "job_id": str(app.job_id),
                "candidate_id": str(app.candidate_id),
                "interview_status": interview.status,
                **details,
            },
        )
        AUDIT_LOGGER.info(
            "INTERVIEW_%s | actor=%s application=%s interview=%s",
            action.upper(), actor.id, app.id, interview.id,
        )
