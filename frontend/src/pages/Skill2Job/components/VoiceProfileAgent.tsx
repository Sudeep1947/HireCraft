import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Pencil, RotateCcw, Send, CheckCircle, AlertCircle, X, Loader2, Keyboard } from "lucide-react";
import { skill2jobApi } from "../../../api/skill2job";

/* -------------------------------------------------------------------------- */
/*  Types                                                                      */
/* -------------------------------------------------------------------------- */

type VoiceState =
  | "idle"
  | "listening"
  | "transcript_ready"
  | "editing_transcript"
  | "analyzing"
  | "review"
  | "confirming"
  | "success"
  | "error";

interface ExtractedSkill {
  name: string;
  category?: string;
  inferred?: boolean;
}

interface ExtractedExperience {
  skill: string;
  years?: number;
  company?: string;
}

interface VoiceProfileResult {
  skills: ExtractedSkill[];
  experience: ExtractedExperience[];
  education: string[];
  projects: string[];
  certifications: string[];
  learning: string[];
  rawSkills: string[];
}

interface VoiceProfileAgentProps {
  onProfileUpdated?: () => void;
}

/* -------------------------------------------------------------------------- */
/*  Speech Recognition Detection                                               */
/* -------------------------------------------------------------------------- */

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionExtended extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event & { error: string }) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognitionExtended;
    webkitSpeechRecognition: new () => SpeechRecognitionExtended;
  }
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                    */
/* -------------------------------------------------------------------------- */

function classifyExperience(
  transcript: string,
  skills: string[]
): { experience: ExtractedExperience[]; learning: string[] } {
  const lower = transcript.toLowerCase();
  const experience: ExtractedExperience[] = [];

  // Detect "learning X" / "studying X" / "currently learning X"
  const learningPatterns = [
    /(?:currently\s+)?(?:learning|studying|picking\s+up|getting\s+into|starting\s+to\s+learn)\s+([\w\s#+.-]+?)(?:\.|,|;|and\b|$)/gi,
  ];
  const learningSkills = new Set<string>();
  for (const pattern of learningPatterns) {
    let match;
    while ((match = pattern.exec(lower)) !== null) {
      const raw = match[1].trim();
      // Extract skill names (split on "and", commas)
      const parts = raw.split(/,|\band\b/).map((s) => s.trim()).filter(Boolean);
      for (const part of parts) {
        const matched = skills.find(
          (s) => part.includes(s.toLowerCase()) || s.toLowerCase().includes(part)
        );
        if (matched) learningSkills.add(matched);
      }
    }
  }

  // Detect experience patterns: "X years of Y", "Y for X years", "Y experience"
  const expPatterns = [
    /(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience\s+(?:in|with)\s+)?([\w\s#+.-]+?)(?:\.|,|;|and\b|$)/gi,
    /([\w\s#+.-]+?)\s+(?:for\s+)?(\d+)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?(?:\.|,|;|and\b|$)/gi,
    /(?:experience\s+(?:in|with)\s+)([\w\s#+.-]+?)(?:\.|,|;|and\b|$)/gi,
  ];

  for (const skill of skills) {
    if (learningSkills.has(skill)) continue;
    const skillLower = skill.toLowerCase();

    // Check for explicit year mentions
    for (const pattern of expPatterns) {
      const text = lower;
      let match;
      pattern.lastIndex = 0;
      while ((match = pattern.exec(text)) !== null) {
        let years: number | undefined;
        let matchedSkill: string | undefined;

        if (/^\d/.test(match[1])) {
          years = parseInt(match[1], 10);
          matchedSkill = skills.find(
            (s) => match![2].includes(s.toLowerCase()) || s.toLowerCase().includes(match![2].trim())
          );
        } else {
          matchedSkill = skills.find(
            (s) => match![1].includes(s.toLowerCase()) || s.toLowerCase().includes(match![1].trim())
          );
          if (/^\d/.test(match[2])) years = parseInt(match[2], 10);
        }

        if (matchedSkill === skill || skillLower.includes((matchedSkill || "").toLowerCase())) {
          if (!experience.find((e) => e.skill === skill)) {
            experience.push({ skill, years });
          }
        }
      }
    }

    // If skill is mentioned in context of "worked with/using" but no years
    if (!experience.find((e) => e.skill === skill)) {
      const workContext = new RegExp(
        `(?:worked?\\s+(?:with|on|in|using)|built\\s+with|experience\\s+(?:with|in))\\s+.*?${skillLower.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
        "i"
      );
      if (workContext.test(lower)) {
        experience.push({ skill });
      }
    }
  }

  return { experience, learning: Array.from(learningSkills) };
}

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

export function VoiceProfileAgent({ onProfileUpdated }: VoiceProfileAgentProps) {
  // --- State ---
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [result, setResult] = useState<VoiceProfileResult | null>(null);
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set());
  const [editedExperience, setEditedExperience] = useState<ExtractedExperience[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [browserSupported, setBrowserSupported] = useState<boolean | null>(null);

  const recognitionRef = useRef<SpeechRecognitionExtended | null>(null);

  // --- Browser support check ---
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    setBrowserSupported(!!SpeechRecognition);
  }, []);

  // --- Cleanup on unmount ---
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
        recognitionRef.current = null;
      }
    };
  }, []);

  // --- Start listening ---
  const startListening = useCallback(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setErrorMessage("Voice input is not supported in this browser. You can paste or type your information instead.");
      setState("error");
      return;
    }

    setErrorMessage("");
    setTranscript("");
    setResult(null);

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => setState("listening");

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimText += event.results[i][0].transcript;
        }
      }
      if (finalTranscript) {
        setTranscript((prev) => (prev ? prev + " " + finalTranscript : finalTranscript));
      }
      setInterimTranscript(interimText);
    };

    recognition.onerror = (event: Event & { error: string }) => {
      const err = event.error;
      if (err === "not-allowed") {
        setErrorMessage(
          "Microphone access was denied. Please allow microphone access in your browser settings, or type your information instead."
        );
      } else if (err === "no-speech") {
        setErrorMessage(
          "No speech was detected. Make sure your microphone is working and try speaking closer to it."
        );
      } else if (err === "audio-capture") {
        setErrorMessage(
          "No microphone was found. Please connect a microphone or type your information instead."
        );
      } else if (err === "network") {
        setErrorMessage(
          "Speech recognition service is unavailable. This may be a temporary issue — try again or type your information."
        );
      } else if (err === "aborted") {
        // User aborted — don't show error, just go to transcript_ready if there's content
        setState((prev) => {
          if (prev === "listening") return "transcript_ready";
          return prev;
        });
        return;
      } else {
        setErrorMessage(
          `Voice recognition error (${err}). You can try again or type your information instead.`
        );
      }
      setState("error");
    };

    recognition.onend = () => {
      setInterimTranscript("");
      // Only transition if still in listening state
      setState((prev) => {
        if (prev === "listening") {
          return "transcript_ready";
        }
        return prev;
      });
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, []);

  // --- Stop listening ---
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setState((prev) => (prev === "listening" ? "transcript_ready" : prev));
  }, []);

  // --- Analyze transcript via existing perception pipeline ---
  const analyzeTranscript = useCallback(async (text: string) => {
    if (!text.trim()) {
      setErrorMessage("No speech was detected. Please try again.");
      setState("error");
      return;
    }

    setState("analyzing");
    setErrorMessage("");

    try {
      const res = await skill2jobApi.perceiveText(text);
      const resultData = res.result as Record<string, unknown>;
      const skills = (resultData.skills as Array<Record<string, unknown>> || []).map((s) => ({
        name: String(s.name || s.canonical || ""),
        category: s.category as string | undefined,
        inferred: (s.inferred as boolean) || false,
      })).filter((s) => s.name);

      const rawSkills = skills.map((s) => s.name);

      const { experience, learning } = classifyExperience(text, rawSkills);

      // Extract education, projects, certifications from perception result
      const education = (resultData.education as Array<Record<string, unknown>> || [])
        .map((e) => {
          const parts = [e.degree, e.field_of_study, e.institution].filter(Boolean);
          return parts.join(" — ") || String(e.raw_text || "");
        })
        .filter(Boolean);

      const projects = (resultData.projects as Array<Record<string, unknown>> || [])
        .map((p) => p.name as string || "")
        .filter(Boolean);

      const certifications = (resultData.certifications as Array<Record<string, unknown>> || [])
        .map((c) => c.name as string || "")
        .filter(Boolean);

      const extracted: VoiceProfileResult = {
        skills,
        experience,
        education,
        projects,
        certifications,
        learning,
        rawSkills,
      };

      setResult(extracted);
      setSelectedSkills(new Set(rawSkills));
      setEditedExperience(experience);
      setState("review");
    } catch {
      setErrorMessage("Unable to analyze the transcript right now. Your existing profile has not been changed.");
      setState("error");
    }
  }, []);

  // --- Confirm and update profile ---
  const confirmUpdate = useCallback(async () => {
    if (!result) return;
    setState("confirming");
    setErrorMessage("");

    try {
      const skillsToAdd = Array.from(selectedSkills);

      // Build corrections for experience
      const corrections = editedExperience
        .filter((e) => e.years != null)
        .map((e) => ({
          field: `skill_experience:${e.skill}`,
          value: `${e.years}`,
          note: `Voice-input: ${e.years} years of ${e.skill}`,
        }));

      await skill2jobApi.applyProfileReview({
        skills_to_add: skillsToAdd,
        skills_to_exclude: [],
        corrections,
      });

      setState("success");
      onProfileUpdated?.();
    } catch {
      setErrorMessage("Profile update failed. No partial changes should remain.");
      setState("error");
    }
  }, [result, selectedSkills, editedExperience, onProfileUpdated]);

  // --- Reset to start over ---
  const reset = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.abort();
      recognitionRef.current = null;
    }
    setState("idle");
    setTranscript("");
    setInterimTranscript("");
    setResult(null);
    setSelectedSkills(new Set());
    setEditedExperience([]);
    setErrorMessage("");
  }, []);

  // --- Toggle skill selection ---
  const toggleSkill = useCallback((skill: string) => {
    setSelectedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(skill)) next.delete(skill);
      else next.add(skill);
      return next;
    });
  }, []);

  // --- Update experience years ---
  const updateExperienceYears = useCallback((skill: string, years: string) => {
    setEditedExperience((prev) =>
      prev.map((e) =>
        e.skill === skill ? { ...e, years: years ? parseInt(years, 10) : undefined } : e
      )
    );
  }, []);

  /* ---------------------------------------------------------------------- */
  /*  Render                                                                 */
  /* ---------------------------------------------------------------------- */

  // --- Browser not supported ---
  if (browserSupported === false) {
    return (
      <div className="card border-amber-200/80 bg-amber-50/70 p-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 rounded-lg bg-amber-100 p-1.5 text-amber-600" aria-hidden="true">
            <MicOff className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-amber-800">Voice input not available</h3>
            <p className="mt-1 text-sm text-amber-700">
              Voice input is not supported in this browser. You can paste or type your information
              in the free-text area below instead.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" role="region" aria-label="Voice Profile Agent">
      {/* ── Main Card ─────────────────────────────────────────────────── */}
      <div className="card relative overflow-hidden p-6">
        <div
          className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-brand-gradient-soft blur-3xl"
          aria-hidden="true"
        />
        <div className="relative">
          <h2 className="flex items-center gap-3 section-title">
            <span className="rounded-xl bg-primary-50 p-2.5 text-primary-600">
              <Mic className="h-5 w-5" aria-hidden="true" />
            </span>
            Build Your Profile With Your Voice
          </h2>
          <p className="mt-1.5 max-w-2xl text-sm text-gray-500">
            Tell us about your skills and experience naturally. Your words are converted to text, analyzed,
            and reviewed before any profile changes.
          </p>
        </div>

        {/* ── IDLE: Mic button ────────────────────────────────────────── */}
        {state === "idle" && (
          <div className="relative mt-8 flex flex-col items-center gap-4">
            <button
              type="button"
              onClick={startListening}
              className="group flex h-20 w-20 items-center justify-center rounded-full bg-brand-gradient text-white shadow-glow transition-all duration-200 hover:scale-105 hover:shadow-glow focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/60 focus-visible:ring-offset-2"
              aria-label="Start voice recording"
            >
              <Mic className="h-8 w-8 transition-transform group-hover:scale-110" />
            </button>
            <span className="text-sm font-medium text-gray-600">Tap to start speaking</span>
            <p className="max-w-sm text-center text-xs text-gray-400">
              Example: &ldquo;I have 2 years of Python experience. I&apos;ve worked with FastAPI
              and PostgreSQL. I&apos;m currently learning Docker.&rdquo;
            </p>
            <button
              type="button"
              onClick={() => {
                setTranscript("");
                setState("transcript_ready");
              }}
              className="inline-flex items-center gap-1.5 rounded px-1 text-xs font-medium text-gray-500 transition-colors hover:text-primary-700"
            >
              <Keyboard className="h-3.5 w-3.5" aria-hidden="true" />
              Or type instead
            </button>
          </div>
        )}

        {/* ── LISTENING ───────────────────────────────────────────────── */}
        {state === "listening" && (
          <div className="relative mt-8 flex flex-col items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 animate-ping rounded-full bg-red-400 opacity-20" aria-hidden="true" />
              <div
                className="absolute inset-[-10px] animate-pulse-soft rounded-full bg-red-400/20"
                aria-hidden="true"
              />
              <button
                type="button"
                onClick={stopListening}
                className="relative flex h-20 w-20 items-center justify-center rounded-full bg-red-50 text-red-600 ring-1 ring-red-200 transition-all hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60 focus-visible:ring-offset-2"
                aria-label="Stop voice recording"
              >
                <MicOff className="h-8 w-8" />
              </button>
            </div>
            <span className="flex items-center gap-2 text-sm font-medium text-red-600">
              <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" aria-hidden="true" />
              Listening...
            </span>
            {(transcript || interimTranscript) && (
              <div className="max-w-md rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700 shadow-xs">
                {transcript && <span>{transcript}</span>}
                {interimTranscript && (
                  <span className="italic text-gray-400">{interimTranscript}</span>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── TRANSCRIPT READY ────────────────────────────────────────── */}
        {state === "transcript_ready" && (
          <div className="relative mt-6 space-y-4">
            <div>
              <label className="field-label" htmlFor="voice-transcript">Your Transcript</label>
              <textarea
                id="voice-transcript"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                rows={4}
                placeholder="Type or paste your skills, experience, and education here..."
                className="field resize-y"
                aria-label="Edit transcript before analysis"
                autoFocus
              />
              {!transcript.trim() && (
                <p className="field-hint">
                  Describe your skills, years of experience, projects, or anything you&apos;d like in your profile.
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => analyzeTranscript(transcript)}
                disabled={!transcript.trim()}
                className="btn-primary"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
                Analyze
              </button>
              <button
                type="button"
                onClick={startListening}
                className="btn-secondary"
              >
                <Mic className="h-4 w-4" aria-hidden="true" />
                Use Voice
              </button>
              <button
                type="button"
                onClick={reset}
                className="btn-secondary"
              >
                <X className="h-4 w-4" aria-hidden="true" />
                Discard
              </button>
            </div>
          </div>
        )}

        {/* ── ANALYZING ───────────────────────────────────────────────── */}
        {state === "analyzing" && (
          <div className="relative mt-6 flex flex-col items-center gap-3 py-8" role="status">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50">
              <Loader2 className="h-6 w-6 animate-spin text-primary-600" aria-hidden="true" />
            </span>
            <span className="text-sm font-medium text-gray-600">Analyzing your profile...</span>
          </div>
        )}

        {/* ── REVIEW ──────────────────────────────────────────────────── */}
        {state === "review" && result && (
          <div className="relative mt-6 space-y-6">
            <div className="success-banner">
              <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <div>
                <span className="block text-sm font-semibold">Information extracted</span>
                <p className="mt-0.5 text-xs text-emerald-700">
                  Review and edit before confirming. Uncheck skills you don&apos;t want added.
                </p>
              </div>
            </div>

            {/* Skills */}
            {result.skills.length > 0 && (
              <section>
                <h3 className="section-label mb-3">Skills</h3>
                <div className="flex flex-wrap gap-2">
                  {result.skills.map((skill) => (
                    <label
                      key={skill.name}
                      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
                        selectedSkills.has(skill.name)
                          ? "border-primary-300 bg-primary-50 text-primary-800 shadow-xs"
                          : "border-gray-200 bg-gray-50 text-gray-400 line-through hover:border-gray-300"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedSkills.has(skill.name)}
                        onChange={() => toggleSkill(skill.name)}
                        className="sr-only"
                      />
                      {skill.name}
                      {skill.inferred && (
                        <span className="text-xs text-gray-400">(inferred)</span>
                      )}
                    </label>
                  ))}
                </div>
              </section>
            )}

            {/* Experience */}
            {editedExperience.length > 0 && (
              <section>
                <h3 className="section-label mb-3">Experience</h3>
                <div className="space-y-2">
                  {editedExperience.map((exp) => (
                    <div
                      key={exp.skill}
                      className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50/80 px-3 py-2 shadow-xs"
                    >
                      <span className="text-sm font-medium text-gray-800">{exp.skill}</span>
                      <span className="text-xs text-gray-500">&mdash;</span>
                      <input
                        type="number"
                        min={0}
                        max={50}
                        value={exp.years ?? ""}
                        onChange={(e) => updateExperienceYears(exp.skill, e.target.value)}
                        className="field w-16 !px-2 !py-1 text-center"
                        placeholder="?"
                        aria-label={`Years of experience for ${exp.skill}`}
                      />
                      <span className="text-xs text-gray-500">years</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Learning */}
            {result.learning.length > 0 && (
              <section>
                <h3 className="section-label mb-3">Currently Learning</h3>
                <div className="flex flex-wrap gap-2">
                  {result.learning.map((skill) => (
                    <span
                      key={skill}
                      className="badge-warning !px-3 !py-1 !text-sm"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Education */}
            {result.education.length > 0 && (
              <section>
                <h3 className="section-label mb-3">Education</h3>
                <ul className="space-y-1">
                  {result.education.map((edu, i) => (
                    <li key={i} className="text-sm text-gray-700">&bull; {edu}</li>
                  ))}
                </ul>
              </section>
            )}

            {/* Projects */}
            {result.projects.length > 0 && (
              <section>
                <h3 className="section-label mb-3">Projects</h3>
                <ul className="space-y-1">
                  {result.projects.map((proj, i) => (
                    <li key={i} className="text-sm text-gray-700">&bull; {proj}</li>
                  ))}
                </ul>
              </section>
            )}

            {/* Certifications */}
            {result.certifications.length > 0 && (
              <section>
                <h3 className="section-label mb-3">Certifications</h3>
                <ul className="space-y-1">
                  {result.certifications.map((cert, i) => (
                    <li key={i} className="text-sm text-gray-700">&bull; {cert}</li>
                  ))}
                </ul>
              </section>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-3 border-t border-gray-100 pt-4">
              <button
                type="button"
                onClick={confirmUpdate}
                className="btn-primary"
              >
                <CheckCircle className="h-4 w-4" aria-hidden="true" />
                Confirm &amp; Update Profile
              </button>
              <button
                type="button"
                onClick={reset}
                className="btn-secondary"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Start Over
              </button>
            </div>
          </div>
        )}

        {/* ── CONFIRMING ──────────────────────────────────────────────── */}
        {state === "confirming" && (
          <div className="relative mt-6 flex flex-col items-center gap-3 py-8" role="status">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50">
              <Loader2 className="h-6 w-6 animate-spin text-primary-600" aria-hidden="true" />
            </span>
            <span className="text-sm font-medium text-gray-600">Updating your profile...</span>
          </div>
        )}

        {/* ── SUCCESS ─────────────────────────────────────────────────── */}
        {state === "success" && (
          <div className="relative mt-6 space-y-4">
            <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/80 p-6 text-center shadow-xs animate-scale-in">
              <CheckCircle className="mx-auto h-10 w-10 text-emerald-500" aria-hidden="true" />
              <h3 className="mt-2 text-sm font-bold text-emerald-800">Profile Updated</h3>
              <ul className="mt-2 space-y-1 text-sm text-emerald-700">
                <li>&#10003; Skills synchronized</li>
                <li>&#10003; Profile updated</li>
                <li>&#10003; Skill intelligence updated</li>
              </ul>
            </div>
            <div className="flex justify-center">
              <button
                type="button"
                onClick={reset}
                className="btn-primary"
              >
                <Mic className="h-4 w-4" aria-hidden="true" />
                Add More
              </button>
            </div>
          </div>
        )}

        {/* ── ERROR ───────────────────────────────────────────────────── */}
        {state === "error" && (
          <div className="relative mt-6 space-y-4">
            <div className="error-banner items-start">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium">{errorMessage}</p>
                <p className="mt-1 text-xs text-red-600">
                  You can always type or paste your information instead.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  setErrorMessage("");
                  setTranscript("");
                  setState("transcript_ready");
                }}
                className="btn-secondary"
              >
                <Keyboard className="h-4 w-4" aria-hidden="true" />
                Type Instead
              </button>
              <button
                type="button"
                onClick={reset}
                className="btn-primary"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Try Voice Again
              </button>
              {transcript && (
                <button
                  type="button"
                  onClick={() => {
                    setErrorMessage("");
                    setState("transcript_ready");
                  }}
                  className="btn-secondary"
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                  Edit Transcript
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Status announcements for screen readers ───────────────── */}
        <div className="sr-only" role="status" aria-live="polite">
          {state === "listening" && "Recording voice input"}
          {state === "analyzing" && "Analyzing transcript"}
          {state === "confirming" && "Updating profile"}
          {state === "success" && "Profile updated successfully"}
        </div>
      </div>
    </div>
  );
}
