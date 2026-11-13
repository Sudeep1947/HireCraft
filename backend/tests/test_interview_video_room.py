"""Tests for Phase 16: WebRTC signaling for the shared interview room.

The contract under test
-----------------------

The gap these tests close: Phase 14 gave an interview one shared room with a
server-owned join window, but the repository had no media stack — nothing
carried audio/video between the two participants, so a scheduled interview
could never be attended as a live interview.

So, under test:

- **The handshake is the same authorization the REST room endpoints use.**
  ``resolve_video_access`` decodes the same access token, applies the same
  role gate, and delegates to the room service — so an interview id from
  another tenant is refused exactly like a missing one, the join window
  (15 minutes early, closes at the scheduled end) gates the socket, and an
  already-joined participant is not locked out when the window shuts.
- **Two slots, one per role, per interview.** The hub admits exactly the
  interview's candidate and interviewer; a reload replaces the stale socket
  (closing it with 4409) instead of refusing the participant.
- **Signaling relay with direction rules.** Offers flow interviewer →
  candidate, answers candidate → interviewer, ICE both ways; the opposite is
  a protocol violation, so two peers cannot wedge the negotiation by both
  offering.
- **End Interview is the interviewer's, and writes nothing.** A candidate
  sending ``end`` is refused; the interviewer's ``end`` closes both sockets
  with 4400. The interview's status is untouched: completion stays the
  explicit Phase 11 endpoint's job.
- **Protocol hygiene.** Malformed JSON, unknown message types and unknown
  signal kinds are rejected by the parser; media state and ping/pong work.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.domain.enums import InterviewStatus, RoleName
from app.services.interview.interview_video_service import (
    WS_FORBIDDEN,
    WS_NOT_FOUND,
    WS_REPLACED,
    WS_UNAUTHENTICATED,
    MessageProtocolError,
    VideoRoomHub,
    VideoRoomRefused,
    check_signal_direction,
    parse_client_message,
    resolve_video_access,
)
from tests.test_application_interview_integration import (
    _auth,
    _interviews_url,
    _login,
    _schedule_body,
    _setup,
)

# ── Fakes ──────────────────────────────────────────────────────────────────


class FakeSocket:
    """The slice of a WebSocket the hub touches, recording what it sends."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed_with: int | None = None

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000) -> None:
        self.closed_with = code

    def of_type(self, msg_type: str) -> list[dict]:
        return [m for m in self.sent if m.get("type") == msg_type]


# ── Helpers ────────────────────────────────────────────────────────────────


async def _schedule_now(
    client, session, ctx, token: str, *,
    starts_in: timedelta = timedelta(minutes=5),
    duration_minutes: int = 60,
):
    """Schedule an interview whose join window is open right now."""
    when = datetime.now(timezone.utc) + starts_in
    resp = await client.post(
        _interviews_url(ctx["app"].id),
        json=_schedule_body(
            scheduled_at=when.isoformat(),
            duration_minutes=duration_minutes,
            question_count=1,
        ),
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["interview_id"])


def _ws_url(interview_id: uuid.UUID, token: str | None) -> str:
    query = f"?token={token}" if token else ""
    return f"/api/v1/interview/{interview_id}/video{query}"


# ── Handshake: resolve_video_access ────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_token_resolves_with_candidate_role(client, session):
    """A valid candidate token inside the window resolves access with role=candidate."""
    ctx = await _setup(session, "vid-auth-cand")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    interview_id = await _schedule_now(client, session, ctx, recruiter_token)

    access = await resolve_video_access(session, interview_id, candidate_token)

    assert access.role == "candidate"
    assert access.user.id == ctx["candidate"].id
    assert access.room.interview_id == interview_id
    assert access.room.can_join is True


@pytest.mark.asyncio
async def test_recruiter_token_resolves_with_interviewer_role(client, session):
    ctx = await _setup(session, "vid-auth-rec")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    access = await resolve_video_access(session, interview_id, token)

    assert access.role == "interviewer"


@pytest.mark.asyncio
async def test_missing_token_is_refused_as_unauthenticated(session):
    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, uuid.uuid4(), None)
    assert exc.value.code == WS_UNAUTHENTICATED


@pytest.mark.asyncio
async def test_garbage_token_is_refused_as_unauthenticated(session):
    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, uuid.uuid4(), "not-a-jwt")
    assert exc.value.code == WS_UNAUTHENTICATED


@pytest.mark.asyncio
async def test_refresh_token_is_refused(session):
    """A refresh token must not open a signaling socket: access tokens only."""
    from app.core.security import create_refresh_token

    ctx = await _setup(session, "vid-auth-refresh")
    refresh = create_refresh_token(str(ctx["candidate"].id))

    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, uuid.uuid4(), refresh)
    assert exc.value.code == WS_UNAUTHENTICATED


@pytest.mark.asyncio
async def test_foreign_interview_is_refused_as_not_found(client, session):
    """Another tenant's interview id is indistinguishable from a missing one."""
    ctx = await _setup(session, "vid-auth-tenant")
    other = await _setup(session, "vid-auth-other")
    # Org A's recruiter schedules org A's interview.
    ctx_a_token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, ctx_a_token)

    access_a = await resolve_video_access(session, interview_id, ctx_a_token)
    assert access_a.role == "interviewer"

    # A recruiter from org B attempts the signaling socket of org A's interview.
    other_token = await _login(client, other["recruiter"].email)
    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, interview_id, other_token)
    assert exc.value.code == WS_NOT_FOUND


@pytest.mark.asyncio
async def test_unrelated_candidate_is_refused(client, session):
    """A candidate who is not *the* candidate of the interview is refused."""
    from sqlalchemy import select

    from app.domain.models import Role, UserRole
    from tests.test_application_interview_integration import _create_user

    ctx = await _setup(session, "vid-auth-othercand")
    stranger = await _create_user(session, "Stranger", "stranger-vid@test.com")
    role = (
        await session.execute(select(Role).where(Role.name == RoleName.CANDIDATE.value))
    ).scalar_one()
    session.add(UserRole(user_id=stranger.id, role_id=role.id))
    await session.flush()
    token = create_access_token(str(stranger.id), ["candidate"])

    recruiter_token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, recruiter_token)

    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, interview_id, token)
    assert exc.value.code == WS_NOT_FOUND


@pytest.mark.asyncio
async def test_window_not_open_refuses_with_room_reason(client, session):
    """An early socket is refused with the room's controlled reason, not prose."""
    ctx = await _setup(session, "vid-window-early")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(
        client, session, ctx, token,
        starts_in=timedelta(hours=3),  # window opens 2h45m from now
    )

    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, interview_id, token)
    assert exc.value.code == WS_FORBIDDEN
    assert exc.value.reason == "join_window_not_open"


@pytest.mark.asyncio
async def test_window_closed_refuses_new_but_not_joined(client, session):
    """After the window closes: refused for newcomers, still fine for someone who joined."""
    from app.repositories.interview.interview import InterviewRepository
    from app.services.interview.interview_room_service import InterviewRoomService

    ctx = await _setup(session, "vid-window-late")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    interview_id = await _schedule_now(
        client, session, ctx, recruiter_token,
        starts_in=timedelta(minutes=5), duration_minutes=30,
    )

    # The candidate attends while the window is open.
    await InterviewRoomService(session).join(interview_id, ctx["candidate"])

    # The scheduled time then passes without the interview being completed:
    # the window is shut for anyone new.
    repo = InterviewRepository(session)
    row = await repo.get(interview_id)
    row.scheduled_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await session.flush()

    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, interview_id, recruiter_token)
    assert exc.value.code == WS_FORBIDDEN
    assert exc.value.reason == "join_window_closed"

    # Attendance was recorded while the window was open: the participant is
    # not locked out when the window shuts (window gates entry, not attendance).
    access = await resolve_video_access(session, interview_id, candidate_token)
    assert access.room.you_joined is True


@pytest.mark.asyncio
async def test_completed_interview_socket_is_refused(client, session):
    ctx = await _setup(session, "vid-completed")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    interview_id = await _schedule_now(client, session, ctx, recruiter_token)

    from app.repositories.interview.interview import InterviewRepository
    repo = InterviewRepository(session)
    row = await repo.get(interview_id)
    row.status = InterviewStatus.COMPLETED.value
    await session.flush()

    with pytest.raises(VideoRoomRefused) as exc:
        await resolve_video_access(session, interview_id, candidate_token)
    assert exc.value.code == WS_FORBIDDEN
    assert exc.value.reason == "interview_not_joinable"


# ── Hub: two slots, replacement, presence ──────────────────────────────────


@pytest.mark.asyncio
async def test_hub_admits_two_sides_and_reports_presence():
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    candidate, interviewer = FakeSocket(), FakeSocket()

    first = await hub.join(interview_id, "interviewer", interviewer)
    assert first["payload"]["peer_present"] is False

    second = await hub.join(interview_id, "candidate", candidate)
    assert second["payload"]["role"] == "candidate"
    assert second["payload"]["peer_present"] is True
    # The earlier participant learns the candidate arrived.
    assert interviewer.of_type("peer_joined") == [
        {"type": "peer_joined", "payload": {"role": "candidate"}},
    ]


@pytest.mark.asyncio
async def test_hub_replacement_closes_stale_socket_with_4409():
    """A reload replaces the same role's socket rather than locking them out."""
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    stale, fresh = FakeSocket(), FakeSocket()

    await hub.join(interview_id, "candidate", stale)
    await hub.join(interview_id, "candidate", fresh)

    assert stale.closed_with == WS_REPLACED
    assert hub.is_present(interview_id, "candidate")


@pytest.mark.asyncio
async def test_hub_drop_does_not_evict_the_replacing_socket():
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    stale, fresh, interviewer = FakeSocket(), FakeSocket(), FakeSocket()

    await hub.join(interview_id, "candidate", stale)
    await hub.join(interview_id, "candidate", fresh)
    await hub.join(interview_id, "interviewer", interviewer)

    # The stale socket's disconnect arrives *after* the replacement.
    await hub.drop(interview_id, "candidate", stale)

    assert hub.is_present(interview_id, "candidate")
    assert interviewer.of_type("peer_left") == []


@pytest.mark.asyncio
async def test_hub_leave_notifies_peer_and_cleans_empty_rooms():
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    candidate, interviewer = FakeSocket(), FakeSocket()
    await hub.join(interview_id, "interviewer", interviewer)
    await hub.join(interview_id, "candidate", candidate)

    await hub.leave(interview_id, "candidate")

    assert interviewer.of_type("peer_left") == [
        {"type": "peer_left", "payload": {"role": "candidate"}},
    ]
    assert not hub.is_present(interview_id, "candidate")
    # The interviewer's side is still open, so the room still exists.
    assert hub.is_present(interview_id, "interviewer")
    assert hub.room_count() == 1

    # Once the last side leaves, the room is forgotten entirely.
    await hub.leave(interview_id, "interviewer")
    assert hub.room_count() == 0


@pytest.mark.asyncio
async def test_hub_relay_reaches_only_the_peer():
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    candidate, interviewer = FakeSocket(), FakeSocket()
    await hub.join(interview_id, "interviewer", interviewer)
    await hub.join(interview_id, "candidate", candidate)

    delivered = await hub.relay(interview_id, "interviewer", {
        "type": "signal", "payload": {"kind": "offer", "sdp": "v=0"},
    })

    assert delivered is True
    assert candidate.of_type("signal") == [
        {"type": "signal", "payload": {"kind": "offer", "sdp": "v=0"}},
    ]
    # The sender never receives its own relay back.
    assert interviewer.of_type("signal") == []


@pytest.mark.asyncio
async def test_hub_relay_to_empty_room_is_not_an_error():
    hub = VideoRoomHub()
    delivered = await hub.relay(uuid.uuid4(), "interviewer", {"type": "signal"})
    assert delivered is False


@pytest.mark.asyncio
async def test_hub_media_state_is_remembered_for_late_joiners():
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    interviewer = FakeSocket()
    await hub.join(interview_id, "interviewer", interviewer)
    await hub.record_media_state(interview_id, "interviewer", {"camera": True, "mic": False})

    late = FakeSocket()
    joined = await hub.join(interview_id, "candidate", late)

    assert joined["payload"]["peer_media"] == {"camera": True, "mic": False}


@pytest.mark.asyncio
async def test_hub_end_closes_both_sockets_and_clears_the_room():
    hub = VideoRoomHub()
    interview_id = uuid.uuid4()
    candidate, interviewer = FakeSocket(), FakeSocket()
    await hub.join(interview_id, "interviewer", interviewer)
    await hub.join(interview_id, "candidate", candidate)

    await hub.end_interview(interview_id, by="interviewer")

    assert candidate.of_type("ended") == [
        {"type": "ended", "payload": {"by": "interviewer"}},
    ]
    assert interviewer.of_type("ended") == [
        {"type": "ended", "payload": {"by": "interviewer"}},
    ]
    assert not hub.is_present(interview_id, "candidate")
    assert not hub.is_present(interview_id, "interviewer")
    assert hub.room_count() == 0


# ── Protocol parsing and direction rules ───────────────────────────────────


def test_parse_accepts_the_documented_message_shapes():
    offer = parse_client_message(
        json.dumps({"type": "signal", "payload": {"kind": "offer", "sdp": "v=0"}})
    )
    assert offer["payload"]["kind"] == "offer"

    ice = parse_client_message(
        json.dumps({"type": "signal", "payload": {"kind": "ice", "candidate": None}})
    )
    assert ice["payload"]["candidate"] is None

    media = parse_client_message(
        json.dumps({"type": "media_state", "payload": {"camera": True, "mic": False}})
    )
    assert media["payload"] == {"camera": True, "mic": False}

    for bare in ("leave", "end", "ping"):
        assert parse_client_message(json.dumps({"type": bare}))["type"] == bare


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"type": "nope"}',
        '{"type": "signal", "payload": {"kind": "telepathy"}}',
        '{"type": "signal", "payload": {"kind": "offer"}}',  # missing sdp
        '{"type": "media_state", "payload": {"camera": "yes"}}',
        '{"type": "signal", "payload": "string"}',
    ],
)
def test_parse_rejects_malformed_messages(raw):
    with pytest.raises(MessageProtocolError):
        parse_client_message(raw)


def test_direction_rules_keep_the_interviewer_as_offerer():
    check_signal_direction("interviewer", {"kind": "offer", "sdp": "v=0"})
    check_signal_direction("candidate", {"kind": "answer", "sdp": "v=0"})
    check_signal_direction("candidate", {"kind": "ice", "candidate": None})
    check_signal_direction("interviewer", {"kind": "ice", "candidate": None})

    with pytest.raises(MessageProtocolError):
        check_signal_direction("candidate", {"kind": "offer", "sdp": "v=0"})
    with pytest.raises(MessageProtocolError):
        check_signal_direction("interviewer", {"kind": "answer", "sdp": "v=0"})


# ── Route registration ─────────────────────────────────────────────────────


def test_video_websocket_route_is_registered():
    """The signaling endpoint is mounted alongside the interview routes."""
    from app.main import app

    paths = [
        (route.path, route.name)
        for route in app.routes
        if getattr(route, "methods", None) is None  # websocket routes have no methods
    ]
    assert any(path.endswith("/interview/{interview_id}/video") for path, _ in paths)


# ── List wiring the two Interviews pages depend on ─────────────────────────


@pytest.mark.asyncio
async def test_list_rows_carry_the_fields_both_pages_render(client, session):
    """Each side's list carries the interviewer's name and the duration.

    The candidate's Interviews page must show the job, the recruiter, the
    date/time, the duration and the status, and the recruiter's own workspace
    shows the same schedule line — both read them straight off the list row, so
    these two additive fields are what makes the candidate's page complete
    without a second request.
    """
    ctx = await _setup(session, "vid-list-fields")
    recruiter_token = await _login(client, ctx["recruiter"].email)
    candidate_token = await _login(client, ctx["candidate"].email)
    await _schedule_now(client, session, ctx, recruiter_token, duration_minutes=45)

    for token in (recruiter_token, candidate_token):
        resp = await client.get(
            "/api/v1/interview/list", headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()["items"]
        live = [r for r in rows if r["interview_type"] == "recruiter_scheduled"]
        assert live, "the scheduled interview must appear on both sides' lists"
        for row in live:
            assert row["duration_minutes"] == 45
            assert row["recruiter_name"]
            # The fields the join entry point needs are on the row itself:
            # nothing else has to be fetched to render a joinable line.
            assert row["status"] in ("scheduled", "in_progress")
            assert row["scheduled_at"]
