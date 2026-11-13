"""Phase 9 candidate application tracking service.

Assembles the candidate's view of *one* application: where it is, how it got
there, and what they are told at each step.

Design notes:
- The application row is the single source of truth. This service is read-only:
  it never writes status, history, decisions or screening state, and it derives
  nothing from a screening score or an AI recommendation.
- The progress view is built from the real
  ``ApplicationStatusHistory`` trail, so a stage is only ever reported as
  reached when a row for it exists. A terminal outcome (rejected/withdrawn) is
  reported as the current stage rather than forced into the happy path.
- Candidate wording is delegated to
  :class:`~app.services.applications.application_decision_service.ApplicationDecisionService`,
  the single reviewed projection, so tracking and decision views cannot disagree.
- ``can_withdraw`` is read from ``CANDIDATE_TRANSITIONS``, the same map the
  write path enforces, so the client never re-implements the rule.
- Ownership is resolved through ``authorize_application_ownership``, which
  raises the identical error for "not yours" and "does not exist" so application
  ids cannot be probed.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.application_decision_schemas import (
    CANDIDATE_STATUS_LABELS,
    candidate_status_message,
)
from app.domain.application_tracking_schemas import (
    CandidateApplicationStage,
    CandidateApplicationTimelineEvent,
    CandidateApplicationTrackResponse,
    PROGRESS_STAGES,
)
from app.domain.enums import ApplicationStatus, RejectionReason, ScreeningStatus
from app.domain.models import Job, JobApplication, User
from app.services.applications.application_decision_service import (
    ApplicationDecisionService,
)
from app.services.applications.application_lifecycle_service import (
    ApplicationLifecycleService,
    CANDIDATE_TRANSITIONS,
    TERMINAL_STATUSES,
)
from app.services.screening.access import authorize_application_ownership
from app.services.interview.application_interview_service import (
    ApplicationInterviewIntegrationService,
)

logger = logging.getLogger(__name__)

# Used only if a stored status string is unrecognized, so response construction
# cannot fail on legacy data. Matches the decision service's fallback.
_FALLBACK_STATUS = ApplicationStatus.APPLIED

# A candidate-visible history is short. The cap bounds a response that would
# otherwise grow with an application's whole life.
_TIMELINE_LIMIT = 100


class CandidateApplicationTrackingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lifecycle = ApplicationLifecycleService(session)
        self.decisions = ApplicationDecisionService(session)
        # Phase 11: resolved lazily inside the request, because instantiating it
        # eagerly would build the interview repositories for every tracking read
        # including the many applications that have no interview at all.
        self._interviews: ApplicationInterviewIntegrationService | None = None

    @property
    def interviews(self) -> ApplicationInterviewIntegrationService:
        if self._interviews is None:
            self._interviews = ApplicationInterviewIntegrationService(self.session)
        return self._interviews

    async def get_application_track(
        self, application_id: uuid.UUID, candidate: User,
    ) -> CandidateApplicationTrackResponse:
        """Return the candidate tracking view for one of their applications.

        Raises:
            ApplicationAccessDeniedError: the application does not exist or is
                not the caller's. Both cases are indistinguishable to the client.
        """
        app = await authorize_application_ownership(
            self.session, application_id, candidate,
        )
        job = await self.session.get(Job, app.job_id)
        records = await self.lifecycle.list_history(
            application_id, limit=_TIMELINE_LIMIT,
        )

        status = ApplicationStatus.from_value(app.status) or _FALLBACK_STATUS
        job_title = job.title if job else ""
        reason = (
            RejectionReason.from_value(app.decision_reason_code)
            if app.decision_reason_code else None
        )

        timeline = self._build_timeline(records, status, job_title, reason)
        last = records[-1] if records else None

        return CandidateApplicationTrackResponse(
            application_id=app.id,
            job_id=app.job_id,
            job_title=job_title,
            company=job.company if job else "",
            location=job.location if job else "",
            employment_type=job.employment_type if job else "",
            status=status,
            status_label=self._label(status),
            is_decision_final=status in TERMINAL_STATUSES,
            can_withdraw=(
                ApplicationStatus.WITHDRAWN
                in CANDIDATE_TRANSITIONS.get(status, set())
            ),
            applied_at=app.created_at,
            last_status_change_at=last.changed_at if last else None,
            decided_at=app.decided_at,
            status_changed=bool(last and last.from_status != last.to_status),
            screening_status=app.screening_status or ScreeningStatus.NOT_STARTED.value,
            screening_completed_at=app.screening_completed_at,
            has_match_explanation=(
                app.screening_status == ScreeningStatus.COMPLETED.value
            ),
            decision=self.decisions.build_candidate_decision_payload(app, job),
            interview=await self.interviews.get_candidate_view(app.id, candidate),
            stages=self._build_stages(records, status),
            timeline=timeline,
        )

    # ── Internals ───────────────────────────────────────────────────
    @staticmethod
    def _label(status: ApplicationStatus) -> str:
        return CANDIDATE_STATUS_LABELS.get(
            status, status.value.replace("_", " ").title(),
        )

    def _build_timeline(
        self,
        records: list,
        status: ApplicationStatus,
        job_title: str,
        reason: RejectionReason | None,
    ) -> list[CandidateApplicationTimelineEvent]:
        """Project each history row to a candidate-visible event.

        Only the recorded status change, its timestamp and the approved wording
        survive. ``reason``, ``comment``, ``changed_by`` and ``metadata_json``
        are read by neither this method nor the response schema, so staff prose
        cannot leak into a candidate's timeline.
        """
        last_index = len(records) - 1
        events: list[CandidateApplicationTimelineEvent] = []
        for index, record in enumerate(records):
            to_status = ApplicationStatus.from_value(record.to_status)
            if to_status is None:
                # A status this build does not know about is skipped rather than
                # guessed at; the candidate still sees their current status.
                continue
            events.append(
                CandidateApplicationTimelineEvent(
                    status=to_status,
                    status_label=self._label(to_status),
                    from_status=(
                        ApplicationStatus.from_value(record.from_status)
                        if record.from_status else None
                    ),
                    occurred_at=record.changed_at,
                    is_current=index == last_index,
                    message=candidate_status_message(
                        to_status, job_title, reason,
                    ),
                )
            )
        return events

    def _build_stages(
        self, records: list, status: ApplicationStatus,
    ) -> list[CandidateApplicationStage]:
        """Render progress strictly from the statuses actually recorded.

        Reached statuses come from the history trail, not from the stored
        current status alone, so the funnel cannot claim progress that has no
        record behind it. A terminal outcome is appended as the final stage
        when it is not already part of the progress path.
        """
        reached = {
            ApplicationStatus.from_value(record.to_status)
            for record in records
        }
        reached.discard(None)
        # A legacy row that was never given a history entry still shows its real
        # current status rather than appearing to have made no progress at all.
        reached.add(status)

        ordered = list(PROGRESS_STAGES)
        if status in TERMINAL_STATUSES and status not in ordered:
            ordered.append(status)

        stages: list[CandidateApplicationStage] = []
        for stage in ordered:
            if stage not in reached and stage is not status:
                continue
            stages.append(
                CandidateApplicationStage(
                    status=stage,
                    status_label=self._label(stage),
                    reached=stage in reached,
                    is_current=stage is status,
                )
            )
        return stages
