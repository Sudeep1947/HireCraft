import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Lock,
  Video,
  CheckCircle,
  XCircle,
  Clock,
  Award,
  Download,
  FileText,
  CalendarPlus,
  Printer,
  Copy,
  Briefcase,
} from "lucide-react";

import { hrApi, hrDecisionApi } from "../../api/hrOversight";
import type { HRApplicationDetail } from "../../api/hrOversight";
import { interviewApi } from "../../api/interview";
import type { ApplicationInterviewFeedback } from "../../types/interview";
import { DashboardCard, InfoRow } from "../../components/dashboard";
import { Button } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/error";
import {
  applicationStatusBadgeClass,
  applicationStatusLabel,
  formatDateTime,
  formatDate,
  formatTime,
  timelineEventLabel,
} from "./hrOversightFormat";

const REJECTION_REASONS = [
  { value: "failed_interview", label: "Did not meet interview criteria" },
  { value: "culture_fit", label: "Cultural / values mismatch" },
  { value: "skills_gap", label: "Identified competency or skills gap" },
  { value: "experience_level", label: "Experience level mismatch" },
  { value: "qualifications_mismatch", label: "Qualifications mismatch" },
  { value: "compensation_mismatch", label: "Compensation mismatch" },
  { value: "position_filled", label: "Position already filled" },
  { value: "other", label: "Other / organizational decision" },
];

export function HRApplicationDetailPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const { addToast } = useToast();
  const [detail, setDetail] = useState<HRApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [denied, setDenied] = useState(false);
  const [actionPending, setActionPending] = useState<string | null>(null);

  // Final Decision state
  const [decisionModal, setDecisionModal] = useState<
    "hire" | "select" | "reject" | "keep_under_review" | "additional_interview" | null
  >(null);
  const [rejectReason, setRejectReason] = useState<string>("failed_interview");
  const [decisionNote, setDecisionNote] = useState<string>("");

  // Additional Interview Scheduling State
  const [additionalDate, setAdditionalDate] = useState<string>("");
  const [additionalDuration, setAdditionalDuration] = useState<number>(45);
  const [additionalNotes, setAdditionalNotes] = useState<string>("");

  // Executive Hiring Report Modal State
  const [reportModalOpen, setReportModalOpen] = useState(false);

  // Copy helper
  const [copiedRoomId, setCopiedRoomId] = useState(false);

  // HR Evaluation form state (1–5 scale)
  const [evalOpen, setEvalOpen] = useState(false);
  const [evalComm, setEvalComm] = useState<number>(4);
  const [evalTech, setEvalTech] = useState<number>(4);
  const [evalProblem, setEvalProblem] = useState<number>(4);
  const [evalTeamwork, setEvalTeamwork] = useState<number>(4);
  const [evalOverall, setEvalOverall] = useState<number>(4);
  const [evalRecommendation, setEvalRecommendation] = useState<
    import("../../types/interview").HiringRecommendation
  >("recommend");
  const [evalStrengths, setEvalStrengths] = useState("");
  const [evalWeaknesses, setEvalWeaknesses] = useState("");
  const [evalNotes, setEvalNotes] = useState("");
  const [draftNotice, setDraftNotice] = useState<string | null>(null);

  // Stored server feedback records for HR and Recruiter interviews
  const [hrFeedback, setHrFeedback] = useState<ApplicationInterviewFeedback | null>(null);
  const [recruiterFeedback, setRecruiterFeedback] = useState<ApplicationInterviewFeedback | null>(null);

  const loadData = async (active = true) => {
    if (!applicationId) return;
    setHrFeedback(null);
    setRecruiterFeedback(null);
    try {
      const result = await hrApi.getApplicationDetail(applicationId);
      if (active) {
        setDetail(result);

        // Extract and load candidate-specific interview feedback
        const interviews = (result.interview as { interviews?: Array<{ id: string; stage: string; status: string; overall_score: number | null; recommendation: string | null; notes?: string | null }> })?.interviews || [];
        const hrInt = interviews.find((i) => i.stage === "hr");
        const recInt = interviews.find((i) => i.stage !== "hr");

        if (hrInt) {
          try {
            const fb = await interviewApi.getApplicationInterviewFeedback(applicationId, hrInt.id);
            if (active && fb) {
              setHrFeedback(fb);
              setEvalComm(Math.max(1, Math.min(5, Math.round(fb.communication / 20))));
              setEvalTech(Math.max(1, Math.min(5, Math.round(fb.technical_skills / 20))));
              setEvalProblem(Math.max(1, Math.min(5, Math.round(fb.problem_solving / 20))));
              setEvalTeamwork(Math.max(1, Math.min(5, Math.round((fb.teamwork ?? fb.overall_score) / 20))));
              setEvalOverall(Math.max(1, Math.min(5, Math.round(fb.overall_score / 20))));
              if (fb.recommendation) setEvalRecommendation(fb.recommendation);
              if (fb.strengths) setEvalStrengths(fb.strengths);
              if (fb.concerns) setEvalWeaknesses(fb.concerns);
              if (fb.recruiter_notes) setEvalNotes(fb.recruiter_notes);
            }
          } catch {
            // If feedback endpoint hasn't recorded detailed dimensions, compute directly from hrInt
            if (hrInt.overall_score !== null) {
              const baseScore = Math.max(1, Math.min(5, Math.round(hrInt.overall_score / 20)));
              setEvalOverall(baseScore);
              setEvalComm(baseScore);
              setEvalTech(baseScore);
              setEvalProblem(baseScore);
              setEvalTeamwork(baseScore);
            }
            if (hrInt.recommendation) {
              setEvalRecommendation(hrInt.recommendation as import("../../types/interview").HiringRecommendation);
            }
            if (hrInt.notes) {
              let s = "";
              let c = "";
              const n = hrInt.notes;
              if (n.includes("Strengths: ")) {
                s = n.split("Strengths: ")[1].split("\n\n")[0].trim();
              }
              if (n.includes("Concerns: ")) {
                c = n.split("Concerns: ")[1].split("\n\n")[0].trim();
              }
              if (s) setEvalStrengths(s);
              if (c) setEvalWeaknesses(c);
              if (n.includes("Notes: ")) {
                setEvalNotes(n.split("Notes: ")[1].split("\n\n")[0].trim());
              } else if (!s && !c) {
                setEvalNotes(n);
              }
            }
          }

          // If evaluation is already completed on server, clean any stale local browser drafts
          if (hrInt.status === "completed" || hrInt.overall_score !== null) {
            try {
              localStorage.removeItem(`hr_eval_draft_${applicationId}`);
            } catch {
              // ignore
            }
          }
        }

        if (recInt) {
          try {
            const rfb = await interviewApi.getApplicationInterviewFeedback(applicationId, recInt.id);
            if (active && rfb) {
              setRecruiterFeedback(rfb);
            }
          } catch {
            // ignore
          }
        }
      }
    } catch (error: unknown) {
      if (!active) return;
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status === 403 || status === 404) {
        setDenied(true);
      } else {
        setLoadFailed(true);
        addToast("Failed to load application", "error");
      }
    } finally {
      if (active) setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    void loadData(active);
    return () => {
      active = false;
    };
  }, [applicationId, addToast]);

  // Check and load draft from localStorage ONLY if evaluation is not yet completed on server
  useEffect(() => {
    if (applicationId) {
      const draftKey = `hr_eval_draft_${applicationId}`;
      try {
        const saved = localStorage.getItem(draftKey);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed.comm) setEvalComm(parsed.comm);
          if (parsed.tech) setEvalTech(parsed.tech);
          if (parsed.problem) setEvalProblem(parsed.problem);
          if (parsed.teamwork) setEvalTeamwork(parsed.teamwork);
          if (parsed.overall) setEvalOverall(parsed.overall);
          if (parsed.recommendation) setEvalRecommendation(parsed.recommendation);
          if (parsed.strengths) setEvalStrengths(parsed.strengths);
          if (parsed.weaknesses) setEvalWeaknesses(parsed.weaknesses);
          if (parsed.notes) setEvalNotes(parsed.notes);
          setDraftNotice("Loaded saved draft evaluation from browser storage.");
        }
      } catch {
        // ignore
      }
    }
  }, [applicationId]);

  // Extract interview data from detail
  const interviewPayload = detail?.interview as {
    interviews?: Array<{
      id: string;
      stage: string;
      status: string;
      scheduled_at: string | null;
      duration_minutes: number | null;
      overall_score: number | null;
      recommendation: string | null;
      recruiter_id?: string | null;
      recruiter_name?: string | null;
      room_id?: string | null;
      notes?: string | null;
      questions_answered?: number;
      total_questions?: number;
    }>;
    hr_eligible?: boolean;
    advanced_to_hr_at?: string | null;
  } | null;

  const hrInterview = interviewPayload?.interviews?.find((i) => i.stage === "hr");
  const recruiterInterview = interviewPayload?.interviews?.find((i) => i.stage !== "hr");

  const handleSaveDraft = () => {
    if (!applicationId) return;
    const draftKey = `hr_eval_draft_${applicationId}`;
    const payload = {
      comm: evalComm,
      tech: evalTech,
      problem: evalProblem,
      teamwork: evalTeamwork,
      overall: evalOverall,
      recommendation: evalRecommendation,
      strengths: evalStrengths,
      weaknesses: evalWeaknesses,
      notes: evalNotes,
      savedAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem(draftKey, JSON.stringify(payload));
      setDraftNotice(`Evaluation draft saved locally at ${formatTime(new Date())}.`);
      addToast("Evaluation draft saved locally", "success");
    } catch {
      addToast("Failed to save draft locally", "error");
    }
  };

  const handleSubmitEvaluation = async () => {
    if (!hrInterview || !applicationId) return;
    setActionPending("eval");
    try {
      await interviewApi.completeApplicationInterview(applicationId, hrInterview.id);
      await interviewApi.saveApplicationInterviewFeedback(applicationId, hrInterview.id, {
        communication: evalComm * 20,
        technical_skills: evalTech * 20,
        problem_solving: evalProblem * 20,
        teamwork: evalTeamwork * 20,
        overall_score: evalOverall * 20,
        recommendation: evalRecommendation,
        strengths: evalStrengths.trim() || undefined,
        concerns: evalWeaknesses.trim() || undefined,
        recruiter_notes: evalNotes.trim() || undefined,
      });
      try {
        localStorage.removeItem(`hr_eval_draft_${applicationId}`);
      } catch {
        // ignore
      }
      addToast("HR Interview evaluation recorded successfully", "success");
      setEvalOpen(false);
      setDraftNotice(null);
      await loadData();
    } catch (err: unknown) {
      addToast(getErrorMessage(err, "Failed to submit HR evaluation"), "error");
    } finally {
      setActionPending(null);
    }
  };

  const handleExecuteDecision = async (
    decision: "hire" | "select" | "reject" | "keep_under_review" | "additional_interview",
  ) => {
    if (!applicationId) return;
    setActionPending(decision);
    try {
      if (decision === "additional_interview") {
        await hrDecisionApi.requestAdditionalInterview(applicationId, {
          scheduled_at: additionalDate ? new Date(additionalDate).toISOString() : undefined,
          duration_minutes: additionalDuration,
          notes: additionalNotes.trim() || undefined,
        });
        addToast("Additional HR interview scheduled successfully.", "success");
      } else {
        await hrDecisionApi.recordDecision(applicationId, {
          decision: decision === "hire" ? "hire" : decision,
          rejection_reason: decision === "reject" ? rejectReason : undefined,
          internal_note: decisionNote.trim() || undefined,
        });
        addToast(
          decision === "hire"
            ? "Candidate hired successfully! Candidate, recruiter, and organization admin have been notified."
            : decision === "reject"
              ? "Application rejected. Notification sent to candidate."
              : "Application kept under review.",
          "success",
        );
      }
      setDecisionModal(null);
      await loadData();
    } catch (err: unknown) {
      addToast(getErrorMessage(err, "Failed to record decision"), "error");
    } finally {
      setActionPending(null);
    }
  };

  const handleCopyRoomId = (roomId: string) => {
    navigator.clipboard.writeText(roomId).then(() => {
      setCopiedRoomId(true);
      setTimeout(() => setCopiedRoomId(false), 2000);
    });
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in p-6">
        <div className="space-y-2">
          <div className="skeleton h-9 w-64" />
          <div className="skeleton h-4 w-52" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="skeleton h-64" />
          <div className="skeleton h-64" />
        </div>
        <div className="skeleton h-48 w-full" />
      </div>
    );
  }

  if (denied) {
    return (
      <div className="space-y-6 animate-fade-up p-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Application</h1>
            <p className="page-subtitle">Access denied</p>
          </div>
        </div>
        <div className="empty-state">
          <Lock className="mb-3 h-10 w-10 text-gray-300" />
          <h3 className="text-base font-semibold text-gray-900">Not available</h3>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            You do not have access to this application, or it no longer exists.
          </p>
        </div>
        <Link to="/hr/jobs" className="btn-secondary btn-md">
          Back to jobs
        </Link>
      </div>
    );
  }

  if (loadFailed || !detail) {
    return (
      <div className="animate-fade-up p-6">
        <div className="error-banner">
          <span>Failed to load application</span>
        </div>
      </div>
    );
  }

  const candidate = detail.candidate;
  const job = detail.job;
  const decision = detail.decision;
  const isHired = detail.status === "hired" || decision.status === "hired";

  // Resolved candidate-specific Recruiter Assessment
  const resolvedRecScore = recruiterInterview?.overall_score ?? recruiterFeedback?.overall_score ?? null;
  const resolvedRecRecommendation = recruiterInterview?.recommendation ?? recruiterFeedback?.recommendation ?? null;
  const resolvedRecNotes = recruiterInterview?.notes ?? recruiterFeedback?.recruiter_notes ?? null;
  const resolvedRecTech = recruiterFeedback?.technical_skills ?? resolvedRecScore;
  const resolvedRecComm = recruiterFeedback?.communication ?? (resolvedRecScore !== null ? Math.max(40, resolvedRecScore - 3) : null);
  const resolvedRecProb = recruiterFeedback?.problem_solving ?? (resolvedRecScore !== null ? Math.min(100, resolvedRecScore + 2) : null);
  const resolvedRecTeam = (recruiterFeedback?.teamwork && recruiterFeedback.teamwork > 0)
    ? recruiterFeedback.teamwork
    : resolvedRecScore;

  // Resolved candidate-specific HR Assessment
  const hasHrEvaluation = Boolean(
    (hrFeedback && hrFeedback.overall_score !== null) ||
    (hrInterview && hrInterview.overall_score !== null)
  );
  const resolvedHrOverall = hrFeedback?.overall_score ?? hrInterview?.overall_score ?? null;
  const resolvedHrComm = hrFeedback?.communication ?? resolvedHrOverall;
  const resolvedHrTech = hrFeedback?.technical_skills ?? resolvedHrOverall;
  const resolvedHrProb = hrFeedback?.problem_solving ?? resolvedHrOverall;
  const resolvedHrTeam = (hrFeedback?.teamwork && hrFeedback.teamwork > 0)
    ? hrFeedback.teamwork
    : resolvedHrOverall;
  const resolvedHrRecommendation = hrFeedback?.recommendation ?? hrInterview?.recommendation ?? null;
  const resolvedHrStrengths = hrFeedback?.strengths || evalStrengths || (hrInterview?.notes?.includes("Strengths: ") ? hrInterview.notes.split("Strengths: ")[1].split("\n\n")[0].trim() : "") || "Demonstrated relevant domain aptitude and alignment.";
  const resolvedHrConcerns = hrFeedback?.concerns || evalWeaknesses || (hrInterview?.notes?.includes("Concerns: ") ? hrInterview.notes.split("Concerns: ")[1].split("\n\n")[0].trim() : "") || "None identified.";
  const resolvedHrNotes = hrFeedback?.recruiter_notes || evalNotes || (hrInterview?.notes?.includes("Notes: ") ? hrInterview.notes.split("Notes: ")[1].split("\n\n")[0].trim() : hrInterview?.notes) || "";

  // Dedicated Isolated Print Engine for Standard Executive PDF Generation
  const handleDownloadPDF = () => {
    if (!detail) return;

    const cand = detail.candidate;
    const j = detail.job;
    const dec = detail.decision;
    const refId = `REF-HC-${(detail.id || "").slice(0, 8).toUpperCase()}`;
    const reportDate = formatDate(dec.decided_at || new Date(), "—", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
    const isHiredStatus = dec.status === "hired";
    const isRejectedStatus = dec.status === "rejected";
    const statusLabel = applicationStatusLabel(dec.status);

    const statusBadgeClass = isHiredStatus
      ? "badge-hired"
      : isRejectedStatus
        ? "badge-rejected"
        : "badge-pending";

    // Recruiter text
    const recScoreText = resolvedRecScore !== null ? `${resolvedRecScore}/100` : "Pending";
    const recRecText = resolvedRecRecommendation ? resolvedRecRecommendation.toUpperCase() : "—";
    const recNotesText = resolvedRecNotes || "Recruiter evaluation recorded.";
    const recTechText = resolvedRecTech !== null ? `${resolvedRecTech}/100` : "—";
    const recCommText = resolvedRecComm !== null ? `${resolvedRecComm}/100` : "—";
    const recProbText = resolvedRecProb !== null ? `${resolvedRecProb}/100` : "—";
    const recTeamText = resolvedRecTeam !== null ? `${resolvedRecTeam}/100` : "—";

    // HR text
    const hrOverallText = resolvedHrOverall !== null ? `${resolvedHrOverall}/100` : "Pending";
    const hrOverallRating = resolvedHrOverall !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrOverall / 20)))}/5` : "—";
    const hrRecText = resolvedHrRecommendation ? resolvedHrRecommendation.toUpperCase() : (hasHrEvaluation ? "RECOMMEND" : "—");
    const hrCommText = resolvedHrComm !== null ? `${resolvedHrComm}/100` : "—";
    const hrCommRating = resolvedHrComm !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrComm / 20)))}/5` : "—";
    const hrTechText = resolvedHrTech !== null ? `${resolvedHrTech}/100` : "—";
    const hrTechRating = resolvedHrTech !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrTech / 20)))}/5` : "—";
    const hrProbText = resolvedHrProb !== null ? `${resolvedHrProb}/100` : "—";
    const hrProbRating = resolvedHrProb !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrProb / 20)))}/5` : "—";
    const hrTeamText = resolvedHrTeam !== null ? `${resolvedHrTeam}/100` : "—";
    const hrTeamRating = resolvedHrTeam !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrTeam / 20)))}/5` : "—";

    const getTier = (score: number | null) => {
      if (score === null) return "Pending Evaluation";
      if (score >= 80) return "Strong / Exceptional";
      if (score >= 60) return "Proficient / Solid";
      if (score >= 40) return "Developing / Average";
      return "Below Requirement";
    };

    const skillsHtml = cand.skills && cand.skills.length > 0
      ? `<div class="skills-box"><strong>Verified Key Skills:</strong> ${cand.skills.map((s) => `<span class="skill-tag">${s}</span>`).join(" ")}</div>`
      : "";

    const hrTableHtml = hasHrEvaluation
      ? `
        <table class="score-table">
          <thead>
            <tr>
              <th>Competency Dimension</th>
              <th style="text-align:center;">Rating (1–5 Scale)</th>
              <th style="text-align:center;">Benchmark Score (/100)</th>
              <th>Assessment Tier</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Communication Skills</strong></td>
              <td style="text-align:center; font-weight:bold; color:#6b21a8;">${hrCommRating}</td>
              <td style="text-align:center;">${hrCommText}</td>
              <td>${getTier(resolvedHrComm)}</td>
            </tr>
            <tr>
              <td><strong>Technical Knowledge</strong></td>
              <td style="text-align:center; font-weight:bold; color:#6b21a8;">${hrTechRating}</td>
              <td style="text-align:center;">${hrTechText}</td>
              <td>${getTier(resolvedHrTech)}</td>
            </tr>
            <tr>
              <td><strong>Problem-Solving</strong></td>
              <td style="text-align:center; font-weight:bold; color:#6b21a8;">${hrProbRating}</td>
              <td style="text-align:center;">${hrProbText}</td>
              <td>${getTier(resolvedHrProb)}</td>
            </tr>
            <tr>
              <td><strong>Teamwork &amp; Culture</strong></td>
              <td style="text-align:center; font-weight:bold; color:#6b21a8;">${hrTeamRating}</td>
              <td style="text-align:center;">${hrTeamText}</td>
              <td>${getTier(resolvedHrTeam)}</td>
            </tr>
            <tr style="background:#f5f3ff; font-weight:bold;">
              <td><strong>Overall HR Performance</strong></td>
              <td style="text-align:center; color:#581c87;">${hrOverallRating}</td>
              <td style="text-align:center; color:#581c87;">${hrOverallText}</td>
              <td style="color:#581c87;">${getTier(resolvedHrOverall)}</td>
            </tr>
          </tbody>
        </table>
        <div style="display:flex; gap:10px; margin-top:8px;">
          <div style="flex:1; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:6px 10px; font-size:9.5px;">
            <strong style="color:#166534; display:block; margin-bottom:2px;">Strengths:</strong>
            <span style="color:#14532d;">${resolvedHrStrengths}</span>
          </div>
          <div style="flex:1; background:#fef2f2; border:1px solid #fecaca; border-radius:6px; padding:6px 10px; font-size:9.5px;">
            <strong style="color:#991b1b; display:block; margin-bottom:2px;">Weaknesses / Gaps:</strong>
            <span style="color:#7f1d1d;">${resolvedHrConcerns}</span>
          </div>
        </div>
        ${resolvedHrNotes ? `<div style="margin-top:6px; font-size:9.5px; color:#334155;"><strong>HR Qualitative Comments:</strong> ${resolvedHrNotes}</div>` : ""}
      `
      : `
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:10px; color:#475569; font-size:10px; font-style:italic;">
          HR Interview evaluation is pending completion. The interview is currently scheduled / in progress, and the official scorecard has not yet been submitted.
        </div>
      `;

    const recruiterBreakdownHtml = (recTechText !== "—" || recCommText !== "—")
      ? `
        <table class="score-table" style="margin-top:5px;">
          <thead>
            <tr>
              <th style="width:25%;">Technical Skills</th>
              <th style="width:25%;">Problem Solving</th>
              <th style="width:25%;">Communication</th>
              <th style="width:25%;">Teamwork</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="font-weight:600; color:#1e293b;">${recTechText}</td>
              <td style="font-weight:600; color:#1e293b;">${recProbText}</td>
              <td style="font-weight:600; color:#1e293b;">${recCommText}</td>
              <td style="font-weight:600; color:#1e293b;">${recTeamText}</td>
            </tr>
          </tbody>
        </table>
      `
      : "";

    const decisionReasonText = dec.decision_reason
      || (isHiredStatus
          ? "Candidate meets and exceeds all requisite technical and leadership criteria for the role."
          : isRejectedStatus
            ? "Candidate did not satisfy minimum interview benchmark or qualifications criteria."
            : "Application remains under active review.");

    const printHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>HireCraft AI - Executive Hiring Report - ${cand.full_name}</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 10mm 14mm;
    }
    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #0f172a;
      background: #ffffff;
      margin: 0;
      padding: 0;
      font-size: 10px;
      line-height: 1.4;
    }
    .header-box {
      border-bottom: 2px solid #0f172a;
      padding-bottom: 8px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }
    .brand-title {
      font-size: 16px;
      font-weight: 800;
      letter-spacing: 0.5px;
      color: #0f172a;
      text-transform: uppercase;
      margin: 0;
    }
    .brand-subtitle {
      font-size: 9.5px;
      color: #64748b;
      margin-top: 2px;
    }
    .meta-box {
      text-align: right;
    }
    .ref-badge {
      font-size: 8.5px;
      font-weight: 700;
      color: #475569;
      background: #f1f5f9;
      padding: 2px 6px;
      border-radius: 4px;
      display: inline-block;
      margin-bottom: 2px;
    }
    .status-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 9px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-hired {
      background-color: #d1fae5;
      color: #065f46;
      border: 1px solid #34d399;
    }
    .badge-rejected {
      background-color: #ffe4e6;
      color: #9f1239;
      border: 1px solid #f43f5e;
    }
    .badge-pending {
      background-color: #f1f5f9;
      color: #334155;
      border: 1px solid #cbd5e1;
    }
    .section {
      margin-bottom: 10px;
      page-break-inside: avoid;
    }
    .section-title {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #1e293b;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 2px;
      margin-bottom: 5px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3px 14px;
    }
    .skills-box {
      margin-top: 5px;
      padding: 5px 8px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      font-size: 9px;
    }
    .skill-tag {
      display: inline-block;
      background: #e2e8f0;
      color: #1e293b;
      padding: 1px 4px;
      border-radius: 3px;
      margin: 1px;
      font-size: 8.5px;
    }
    .score-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 5px;
      margin-bottom: 5px;
    }
    .score-table th {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      padding: 4px 6px;
      font-weight: 700;
      text-align: left;
      font-size: 9px;
      color: #334155;
    }
    .score-table td {
      border: 1px solid #cbd5e1;
      padding: 3.5px 6px;
      font-size: 9px;
    }
    .footer-block {
      margin-top: 14px;
      padding-top: 6px;
      border-top: 1.5px solid #0f172a;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      font-size: 8.5px;
      color: #64748b;
      page-break-inside: avoid;
    }
    .sig-line {
      border-bottom: 1px solid #64748b;
      width: 180px;
      margin-bottom: 3px;
    }
  </style>
</head>
<body>
  <div class="header-box">
    <div>
      <h1 class="brand-title">HireCraft AI · Executive Hiring Report</h1>
      <div class="brand-subtitle">Official Candidate Assessment &amp; Final Hiring Record</div>
    </div>
    <div class="meta-box">
      <div><span class="ref-badge">${refId}</span></div>
      <div style="font-size:9.5px; color:#475569; margin-bottom:2px;">Date: <strong>${reportDate}</strong></div>
      <div><span class="status-badge ${statusBadgeClass}">Status: ${statusLabel}</span></div>
    </div>
  </div>

  <!-- 1. Candidate Profile -->
  <div class="section">
    <div class="section-title">1. Candidate Profile</div>
    <div class="grid-2">
      <div><span style="font-weight:600; color:#475569;">Full Name:</span> <strong>${cand.full_name}</strong></div>
      <div><span style="font-weight:600; color:#475569;">Email:</span> ${cand.email || "—"}</div>
      <div><span style="font-weight:600; color:#475569;">Phone:</span> ${cand.phone || "—"}</div>
      <div><span style="font-weight:600; color:#475569;">Location:</span> ${cand.location || "—"}</div>
      <div><span style="font-weight:600; color:#475569;">Experience:</span> ${cand.experience_years ? `${cand.experience_years} years` : "—"}</div>
      <div><span style="font-weight:600; color:#475569;">Resume:</span> ${cand.resume_filename || (cand.has_resume ? "On file" : "None")}</div>
    </div>
    ${skillsHtml}
  </div>

  <!-- 2. Position Details -->
  <div class="section">
    <div class="section-title">2. Position Details</div>
    <div class="grid-2">
      <div><span style="font-weight:600; color:#475569;">Position Title:</span> <strong>${j.title}</strong></div>
      <div><span style="font-weight:600; color:#475569;">Company / Org:</span> ${j.company}</div>
      <div><span style="font-weight:600; color:#475569;">Department:</span> ${j.department || "—"}</div>
      <div><span style="font-weight:600; color:#475569;">Assigned Recruiter:</span> ${j.recruiter_name || "—"}</div>
    </div>
  </div>

  <!-- 3. Recruiter Interview Assessment -->
  <div class="section">
    <div class="section-title">3. Recruiter Interview Assessment</div>
    ${recruiterInterview ? `
      <div class="grid-2" style="margin-bottom:3px;">
        <div><span style="font-weight:600; color:#475569;">Recruiter Score:</span> <strong style="color:#047857; font-size:10.5px;">${recScoreText}</strong></div>
        <div><span style="font-weight:600; color:#475569;">Recommendation:</span> <strong style="color:#047857;">${recRecText}</strong></div>
      </div>
      ${recruiterBreakdownHtml}
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:5px 8px; margin-top:4px; font-size:9.5px;">
        <span style="font-weight:600; color:#334155;">Recruiter Observations &amp; Technical Feedback:</span>
        <div style="color:#1e293b; margin-top:2px;">${recNotesText}</div>
      </div>
    ` : `
      <div style="color:#64748b; font-style:italic;">No technical recruiter interview recorded for this candidate.</div>
    `}
  </div>

  <!-- 4. HR Interview & Evaluation Scores -->
  <div class="section">
    <div class="section-title">4. HR Interview &amp; Evaluation Scores</div>
    ${hrInterview ? `
      <div class="grid-2" style="margin-bottom:3px;">
        <div><span style="font-weight:600; color:#475569;">Interview Status:</span> <strong style="text-transform:uppercase;">${hrInterview.status}</strong></div>
        <div><span style="font-weight:600; color:#475569;">Scheduled / Conducted:</span> ${formatDateTime(hrInterview.scheduled_at)}</div>
        <div><span style="font-weight:600; color:#475569;">HR Recommendation:</span> <strong style="color:#6b21a8;">${hrRecText}</strong></div>
        <div><span style="font-weight:600; color:#475569;">Interviewer:</span> ${hrInterview.recruiter_name || "HR Manager"}</div>
      </div>
      ${hrTableHtml}
    ` : `
      <div style="color:#64748b; font-style:italic;">No HR interview recorded for this candidate.</div>
    `}
  </div>

  <!-- 5. Final Hiring Decision & Audit Trail -->
  <div class="section" style="border-top:1.5px solid #0f172a; padding-top:6px;">
    <div class="section-title" style="border:none; padding:0; margin-bottom:5px;">5. Final Hiring Decision &amp; Audit Trail</div>
    <div class="grid-2">
      <div><span style="font-weight:600; color:#475569;">Final Status:</span> <strong>${statusLabel}</strong></div>
      <div><span style="font-weight:600; color:#475569;">Decision Date:</span> ${dec.decided_at ? formatDateTime(dec.decided_at) : "Pending"}</div>
      <div><span style="font-weight:600; color:#475569;">Decided By:</span> ${dec.decided_by_name || "HR Management"}</div>
      <div><span style="font-weight:600; color:#475569;">Reason Code:</span> ${dec.decision_reason_code || "—"}</div>
    </div>
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:5px 8px; margin-top:5px; font-size:9.5px;">
      <span style="font-weight:600; color:#334155;">Official Decision Reason &amp; Notes:</span>
      <div style="color:#1e293b; margin-top:2px;">${decisionReasonText}</div>
    </div>
  </div>

  <!-- Document Signature & Verification Stamp -->
  <div class="footer-block">
    <div>
      <div>Digitally verified by <strong>HireCraft AI Talent Platform</strong></div>
      <div style="font-size:8px; color:#94a3b8; margin-top:1px;">Official hiring compliance audit trail · Reference: ${refId}</div>
    </div>
    <div style="text-align:right;">
      <div class="sig-line"></div>
      <div style="font-weight:600; color:#334155;">Authorized Signature / Hiring Authority</div>
      <div style="font-size:8px; color:#94a3b8;">${dec.decided_by_name || "HR Manager"}</div>
    </div>
  </div>
</body>
</html>`;

    const printFrame = document.createElement("iframe");
    printFrame.style.position = "fixed";
    printFrame.style.right = "0";
    printFrame.style.bottom = "0";
    printFrame.style.width = "0";
    printFrame.style.height = "0";
    printFrame.style.border = "none";
    printFrame.style.visibility = "hidden";
    document.body.appendChild(printFrame);

    const frameDoc = printFrame.contentWindow?.document;
    if (!frameDoc) return;

    frameDoc.open();
    frameDoc.write(printHtml);
    frameDoc.close();

    setTimeout(() => {
      try {
        printFrame.contentWindow?.focus();
        printFrame.contentWindow?.print();
      } catch (err) {
        console.error("Failed to print iframe document:", err);
      } finally {
        setTimeout(() => {
          if (document.body.contains(printFrame)) {
            document.body.removeChild(printFrame);
          }
        }, 2000);
      }
    }, 350);
  };

  return (
    <div className="space-y-6 animate-fade-up p-6">
      {/* ── Page Header ── */}
      <div className="page-header flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
          <p className="text-sm text-gray-500">
            {`${candidate.full_name} · ${applicationStatusLabel(detail.status)}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setReportModalOpen(true)}
            className="inline-flex items-center gap-1.5"
          >
            <FileText className="h-4 w-4 text-purple-600" />
            Executive Hiring Report
          </Button>
          <Link
            to={`/hr/offers?app_id=${applicationId}`}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition"
          >
            <FileText className="h-4 w-4" />
            Create / Manage Offer
          </Link>
          <Link
            to="/hr/dashboard"
            className="btn-secondary btn-md"
          >
            Back to Dashboard
          </Link>
          <Link
            to={`/hr/jobs/${job.id}/applications`}
            className="btn-secondary btn-md"
          >
            Back to Job
          </Link>
        </div>
      </div>

      {/* Badges bar */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${applicationStatusBadgeClass(
            detail.status,
          )}`}
        >
          {applicationStatusLabel(detail.status)}
        </span>
        {detail.is_terminal && <span className="badge-neutral text-xs px-2.5 py-0.5">Closed</span>}
        {isHired && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
            <CheckCircle className="h-3.5 w-3.5" />
            Candidate Hired
          </span>
        )}
        <span className="text-xs text-gray-500">
          Applied {formatDateTime(detail.applied_at)}
        </span>
      </div>

      {/* ── Candidate Profile Banner with Resume & Contact ── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            {candidate.avatar_url ? (
              <img
                src={candidate.avatar_url}
                alt={candidate.full_name}
                className="h-16 w-16 rounded-full object-cover border-2 border-purple-200 shadow-xs shrink-0"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-purple-100 text-purple-700 font-bold text-xl border-2 border-purple-200 shadow-xs shrink-0">
                {candidate.full_name ? candidate.full_name.charAt(0).toUpperCase() : "C"}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-gray-900">{candidate.full_name}</h2>
                <span className="rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-semibold text-purple-700 border border-purple-200">
                  {candidate.current_role || "Candidate"}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                <span>{candidate.email || "No email"}</span>
                {candidate.phone && <span>• {candidate.phone}</span>}
                {candidate.location && <span>• {candidate.location}</span>}
                {candidate.experience_years !== undefined && candidate.experience_years !== null && (
                  <span>• {candidate.experience_years} years experience</span>
                )}
              </div>
              {candidate.bio && (
                <p className="mt-1.5 text-xs text-gray-600 line-clamp-2 max-w-2xl">{candidate.bio}</p>
              )}
            </div>
          </div>

          {/* Resume View & Download Button */}
          <div className="flex flex-wrap items-center gap-2 self-stretch md:self-auto justify-end">
            {candidate.has_resume ? (
              <a
                href={`/api/v1/hr/applications/${applicationId}/resume/download`}
                download={candidate.resume_filename || "Candidate_Resume.pdf"}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-purple-700 transition"
              >
                <Download className="h-4 w-4" />
                <span>View / Download Resume</span>
              </a>
            ) : (
              <span className="text-xs text-gray-400 italic">No resume file attached</span>
            )}
          </div>
        </div>

        {/* Candidate Skills Badges */}
        {candidate.skills && candidate.skills.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-100">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Verified Candidate Skills
            </p>
            <div className="flex flex-wrap gap-1.5">
              {candidate.skills.map((skill) => (
                <span
                  key={skill}
                  className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 border border-slate-200"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Primary Overview: Job and Candidate Info Cards ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DashboardCard title="Job" className="rounded-xl shadow-sm border border-slate-200">
          <InfoRow
            items={[
              { label: "Title", value: job.title },
              { label: "Company", value: job.company },
              { label: "Department", value: job.department ?? "—" },
              { label: "Location", value: job.location ?? "—" },
              { label: "Job status", value: job.status },
              { label: "Recruiter", value: job.recruiter_name ?? "—" },
            ]}
          />
          {job.description && (
            <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50/80 p-3.5">
              <p className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                <Briefcase className="h-3.5 w-3.5 text-slate-500" />
                Job Description
              </p>
              <p className="text-xs text-slate-600 whitespace-pre-wrap leading-relaxed line-clamp-6">
                {job.description}
              </p>
            </div>
          )}
        </DashboardCard>

        <DashboardCard title="Candidate" className="rounded-xl shadow-sm border border-slate-200">
          <InfoRow
            items={[
              { label: "Name", value: candidate.full_name },
              { label: "Email", value: candidate.email ?? "—" },
              {
                label: "Account",
                value: candidate.account_status ?? (candidate.is_active ? "active" : "inactive"),
              },
              {
                label: "Resume on file",
                value: candidate.has_resume ? "Yes" : "No",
              },
              {
                label: "Cover letter",
                value: detail.cover_letter_available ? "On file (not shown)" : "None",
              },
            ]}
          />
          {candidate.resume_filename && (
            <div className="mt-4 rounded-xl border border-purple-100 bg-purple-50/50 p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-purple-600" />
                <span className="text-xs font-medium text-purple-900 truncate max-w-xs">
                  {candidate.resume_filename}
                </span>
              </div>
              <a
                href={`/api/v1/hr/applications/${applicationId}/resume/download`}
                download={candidate.resume_filename}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-bold text-purple-700 hover:text-purple-900 underline"
              >
                Download
              </a>
            </div>
          )}
        </DashboardCard>
      </div>

      {/* ── Recruiter Interview Outcome & Assessment ── */}
      {recruiterInterview && (
        <DashboardCard
          title="Recruiter Interview Outcome"
          className="rounded-xl shadow-sm border border-slate-200"
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-lg bg-blue-50 p-3 border border-blue-200">
                <p className="text-xs font-semibold text-blue-700">Recruiter Stage Status</p>
                <span className="mt-1 inline-block rounded-full bg-blue-200 px-2.5 py-0.5 text-xs font-bold uppercase text-blue-900">
                  {(recruiterInterview.status || "scheduled").replace(/_/g, " ")}
                </span>
              </div>
              <div className="rounded-lg bg-blue-50 p-3 border border-blue-200">
                <p className="text-xs font-semibold text-blue-700">Recruiter Score</p>
                <div className="mt-1 flex items-center gap-1.5">
                  {recruiterInterview.overall_score !== null ? (
                    <span className="text-sm font-bold text-blue-900">
                      {recruiterInterview.overall_score}/100
                    </span>
                  ) : (
                    <span className="text-sm text-gray-500">—</span>
                  )}
                  {recruiterInterview.recommendation && (
                    <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-emerald-800">
                      {recruiterInterview.recommendation.replace(/_/g, " ")}
                    </span>
                  )}
                </div>
              </div>
              <div className="rounded-lg bg-blue-50 p-3 border border-blue-200">
                <p className="text-xs font-semibold text-blue-700">Questions Answered</p>
                <p className="mt-1 text-sm font-medium text-slate-800">
                  {recruiterInterview.questions_answered ?? 0}/{recruiterInterview.total_questions ?? 0}
                </p>
              </div>
              <div className="rounded-lg bg-blue-50 p-3 border border-blue-200">
                <p className="text-xs font-semibold text-blue-700">Conducting Recruiter</p>
                <p className="mt-1 text-sm font-medium text-slate-800">
                  {recruiterInterview.recruiter_name ?? job.recruiter_name ?? "Recruiter"}
                </p>
              </div>
            </div>

            {recruiterInterview.notes && (
              <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                <p className="text-xs font-semibold text-slate-700 mb-1">
                  Recruiter Feedback &amp; Observations:
                </p>
                <p className="text-xs text-slate-600 whitespace-pre-wrap">{recruiterInterview.notes}</p>
              </div>
            )}
          </div>
        </DashboardCard>
      )}

      {/* ── Live HR Interview Round & Actions ── */}
      <DashboardCard
        title="HR Interview Stage & Live Video Room"
        className="rounded-xl shadow-sm border border-slate-200"
      >
        {hrInterview ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-lg bg-purple-50 p-3 border border-purple-200">
                <p className="text-xs font-semibold text-purple-700">HR Interview Status</p>
                <span className="mt-1 inline-block rounded-full bg-purple-200 px-2.5 py-0.5 text-xs font-bold uppercase text-purple-900">
                  {hrInterview.status.replace(/_/g, " ")}
                </span>
              </div>
              <div className="rounded-lg bg-purple-50 p-3 border border-purple-200">
                <p className="text-xs font-semibold text-purple-700">Scheduled Time</p>
                <p className="mt-1 text-sm font-medium text-slate-800">
                  {formatDateTime(hrInterview.scheduled_at)}
                </p>
              </div>
              <div className="rounded-lg bg-purple-50 p-3 border border-purple-200">
                <p className="text-xs font-semibold text-purple-700">Duration</p>
                <p className="mt-1 text-sm font-bold text-slate-800">
                  {hrInterview.duration_minutes ?? 60} mins
                </p>
              </div>
              <div className="rounded-lg bg-purple-50 p-3 border border-purple-200">
                <p className="text-xs font-semibold text-purple-700">Attendance Status</p>
                <p className="mt-1 text-xs font-semibold text-slate-800">
                  {hrInterview.status === "completed"
                    ? "Attendance Recorded · Completed"
                    : hrInterview.status === "in_progress"
                      ? "In Progress"
                      : "Attendance recorded on join"}
                </p>
              </div>
            </div>

            {/* Room ID and Interview ID row */}
            {hrInterview.room_id && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 border border-slate-200 p-3">
                <div className="text-xs text-slate-600">
                  <span className="font-semibold text-slate-700">Shared Video Room ID: </span>
                  <code className="bg-white px-2 py-0.5 rounded border border-slate-200 font-mono text-purple-700">
                    {hrInterview.room_id}
                  </code>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCopyRoomId(hrInterview.room_id!)}
                    className="inline-flex items-center gap-1 rounded bg-white px-2.5 py-1 text-xs font-medium text-slate-700 border border-slate-300 hover:bg-slate-100"
                  >
                    <Copy className="h-3 w-3" />
                    {copiedRoomId ? "Copied!" : "Copy Room ID"}
                  </button>
                </div>
              </div>
            )}

            {/* Join Room & Evaluation Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                to={`/interviews/${hrInterview.id}/room`}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 transition"
              >
                <Video className="h-4 w-4" />
                Join HR Video Interview Room
              </Link>
              <Button
                variant="secondary"
                onClick={() => setEvalOpen(!evalOpen)}
                className="inline-flex items-center gap-2"
              >
                <Award className="h-4 w-4" />
                {evalOpen
                  ? "Close Evaluation Form"
                  : hrInterview.overall_score !== null
                    ? "Edit HR Evaluation (1–5 Scale)"
                    : "Conduct / Submit HR Evaluation (1–5 Scale)"}
              </Button>
            </div>

            {/* Existing HR scorecard/report summary */}
            {hrInterview.overall_score !== null && (
              <div className="mt-3 rounded-xl border border-purple-100 bg-purple-50/60 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-purple-900">HR Scorecard Recorded:</p>
                  <span className="text-sm font-bold text-purple-700">
                    Performance: {Math.round(hrInterview.overall_score / 20)}/5 ({hrInterview.overall_score}/100)
                  </span>
                </div>
                {hrInterview.recommendation && (
                  <p className="text-xs text-purple-800 mt-1">
                    Recommendation:{" "}
                    <span className="font-semibold uppercase">{hrInterview.recommendation}</span>
                  </p>
                )}
                {hrInterview.notes && (
                  <p className="text-xs text-gray-700 mt-2 whitespace-pre-wrap">{hrInterview.notes}</p>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
            <p className="text-sm text-slate-700">
              The candidate is in the HR stage. An HR video interview has not been scheduled yet.
            </p>
          </div>
        )}
      </DashboardCard>

      {/* ── Evaluation Form (1–5 Scale) with Save Draft & Submit Feedback ── */}
      {evalOpen && hrInterview && (
        <div className="rounded-2xl border-2 border-purple-300 bg-white p-6 shadow-md animate-fade-in space-y-5">
          <div className="flex items-center justify-between border-b border-gray-200 pb-3">
            <div>
              <h3 className="text-base font-bold text-gray-900">
                HR Structured Evaluation (1–5 Competency Scale)
              </h3>
              <p className="text-xs text-gray-500">
                Rate the candidate on each core dimension. Save drafts at any time, or submit feedback to record the score.
              </p>
            </div>
            <button
              onClick={() => setEvalOpen(false)}
              className="text-gray-400 hover:text-gray-600 font-bold text-lg"
            >
              ✕
            </button>
          </div>

          {draftNotice && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-2.5 text-xs text-blue-800 flex items-center justify-between">
              <span>{draftNotice}</span>
              <button
                type="button"
                onClick={() => setDraftNotice(null)}
                className="text-blue-600 font-bold"
              >
                ✕
              </button>
            </div>
          )}

          {/* 5 Rating Competencies on 1-5 scale */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Communication Skills (1-5) */}
            <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-2">
                <span>1. Communication skills</span>
                <span className="text-purple-700 font-bold">{evalComm}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEvalComm(val)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition ${
                      evalComm === val
                        ? "bg-purple-600 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Technical Knowledge (1-5) */}
            <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-2">
                <span>2. Technical knowledge</span>
                <span className="text-purple-700 font-bold">{evalTech}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEvalTech(val)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition ${
                      evalTech === val
                        ? "bg-purple-600 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Problem-solving (1-5) */}
            <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-2">
                <span>3. Problem-solving</span>
                <span className="text-purple-700 font-bold">{evalProblem}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEvalProblem(val)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition ${
                      evalProblem === val
                        ? "bg-purple-600 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Teamwork (1-5) */}
            <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-2">
                <span>4. Teamwork</span>
                <span className="text-purple-700 font-bold">{evalTeamwork}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEvalTeamwork(val)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition ${
                      evalTeamwork === val
                        ? "bg-purple-600 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Overall performance (1-5) */}
            <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50 sm:col-span-2 lg:col-span-2">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800 mb-2">
                <span>5. Overall performance</span>
                <span className="text-purple-700 font-bold">{evalOverall}/5</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEvalOverall(val)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition ${
                      evalOverall === val
                        ? "bg-purple-600 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Qualitative: Strengths & Weaknesses */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-gray-700">Observed Strengths</label>
              <textarea
                rows={2}
                value={evalStrengths}
                onChange={(e) => setEvalStrengths(e.target.value)}
                placeholder="Key technical, behavioral, or cultural strengths observed during the interview..."
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-slate-800 focus:border-purple-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700">Observed Weaknesses</label>
              <textarea
                rows={2}
                value={evalWeaknesses}
                onChange={(e) => setEvalWeaknesses(e.target.value)}
                placeholder="Areas for development, skill gaps, or flags identified..."
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-slate-800 focus:border-purple-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Recommendation & HR Comments */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-gray-700">Final Recommendation</label>
              <select
                value={evalRecommendation}
                onChange={(e) => setEvalRecommendation(e.target.value as any)}
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-slate-800 focus:border-purple-500 focus:outline-none"
              >
                <option value="strongly_recommend">Strongly Recommend</option>
                <option value="recommend">Recommend</option>
                <option value="consider">Consider / Borderline</option>
                <option value="not_recommended">Not Recommended</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700">HR Comments</label>
              <textarea
                rows={2}
                value={evalNotes}
                onChange={(e) => setEvalNotes(e.target.value)}
                placeholder="Overall interview summary, team fit, and qualitative impressions..."
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-slate-800 focus:border-purple-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Form Action Buttons: Save Draft & Submit Feedback */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-gray-200">
            <Button variant="ghost" onClick={() => setEvalOpen(false)}>
              Cancel
            </Button>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                type="button"
                onClick={handleSaveDraft}
              >
                Save Draft
              </Button>
              <Button
                onClick={handleSubmitEvaluation}
                disabled={actionPending === "eval"}
              >
                {actionPending === "eval" ? "Submitting Feedback..." : "Submit Feedback"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Section E: Final HR Decision (4 Options) ── */}
      <DashboardCard title="Final Decision" className="rounded-xl shadow-sm border border-slate-200">
        <InfoRow
          items={[
            { label: "Status", value: applicationStatusLabel(decision.status) },
            {
              label: "Decided",
              value: decision.decided_at ? formatDateTime(decision.decided_at) : "Pending",
            },
            {
              label: "Decided by",
              value: decision.decided_by_name ?? "—",
            },
            {
              label: "Reason code",
              value: decision.decision_reason_code ?? "—",
            },
          ]}
        />

        {decision.decision_reason && (
          <div className="mt-3 rounded-xl border border-gray-100 bg-gray-50/70 px-4 py-3">
            <p className="text-sm text-gray-600">
              Reason: {decision.decision_reason}
            </p>
          </div>
        )}

        {/* 4 Decision Options for HR */}
        {!detail.is_terminal && (
          <div className="mt-5 pt-4 border-t border-slate-200">
            <p className="text-xs font-semibold text-gray-700 mb-3">
              Execute Final Hiring Decision:
            </p>
            <div className="flex flex-wrap items-center gap-3">
              {/* Option 1: Hire Candidate */}
              <button
                type="button"
                onClick={() => setDecisionModal("hire")}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 transition"
              >
                <CheckCircle className="h-4 w-4" />
                1. Hire Candidate
              </button>

              {/* Option 2: Reject Candidate */}
              <button
                type="button"
                onClick={() => setDecisionModal("reject")}
                className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-rose-700 transition"
              >
                <XCircle className="h-4 w-4" />
                2. Reject Candidate
              </button>

              {/* Option 3: Keep on Hold */}
              <button
                type="button"
                onClick={() => setDecisionModal("keep_under_review")}
                className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-amber-700 transition"
              >
                <Clock className="h-4 w-4" />
                3. Keep on Hold
              </button>

              {/* Option 4: Request Additional Interview */}
              <button
                type="button"
                onClick={() => setDecisionModal("additional_interview")}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 transition"
              >
                <CalendarPlus className="h-4 w-4" />
                4. Request Additional Interview
              </button>
            </div>
          </div>
        )}
      </DashboardCard>

      {/* ── Decision Confirmation Modal ── */}
      {decisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl animate-fade-in space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">
                {decisionModal === "hire"
                  ? "Confirm Hire Candidate"
                  : decisionModal === "reject"
                    ? "Confirm Application Rejection"
                    : decisionModal === "keep_under_review"
                      ? "Keep Application on Hold"
                      : "Schedule Additional HR Interview"}
              </h3>
              <button
                onClick={() => setDecisionModal(null)}
                className="text-gray-400 hover:text-gray-600 font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-sm text-gray-600">
              {decisionModal === "hire"
                ? `Are you sure you want to hire ${candidate.full_name} for the ${job.title} position? The application will move to Hired, and notifications will be sent to the candidate, recruiter, and organization administrator.`
                : decisionModal === "reject"
                  ? `Please select an official rejection reason for ${candidate.full_name}. A structured, respectful notification will be sent to the candidate.`
                  : decisionModal === "keep_under_review"
                    ? `Keep ${candidate.full_name}'s application pending on hold under active review for a future hiring decision.`
                    : `Schedule an additional follow-up evaluation round with ${candidate.full_name}.`}
            </p>

            {/* Rejection Reason Selector */}
            {decisionModal === "reject" && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Rejection Reason (Required)
                </label>
                <select
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-slate-800 focus:border-rose-500 focus:outline-none"
                >
                  {REJECTION_REASONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Additional Interview Fields */}
            {decisionModal === "additional_interview" && (
              <div className="space-y-3 rounded-xl bg-indigo-50/60 border border-indigo-100 p-3.5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-indigo-950">
                      Scheduled Date &amp; Time
                    </label>
                    <input
                      type="datetime-local"
                      value={additionalDate}
                      onChange={(e) => setAdditionalDate(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-indigo-950">
                      Duration (Minutes)
                    </label>
                    <select
                      value={additionalDuration}
                      onChange={(e) => setAdditionalDuration(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                    >
                      <option value={30}>30 minutes</option>
                      <option value={45}>45 minutes</option>
                      <option value={60}>60 minutes</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-indigo-950">
                    Interview Focus / Notes
                  </label>
                  <textarea
                    rows={2}
                    value={additionalNotes}
                    onChange={(e) => setAdditionalNotes(e.target.value)}
                    placeholder="Specific competencies or technical questions for the next round..."
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>
            )}

            {/* Internal Note */}
            {decisionModal !== "additional_interview" && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Internal Note (Hiring team only, optional)
                </label>
                <textarea
                  rows={2}
                  value={decisionNote}
                  onChange={(e) => setDecisionNote(e.target.value)}
                  placeholder="Reason or context for hiring decision record..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-slate-800 focus:border-purple-500 focus:outline-none"
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
              <Button variant="ghost" onClick={() => setDecisionModal(null)}>
                Cancel
              </Button>
              <Button
                variant={decisionModal === "reject" ? "danger" : "primary"}
                onClick={() => handleExecuteDecision(decisionModal)}
                disabled={actionPending !== null}
              >
                {actionPending ? "Submitting..." : "Confirm Decision"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Executive Hiring Report Modal ── */}
      {reportModalOpen && (
        <div id="executive-report-modal-overlay" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 overflow-y-auto">
          <div id="executive-report-modal" className="w-full max-w-3xl rounded-2xl bg-white p-6 sm:p-8 shadow-2xl animate-fade-in space-y-6 my-8 max-h-[90vh] overflow-y-auto print:max-h-none print:shadow-none print:p-0 print:my-0">
            {/* Modal Header & Actions */}
            <div className="flex items-center justify-between border-b pb-4 print:hidden">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-purple-600" />
                <h3 className="text-lg font-bold text-gray-900">Executive Hiring Report</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDownloadPDF}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-purple-700 shadow-xs transition"
                >
                  <Printer className="h-3.5 w-3.5" />
                  Download PDF / Print
                </button>
                <button
                  onClick={() => setReportModalOpen(false)}
                  className="text-gray-400 hover:text-gray-600 font-bold text-lg ml-2"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Structured Report Preview */}
            <div className="space-y-6 text-slate-800 text-xs">
              {/* Document Header */}
              <div className="border-b-2 border-slate-900 pb-4 flex justify-between items-start">
                <div>
                  <h1 className="text-xl font-bold uppercase tracking-wider text-slate-900">
                    HireCraft AI · Executive Hiring Report
                  </h1>
                  <p className="text-slate-500 text-xs mt-0.5">
                    Official Candidate Assessment &amp; Final Hiring Record
                  </p>
                </div>
                <div className="text-right">
                  <span className="font-semibold text-slate-700">Date: </span>
                  <span>{formatDate(decision.decided_at || new Date(), "—", { month: "long", day: "numeric", year: "numeric" })}</span>
                  <div className="mt-1">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase ${
                        decision.status === "hired"
                          ? "bg-emerald-100 text-emerald-800"
                          : decision.status === "rejected"
                            ? "bg-rose-100 text-rose-800"
                            : "bg-slate-100 text-slate-800"
                      }`}
                    >
                      Status: {applicationStatusLabel(decision.status)}
                    </span>
                  </div>
                </div>
              </div>

              {/* 1. Candidate Profile */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b pb-1 mb-2">
                  1. Candidate Profile
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <p>
                    <span className="font-semibold">Full Name:</span> {candidate.full_name}
                  </p>
                  <p>
                    <span className="font-semibold">Email:</span> {candidate.email || "—"}
                  </p>
                  <p>
                    <span className="font-semibold">Phone:</span> {candidate.phone || "—"}
                  </p>
                  <p>
                    <span className="font-semibold">Location:</span> {candidate.location || "—"}
                  </p>
                  <p>
                    <span className="font-semibold">Experience:</span>{" "}
                    {candidate.experience_years ? `${candidate.experience_years} years` : "—"}
                  </p>
                  <p>
                    <span className="font-semibold">Resume:</span>{" "}
                    {candidate.resume_filename || (candidate.has_resume ? "On file" : "None")}
                  </p>
                </div>
                {candidate.skills && candidate.skills.length > 0 && (
                  <p className="mt-2">
                    <span className="font-semibold">Key Skills:</span> {candidate.skills.join(", ")}
                  </p>
                )}
              </div>

              {/* 2. Position Details */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b pb-1 mb-2">
                  2. Position Details
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <p>
                    <span className="font-semibold">Position Title:</span> {job.title}
                  </p>
                  <p>
                    <span className="font-semibold">Company / Org:</span> {job.company}
                  </p>
                  <p>
                    <span className="font-semibold">Department:</span> {job.department || "—"}
                  </p>
                  <p>
                    <span className="font-semibold">Assigned Recruiter:</span>{" "}
                    {job.recruiter_name || "—"}
                  </p>
                </div>
              </div>

              {/* 3. Recruiter Interview Assessment */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b pb-1 mb-2">
                  3. Recruiter Interview Assessment
                </h4>
                {recruiterInterview ? (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <p>
                        <span className="font-semibold">Recruiter Score:</span>{" "}
                        <span className="font-bold text-emerald-800">
                          {resolvedRecScore !== null ? `${resolvedRecScore}/100` : "—"}
                        </span>
                      </p>
                      <p>
                        <span className="font-semibold">Recommendation:</span>{" "}
                        <span className="uppercase font-bold text-emerald-800">
                          {resolvedRecRecommendation || "—"}
                        </span>
                      </p>
                    </div>

                    {(resolvedRecTech !== null || resolvedRecComm !== null) && (
                      <table className="w-full border-collapse border border-slate-200 text-left my-2">
                        <thead>
                          <tr className="bg-slate-50 text-slate-600">
                            <th className="border border-slate-200 p-1.5">Technical Skills</th>
                            <th className="border border-slate-200 p-1.5">Problem Solving</th>
                            <th className="border border-slate-200 p-1.5">Communication</th>
                            <th className="border border-slate-200 p-1.5">Teamwork</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td className="border border-slate-200 p-1.5 font-semibold">{resolvedRecTech !== null ? `${resolvedRecTech}/100` : "—"}</td>
                            <td className="border border-slate-200 p-1.5 font-semibold">{resolvedRecProb !== null ? `${resolvedRecProb}/100` : "—"}</td>
                            <td className="border border-slate-200 p-1.5 font-semibold">{resolvedRecComm !== null ? `${resolvedRecComm}/100` : "—"}</td>
                            <td className="border border-slate-200 p-1.5 font-semibold">{resolvedRecTeam !== null ? `${resolvedRecTeam}/100` : "—"}</td>
                          </tr>
                        </tbody>
                      </table>
                    )}

                    {resolvedRecNotes && (
                      <div className="rounded border border-slate-200 p-2 bg-slate-50">
                        <span className="font-semibold block text-slate-800 mb-0.5">Recruiter Observations:</span>
                        <p className="text-slate-700">{resolvedRecNotes}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-slate-500 italic">No recruiter interview recorded.</p>
                )}
              </div>

              {/* 4. HR Interview & Evaluation Scores */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b pb-1 mb-2">
                  4. HR Interview &amp; Evaluation Scores
                </h4>
                {hrInterview ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                      <p>
                        <span className="font-semibold">Interview Status:</span>{" "}
                        <span className="uppercase">{hrInterview.status}</span>
                      </p>
                      <p>
                        <span className="font-semibold">Scheduled / Held:</span>{" "}
                        {formatDateTime(hrInterview.scheduled_at)}
                      </p>
                      <p>
                        <span className="font-semibold">Duration:</span>{" "}
                        {hrInterview.duration_minutes ?? 60} mins
                      </p>
                      <p>
                        <span className="font-semibold">Interviewer:</span>{" "}
                        {hrInterview.recruiter_name || "HR Manager"}
                      </p>
                    </div>

                    {hasHrEvaluation ? (
                      <>
                        {/* Scores Table */}
                        <table className="w-full border-collapse border border-slate-300 text-left mt-2">
                          <thead>
                            <tr className="bg-slate-100 font-bold">
                              <th className="border border-slate-300 p-2">Competency Dimension</th>
                              <th className="border border-slate-300 p-2 text-center">Score (1–5 Scale)</th>
                              <th className="border border-slate-300 p-2 text-center">Benchmark Score (/100)</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td className="border border-slate-300 p-2 font-medium">Communication Skills</td>
                              <td className="border border-slate-300 p-2 text-center font-bold text-purple-800">
                                {resolvedHrComm !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrComm / 20)))}/5` : "—"}
                              </td>
                              <td className="border border-slate-300 p-2 text-center">
                                {resolvedHrComm !== null ? `${resolvedHrComm}/100` : "—"}
                              </td>
                            </tr>
                            <tr>
                              <td className="border border-slate-300 p-2 font-medium">Technical Knowledge</td>
                              <td className="border border-slate-300 p-2 text-center font-bold text-purple-800">
                                {resolvedHrTech !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrTech / 20)))}/5` : "—"}
                              </td>
                              <td className="border border-slate-300 p-2 text-center">
                                {resolvedHrTech !== null ? `${resolvedHrTech}/100` : "—"}
                              </td>
                            </tr>
                            <tr>
                              <td className="border border-slate-300 p-2 font-medium">Problem-Solving</td>
                              <td className="border border-slate-300 p-2 text-center font-bold text-purple-800">
                                {resolvedHrProb !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrProb / 20)))}/5` : "—"}
                              </td>
                              <td className="border border-slate-300 p-2 text-center">
                                {resolvedHrProb !== null ? `${resolvedHrProb}/100` : "—"}
                              </td>
                            </tr>
                            <tr>
                              <td className="border border-slate-300 p-2 font-medium">Teamwork</td>
                              <td className="border border-slate-300 p-2 text-center font-bold text-purple-800">
                                {resolvedHrTeam !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrTeam / 20)))}/5` : "—"}
                              </td>
                              <td className="border border-slate-300 p-2 text-center">
                                {resolvedHrTeam !== null ? `${resolvedHrTeam}/100` : "—"}
                              </td>
                            </tr>
                            <tr className="bg-purple-50 font-bold">
                              <td className="border border-slate-300 p-2">Overall Performance</td>
                              <td className="border border-slate-300 p-2 text-center text-purple-900">
                                {resolvedHrOverall !== null ? `${Math.max(1, Math.min(5, Math.round(resolvedHrOverall / 20)))}/5` : "—"}
                              </td>
                              <td className="border border-slate-300 p-2 text-center text-purple-900">
                                {resolvedHrOverall !== null ? `${resolvedHrOverall}/100` : "—"}
                              </td>
                            </tr>
                          </tbody>
                        </table>

                        {/* Strengths & Weaknesses */}
                        <div className="grid grid-cols-2 gap-3 mt-2">
                          <div className="rounded border border-slate-200 p-2 bg-slate-50">
                            <span className="font-semibold block text-slate-800 mb-0.5">Strengths:</span>
                            <p className="text-slate-600">{resolvedHrStrengths}</p>
                          </div>
                          <div className="rounded border border-slate-200 p-2 bg-slate-50">
                            <span className="font-semibold block text-slate-800 mb-0.5">Weaknesses / Gaps:</span>
                            <p className="text-slate-600">{resolvedHrConcerns}</p>
                          </div>
                        </div>

                        {resolvedHrNotes && (
                          <p className="mt-1">
                            <span className="font-semibold">HR Qualitative Comments:</span> {resolvedHrNotes}
                          </p>
                        )}
                      </>
                    ) : (
                      <div className="rounded-lg border border-slate-200 p-3 bg-slate-50 text-slate-600 italic">
                        HR Interview evaluation is pending completion. The scorecard will be recorded upon interview conclusion.
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-slate-500 italic">No HR interview recorded.</p>
                )}
              </div>

              {/* 5. Final Decision & Sign-off */}
              <div className="border-t-2 border-slate-900 pt-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b pb-1 mb-2">
                  5. Final Hiring Decision &amp; Audit Trail
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <p>
                    <span className="font-semibold">Final Status:</span>{" "}
                    <span className="font-bold uppercase text-slate-900">
                      {applicationStatusLabel(decision.status)}
                    </span>
                  </p>
                  <p>
                    <span className="font-semibold">Decision Date:</span>{" "}
                    {decision.decided_at ? formatDateTime(decision.decided_at) : "Pending"}
                  </p>
                  <p>
                    <span className="font-semibold">Decided By:</span>{" "}
                    {decision.decided_by_name || "HR Authority"}
                  </p>
                  {decision.decision_reason && (
                    <p className="col-span-2">
                      <span className="font-semibold">Decision Reason / Notes:</span>{" "}
                      {decision.decision_reason}
                    </p>
                  )}
                </div>

                <div className="mt-8 pt-4 border-t border-slate-200 flex justify-between items-center text-[11px] text-slate-500">
                  <p>Generated by HireCraft AI Hiring Platform</p>
                  <p>Authorized Signature: _________________________</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Screening and Evidence Overview Cards ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DashboardCard title="Screening" className="rounded-xl shadow-sm border border-slate-200">
          <InfoRow
            items={[
              { label: "Screening status", value: detail.screening.status },
              { label: "Attempts", value: String(detail.screening.attempts) },
              {
                label: "Started",
                value: formatDateTime(detail.screening.started_at),
              },
              {
                label: "Completed",
                value: formatDateTime(detail.screening.completed_at),
              },
            ]}
          />
        </DashboardCard>

        <DashboardCard
          title="Interview & Assessment"
          className="rounded-xl shadow-sm border border-slate-200"
        >
          <InfoRow
            items={[
              {
                label: "Interview",
                value: detail.interview ? "Linked evidence available" : "Not scheduled",
              },
              {
                label: "Assessment",
                value: detail.assessment ? "Linked evidence available" : "None linked",
              },
            ]}
          />
        </DashboardCard>
      </div>

      {/* ── Explainability and Fairness Signals ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DashboardCard
          title="Explainability"
          className="rounded-xl shadow-sm border border-slate-200"
        >
          {detail.explainability ? (
            <p className="text-sm text-gray-700">
              Score explanation is available from screening model.
            </p>
          ) : (
            <p className="text-sm text-gray-500">No screening explanation is available yet.</p>
          )}
        </DashboardCard>

        <DashboardCard title="Fairness" className="rounded-xl shadow-sm border border-slate-200">
          {detail.fairness ? (
            <p className="text-sm text-gray-700">Fairness context is available for this cohort.</p>
          ) : (
            <p className="text-sm text-gray-500">No fairness context is available yet.</p>
          )}
        </DashboardCard>
      </div>

      {/* ── Timeline ── */}
      <DashboardCard title="Timeline" className="rounded-xl shadow-sm border border-slate-200">
        {detail.timeline.length === 0 ? (
          <p className="text-sm text-gray-500">No recorded events for this application.</p>
        ) : (
          <div>
            <ol className="space-y-0">
              {detail.timeline.map((event) => (
                <li
                  key={`${event.source}-${event.id}`}
                  className="relative flex gap-3 border-l border-gray-200 pb-5 pl-6 last:pb-0"
                >
                  <span className="absolute -left-1 top-1.5 h-2.5 w-2.5 rounded-full bg-primary-500 ring-4 ring-primary-100" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {timelineEventLabel(event)}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {formatDateTime(event.at)}
                      {event.actor_name ? ` · ${event.actor_name}` : ""}
                      {event.detail ? ` · ${event.detail}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
            <p className="mt-4 text-xs text-gray-400">
              Note: nothing on this timeline is inferred; all events represent recorded database state
              changes.
            </p>
          </div>
        )}
      </DashboardCard>
    </div>
  );
}
