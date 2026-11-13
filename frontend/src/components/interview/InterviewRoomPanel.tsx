import { formatDateTime, parseUTCDate } from "../../utils/dateTime";
/**
 * The shared interview room, for both participants.
 *
 * A recruiter and a candidate reach the same room by the same interview id, so
 * this one component serves both sides and takes no role or identity prop: what
 * it renders about who is present comes from the server's presence projection,
 * which reports only *that* someone joined and never who they are.
 *
 * The panel holds no join rule of its own. Whether joining is allowed, and the
 * reason it is not, arrive as `can_join` / `unavailable_reason` computed by the
 * backend from the stored schedule, duration and status. This component only
 * renders that verdict, which is what keeps a button it offers from being an
 * action the API would refuse — and a disabled button from hiding a reason a
 * participant is entitled to.
 *
 * Countdowns are measured against `server_time` rather than the browser clock,
 * so a device with a skewed clock still sees the same window everyone else sees.
 *
 * There is deliberately no Leave action. Presence records that someone attended,
 * and attendance is a fact about the interview, not a connection to be closed:
 * a fake "leave" would imply the server could un-record a participant, and would
 * hide someone who has genuinely arrived. Navigating away is the way out.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { interviewApi } from "../../api/interview";
import { Button } from "../ui/Button";
import { IdentifierField } from "../ui/IdentifierField";
import { getServerErrorMessage } from "../../utils/error";
import {
  INTERVIEW_STAGE_LABELS,
  ROOM_REASON_LABELS,
  ROOM_STATE_COLORS,
  ROOM_STATE_LABELS,
  type InterviewRoomState,
} from "../../types/interview";

interface InterviewRoomPanelProps {
  interviewId: string;
  /**
   * Called after a successful join that changed something, so a page holding a
   * recruiter's interview or scorecard can refresh it. Re-joining by the same
   * person is a no-op server-side, so this does not fire for a second join.
   */
  onJoined?: () => void;
  className?: string;
}

/** How often the other participant's arrival is re-read while the panel is open. */
const POLL_INTERVAL_MS = 30_000;

function formatWhen(value: string | null): string {
  return formatDateTime(value, "—");
}

/**
 * Describe the gap between an instant and the server's idea of now.
 *
 * Returns null when the target is not a usable date, so the caller omits the line
 * rather than printing "in NaN minutes".
 */
function describeGap(target: string | null, serverTime: string): string | null {
  if (!target) return null;
  const at = parseUTCDate(target)?.getTime() ?? NaN;
  const now = parseUTCDate(serverTime)?.getTime() ?? NaN;
  if (Number.isNaN(at) || Number.isNaN(now)) return null;
  const minutes = Math.round((at - now) / 60_000);
  if (minutes === 0) return "now";
  const magnitude = Math.abs(minutes);
  const unit = magnitude >= 60 ? pluralish(magnitude, "hour") : pluralish(magnitude, "minute");
  return minutes > 0 ? `in ${unit}` : `${unit} ago`;
}

function pluralish(amount: number, unit: string): string {
  return `${amount} ${unit}${amount === 1 ? "" : "s"}`;
}

export function InterviewRoomPanel({
  interviewId,
  onJoined,
  className = "",
}: InterviewRoomPanelProps) {
  const [room, setRoom] = useState<InterviewRoomState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  // Read as a ref so the polling effect does not re-subscribe on every join.
  const onJoinedRef = useRef(onJoined);
  onJoinedRef.current = onJoined;

  const load = useCallback(async () => {
    try {
      const next = await interviewApi.getInterviewRoom(interviewId);
      setRoom(next);
      setLoadError(null);
    } catch (err) {
      setLoadError(
        getServerErrorMessage(err, "The interview room could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, [interviewId]);

  useEffect(() => {
    setLoading(true);
    void load();
    // Re-read so the other participant's arrival appears without a manual
    // refresh. The interval is cleared on unmount and on an id change.
    const timer = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [load]);

  const join = async () => {
    setJoining(true);
    setJoinError(null);
    try {
      const next = await interviewApi.joinInterviewRoom(interviewId);
      setRoom(next);
      onJoinedRef.current?.();
    } catch (err) {
      setJoinError(
        getServerErrorMessage(err, "You could not be joined to this interview."),
      );
      // The refusal is the server's current truth, so re-read rather than
      // guess: the window may have opened or closed while the button was held.
      void load();
    } finally {
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <section
        className={`rounded-lg border border-slate-200/70 bg-white p-4 ${className}`}
        data-testid="interview-room"
      >
        <p className="text-sm text-ink-muted">Checking the interview room…</p>
      </section>
    );
  }

  if (loadError || !room) {
    return (
      <section
        className={`rounded-lg border border-rose-200 bg-rose-50/50 p-4 ${className}`}
        data-testid="interview-room"
      >
        <h2 className="text-sm font-semibold text-ink">Interview room</h2>
        <p className="mt-1 text-sm text-ink">
          {loadError ?? "The interview room could not be loaded."}
        </p>
      </section>
    );
  }

  const otherRole = room.your_role === "candidate" ? "interviewer" : "candidate";
  const otherPresent =
    room.your_role === "candidate"
      ? room.presence.interviewer_joined
      : room.presence.candidate_joined;
  const otherJoinedAt =
    room.your_role === "candidate"
      ? room.presence.interviewer_joined_at
      : room.presence.candidate_joined_at;
  const otherLabel = room.your_role === "candidate" ? "Interviewer" : "Candidate";

  const unavailable = room.unavailable_reason
    ? ROOM_REASON_LABELS[room.unavailable_reason]
    : "Joining is not available for this interview";

  return (
    <section
      className={`rounded-lg border border-slate-200/70 bg-white p-4 ${className}`}
      data-testid="interview-room"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">
          {INTERVIEW_STAGE_LABELS[room.stage] ?? "Interview"} room
        </h2>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            ROOM_STATE_COLORS[room.state] ?? "bg-surface-muted text-ink"
          }`}
        >
          {ROOM_STATE_LABELS[room.state] ?? room.state}
        </span>
      </div>

      <p className="mt-1 text-sm text-ink">{room.message}</p>

      {room.scheduled_at ? (
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-ink-muted">
              {room.state === "rescheduled" ? "New time" : "Scheduled"}
            </dt>
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
          {room.rescheduled_at ? (
            <div>
              <dt className="text-xs text-ink-muted">Rescheduled</dt>
              <dd className="font-medium text-ink">
                {formatWhen(room.rescheduled_at)}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {/* Attendance. Both labels are named by role, never by person, and the
          panel is shown to either side, so neither learns anything about the
          other's account beyond that they turned up. */}
      <div className="mt-3 flex flex-wrap gap-4 border-t border-slate-200/70 pt-3 text-sm">
        <div>
          <span className="text-ink-muted">You</span>{" "}
          <span className="font-medium text-ink">
            {room.you_joined ? "Joined" : "Not joined"}
          </span>
        </div>
        <div>
          <span className="text-ink-muted">{otherLabel}</span>{" "}
          <span className="font-medium text-ink">
            {otherPresent
              ? `Joined${
                  otherJoinedAt ? ` ${formatWhen(otherJoinedAt)}` : ""
                }`
              : "Not joined"}
          </span>
        </div>
      </div>

      {room.you_joined ? (
        <div className="mt-3">
          <p className="text-xs text-ink-muted">
            You are in this room. Attendance is recorded, so leaving this page does
            not remove it.
          </p>
        </div>
      ) : room.can_join ? (
        <div className="mt-3">
          <Button onClick={() => void join()} isLoading={joining} size="sm">
            {joining ? "Joining…" : "Join interview room"}
          </Button>
          {room.join_closes_at ? (
            <p className="mt-2 text-xs text-ink-muted">
              The join window closes{" "}
              {describeGap(room.join_closes_at, room.server_time) ?? "soon"}.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mt-3">
          <Button size="sm" disabled title={unavailable}>
            Join interview room
          </Button>
          <p className="mt-2 text-xs text-ink-muted">
            {unavailable}
            {room.join_opens_at && room.unavailable_reason === "join_window_not_open"
              ? ` — opens ${describeGap(room.join_opens_at, room.server_time) ?? "shortly"}.`
              : null}
          </p>
        </div>
      )}

      {/* The live room itself. Deliberately an anchor rather than a button:
          the panel's own button is the *attendance* join the Phase 14 test
          contract pins down, while this navigates to the shared video room
          where the actual call happens. It adds no API call — the room page
          re-reads and re-authorizes everything itself. */}
      {room.can_join || room.you_joined ? (
        <div className="mt-3 border-t border-slate-200/70 pt-3">
          <a
            href={`/interviews/${interviewId}/room`}
            className="text-sm font-medium text-primary-700 underline-offset-2 hover:underline"
          >
            Open video room
          </a>
          <p className="mt-1 text-xs text-ink-muted">
            The live camera and microphone room for this interview. Both sides
            enter the same room automatically — no meeting ID to type.
          </p>
        </div>
      ) : null}

      {joinError ? (
        <p className="mt-2 text-xs text-rose-700">{joinError}</p>
      ) : null}

      <div className="mt-3">
        <IdentifierField
          label="Room ID"
          value={room.room_id}
          size="sm"
          copyable
          hint={`The room for this interview. Your side is "${room.your_role}", the other is "${otherRole}".`}
        />
      </div>
    </section>
  );
}