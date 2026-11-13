import React, { useEffect, useState } from "react";
import {
  FileText,
  ShieldCheck,
  UserCheck,
  CheckCircle,
  CheckCircle2,
  Clock,
  Download,
  Upload,
  HelpCircle,
  Eye,
  Calendar,
  Check,
  Sparkles,
  X,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  ArrowRight,
  Gift,
  Send,
  DollarSign,
  FileCheck2,
  BadgeCheck,
} from "lucide-react";

import postHiringApi from "../../api/postHiring";
import type { CandidateDocument, Employee, JobOffer, OnboardingTask } from "../../types/postHiring";
import { useToast } from "../../contexts/ToastContext";
import { formatDate } from "../../utils/dateTime";
import OfferLetterModal from "../../components/postHiring/OfferLetterModal";

// Standard 4 required verification document types
const STANDARD_DOC_TYPES = [
  {
    type: "gov_id",
    title: "Government Photo ID (Passport / Driving License / National ID)",
    category: "Identity Proof",
    description: "Valid Passport, Driver's License, or Government National ID card (clear front & back).",
  },
  {
    type: "address_proof",
    title: "Proof of Address (Utility Bill / Bank Statement)",
    category: "Address Proof",
    description: "Recent utility bill (electricity, gas, water), bank statement, or rental agreement (issued within last 3 months).",
  },
  {
    type: "education",
    title: "Educational Degree Certificate & Transcripts",
    category: "Academic Records",
    description: "Highest completed degree certificate, diploma, or official consolidated mark transcripts.",
  },
  {
    type: "previous_employment",
    title: "Previous Relieving Letter & Experience Certificates",
    category: "Employment History",
    description: "Relieving letter, service experience certificate, or latest 3 months salary slips from previous employer.",
  },
];

export default function CandidateOffersOnboarding() {
  const { addToast } = useToast();

  const [activeTab, setActiveTab] = useState<"offers" | "documents" | "onboarding">("offers");
  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [documents, setDocuments] = useState<CandidateDocument[]>([]);
  const [onboarding, setOnboarding] = useState<Employee | null>(null);
  const [loading, setLoading] = useState(true);

  // Accordion states
  const [benefitsOpen, setBenefitsOpen] = useState(true);
  const [termsOpen, setTermsOpen] = useState(true);

  // Offer Actions
  const [selectedOffer, setSelectedOffer] = useState<JobOffer | null>(null);
  const [viewingOfferModal, setViewingOfferModal] = useState<JobOffer | null>(null);
  const [showAcceptModal, setShowAcceptModal] = useState(false);
  const [showDeclineModal, setShowDeclineModal] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [acceptNotes, setAcceptNotes] = useState("");
  const [acceptConfirmed, setAcceptConfirmed] = useState(false);
  const [showClarifyModal, setShowClarifyModal] = useState(false);
  const [clarifyQuestion, setClarifyQuestion] = useState("");
  const [responding, setResponding] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // Document Upload
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Candidate Task Submission Modal
  const [submittingTaskItem, setSubmittingTaskItem] = useState<OnboardingTask | null>(null);
  const [taskSubmissionNotes, setTaskSubmissionNotes] = useState("");
  const [taskAttachmentUrl, setTaskAttachmentUrl] = useState("");
  const [isSubmittingTask, setIsSubmittingTask] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [offersData, docsData, onbData] = await Promise.all([
        postHiringApi.candidateGetOffers(),
        postHiringApi.candidateGetDocuments(),
        postHiringApi.candidateGetOnboarding(),
      ]);
      setOffers(offersData);
      setDocuments(docsData);
      setOnboarding(onbData);

      // Auto-focus tabs intelligently if starting afresh
      if (onbData) {
        // if user already on onboarding, keep tab
      } else if (offersData.some((o) => o.status === "accepted")) {
        // if offer accepted, document verification is primary
      }
    } catch {
      addToast("Failed to load post-hiring details", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenAcceptModal = (offer: JobOffer) => {
    setSelectedOffer(offer);
    setAcceptNotes("");
    setAcceptConfirmed(true);
    setShowAcceptModal(true);
  };

  const handleConfirmAcceptOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOffer) return;
    if (!acceptConfirmed) {
      addToast("Please check the confirmation box to proceed", "error");
      return;
    }

    setResponding(true);
    try {
      await postHiringApi.candidateRespondOffer(selectedOffer.id, "accept", undefined, acceptNotes);
      addToast(`🎉 Congratulations! You have accepted the offer for ${selectedOffer.designation}. Please submit your verification documents below.`, "success");
      setShowAcceptModal(false);
      setSelectedOffer(null);
      setAcceptNotes("");

      // Re-fetch all data and immediately switch to Document Verification tab
      await fetchData();
      setActiveTab("documents");
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to accept offer", "error");
    } finally {
      setResponding(false);
    }
  };

  const handleDeclineOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOffer) return;
    setResponding(true);
    try {
      await postHiringApi.candidateRespondOffer(selectedOffer.id, "decline", declineReason);
      addToast("Offer has been declined.", "info");
      setShowDeclineModal(false);
      setSelectedOffer(null);
      setDeclineReason("");
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to decline offer", "error");
    } finally {
      setResponding(false);
    }
  };

  const handleClarifyOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOffer) return;
    setResponding(true);
    try {
      await postHiringApi.candidateClarifyOffer(selectedOffer.id, clarifyQuestion);
      addToast("Your question has been sent to the HR team.", "success");
      setShowClarifyModal(false);
      setSelectedOffer(null);
      setClarifyQuestion("");
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to submit clarification", "error");
    } finally {
      setResponding(false);
    }
  };

  const handleDownloadPDF = async (offer: JobOffer) => {
    setDownloadingPdf(true);
    try {
      const blob = await postHiringApi.downloadOfferPdf(offer.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Job_Offer_${offer.designation.replace(/\s+/g, "_")}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      addToast("Offer letter downloaded", "success");
    } catch {
      addToast("Failed to download offer PDF", "error");
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleUploadDocument = async (e: React.FormEvent, docType: string, docTitle: string, applicationId?: string) => {
    e.preventDefault();
    if (!uploadFile) {
      addToast("Please choose a file to upload", "error");
      return;
    }

    const appId = applicationId || offers[0]?.application_id || documents[0]?.application_id;
    if (!appId) {
      addToast("Application reference missing. Please refresh the page.", "error");
      return;
    }

    setUploading(true);
    try {
      await postHiringApi.candidateUploadDocument(
        appId,
        docType,
        docTitle,
        uploadFile
      );
      addToast(`Uploaded ${docTitle} successfully! HR team has been notified.`, "success");
      setUploadingDocType(null);
      setUploadFile(null);
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to upload document", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleSubmitTaskReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!submittingTaskItem) return;
    setIsSubmittingTask(true);
    try {
      await postHiringApi.candidateSubmitTask(submittingTaskItem.id, {
        submission_notes: taskSubmissionNotes,
        attachment_url: taskAttachmentUrl || undefined,
      });
      addToast("Task submitted for HR approval!", "success");
      setSubmittingTaskItem(null);
      setTaskSubmissionNotes("");
      setTaskAttachmentUrl("");
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to submit task", "error");
    } finally {
      setIsSubmittingTask(false);
    }
  };

  const handleToggleCandidateTask = async (task: OnboardingTask) => {
    try {
      await postHiringApi.candidateToggleTask(task.id);
      addToast(task.is_completed ? "Task marked incomplete" : "Task completed!", "success");
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to update task", "error");
    }
  };

  // Determine accepted offer if any
  const acceptedOffer = offers.find((o) => o.status === "accepted");
  const hasAcceptedOffer = Boolean(acceptedOffer);

  // Merged documents: ensure all 4 standard slots exist for display
  const mergedDocuments = STANDARD_DOC_TYPES.map((std) => {
    const existing = documents.find((d) => d.document_type === std.type);
    if (existing) return existing;
    return {
      id: `virtual-${std.type}`,
      application_id: offers[0]?.application_id || "",
      candidate_id: offers[0]?.candidate_id || "",
      organization_id: offers[0]?.organization_id || "",
      document_type: std.type,
      document_title: std.title,
      file_name: undefined,
      file_url: undefined,
      file_size_bytes: undefined,
      mime_type: undefined,
      status: "not_submitted",
      hr_remarks: undefined,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    } as unknown as CandidateDocument;
  });

  const verifiedDocsCount = mergedDocuments.filter((d) => d.status === "verified").length;
  const submittedDocsCount = mergedDocuments.filter((d) => ["submitted", "verified"].includes(d.status)).length;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-blue-600" />
          My Offers & Onboarding Portal
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Review formal offers, upload verification credentials, and complete your onboarding checklist.
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab("offers")}
          className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeTab === "offers"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <FileText className="w-4 h-4" />
          Official Offers ({offers.length})
        </button>

        <button
          onClick={() => setActiveTab("documents")}
          className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeTab === "documents"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          Document Verification ({verifiedDocsCount}/{mergedDocuments.length})
        </button>

        <button
          onClick={() => setActiveTab("onboarding")}
          className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeTab === "onboarding"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <UserCheck className="w-4 h-4" />
          Onboarding Checklist {onboarding ? `(${onboarding.onboarding_progress_percent}%)` : ""}
        </button>
      </div>

      {loading ? (
        <div className="py-16 text-center text-slate-500 text-sm">Loading your records...</div>
      ) : (
        <>
          {/* TAB 1: JOB OFFERS */}
          {activeTab === "offers" && (
            <div className="space-y-6">
              {offers.length === 0 ? (
                <div className="bg-white p-12 rounded-2xl border border-slate-200 text-center text-slate-400 text-sm shadow-sm">
                  You do not have any active job offers at this time. Once HR completes their review, official offers will appear here.
                </div>
              ) : (
                offers.map((offer) => {
                  const isAccepted = offer.status === "accepted";
                  const isDeclined = offer.status === "declined";
                  const orgInitial = (offer.organization_name || "HireCraft AI").charAt(0).toUpperCase();

                  return (
                    <div key={offer.id} className="space-y-6">
                      {/* OFFER CARD MATCHING SCREENSHOT */}
                      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
                        {/* Navy Header Banner */}
                        <div className="bg-[#0a192f] text-white p-5 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                          <div className="flex items-center gap-4">
                            {/* Organization Logo Square */}
                            <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center font-extrabold text-blue-600 text-2xl shadow-sm shrink-0">
                              {orgInitial}
                            </div>

                            {/* Organization Info */}
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-lg font-bold text-white tracking-tight">
                                  {offer.organization_name || "NPnu Corp"}
                                </h3>
                              </div>
                              <p className="text-xs text-slate-300 font-medium mt-0.5">
                                {offer.department || "Cloud Infrastructure"} • {offer.work_arrangement || "Hybrid"} • {offer.work_location || "Headquarters"}
                              </p>
                            </div>

                            {/* Vertical Divider */}
                            <div className="hidden sm:block h-8 w-px bg-slate-700 mx-2" />

                            {/* Job Position Title */}
                            <div className="hidden sm:block">
                              <h2 className="text-xl font-bold text-white tracking-tight">
                                {offer.designation}
                              </h2>
                            </div>
                          </div>

                          {/* Mobile Job Title Fallback */}
                          <div className="sm:hidden w-full">
                            <h2 className="text-lg font-bold text-white tracking-tight">
                              {offer.designation}
                            </h2>
                          </div>

                          {/* Status Pill on the Right */}
                          <div>
                            {isAccepted ? (
                              <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-emerald-600 text-white shadow-sm">
                                <CheckCircle className="w-3.5 h-3.5" />
                                Offer Accepted
                              </span>
                            ) : isDeclined ? (
                              <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-rose-600 text-white shadow-sm">
                                <X className="w-3.5 h-3.5" />
                                Offer Declined
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-blue-600 text-white shadow-sm">
                                <Send className="w-3.5 h-3.5" />
                                Offer Sent
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Card Body */}
                        <div className="p-6 space-y-6">
                          {/* 4 Metric Cards Row */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-100 flex items-center gap-3.5">
                              <div className="w-10 h-10 rounded-lg bg-blue-100/70 text-blue-600 flex items-center justify-center shrink-0">
                                <Calendar className="w-5 h-5" />
                              </div>
                              <div>
                                <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider">
                                  Proposed Joining
                                </p>
                                <p className="text-sm font-bold text-slate-900 mt-0.5">
                                  {formatDate(offer.joining_date)}
                                </p>
                              </div>
                            </div>

                            <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-100 flex items-center gap-3.5">
                              <div className="w-10 h-10 rounded-lg bg-amber-100/70 text-amber-600 flex items-center justify-center shrink-0">
                                <Clock className="w-5 h-5" />
                              </div>
                              <div>
                                <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider">
                                  Offer Expiry
                                </p>
                                <p className="text-sm font-bold text-slate-900 mt-0.5">
                                  {formatDate(offer.offer_expiry_date)}
                                </p>
                              </div>
                            </div>

                            <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-100 flex items-center gap-3.5">
                              <div className="w-10 h-10 rounded-lg bg-emerald-100/70 text-emerald-600 flex items-center justify-center shrink-0">
                                <ShieldCheck className="w-5 h-5" />
                              </div>
                              <div>
                                <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider">
                                  Probation Period
                                </p>
                                <p className="text-sm font-bold text-slate-900 mt-0.5">
                                  {offer.probation_period_months} Months
                                </p>
                              </div>
                            </div>

                            <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-100 flex items-center gap-3.5">
                              <div className="w-10 h-10 rounded-lg bg-amber-100/70 text-amber-500 flex items-center justify-center shrink-0">
                                <DollarSign className="w-5 h-5" />
                              </div>
                              <div>
                                <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider">
                                  Annual Compensation
                                </p>
                                <p className="text-sm font-bold text-slate-900 mt-0.5">
                                  {offer.currency} {offer.offered_salary.toLocaleString()} / year
                                </p>
                              </div>
                            </div>
                          </div>

                          {/* Action Buttons Row */}
                          <div className="flex flex-wrap items-center gap-3 pt-2">
                            {!isAccepted && !isDeclined && (
                              <>
                                <button
                                  onClick={() => handleOpenAcceptModal(offer)}
                                  disabled={responding}
                                  className="inline-flex items-center gap-2 text-sm font-bold text-white bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] px-6 py-2.5 rounded-xl shadow-sm transition-all cursor-pointer"
                                >
                                  <Check className="w-4 h-4 stroke-[3]" />
                                  Accept Offer
                                </button>

                                <button
                                  onClick={() => {
                                    setSelectedOffer(offer);
                                    setShowDeclineModal(true);
                                  }}
                                  className="inline-flex items-center gap-2 text-sm font-bold text-rose-600 hover:bg-rose-50 border border-rose-300 px-5 py-2.5 rounded-xl transition-all cursor-pointer"
                                >
                                  <X className="w-4 h-4 stroke-[2.5]" />
                                  Decline Offer
                                </button>
                              </>
                            )}

                            {isAccepted && (
                              <div className="inline-flex items-center gap-2 text-xs font-bold text-emerald-800 bg-emerald-50 px-4 py-2.5 rounded-xl border border-emerald-300">
                                <BadgeCheck className="w-4 h-4 text-emerald-600" />
                                Offer Accepted on {formatDate(offer.responded_at || offer.updated_at)}
                              </div>
                            )}

                            <button
                              onClick={() => setViewingOfferModal(offer)}
                              className="inline-flex items-center gap-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 border border-blue-400 px-5 py-2.5 rounded-xl shadow-sm transition-all cursor-pointer"
                            >
                              <Eye className="w-4 h-4 text-blue-600" />
                              View Offer Letter & Summary
                            </button>

                            <button
                              onClick={() => handleDownloadPDF(offer)}
                              disabled={downloadingPdf}
                              className="inline-flex items-center gap-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 border border-blue-400 px-5 py-2.5 rounded-xl shadow-sm transition-all cursor-pointer"
                            >
                              <Download className="w-4 h-4 text-blue-600" />
                              {downloadingPdf ? "Generating PDF..." : "Download PDF"}
                            </button>

                            {!isAccepted && !isDeclined && (
                              <button
                                onClick={() => {
                                  setSelectedOffer(offer);
                                  setShowClarifyModal(true);
                                }}
                                className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 px-3 py-2 ml-auto rounded-lg transition-colors cursor-pointer"
                              >
                                <HelpCircle className="w-4 h-4" />
                                Ask a Question
                              </button>
                            )}

                            {isAccepted && (
                              <button
                                onClick={() => setActiveTab("documents")}
                                className="inline-flex items-center gap-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.98] px-6 py-2.5 rounded-xl shadow-sm ml-auto transition-all cursor-pointer"
                              >
                                Complete Document Verification
                                <ArrowRight className="w-4 h-4" />
                              </button>
                            )}
                          </div>

                          {/* Accordion 1: Benefits & Perks */}
                          <div className="rounded-xl border border-slate-200/80 overflow-hidden bg-slate-50/40">
                            <button
                              onClick={() => setBenefitsOpen(!benefitsOpen)}
                              className="w-full px-4 py-3.5 flex items-center justify-between text-left hover:bg-slate-50 transition-colors cursor-pointer"
                            >
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-blue-100/70 text-blue-600 flex items-center justify-center shrink-0">
                                  <Gift className="w-4 h-4" />
                                </div>
                                <div>
                                  <h4 className="text-xs font-bold text-slate-900">Benefits & Perks</h4>
                                  <p className="text-[11px] text-slate-500 mt-0.5">
                                    {offer.benefits_summary || "Comprehensive health, dental & vision insurance, 401(k) matching, 20 days PTO, learning stipend."}
                                  </p>
                                </div>
                              </div>
                              {benefitsOpen ? (
                                <ChevronUp className="w-4 h-4 text-slate-400" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-slate-400" />
                              )}
                            </button>

                            {benefitsOpen && (
                              <div className="px-5 pb-4 pt-1 text-xs text-slate-600 border-t border-slate-100 bg-white leading-relaxed">
                                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                                  <li className="flex items-center gap-2 text-slate-700">
                                    <Check className="w-3.5 h-3.5 text-blue-600" /> Health, Dental & Vision Insurance Coverage
                                  </li>
                                  <li className="flex items-center gap-2 text-slate-700">
                                    <Check className="w-3.5 h-3.5 text-blue-600" /> 401(k) Retirement Matching Program
                                  </li>
                                  <li className="flex items-center gap-2 text-slate-700">
                                    <Check className="w-3.5 h-3.5 text-blue-600" /> 20 Days Paid Annual Leave & Flexible Holidays
                                  </li>
                                  <li className="flex items-center gap-2 text-slate-700">
                                    <Check className="w-3.5 h-3.5 text-blue-600" /> Annual Learning & Certification Stipend
                                  </li>
                                </ul>
                              </div>
                            )}
                          </div>

                          {/* Accordion 2: Terms & Conditions */}
                          <div className="rounded-xl border border-slate-200/80 overflow-hidden bg-slate-50/40">
                            <button
                              onClick={() => setTermsOpen(!termsOpen)}
                              className="w-full px-4 py-3.5 flex items-center justify-between text-left hover:bg-slate-50 transition-colors cursor-pointer"
                            >
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-blue-100/70 text-blue-600 flex items-center justify-center shrink-0">
                                  <FileText className="w-4 h-4" />
                                </div>
                                <div>
                                  <h4 className="text-xs font-bold text-slate-900">Terms & Conditions</h4>
                                  <p className="text-[11px] text-slate-500 mt-0.5">
                                    {offer.additional_terms || "Offer contingent upon satisfactory completion of background verification and document submission."}
                                  </p>
                                </div>
                              </div>
                              {termsOpen ? (
                                <ChevronUp className="w-4 h-4 text-slate-400" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-slate-400" />
                              )}
                            </button>

                            {termsOpen && (
                              <div className="px-5 pb-4 pt-1 text-xs text-slate-600 border-t border-slate-100 bg-white leading-relaxed space-y-1.5">
                                <p className="mt-2 text-slate-700">
                                  This offer is valid until <strong>{formatDate(offer.offer_expiry_date)}</strong>. Acceptance of this offer signifies agreement to the organization's standard code of conduct, confidentiality obligations, and satisfactory verification of requested identity and employment credentials.
                                </p>
                              </div>
                            )}
                          </div>

                          {/* Info Notification Banner */}
                          <div className="bg-blue-50/90 border border-blue-200 text-blue-800 rounded-xl px-4 py-3 text-xs flex items-center gap-2.5 font-medium">
                            <AlertCircle className="w-4 h-4 text-blue-600 shrink-0" />
                            <span>
                              {isAccepted
                                ? "Offer accepted! Please complete your document submission in the Document Verification tab to initiate HR verification."
                                : "Please accept or decline the offer before the expiry date. Feel free to contact HR for any queries."}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* NEXT STEPS SECTION (SHOWN WHEN OFFER IS ACCEPTED) */}
                      {isAccepted && (
                        <div className="bg-gradient-to-br from-white to-blue-50/50 rounded-2xl border border-blue-200/80 p-6 shadow-sm space-y-5">
                          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                            <div>
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                Next Steps in Your Onboarding Journey
                              </div>
                              <h3 className="text-base font-bold text-slate-900 mt-1">
                                Complete Onboarding Roadmap
                              </h3>
                              <p className="text-xs text-slate-500 mt-0.5">
                                Track your progression through the 4 stages from offer acceptance to your first day.
                              </p>
                            </div>

                            <button
                              onClick={() => setActiveTab("documents")}
                              className="inline-flex items-center gap-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-xl shadow-sm transition-all"
                            >
                              Upload Documents
                              <ArrowRight className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          {/* 4-Step Progress Roadmap */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                            {/* Step 1 */}
                            <div className="bg-white rounded-xl p-4 border border-emerald-200 shadow-xs relative overflow-hidden">
                              <div className="absolute top-0 right-0 w-12 h-12 bg-emerald-50 rounded-bl-full flex items-start justify-end p-2 text-emerald-600">
                                <Check className="w-3.5 h-3.5 stroke-[3]" />
                              </div>
                              <span className="text-[10px] font-extrabold uppercase tracking-wider text-emerald-600">
                                Stage 1 • Completed
                              </span>
                              <h4 className="text-xs font-bold text-slate-900 mt-1 flex items-center gap-1.5">
                                <FileCheck2 className="w-4 h-4 text-emerald-600" />
                                Offer Accepted
                              </h4>
                              <p className="text-[11px] text-slate-500 mt-1">
                                Official offer letter accepted. Reference: #{offer.id.slice(0, 8)}.
                              </p>
                            </div>

                            {/* Step 2 (ACTIVE) */}
                            <div className="bg-blue-50/80 rounded-xl p-4 border-2 border-blue-500 shadow-xs relative overflow-hidden">
                              <div className="absolute top-0 right-0 px-2 py-0.5 bg-blue-600 text-[9px] font-extrabold uppercase tracking-wider text-white rounded-bl-lg">
                                Current
                              </div>
                              <span className="text-[10px] font-extrabold uppercase tracking-wider text-blue-700">
                                Stage 2 • Action Required
                              </span>
                              <h4 className="text-xs font-bold text-blue-900 mt-1 flex items-center gap-1.5">
                                <ShieldCheck className="w-4 h-4 text-blue-600" />
                                Document Verification
                              </h4>
                              <p className="text-[11px] text-blue-950/80 mt-1">
                                Submit Government ID, Address Proof, Degree & Relieving letter.
                              </p>
                            </div>

                            {/* Step 3 */}
                            <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-xs">
                              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                                Stage 3 • Upcoming
                              </span>
                              <h4 className="text-xs font-bold text-slate-700 mt-1 flex items-center gap-1.5">
                                <Clock className="w-4 h-4 text-slate-400" />
                                HR Clearance
                              </h4>
                              <p className="text-[11px] text-slate-500 mt-1">
                                HR validates credentials and clears background verification.
                              </p>
                            </div>

                            {/* Step 4 */}
                            <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-xs">
                              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                                Stage 4 • Upcoming
                              </span>
                              <h4 className="text-xs font-bold text-slate-700 mt-1 flex items-center gap-1.5">
                                <UserCheck className="w-4 h-4 text-slate-400" />
                                First Day & Onboarding
                              </h4>
                              <p className="text-[11px] text-slate-500 mt-1">
                                Receive Employee ID, IT access credentials & Day 1 checklist.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* TAB 2: DOCUMENT VERIFICATION */}
          {activeTab === "documents" && (
            <div className="space-y-6">
              {/* Document Stage Header & Next Steps Banner */}
              <div className="bg-gradient-to-r from-blue-900 to-indigo-950 text-white rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Post-Hiring Verification Stage
                    </span>
                    <h2 className="text-xl font-bold mt-2 text-white">
                      Document Verification & Credentials Submission
                    </h2>
                    <p className="text-xs text-blue-200 mt-1">
                      Please upload clear copies of the 4 requested verification documents. PDF, JPG, and PNG files up to 10MB are accepted.
                    </p>
                  </div>

                  <div className="text-left sm:text-right bg-white/10 p-3.5 rounded-xl border border-white/10">
                    <p className="text-xs text-blue-200">Upload Status</p>
                    <p className="text-lg font-bold text-white mt-0.5">
                      {submittedDocsCount} / {mergedDocuments.length} Submitted
                    </p>
                    <p className="text-[11px] text-emerald-300 mt-0.5">
                      {verifiedDocsCount} Approved by HR
                    </p>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-blue-950/60 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-emerald-400 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${(submittedDocsCount / mergedDocuments.length) * 100}%` }}
                  />
                </div>
              </div>

              {!hasAcceptedOffer && (
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-900">
                    <p className="font-semibold">Offer Acceptance Pending</p>
                    <p className="mt-0.5 text-amber-800">
                      Please accept your official offer in the <strong>Official Offers</strong> tab first. You can preview the 4 required verification documents below to prepare them in advance.
                    </p>
                    <button
                      onClick={() => setActiveTab("offers")}
                      className="mt-2 text-xs font-bold text-blue-700 underline hover:text-blue-800"
                    >
                      ← Return to Official Offers to Accept
                    </button>
                  </div>
                </div>
              )}

              {/* 4 DOCUMENT UPLOAD CARDS */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {mergedDocuments.map((doc, idx) => {
                  const isVerified = doc.status === "verified";
                  const isSubmitted = doc.status === "submitted";
                  const isResubmission = doc.status === "resubmission_required";
                  const isNotSubmitted = !doc.file_name || doc.status === "not_submitted";
                  const stdInfo = STANDARD_DOC_TYPES.find((s) => s.type === doc.document_type) || STANDARD_DOC_TYPES[idx];

                  return (
                    <div
                      key={doc.document_type || doc.id}
                      className={`bg-white rounded-2xl border p-5 shadow-sm space-y-4 transition-all ${
                        isVerified
                          ? "border-emerald-200 bg-emerald-50/20"
                          : isResubmission
                          ? "border-rose-300 bg-rose-50/20"
                          : isSubmitted
                          ? "border-blue-200"
                          : "border-slate-200"
                      }`}
                    >
                      {/* Document Card Header */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                            isVerified
                              ? "bg-emerald-100 text-emerald-700"
                              : isResubmission
                              ? "bg-rose-100 text-rose-700"
                              : isSubmitted
                              ? "bg-blue-100 text-blue-700"
                              : "bg-slate-100 text-slate-600"
                          }`}>
                            <ShieldCheck className="w-5 h-5" />
                          </div>

                          <div>
                            <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md uppercase tracking-wider">
                              {stdInfo?.category || "Required Document"}
                            </span>
                            <h4 className="text-xs font-bold text-slate-900 mt-1">
                              {stdInfo?.title || doc.document_title}
                            </h4>
                            <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                              {stdInfo?.description}
                            </p>
                          </div>
                        </div>

                        {/* Status Badge */}
                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold capitalize whitespace-nowrap shrink-0 ${
                          isVerified
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : isResubmission
                            ? "bg-rose-100 text-rose-800 border border-rose-300"
                            : isSubmitted
                            ? "bg-blue-100 text-blue-800 border border-blue-300"
                            : "bg-slate-100 text-slate-600 border border-slate-200"
                        }`}>
                          {isVerified
                            ? "✓ Verified"
                            : isResubmission
                            ? "⚠ Resubmit Required"
                            : isSubmitted
                            ? "Pending HR Review"
                            : "Not Submitted"}
                        </span>
                      </div>

                      {/* HR Remarks Alert if any */}
                      {doc.hr_remarks && (
                        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900 flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-bold">HR Remark:</span> {doc.hr_remarks}
                          </div>
                        </div>
                      )}

                      {/* Current File Status */}
                      {doc.file_name && (
                        <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2 overflow-hidden">
                            <FileText className="w-4 h-4 text-slate-500 shrink-0" />
                            <span className="font-semibold text-slate-800 truncate max-w-[200px]" title={doc.file_name}>
                              {doc.file_name}
                            </span>
                          </div>
                          {doc.file_url && (
                            <a
                              href={doc.file_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:text-blue-800 font-bold text-xs shrink-0 flex items-center gap-1"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              View
                            </a>
                          )}
                        </div>
                      )}

                      {/* Upload Controls */}
                      {!isVerified && (
                        <div className="pt-1">
                          {uploadingDocType === doc.document_type ? (
                            <form
                              onSubmit={(e) =>
                                handleUploadDocument(
                                  e,
                                  doc.document_type,
                                  stdInfo?.title || doc.document_title,
                                  doc.application_id
                                )
                              }
                              className="space-y-3 bg-blue-50/40 p-3.5 rounded-xl border border-blue-200"
                            >
                              <div className="text-[11px] font-semibold text-slate-700">
                                Select document file to upload:
                              </div>
                              <input
                                type="file"
                                accept=".pdf,.jpg,.jpeg,.png"
                                required
                                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                                className="w-full text-xs text-slate-600 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer"
                              />
                              <div className="flex gap-2 justify-end pt-1">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setUploadingDocType(null);
                                    setUploadFile(null);
                                  }}
                                  className="px-3 py-1.5 text-slate-600 hover:bg-slate-100 rounded-lg text-xs font-semibold cursor-pointer"
                                >
                                  Cancel
                                </button>
                                <button
                                  type="submit"
                                  disabled={uploading}
                                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-sm cursor-pointer"
                                >
                                  <Upload className="w-3.5 h-3.5" />
                                  {uploading ? "Uploading..." : "Submit File"}
                                </button>
                              </div>
                            </form>
                          ) : (
                            <button
                              onClick={() => setUploadingDocType(doc.document_type)}
                              className={`w-full py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                                isNotSubmitted
                                  ? "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                                  : "bg-white hover:bg-slate-50 text-blue-700 border border-blue-300"
                              }`}
                            >
                              <Upload className="w-4 h-4" />
                              {isNotSubmitted
                                ? `Upload ${stdInfo?.category || "Document"}`
                                : "Re-upload / Update Document"}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* NEXT STEPS & VERIFICATION GUIDELINES CARD */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <BadgeCheck className="w-4 h-4 text-blue-600" />
                  What Happens Next After Uploading?
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-600">
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                    <p className="font-bold text-slate-900">1. HR Document Review</p>
                    <p className="text-slate-500 text-[11px] leading-relaxed">
                      Our HR operations team checks document authenticity and matches your records within 24 to 48 business hours.
                    </p>
                  </div>
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                    <p className="font-bold text-slate-900">2. Instant Status Updates</p>
                    <p className="text-slate-500 text-[11px] leading-relaxed">
                      You will receive immediate notifications when documents are approved or if any re-upload is required.
                    </p>
                  </div>
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                    <p className="font-bold text-slate-900">3. Employee Onboarding</p>
                    <p className="text-slate-500 text-[11px] leading-relaxed">
                      Once all 4 credentials are confirmed, your official Employee ID and Day 1 Onboarding Checklist will unlock in Tab 3!
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: ONBOARDING CHECKLIST */}
          {activeTab === "onboarding" && (
            <div className="space-y-6">
              {!onboarding ? (
                <div className="bg-white p-12 rounded-2xl border border-slate-200 text-center text-slate-500 text-sm shadow-sm space-y-3">
                  <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
                    <Clock className="w-6 h-6" />
                  </div>
                  <h3 className="text-base font-bold text-slate-900">Onboarding Activation in Progress</h3>
                  <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                    Your official employee onboarding checklist and company credentials will be activated once HR verifies your credentials and confirms your official joining date.
                  </p>
                  <button
                    onClick={() => setActiveTab("documents")}
                    className="inline-flex items-center gap-2 text-xs font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 px-4 py-2 rounded-xl transition-colors cursor-pointer"
                  >
                    View Document Verification Status &rarr;
                  </button>
                </div>
              ) : (
                <>
                  {/* Status Banner when Activated or Joining Confirmed */}
                  {onboarding.employment_status === "active" ? (
                    <div className="bg-gradient-to-r from-emerald-600 to-teal-700 text-white p-5 rounded-2xl shadow-sm flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/20 flex items-center justify-center shrink-0">
                        <Sparkles className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h4 className="font-bold text-base">Active Employee Profile</h4>
                        <p className="text-xs text-emerald-100 mt-0.5">
                          Congratulations! Your employee profile is active at <strong>{onboarding.organization_name || "HireCraft AI"}</strong>. You have completed the hiring and onboarding journey.
                        </p>
                      </div>
                    </div>
                  ) : onboarding.joining_status === "confirmed" ? (
                    <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 text-white p-5 rounded-2xl shadow-sm flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/20 flex items-center justify-center shrink-0">
                        <BadgeCheck className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h4 className="font-bold text-base">Joining Confirmed!</h4>
                        <p className="text-xs text-emerald-100 mt-0.5">
                          HR has confirmed your scheduled start date on <strong>{formatDate(onboarding.joining_date)}</strong>. Please finish any remaining checklist items below.
                        </p>
                      </div>
                    </div>
                  ) : onboarding.completed_tasks === onboarding.total_tasks && onboarding.total_tasks > 0 ? (
                    <div className="bg-blue-50 border border-blue-200 p-5 rounded-2xl flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0">
                        <CheckCircle2 className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="font-bold text-slate-900 text-sm">All Onboarding Tasks Submitted</h4>
                        <p className="text-xs text-slate-600 mt-0.5">
                          Your onboarding tasks have been submitted. HR will review the submissions and confirm your joining.
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {/* Welcome Overview Banner */}
                  <div className="bg-gradient-to-r from-[#0a192f] to-[#1e3a8a] text-white p-6 rounded-2xl shadow-sm space-y-4">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                      <div>
                        <span className="text-xs uppercase font-bold tracking-wider text-blue-300">
                          {onboarding.organization_name || "HireCraft AI"} &bull; Onboarding Portal
                        </span>
                        <h2 className="text-2xl font-bold mt-1">Welcome aboard, {onboarding.user_name}!</h2>
                        <div className="flex items-center gap-2 flex-wrap mt-2 text-xs text-slate-200">
                          <span>Employee ID: <strong className="font-mono bg-white/10 px-2 py-0.5 rounded">{onboarding.employee_id}</strong></span>
                          <span>&bull;</span>
                          <span>Role: <strong>{onboarding.designation}</strong></span>
                          <span>&bull;</span>
                          <span>Department: <strong>{onboarding.department}</strong></span>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <div className="text-2xl font-bold text-emerald-400">{onboarding.onboarding_progress_percent}%</div>
                        <span className="text-xs text-blue-200">
                          {onboarding.completed_tasks} of {onboarding.total_tasks} Tasks Done
                        </span>
                      </div>
                    </div>

                    <div className="w-full bg-slate-800/80 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="bg-emerald-400 h-2.5 rounded-full transition-all duration-300"
                        style={{ width: `${onboarding.onboarding_progress_percent}%` }}
                      />
                    </div>

                    {/* Metadata summary grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-slate-700/60 text-xs">
                      <div>
                        <span className="text-slate-400 text-[10px] uppercase font-bold">Scheduled Joining</span>
                        <p className="font-bold text-white mt-0.5">{formatDate(onboarding.joining_date)}</p>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[10px] uppercase font-bold">Joining Status</span>
                        <p className="font-bold text-white mt-0.5 capitalize">
                          {onboarding.joining_status === "confirmed" ? "✓ Confirmed" : "Pending Confirmation"}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[10px] uppercase font-bold">Reporting Manager</span>
                        <p className="font-bold text-white mt-0.5">{onboarding.reporting_manager || "To be assigned"}</p>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[10px] uppercase font-bold">Work Arrangement</span>
                        <p className="font-bold text-white mt-0.5">{onboarding.work_location || "Headquarters"}</p>
                      </div>
                    </div>
                  </div>

                  {/* Tasks Checklist */}
                  <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                        Your Onboarding Action Items ({onboarding.completed_tasks}/{onboarding.total_tasks})
                      </h3>
                      <span className="text-xs text-slate-500 font-medium">
                        Click any task to submit notes or mark completion
                      </span>
                    </div>

                    <div className="space-y-3">
                      {onboarding.tasks.map((task) => {
                        const isPendingApproval = task.status === "pending_approval";
                        const isRejected = task.status === "rejected";

                        return (
                          <div
                            key={task.id}
                            className={`p-4 rounded-xl border transition-all flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
                              task.is_completed
                                ? "bg-slate-50 border-slate-200 opacity-80"
                                : isPendingApproval
                                ? "bg-amber-50/60 border-amber-200 shadow-sm"
                                : isRejected
                                ? "bg-rose-50/60 border-rose-200 shadow-sm"
                                : "bg-white border-blue-200 shadow-sm hover:border-blue-300"
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              <button
                                onClick={() => handleToggleCandidateTask(task)}
                                className={`mt-0.5 w-5 h-5 rounded border flex items-center justify-center transition-colors cursor-pointer shrink-0 ${
                                  task.is_completed
                                    ? "bg-emerald-500 border-emerald-500 text-white"
                                    : "border-slate-300 hover:border-blue-500"
                                }`}
                              >
                                {task.is_completed && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                              </button>

                              <div>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span
                                    className={
                                      task.is_completed
                                        ? "line-through text-slate-400 font-semibold text-xs"
                                        : "font-semibold text-slate-900 text-xs"
                                    }
                                  >
                                    {task.title}
                                  </span>

                                  <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded capitalize">
                                    {task.category.replace("_", " ")}
                                  </span>

                                  {isPendingApproval && (
                                    <span className="text-[10px] font-bold bg-amber-500 text-white px-2 py-0.5 rounded-full">
                                      Pending HR Approval
                                    </span>
                                  )}

                                  {isRejected && (
                                    <span className="text-[10px] font-bold bg-rose-600 text-white px-2 py-0.5 rounded-full">
                                      Changes Requested
                                    </span>
                                  )}

                                  {task.is_completed && (
                                    <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                                      Completed
                                    </span>
                                  )}
                                </div>

                                {task.description && (
                                  <p className="text-[11px] text-slate-500 mt-1">{task.description}</p>
                                )}

                                {task.instructions && (
                                  <p className="text-[11px] text-blue-700 bg-blue-50/70 border border-blue-200/60 p-1.5 rounded-lg mt-1.5">
                                    <strong>Instructions:</strong> {task.instructions}
                                  </p>
                                )}

                                {task.submission_notes && (
                                  <p className="text-[11px] text-slate-600 bg-slate-100 p-1.5 rounded-lg mt-1.5">
                                    <strong>Your Submission Note:</strong> {task.submission_notes}
                                  </p>
                                )}

                                {task.hr_remarks && (
                                  <p className="text-[11px] text-rose-700 bg-rose-50 border border-rose-200 p-1.5 rounded-lg mt-1.5">
                                    <strong>HR Feedback:</strong> {task.hr_remarks}
                                  </p>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                              {task.deadline && (
                                <div className="text-[11px] text-slate-400 whitespace-nowrap">
                                  Due: {formatDate(task.deadline)}
                                </div>
                              )}

                              {!task.is_completed && (
                                <button
                                  onClick={() => {
                                    setSubmittingTaskItem(task);
                                    setTaskSubmissionNotes(task.submission_notes || "");
                                    setTaskAttachmentUrl(task.attachment_url || "");
                                  }}
                                  className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors cursor-pointer"
                                >
                                  {isRejected ? "Resubmit" : isPendingApproval ? "Update Submission" : "Submit Notes"}
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* CANDIDATE TASK SUBMISSION MODAL */}
      {submittingTaskItem && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in duration-200">
            <div className="bg-blue-600 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCheck2 className="w-5 h-5 text-blue-200" />
                <h3 className="font-bold text-base">Submit Onboarding Task</h3>
              </div>
              <button
                onClick={() => setSubmittingTaskItem(null)}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmitTaskReview} className="p-6 space-y-4 text-xs">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Task Title</span>
                <p className="font-bold text-slate-900 text-sm mt-0.5">{submittingTaskItem.title}</p>
                {submittingTaskItem.instructions && (
                  <p className="text-[11px] text-blue-700 bg-blue-50 p-2 rounded-lg mt-2">
                    {submittingTaskItem.instructions}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Submission Notes / Proof of Completion *
                </label>
                <textarea
                  required
                  rows={3}
                  value={taskSubmissionNotes}
                  onChange={(e) => setTaskSubmissionNotes(e.target.value)}
                  placeholder="e.g. Completed online compliance module and signed agreement; confirmed accounts active."
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Attachment / Artifact Link (Optional)
                </label>
                <input
                  type="url"
                  value={taskAttachmentUrl}
                  onChange={(e) => setTaskAttachmentUrl(e.target.value)}
                  placeholder="https://drive.google.com/... or link to artifact"
                  className="w-full rounded-xl border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSubmittingTaskItem(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingTask}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer"
                >
                  {isSubmittingTask ? "Submitting..." : "Submit for HR Review"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ACCEPT OFFER CONFIRMATION MODAL */}
      {showAcceptModal && selectedOffer && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in duration-200">
            <div className="bg-emerald-700 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-300" />
                <h3 className="font-bold text-base">Accept Employment Offer</h3>
              </div>
              <button
                onClick={() => setShowAcceptModal(false)}
                className="text-white/80 hover:text-white text-xl font-bold p-1 cursor-pointer"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleConfirmAcceptOffer} className="p-6 space-y-4 text-xs">
              <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-4 space-y-2">
                <p className="text-emerald-950 font-bold text-sm">
                  Congratulations on this major career milestone!
                </p>
                <p className="text-emerald-900/80 leading-relaxed text-xs">
                  You are about to accept the official job offer from <strong>{selectedOffer.organization_name || "HireCraft AI"}</strong>.
                </p>
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-emerald-200/60 text-emerald-900">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-700">Role</span>
                    <p className="font-bold text-xs">{selectedOffer.designation}</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-700">Compensation</span>
                    <p className="font-bold text-xs">{selectedOffer.currency} {selectedOffer.offered_salary.toLocaleString()} / year</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-700">Joining Date</span>
                    <p className="font-bold text-xs">{formatDate(selectedOffer.joining_date)}</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-700">Location</span>
                    <p className="font-bold text-xs">{selectedOffer.work_location || "Headquarters"}</p>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Optional Note / Acceptance Message for HR
                </label>
                <textarea
                  rows={2}
                  value={acceptNotes}
                  onChange={(e) => setAcceptNotes(e.target.value)}
                  placeholder="e.g. Thank you for this opportunity! I am excited to join the team."
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div className="flex items-start gap-2 pt-1">
                <input
                  type="checkbox"
                  id="confirm-accept-checkbox"
                  checked={acceptConfirmed}
                  onChange={(e) => setAcceptConfirmed(e.target.checked)}
                  className="mt-0.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                  required
                />
                <label htmlFor="confirm-accept-checkbox" className="text-slate-600 text-xs cursor-pointer select-none">
                  I accept the terms and conditions outlined in the official offer letter and agree to submit the required verification credentials.
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAcceptModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-semibold text-xs cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={responding || !acceptConfirmed}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center gap-1.5 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                >
                  <Check className="w-4 h-4 stroke-[3]" />
                  {responding ? "Accepting Offer..." : "Confirm & Accept Offer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DECLINE MODAL */}
      {showDeclineModal && selectedOffer && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden">
            <div className="bg-rose-600 text-white px-6 py-4 flex items-center justify-between">
              <h3 className="font-semibold text-base">Decline Job Offer</h3>
              <button
                onClick={() => setShowDeclineModal(false)}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleDeclineOffer} className="p-6 space-y-4 text-xs">
              <p className="text-slate-600">
                Are you sure you want to decline the offer for <strong>{selectedOffer.designation}</strong>?
              </p>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Reason (Optional)</label>
                <textarea
                  rows={3}
                  value={declineReason}
                  onChange={(e) => setDeclineReason(e.target.value)}
                  placeholder="e.g. Accepted another opportunity, compensation mismatch..."
                  className="w-full rounded-lg border border-slate-300 p-2.5 focus:ring-2 focus:ring-rose-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowDeclineModal(false)}
                  className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={responding}
                  className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-medium cursor-pointer"
                >
                  {responding ? "Declining..." : "Confirm Decline"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* OFFER LETTER SUMMARY & PDF PREVIEW MODAL */}
      {viewingOfferModal && (
        <OfferLetterModal
          offer={viewingOfferModal}
          onClose={() => setViewingOfferModal(null)}
          onOfferUpdated={fetchData}
        />
      )}

      {/* CLARIFY MODAL */}
      {showClarifyModal && selectedOffer && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden">
            <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
              <h3 className="font-semibold text-base">Ask a Question About Your Offer</h3>
              <button
                onClick={() => setShowClarifyModal(false)}
                className="text-slate-400 hover:text-white text-xl font-bold cursor-pointer"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleClarifyOffer} className="p-6 space-y-4 text-xs">
              <p className="text-slate-600">
                Your question will be delivered to the HR coordinator handling your offer.
              </p>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Your Question *</label>
                <textarea
                  required
                  rows={3}
                  value={clarifyQuestion}
                  onChange={(e) => setClarifyQuestion(e.target.value)}
                  placeholder="e.g. Could you provide details regarding the remote work schedule..."
                  className="w-full rounded-lg border border-slate-300 p-2.5 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowClarifyModal(false)}
                  className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={responding}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer"
                >
                  {responding ? "Sending..." : "Submit Question"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
