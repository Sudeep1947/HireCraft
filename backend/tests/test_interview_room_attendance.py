"""Tests for Phase 14: the shared interview room and candidate attendance.

The contract under test
-----------------------

The gap these tests close: a recruiter could schedule an interview and a
candidate could see that it existed, but there was nothing to attend. Before this,
``InterviewStatus.IN_PROGRESS`` was honoured by every read path and by the Phase 11
reschedule/cancel/complete guards, yet no production code ever *wrote* it -- only
mock practice sessions did. The sole way a real interview left ``scheduled`` was a
recruiter asserting by hand that it had happened.

So, under test:

- **One room per interview, which both participants reach by the same
  ``interview_id``.** The candidate and the interviewer address the identical
  room; there is no second record and no second notion of who is in it.
- **The server owns the join window.** The room opens 15 minutes before the
  scheduled start -- a candidate who arrives early is not turned away -- and
  closes when the interview is scheduled to end. ``can_join`` and
  ``unavailable_reason`` come from the stored schedule and status, so the Join
  button the UI renders and the Join the server accepts cannot disagree.
- **Attendance, not a decision.** Joining records presence and starts the
  interview. It never completes it, never advances the application past
  ``INTERVIEW_SCHEDULED``, and never selects, offers or rejects anybody.
- **Reading the room is not attending.** Polling the room state to run a
  countdown must not mark anybody present and must not start the interview.
- **Idempotent attendance.** A reload, a reconnect or a second tab rejoins
  successfully instead of erroring, and only the first join is audited, because
  the record says *the interview began*, not how many times it was reloaded.
- **The window gates entry, not attendance.** Somebody already in the room stays
  joinable after it shuts, or a reload at the scheduled end would lock them out
  of the page they are sitting on.
- **Presence is reported without identity.** The candidate learns whether the
  interviewer is here and never who they are: the response has no name, id or
  email field to leak, and no scorecard, recommendation or recruiter note appears
  on it either.
- **Tenant isolation.** Another organization's recruiter and another candidate
  both get a 404 indistinguishable from a missing interview, so room state cannot
  be probed by interview id.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    ApplicationStatus,
    AuditEventType,
    InterviewStatus,
    InterviewType,
)
from app.domain.interview_room_schemas import (
    EARLY_JOIN_MINUTES,
    REASON_NO_SCHEDULE,
    REASON_NOT_JOINABLE_STATUS,
    REASON_WINDOW_CLOSED,
    REASON_WINDOW_NOT_OPEN,
)
from app.domain.models import AuditLog, Interview
from app.repositories.interview.interview import InterviewRepository
from app.repositories.jobs.job import JobApplicationRepository
from app.services.interview.interview_room_service import as_utc
from tests.test_application_interview_integration import (
    _auth,
    _interviews_url,
    _login,
    _schedule_body,
    _setup,
)

SECRET_NOTE = "INTERNAL-ONLY-9f02 private recruiter note"


def _room_url(interview_id) -> str:
    return f"/api/v1/interview/{interview_id}/room"


def _join_url(interview_id) -> str:
    return f"/api/v1/interview/{interview_id}/join"


async def _schedule_now(
    client: AsyncClient,
    session: AsyncSession,
    ctx,
    token: str,
    *,
    starts_in: timedelta = timedelta(minutes=5),
    duration_minutes: int = 60,
):
    """Schedule an interview whose window is open right now.

    ``starts_in`` defaults to five minutes out, which is inside the window: the
    default schedule body puts the interview three days ahead, where every
    attendance test would simply be refused and none of the interesting behaviour
    would be reached.
    """
    when = datetime.now(timezone.utc) + starts_in
    resp = await client.post(
        _interviews_url(ctx["app"].id),
        json=_schedule_body(
            scheduled_at=when.isoformat(),
            duration_minutes=duration_minutes,
            # One question keeps the generator cheap; the room does not read any.
            question_count=1,
        ),
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["interview_id"])


async def _room(client: AsyncClient, token: str, interview_id) -> dict:
    resp = await client.get(_room_url(interview_id), headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


# ═════════════════════════════════════════════════════════════════════
# 1. The window is the server's, and it is correct
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_window_bounds_are_derived_from_the_schedule(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Opens EARLY_JOIN_MINUTES before the start, closes at the scheduled end.

    Both bounds are echoed to the client so the countdown renders the same
    numbers the server enforces rather than a client-side recomputation that
    could disagree with them.
    """
    ctx = await _setup(session, "w1")
    token = await _login(client, ctx["recruiter"].email)
    start = datetime.now(timezone.utc) + timedelta(days=2)
    created = (
        await client.post(
            _interviews_url(ctx["app"].id),
            json=_schedule_body(
                scheduled_at=start.isoformat(),
                duration_minutes=45,
                question_count=1,
            ),
            headers=_auth(token),
        )
    ).json()
    interview_id = uuid.UUID(created["interview_id"])

    cand_token = await _login(client, ctx["candidate"].email)
    body = await _room(client, cand_token, interview_id)

    assert body["join_opens_at"] == (
        start - timedelta(minutes=EARLY_JOIN_MINUTES)
    ).isoformat().replace("+00:00", "Z")
    assert body["join_closes_at"] == (start + timedelta(minutes=45)).isoformat().replace(
        "+00:00", "Z",
    )
    # The server's clock, so a countdown does not depend on the viewer's device.
    assert body["server_time"] is not None
    # Two days out: not yet joinable, and the reason says so.
    assert body["can_join"] is False
    assert body["unavailable_reason"] == REASON_WINDOW_NOT_OPEN


@pytest.mark.asyncio
async def test_join_before_the_window_is_refused(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """An interview days away is not joinable, and the refusal is a 409.

    The read endpoint and the join endpoint agree: the read says
    ``join_window_not_open``, and the join is refused rather than quietly
    succeeding behind a disabled button.
    """
    ctx = await _setup(session, "w2")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(
        client, session, ctx, token, starts_in=timedelta(days=2),
    )

    cand_token = await _login(client, ctx["candidate"].email)
    state = await _room(client, cand_token, interview_id)
    assert state["can_join"] is False
    assert state["unavailable_reason"] == REASON_WINDOW_NOT_OPEN

    refused = await client.post(_join_url(interview_id), headers=_auth(cand_token))
    assert refused.status_code == 409, refused.text

    # Nothing was recorded, and the interview was not started.
    interview = await InterviewRepository(session).get(interview_id)
    assert interview.status == InterviewStatus.SCHEDULED.value
    assert interview.candidate_joined_at is None
    assert interview.started_at is None


@pytest.mark.asyncio
async def test_join_after_the_window_closes_is_refused(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The window ends when the interview is scheduled to end.

    Otherwise the room would stay open indefinitely and could be used to sit in
    on an interview days after it happened.
    """
    ctx = await _setup(session, "w3")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    # Move the schedule into the past instead of sleeping through the window.
    interview = await InterviewRepository(session).get(interview_id)
    interview.scheduled_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await session.flush()

    cand_token = await _login(client, ctx["candidate"].email)
    state = await _room(client, cand_token, interview_id)
    assert state["can_join"] is False
    assert state["unavailable_reason"] == REASON_WINDOW_CLOSED

    refused = await client.post(_join_url(interview_id), headers=_auth(cand_token))
    assert refused.status_code == 409, refused.text
    assert (await InterviewRepository(session).get(interview_id)).candidate_joined_at is None


@pytest.mark.asyncio
async def test_someone_already_inside_stays_joinable_after_the_window_shuts(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The window gates entry, not attendance.

    Without this, a candidate who joined on time and then reloaded the page at
    the scheduled end time would be locked out of the room they were sitting in.
    """
    ctx = await _setup(session, "w4")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    cand_token = await _login(client, ctx["candidate"].email)
    assert (await _room(client, cand_token, interview_id))["can_join"] is True
    assert (
        await client.post(_join_url(interview_id), headers=_auth(cand_token))
    ).status_code == 200

    interview = await InterviewRepository(session).get(interview_id)
    interview.scheduled_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await session.flush()

    # The candidate who is already in can still get back in...
    inside = await _room(client, cand_token, interview_id)
    assert inside["can_join"] is True
    assert inside["unavailable_reason"] is None
    assert inside["you_joined"] is True
    assert (
        await client.post(_join_url(interview_id), headers=_auth(cand_token))
    ).status_code == 200

    # ...but the interviewer, who never entered, is still locked out.
    recruiter_token = await _login(client, ctx["recruiter"].email)
    outside = await _room(client, recruiter_token, interview_id)
    assert outside["can_join"] is False
    assert outside["unavailable_reason"] == REASON_WINDOW_CLOSED
    assert (
        await client.post(_join_url(interview_id), headers=_auth(recruiter_token))
    ).status_code == 409


@pytest.mark.asyncio
async def test_interview_without_a_schedule_has_no_room(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """An interview nobody gave a time to must not be joinable forever."""
    ctx = await _setup(session, "w5")
    token = await _login(client, ctx["recruiter"].email)
    interview = Interview(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        recruiter_id=ctx["recruiter"].id,
        interview_type=InterviewType.RECRUITER_SCHEDULED.value,
        status=InterviewStatus.SCHEDULED.value,
        duration_minutes=60,
    )
    session.add(interview)
    await session.flush()

    state = await _room(client, token, interview.id)
    assert state["can_join"] is False
    assert state["unavailable_reason"] == REASON_NO_SCHEDULE
    assert state["join_opens_at"] is None
    assert state["join_closes_at"] is None

    refused = await client.post(_join_url(interview.id), headers=_auth(token))
    assert refused.status_code == 409, refused.text


# ═════════════════════════════════════════════════════════════════════
# 2. Joining records attendance and starts the interview
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_candidate_join_records_presence_and_starts_the_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The candidate joining is what finally writes IN_PROGRESS.

    This is the transition the Phase 11 guards always honoured and that no
    production path ever performed, so an interview's status now finally means it
    was actually held.
    """
    ctx = await _setup(session, "j1")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    cand_token = await _login(client, ctx["candidate"].email)
    resp = await client.post(_join_url(interview_id), headers=_auth(cand_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == InterviewStatus.IN_PROGRESS.value
    assert body["your_role"] == "candidate"
    assert body["you_joined"] is True
    assert body["can_join"] is True
    assert body["presence"]["candidate_joined"] is True
    assert body["presence"]["candidate_joined_at"] is not None
    # Nobody has joined for the interviewer yet.
    assert body["presence"]["interviewer_joined"] is False

    interview = await InterviewRepository(session).get(interview_id)
    assert interview.status == InterviewStatus.IN_PROGRESS.value
    assert interview.candidate_joined_at is not None
    assert interview.started_at is not None
    # One room per interview, and it was recorded when the interview was created.
    assert interview.room_id is not None


@pytest.mark.asyncio
async def test_both_participants_share_one_room_and_see_each_other(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Same room, same interview id, and each sees only that the other is here.

    There is no second room and no second attendance record: the interviewer
    joining does not create anything the candidate's room has to be told about,
    because they are the same row.
    """
    ctx = await _setup(session, "j2")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)
    cand_token = await _login(client, ctx["candidate"].email)

    recruiter_first = await client.post(
        _join_url(interview_id), headers=_auth(token),
    )
    assert recruiter_first.status_code == 200, recruiter_first.text
    assert recruiter_first.json()["your_role"] == "interviewer"

    candidate = await client.post(
        _join_url(interview_id), headers=_auth(cand_token),
    )
    assert candidate.status_code == 200, candidate.text
    body = candidate.json()

    # One room, seen by both.
    assert body["room_id"] == recruiter_first.json()["room_id"]
    # The candidate can see that the interviewer is present, and nothing more.
    assert body["presence"]["interviewer_joined"] is True
    assert body["presence"]["interviewer_joined_at"] is not None

    # The interviewer's view mirrors it.
    interviewer_view = await _room(client, token, interview_id)
    assert interviewer_view["presence"]["candidate_joined"] is True
    assert interviewer_view["your_role"] == "interviewer"
    assert interviewer_view["room_id"] == body["room_id"]


@pytest.mark.asyncio
async def test_rejoining_is_idempotent(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A reload cannot lock somebody out, and cannot rewrite when they arrived.

    The presence timestamp records that the interview began for this person, so a
    second tab or a refresh must not move it, and must not duplicate the audit
    row that says the same thing.
    """
    ctx = await _setup(session, "j3")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)
    cand_token = await _login(client, ctx["candidate"].email)

    first = await client.post(_join_url(interview_id), headers=_auth(cand_token))
    assert first.status_code == 200, first.text
    joined_at = (
        await InterviewRepository(session).get(interview_id)
    ).candidate_joined_at

    second = await client.post(_join_url(interview_id), headers=_auth(cand_token))
    assert second.status_code == 200, second.text
    assert second.json()["you_joined"] is True
    assert (
        await InterviewRepository(session).get(interview_id)
    ).candidate_joined_at == joined_at

    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.INTERVIEW_JOINED.value,
                AuditLog.user_id == ctx["candidate"].id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].details["first_join"] is True
    assert rows[0].details["started_interview"] is True


@pytest.mark.asyncio
async def test_second_participant_join_does_not_restart_the_interview(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """``started_at`` says when it began, so the second join cannot move it."""
    ctx = await _setup(session, "j4")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)
    cand_token = await _login(client, ctx["candidate"].email)

    await client.post(_join_url(interview_id), headers=_auth(token))
    started_at = (await InterviewRepository(session).get(interview_id)).started_at

    await client.post(_join_url(interview_id), headers=_auth(cand_token))
    interview = await InterviewRepository(session).get(interview_id)
    assert interview.started_at == started_at
    assert interview.status == InterviewStatus.IN_PROGRESS.value
    assert interview.recruiter_joined_at is not None
    assert interview.candidate_joined_at is not None

    # The recruiter's second visit is a non-first join and did not start anything.
    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.INTERVIEW_JOINED.value,
                AuditLog.user_id == ctx["recruiter"].id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_reading_the_room_is_not_attending(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Polling the room must not mark anybody present or start the interview.

    The frontend runs a countdown by re-reading this endpoint; if the read had a
    side effect, opening the page would be indistinguishable from attending and
    "did the candidate show up?" would become unanswerable.
    """
    ctx = await _setup(session, "j5")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)
    cand_token = await _login(client, ctx["candidate"].email)

    for _ in range(3):
        state = await _room(client, cand_token, interview_id)
        assert state["you_joined"] is False
        assert state["presence"]["candidate_joined"] is False

    interview = await InterviewRepository(session).get(interview_id)
    assert interview.candidate_joined_at is None
    assert interview.recruiter_joined_at is None
    assert interview.status == InterviewStatus.SCHEDULED.value
    assert interview.started_at is None


@pytest.mark.asyncio
async def test_joining_never_decides_anything(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Attendance is a fact, not a verdict.

    Joining starts the interview and leaves the application exactly where it was.
    Selection and rejection stay the explicit Phase 8 decision actions, which own
    their transitions, locking, history and notifications.
    """
    ctx = await _setup(session, "j6")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    before = await JobApplicationRepository(session).get(ctx["app"].id)
    decided_by_before, decided_at_before = before.decided_by, before.decided_at

    cand_token = await _login(client, ctx["candidate"].email)
    assert (
        await client.post(_join_url(interview_id), headers=_auth(cand_token))
    ).status_code == 200

    app = await JobApplicationRepository(session).get(ctx["app"].id)
    # Still the scheduled stage: joining did not complete the interview.
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value
    assert app.decided_by == decided_by_before
    assert app.decided_at == decided_at_before
    assert app.decision_reason_code is None
    assert app.status not in (
        ApplicationStatus.HIRED.value,
        ApplicationStatus.SELECTED.value,
        ApplicationStatus.OFFERED.value,
        ApplicationStatus.REJECTED.value,
    )


@pytest.mark.asyncio
async def test_completed_and_cancelled_interviews_close_the_room(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """A finished interview is evidence, so its room closes.

    Reopening one would rewrite history; the existing guards already treat
    ``completed`` as final for reschedule, cancel and complete, and the room
    agrees rather than inventing its own rule.
    """
    ctx = await _setup(session, "j7")
    token = await _login(client, ctx["recruiter"].email)
    completed_id = await _schedule_now(client, session, ctx, token)
    await client.post(
        f"{_interviews_url(ctx['app'].id)}/{completed_id}/complete",
        json={}, headers=_auth(token),
    )

    ctx2 = await _setup(session, "j8")
    token2 = await _login(client, ctx2["recruiter"].email)
    cancelled_id = await _schedule_now(client, session, ctx2, token2)
    await client.post(
        f"{_interviews_url(ctx2['app'].id)}/{cancelled_id}/cancel",
        json={}, headers=_auth(token2),
    )

    cand_token = await _login(client, ctx["candidate"].email)
    done = await _room(client, cand_token, completed_id)
    assert done["can_join"] is False
    assert done["unavailable_reason"] == REASON_NOT_JOINABLE_STATUS
    assert "completed" in done["message"].lower()
    assert (
        await client.post(_join_url(completed_id), headers=_auth(cand_token))
    ).status_code == 409

    cand_token2 = await _login(client, ctx2["candidate"].email)
    gone = await _room(client, cand_token2, cancelled_id)
    assert gone["can_join"] is False
    assert gone["unavailable_reason"] == REASON_NOT_JOINABLE_STATUS
    assert (
        await client.post(_join_url(cancelled_id), headers=_auth(cand_token2))
    ).status_code == 409


@pytest.mark.asyncio
async def test_mock_interviews_get_no_room(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """Practice sessions keep their own flow and record no attendance.

    Giving mock interviews a room would let practice be recorded as real
    attendance, and the two could no longer be told apart on the interview row.
    """
    ctx = await _setup(session, "j9")
    interview = Interview(
        job_id=ctx["job"].id,
        candidate_id=ctx["candidate"].id,
        interview_type=InterviewType.MOCK.value,
        status=InterviewStatus.SCHEDULED.value,
        scheduled_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).replace(
            tzinfo=None,
        ),
        duration_minutes=60,
    )
    session.add(interview)
    await session.flush()

    cand_token = await _login(client, ctx["candidate"].email)
    state = await _room(client, cand_token, interview.id)
    assert state["can_join"] is False
    assert state["unavailable_reason"] == REASON_NOT_JOINABLE_STATUS
    assert (
        await client.post(_join_url(interview.id), headers=_auth(cand_token))
    ).status_code == 409


# ═════════════════════════════════════════════════════════════════════
# 3. Authorization
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_room_is_invisible_to_other_tenants_and_candidates(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """An unauthorized room is indistinguishable from a missing interview."""
    ctx = await _setup(session, "z1")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    outsider_token = await _login(client, ctx["outsider"].email)
    # A second, unrelated organization and candidate. ``_setup`` already grants the
    # candidate role, so there is nothing more to assign.
    other_ctx = await _setup(session, "z2")
    other_token = await _login(client, other_ctx["candidate"].email)

    for bad_token in (outsider_token, other_token):
        for method, url in (
            ("get", _room_url(interview_id)),
            ("post", _join_url(interview_id)),
        ):
            resp = await getattr(client, method)(url, headers=_auth(bad_token))
            assert resp.status_code == 404, (method, resp.text)

    # And a genuinely missing id gives the same answer, so ids are not probeable.
    missing = await client.get(_room_url(uuid.uuid4()), headers=_auth(outsider_token))
    forbidden = await client.get(_room_url(interview_id), headers=_auth(outsider_token))
    assert missing.status_code == forbidden.status_code
    assert missing.json()["error"]["message"] == forbidden.json()["error"]["message"]

    # None of the refusals recorded anything.
    interview = await InterviewRepository(session).get(interview_id)
    assert interview.candidate_joined_at is None
    assert interview.recruiter_joined_at is None
    assert interview.status == InterviewStatus.SCHEDULED.value


# ═════════════════════════════════════════════════════════════════════
# 4. The candidate's view is an allowlist
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_candidate_room_exposes_presence_but_never_the_interviewer(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The response has no identity field to leak, checked key by key.

    Give the interview a scorecard with a recommendation and private recruiter
    notes, have both participants join, and assert none of it -- nor the
    interviewer's identity -- can appear on the candidate's room response.
    """
    from app.domain.models import HiringRecommendation, InterviewScorecard

    ctx = await _setup(session, "p1", job_title="Platform Engineer")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)

    session.add(
        InterviewScorecard(
            interview_id=interview_id,
            technical_skills=93,
            communication=88,
            overall_score=91,
            recommendation=HiringRecommendation.STRONGLY_RECOMMEND.value,
            hiring_confidence=95,
            recruiter_notes=SECRET_NOTE,
            ai_summary="Exceptional systems thinking.",
        )
    )
    await session.flush()

    cand_token = await _login(client, ctx["candidate"].email)
    # Both parties are in the room, so the candidate's response reports the other
    # one present -- which is the entire permitted disclosure.
    await client.post(_join_url(interview_id), headers=_auth(token))
    assert (
        await client.post(_join_url(interview_id), headers=_auth(cand_token))
    ).status_code == 200
    resp = await client.get(_room_url(interview_id), headers=_auth(cand_token))
    assert resp.status_code == 200, resp.text
    raw = resp.text
    body = resp.json()

    # No intelligence, and none of the private note text.
    for forbidden in (
        "overall_score",
        "recommendation",
        "hiring_confidence",
        "recruiter_notes",
        "ai_summary",
        "technical_skills",
        "scorecard",
        "evaluation",
        SECRET_NOTE,
        "Exceptional systems thinking",
        "strongly_recommend",
    ):
        assert forbidden not in raw, forbidden

    # No interviewer identity: not by id, name or email, under any key.
    for forbidden in (
        str(ctx["recruiter"].id),
        ctx["recruiter"].email,
        ctx["recruiter"].full_name,
        "recruiter_id",
        "recruiter_name",
        "interviewer_id",
        "interviewer_name",
    ):
        assert forbidden not in raw, forbidden

    # The exact allowlist, so a future field cannot be added by accident.
    assert set(body.keys()) == {
        "interview_id",
        "application_id",
        "interview_type",
        "stage",
        "status",
        "state",
        "your_role",
        "room_id",
        "scheduled_at",
        "rescheduled_at",
        "timezone",
        "duration_minutes",
        "join_opens_at",
        "join_closes_at",
        "server_time",
        "can_join",
        "unavailable_reason",
        "you_joined",
        "presence",
        "message",
    }
    assert set(body["presence"].keys()) == {
        "candidate_joined",
        "candidate_joined_at",
        "interviewer_joined",
        "interviewer_joined_at",
    }

    # What they *do* get: that the interviewer is here, and their own facts.
    assert body["presence"]["interviewer_joined"] is True
    assert body["you_joined"] is True
    assert body["your_role"] == "candidate"
    assert body["application_id"] == str(ctx["app"].id)


# ═════════════════════════════════════════════════════════════════════
# 5. Timezone normalization
# ═════════════════════════════════════════════════════════════════════


def test_as_utc_normalizes_both_forms() -> None:
    """A stored timestamp is compared safely whatever shape it comes back in.

    ``scheduled_at`` is written verbatim from the request and the SQLite test and
    development database does not persist an offset at all, so a value read back
    is naive. Comparing one with an aware ``datetime.now(timezone.utc)`` raises
    ``TypeError``, which is what this function exists to prevent.
    """
    aware = datetime(2026, 10, 2, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    # Converted, not reinterpreted: 15:00+05:30 is 09:30 UTC.
    assert as_utc(aware) == datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc)
    assert as_utc(aware).tzinfo is timezone.utc

    # A naive value is assumed UTC rather than local time, so the window cannot be
    # shifted by the server's own offset.
    assert as_utc(datetime(2026, 10, 2, 9, 30)) == datetime(
        2026, 10, 2, 9, 30, tzinfo=timezone.utc,
    )
    assert as_utc(None) is None


@pytest.mark.asyncio
async def test_window_is_exact_and_every_timestamp_is_aware(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """The bounds are the schedule's, and the client can do arithmetic on them.

    The offset-conversion logic itself is unit tested in
    ``test_as_utc_normalizes_both_forms`` rather than here, and deliberately so:
    ``scheduled_at`` is stored verbatim from the request body, and the SQLite test
    and development database drops the offset on the way in. A schedule given in
    ``+05:30`` therefore comes back as naive local wall-clock time and cannot be
    reconciled here -- an assertion about it would be testing SQLite's storage
    format, not this code. PostgreSQL, which is the deployed target, stores
    ``timestamptz`` and keeps the instant.
    """
    ctx = await _setup(session, "t1")
    token = await _login(client, ctx["recruiter"].email)

    created = (
        await client.post(
            _interviews_url(ctx["app"].id),
            json=_schedule_body(
                scheduled_at=datetime(
                    2026, 10, 2, 9, 30, tzinfo=timezone.utc,
                ).isoformat(),
                duration_minutes=30,
                question_count=1,
            ),
            headers=_auth(token),
        )
    ).json()
    interview_id = uuid.UUID(created["interview_id"])

    cand_token = await _login(client, ctx["candidate"].email)
    body = await _room(client, cand_token, interview_id)

    assert datetime.fromisoformat(body["join_opens_at"]) == datetime(
        2026, 10, 2, 9, 15, tzinfo=timezone.utc,
    )
    assert datetime.fromisoformat(body["join_closes_at"]) == datetime(
        2026, 10, 2, 10, 0, tzinfo=timezone.utc,
    )
    # Every timestamp the API returns is aware, so a browser can compare it
    # against its own clock without guessing the zone.
    for key in (
        "scheduled_at", "join_opens_at", "join_closes_at", "server_time",
    ):
        assert datetime.fromisoformat(body[key]).tzinfo is not None, key


# ═════════════════════════════════════════════════════════════════════
# 6. Audit
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_join_is_audited_with_the_role_and_the_transition(
    client: AsyncClient, session: AsyncSession,
) -> None:
    """"The candidate never joined" and "we have no record either way" must stay
    distinguishable, so the first join of each participant is on the trail.
    """
    ctx = await _setup(session, "au1")
    token = await _login(client, ctx["recruiter"].email)
    interview_id = await _schedule_now(client, session, ctx, token)
    cand_token = await _login(client, ctx["candidate"].email)

    await client.post(_join_url(interview_id), headers=_auth(cand_token))

    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.INTERVIEW_JOINED.value,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == ctx["candidate"].id
    assert row.organization_id == ctx["org"].id
    assert row.resource_type == "interview"
    assert row.resource_id == str(interview_id)
    assert row.details["role"] == "candidate"
    assert row.details["first_join"] is True
    assert row.details["started_interview"] is True
    assert row.details["application_id"] == str(ctx["app"].id)