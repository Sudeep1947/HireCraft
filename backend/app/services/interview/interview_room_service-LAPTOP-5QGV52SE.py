"""Phase 14 shared interview room: attendance for a scheduled interview.

The gap this fills
------------------

Phase 11 made an interview schedulable from an application, and Phase 8 gave the
application a final decision, but nothing connected the two ends. A recruiter
scheduled an interview; the candidate's page rendered a read-only card with no
way to attend; ``InterviewStatus.IN_PROGRESS`` was honoured by every read path
and by the reschedule/cancel/complete guards, yet no production code ever wrote
it. Only mock practice sessions did. The sole way a real interview left
``scheduled`` was a recruiter asserting by hand that it had happened.

This module is the missing middle: one room per interview that both participants
address by the same ``interview_id``, whose first entry moves the interview to
``in_progress`` and whose presence is recorded on the row.

Design notes
------------

- **One room per interview, no second participant record.** The room is a column
  on ``Interview`` rather than a table, because both participants are already that
  row's ``candidate_id`` and ``recruiter_id`` and there is exactly one room per
  interview. A join-participants table would introduce a second source of truth
  for "who is in this interview", and nothing in the schema would enforce that it
  stays consistent with the interview it belongs to.

- **Authorization is the existing one.** Both entry points call
  :func:`~app.services.interview.interview_access.load_interview_for_read`, the
  same job-scoped-or-is-the-candidate rule the interview detail endpoint uses. A
  recruiter from another organization receives a 404 that is indistinguishable
  from a missing id, so interview ids cannot be probed. No method here accepts a
  candidate id, a recruiter id or a room id from the client: the caller is
  resolved against the loaded interview, never told to the server.

- **The server owns the join window.** Eligibility is computed from the stored
  schedule and status, never supplied by the caller, so the UI cannot offer a
  Join button the backend would reject. The window opens
  :data:`~app.domain.interview_room_schemas.EARLY_JOIN_MINUTES` before the start
  -- a candidate who arrives early is not turned away -- and closes when the
  interview is scheduled to end, so the room cannot be used to sit in on an
  interview days later.

- **The window gates entry, not attendance.** Someone already inside stays
  joinable after the window shuts, otherwise reloading the room at the scheduled
  end would lock a candidate out of the page they are sitting on. Status still
  dominates: once an interview is ``completed`` or ``cancelled`` the room is
  closed, because its questions, answers and evaluations are evidence and
  reopening it would rewrite history.

- **Completion stays with the recruiter.** Joining marks the interview
  ``in_progress`` and nothing else. It does not complete the interview, does not
  advance the application past ``INTERVIEW_SCHEDULED``, and never selects or
  rejects anybody: the end of the interview and the decision that follows remain
  the explicit Phase 11 and Phase 8 actions, which own their transitions,
  locking, history and notifications.

- **Comparison is timezone-safe.** ``scheduled_at`` is written verbatim from the
  request body and may arrive with any offset, and the SQLite development and test
  database does not persist an offset at all, so a value read back is naive.
  Every stored timestamp is therefore normalized through :func:`as_utc` before it
  is compared with ``datetime.now(timezone.utc)``. Comparing a naive value from
  the database with an aware one raises ``TypeError``, and only under SQLite,
  which is precisely the failure this normalization prevents.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.domain.enums import AuditEventType, InterviewStage, InterviewStatus, InterviewType
from app.domain.interview_room_schemas import (
    EARLY_JOIN_MINUTES,
    REASON_NOT_JOINABLE_STATUS,
    REASON_NO_SCHEDULE,
    REASON_WINDOW_CLOSED,
    REASON_WINDOW_NOT_OPEN,
    InterviewRoomPresence,
    InterviewRoomState,
    RoomDisplayState,
    RoomRole,
)
from app.domain.models import Interview, User
from app.services.audit_service import AuditService
from app.services.interview.interview_access import load_interview_for_read

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")

# Statuses in which the room is open. Mirrors the intent of the Phase 11
# reschedule/cancel/complete guards: a completed or cancelled interview is
# finished business, and an unrecognized stored status is refused rather than
# guessed at.
_JOINABLE_STATUSES = frozenset(
    {InterviewStatus.SCHEDULED, InterviewStatus.IN_PROGRESS}
)

# Fallback duration for an interview whose ``duration_minutes`` was never set.
# Matches the default on the Phase 11 schedule request, so a legacy row without a
# duration gets the window its author would have expected rather than a
# degenerate one that closes immediately.
_DEFAULT_DURATION_MINUTES = 60


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize a possibly-naive stored timestamp to an aware UTC value.

    Aware values are converted; naive values are *assumed* UTC rather than local
    time, because every writer in the interview module stores UTC (the server
    clock for ``started_at`` / ``completed_at``) and because assuming local time
    would silently shift the join window by the server's offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def room_id_for(interview_id: uuid.UUID) -> str:
    """The deterministic room identifier for an interview.

    Derived from the primary key so it cannot collide and needs no backfill: an
    interview scheduled before the ``room_id`` column existed still has a stable,
    correct room. The stored value is preferred when present, so a row that has
    already been joined keeps reporting the identifier it was actually given.
    """
    return f"room_{interview_id.hex}"


class InterviewRoomService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Reads ────────────────────────────────────────────────────────

    async def get_room_state(
        self, interview_id: uuid.UUID, actor: User,
    ) -> InterviewRoomState:
        """Return the shared room state for a participant, without joining.

        Read-only by construction: this performs no writes, so prefetching or
        polling the room cannot mark anybody as present and cannot start the
        interview. Attendance is recorded only by :meth:`join`.
        """
        interview = await load_interview_for_read(self.session, interview_id, actor)
        role = self._role(interview, actor)
        return self._project(interview, role)

    # ── Writes ───────────────────────────────────────────────────────

    async def join(
        self, interview_id: uuid.UUID, actor: User,
    ) -> InterviewRoomState:
        """Record the caller entering the room and start the interview if due.

        Idempotent. Re-joining returns the same state rather than an error, so a
        page refresh, a reconnect or a second browser tab cannot lock somebody out
        of a room they are already in, and a retried request cannot produce a
        second ``in_progress`` transition. Only the *first* join is audited and
        only the first join sets ``started_at``, because those record that the
        interview began, not how many times it was reloaded.

        Raises ``ConflictError`` when the room is closed to this caller, with the
        controlled reason in ``extra["reason"]`` so the UI can explain the refusal
        without parsing prose.
        """
        interview = await load_interview_for_read(self.session, interview_id, actor)
        role = self._role(interview, actor)
        now = datetime.now(timezone.utc)

        can_join, reason = self._evaluate(interview, role, now)
        if not can_join:
            raise ConflictError(
                self._unavailable_message(reason),
                extra={
                    "interview_id": str(interview.id),
                    "reason": reason,
                },
            )

        first_join = not self._joined_at(interview, role)
        if first_join:
            self._mark_joined(interview, role, now)

        # The first participant into the room starts the interview. Before this
        # module nothing wrote IN_PROGRESS for a recruiter-scheduled interview, so
        # this is the transition that finally makes the status mean what the
        # Phase 11 guards already assumed it meant.
        started_interview = False
        if interview.status == InterviewStatus.SCHEDULED.value:
            interview.status = InterviewStatus.IN_PROGRESS.value
            # Never overwrite an existing start: a reschedule keeps the original
            # ``started_at``, and losing it would rewrite when the interview began.
            if interview.started_at is None:
                interview.started_at = now
            started_interview = True

        # Assigned on join rather than on read, so a GET stays side-effect free
        # while any room somebody has actually used has its id persisted.
        if interview.room_id is None:
            interview.room_id = room_id_for(interview.id)

        # Only a first join is recorded. A reload or a second tab answers no
        # question the first entry did not, and one audit row per page refresh
        # would bury the fact that actually matters.
        if first_join:
            await self._audit_join(
                interview=interview, actor=actor, role=role, joined_at=now,
                started_interview=started_interview,
            )
        await self.session.flush()

        return self._project(interview, role, now=now)

    # ── Internals ────────────────────────────────────────────────────

    @staticmethod
    def _role(interview: Interview, actor: User) -> RoomRole:
        """Which side of this interview the caller is.

        Derived from the loaded row after authorization, never from the request.
        When a user is somehow both the candidate and job staff, ``candidate``
        wins: it is the less privileged projection, and the wrong branch would
        record their presence in the recruiter column.
        """
        return "candidate" if interview.candidate_id == actor.id else "interviewer"

    @staticmethod
    def _joined_at(interview: Interview, role: RoomRole) -> datetime | None:
        if role == "candidate":
            return interview.candidate_joined_at
        return interview.recruiter_joined_at

    @staticmethod
    def _mark_joined(
        interview: Interview, role: RoomRole, now: datetime,
    ) -> None:
        if role == "candidate":
            interview.candidate_joined_at = now
        else:
            interview.recruiter_joined_at = now

    @staticmethod
    def _window(interview: Interview) -> tuple[datetime | None, datetime | None]:
        """The join window as aware UTC instants, or ``(None, None)``.

        Derived entirely from stored state. A missing ``scheduled_at`` yields no
        window at all, which is a refusal rather than an open-ended room -- an
        interview nobody scheduled a time for must not be joinable forever.
        """
        start = as_utc(interview.scheduled_at)
        if start is None:
            return None, None
        duration = interview.duration_minutes or _DEFAULT_DURATION_MINUTES
        return (
            start - timedelta(minutes=EARLY_JOIN_MINUTES),
            start + timedelta(minutes=duration),
        )

    def _evaluate(
        self, interview: Interview, role: RoomRole, now: datetime,
    ) -> tuple[bool, str | None]:
        """Whether ``role`` may enter now, and the controlled reason when not.

        One place decides, and the read projection and the join path both go
        through it, so the Join button the UI renders and the Join the server
        accepts can never disagree.
        """
        status = InterviewStatus.from_value(interview.status)

        # An unrecognized stored status permits nothing: an unexpected state is
        # refused rather than interpreted, matching the Phase 11 action guards.
        if status not in _JOINABLE_STATUSES:
            return False, REASON_NOT_JOINABLE_STATUS

        # A mock interview has its own self-service flow and its own UI. Giving
        # it a room would let attendance be recorded against practice sessions,
        # so those records could not be told apart from real interviews.
        if InterviewType.from_value(interview.interview_type) is not InterviewType.RECRUITER_SCHEDULED:
            return False, REASON_NOT_JOINABLE_STATUS

        opens_at, closes_at = self._window(interview)
        if opens_at is None or closes_at is None:
            return False, REASON_NO_SCHEDULE

        # Already inside: the window limits entry, not attendance. Without this,
        # a reload at the scheduled end time would refuse a candidate who has been
        # in the room the whole time.
        if self._joined_at(interview, role) is not None:
            return True, None

        if now < opens_at:
            return False, REASON_WINDOW_NOT_OPEN
        if now > closes_at:
            return False, REASON_WINDOW_CLOSED
        return True, None

    @staticmethod
    def _display_state(
        interview: Interview,
        can_join: bool,
        reason: str | None,
        you_joined: bool,
    ) -> RoomDisplayState:
        """The human-facing state for the room, derived from stored facts only.

        Status dominates, exactly as it does for joining: a completed or cancelled
        interview is finished regardless of its schedule. Otherwise the schedule
        and the already-computed join verdict decide, so ``state`` and ``can_join``
        can never disagree.

        ``expired`` is a display state, not a status: when the window closes with
        nobody having completed the interview the row stays ``scheduled``. The
        interview ending is the recruiter's explicit completion action, and this
        method never writes anything.
        """
        status = InterviewStatus.from_value(interview.status)
        if status is InterviewStatus.CANCELLED:
            return "cancelled"
        if status is InterviewStatus.COMPLETED:
            return "completed"
        # Someone is in the room: the first join moves the interview to
        # in_progress, but a reload after the window closes while still joined is
        # also "in progress" rather than "expired".
        if status is InterviewStatus.IN_PROGRESS or you_joined:
            return "in_progress"

        if can_join:
            return "ready_to_join"
        if reason == REASON_NO_SCHEDULE:
            return "upcoming"
        if reason == REASON_WINDOW_CLOSED:
            return "expired"
        if reason == REASON_WINDOW_NOT_OPEN:
            return "rescheduled" if interview.rescheduled_at else "upcoming"
        # An unrecognized/refused status (e.g. a mock room) is not joinable and
        # is not "waiting"; "upcoming" is the neutral non-actionable summary.
        return "upcoming"

    def _project(
        self,
        interview: Interview,
        role: RoomRole,
        now: datetime | None = None,
    ) -> InterviewRoomState:
        """Build the response both roles receive.

        Presence is reported as *the other party is here* with a timestamp and
        never as identity, so a candidate cannot learn who the interviewer is and
        the interviewer cannot be profiled to them. That is why this model has no
        name, id or email field to strip.
        """
        now = now or datetime.now(timezone.utc)
        can_join, reason = self._evaluate(interview, role, now)
        opens_at, closes_at = self._window(interview)
        candidate_joined_at = as_utc(interview.candidate_joined_at)
        recruiter_joined_at = as_utc(interview.recruiter_joined_at)
        you_joined_at = (
            candidate_joined_at if role == "candidate" else recruiter_joined_at
        )

        return InterviewRoomState(
            interview_id=interview.id,
            application_id=interview.application_id,
            interview_type=(
                InterviewType.from_value(interview.interview_type)
                or InterviewType.RECRUITER_SCHEDULED
            ),
            stage=(
                InterviewStage.from_value(interview.stage)
                or InterviewStage.default()
            ),
            # An unrecognized stored status would fail enum validation here, and
            # such an interview can never be joined, so the failure state is the
            # accurate projection rather than a silent guess.
            status=InterviewStatus.from_value(interview.status)
            or InterviewStatus.COMPLETED,
            state=self._display_state(
                interview, can_join, reason, you_joined_at is not None,
            ),
            your_role=role,
            room_id=interview.room_id or room_id_for(interview.id),
            scheduled_at=as_utc(interview.scheduled_at),
            rescheduled_at=as_utc(interview.rescheduled_at),
            timezone=interview.timezone or "UTC",
            duration_minutes=interview.duration_minutes,
            join_opens_at=opens_at,
            join_closes_at=closes_at,
            server_time=now,
            can_join=can_join,
            unavailable_reason=reason,
            you_joined=you_joined_at is not None,
            presence=InterviewRoomPresence(
                candidate_joined=candidate_joined_at is not None,
                candidate_joined_at=candidate_joined_at,
                interviewer_joined=recruiter_joined_at is not None,
                interviewer_joined_at=recruiter_joined_at,
            ),
            message=self._message(
                interview, role, can_join, reason, you_joined_at is not None,
            ),
        )

    async def _audit_join(
        self,
        *,
        interview: Interview,
        actor: User,
        role: RoomRole,
        joined_at: datetime,
        started_interview: bool,
    ) -> None:
        """Record a participant entering the room.

        Called only for a first join: the row answers "when did this person
        arrive, and did the interview start", and a reload or a second tab
        answers neither question any differently.

        The organization is resolved from the job rather than from the
        application, because the room is reached by interview id and an
        interviewer reading it may not be the application's owner. It is resolved
        before the join rather than after, since the interview row carries only
        ``job_id``.
        """
        from app.domain.models import Job

        job = await self.session.get(Job, interview.job_id)
        await self.audit.log(
            event_type=AuditEventType.INTERVIEW_JOINED,
            action="interview_joined",
            user_id=actor.id,
            organization_id=job.organization_id if job else None,
            resource_type="interview",
            resource_id=str(interview.id),
            details={
                "application_id": (
                    str(interview.application_id) if interview.application_id else None
                ),
                "job_id": str(interview.job_id),
                "candidate_id": str(interview.candidate_id),
                "role": role,
                "joined_at": joined_at.isoformat(),
                "first_join": True,
                "started_interview": started_interview,
                "interview_status": interview.status,
            },
        )
        AUDIT_LOGGER.info(
            "INTERVIEW_JOINED | actor=%s role=%s interview=%s started=%s",
            actor.id, role, interview.id, started_interview,
        )

    @staticmethod
    def _unavailable_message(reason: str | None) -> str:
        """Staff-facing wording for a refused join."""
        return {
            REASON_NOT_JOINABLE_STATUS: (
                "This interview is not open for joining"
            ),
            REASON_NO_SCHEDULE: (
                "This interview has no scheduled time, so its room is not open"
            ),
            REASON_WINDOW_NOT_OPEN: (
                "The room is not open yet"
            ),
            REASON_WINDOW_CLOSED: (
                "This interview's room has closed"
            ),
        }.get(reason or "", "This interview cannot be joined")

    def _message(
        self,
        interview: Interview,
        role: RoomRole,
        can_join: bool,
        reason: str | None,
        you_joined: bool,
    ) -> str:
        """Server-authored wording for the room's current state.

        Built from stored facts and the controlled reason codes rather than from
        recruiter prose, so a candidate is never shown a message assembled from
        text meant for somebody else.
        """
        status = InterviewStatus.from_value(interview.status)
        if status is InterviewStatus.COMPLETED:
            return "This interview has been completed."
        if status is InterviewStatus.CANCELLED:
            return "This interview was cancelled. The hiring team will be in touch."
        if you_joined:
            return "You are in this interview."
        if can_join:
            if role == "candidate":
                return "Your interview is ready. You can join now."
            return "The candidate's interview room is open. You can join now."
        if reason == REASON_WINDOW_NOT_OPEN:
            if interview.rescheduled_at:
                return (
                    "This interview has been rescheduled. The room opens shortly "
                    "before the new time."
                )
            return "The room opens shortly before the scheduled time."
        if reason == REASON_WINDOW_CLOSED:
            return "This interview's join window has closed."
        if reason == REASON_NO_SCHEDULE:
            return "This interview has no scheduled time."
        return "This interview is not open for joining."