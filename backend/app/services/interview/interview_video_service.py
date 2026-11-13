"""Phase 16 (video): WebRTC signaling for the shared interview room.

The gap this fills
------------------

Phase 14 gave an interview one shared room with a server-owned join window and
attendance, but the repository had no media stack at all: nothing carried
audio or video between the two participants, so a scheduled interview could
never actually be *attended*. Attendance was recorded and the interview moved
to ``in_progress``, yet nobody could see or hear anybody.

This module is the missing media layer, and it is deliberately the smallest
one that satisfies the contract:

- **Peer-to-peer WebRTC between exactly the two participants of one
  interview.** Audio and video travel directly between the two browsers; the
  server only relays the small signaling messages (SDP offers/answers and ICE
  candidates). No third-party provider is involved, so there are no provider
  secrets to keep and nothing sensitive transits the backend.

- **The server remains the source of truth for who may enter.** Connecting to
  the signaling socket does not grant a room: :func:`resolve_video_access`
  authenticates the JWT exactly like the HTTP dependency chain does and then
  delegates to :meth:`InterviewRoomService.get_room_state`, the same
  authorization and join-window evaluation the ``GET /room`` and ``POST /join``
  endpoints use. An interview id from another tenant produces the same refusal
  as a missing one, and the window rules (opens 15 minutes early, closes at the
  scheduled end, completed/cancelled interviews stay closed) apply unchanged.

- **The registry is in-memory and holds no truth.** :class:`VideoRoomHub`
  remembers only which live socket currently occupies each of the two role
  slots for an interview. It is deliberately not persisted: a server restart
  drops the connections, and both participants simply rejoin through the same
  HTTP join path they used the first time. Nothing about scheduling,
  attendance, completion or feedback changes because of this module.

- **Roles come from the interview row, never from the client.** A socket may
  occupy the ``candidate`` slot or the ``interviewer`` slot, decided by
  :meth:`InterviewRoomService._role` after authorization. Signaling messages
  are direction-checked (only the interviewer's side may originate an offer,
  only the candidate's side an answer), so a client cannot corrupt the
  negotiation by sending both.

- **Ending the call is the interviewer's action and stays separate from
  completing the interview.** ``end`` closes both sockets and tells both
  participants the call is over; it writes nothing. The interview still
  leaves ``in_progress`` only through the explicit Phase 11 completion
  endpoint, which owns its transition, history and notification — exactly the
  rule Phase 14 established.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.permissions import expand_required_roles
from app.core.security import decode_token
from app.domain.interview_room_schemas import InterviewRoomState
from app.domain.models import User
from app.repositories.user import UserRepository
from app.services.interview.interview_room_service import InterviewRoomService

logger = logging.getLogger(__name__)

# WebSocket close codes. 4000-4999 is the application-defined range; each one
# maps to a condition the client turns into a human message. They are stable
# contract: the frontend switches on them.
WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN = 4403
WS_NOT_FOUND = 4404
WS_REPLACED = 4409
WS_ENDED = 4400
WS_PROTOCOL = 1008  # standard "policy violation"

RoomRoleLiteral = Literal["candidate", "interviewer"]

# The same role gate the interview HTTP endpoints apply via
# ``require_role("candidate", "hr", "recruiter")``, expanded the same way.
_VIDEO_ROLES = expand_required_roles(("candidate", "hr", "recruiter"))


class VideoRoomRefused(Exception):
    """A connection was refused before it joined a room.

    ``code`` is the WebSocket close code the endpoint sends, and ``reason`` is
    a controlled token (never prose assembled from internals) that the client
    maps to its own wording, mirroring how the room endpoints expose
    ``unavailable_reason``.
    """

    def __init__(self, code: int, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.code = code
        self.reason = reason
        self.detail = detail or reason


class MessageProtocolError(Exception):
    """A client message that does not follow the signaling protocol."""


@runtime_checkable
class VideoSocketLike(Protocol):
    """The slice of Starlette's ``WebSocket`` the hub relies on.

    Typed as a protocol so the hub is unit-testable with a plain fake and so
    the relay logic can be exercised without an ASGI server.
    """

    async def send_json(self, message: dict[str, Any]) -> None: ...

    async def close(self, code: int = 1000) -> None: ...


@dataclass(frozen=True)
class VideoAccess:
    """The result of a successful handshake: who they are and their room."""

    user: User
    room: InterviewRoomState
    role: RoomRoleLiteral


@dataclass
class _RoomSlots:
    """Live sockets for one interview, one per role slot."""

    candidate: VideoSocketLike | None = None
    interviewer: VideoSocketLike | None = None
    # Last reported camera/mic state per role, so a participant who joins late
    # learns whether the other side's camera is on without waiting for an event.
    media: dict[str, dict[str, bool]] = field(default_factory=dict)

    def slot(self, role: RoomRoleLiteral) -> VideoSocketLike | None:
        return self.candidate if role == "candidate" else self.interviewer

    def occupy(self, role: RoomRoleLiteral, sock: VideoSocketLike) -> None:
        if role == "candidate":
            self.candidate = sock
        else:
            self.interviewer = sock

    def vacate(self, role: RoomRoleLiteral) -> None:
        self.occupy(role, None)

    def peer_role(self, role: RoomRoleLiteral) -> RoomRoleLiteral:
        return "interviewer" if role == "candidate" else "candidate"


class VideoRoomHub:
    """In-memory registry of live signaling sockets, one two-slot room per interview.

    The hub stores no interview truth: only the sockets currently occupying
    each role slot. Everything durable about the interview — schedule, status,
    attendance — stays in the database, owned by the Phase 11/14 services, and
    this module never writes to it.
    """

    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, _RoomSlots] = {}

    # ── Connection lifecycle ────────────────────────────────────────

    async def join(
        self,
        interview_id: uuid.UUID,
        role: RoomRoleLiteral,
        sock: VideoSocketLike,
    ) -> dict[str, Any]:
        """Occupy ``role``'s slot for the interview and describe the room.

        A second connection for the same role (a page reload, a second tab)
        *replaces* the old socket rather than being refused: the replacement
        closes the stale connection with :data:`WS_REPLACED`, so a refresh
        cannot lock the participant out or leave a zombie socket relaying.
        """
        slots = self._rooms.setdefault(interview_id, _RoomSlots())
        previous = slots.slot(role)
        slots.occupy(role, sock)

        peer_role = slots.peer_role(role)
        peer_present = slots.slot(peer_role) is not None
        peer_media = slots.media.get(peer_role)

        if previous is not None and previous is not sock:
            # Tell the stale socket why it closed so the old tab can show
            # "rejoined in another tab" instead of a generic disconnect.
            try:
                await previous.close(code=WS_REPLACED)
            except Exception:  # noqa: BLE001 - best-effort close of a dead socket
                logger.debug("Replacing a stale video socket failed to close", exc_info=True)

        # Announce the arrival to whoever is already in the room.
        if peer_present:
            await self._send(slots.slot(peer_role), {
                "type": "peer_joined",
                "payload": {"role": role},
            })

        return {
            "type": "joined",
            "payload": {
                "role": role,
                "peer_present": peer_present,
                "peer_media": peer_media,
            },
        }

    async def leave(self, interview_id: uuid.UUID, role: RoomRoleLiteral) -> None:
        """Free the role slot and tell the peer, if any, that the side left."""
        slots = self._rooms.get(interview_id)
        if slots is None:
            return
        slots.vacate(role)
        slots.media.pop(role, None)
        peer = slots.slot(slots.peer_role(role))
        if peer is not None:
            await self._send(peer, {
                "type": "peer_left",
                "payload": {"role": role},
            })
        self._cleanup(interview_id, slots)

    async def drop(
        self, interview_id: uuid.UUID, role: RoomRoleLiteral, sock: VideoSocketLike,
    ) -> None:
        """Free the slot only if ``sock`` still occupies it.

        Called on disconnect. Without the identity check, a socket that was
        already replaced by a reload would vacate the *new* connection's slot
        when its own close finally propagated.
        """
        slots = self._rooms.get(interview_id)
        if slots is None or slots.slot(role) is not sock:
            return
        await self.leave(interview_id, role)

    # ── Messaging ───────────────────────────────────────────────────

    async def relay(
        self,
        interview_id: uuid.UUID,
        from_role: RoomRoleLiteral,
        message: dict[str, Any],
    ) -> bool:
        """Forward one signaling message to the other side of the room.

        Returns whether a peer was there to receive it. A message relayed to
        nobody is not an error: the peer may simply not have joined yet.
        """
        slots = self._rooms.get(interview_id)
        if slots is None:
            return False
        peer = slots.slot(slots.peer_role(from_role))
        if peer is None:
            return False
        await self._send(peer, message)
        return True

    async def record_media_state(
        self,
        interview_id: uuid.UUID,
        role: RoomRoleLiteral,
        state: dict[str, bool],
    ) -> None:
        """Remember a side's camera/mic state for late joiners and the peer."""
        slots = self._rooms.setdefault(interview_id, _RoomSlots())
        slots.media[role] = state

    async def end_interview(
        self, interview_id: uuid.UUID, by: RoomRoleLiteral,
    ) -> None:
        """Tell both sides the call is over, then close both sockets.

        Writes nothing to the database. The interview's status transition
        remains the recruiter's explicit completion action (Phase 11); this
        only ends the *call*, which is the distinction that keeps a dropped
        call from looking like a completed interview.
        """
        slots = self._rooms.get(interview_id)
        if slots is None:
            return
        message = {"type": "ended", "payload": {"by": by}}
        sockets = [s for s in (slots.candidate, slots.interviewer) if s is not None]
        for sock in sockets:
            try:
                await self._send(sock, message)
            except Exception:  # noqa: BLE001 - best effort before closing
                logger.debug("Failed to deliver end event", exc_info=True)
            try:
                await sock.close(code=WS_ENDED)
            except Exception:  # noqa: BLE001 - best-effort close
                logger.debug("Failed to close ended video socket", exc_info=True)
        slots.candidate = None
        slots.interviewer = None
        slots.media.clear()
        self._cleanup(interview_id, slots)

    # ── Introspection (tests, diagnostics) ──────────────────────────

    def is_present(self, interview_id: uuid.UUID, role: RoomRoleLiteral) -> bool:
        slots = self._rooms.get(interview_id)
        return slots is not None and slots.slot(role) is not None

    def room_count(self) -> int:
        return len(self._rooms)

    # ── Internals ───────────────────────────────────────────────────

    @staticmethod
    async def _send(sock: VideoSocketLike | None, message: dict[str, Any]) -> None:
        """Best-effort delivery to one socket.

        A failed send means that side's connection is already gone — its own
        endpoint will vacate the slot through its `finally` — so the failure is
        logged and swallowed rather than being allowed to tear down the *other*
        participant's live loop, which is still perfectly healthy.
        """
        if sock is None:
            return
        try:
            await sock.send_json(message)
        except Exception:  # noqa: BLE001 - a dead peer must not break the live one
            logger.debug("Video socket send failed", exc_info=True)

    def _cleanup(self, interview_id: uuid.UUID, slots: _RoomSlots) -> None:
        if slots.candidate is None and slots.interviewer is None:
            self._rooms.pop(interview_id, None)


# The process-wide hub. One interview = one room = two slots, so two recruiters
# from the same organization cannot both occupy the interviewer slot: the
# second connection replaces the first, which is the behaviour a page reload
# needs anyway.
hub = VideoRoomHub()


# ── Handshake ──────────────────────────────────────────────────────────────


async def resolve_video_access(
    session: AsyncSession,
    interview_id: uuid.UUID,
    token: str | None,
) -> VideoAccess:
    """Authenticate and authorize one signaling connection.

    Mirrors the HTTP dependency chain exactly: the same JWT decode, the same
    "access token only" rule, the same active-user requirement, and the same
    role gate as ``require_role("candidate", "hr", "recruiter")``. Browsers
    cannot attach an ``Authorization`` header to a WebSocket handshake, so the
    token arrives as a query parameter; it is the *same* access token the REST
    client sends, never a lesser one.

    Authorization then delegates to the room service, so the signaling socket
    enforces precisely the join window and tenant rule the REST endpoints do:
    an interview in another organization, a completed or cancelled interview,
    or a socket connecting before the window opens are all refused here,
    before any relay exists.
    """
    if not token:
        raise VideoRoomRefused(WS_UNAUTHENTICATED, "missing_token")

    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise VideoRoomRefused(WS_UNAUTHENTICATED, "invalid_token") from exc

    if payload.get("type") != "access":
        raise VideoRoomRefused(WS_UNAUTHENTICATED, "invalid_token_type")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise VideoRoomRefused(WS_UNAUTHENTICATED, "invalid_token") from exc

    user = await UserRepository(session).get_with_roles(user_id)
    if not user or not user.is_active:
        raise VideoRoomRefused(WS_UNAUTHENTICATED, "user_inactive")

    role_names = {ur.role.name for ur in user.roles}
    if not role_names.intersection(_VIDEO_ROLES):
        raise VideoRoomRefused(WS_FORBIDDEN, "insufficient_role")

    # Delegation point: the room service owns access, the window and the role.
    try:
        room = await InterviewRoomService(session).get_room_state(interview_id, user)
    except NotFoundError as exc:
        # Same shape as the REST 404: an id in another tenant is
        # indistinguishable from a missing one.
        raise VideoRoomRefused(WS_NOT_FOUND, "interview_not_found") from exc

    if not room.can_join and not room.you_joined:
        # Already-joined participants stay connected (the window gates entry,
        # not attendance); everyone else gets the server's controlled reason.
        raise VideoRoomRefused(
            WS_FORBIDDEN,
            room.unavailable_reason or "room_closed",
            detail=room.message,
        )

    return VideoAccess(user=user, room=room, role=room.your_role)


# ── Client message protocol ────────────────────────────────────────────────

SIGNAL_KINDS = frozenset({"offer", "answer", "ice"})
CLIENT_TYPES = frozenset({"signal", "media_state", "leave", "end", "ping", "chat", "hand_raise", "caption"})


def parse_client_message(raw: str | bytes) -> dict[str, Any]:
    """Parse and validate one client message.

    A malformed message is a protocol error rather than an exception the
    server survives unpredictably: the endpoint closes the socket with the
    standard policy-violation code, so a buggy or hostile client cannot spam
    the relay with arbitrary shapes.
    """
    try:
        message = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MessageProtocolError("message is not valid JSON") from exc

    if not isinstance(message, dict):
        raise MessageProtocolError("message must be a JSON object")

    msg_type = message.get("type")
    if msg_type not in CLIENT_TYPES:
        raise MessageProtocolError(f"unknown message type: {msg_type!r}")

    payload = message.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise MessageProtocolError("payload must be an object")

    if msg_type == "signal":
        kind = payload.get("kind")
        if kind not in SIGNAL_KINDS:
            raise MessageProtocolError(f"unknown signal kind: {kind!r}")
        if kind == "ice":
            candidate = payload.get("candidate")
            if candidate is not None and not isinstance(candidate, dict):
                raise MessageProtocolError("ice candidate must be an object or null")
        else:
            sdp = payload.get("sdp")
            if not isinstance(sdp, str) or not sdp:
                raise MessageProtocolError(f"{kind} signal requires an sdp string")

    if msg_type == "media_state":
        for key in ("camera", "mic"):
            value = payload.get(key)
            if value is not None and not isinstance(value, bool):
                raise MessageProtocolError(f"media_state.{key} must be a boolean")

    if msg_type == "chat":
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise MessageProtocolError("chat message requires non-empty text string")

    if msg_type == "hand_raise":
        raised = payload.get("raised")
        if not isinstance(raised, bool):
            raise MessageProtocolError("hand_raise requires boolean 'raised'")

    if msg_type == "caption":
        text = payload.get("text")
        if text is not None and not isinstance(text, str):
            raise MessageProtocolError("caption requires text string")

    return {"type": msg_type, "payload": payload}


def check_signal_direction(role: RoomRoleLiteral, payload: dict[str, Any]) -> None:
    """Enforce which side may originate which signal.

    The interviewer's side creates the offer and the candidate's side answers;
    ICE flows both ways. Without this, two clients could both offer and wedge
    the negotiation, or a participant could spoof being the offerer's peer.
    """
    kind = payload.get("kind")
    if kind == "offer" and role != "interviewer":
        raise MessageProtocolError("only the interviewer's side may send an offer")
    if kind == "answer" and role != "candidate":
        raise MessageProtocolError("only the candidate's side may send an answer")
