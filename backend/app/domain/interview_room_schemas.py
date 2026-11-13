"""Phase 14 shared interview room contracts.

Before this, an interview could be scheduled from an application and recorded as
completed, but there was nothing in between: the candidate's page rendered a
read-only card, ``InterviewStatus.IN_PROGRESS`` was handled everywhere except by
any code path that wrote it, and the only way an interview left ``scheduled`` was
a recruiter asserting by hand that it had happened. These contracts are the
missing middle: one room per interview, which both participants address by the
same ``interview_id``.

Three properties are load-bearing:

1. **One room per interview, addressed by interview id.** ``room_id`` is an
   opaque identifier for the interview's room, not a capability. There is no
   meeting URL to leak and no third-party provider to integrate, because the
   repository has no video stack; the room is the shared, persisted state of one
   interview plus the presence of its two participants, both of whom the
   ``Interview`` row already identifies.

2. **The server owns the join window.** ``can_join`` and
   ``unavailable_reason`` are computed from the interview's own schedule and
   status, never by the client, so the UI cannot offer a Join button the backend
   would reject, and the countdown is driven by ``server_time`` rather than by a
   browser clock the user may have set wrong. The client is not asked to judge
   whether it is time yet.

3. **The candidate view is an explicit allowlist, in the other direction too.**
   Presence is reported as *the other party is here* / *the other party is not
   here*, never as identity: there is no interviewer name, id, email or notes on
   :class:`InterviewRoomPresence`, so the recruiter cannot be profiled to the
   candidate even accidentally, and no scorecard, evaluation, recommendation,
   recruiter note, fairness or protected-attribute data appears on any model
   here. This matches the existing rule in
   :mod:`app.domain.application_interview_schemas`, where interview intelligence
   is staff-only evidence and the candidate's projection simply lacks the fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import InterviewStage, InterviewStatus, InterviewType


# ── Controlled reasons a join is unavailable ────────────────────────────────
# A fixed vocabulary so the client can render a sensible message and no internal
# exception text ever reaches the browser, matching the Phase 11 affordance
# reasons in ``application_interview_schemas``.
REASON_NOT_JOINABLE_STATUS = "interview_not_joinable"
REASON_WINDOW_NOT_OPEN = "join_window_not_open"
REASON_WINDOW_CLOSED = "join_window_closed"
REASON_NO_SCHEDULE = "interview_has_no_schedule"

# The room opens a little before the start so a candidate who arrives a few
# minutes early is not turned away, and closes when the interview is scheduled to
# end, so a join cannot be used to sit in on an interview days later.
EARLY_JOIN_MINUTES = 15

# Which side of the interview the caller is. ``interviewer`` rather than
# ``recruiter`` because the column is ``recruiter_id`` but an HR user may hold
# the room; this name stays correct if that ever changes.
RoomRole = Literal["candidate", "interviewer"]

# The display state of the room, derived on the server from the interview's own
# status and schedule. A fixed vocabulary so the UI renders one label per state
# instead of re-deriving "is it ready?" from raw timestamps, which is exactly the
# client-side judgement this module exists to remove. ``status`` stays the
# authoritative stored value; ``state`` is the human-facing summary of it:
#
# - ``upcoming``      scheduled, window not yet open (or no schedule at all)
# - ``ready_to_join`` inside the join window, not yet entered
# - ``in_progress``   at least one participant has entered
# - ``completed``     the recruiter marked it done; immutable
# - ``cancelled``     cancelled; the room is closed
# - ``rescheduled``   moved to a new time and waiting for the new window
# - ``expired``       the join window closed and nobody completed it
#
# ``expired`` is display state only: the interview is still ``scheduled`` and no
# status is written, because the window closing is not the interview ending. That
# remains the recruiter's explicit completion action.
RoomDisplayState = Literal[
    "upcoming",
    "ready_to_join",
    "in_progress",
    "completed",
    "cancelled",
    "rescheduled",
    "expired",
]


# ── Presence ────────────────────────────────────────────────────────────────


class InterviewRoomPresence(BaseModel):
    """Who has entered the room so far.

    Deliberately holds timestamps and booleans but no identities: the candidate
    sees ``interviewer_joined`` and never learns who the interviewer is, and
    neither side learns anything about the other's account. Presence is a
    first-entry fact and is never cleared, so it remains accurate after somebody
    leaves and comes back.
    """

    candidate_joined: bool = False
    candidate_joined_at: datetime | None = None
    interviewer_joined: bool = False
    interviewer_joined_at: datetime | None = None


# ── Room state ──────────────────────────────────────────────────────────────


class InterviewRoomState(BaseModel):
    """Everything one participant needs to see the room they share.

    Returned identically to both roles, minus the fact of which role asked:
    ``your_role`` is what lets the same component render the interviewer's extra
    controls without the server branching into two shapes, and everything else in
    this model is safe for either audience.
    """

    interview_id: uuid.UUID
    # Null for a mock/practice interview and for any interview scheduled before
    # Phase 11; present for every application-driven interview, which is what
    # lets the interviewer surface the existing application decision controls.
    application_id: uuid.UUID | None = None
    interview_type: InterviewType
    # Which hiring stage this round is (recruiter / HR). Both participants may
    # know it -- it names the round, not the interviewer -- so the same card can
    # read "Recruiter Interview" or "HR Interview".
    stage: InterviewStage = InterviewStage.RECRUITER
    status: InterviewStatus
    # The human-facing summary of ``status`` and the schedule, derived on the
    # server so the client never has to decide whether the room is joinable.
    state: RoomDisplayState = "upcoming"
    your_role: RoomRole

    # The shared room identifier. Opaque and per-interview; see the module
    # docstring for why this is not a secret capability.
    room_id: str

    # Schedule facts, as stored. ``timezone`` is the interviewer's zone, so the
    # UI can show "2:00 PM your time" without inventing an offset.
    scheduled_at: datetime | None = None
    # When the interview was last moved, so the room can say "rescheduled" rather
    # than a plain "upcoming". Null unless a reschedule happened.
    rescheduled_at: datetime | None = None
    timezone: str = "UTC"
    duration_minutes: int | None = None

    # The window the server computed, echoed back so the client renders the same
    # numbers the server enforces. Null when the interview has no schedule to
    # derive a window from, in which case ``can_join`` is false and
    # ``unavailable_reason`` is ``interview_has_no_schedule``.
    join_opens_at: datetime | None = None
    join_closes_at: datetime | None = None
    # The server's clock at the moment of this response, so a countdown does not
    # depend on the viewer's device being set correctly.
    server_time: datetime

    # Whether this caller may enter right now, and the controlled reason when not.
    can_join: bool = False
    unavailable_reason: str | None = None
    # True once *this* caller has entered. Re-joining is permitted and idempotent
    # (a reload should not lock someone out of a room they are already in), so
    # this is display state, not the thing gating ``can_join``.
    you_joined: bool = False

    presence: InterviewRoomPresence = Field(default_factory=InterviewRoomPresence)

    # Server-authored wording for the current state, so the UI never assembles a
    # message about someone else's interview out of raw timestamps.
    message: str = ""