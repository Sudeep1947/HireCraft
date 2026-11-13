# Phase 1 — Recruiter↔Candidate Real-Time Video Interviews

## Root cause of the original issue ("a scheduled interview could not actually be attended")

The backend already scheduled interviews (Phase 11), already gave each interview
one shared room with a **server-owned join window and attendance** (Phase 14),
and already had feedback + advance/reject (Phase 15). Two things were missing,
and neither was a bug in what existed:

1. **There was no real-time media layer anywhere in the repository.** No
   WebSocket endpoint, no WebRTC, no `getUserMedia`. The room endpoints only
   *recorded attendance*; nothing carried audio or video, so a scheduled
   interview could reach `in_progress` and still be impossible to actually
   attend.
2. **The candidate had no "Join Interview" entry point.** The only room surface
   (`InterviewRoomPanel`) was embedded inside the application-detail pages. The
   candidate's Interview History list showed no recruiter, time, duration or
   join action, and no page existed where both participants entered the *same*
   live room.

The fix therefore adds the missing media layer and the missing entry points,
reusing every existing interview/room/feedback/notification service rather than
building a parallel system.

## TODO

### Backend
- [x] `app/services/interview/interview_video_service.py`
      - `resolve_video_access()` — the *same* JWT decode, active-user check,
        role gate and room authorization the REST endpoints use, delegating to
        `InterviewRoomService.get_room_state`, so the signaling socket cannot
        grant more than `GET/POST /interview/{id}/room` would.
      - `VideoRoomHub` — in-memory, two role slots per interview (candidate /
        interviewer); reload replaces the stale socket (close 4409); presence
        events; media-state memory for late joiners; `end_interview` closes both
        sides and **writes nothing**.
      - `parse_client_message` + `check_signal_direction` — protocol validation,
        and interviewer-offers / candidate-answers direction rules.
- [x] `app/api/v1/interview_video.py` — `WS /api/v1/interview/{id}/video`,
      query-param JWT (browsers cannot send an `Authorization` header on a WS
      handshake). Refusals are delivered as *application* close codes
      (4401 / 4404 / 4403): the socket is accepted only so the coded close can
      be delivered, because a handshake rejected before `accept()` surfaces to
      a browser as an anonymous 1006 — an uninterpretable network failure in
      place of "your room is not open yet". A refused socket never joins the
      hub and never reaches the relay loop.
- [x] Register the router in `app/main.py`.
- [x] `interview_service.list_interviews`: additive `recruiter_name` and
      `duration_minutes` (the candidate list needs them; backward compatible).
- [x] `interview_schemas.InterviewListItem`: the two new fields had to be added
      to the **response model** as well — FastAPI's `response_model` re-validates
      through Pydantic and silently stripped the serializer's output, so the
      fields never reached the client until the model carried them. This was
      caught by the list-fields test below, not by inspection.
- [x] Tests `backend/tests/test_interview_video_room.py` — 29 tests, including
      one that walks the exact rows both Interviews pages render.

### Frontend
- [x] `src/types/interview.ts`: additive list fields + the signaling types.
- [x] `src/api/interviewVideo.ts`: signaling URL builder (separate module, so
      components whose tests pin an explicit `interviewApi` mock list are
      untouched).
- [x] `src/components/interview/InterviewVideoRoom.tsx`: real WebRTC —
      `getUserMedia` with permission-denied / no-device handling and audio-only
      fallback, `RTCPeerConnection` (P2P, STUN), camera on/off + mic mute via
      `track.enabled`, connection + participant status, reconnect backoff, ICE
      restart (offerer side), Leave, and an interviewer-only **End interview**.
- [x] `src/components/interview/InterviewEndPanel.tsx`: complete → feedback
      (three 0–100 ratings, derived recommendation, internal notes) → Advance
      for further review / Reject (controlled reason + internal note), all
      through the existing Phase 11/15 endpoints; server refusals are shown.
- [x] `src/pages/interview/InterviewVideoPage.tsx`: one route for both sides;
      server-driven gating, clear early/late-join messages with a server-clock
      countdown, Join Interview, live call, ended state (recruiter gets the
      feedback panel; candidate never does).
- [x] Route `/interviews/:id/room` in `App.tsx`.
- [x] `InterviewHistory.tsx` (candidate): job, recruiter, date/time, duration,
      status + **Join Interview**; list is already scoped to the logged-in
      candidate by the server.
- [x] `InterviewWorkspace.tsx` (recruiter): schedule line + **Join Interview**.
- [x] `InterviewRoomPanel.tsx`: an "Open video room" **anchor** (no new API
      calls, no button-role changes, so its existing tests keep passing).
- [x] `vite.config.ts`: `ws: true` on the `/api` proxy so the signaling socket
      works in dev (HTTP proxying unaffected).
- [x] `frontend/.env.example`: documented the optional `VITE_ICE_SERVERS`.
- [x] Tests: `InterviewVideoPage.test.tsx` (7), `InterviewEndPanel.test.tsx`.

### Verification
- [x] Backend: new video tests green; the interview suites
      (`test_interview.py`, `test_interview_room_attendance.py`,
      `test_application_interview_integration.py`, `test_interview_video_room.py`)
      green — 111 passed.
- [x] Backend: full suite run (see the final report).
- [x] Frontend: `tsc -b` clean; full `vitest run` — 32 files / 421 tests passed.
- [ ] `npm run lint`: **cannot run in this repository** — ESLint is not in
      `devDependencies` and no `eslint.config.*` / `.eslintrc.*` exists (checked
      at the repo root and in `frontend/`). This is pre-existing and unrelated
      to these changes; `tsc -b` (part of `npm run build`) is the project's
      working static check and is clean.

### Notes
- **No database migration is needed.** Signaling state is in-memory by design
  (a server restart drops sockets; both sides simply rejoin through the same
  HTTP join path), and no new columns were added — the only backend schema
  surface touched is the additive list-serializer fields.
- **No third-party video provider and no provider secrets.** Audio/video is
  peer-to-peer WebRTC; the backend only relays SDP/ICE. Default ICE is public
  STUN; `VITE_ICE_SERVERS` can add TURN for strict NATs.

---

## Fix — Recruiter Interview Analytics page ("Failed to load analytics")

### Root cause
`GET /api/v1/interview/analytics` raised `sqlalchemy.exc.MissingGreenlet`
(`interview_analytics.py`, `_category_performance`): the engine read the
`question.answer.evaluation` relationship chain off freshly selected questions,
and that chain is **lazily loaded** — illegal in an async session. It only
triggered once a recruiter had a **completed, answered** interview, which is
why the page worked while the database was empty and broke as soon as real
interviews existed. The 500 surfaced in the UI as the generic error, with no
retry and no server detail.

### Changes
- [x] `backend/app/services/interview/interview_analytics.py`:
      `_category_performance` now selects `(category, overall_score)` with one
      explicit three-table join — no relationship traversal, and the per-
      completed-interview N+1 becomes a single query. Nothing else in the
      service changed; the endpoint's recruiter/HR scoping is untouched.
- [x] `backend/tests/test_application_interview_integration.py`: regression
      test — a completed interview with an answered, evaluated question and a
      scorecard must aggregate (200 with the real numbers), read fresh from
      the DB (`expire_all`) so nothing is served from the test's identity map.
- [x] `frontend/src/pages/interview/InterviewAnalytics.tsx`: same layout and
      charts; added a Retry button on failure, the server's own error message
      via `getServerErrorMessage` (raw exception text never shown), and an
      honest empty state ("No interviews yet") instead of a grid of zeroes.
      No hardcoded or fabricated statistics anywhere.
- [x] `frontend/src/pages/interview/InterviewAnalytics.test.tsx`: 4 tests —
      real stats rendered, empty state, retry flow, fallback message.

### Verification
- [x] Backend: `test_application_interview_integration.py` + `test_interview.py`
      — 66 passed (includes the new regression test and the pre-existing
      analytics scoping/tenant-isolation test).
- [x] Frontend: `tsc -b` clean; `InterviewAnalytics.test.tsx` 4 passed;
      `src/pages/interview` suite 26 passed.
- No configuration or database migration required.
