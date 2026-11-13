import { useEffect, useRef, useState } from "react";
import {
  Camera,
  CameraOff,
  Mic,
  MicOff,
  Volume2,
  Briefcase,
  Calendar,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Sparkles,
  Info,
} from "lucide-react";
import { Button } from "../ui/Button";
import { IdentifierField } from "../ui/IdentifierField";
import type { InterviewRoomState } from "../../types/interview";
import {
  INTERVIEW_STAGE_LABELS,
  ROOM_REASON_LABELS,
  ROOM_STATE_COLORS,
  ROOM_STATE_LABELS,
} from "../../types/interview";

interface CandidateDeviceCheckProps {
  room: InterviewRoomState;
  jobTitle?: string;
  companyName?: string;
  interviewerName?: string;
  onJoin: () => void;
  isJoining: boolean;
  joinError: string | null;
  onGoBack: () => void;
}

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    dateStyle: "full",
    timeStyle: "short",
  });
}

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

export function CandidateDeviceCheck({
  room,
  jobTitle = "Software Engineer",
  companyName = "HireCraft Partner Organization",
  interviewerName = "Assigned Interviewer",
  onJoin,
  isJoining,
  joinError,
  onGoBack,
}: CandidateDeviceCheckProps) {
  // Device lists & selections
  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<string>("");
  const [selectedAudioId, setSelectedAudioId] = useState<string>("");

  // States
  const [cameraActive, setCameraActive] = useState(true);
  const [micActive, setMicActive] = useState(true);
  const [cameraPermission, setCameraPermission] = useState<"granted" | "denied" | "prompt">("prompt");
  const [micVolume, setMicVolume] = useState(0);
  const [speakerTestState, setSpeakerTestState] = useState<"idle" | "playing" | "passed">("idle");
  const [networkQuality, setNetworkQuality] = useState<"good" | "fair" | "offline">("good");

  // Media refs
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Network check
  useEffect(() => {
    const checkNetwork = () => {
      if (!navigator.onLine) {
        setNetworkQuality("offline");
      } else {
        setNetworkQuality("good");
      }
    };
    checkNetwork();
    window.addEventListener("online", checkNetwork);
    window.addEventListener("offline", checkNetwork);
    return () => {
      window.removeEventListener("online", checkNetwork);
      window.removeEventListener("offline", checkNetwork);
    };
  }, []);

  // Enumerate devices and acquire initial media preview
  useEffect(() => {
    let cancelled = false;

    async function setupPreview() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: selectedVideoId ? { deviceId: { exact: selectedVideoId } } : true,
          audio: selectedAudioId ? { deviceId: { exact: selectedAudioId } } : true,
        });

        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        streamRef.current = stream;
        setCameraPermission("granted");

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        // List devices
        const devices = await navigator.mediaDevices.enumerateDevices();
        const vList = devices.filter((d) => d.kind === "videoinput");
        const aList = devices.filter((d) => d.kind === "audioinput");
        setVideoDevices(vList);
        setAudioDevices(aList);

        if (!selectedVideoId && vList.length > 0) {
          setSelectedVideoId(vList[0].deviceId);
        }
        if (!selectedAudioId && aList.length > 0) {
          setSelectedAudioId(aList[0].deviceId);
        }

        // Setup audio level meter
        const audioTracks = stream.getAudioTracks();
        if (audioTracks.length > 0) {
          const AudioContextClass =
            window.AudioContext ||
            (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          if (AudioContextClass) {
            const ctx = new AudioContextClass();
            audioContextRef.current = ctx;
            const source = ctx.createMediaStreamSource(stream);
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            const checkVolume = () => {
              if (cancelled) return;
              analyser.getByteFrequencyData(dataArray);
              let sum = 0;
              for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
              }
              const average = sum / dataArray.length;
              setMicVolume(Math.min(100, Math.round((average / 128) * 100)));
              animFrameRef.current = requestAnimationFrame(checkVolume);
            };
            checkVolume();
          }
        }
      } catch (err) {
        console.warn("Camera/Mic device preview failed:", err);
        setCameraPermission("denied");
      }
    }

    void setupPreview();

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [selectedVideoId, selectedAudioId]);

  // Toggle camera in preview
  const toggleCamera = () => {
    const next = !cameraActive;
    setCameraActive(next);
    if (streamRef.current) {
      streamRef.current.getVideoTracks().forEach((t) => {
        t.enabled = next;
      });
    }
  };

  // Toggle mic in preview
  const toggleMic = () => {
    const next = !micActive;
    setMicActive(next);
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((t) => {
        t.enabled = next;
      });
    }
  };

  // Test sound chime generator
  const playSpeakerTestChime = () => {
    try {
      setSpeakerTestState("playing");
      const AudioContextClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;

      const ctx = new AudioContextClass();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
      osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.2); // E5
      osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.4); // G5
      osc.frequency.setValueAtTime(1046.5, ctx.currentTime + 0.6); // C6

      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1.2);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 1.2);

      setTimeout(() => {
        setSpeakerTestState("passed");
        void ctx.close();
      }, 1200);
    } catch (err) {
      console.warn("Speaker test failed:", err);
      setSpeakerTestState("idle");
    }
  };

  const unavailable = room.unavailable_reason
    ? ROOM_REASON_LABELS[room.unavailable_reason]
    : "Joining is not available for this interview";

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 animate-fadeIn font-sans" data-testid="video-room-ready">
      {/* ── Brand & Welcome Banner ── */}
      <div className="flex flex-wrap items-center justify-between rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 p-6 text-white shadow-xl">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600/30 border border-indigo-400/30 shadow-inner">
            <Sparkles className="h-7 w-7 text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase font-bold tracking-widest text-indigo-300">
                HireCraft AI • Interview Hub
              </span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                  ROOM_STATE_COLORS[room.state] ?? "bg-slate-700 text-white"
                }`}
              >
                {ROOM_STATE_LABELS[room.state] ?? room.state}
              </span>
            </div>
            <h1 className="text-2xl font-bold text-white mt-0.5">
              {INTERVIEW_STAGE_LABELS[room.stage] ?? "Interview"} Device & Audio Check
            </h1>
            <p className="text-sm text-slate-300 mt-1">
              Verify your camera, microphone, and speakers before entering the live interview room.
            </p>
          </div>
        </div>

        <div className="mt-3 sm:mt-0 flex items-center gap-2">
          <div className="rounded-xl bg-white/10 px-3.5 py-1.5 backdrop-blur-md border border-white/10 text-xs">
            <span className="text-slate-400">Duration: </span>
            <span className="font-semibold text-white">{room.duration_minutes || 60} mins</span>
          </div>
        </div>
      </div>

      {/* ── Main Two-Column Layout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN: Camera Preview & Device Controls (7 cols) */}
        <section className="lg:col-span-7 rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Pre-Interview Hardware Test</h2>
              <p className="text-xs text-slate-500">Ensure your equipment is configured and functioning</p>
            </div>
            <div className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 border border-emerald-100">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>{networkQuality === "good" ? "Network: Strong" : "Checking Network"}</span>
            </div>
          </div>

          {/* 1. Camera Preview Box */}
          <div className="relative aspect-video w-full rounded-2xl bg-slate-950 overflow-hidden shadow-inner border border-slate-800 flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`h-full w-full object-cover mirror ${cameraActive ? "block" : "hidden"}`}
            />

            {!cameraActive && (
              <div className="flex flex-col items-center justify-center gap-2 text-slate-400">
                <CameraOff className="h-12 w-12 text-slate-500" />
                <p className="text-sm font-medium">Camera is currently disabled</p>
                <span className="text-xs text-slate-500">Turn on camera to verify video preview</span>
              </div>
            )}

            {cameraPermission === "denied" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 p-4 text-center text-rose-300">
                <AlertTriangle className="h-10 w-10 text-rose-500 mb-2" />
                <p className="text-sm font-semibold">Camera Access Blocked</p>
                <p className="text-xs text-slate-400 max-w-sm mt-1">
                  Please allow camera and microphone permissions in your browser's address bar to join.
                </p>
              </div>
            )}

            {/* Quick floating controls over video */}
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-xl bg-slate-900/80 px-3 py-1.5 backdrop-blur-md border border-slate-700/60">
              <button
                onClick={toggleCamera}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition ${
                  cameraActive ? "bg-slate-800 text-white hover:bg-slate-700" : "bg-rose-600 text-white"
                }`}
                title={cameraActive ? "Turn off camera" : "Turn on camera"}
              >
                {cameraActive ? <Camera className="h-4 w-4" /> : <CameraOff className="h-4 w-4" />}
              </button>
              <button
                onClick={toggleMic}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition ${
                  micActive ? "bg-slate-800 text-white hover:bg-slate-700" : "bg-rose-600 text-white"
                }`}
                title={micActive ? "Mute microphone" : "Unmute microphone"}
              >
                {micActive ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* 2. Audio & Video Device Selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Camera Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Camera className="h-3.5 w-3.5 text-indigo-600" />
                Camera Device
              </label>
              <select
                value={selectedVideoId}
                onChange={(e) => setSelectedVideoId(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              >
                {videoDevices.map((dev, i) => (
                  <option key={dev.deviceId || i} value={dev.deviceId}>
                    {dev.label || `Camera ${i + 1}`}
                  </option>
                ))}
              </select>
            </div>

            {/* Mic Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Mic className="h-3.5 w-3.5 text-indigo-600" />
                Microphone Device
              </label>
              <select
                value={selectedAudioId}
                onChange={(e) => setSelectedAudioId(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              >
                {audioDevices.map((dev, i) => (
                  <option key={dev.deviceId || i} value={dev.deviceId}>
                    {dev.label || `Microphone ${i + 1}`}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 3. Live Microphone Level & Speaker Testing */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-slate-100 pt-4">
            {/* Live Mic Meter */}
            <div className="space-y-2 rounded-xl bg-slate-50 p-3 border border-slate-200/70">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700 flex items-center gap-1.5">
                  <Mic className="h-3.5 w-3.5 text-indigo-600" />
                  Microphone Input
                </span>
                <span className="font-mono text-slate-500">{micVolume}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-75"
                  style={{ width: `${micActive ? micVolume : 0}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-500">
                {micActive ? "Speak into your mic to test volume level." : "Microphone is muted."}
              </p>
            </div>

            {/* Speaker Sound Test */}
            <div className="space-y-2 rounded-xl bg-slate-50 p-3 border border-slate-200/70">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700 flex items-center gap-1.5">
                  <Volume2 className="h-3.5 w-3.5 text-indigo-600" />
                  Speaker Output
                </span>
                {speakerTestState === "passed" && (
                  <span className="text-[11px] font-semibold text-emerald-600 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" /> Audio Working
                  </span>
                )}
              </div>
              <Button
                size="sm"
                variant={speakerTestState === "playing" ? "secondary" : "outline"}
                className="w-full text-xs h-8 gap-1.5"
                onClick={playSpeakerTestChime}
                disabled={speakerTestState === "playing"}
              >
                <Volume2 className="h-3.5 w-3.5 text-indigo-600" />
                {speakerTestState === "playing" ? "Playing Chime..." : "Test Audio Output"}
              </Button>
              <p className="text-[11px] text-slate-500">Click above to play a sample audio chime.</p>
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: Interview Information & Join CTA (5 cols) */}
        <section className="lg:col-span-5 rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            <div className="border-b border-slate-100 pb-3">
              <span className="text-xs uppercase font-bold tracking-wider text-indigo-600">
                Session Information
              </span>
              <h2 className="text-lg font-bold text-slate-900 mt-1">{jobTitle}</h2>
              <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                <Building2 className="h-3.5 w-3.5 text-slate-400" />
                {companyName}
              </p>
            </div>

            {/* Scheduled details card */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-4 space-y-3 text-xs">
              <div className="flex items-start gap-2.5">
                <Calendar className="h-4 w-4 text-indigo-600 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-700">Interview Date & Time</span>
                  <p className="text-slate-600 mt-0.5 font-medium">{formatWhen(room.scheduled_at)}</p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Clock className="h-4 w-4 text-indigo-600 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-700">Expected Duration</span>
                  <p className="text-slate-600 mt-0.5 font-medium">
                    {room.duration_minutes ? `${room.duration_minutes} minutes` : "60 minutes"}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Briefcase className="h-4 w-4 text-indigo-600 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-700">Interview Type & Stage</span>
                  <p className="text-slate-600 mt-0.5 font-medium">
                    {INTERVIEW_STAGE_LABELS[room.stage] ?? "Recruiter"} Evaluation • 1-on-1 Live Video
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Sparkles className="h-4 w-4 text-indigo-600 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-700">Interviewer</span>
                  <p className="text-slate-600 mt-0.5 font-medium">{interviewerName}</p>
                </div>
              </div>
            </div>

            {/* Room ID Identifier */}
            <div className="rounded-xl border border-slate-200/70 p-3">
              <IdentifierField
                label="Room ID"
                value={room.room_id}
                size="sm"
                copyable
                hint="Both participants enter this same room automatically — no meeting ID needs to be typed."
              />
            </div>

            {/* Helpful reminders */}
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3.5 space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-900">
                <Info className="h-3.5 w-3.5 text-indigo-600" />
                <span>Helpful Reminders for Candidates</span>
              </div>
              <ul className="text-[11px] text-slate-600 space-y-1 list-disc pl-4">
                <li>Choose a quiet, well-lit environment.</li>
                <li>Keep a copy of your resume accessible.</li>
                <li>Speak clearly and feel free to ask for clarification.</li>
              </ul>
            </div>
          </div>

          {/* Join Interview Button and Access Conditions */}
          <div className="border-t border-slate-100 pt-4 space-y-3">
            <p className="text-xs text-slate-600">{room.message}</p>

            {room.can_join || room.you_joined ? (
              <Button
                onClick={onJoin}
                isLoading={isJoining}
                data-testid="join-interview"
                size="lg"
                className="w-full text-sm font-semibold h-11 shadow-md shadow-indigo-600/20"
              >
                {isJoining ? "Entering Interview Room..." : "Join Interview Room"}
              </Button>
            ) : (
              <>
                <Button size="lg" disabled title={unavailable} data-testid="join-interview" className="w-full h-11">
                  Join Interview Room
                </Button>
                <p className="text-xs text-slate-500">
                  {unavailable}
                  {room.join_opens_at && room.unavailable_reason === "join_window_not_open"
                    ? ` — opens ${describeGap(room.join_opens_at, room.server_time) ?? "shortly"}.`
                    : null}
                  {room.join_closes_at && room.unavailable_reason === "join_window_closed"
                    ? ` — closed ${describeGap(room.join_closes_at, room.server_time) ?? "at scheduled end"}.`
                    : null}
                </p>
              </>
            )}

            {joinError && <p className="text-xs text-rose-600 font-medium">{joinError}</p>}

            <Button size="sm" variant="ghost" onClick={onGoBack} className="w-full text-xs text-slate-500">
              Return to Previous Page
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
