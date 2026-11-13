/**
 * Upgrade: Recruiter and HR Video Interview Interface.
 *
 * Enterprise video conferencing room for HireCraft AI:
 * - Peer-to-peer WebRTC video/audio stream separation.
 * - Active speaker detection with glowing ring via Web Audio API AnalyserNode.
 * - Screen sharing with dynamic track replacement (RTCRtpSender.replaceTrack) and auto restore.
 * - In-call real-time text chat relayed through WebSocket signaling with unread badge.
 * - Live speech-to-text captions (Web Speech API) & transcription feed.
 * - Audio/Video input device settings modal.
 * - Session recording with MediaRecorder, consent dialog, and .webm file download.
 * - Full candidate profile, resume, interview history, AI assistant & scorecard sidebar.
 * - Role-based permissions: Interviewer (End call, Record, AI, Scorecard), Candidate (Leave call, Chat, Hand raise).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Monitor,
  MonitorOff,
  MessageSquare,
  Users,
  Hand,
  Subtitles,
  Settings,
  FileText,
  Disc,
  Maximize2,
  PhoneOff,
  Copy,
  Check,
  AlertCircle,
  Wifi,
} from "lucide-react";
import { Button } from "../ui/Button";
import { videoSignalingUrl } from "../../api/interviewVideo";
import { interviewApi } from "../../api/interview";
import { getApplicationScreeningDetail } from "../../api/screening";
import { InterviewSidebar, type SidebarTab, type ScorecardState } from "./InterviewSidebar";
import { InterviewSettingsModal } from "./InterviewSettingsModal";
import {
  VIDEO_CLOSE_CODES,
  type VideoCallStatus,
  type VideoClientMessage,
  type VideoServerMessage,
  type VideoSignalingRole,
  type ApplicationInterviewEvidence,
} from "../../types/interview";
import type { ApplicationScreeningDetailResponse } from "../../types/screening";

interface InterviewVideoRoomProps {
  interviewId: string;
  role: VideoSignalingRole;
  peerPresentOnJoin: boolean;
  onEnded: () => void;
  onLeft?: () => void;
  className?: string;
  applicationId?: string | null;
  stage?: string;
  scheduledAt?: string | null;
  durationMinutes?: number | null;
  roomId?: string;
}

const DEFAULT_ICE_SERVERS: RTCIceServer[] = [
  { urls: "stun:stun.l.google.com:19302" },
];

function iceServers(): RTCIceServer[] {
  const raw = import.meta.env.VITE_ICE_SERVERS;
  if (!raw) return DEFAULT_ICE_SERVERS;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : DEFAULT_ICE_SERVERS;
  } catch {
    return DEFAULT_ICE_SERVERS;
  }
}

const RECONNECT_BACKOFF_MS = [1_000, 2_000, 5_000, 10_000];
const PING_INTERVAL_MS = 25_000;

const STATUS_TEXT: Record<VideoCallStatus, string> = {
  idle: "Preparing your camera…",
  connecting: "Connecting…",
  waiting: "Waiting for participant to join…",
  connecting_peer: "Connecting to participant…",
  connected: "Connected",
  reconnecting: "Reconnecting…",
  failed: "Connection lost",
  ended: "Interview completed",
};

const STATUS_DOT: Record<VideoCallStatus, string> = {
  idle: "bg-slate-300",
  connecting: "bg-amber-400 animate-pulse",
  waiting: "bg-amber-400",
  connecting_peer: "bg-amber-400 animate-pulse",
  connected: "bg-emerald-500",
  reconnecting: "bg-amber-400 animate-pulse",
  failed: "bg-rose-500",
  ended: "bg-slate-400",
};

export function InterviewVideoRoom({
  interviewId,
  role,
  peerPresentOnJoin,
  onEnded,
  onLeft,
  className = "",
  applicationId = null,
  stage = "recruiter",
  scheduledAt: _scheduledAt = null,
  durationMinutes: _durationMinutes = 60,
  roomId = "",
}: InterviewVideoRoomProps) {
  // ── Connection and Media State ──────────────────────────────────────
  const [status, setStatus] = useState<VideoCallStatus>("connecting");
  const [cameraOn, setCameraOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [peerPresent, setPeerPresent] = useState(peerPresentOnJoin);
  const [peerCamera, setPeerCamera] = useState(true);
  const [peerMic, setPeerMic] = useState(true);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [socketError, setSocketError] = useState<string | null>(null);

  // ── Layout and UI States ───────────────────────────────────────────
  const [layoutMode, setLayoutMode] = useState<"grid" | "speaker">("grid");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<SidebarTab>(role === "interviewer" ? "profile" : "instructions");
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showEndConfirmModal, setShowEndConfirmModal] = useState(false);
  const [showRecordingModal, setShowRecordingModal] = useState(false);
  const [copiedRoomId, setCopiedRoomId] = useState(false);

  // ── Active Speaker Detection ───────────────────────────────────────
  const [localSpeaking, setLocalSpeaking] = useState(false);
  const [remoteSpeaking, setRemoteSpeaking] = useState(false);

  // ── Screen Share State ─────────────────────────────────────────────
  const [isSharingScreen, setIsSharingScreen] = useState(false);

  // ── Hand Raise State ──────────────────────────────────────────────
  const [handRaised, setHandRaised] = useState(false);
  const [peerHandRaised, setPeerHandRaised] = useState(false);

  // ── Live Captions & Transcription ──────────────────────────────────
  const [captionsEnabled, setCaptionsEnabled] = useState(false);
  const [currentCaption, setCurrentCaption] = useState<{ speaker: string; text: string } | null>(null);
  const [transcriptEntries, setTranscriptEntries] = useState<
    Array<{ id: string; speaker: string; text: string; time: string }>
  >([]);

  // ── Real-Time Chat ────────────────────────────────────────────────
  const [chatMessages, setChatMessages] = useState<
    Array<{ id: string; senderRole: VideoSignalingRole; senderName: string; text: string; time: string }>
  >([]);
  const [unreadChatCount, setUnreadChatCount] = useState(0);

  // ── Call Recording ─────────────────────────────────────────────────
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  // ── Duration Timer ─────────────────────────────────────────────────
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // ── Candidate & Application Context ────────────────────────────────
  const [candidateName, setCandidateName] = useState<string>("Candidate");
  const [candidateEmail, setCandidateEmail] = useState<string>("");
  const [jobTitle, setJobTitle] = useState<string>("Software Engineer");
  const [screeningDetail, setScreeningDetail] = useState<ApplicationScreeningDetailResponse | null>(null);
  const [applicationInterviews, setApplicationInterviews] = useState<ApplicationInterviewEvidence | null>(null);

  // ── Interviewer Scorecard & Notes ──────────────────────────────────
  const [notes, setNotes] = useState("");
  const [notesSaved, setNotesSaved] = useState(false);
  const [isSubmittingScorecard, setIsSubmittingScorecard] = useState(false);
  const [scorecardData, setScorecardData] = useState<ScorecardState>({
    technical: 4,
    problemSolving: 4,
    experience: 4,
    communication: 4,
    roleSpecific: 4,
    overall: 4.0,
    notes: "",
    strengths: "",
    weaknesses: "",
    recommendation: "recommend",
  });

  // ── Audio/Video Device Selections ──────────────────────────────────
  const [selectedAudioId, setSelectedAudioId] = useState<string>("");
  const [selectedVideoId, setSelectedVideoId] = useState<string>("");

  // ── DOM & WebRTC References ────────────────────────────────────────
  const containerRef = useRef<HTMLDivElement | null>(null);
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteStreamRef = useRef<MediaStream | null>(null);
  const originalCameraTrackRef = useRef<MediaStreamTrack | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  // Audio Analysers for active speaker detection
  const audioContextRef = useRef<AudioContext | null>(null);
  const localAnalyserRef = useRef<AnalyserNode | null>(null);
  const remoteAnalyserRef = useRef<AnalyserNode | null>(null);
  const speechRecognitionRef = useRef<any>(null);

  // Refs mirroring state for socket/peer callbacks
  const roleRef = useRef(role);
  const peerPresentRef = useRef(peerPresentOnJoin);
  const cameraRef = useRef(true);
  const micRef = useRef(true);
  const endedRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const socketGenRef = useRef(0);

  const isInterviewer = role === "interviewer";

  // ── Format helpers ────────────────────────────────────────────────
  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainingSecs = secs % 60;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    if (hours > 0) {
      return `${hours.toString().padStart(2, "0")}:${remMins.toString().padStart(2, "0")}:${remainingSecs.toString().padStart(2, "0")}`;
    }
    return `${remMins.toString().padStart(2, "0")}:${remainingSecs.toString().padStart(2, "0")}`;
  };

  // ── Live Elapsed Duration Timer ────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // ── Recording Duration Timer ───────────────────────────────────────
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (isRecording) {
      timer = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setRecordingSeconds(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isRecording]);

  // ── Fetch Interview Details & Candidate Context ────────────────────
  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const detail = await interviewApi.getInterviewDetail(interviewId);
        if (!active) return;
        if (detail.candidate_name) setCandidateName(detail.candidate_name);
        if (detail.candidate_email) setCandidateEmail(detail.candidate_email);
        if (detail.job_title) setJobTitle(detail.job_title);

        const appId = applicationId || detail.application_id;
        if (appId && isInterviewer) {
          try {
            const screening = await getApplicationScreeningDetail(appId);
            if (active && screening) {
              setScreeningDetail(screening);
              if (screening.candidate.name) setCandidateName(screening.candidate.name);
              if (screening.candidate.email) setCandidateEmail(screening.candidate.email);
              if (screening.job.title) setJobTitle(screening.job.title);
            }
          } catch {
            // Screening context optional
          }

          try {
            const interviews = await interviewApi.getApplicationInterviews(appId);
            if (active && interviews) {
              setApplicationInterviews(interviews);
            }
          } catch {
            // Evidence optional
          }
        }
      } catch (err) {
        console.error("Failed to load interview context:", err);
      }
    }

    void loadData();

    return () => {
      active = false;
    };
  }, [interviewId, applicationId, isInterviewer]);

  // ── WebSocket Send Callback ────────────────────────────────────────
  const send = useCallback((message: VideoClientMessage) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }, []);

  const reportMediaState = useCallback(() => {
    send({
      type: "media_state",
      payload: { camera: cameraRef.current, mic: micRef.current },
    });
  }, [send]);

  // ── Setup Audio Analyser for Active Speaker Detection ──────────────
  const setupAudioAnalysers = useCallback(() => {
    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextClass();
      }
      const ctx = audioContextRef.current;

      // Local track analyser
      if (localStreamRef.current && localStreamRef.current.getAudioTracks().length > 0) {
        try {
          const localSource = ctx.createMediaStreamSource(localStreamRef.current);
          const localAnalyser = ctx.createAnalyser();
          localAnalyser.fftSize = 256;
          localSource.connect(localAnalyser);
          localAnalyserRef.current = localAnalyser;
        } catch {
          // ignore
        }
      }

      // Remote track analyser
      if (remoteStreamRef.current && remoteStreamRef.current.getAudioTracks().length > 0) {
        try {
          const remoteSource = ctx.createMediaStreamSource(remoteStreamRef.current);
          const remoteAnalyser = ctx.createAnalyser();
          remoteAnalyser.fftSize = 256;
          remoteSource.connect(remoteAnalyser);
          remoteAnalyserRef.current = remoteAnalyser;
        } catch {
          // ignore
        }
      }

      // Speaker polling loop
      const checkAudioLevels = () => {
        if (endedRef.current) return;

        if (localAnalyserRef.current && micRef.current) {
          const dataArray = new Uint8Array(localAnalyserRef.current.frequencyBinCount);
          localAnalyserRef.current.getByteFrequencyData(dataArray);
          const avg = dataArray.reduce((acc, val) => acc + val, 0) / dataArray.length;
          setLocalSpeaking(avg > 25);
        } else {
          setLocalSpeaking(false);
        }

        if (remoteAnalyserRef.current) {
          const dataArray = new Uint8Array(remoteAnalyserRef.current.frequencyBinCount);
          remoteAnalyserRef.current.getByteFrequencyData(dataArray);
          const avg = dataArray.reduce((acc, val) => acc + val, 0) / dataArray.length;
          setRemoteSpeaking(avg > 25);
        } else {
          setRemoteSpeaking(false);
        }

        requestAnimationFrame(checkAudioLevels);
      };

      requestAnimationFrame(checkAudioLevels);
    } catch (err) {
      console.warn("Active speaker audio context not initialized:", err);
    }
  }, []);

  // ── Acquire Local Camera & Microphone ──────────────────────────────
  const acquireMedia = useCallback(
    async (audioDeviceId?: string, videoDeviceId?: string) => {
      try {
        const constraints: MediaStreamConstraints = {
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            ...(videoDeviceId ? { deviceId: { exact: videoDeviceId } } : {}),
          },
          audio: audioDeviceId ? { deviceId: { exact: audioDeviceId } } : true,
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        localStreamRef.current = stream;
        originalCameraTrackRef.current = stream.getVideoTracks()[0] || null;
        setMediaError(null);

        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }

        setupAudioAnalysers();
        return stream;
      } catch (err) {
        const name = err instanceof DOMException ? err.name : "";
        if (name === "NotAllowedError" || name === "PermissionDeniedError") {
          setMediaError(
            "Camera and microphone access was blocked. Please allow browser permissions and rejoin.",
          );
        } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
          setMediaError("No camera or microphone found on this device.");
        } else {
          setMediaError("Your camera and microphone could not be started.");
        }

        try {
          const audioOnly = await navigator.mediaDevices.getUserMedia({ audio: true });
          localStreamRef.current = audioOnly;
          if (localVideoRef.current) {
            localVideoRef.current.srcObject = audioOnly;
          }
          setCameraOn(false);
          cameraRef.current = false;
          setupAudioAnalysers();
          return audioOnly;
        } catch {
          return null;
        }
      }
    },
    [setupAudioAnalysers],
  );

  // ── WebRTC Peer Connection ─────────────────────────────────────────
  const ensurePeer = useCallback(() => {
    if (peerRef.current) return peerRef.current;

    const peer = new RTCPeerConnection({ iceServers: iceServers() });
    peerRef.current = peer;

    remoteStreamRef.current = new MediaStream();
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = remoteStreamRef.current;
    }

    peer.onicecandidate = (event) => {
      send({
        type: "signal",
        payload: {
          kind: "ice",
          candidate: event.candidate ? event.candidate.toJSON() : null,
        },
      });
    };

    peer.ontrack = (event) => {
      remoteStreamRef.current?.addTrack(event.track);
      if (remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = remoteStreamRef.current;
      }
      setupAudioAnalysers();
    };

    peer.onconnectionstatechange = () => {
      switch (peer.connectionState) {
        case "connected":
          setStatus("connected");
          reconnectAttemptRef.current = 0;
          break;
        case "connecting":
          setStatus((current) =>
            current === "connected" || current === "reconnecting" ? current : "connecting_peer",
          );
          break;
        case "disconnected":
          setStatus("reconnecting");
          break;
        case "failed":
          if (roleRef.current === "interviewer") {
            void restartIce();
          } else {
            setStatus("reconnecting");
          }
          break;
        case "closed":
          break;
      }
    };

    const local = localStreamRef.current;
    if (local) {
      for (const track of local.getTracks()) {
        peer.addTrack(track, local);
      }
    }

    return peer;
  }, [send, setupAudioAnalysers]);

  const restartIce = useCallback(async () => {
    const peer = peerRef.current;
    if (!peer || roleRef.current !== "interviewer") return;
    try {
      setStatus("reconnecting");
      const offer = await peer.createOffer({ iceRestart: true });
      await peer.setLocalDescription(offer);
      send({ type: "signal", payload: { kind: "offer", sdp: offer.sdp ?? "" } });
    } catch {
      // Reconnect handled by socket fallback
    }
  }, [send]);

  // ── Server Message Dispatcher ──────────────────────────────────────
  const handleServerMessage = useCallback(
    async (message: VideoServerMessage) => {
      const peer = ensurePeer();

      switch ((message as any).type) {
        case "joined": {
          const m = message as any;
          setPeerPresent(m.payload.peer_present);
          peerPresentRef.current = m.payload.peer_present;
          if (m.payload.peer_media) {
            setPeerCamera(m.payload.peer_media.camera);
            setPeerMic(m.payload.peer_media.mic);
          }
          reportMediaState();

          if (roleRef.current === "interviewer" && m.payload.peer_present) {
            setStatus("connecting_peer");
            const offer = await peer.createOffer();
            await peer.setLocalDescription(offer);
            send({
              type: "signal",
              payload: { kind: "offer", sdp: offer.sdp ?? "" },
            });
          } else {
            setStatus("waiting");
          }
          return;
        }

        case "peer_joined": {
          setPeerPresent(true);
          peerPresentRef.current = true;
          if (roleRef.current === "interviewer") {
            setStatus("connecting_peer");
            const offer = await peer.createOffer();
            await peer.setLocalDescription(offer);
            send({
              type: "signal",
              payload: { kind: "offer", sdp: offer.sdp ?? "" },
            });
          } else {
            setStatus("connecting_peer");
          }
          return;
        }

        case "peer_left": {
          setPeerPresent(false);
          peerPresentRef.current = false;
          setStatus((current) => (current === "connected" ? "reconnecting" : "waiting"));
          return;
        }

        case "signal": {
          const payload = (message as any).payload;
          if (payload.kind === "offer") {
            await peer.setRemoteDescription(
              new RTCSessionDescription({ type: "offer", sdp: payload.sdp }),
            );
            const answer = await peer.createAnswer();
            await peer.setLocalDescription(answer);
            send({
              type: "signal",
              payload: { kind: "answer", sdp: answer.sdp ?? "" },
            });
          } else if (payload.kind === "answer") {
            await peer.setRemoteDescription(
              new RTCSessionDescription({ type: "answer", sdp: payload.sdp }),
            );
          } else if (payload.kind === "ice") {
            try {
              await peer.addIceCandidate(
                payload.candidate ? new RTCIceCandidate(payload.candidate) : null,
              );
            } catch {
              // Ignore late candidates
            }
          }
          return;
        }

        case "media_state": {
          const payload = (message as any).payload;
          if (payload.role !== roleRef.current) {
            setPeerCamera(payload.camera);
            setPeerMic(payload.mic);
          }
          return;
        }

        case "chat": {
          const p = (message as any).payload;
          const senderName = p.sender || (p.from === "interviewer" ? "Interviewer" : candidateName);
          const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          setChatMessages((prev) => [
            ...prev,
            { id: String(Date.now()), senderRole: p.from, senderName, text: p.text, time },
          ]);
          if (!sidebarOpen || activeTab !== "chat") {
            setUnreadChatCount((prev) => prev + 1);
          }
          return;
        }

        case "hand_raise": {
          const p = (message as any).payload;
          if (p.from !== roleRef.current) {
            setPeerHandRaised(p.raised);
          }
          return;
        }

        case "caption": {
          const p = (message as any).payload;
          const speaker = p.from === "interviewer" ? "Interviewer" : candidateName;
          setCurrentCaption({ speaker, text: p.text });
          const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          setTranscriptEntries((prev) => [
            ...prev,
            { id: String(Date.now()), speaker, text: p.text, time },
          ]);
          return;
        }

        case "ended": {
          endedRef.current = true;
          setStatus("ended");
          onEnded();
          return;
        }

        case "pong":
          return;
      }
    },
    [candidateName, ensurePeer, onEnded, reportMediaState, send, sidebarOpen, activeTab],
  );

  // ── WebSocket Connection Loop ──────────────────────────────────────
  const connectSocket = useCallback(() => {
    const gen = ++socketGenRef.current;
    let socket: WebSocket;
    try {
      socket = new WebSocket(videoSignalingUrl(interviewId));
    } catch {
      setSocketError("Connection to the interview server could not be opened.");
      setStatus("failed");
      return;
    }
    socketRef.current = socket;

    socket.onopen = () => {
      if (gen !== socketGenRef.current) return;
      reconnectAttemptRef.current = 0;
      setSocketError(null);
      if (!endedRef.current) {
        setStatus((current) => (current === "connected" ? current : "connecting"));
      }
      pingTimerRef.current = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL_MS);
    };

    socket.onmessage = (event) => {
      if (gen !== socketGenRef.current) return;
      let message: VideoServerMessage;
      try {
        message = JSON.parse(String(event.data));
      } catch {
        return;
      }
      void handleServerMessage(message);
    };

    socket.onclose = (event) => {
      if (gen !== socketGenRef.current) return;
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      if (endedRef.current) return;

      if (event.code === VIDEO_CLOSE_CODES.ended) {
        endedRef.current = true;
        setStatus("ended");
        onEnded();
        return;
      }
      if (event.code === VIDEO_CLOSE_CODES.replaced) {
        setSocketError("This room was opened in another browser tab.");
        setStatus("failed");
        return;
      }
      if (event.code === VIDEO_CLOSE_CODES.forbidden) {
        setSocketError("Access to this interview room is closed.");
        setStatus("failed");
        return;
      }

      const attempt = reconnectAttemptRef.current;
      if (attempt >= RECONNECT_BACKOFF_MS.length) {
        setSocketError("Could not reconnect to the interview server. Please rejoin.");
        setStatus("failed");
        return;
      }
      setStatus("reconnecting");
      reconnectTimerRef.current = setTimeout(() => {
        reconnectAttemptRef.current = attempt + 1;
        connectSocket();
      }, RECONNECT_BACKOFF_MS[attempt]);
    };
  }, [handleServerMessage, interviewId, onEnded]);

  // ── Lifecycle: Acquire Media and Mount Socket ──────────────────────
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const stream = await acquireMedia();
      if (cancelled) return;
      if (localVideoRef.current && stream) {
        localVideoRef.current.srcObject = stream;
      }
      connectSocket();
    })();

    return () => {
      cancelled = true;
      socketGenRef.current += 1;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);

      const socket = socketRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        try {
          socket.send(JSON.stringify({ type: "leave" }));
        } catch {
          // ignore
        }
        socket.close();
      }

      peerRef.current?.close();
      peerRef.current = null;

      for (const track of localStreamRef.current?.getTracks() ?? []) {
        track.stop();
      }
      localStreamRef.current = null;

      if (speechRecognitionRef.current) {
        try {
          speechRecognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Controls: Camera, Microphone, Screen Sharing ────────────────────
  const toggleCamera = () => {
    const next = !cameraRef.current;
    cameraRef.current = next;
    setCameraOn(next);
    for (const track of localStreamRef.current?.getVideoTracks() ?? []) {
      track.enabled = next;
    }
    reportMediaState();
  };

  const toggleMic = () => {
    const next = !micRef.current;
    micRef.current = next;
    setMicOn(next);
    for (const track of localStreamRef.current?.getAudioTracks() ?? []) {
      track.enabled = next;
    }
    reportMediaState();
  };

  const startScreenShare = async () => {
    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });
      const screenTrack = screenStream.getVideoTracks()[0];
      if (!screenTrack) return;

      setIsSharingScreen(true);

      const sender = peerRef.current?.getSenders().find((s) => s.track?.kind === "video");
      if (sender) {
        await sender.replaceTrack(screenTrack);
      }

      if (localVideoRef.current) {
        localVideoRef.current.srcObject = screenStream;
      }

      screenTrack.onended = () => {
        void stopScreenShare();
      };
    } catch (err) {
      console.warn("Screen share cancelled or not allowed:", err);
      setIsSharingScreen(false);
    }
  };

  const stopScreenShare = async () => {
    setIsSharingScreen(false);
    const cameraTrack = originalCameraTrackRef.current;
    const sender = peerRef.current?.getSenders().find((s) => s.track?.kind === "video");
    if (sender && cameraTrack) {
      await sender.replaceTrack(cameraTrack);
    }
    if (localVideoRef.current && localStreamRef.current) {
      localVideoRef.current.srcObject = localStreamRef.current;
    }
  };

  const toggleScreenShare = () => {
    if (isSharingScreen) {
      void stopScreenShare();
    } else {
      void startScreenShare();
    }
  };

  // ── Raise Hand ────────────────────────────────────────────────────
  const toggleRaiseHand = () => {
    const next = !handRaised;
    setHandRaised(next);
    send({
      type: "hand_raise",
      payload: { raised: next },
    });
  };

  // ── Live Captions & Speech Recognition ────────────────────────────
  const toggleCaptions = () => {
    if (captionsEnabled) {
      setCaptionsEnabled(false);
      setCurrentCaption(null);
      if (speechRecognitionRef.current) {
        try {
          speechRecognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
      return;
    }

    const SpeechRecognitionClass =
      (window as unknown as { SpeechRecognition: any }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition: any }).webkitSpeechRecognition;

    if (!SpeechRecognitionClass) {
      alert("Live speech recognition is not supported in this browser.");
      return;
    }

    try {
      const recognition = new SpeechRecognitionClass();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onresult = (event: any) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript.trim()) {
          const speaker = isInterviewer ? "Interviewer (You)" : `${candidateName} (You)`;
          setCurrentCaption({ speaker, text: transcript });
          send({
            type: "caption",
            payload: { text: transcript },
          });

          if (event.results[event.results.length - 1].isFinal) {
            const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            setTranscriptEntries((prev) => [
              ...prev,
              { id: String(Date.now()), speaker, text: transcript, time },
            ]);
          }
        }
      };

      recognition.onerror = () => {
        // continue
      };

      recognition.onend = () => {
        if (captionsEnabled) {
          try {
            recognition.start();
          } catch {
            // ignore
          }
        }
      };

      recognition.start();
      speechRecognitionRef.current = recognition;
      setCaptionsEnabled(true);
    } catch (err) {
      console.warn("Speech recognition error:", err);
    }
  };

  // ── In-Call Chat Send ─────────────────────────────────────────────
  const handleSendMessage = (text: string) => {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const senderName = isInterviewer ? "You (Interviewer)" : `${candidateName} (You)`;
    setChatMessages((prev) => [
      ...prev,
      { id: String(Date.now()), senderRole: role, senderName, text, time },
    ]);
    send({
      type: "chat",
      payload: { text, sender: isInterviewer ? "Interviewer" : candidateName },
    });
  };

  // ── Call Recording ─────────────────────────────────────────────────
  const startRecording = () => {
    setShowRecordingModal(false);
    try {
      const streamToRecord = new MediaStream();
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((t) => streamToRecord.addTrack(t));
      }
      if (remoteStreamRef.current) {
        remoteStreamRef.current.getTracks().forEach((t) => streamToRecord.addTrack(t));
      }

      recordedChunksRef.current = [];
      const recorder = new MediaRecorder(streamToRecord, { mimeType: "video/webm;codecs=vp9,opus" });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          recordedChunksRef.current.push(e.data);
        }
      };
      recorder.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: "video/webm" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        a.download = `HireCraft-Interview-${interviewId}.webm`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }, 100);
      };
      recorder.start(1000);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      console.error("Recording error:", err);
      alert("Recording could not be started.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // ── Fullscreen Toggle ──────────────────────────────────────────────
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  };

  // ── End and Leave Call ─────────────────────────────────────────────
  const leave = () => {
    endedRef.current = true;
    send({ type: "leave" });
    socketRef.current?.close();
    onLeft?.();
  };

  const endInterview = () => {
    send({ type: "end" });
    endedRef.current = true;
    setStatus("ended");
    setShowEndConfirmModal(false);
    onEnded();
  };

  const copyRoomId = () => {
    void navigator.clipboard.writeText(roomId || interviewId);
    setCopiedRoomId(true);
    setTimeout(() => setCopiedRoomId(false), 2000);
  };

  // ── Save Draft / Submit Scorecard ──────────────────────────────────
  const handleSaveScorecardDraft = async () => {
    try {
      await interviewApi.createScorecard(interviewId, {
        technical_skills: scorecardData.technical * 20,
        communication: scorecardData.communication * 20,
        teamwork: scorecardData.roleSpecific * 20,
        leadership: 70,
        problem_solving: scorecardData.problemSolving * 20,
        culture_fit: 80,
        learning_ability: 80,
        recommendation: scorecardData.recommendation,
        hiring_confidence: 85,
        recruiter_notes: `${notes}\n\nStrengths: ${scorecardData.strengths}\nAreas for Improvement: ${scorecardData.weaknesses}`,
      });
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 3000);
    } catch (err) {
      console.error("Save scorecard draft error:", err);
    }
  };

  const handleSubmitScorecard = async () => {
    setIsSubmittingScorecard(true);
    try {
      await handleSaveScorecardDraft();
    } finally {
      setIsSubmittingScorecard(false);
    }
  };

  const handleSaveNotes = async () => {
    try {
      await interviewApi.addNotes(interviewId, notes);
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 2500);
    } catch {
      // ignore
    }
  };

  const handleDeviceSelect = (audioId: string, videoId: string) => {
    setSelectedAudioId(audioId);
    setSelectedVideoId(videoId);
    void acquireMedia(audioId, videoId);
  };

  const participantsList = [
    {
      role: (isInterviewer ? "interviewer" : "candidate") as VideoSignalingRole,
      name: isInterviewer ? "Interviewer (You)" : `${candidateName} (You)`,
      isPresent: true,
      micOn,
      cameraOn,
      handRaised,
    },
    {
      role: (isInterviewer ? "candidate" : "interviewer") as VideoSignalingRole,
      name: isInterviewer ? candidateName : "Interviewer",
      isPresent: peerPresent,
      micOn: peerMic,
      cameraOn: peerCamera,
      handRaised: peerHandRaised,
    },
  ];

  return (
    <div
      ref={containerRef}
      className={`relative flex flex-col h-[calc(100vh-100px)] min-h-[640px] w-full rounded-2xl bg-white border border-slate-200/90 shadow-xl overflow-hidden font-sans ${className}`}
      data-testid="interview-video-room"
    >
      {/* ── 1. HEADER SECTION ────────────────────────────────────────── */}
      <header className="flex flex-wrap items-center justify-between border-b border-slate-200/80 bg-slate-50/90 px-4 py-3 gap-2 z-10">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-xs">
            <Video className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900 leading-tight">
                {stage === "hr" ? "HR Interview Room" : "Recruiter Interview Room"}
              </h1>
              <span className="rounded-full bg-indigo-100/80 px-2 py-0.5 text-[11px] font-semibold text-indigo-800">
                {stage === "hr" ? "HR Stage" : "Recruiter Stage"}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
              <span className="font-medium text-slate-700">{candidateName}</span>
              <span>•</span>
              <span className="truncate max-w-[200px]">{jobTitle}</span>
              <span>•</span>
              <button
                onClick={copyRoomId}
                className="flex items-center gap-1 font-mono text-slate-400 hover:text-indigo-600 transition"
                title="Copy Room ID"
              >
                <span>ID: {(roomId || interviewId).slice(0, 8)}...</span>
                {copiedRoomId ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
              </button>
            </div>
          </div>
        </div>

        {/* Center Indicators: Status, Timer, REC */}
        <div className="flex items-center gap-3">
          {/* Status Badge */}
          <div className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 shadow-xs border border-slate-200/70 text-xs font-medium text-slate-700">
            <span className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[status]}`} aria-hidden="true" />
            <span role="status">{STATUS_TEXT[status]}</span>
          </div>

          {/* Duration Timer */}
          <div className="flex items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1 text-xs font-mono font-bold text-white shadow-xs">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
            <span>{formatTime(elapsedSeconds)}</span>
          </div>

          {/* Recording Badge */}
          {isRecording && (
            <div className="flex items-center gap-1.5 rounded-full bg-rose-600 px-3 py-1 text-xs font-mono font-bold text-white shadow-xs animate-pulse">
              <span className="h-2 w-2 rounded-full bg-white" />
              <span>REC {formatTime(recordingSeconds)}</span>
            </div>
          )}

          {/* Network Quality */}
          <div className="flex items-center gap-1 text-slate-400 text-xs" title="Network Connection: Good">
            <Wifi className="h-4 w-4 text-emerald-500" />
          </div>
        </div>

        {/* Right Action Buttons */}
        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="hidden sm:flex items-center rounded-xl bg-slate-200/70 p-0.5 text-xs">
            <button
              onClick={() => setLayoutMode("grid")}
              className={`rounded-lg px-2.5 py-1 font-medium transition ${
                layoutMode === "grid" ? "bg-white text-slate-800 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Grid
            </button>
            <button
              onClick={() => setLayoutMode("speaker")}
              className={`rounded-lg px-2.5 py-1 font-medium transition ${
                layoutMode === "speaker" ? "bg-white text-slate-800 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Speaker
            </button>
          </div>

          {/* Toggle Sidebar Button */}
          <button
            onClick={() => setSidebarOpen((prev) => !prev)}
            className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition ${
              sidebarOpen
                ? "bg-indigo-50 border-indigo-200 text-indigo-700"
                : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Workspace</span>
            {unreadChatCount > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                {unreadChatCount}
              </span>
            )}
          </button>

          {/* End / Leave Button */}
          {isInterviewer ? (
            <Button
              size="sm"
              variant="danger"
              onClick={() => setShowEndConfirmModal(true)}
              data-testid="end-interview"
              className="font-medium shadow-xs"
            >
              End interview
            </Button>
          ) : (
            <Button
              size="sm"
              variant="danger"
              onClick={leave}
              data-testid="leave-interview"
              className="font-medium shadow-xs"
            >
              Leave interview
            </Button>
          )}
        </div>
      </header>

      {/* ── 2. MAIN CALL & SIDEBAR SPLIT ─────────────────────────────── */}
      <div className="relative flex-1 flex overflow-hidden bg-slate-950">
        {/* VIDEO DISPLAY AREA */}
        <main className="relative flex-1 flex flex-col justify-center items-center p-4 overflow-hidden">
          {/* Status alerts */}
          {mediaError && (
            <div className="absolute top-4 left-4 right-4 z-20 flex items-center justify-between rounded-xl bg-amber-500/95 px-4 py-2 text-xs font-medium text-white shadow-lg backdrop-blur-xs">
              <span className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                {mediaError}
              </span>
              <button onClick={() => setMediaError(null)} className="underline hover:opacity-80">
                Dismiss
              </button>
            </div>
          )}

          {socketError && (
            <div className="absolute top-4 left-4 right-4 z-20 flex items-center justify-between rounded-xl bg-rose-600/95 px-4 py-2 text-xs font-medium text-white shadow-lg backdrop-blur-xs">
              <span className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                {socketError}
              </span>
              <button
                onClick={() => {
                  setSocketError(null);
                  connectSocket();
                }}
                className="rounded bg-white/20 px-2 py-0.5 hover:bg-white/30"
              >
                Retry
              </button>
            </div>
          )}

          {/* GRID LAYOUT (Side-by-side) */}
          {layoutMode === "grid" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full h-full max-h-[720px] items-center">
              {/* Tile 1: Local Participant */}
              <div
                className={`relative flex items-center justify-center h-full max-h-[560px] w-full rounded-2xl bg-slate-900 overflow-hidden shadow-md border border-slate-800 transition-all duration-300 ${
                  localSpeaking ? "ring-3 ring-indigo-500 shadow-indigo-500/30" : ""
                }`}
              >
                <video
                  ref={localVideoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`h-full w-full object-cover mirror ${cameraOn ? "block" : "hidden"}`}
                  data-testid="local-video"
                />

                {/* Camera off placeholder */}
                {!cameraOn && (
                  <div className="flex flex-col items-center justify-center gap-2 text-center text-slate-400">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full bg-slate-800 text-2xl font-bold text-indigo-400 border border-slate-700 shadow-inner">
                      {isInterviewer ? "HR" : "CD"}
                    </div>
                    <span className="text-xs text-slate-400">Your camera is off</span>
                  </div>
                )}

                {/* Local Video Tag Overlays */}
                <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-lg bg-slate-900/80 px-2.5 py-1 text-xs text-white backdrop-blur-xs">
                  <span className="font-semibold">{isInterviewer ? "You (Interviewer)" : "You (Candidate)"}</span>
                  {!micOn && (
                    <span className="flex items-center text-rose-400" title="Microphone muted">
                      <MicOff className="h-3 w-3" />
                    </span>
                  )}
                </div>

                {handRaised && (
                  <div className="absolute top-3 left-3 flex items-center gap-1 rounded-full bg-amber-500 px-2.5 py-1 text-xs font-bold text-white shadow-md">
                    <Hand className="h-3.5 w-3.5" />
                    <span>Hand Raised</span>
                  </div>
                )}
              </div>

              {/* Tile 2: Remote Participant */}
              <div
                className={`relative flex items-center justify-center h-full max-h-[560px] w-full rounded-2xl bg-slate-900 overflow-hidden shadow-md border border-slate-800 transition-all duration-300 ${
                  remoteSpeaking ? "ring-3 ring-indigo-500 shadow-indigo-500/30" : ""
                }`}
              >
                <video
                  ref={remoteVideoRef}
                  autoPlay
                  playsInline
                  className={`h-full w-full object-cover ${peerPresent && peerCamera ? "block" : "hidden"}`}
                  data-testid="remote-video"
                />

                {/* Waiting or peer camera off placeholder */}
                {(!peerPresent || !peerCamera) && (
                  <div className="flex flex-col items-center justify-center gap-2 text-center text-slate-400 p-6">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full bg-slate-800 text-2xl font-bold text-indigo-400 border border-slate-700 shadow-inner">
                      {isInterviewer
                        ? candidateName
                            .split(" ")
                            .map((n) => n[0])
                            .slice(0, 2)
                            .join("")
                        : "HR"}
                    </div>
                    <p className="text-sm font-medium text-slate-300">
                      {!peerPresent ? "Waiting for the other participant to join..." : "Participant's camera is off"}
                    </p>
                    {!peerPresent && (
                      <span className="text-xs text-slate-500">
                        They will appear here automatically when connected.
                      </span>
                    )}
                  </div>
                )}

                {/* Remote Video Tag Overlays */}
                <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-lg bg-slate-900/80 px-2.5 py-1 text-xs text-white backdrop-blur-xs">
                  <span className="font-semibold">
                    {peerPresent
                      ? isInterviewer
                        ? candidateName
                        : "Interviewer"
                      : "Waiting…"}
                  </span>
                  {!peerMic && (
                    <span className="flex items-center text-rose-400" title="Microphone muted">
                      <MicOff className="h-3 w-3" />
                    </span>
                  )}
                </div>

                {peerHandRaised && (
                  <div className="absolute top-3 left-3 flex items-center gap-1 rounded-full bg-amber-500 px-2.5 py-1 text-xs font-bold text-white shadow-md animate-bounce">
                    <Hand className="h-3.5 w-3.5" />
                    <span>Participant Raised Hand</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* SPEAKER VIEW (Main + PIP) */
            <div className="relative w-full h-full max-h-[640px] rounded-2xl bg-slate-900 overflow-hidden border border-slate-800 flex items-center justify-center">
              <video
                ref={remoteVideoRef}
                autoPlay
                playsInline
                className={`h-full w-full object-cover ${peerPresent && peerCamera ? "block" : "hidden"}`}
              />

              {(!peerPresent || !peerCamera) && (
                <div className="flex flex-col items-center justify-center gap-2 text-center text-slate-400">
                  <div className="flex h-24 w-24 items-center justify-center rounded-full bg-slate-800 text-3xl font-bold text-indigo-400 border border-slate-700">
                    {isInterviewer ? candidateName[0] : "H"}
                  </div>
                  <p className="text-sm text-slate-300">
                    {!peerPresent ? "Waiting for participant..." : "Participant's camera is off"}
                  </p>
                </div>
              )}

              {/* Floating PIP Local View */}
              <div
                className={`absolute bottom-4 right-4 h-36 w-52 rounded-xl bg-slate-950 overflow-hidden shadow-2xl border-2 border-slate-700 transition ${
                  localSpeaking ? "ring-2 ring-indigo-500" : ""
                }`}
              >
                <video
                  ref={localVideoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`h-full w-full object-cover mirror ${cameraOn ? "block" : "hidden"}`}
                />
                {!cameraOn && (
                  <div className="flex h-full w-full items-center justify-center text-xs text-slate-400">
                    Camera Off
                  </div>
                )}
                <span className="absolute bottom-1 left-2 rounded bg-slate-900/80 px-1.5 py-0.5 text-[10px] text-white">
                  You
                </span>
              </div>
            </div>
          )}

          {/* LIVE SUBTITLE CAPTIONS OVERLAY */}
          {captionsEnabled && currentCaption && (
            <div className="absolute bottom-20 left-1/2 -translate-x-1/2 max-w-2xl w-11/12 rounded-xl bg-slate-950/85 px-4 py-2.5 text-center text-sm text-white shadow-2xl border border-slate-700/60 backdrop-blur-md z-20 animate-fadeIn">
              <span className="font-semibold text-indigo-300 mr-2">[{currentCaption.speaker}]:</span>
              <span className="text-slate-100">{currentCaption.text}</span>
            </div>
          )}

          {/* ── 3. FLOATING INTERVIEW CONTROL TOOLBAR ──────────────────── */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1.5 sm:gap-2 rounded-2xl bg-slate-900/90 px-3 py-2 shadow-2xl border border-slate-700/70 backdrop-blur-md">
            {/* 1. Mic mute/unmute */}
            <button
              onClick={toggleMic}
              aria-pressed={micOn}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                micOn ? "bg-slate-800 text-white hover:bg-slate-700" : "bg-rose-600 text-white hover:bg-rose-700"
              }`}
              title={micOn ? "Mute Microphone" : "Unmute Microphone"}
            >
              {micOn ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
            </button>

            {/* 2. Camera on/off */}
            <button
              onClick={toggleCamera}
              aria-pressed={cameraOn}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                cameraOn ? "bg-slate-800 text-white hover:bg-slate-700" : "bg-rose-600 text-white hover:bg-rose-700"
              }`}
              title={cameraOn ? "Turn Camera Off" : "Turn Camera On"}
            >
              {cameraOn ? <Video className="h-4 w-4" /> : <VideoOff className="h-4 w-4" />}
            </button>

            {/* 3. Screen sharing */}
            <button
              onClick={toggleScreenShare}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                isSharingScreen
                  ? "bg-indigo-600 text-white hover:bg-indigo-700"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}
              title={isSharingScreen ? "Stop Screen Share" : "Share Screen"}
            >
              {isSharingScreen ? <MonitorOff className="h-4 w-4" /> : <Monitor className="h-4 w-4" />}
            </button>

            {/* 4. In-Call Chat */}
            <button
              onClick={() => {
                setActiveTab("chat");
                setSidebarOpen(true);
                setUnreadChatCount(0);
              }}
              className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition"
              title="In-Call Chat"
            >
              <MessageSquare className="h-4 w-4" />
              {unreadChatCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                  {unreadChatCount}
                </span>
              )}
            </button>

            {/* 5. Participants */}
            <button
              onClick={() => {
                setActiveTab("participants");
                setSidebarOpen(true);
              }}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition"
              title="Participants"
            >
              <Users className="h-4 w-4" />
            </button>

            {/* 6. Raise hand */}
            <button
              onClick={toggleRaiseHand}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                handRaised ? "bg-amber-500 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}
              title={handRaised ? "Lower Hand" : "Raise Hand"}
            >
              <Hand className="h-4 w-4" />
            </button>

            {/* 7. Live captions */}
            <button
              onClick={toggleCaptions}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                captionsEnabled ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}
              title={captionsEnabled ? "Turn Off Captions" : "Turn On Captions (CC)"}
            >
              <Subtitles className="h-4 w-4" />
            </button>

            {/* 8. Audio/Video Settings */}
            <button
              onClick={() => setShowSettingsModal(true)}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition"
              title="Device Settings"
            >
              <Settings className="h-4 w-4" />
            </button>

            {/* 9. Interview notes (Staff only) */}
            {isInterviewer && (
              <button
                onClick={() => {
                  setActiveTab("scorecard");
                  setSidebarOpen(true);
                }}
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition"
                title="Interview Scorecard & Notes"
              >
                <FileText className="h-4 w-4" />
              </button>
            )}

            {/* 10. Recording controls (Interviewer only) */}
            {isInterviewer && (
              <button
                onClick={() => {
                  if (isRecording) {
                    stopRecording();
                  } else {
                    setShowRecordingModal(true);
                  }
                }}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                  isRecording ? "bg-rose-600 text-white animate-pulse" : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                }`}
                title={isRecording ? "Stop Recording" : "Record Interview"}
              >
                <Disc className="h-4 w-4" />
              </button>
            )}

            {/* 11. Fullscreen mode */}
            <button
              onClick={toggleFullscreen}
              className="hidden sm:flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition"
              title="Toggle Fullscreen"
            >
              <Maximize2 className="h-4 w-4" />
            </button>

            {/* 12. End / Leave Call button */}
            <button
              onClick={() => (isInterviewer ? setShowEndConfirmModal(true) : leave())}
              className="flex items-center gap-1.5 h-10 rounded-xl bg-rose-600 px-3.5 text-xs font-semibold text-white hover:bg-rose-700 transition shadow-xs ml-1"
              title={isInterviewer ? "End Interview" : "Leave Interview"}
            >
              <PhoneOff className="h-4 w-4" />
              <span className="hidden sm:inline">{isInterviewer ? "End Call" : "Leave"}</span>
            </button>
          </div>
        </main>

        {/* ── 4. RIGHT SIDEBAR WORKSPACE ─────────────────────────────── */}
        <InterviewSidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          role={role}
          interviewId={interviewId}
          applicationId={applicationId}
          stage={stage}
          candidateName={candidateName}
          candidateEmail={candidateEmail}
          jobTitle={jobTitle}
          screeningDetail={screeningDetail}
          applicationInterviews={applicationInterviews}
          transcriptEntries={transcriptEntries}
          chatMessages={chatMessages}
          onSendMessage={handleSendMessage}
          unreadChatCount={unreadChatCount}
          participants={participantsList}
          notes={notes}
          onNotesChange={setNotes}
          onSaveNotes={() => void handleSaveNotes()}
          notesSaved={notesSaved}
          scorecardData={scorecardData}
          onScorecardChange={setScorecardData}
          onSaveScorecardDraft={handleSaveScorecardDraft}
          onSubmitScorecard={handleSubmitScorecard}
          isSubmittingScorecard={isSubmittingScorecard}
        />
      </div>

      {/* ── 5. MODALS & POPUPS ────────────────────────────────────────── */}

      {/* Settings Modal */}
      <InterviewSettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        selectedAudioDeviceId={selectedAudioId}
        selectedVideoDeviceId={selectedVideoId}
        onSelectDevices={handleDeviceSelect}
      />

      {/* Recording Consent Modal */}
      {showRecordingModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl border border-slate-100 space-y-3">
            <div className="flex items-center gap-2 text-rose-600">
              <Disc className="h-5 w-5" />
              <h3 className="text-base font-semibold text-slate-900">Start Call Recording?</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Recording will capture audio and video streams for hiring compliance and interview review. Ensure all participants have provided their consent.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setShowRecordingModal(false)}>
                Cancel
              </Button>
              <Button variant="danger" size="sm" onClick={startRecording}>
                Consent & Start Recording
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* End Call Confirmation Modal (Interviewer Only) */}
      {showEndConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl border border-slate-100 space-y-3">
            <div className="flex items-center gap-2 text-rose-600">
              <PhoneOff className="h-5 w-5" />
              <h3 className="text-base font-semibold text-slate-900">End Interview for Both Sides?</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              This will conclude the live video session. You will be redirected to the post-interview evaluation report where you can record feedback.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setShowEndConfirmModal(false)}>
                Stay in call
              </Button>
              <Button variant="danger" size="sm" onClick={endInterview} data-testid="confirm-end-interview">
                End interview
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
