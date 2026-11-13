import { useEffect, useState, useRef } from "react";
import { X, Mic, Video, Volume2 } from "lucide-react";
import { Button } from "../ui/Button";

interface InterviewSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedAudioDeviceId: string;
  selectedVideoDeviceId: string;
  onSelectDevices: (audioId: string, videoId: string) => void;
}

export function InterviewSettingsModal({
  isOpen,
  onClose,
  selectedAudioDeviceId,
  selectedVideoDeviceId,
  onSelectDevices,
}: InterviewSettingsModalProps) {
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [currentAudio, setCurrentAudio] = useState(selectedAudioDeviceId);
  const [currentVideo, setCurrentVideo] = useState(selectedVideoDeviceId);
  const [micVolume, setMicVolume] = useState(0);

  const previewVideoRef = useRef<HTMLVideoElement | null>(null);
  const previewStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    setCurrentAudio(selectedAudioDeviceId);
    setCurrentVideo(selectedVideoDeviceId);

    async function loadDevices() {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audios = devices.filter((d) => d.kind === "audioinput");
        const videos = devices.filter((d) => d.kind === "videoinput");
        setAudioDevices(audios);
        setVideoDevices(videos);

        if (!currentAudio && audios.length > 0) {
          setCurrentAudio(audios[0].deviceId);
        }
        if (!currentVideo && videos.length > 0) {
          setCurrentVideo(videos[0].deviceId);
        }
      } catch (err) {
        console.error("Failed to enumerate devices:", err);
      }
    }

    void loadDevices();
  }, [isOpen, selectedAudioDeviceId, selectedVideoDeviceId]);

  // Start preview stream
  useEffect(() => {
    if (!isOpen) {
      if (previewStreamRef.current) {
        previewStreamRef.current.getTracks().forEach((t) => t.stop());
        previewStreamRef.current = null;
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
      return;
    }

    let active = true;

    async function startPreview() {
      try {
        if (previewStreamRef.current) {
          previewStreamRef.current.getTracks().forEach((t) => t.stop());
        }

        const constraints: MediaStreamConstraints = {
          video: currentVideo ? { deviceId: { exact: currentVideo } } : true,
          audio: currentAudio ? { deviceId: { exact: currentAudio } } : true,
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        previewStreamRef.current = stream;
        if (previewVideoRef.current) {
          previewVideoRef.current.srcObject = stream;
        }

        // Setup volume meter
        const audioTracks = stream.getAudioTracks();
        if (audioTracks.length > 0) {
          const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          if (AudioContextClass) {
            const ctx = new AudioContextClass();
            audioContextRef.current = ctx;
            const source = ctx.createMediaStreamSource(stream);
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            const checkVolume = () => {
              if (!active) return;
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
        console.error("Preview media error:", err);
      }
    }

    void startPreview();

    return () => {
      active = false;
      if (previewStreamRef.current) {
        previewStreamRef.current.getTracks().forEach((t) => t.stop());
        previewStreamRef.current = null;
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [isOpen, currentAudio, currentVideo]);

  if (!isOpen) return null;

  const handleApply = () => {
    onSelectDevices(currentAudio, currentVideo);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl border border-slate-100">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Video className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Audio & Video Settings</h2>
              <p className="text-xs text-slate-500">Configure your camera and microphone</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          {/* Camera preview */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Camera Preview
            </label>
            <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-slate-950 border border-slate-200">
              <video
                ref={previewVideoRef}
                autoPlay
                playsInline
                muted
                className="h-full w-full object-cover mirror"
              />
              <span className="absolute bottom-2 left-2 rounded-md bg-slate-900/75 px-2 py-0.5 text-xs text-white">
                Live Preview
              </span>
            </div>
          </div>

          {/* Camera selector */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1.5">
              <Video className="h-3.5 w-3.5 text-indigo-600" />
              Camera Device
            </label>
            <select
              value={currentVideo}
              onChange={(e) => setCurrentVideo(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              {videoDevices.map((dev, i) => (
                <option key={dev.deviceId || i} value={dev.deviceId}>
                  {dev.label || `Camera ${i + 1}`}
                </option>
              ))}
            </select>
          </div>

          {/* Microphone selector */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1.5">
              <Mic className="h-3.5 w-3.5 text-indigo-600" />
              Microphone Device
            </label>
            <select
              value={currentAudio}
              onChange={(e) => setCurrentAudio(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              {audioDevices.map((dev, i) => (
                <option key={dev.deviceId || i} value={dev.deviceId}>
                  {dev.label || `Microphone ${i + 1}`}
                </option>
              ))}
            </select>

            {/* Mic volume meter */}
            <div className="mt-2 flex items-center gap-2">
              <Volume2 className="h-4 w-4 text-slate-400" />
              <div className="h-2 flex-1 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-75"
                  style={{ width: `${micVolume}%` }}
                />
              </div>
              <span className="text-xs font-mono text-slate-400 w-8 text-right">{micVolume}%</span>
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleApply}>
            Save & Apply
          </Button>
        </div>
      </div>
    </div>
  );
}
