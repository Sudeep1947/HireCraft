"""Phase 16 (video): the WebSocket signaling endpoint for one interview room.

Declared as its own router because the protocol is not REST: browsers cannot
attach an ``Authorization`` header to a WebSocket handshake, so the JWT rides
in the query string and the connection is authenticated once, at connect time,
by :func:`~app.services.interview.interview_video_service.resolve_video_access`.
Every rule about *who* may enter *which* room, and *when*, stays in the room
service — this module only moves bytes between the two sockets that service
authorized.

Protocol (client → server), validated by ``parse_client_message``:

- ``{"type": "signal", "payload": {"kind": "offer"|"answer"|"ice", ...}}``
  Relay to the other participant. The interviewer's side originates offers and
  the candidate's side answers (``check_signal_direction``); ICE flows both
  ways.
- ``{"type": "media_state", "payload": {"camera": bool, "mic": bool}}``
  Camera/microphone state, relayed to the peer and remembered for late joiners.
- ``{"type": "leave"}`` — the side is leaving the call (attendance stays
  recorded, exactly as the Phase 14 panel documents).
- ``{"type": "end"}`` — interviewer only: end the call for both sides. Writes
  nothing; completion remains the explicit Phase 11 endpoint.
- ``{"type": "ping"}`` — keepalive, answered with ``{"type": "pong"}``.

Protocol (server → client): ``joined``, ``peer_joined``, ``peer_left``,
``signal``, ``media_state``, ``ended``, ``pong``.

Close codes: 4401 unauthenticated, 4403 not permitted (including the room's
controlled ``unavailable_reason`` token), 4404 no such interview for this
caller, 4409 replaced by a newer connection from the same side, 4400 ended by
the interviewer, 1008 protocol violation.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.interview.interview_video_service import (
    WS_ENDED,
    WS_FORBIDDEN,
    WS_NOT_FOUND,
    WS_UNAUTHENTICATED,
    MessageProtocolError,
    RoomRoleLiteral,
    VideoRoomRefused,
    check_signal_direction,
    hub,
    parse_client_message,
    resolve_video_access,
)

router = APIRouter(prefix="/interview", tags=["interview-video"])

logger = logging.getLogger(__name__)


@router.websocket("/{interview_id}/video")
async def interview_video_socket(
    interview_id: uuid.UUID,
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """One signaling connection for one interview room.

    See the module docstring for the message protocol.

    Access is decided before the connection enters any room: a missing or bad
    token closes with 4401, an interview the caller cannot reach (other tenant,
    unknown id) with 4404, and a room that is not open right now with 4403
    carrying the room's controlled reason — the same reason the REST room
    endpoints report, because it comes from the same evaluation.

    A refused connection is *accepted* only so that it can then be closed with
    the application close code: rejecting the handshake outright surfaces to a
    browser as an anonymous 1006, which would turn "your room is not open yet"
    into an uninterpretable network failure on the client. The refused socket
    never joins the hub, never receives the joined event, and never reaches the
    relay loop — it is closed immediately after the code is delivered.
    """
    try:
        access = await resolve_video_access(db, interview_id, token)
    except VideoRoomRefused as refused:
        await websocket.accept()
        await websocket.close(code=refused.code)
        logger.info(
            "VIDEO_WS_REFUSED | interview=%s code=%s reason=%s",
            interview_id, refused.code, refused.reason,
        )
        return

    role = access.role
    await websocket.accept()

    try:
        # Announce this side and describe the room as it stands: whether the
        # other participant is already here, and their last camera/mic state so
        # a late joiner renders the remote tile correctly from the first frame.
        await websocket.send_json(
            await hub.join(interview_id, role, websocket)
        )

        await _serve(websocket, interview_id, role)
    except WebSocketDisconnect:
        pass
    finally:
        # Only vacates the slot if this socket still owns it, so a connection
        # already replaced by a reload cannot evict the newer one.
        await hub.drop(interview_id, role, websocket)


async def _serve(
    websocket: WebSocket, interview_id: uuid.UUID, role: RoomRoleLiteral,
) -> None:
    """Relay loop for one authorized connection."""
    while True:
        raw = await websocket.receive()

        # ``websocket.disconnect`` frames arrive as this shape; anything else
        # is application data.
        if raw["type"] == "websocket.disconnect":
            return

        text = raw.get("text")
        if text is None:
            # Binary frames carry no meaning in this protocol; ignore rather
            # than disconnect, so a stray frame cannot end a live interview.
            continue

        try:
            message = parse_client_message(text)
        except MessageProtocolError as exc:
            # A buggy or hostile client is closed with the standard
            # policy-violation code instead of being tolerated forever.
            logger.info("VIDEO_WS_PROTOCOL | interview=%s error=%s", interview_id, exc)
            await websocket.close(code=1008)
            return

        msg_type = message["type"]
        payload = message["payload"]

        if msg_type == "ping":
            try:
                await websocket.send_json({"type": "pong"})
            except Exception:  # noqa: BLE001 - the connection vanished mid-ping
                # A failed send means this side is already gone; the endpoint's
                # `finally` vacates the slot.
                return
            continue

        if msg_type == "leave":
            # Attendance stays recorded: leaving the *call* never un-records
            # that the participant arrived (Phase 14's rule). The slot is
            # vacated by the endpoint's `finally` (hub.drop), which notifies
            # the peer exactly once and only if this socket still owns the
            # slot — so no relay is done here, to avoid a duplicate event.
            return

        if msg_type == "end":
            if role != "interviewer":
                await websocket.close(code=WS_FORBIDDEN)
                return
            # Closes both sockets with WS_ENDED and writes nothing: the
            # interview's status changes only through the explicit completion
            # endpoint, never because a call dropped or ended here.
            await hub.end_interview(interview_id, by=role)
            return

        if msg_type == "media_state":
            state = {
                "camera": bool(payload.get("camera", False)),
                "mic": bool(payload.get("mic", False)),
            }
            await hub.record_media_state(interview_id, role, state)
            await hub.relay(interview_id, role, {
                "type": "media_state",
                "payload": {"role": role, **state},
            })
            continue

        if msg_type in ("chat", "hand_raise", "caption"):
            await hub.relay(interview_id, role, {
                "type": msg_type,
                "payload": {"from": role, **payload},
            })
            continue

        # signal
        try:
            check_signal_direction(role, payload)
        except MessageProtocolError as exc:
            logger.info("VIDEO_WS_PROTOCOL | interview=%s error=%s", interview_id, exc)
            await websocket.close(code=1008)
            return
        await hub.relay(interview_id, role, {
            "type": "signal",
            "payload": {"from": role, **payload},
        })


# Re-exported for tests that assert the refusal vocabulary without importing
# the endpoint module's internals.
__all__ = [
    "router",
    "WS_ENDED",
    "WS_FORBIDDEN",
    "WS_NOT_FOUND",
    "WS_UNAUTHENTICATED",
]
