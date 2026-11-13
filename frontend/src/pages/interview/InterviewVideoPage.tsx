/**
 * The live interview room page, shared by the recruiter and the candidate.
 *
 * One route (`/interviews/:id/room`) serves both sides, because the room
 * itself is one: the server resolved each caller's role at handshake time and
 * this page renders the same state for either role, branching only on what
 * the server said (`your_role`, `can_join`, `message`).
 *
 * The page adds no join rule of its own. Whether the call may start, when the
 * window opens and closes, and the wording of a refusal all come from
 * `getInterviewRoom` / `joinInterviewRoom` — the same endpoints the attendance
 * panel uses — so the button this page renders and the join the API accepts
 * cannot disagree. A candidate who arrives early, late, or to a cancelled
 * interview sees the server's own explanation, not a dead button.
 *
 * Flow: load room → Join Interview (records attendance, starts the interview
 * server-side) → live call → on end (either side leaving, or the interviewer
 * ending), the interviewer with an application-linked interview is shown the
 * feedback panel; the candidate sees a calm "ended" state.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { Button } from "../../components/ui/Button";
import { IdentifierField } from "../../components/ui/IdentifierField";
import { InterviewVideoRoom } from "../../components/interview/InterviewVideoRoom";
import { InterviewEndPanel } from "../../components/interview/InterviewEndPanel";
import { CandidateDeviceCheck } from "../../components/interview/CandidateDeviceCheck";
import { CandidateInterviewCompletion } from "../../components/interview/CandidateInterviewCompletion";
import { interviewApi } from "../../api/interview";
import { getServerErrorMessage } from "../../utils/error";
import {
  INTERVIEW_STAGE_LABELS,
  ROOM_REASON_LABELS,
  ROOM_STATE_COLORS,
  ROOM_STATE_LABELS,
  type InterviewRoomState,
} from "../../types/interview";

type Phase = "loading" | "refused" | "ready" | "in_call" | "ended";

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/**
 * Describe the gap between an instant and the server's idea of now, so an
 * early or late participant reads the same window the server enforces (measured
 * against `server_time`, not the possibly-skewed device clock).
 */
function describeGap(target: string | null, serverTime: string): string | null {
  if (!target) return null;
  const at = new Date(target).getTime();
  const now = new Date(serverTime).getTime();
  if (Number.isNaN(at) || Number.isNaN(now)) return null;
  const minutes = Math.round((at - now) / 60_000);
  if (minutes === 0) return "now";
  const magnitude = Math.abs(minutes);
  const unit =
    magnitude >= 60
      ? `${Math.round(magnitude / 60)} hour${Math.round(magnitude / 60) === 1 ? "" : "s"}`
      : `${magnitude} minute${magnitude === 1 ? "" : "s"}`;
  return minutes > 0 ? `in ${unit}` : `${unit} ago`;
}

export function InterviewVideoPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("loading");
  const [room, setRoom] = useState<InterviewRoomState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const next = await interviewApi.getInterviewRoom(id);
      setRoom(next);
      setLoadError(null);
      // Only flips the *initial* load: a re-read while in a call or after an
      // end must never kick the participant back to the pre-join screen.
      setPhase((current) => (current === "loading" ? "ready" : current));
    } catch (err) {
      setLoadError(
        getServerErrorMessage(err, "The interview room could not be loaded."),
      );
      setPhase("refused");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const join = async () => {
    if (!id) return;
    setJoining(true);
    setJoinError(null);
    try {
      const next = await interviewApi.joinInterviewRoom(id);
      setRoom(next);
      setPhase("in_call");
    } catch (err) {
      setJoinError(
        getServerErrorMessage(err, "You could not join this interview."),
      );
      // The refusal is the server's current truth; re-read it rather than
      // guess — the window may have moved while the button was held.
      void load();
    } finally {
      setJoining(false);
    }
  };

  if (phase === "loading") {
    return <LoadingSpinner size="lg" className="mt-20" />;
  }

  if (phase === "refused" || !room) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <section className="rounded-xl border border-rose-200 bg-rose-50/50 p-6">
          <h1 className="text-lg font-semibold text-ink">Interview room</h1>
          <p className="mt-2 text-sm text-ink">
            {loadError ?? "This interview room is not available."}
          </p>
        </section>
        <Button size="sm" variant="outline" onClick={() => navigate(-1)}>
          Go back
        </Button>
      </div>
    );
  }

  if (phase === "ended") {
    if (room.your_role === "candidate") {
      return (
        <CandidateInterviewCompletion
          room={room}
          canRejoin={room.can_join || room.you_joined}
          onRejoin={() => setPhase("in_call")}
        />
      );
    }

    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <section className="rounded-xl border border-slate-200/70 bg-white p-6">
          <h1 className="text-lg font-semibold text-ink">
            {INTERVIEW_STAGE_LABELS[room.stage] ?? "Interview"} ended
          </h1>
          <p className="mt-2 text-sm text-ink">
            The call is over. Attendance is recorded; the interview is completed from the feedback panel.
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            Your attendance stays recorded. Leaving a call never removes it.
          </p>
        </section>

        {room.application_id ? (
          <InterviewEndPanel
            applicationId={room.application_id}
            interviewId={room.interview_id}
            stage={room.stage}
          />
        ) : null}

        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            navigate(
              room.stage === "hr" ? "/hr/dashboard" : "/recruiter/interviews",
            )
          }
        >
          Back to interviews
        </Button>
      </div>
    );
  }

  if (phase === "ready") {
    if (room.your_role === "candidate") {
      return (
        <CandidateDeviceCheck
          room={room}
          onJoin={() => void join()}
          isJoining={joining}
          joinError={joinError}
          onGoBack={() => navigate(-1)}
        />
      );
    }

    const unavailable = room.unavailable_reason
      ? ROOM_REASON_LABELS[room.unavailable_reason]
      : "Joining is not available for this interview";

    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <section
          className="rounded-xl border border-slate-200/70 bg-white p-6"
          data-testid="video-room-ready"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-lg font-semibold text-ink">
              {INTERVIEW_STAGE_LABELS[room.stage] ?? "Interview"} interview
            </h1>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                ROOM_STATE_COLORS[room.state] ?? "bg-surface-muted text-ink"
              }`}
            >
              {ROOM_STATE_LABELS[room.state] ?? room.state}
            </span>
          </div>

          <p className="mt-2 text-sm text-ink">{room.message}</p>

          {room.scheduled_at ? (
            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-muted">Scheduled</dt>
                <dd className="font-medium text-ink">
                  {formatWhen(room.scheduled_at)}
                </dd>
              </div>
              {room.duration_minutes ? (
                <div>
                  <dt className="text-xs text-ink-muted">Duration</dt>
                  <dd className="font-medium text-ink">
                    {room.duration_minutes} minutes
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          <div className="mt-4">
            {room.can_join || room.you_joined ? (
              <Button
                onClick={() => void join()}
                isLoading={joining}
                data-testid="join-interview"
              >
                {joining ? "Joining…" : "Join interview"}
              </Button>
            ) : (
              <>
                <Button size="sm" disabled title={unavailable} data-testid="join-interview">
                  Join interview
                </Button>
                <p className="mt-2 text-xs text-ink-muted">
                  {unavailable}
                  {room.join_opens_at &&
                  room.unavailable_reason === "join_window_not_open"
                    ? ` — opens ${describeGap(room.join_opens_at, room.server_time) ?? "shortly"}.`
                    : null}
                  {room.join_closes_at &&
                  room.unavailable_reason === "join_window_closed"
                    ? ` — closed ${describeGap(room.join_closes_at, room.server_time) ?? "at the scheduled end"}.`
                    : null}
                </p>
              </>
            )}
            {joinError ? (
              <p className="mt-2 text-sm text-rose-700">{joinError}</p>
            ) : null}
          </div>

          <div className="mt-4 border-t border-slate-200/70 pt-3">
            <IdentifierField
              label="Room ID"
              value={room.room_id}
              size="sm"
              copyable
              hint="Both participants enter this same room automatically — no meeting ID needs to be typed."
            />
          </div>
        </section>

        <Button size="sm" variant="ghost" onClick={() => navigate(-1)}>
          Go back
        </Button>
      </div>
    );
  }

  // phase === "in_call"
  return (
    <div className="w-full max-w-[1600px] mx-auto">
      <InterviewVideoRoom
        key={room.interview_id}
        interviewId={room.interview_id}
        applicationId={room.application_id}
        stage={room.stage}
        scheduledAt={room.scheduled_at}
        durationMinutes={room.duration_minutes}
        roomId={room.room_id}
        role={room.your_role}
        peerPresentOnJoin={
          room.your_role === "candidate"
            ? room.presence.interviewer_joined
            : room.presence.candidate_joined
        }
        onEnded={() => setPhase("ended")}
        /* Leaving the *call* is not the call ending: back to the ready screen,
           where the server's own verdict decides whether rejoining is still
           possible (attendance is recorded either way). */
        onLeft={() => setPhase("ready")}
      />
    </div>
  );
}
