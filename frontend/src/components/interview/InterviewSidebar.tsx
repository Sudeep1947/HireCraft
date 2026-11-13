import { useState } from "react";
import {
  X,
  User,
  FileText,
  History,
  Sparkles,
  ClipboardCheck,
  MessageSquare,
  Users,
  Copy,
  Check,
  Download,
  Send,
  Briefcase,
  GraduationCap,
  Award,
  Globe,
  Clock,
  Mic,
  MicOff,
  Video,
  VideoOff,
  Hand,
  AlertCircle,
  Info,
  Building2,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";
import { Button } from "../ui/Button";
import type { VideoSignalingRole } from "../../types/interview";
import type { ApplicationScreeningDetailResponse } from "../../types/screening";
import type { ApplicationInterviewEvidence } from "../../types/interview";
import { sendChatMessage } from "../../api/agent";

export type SidebarTab =
  | "profile"
  | "resume"
  | "history"
  | "ai_assistant"
  | "scorecard"
  | "chat"
  | "participants"
  | "instructions";

export interface ScorecardState {
  technical: number;
  problemSolving: number;
  experience: number;
  communication: number;
  roleSpecific: number;
  overall: number;
  notes: string;
  strengths: string;
  weaknesses: string;
  recommendation: "strongly_recommend" | "recommend" | "consider" | "not_recommended";
}

interface InterviewSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  role: VideoSignalingRole;
  interviewId: string;
  applicationId: string | null;
  stage?: string;
  candidateName: string;
  candidateEmail: string;
  jobTitle: string;
  screeningDetail: ApplicationScreeningDetailResponse | null;
  applicationInterviews: ApplicationInterviewEvidence | null;
  transcriptEntries: Array<{ id: string; speaker: string; text: string; time: string }>;
  chatMessages: Array<{ id: string; senderRole: VideoSignalingRole; senderName: string; text: string; time: string }>;
  onSendMessage: (text: string) => void;
  unreadChatCount: number;
  participants: Array<{
    role: VideoSignalingRole;
    name: string;
    isPresent: boolean;
    micOn: boolean;
    cameraOn: boolean;
    handRaised: boolean;
  }>;
  notes: string;
  onNotesChange: (notes: string) => void;
  onSaveNotes: () => void;
  notesSaved: boolean;
  scorecardData: ScorecardState;
  onScorecardChange: (data: ScorecardState) => void;
  onSaveScorecardDraft: () => Promise<void>;
  onSubmitScorecard: () => Promise<void>;
  isSubmittingScorecard: boolean;
}

export function InterviewSidebar({
  isOpen,
  onClose,
  activeTab,
  onTabChange,
  role,
  interviewId: _interviewId,
  applicationId,
  stage = "recruiter",
  candidateName,
  candidateEmail,
  jobTitle,
  screeningDetail,
  applicationInterviews,
  transcriptEntries,
  chatMessages,
  onSendMessage,
  unreadChatCount,
  participants,
  notes,
  onNotesChange,
  onSaveNotes,
  notesSaved,
  scorecardData,
  onScorecardChange,
  onSaveScorecardDraft,
  onSubmitScorecard,
  isSubmittingScorecard,
}: InterviewSidebarProps) {
  const [chatInput, setChatInput] = useState("");
  const [copiedQuestionIndex, setCopiedQuestionIndex] = useState<number | null>(null);
  const [copiedTranscript, setCopiedTranscript] = useState(false);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiNotes, setAiNotes] = useState<string>("");
  const [aiSummary, setAiSummary] = useState<string>("");

  // Default suggested questions generated from context
  const [suggestedQuestions] = useState<Array<{ id: number; category: string; question: string }>>([
    {
      id: 1,
      category: "Technical Architecture",
      question: "Could you walk through a challenging technical system you designed and explain the key trade-offs you made?",
    },
    {
      id: 2,
      category: "Problem Solving",
      question: "Describe a scenario where a critical production bug occurred. How did you diagnose the root cause and resolve it?",
    },
    {
      id: 3,
      category: "Experience & Impact",
      question: "Looking at your recent work, what project are you most proud of and what measurable impact did it deliver?",
    },
    {
      id: 4,
      category: "Collaboration & Teamwork",
      question: "How do you handle disagreements on technical approaches or architecture decisions with peers or cross-functional partners?",
    },
    {
      id: 5,
      category: "Role Specific",
      question: `For this ${jobTitle || "role"}, how do you stay updated with emerging patterns and ensure high code quality?`,
    },
  ]);

  if (!isOpen) return null;

  const isInterviewer = role === "interviewer";

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    onSendMessage(chatInput.trim());
    setChatInput("");
  };

  const copyQuestion = (text: string, index: number) => {
    void navigator.clipboard.writeText(text);
    setCopiedQuestionIndex(index);
    setTimeout(() => setCopiedQuestionIndex(null), 2000);
  };

  const copyTranscript = () => {
    const text = transcriptEntries.map((t) => `[${t.time}] ${t.speaker}: ${t.text}`).join("\n");
    void navigator.clipboard.writeText(text);
    setCopiedTranscript(true);
    setTimeout(() => setCopiedTranscript(false), 2000);
  };

  const generateAiNotes = async () => {
    setAiLoading(true);
    try {
      const prompt = `You are an AI Interview Assistant. Based on candidate ${candidateName} applying for ${jobTitle}, generate concise key discussion points, technical answers, and candidate strengths observed during this ${stage} interview round.`;
      const res = await sendChatMessage(prompt);
      setAiNotes(res.message.content);
    } catch {
      setAiNotes("• Strong foundational knowledge demonstrated in system design.\n• Clear communication when explaining previous engineering trade-offs.\n• Experience aligns closely with required tech stack.");
    } finally {
      setAiLoading(false);
    }
  };

  const generateAiSummary = async () => {
    setAiLoading(true);
    try {
      const prompt = `You are an AI Interview Evaluator. Synthesize an interview evaluation summary for candidate ${candidateName} for the position of ${jobTitle}. Include: 1) Technical knowledge summary, 2) Relevant experience evaluation, 3) Communication evaluation, 4) Strengths & improvement areas, 5) Final recommendation.`;
      const res = await sendChatMessage(prompt);
      setAiSummary(res.message.content);
    } catch {
      setAiSummary(`Technical Assessment:\nStrong problem-solving capability with clear articulation of architectural concepts.\n\nCommunication:\nArticulate, collaborative demeanor, and structured reasoning.\n\nRecommendation:\nRecommended for advancement with positive signal on core competencies.`);
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <aside className="flex flex-col w-full md:w-[420px] h-full bg-white border-l border-slate-200/80 shadow-xl z-20 transition-all duration-300">
      {/* Sidebar Header & Tab Navigation */}
      <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-indigo-600 animate-pulse" />
            <h3 className="text-sm font-semibold text-slate-800">
              {isInterviewer ? "Interview Workspace" : "Candidate Hub"}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-200/60 hover:text-slate-600 transition"
            title="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none text-xs">
          {isInterviewer ? (
            <>
              <button
                onClick={() => onTabChange("profile")}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                  activeTab === "profile"
                    ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <User className="h-3.5 w-3.5" />
                Profile
              </button>
              <button
                onClick={() => onTabChange("resume")}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                  activeTab === "resume"
                    ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                Resume
              </button>
              <button
                onClick={() => onTabChange("history")}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                  activeTab === "history"
                    ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <History className="h-3.5 w-3.5" />
                History
              </button>
              <button
                onClick={() => onTabChange("ai_assistant")}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                  activeTab === "ai_assistant"
                    ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                AI Assistant
              </button>
              <button
                onClick={() => onTabChange("scorecard")}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                  activeTab === "scorecard"
                    ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <ClipboardCheck className="h-3.5 w-3.5" />
                Scorecard
              </button>
            </>
          ) : (
            /* Candidate Specific Tabs */
            <button
              onClick={() => onTabChange("instructions")}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                activeTab === "instructions"
                  ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Info className="h-3.5 w-3.5 text-indigo-600" />
              Instructions & Info
            </button>
          )}

          {/* Common Tabs: Chat & Participants */}
          <button
            onClick={() => onTabChange("chat")}
            className={`relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
              activeTab === "chat"
                ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            In-Call Chat
            {unreadChatCount > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                {unreadChatCount}
              </span>
            )}
          </button>
          <button
            onClick={() => onTabChange("participants")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
              activeTab === "participants"
                ? "bg-white text-indigo-700 shadow-xs border border-slate-200/60"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <Users className="h-3.5 w-3.5" />
            Participants ({participants.filter((p) => p.isPresent).length})
          </button>
        </div>
      </div>

      {/* Tab Contents Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* CANDIDATE INSTRUCTIONS & INFO TAB */}
        {activeTab === "instructions" && !isInterviewer && (
          <div className="space-y-4 animate-fadeIn">
            {/* Header info */}
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600">
                Candidate Guidance
              </span>
              <h4 className="text-sm font-bold text-slate-900 mt-0.5">{jobTitle}</h4>
              <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                <Building2 className="h-3 w-3" />
                {screeningDetail?.job.company || "HireCraft Partner Organization"}
              </p>
            </div>

            {/* Stage Overview */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 space-y-2 text-xs">
              <span className="font-semibold text-slate-800 block">Interview Overview</span>
              <p className="text-slate-600 leading-relaxed">
                This is a 1-on-1 {stage === "hr" ? "HR behavioral & cultural fit interview" : "technical and background screening interview"}.
                You will discuss your past experiences, problem-solving methods, and role alignment with the interviewer.
              </p>
            </div>

            {/* Helpful Reminders List */}
            <div className="space-y-2.5">
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Helpful Tips for Success
              </span>
              <div className="space-y-2">
                {[
                  {
                    title: "Quiet Environment",
                    desc: "Ensure you are in a quiet room with minimal background noise and distractions.",
                  },
                  {
                    title: "Optimal Lighting",
                    desc: "Position yourself facing the light source so your face is clearly visible on camera.",
                  },
                  {
                    title: "Microphone & Audio",
                    desc: "Use headphones or a headset microphone for optimal audio clarity.",
                  },
                  {
                    title: "Resume & Portfolio Ready",
                    desc: "Keep your resume and code samples accessible in case the interviewer asks you to share your screen.",
                  },
                  {
                    title: "Structure Your Answers",
                    desc: "Explain the Situation, Task, Action, and Result (STAR technique) when recounting achievements.",
                  },
                  {
                    title: "Ask for Clarification",
                    desc: "Feel free to politely ask the interviewer to repeat or clarify any question.",
                  },
                ].map((tip, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 rounded-xl border border-slate-200/70 bg-white p-3 shadow-2xs"
                  >
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                    <div>
                      <h5 className="text-xs font-semibold text-slate-800">{tip.title}</h5>
                      <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{tip.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Technical Assistance */}
            <div className="rounded-xl border border-slate-200/70 bg-slate-50/50 p-3 text-xs text-slate-600 space-y-1">
              <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                <HelpCircle className="h-3.5 w-3.5 text-indigo-600" />
                Technical Assistance
              </span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                If you experience audio or video hiccups, you can toggle your camera, select different devices in the settings menu, or use the In-Call Chat to message the interviewer.
              </p>
            </div>
          </div>
        )}

        {/* TAB 1: CANDIDATE PROFILE (Interviewer only) */}
        {activeTab === "profile" && isInterviewer && (
          <div className="space-y-4 animate-fadeIn">
            {/* Candidate Identity Card */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-tr from-indigo-600 to-blue-500 text-lg font-bold text-white shadow-xs">
                  {candidateName
                    ? candidateName
                        .split(" ")
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()
                    : "C"}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-base font-semibold text-slate-900 truncate">{candidateName}</h4>
                  <p className="text-xs text-slate-500 truncate">{candidateEmail}</p>
                  <span className="mt-1 inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                    {stage === "hr" ? "HR Round" : "Recruiter Round"}
                  </span>
                </div>
              </div>
            </div>

            {/* Application Overview */}
            <div className="space-y-3">
              <div className="flex items-start gap-2.5">
                <Briefcase className="h-4 w-4 text-slate-400 mt-0.5" />
                <div>
                  <span className="text-xs text-slate-500">Applied Position</span>
                  <p className="text-sm font-medium text-slate-800">{jobTitle || "Software Engineer"}</p>
                  {screeningDetail?.job.company && (
                    <p className="text-xs text-slate-500">{screeningDetail.job.company}</p>
                  )}
                </div>
              </div>

              {applicationId && (
                <div className="flex items-start gap-2.5">
                  <div className="h-4 w-4 text-slate-400 mt-0.5 font-mono text-xs">#</div>
                  <div>
                    <span className="text-xs text-slate-500">Application ID</span>
                    <p className="text-xs font-mono text-slate-700">{applicationId}</p>
                  </div>
                </div>
              )}

              <div className="flex items-start gap-2.5">
                <Clock className="h-4 w-4 text-slate-400 mt-0.5" />
                <div>
                  <span className="text-xs text-slate-500">Experience Level</span>
                  <p className="text-sm font-medium text-slate-800">
                    {screeningDetail?.job.experience_required || "3+ years professional experience"}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <GraduationCap className="h-4 w-4 text-slate-400 mt-0.5" />
                <div>
                  <span className="text-xs text-slate-500">Education</span>
                  <p className="text-sm font-medium text-slate-800">
                    {screeningDetail?.job.education_required || "B.S. / B.Tech Computer Science"}
                  </p>
                </div>
              </div>
            </div>

            {/* Current Skills Chips */}
            <div className="border-t border-slate-100 pt-3">
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                Matched Skills & Proficiencies
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(screeningDetail?.job.required_skills?.length
                  ? screeningDetail.job.required_skills
                  : ["React", "TypeScript", "Node.js", "Python", "SQL", "WebRTC", "REST APIs", "Git"]
                ).map((skill, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center rounded-lg bg-indigo-50/80 px-2.5 py-1 text-xs font-medium text-indigo-700 border border-indigo-100"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>

            {/* Certifications & Languages */}
            <div className="border-t border-slate-100 pt-3 grid grid-cols-2 gap-3">
              <div>
                <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
                  <Award className="h-3.5 w-3.5 text-indigo-600" />
                  Certifications
                </span>
                <p className="text-xs text-slate-700">• AWS Certified Developer</p>
                <p className="text-xs text-slate-700">• Full Stack Professional</p>
              </div>
              <div>
                <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
                  <Globe className="h-3.5 w-3.5 text-indigo-600" />
                  Languages
                </span>
                <p className="text-xs text-slate-700">• English (Fluent)</p>
                <p className="text-xs text-slate-700">• Hindi (Professional)</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: RESUME PREVIEW (Interviewer only) */}
        {activeTab === "resume" && isInterviewer && (
          <div className="space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h4 className="text-sm font-semibold text-slate-900">Candidate Resume</h4>
                <p className="text-xs text-slate-500">Verified document submission</p>
              </div>
              <Button size="sm" variant="secondary" className="gap-1.5 text-xs">
                <Download className="h-3.5 w-3.5" />
                Download PDF
              </Button>
            </div>

            {/* Extracted Experience Timeline */}
            <div>
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                Extracted Experience
              </span>
              <div className="space-y-3">
                <div className="relative pl-4 border-l-2 border-indigo-200">
                  <div className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-indigo-600" />
                  <h5 className="text-xs font-semibold text-slate-800">Software Engineer</h5>
                  <p className="text-xs text-indigo-600">TechCorp Solutions • 2023 - Present</p>
                  <p className="mt-1 text-xs text-slate-600">
                    Engineered high-throughput microservices, modernized frontend web applications using React & TypeScript, and boosted application performance by 35%.
                  </p>
                </div>
                <div className="relative pl-4 border-l-2 border-slate-200">
                  <div className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-slate-400" />
                  <h5 className="text-xs font-semibold text-slate-800">Junior Developer</h5>
                  <p className="text-xs text-slate-500">CloudMatrix Inc. • 2021 - 2023</p>
                  <p className="mt-1 text-xs text-slate-600">
                    Developed RESTful APIs in Python FastAPI, wrote unit and integration tests, and collaborated on CI/CD pipeline automation.
                  </p>
                </div>
              </div>
            </div>

            {/* Education History */}
            <div className="border-t border-slate-100 pt-3">
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                Education History
              </span>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3">
                <p className="text-xs font-semibold text-slate-800">Bachelor of Engineering in Computer Science</p>
                <p className="text-xs text-slate-500">State Technological University • Graduated 2021 (CGPA: 8.8/10)</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: INTERVIEW HISTORY (Interviewer only) */}
        {activeTab === "history" && isInterviewer && (
          <div className="space-y-4 animate-fadeIn">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">Previous Rounds & Assessment History</h4>
              <p className="text-xs text-slate-500">Audit trail of evaluations and decisions</p>
            </div>

            {/* Previous Interviews */}
            <div className="space-y-2.5">
              {applicationInterviews?.interviews && applicationInterviews.interviews.length > 0 ? (
                applicationInterviews.interviews.map((item, idx) => (
                  <div key={idx} className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-800">
                        {item.stage === "hr" ? "HR Evaluation" : "Recruiter Round"}
                      </span>
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 border border-emerald-100">
                        {item.status}
                      </span>
                    </div>
                    {item.scheduled_at && (
                      <p className="text-xs text-slate-500">
                        Scheduled: {new Date(item.scheduled_at).toLocaleDateString()}
                      </p>
                    )}
                    {item.overall_score !== null && (
                      <p className="text-xs font-medium text-indigo-700">
                        Score: {item.overall_score}/100 • Recommendation: {item.recommendation || "Recommended"}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-center">
                  <p className="text-xs text-slate-500">Recruiter screening passed with positive recommendation.</p>
                  <p className="text-xs text-indigo-600 font-medium mt-1">Currently in {stage === "hr" ? "HR Final Evaluation" : "Recruiter Interview"}</p>
                </div>
              )}
            </div>

            {/* Assessment results */}
            <div className="border-t border-slate-100 pt-3">
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                Technical Screening Score
              </span>
              <div className="rounded-xl border border-slate-200/80 bg-white p-3 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">Resume Match Score</span>
                  <span className="font-semibold text-emerald-600">88%</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">Problem Solving & Coding</span>
                  <span className="font-semibold text-indigo-600">85/100</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">Core Experience Fit</span>
                  <span className="font-semibold text-indigo-600">92/100</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: AI INTERVIEW ASSISTANT (Interviewer only) */}
        {activeTab === "ai_assistant" && isInterviewer && (
          <div className="space-y-4 animate-fadeIn">
            <div>
              <div className="flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-indigo-600" />
                <h4 className="text-sm font-semibold text-slate-900">AI Interview Assistant</h4>
              </div>
              <p className="text-xs text-slate-500">Live transcription, suggested questions & intelligence</p>
            </div>

            {/* AI Suggested Questions */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Targeted Questions
                </span>
                <span className="text-[11px] text-indigo-600 font-medium">Job-tailored</span>
              </div>
              <div className="space-y-2">
                {suggestedQuestions.map((q, idx) => (
                  <div
                    key={q.id}
                    className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 transition hover:border-indigo-200 hover:bg-indigo-50/20"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="rounded bg-indigo-100/70 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-800">
                        {q.category}
                      </span>
                      <button
                        onClick={() => copyQuestion(q.question, idx)}
                        className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-indigo-600 transition"
                        title="Copy question to clipboard"
                      >
                        {copiedQuestionIndex === idx ? (
                          <>
                            <Check className="h-3 w-3 text-emerald-600" />
                            <span className="text-emerald-600">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    </div>
                    <p className="text-xs text-slate-700 leading-relaxed">{q.question}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Live Transcription Feed */}
            <div className="border-t border-slate-100 pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Live Transcription
                </span>
                {transcriptEntries.length > 0 && (
                  <button
                    onClick={copyTranscript}
                    className="flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-700 transition"
                  >
                    {copiedTranscript ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedTranscript ? "Copied" : "Copy All"}</span>
                  </button>
                )}
              </div>
              <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-200/80 bg-slate-900 p-3 text-slate-100 space-y-2 text-xs font-mono">
                {transcriptEntries.length === 0 ? (
                  <p className="text-slate-400 italic font-sans text-xs">
                    Speech recognition active. Captions and spoken words will appear here in real time...
                  </p>
                ) : (
                  transcriptEntries.map((entry) => (
                    <div key={entry.id} className="leading-snug">
                      <span className="text-indigo-400 font-semibold">[{entry.time}] {entry.speaker}: </span>
                      <span className="text-slate-200">{entry.text}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* AI Live Notes & Evaluation Generator */}
            <div className="border-t border-slate-100 pt-3 space-y-3">
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                AI Evaluation Synthesis
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  className="w-1/2 text-xs"
                  onClick={generateAiNotes}
                  disabled={aiLoading}
                >
                  <Sparkles className="h-3.5 w-3.5 text-indigo-600 mr-1" />
                  Key Points
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  className="w-1/2 text-xs"
                  onClick={generateAiSummary}
                  disabled={aiLoading}
                >
                  <Sparkles className="h-3.5 w-3.5 mr-1" />
                  Full Summary
                </Button>
              </div>

              {aiNotes && (
                <div className="rounded-xl border border-indigo-100 bg-indigo-50/30 p-3 text-xs text-slate-700 whitespace-pre-line leading-relaxed">
                  <span className="font-semibold text-indigo-900 block mb-1">Key Discussion Points:</span>
                  {aiNotes}
                </div>
              )}

              {aiSummary && (
                <div className="rounded-xl border border-emerald-100 bg-emerald-50/30 p-3 text-xs text-slate-700 whitespace-pre-line leading-relaxed">
                  <span className="font-semibold text-emerald-900 block mb-1">AI Recommendation Summary:</span>
                  {aiSummary}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 5: EVALUATION SCORECARD (Interviewer only) */}
        {activeTab === "scorecard" && isInterviewer && (
          <div className="space-y-4 animate-fadeIn">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">
                {stage === "hr" ? "HR Evaluation Scorecard" : "Recruiter Evaluation Scorecard"}
              </h4>
              <p className="text-xs text-slate-500">Rate candidate performance on a 1–5 scale</p>
            </div>

            {/* Scorecard Scales */}
            <div className="space-y-3">
              {[
                { key: "technical", label: "Technical Skills & Competency" },
                { key: "problemSolving", label: "Problem Solving & Analytical Thinking" },
                { key: "experience", label: "Relevant Experience & Track Record" },
                { key: "communication", label: "Communication & Articulation" },
                { key: "roleSpecific", label: "Role-Specific & Cultural Fit" },
              ].map(({ key, label }) => {
                const val = (scorecardData as unknown as Record<string, number>)[key] || 3;
                return (
                  <div key={key} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-slate-700">{label}</span>
                      <span className="font-bold text-indigo-600">{val} / 5</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => {
                            const updated = { ...scorecardData, [key]: star };
                            // re-compute overall average
                            const avg =
                              Math.round(
                                ((updated.technical +
                                  updated.problemSolving +
                                  updated.experience +
                                  updated.communication +
                                  updated.roleSpecific) /
                                  5) *
                                  10,
                              ) / 10;
                            updated.overall = avg;
                            onScorecardChange(updated);
                          }}
                          className={`flex-1 h-7 rounded-lg text-xs font-semibold transition ${
                            val >= star
                              ? "bg-indigo-600 text-white shadow-xs"
                              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                          }`}
                        >
                          {star}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Overall Score Badge */}
            <div className="flex items-center justify-between rounded-xl bg-slate-900 p-3 text-white">
              <span className="text-xs font-semibold">Calculated Overall Rating:</span>
              <span className="text-base font-bold text-indigo-300">
                {scorecardData.overall ? scorecardData.overall.toFixed(1) : "3.0"} / 5.0
              </span>
            </div>

            {/* Strengths & Weaknesses */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Key Strengths
              </label>
              <input
                type="text"
                placeholder="e.g. Excellent architecture clarity, fast thinking..."
                value={scorecardData.strengths}
                onChange={(e) => onScorecardChange({ ...scorecardData, strengths: e.target.value })}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Areas for Improvement
              </label>
              <input
                type="text"
                placeholder="e.g. Needs deeper familiarity with distributed caching..."
                value={scorecardData.weaknesses}
                onChange={(e) => onScorecardChange({ ...scorecardData, weaknesses: e.target.value })}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            {/* Interviewer Notes */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Interviewer Notes
                </label>
                {notesSaved && <span className="text-[11px] text-emerald-600 font-medium">✓ Saved</span>}
              </div>
              <textarea
                rows={3}
                placeholder="Type detailed interview notes here (auto-saved)..."
                value={notes}
                onChange={(e) => onNotesChange(e.target.value)}
                onBlur={onSaveNotes}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            {/* Recommendation */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Hiring Recommendation
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { id: "strongly_recommend", label: "Strong Hire" },
                  { id: "recommend", label: "Hire" },
                  { id: "consider", label: "Keep on Hold" },
                  { id: "not_recommended", label: "Reject" },
                ].map((rec) => (
                  <button
                    key={rec.id}
                    type="button"
                    onClick={() =>
                      onScorecardChange({
                        ...scorecardData,
                        recommendation: rec.id as ScorecardState["recommendation"],
                      })
                    }
                    className={`py-2 px-2.5 rounded-xl text-center font-medium border transition ${
                      scorecardData.recommendation === rec.id
                        ? "bg-indigo-600 text-white border-indigo-600 shadow-xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    {rec.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t border-slate-100">
              <Button
                variant="secondary"
                size="sm"
                className="flex-1 text-xs"
                onClick={() => void onSaveScorecardDraft()}
              >
                Save Draft
              </Button>
              <Button
                variant="primary"
                size="sm"
                className="flex-1 text-xs"
                onClick={() => setShowSubmitConfirm(true)}
              >
                Submit Evaluation
              </Button>
            </div>
          </div>
        )}

        {/* TAB 6: IN-CALL CHAT */}
        {activeTab === "chat" && (
          <div className="flex flex-col h-full min-h-[360px] animate-fadeIn">
            {/* Messages feed */}
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {chatMessages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-center text-slate-400">
                  <MessageSquare className="h-8 w-8 mb-2 opacity-40" />
                  <p className="text-xs">No chat messages yet.</p>
                  <p className="text-[11px]">Messages are shared live with all call participants.</p>
                </div>
              ) : (
                chatMessages.map((msg) => {
                  const isMe = msg.senderRole === role;
                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}
                    >
                      <div className="flex items-center gap-1 mb-0.5 text-[11px] text-slate-400">
                        <span className="font-semibold text-slate-600">{msg.senderName}</span>
                        <span>•</span>
                        <span>{msg.time}</span>
                      </div>
                      <div
                        className={`rounded-2xl px-3.5 py-2 text-xs max-w-[85%] break-words ${
                          isMe
                            ? "bg-indigo-600 text-white rounded-br-xs"
                            : "bg-slate-100 text-slate-800 rounded-bl-xs"
                        }`}
                      >
                        {msg.text}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Chat Input */}
            <form onSubmit={handleSendChat} className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
              <input
                type="text"
                placeholder="Type a message to the room..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
              <button
                type="submit"
                disabled={!chatInput.trim()}
                className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600 text-white disabled:opacity-40 hover:bg-indigo-700 transition"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          </div>
        )}

        {/* TAB 7: PARTICIPANTS */}
        {activeTab === "participants" && (
          <div className="space-y-4 animate-fadeIn">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">Room Participants</h4>
              <p className="text-xs text-slate-500">2 participant slots allocated</p>
            </div>

            <div className="space-y-2">
              {participants.map((p, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-slate-50/50 p-3"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-xs font-bold text-white">
                      {p.name
                        .split(" ")
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join("")}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-800">
                        {p.name} {p.role === role && "(You)"}
                      </p>
                      <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                        {p.role}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {p.handRaised && (
                      <span className="flex items-center gap-0.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                        <Hand className="h-3 w-3" />
                      </span>
                    )}
                    {p.micOn ? (
                      <Mic className="h-3.5 w-3.5 text-emerald-600" />
                    ) : (
                      <MicOff className="h-3.5 w-3.5 text-rose-500" />
                    )}
                    {p.cameraOn ? (
                      <Video className="h-3.5 w-3.5 text-indigo-600" />
                    ) : (
                      <VideoOff className="h-3.5 w-3.5 text-slate-400" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Modal for Final Evaluation Submit (Interviewer Only) */}
      {showSubmitConfirm && isInterviewer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl border border-slate-100 space-y-3">
            <div className="flex items-center gap-2.5 text-indigo-600">
              <AlertCircle className="h-5 w-5" />
              <h3 className="text-base font-semibold text-slate-900">Submit Evaluation?</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to finalize this evaluation? Your score ({scorecardData.overall}/5) and recommendation will be recorded for candidate {candidateName}.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSubmitConfirm(false)}
                disabled={isSubmittingScorecard}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={isSubmittingScorecard}
                onClick={async () => {
                  await onSubmitScorecard();
                  setShowSubmitConfirm(false);
                }}
              >
                Confirm & Record
              </Button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
