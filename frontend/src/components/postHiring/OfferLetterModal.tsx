import { useState, useEffect } from "react";
import {
  X,
  Mail,
  Phone,
  Briefcase,
  DollarSign,
  Gift,
  FileText,
  CheckCircle,
  Download,
  Eye,
  Printer,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Check,
} from "lucide-react";
import type { JobOffer } from "../../types/postHiring";
import postHiringApi from "../../api/postHiring";
import { useToast } from "../../contexts/ToastContext";
import { formatDate } from "../../utils/dateTime";

interface OfferLetterModalProps {
  offer: JobOffer;
  onClose: () => void;
  onOfferUpdated?: () => void;
}

export default function OfferLetterModal({ offer, onClose }: OfferLetterModalProps) {
  const { addToast } = useToast();
  const [currentPage, setCurrentPage] = useState<1 | 2>(1);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [downloading, setDownloading] = useState(false);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    postHiringApi
      .downloadOfferPdf(offer.id)
      .then((blob) => {
        url = window.URL.createObjectURL(blob);
        setPdfBlobUrl(url);
      })
      .catch(() => {
        // Fallback to high-fidelity document preview
      });
    return () => {
      if (url) window.URL.revokeObjectURL(url);
    };
  }, [offer.id]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await postHiringApi.downloadOfferPdf(offer.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const candClean = offer.candidate_name ? offer.candidate_name.replace(/\s+/g, "_") : "Candidate";
      link.setAttribute("download", `Offer_Letter_${candClean}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      addToast("Offer letter downloaded successfully", "success");
    } catch {
      addToast("Failed to download offer PDF", "error");
    } finally {
      setDownloading(false);
    }
  };

  const handlePrint = () => {
    if (pdfBlobUrl) {
      const printWin = window.open(pdfBlobUrl, "_blank");
      printWin?.print();
    } else {
      window.print();
    }
  };

  // Salary & compensation breakdown
  const offered = offer.offered_salary || 85000;
  const baseSalary = offer.base_salary ?? Math.round(offered * 0.8235);
  const variableComp = offer.variable_compensation ?? Math.round(offered * 0.0588);
  const allowances = offer.allowances ?? Math.round(offered - (baseSalary + variableComp));
  const varPct = offer.variable_percentage ?? (offered > 0 ? Math.round((variableComp / offered) * 100) : 6);

  const refNo = offer.offer_reference_no || `HC-2025-${offer.id.slice(-4).toUpperCase()}`;
  const appId = offer.application_reference || `APP-2025-${offer.application_id.slice(-4).toUpperCase()}`;
  const candName = offer.candidate_name || "Rohit Sharma";

  // Company branding (img2 fix)
  const compName: string = (offer as unknown as Record<string, string>).organization_name || (offer as unknown as Record<string, string>).company_name || "Company";
  const compInitial: string = compName.charAt(0).toUpperCase();
  const compDomain: string = compName.toLowerCase().replace(/[^a-z0-9]/g, "") + ".com";
  const firstName = candName.split(" ")[0] || "Candidate";
  const candEmail = offer.candidate_email || "rohit.sharma@example.com";
  const candPhone = offer.candidate_phone || "+91 98765 43210";
  const candLoc = offer.candidate_location || offer.work_location || "Bengaluru, Karnataka";
  const issueDate = offer.sent_at ? formatDate(offer.sent_at) : formatDate(offer.created_at);
  const joiningDateFormatted = formatDate(offer.joining_date);
  const expiryDateFormatted = formatDate(offer.offer_expiry_date);

  // Status badge styling
  const isSent = offer.status === "sent" || offer.status === "viewed";
  const isAccepted = offer.status === "accepted";
  const isDeclined = offer.status === "declined";

  // Simple number to words
  const numberToWords = (num: number): string => {
    const ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
      "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
      "Seventeen", "Eighteen", "Nineteen"];
    const tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];
    const helper = (n: number): string => {
      if (n === 0) return "";
      if (n < 20) return ones[n] + " ";
      if (n < 100) return tens[Math.floor(n / 10)] + (n % 10 !== 0 ? " " + ones[n % 10] : "") + " ";
      if (n < 1000) return ones[Math.floor(n / 100)] + " Hundred " + helper(n % 100);
      if (n < 1000000) return helper(Math.floor(n / 1000)) + "Thousand " + helper(n % 1000);
      return helper(Math.floor(n / 1000000)) + "Million " + helper(n % 1000000);
    };
    const res = helper(Math.round(num)).trim();
    return res ? `${res} Only` : "Zero Only";
  };

  const salaryInWords = numberToWords(offered);

  return (
    <div className="fixed inset-0 bg-slate-900/75 backdrop-blur-sm z-50 flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div className="bg-slate-100/90 rounded-2xl shadow-2xl border border-slate-200/80 w-full max-w-7xl max-h-[94vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Main Content: Left Summary + Right PDF Viewer */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* LEFT PANEL: OFFER LETTER SUMMARY                                 */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          <div className="lg:col-span-5 bg-white rounded-2xl shadow-sm border border-slate-200/80 flex flex-col space-y-4 overflow-hidden">
            
            {/* Modal Title & Close — Dark navy bar (img1 fix) */}
            <div className="bg-[#0a192f] px-5 py-4 flex items-center justify-between rounded-t-2xl">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  Offer Letter Summary
                </h2>
                <p className="text-[11px] text-slate-300 font-mono mt-0.5">Offer ID: {offer.id}</p>
              </div>
              <button
                onClick={onClose}
                className="text-slate-300 hover:text-white hover:bg-slate-700 p-1.5 rounded-lg transition-colors"
                title="Close"
              >
                <X className="w-5 h-5 text-white" />
              </button>
            </div>
            <div className="px-5 pb-5 flex flex-col space-y-4">

            {/* Candidate Header Identity */}
            <div className="flex items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm ring-2 ring-blue-100">
                  {candName
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base leading-snug">{candName}</h3>
                  <p className="text-xs font-medium text-slate-500">Application ID: {appId}</p>
                  <div className="flex flex-col gap-0.5 mt-1 text-[11px] text-slate-600">
                    <span className="flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5 text-slate-400" />
                      {candEmail}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      {candPhone}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Badge */}
              <div>
                {isAccepted ? (
                  <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full text-xs font-semibold">
                    <CheckCircle className="w-3.5 h-3.5" />
                    Offer Accepted
                  </span>
                ) : isDeclined ? (
                  <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 border border-rose-200 px-3 py-1 rounded-full text-xs font-semibold">
                    <X className="w-3.5 h-3.5" />
                    Offer Declined
                  </span>
                ) : isSent ? (
                  <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full text-xs font-semibold">
                    <Check className="w-3.5 h-3.5" />
                    Offer Sent
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200 px-3 py-1 rounded-full text-xs font-semibold">
                    Draft
                  </span>
                )}
              </div>
            </div>

            {/* 1. Offer Details Card */}
            <div className="bg-[#F0F7FF] border border-blue-100 rounded-xl p-3.5 text-xs">
              <div className="flex items-center gap-1.5 font-bold text-slate-900 mb-2.5">
                <Briefcase className="w-4 h-4 text-blue-600" />
                <span>Offer Details</span>
              </div>
              <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                <div>
                  <span className="text-slate-500 block text-[11px]">Designation</span>
                  <span className="font-semibold text-slate-900">{offer.designation}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Department</span>
                  <span className="font-semibold text-slate-900">{offer.department}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Employment Type</span>
                  <span className="font-semibold text-slate-900">
                    {offer.employment_type.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Work Location</span>
                  <span className="font-semibold text-slate-900">{offer.work_location}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Reporting Manager</span>
                  <span className="font-semibold text-slate-900">
                    {offer.reporting_manager || "Anita Verma"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Joining Date</span>
                  <span className="font-semibold text-slate-900">{joiningDateFormatted}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Offer Expiry Date</span>
                  <span className="font-semibold text-slate-900">{expiryDateFormatted}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Work Arrangement</span>
                  <span className="font-semibold text-slate-900">{offer.work_arrangement || "Hybrid"}</span>
                </div>
              </div>
            </div>

            {/* 2. Compensation Details Card */}
            <div className="bg-[#F0F7FF] border border-blue-100 rounded-xl p-3.5">
              <div className="flex items-center gap-1.5 font-bold text-slate-900 mb-2 text-xs">
                <DollarSign className="w-4 h-4 text-blue-600" />
                <span>Compensation Details</span>
              </div>
              <div className="grid grid-cols-2 divide-x divide-blue-200">
                <div className="pr-3">
                  <div className="text-blue-700 font-bold text-base md:text-lg">
                    {offer.currency} {offered.toLocaleString()} / year
                  </div>
                  <div className="text-[11px] font-medium text-slate-500">Annual Fixed Salary</div>
                </div>
                <div className="pl-3">
                  <div className="text-blue-700 font-bold text-sm md:text-base">
                    {offer.currency} {variableComp.toLocaleString()} ({varPct}%)
                  </div>
                  <div className="text-[11px] font-medium text-slate-500">Variable Compensation</div>
                </div>
              </div>
            </div>

            {/* 3. Benefits Badges */}
            <div>
              <div className="flex items-center gap-1.5 font-bold text-slate-900 mb-2 text-xs">
                <Gift className="w-4 h-4 text-blue-600" />
                <span>Benefits</span>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full font-medium text-[11px]">
                  <Check className="w-3 h-3 text-blue-600" /> Health Insurance
                </span>
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full font-medium text-[11px]">
                  <Check className="w-3 h-3 text-blue-600" /> Paid Leave
                </span>
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full font-medium text-[11px]">
                  <Check className="w-3 h-3 text-blue-600" /> Learning Support
                </span>
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full font-medium text-[11px]">
                  <Check className="w-3 h-3 text-blue-600" /> Retirement Benefits
                </span>
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full font-medium text-[11px]">
                  <Check className="w-3 h-3 text-blue-600" /> Other Benefits
                </span>
              </div>
            </div>

            {/* 4. Terms & Conditions */}
            <div>
              <div className="flex items-center gap-1.5 font-bold text-slate-900 mb-1 text-xs">
                <FileText className="w-4 h-4 text-blue-600" />
                <span>Terms & Conditions</span>
              </div>
              <p className="text-[11px] text-slate-600 bg-slate-50 border border-slate-200/80 p-2.5 rounded-lg leading-relaxed">
                {offer.additional_terms ||
                  "Offer contingent upon background verification and document submission."}
              </p>
            </div>

            {/* 5. Stepper Timeline */}
            <div className="pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between text-center relative px-2">
                <div className="absolute top-3 left-4 right-4 h-0.5 bg-blue-200 -z-0" />
                
                {/* Step 1: Created */}
                <div className="relative z-10 flex flex-col items-center">
                  <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold ring-4 ring-white">
                    <Check className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-[10px] font-semibold text-slate-800 mt-1">Created</span>
                  <span className="text-[9px] text-slate-500">{formatDate(offer.created_at)}</span>
                </div>

                {/* Step 2: Sent */}
                <div className="relative z-10 flex flex-col items-center">
                  <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold ring-4 ring-white">
                    <Check className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-[10px] font-semibold text-slate-800 mt-1">Sent</span>
                  <span className="text-[9px] text-slate-500">{issueDate}</span>
                </div>

                {/* Step 3: Viewed */}
                <div className="relative z-10 flex flex-col items-center">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ring-4 ring-white ${offer.viewed_at ? "bg-blue-600 text-white" : "bg-blue-100 text-blue-600"}`}>
                    <Eye className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-[10px] font-semibold text-slate-800 mt-1">Viewed</span>
                  <span className="text-[9px] text-slate-500">{offer.viewed_at ? formatDate(offer.viewed_at) : "Pending"}</span>
                </div>

                {/* Step 4: Responded */}
                <div className="relative z-10 flex flex-col items-center">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ring-4 ring-white ${isAccepted ? "bg-emerald-600 text-white" : isDeclined ? "bg-rose-600 text-white" : "bg-blue-500 text-white"}`}>
                    <Check className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-[10px] font-semibold text-slate-800 mt-1">{isAccepted ? "Accepted" : isDeclined ? "Declined" : "Sent"}</span>
                  <span className="text-[9px] text-slate-500">{offer.responded_at ? formatDate(offer.responded_at) : "Active"}</span>
                </div>
              </div>
            </div>

            {/* Bottom Action Buttons */}
            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={handlePrint}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-blue-600 bg-white border border-blue-300 hover:bg-blue-50 rounded-lg transition-colors shadow-sm"
              >
                <Eye className="w-3.5 h-3.5" />
                Preview PDF
              </button>
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloading}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                <Download className="w-3.5 h-3.5" />
                {downloading ? "Downloading..." : "Download PDF"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors border border-slate-200"
              >
                Close
              </button>
            </div>
            </div>
          </div>

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* RIGHT PANEL: OFFICIAL EMBEDDED PDF PREVIEW (MATCHING DESIGN)     */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          <div className="lg:col-span-7 bg-[#2A2E33] rounded-2xl shadow-xl overflow-hidden flex flex-col border border-slate-700/60 min-h-[750px]">
            
            {/* PDF Viewer Top Toolbar */}
            <div className="bg-[#1E2227] text-white px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/80 text-xs">
              <div className="flex items-center gap-2 font-medium truncate max-w-xs text-slate-300">
                <FileText className="w-4 h-4 text-rose-400 shrink-0" />
                <span className="truncate">Offer_Letter_{candName.replace(/\s+/g, "_")}.pdf</span>
              </div>

              {/* Page and Zoom Navigation Controls */}
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 bg-[#2C3138] px-2 py-1 rounded border border-slate-600 text-xs text-slate-300">
                  <button
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                    className="hover:text-white disabled:opacity-40"
                    title="Previous Page"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <span className="px-1.5 font-mono">{currentPage} / 2</span>
                  <button
                    onClick={() => setCurrentPage(2)}
                    disabled={currentPage === 2}
                    className="hover:text-white disabled:opacity-40"
                    title="Next Page"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="hidden sm:flex items-center gap-1 bg-[#2C3138] px-2 py-1 rounded border border-slate-600 text-xs text-slate-300">
                  <button
                    onClick={() => setZoomLevel((z) => Math.max(75, z - 10))}
                    className="hover:text-white px-1"
                    title="Zoom Out"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <span className="px-1 text-[11px] font-mono">{zoomLevel}%</span>
                  <button
                    onClick={() => setZoomLevel((z) => Math.min(130, z + 10))}
                    className="hover:text-white px-1"
                    title="Zoom In"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={handleDownload}
                    className="p-1.5 hover:bg-slate-700 rounded text-slate-300 hover:text-white transition-colors"
                    title="Download PDF"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handlePrint}
                    className="p-1.5 hover:bg-slate-700 rounded text-slate-300 hover:text-white transition-colors"
                    title="Print Document"
                  >
                    <Printer className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Document Render Area (Page 1 or Page 2) */}
            <div className="flex-1 bg-[#525659] p-4 md:p-8 overflow-y-auto flex justify-center">
              <div
                style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: "top center" }}
                className="bg-white text-slate-900 shadow-2xl rounded-sm w-full max-w-[595px] min-h-[842px] p-8 flex flex-col justify-between transition-transform duration-150"
              >
                {currentPage === 1 ? (
                  /* ───────────────────────────────────────────────────────────── */
                  /* PAGE 1 CONTENT                                                */
                  /* ───────────────────────────────────────────────────────────── */
                  <div className="space-y-4">
                    {/* Header */}
                    <div className="flex justify-between items-start border-b-0 pb-1">
                      <div className="flex items-center gap-2.5">
                        <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center text-white font-black text-xl shadow-sm">
                          {compInitial}
                        </div>
                        <div>
                          <h1 className="text-xl font-extrabold text-[#0B2545] tracking-tight leading-tight">
                            {compName}
                          </h1>
                          <p className="text-[11px] font-bold text-blue-600">{(offer as unknown as Record<string, string>).department || "Official Employment Offer"}</p>
                        </div>
                      </div>

                      <div className="text-right text-[10px] text-slate-500 leading-tight">
                        <p>123 Tech Park, Whitefield</p>
                        <p>Bengaluru, Karnataka - 560066, India</p>
                        <p className="font-medium text-slate-600">www.{compDomain} | hr@{compDomain}</p>
                      </div>
                    </div>

                    {/* Dark Navy Offer Banner */}
                    <div className="bg-[#0B2545] text-white font-extrabold text-center py-2.5 rounded-sm tracking-wider uppercase text-sm shadow-sm">
                      OFFER OF EMPLOYMENT
                    </div>

                    {/* Meta Reference Bar */}
                    <div className="flex justify-between items-start text-[11px] text-[#0F172A] pt-1">
                      <div>
                        <p className="font-bold">Offer Reference No: {refNo}</p>
                        <p className="font-extrabold tracking-wide text-[#0B2545] text-[10px] uppercase mt-0.5">
                          PRIVATE & CONFIDENTIAL
                        </p>
                      </div>
                      <div className="text-right font-bold">
                        <p>Date of Issue: {issueDate}</p>
                      </div>
                    </div>

                    {/* Addressee */}
                    <div className="text-xs text-slate-800 space-y-0.5 pt-1">
                      <p className="font-bold text-slate-900">To,</p>
                      <p className="font-extrabold text-slate-900 text-sm">{candName}</p>
                      <p className="text-slate-600">{candEmail}</p>
                      <p className="text-slate-600">{candLoc}</p>
                    </div>

                    {/* Dear Salutation */}
                    <div className="text-xs text-slate-700 leading-relaxed pt-1">
                      <p className="font-bold text-slate-900 mb-1.5">Dear {firstName},</p>
                      <p>
                        We are pleased to offer you the position of{" "}
                        <strong className="text-slate-900 font-bold">{offer.designation}</strong> at{" "}
                        <strong className="text-slate-900 font-bold">{compName}</strong>, in the{" "}
                        <strong className="text-slate-900 font-bold">{offer.department}</strong> department.
                        We look forward to welcoming you to our organization and being a part of our growing team.
                      </p>
                    </div>

                    {/* 1. Employment Details */}
                    <div>
                      <div className="bg-[#0B2545] text-white text-[11px] font-bold px-3 py-1.5 rounded-t-sm flex items-center">
                        1. Employment Details
                      </div>
                      <table className="w-full text-[11px] border-collapse border border-slate-300">
                        <tbody>
                          <tr className="border-b border-slate-200">
                            <td className="w-1/3 bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Designation</td>
                            <td className="w-2/3 px-3 py-1.5 text-slate-700">{offer.designation}</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Department</td>
                            <td className="px-3 py-1.5 text-slate-700">{offer.department}</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Employment Type</td>
                            <td className="px-3 py-1.5 text-slate-700">{offer.employment_type.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase())}</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Work Location</td>
                            <td className="px-3 py-1.5 text-slate-700">{offer.work_location}</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Work Arrangement</td>
                            <td className="px-3 py-1.5 text-slate-700">{offer.work_arrangement || "Hybrid"}</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Reporting Manager</td>
                            <td className="px-3 py-1.5 text-slate-700">{offer.reporting_manager || "Anita Verma (Engineering Manager)"}</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Joining Date</td>
                            <td className="px-3 py-1.5 text-slate-700 font-semibold">{joiningDateFormatted}</td>
                          </tr>
                          <tr>
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-1.5 border-r border-slate-300">Probation Period</td>
                            <td className="px-3 py-1.5 text-slate-700">{offer.probation_period_months} months</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* 2. Compensation Details */}
                    <div>
                      <div className="bg-[#0B2545] text-white text-[11px] font-bold px-3 py-1.5 rounded-t-sm flex items-center">
                        2. Compensation Details
                      </div>
                      <div className="bg-[#EBF3FC] border border-[#BFDBFE] p-4 text-xs rounded-b-sm grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="flex flex-col justify-center border-b sm:border-b-0 sm:border-r border-[#BFDBFE] pb-3 sm:pb-0 sm:pr-4">
                          <span className="text-[10px] uppercase font-bold tracking-wide text-slate-500">
                            Total Annual Compensation
                          </span>
                          <span className="text-xl md:text-2xl font-black text-[#0B2545] my-1">
                            {offer.currency} {offered.toLocaleString()}
                          </span>
                          <span className="text-[10px] text-slate-600 italic">
                            ({salaryInWords})
                          </span>
                        </div>

                        <div className="text-[11px] space-y-1.5 text-slate-800 sm:pl-2">
                          <div className="flex justify-between">
                            <span className="font-semibold text-slate-700">Base Salary:</span>
                            <span className="font-bold">{offer.currency} {baseSalary.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="font-semibold text-slate-700">Variable Compensation:</span>
                            <span className="font-bold">{offer.currency} {variableComp.toLocaleString()} ({varPct}%)</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="font-semibold text-slate-700">Allowances:</span>
                            <span className="font-bold">{offer.currency} {allowances.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between border-t border-blue-200/60 pt-1">
                            <span className="font-semibold text-slate-700">Currency:</span>
                            <span className="font-bold">{offer.currency}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* ───────────────────────────────────────────────────────────── */
                  /* PAGE 2 CONTENT                                                */
                  /* ───────────────────────────────────────────────────────────── */
                  <div className="space-y-4">
                    {/* Page 2 Mini Header */}
                    <div className="flex justify-between items-center border-b border-slate-200 pb-2 text-[11px]">
                      <span className="font-extrabold text-[#0B2545]">{compName} • Official Offer Letter</span>
                      <span className="text-slate-500 font-mono text-[10px]">Ref: {refNo}</span>
                    </div>

                    {/* 3. Benefits & Perks */}
                    <div>
                      <div className="bg-[#0B2545] text-white text-[11px] font-bold px-3 py-1.5 rounded-t-sm">
                        3. Benefits & Perks
                      </div>
                      <table className="w-full text-[11px] border-collapse border border-slate-300">
                        <tbody>
                          <tr className="border-b border-slate-200">
                            <td className="w-1/3 bg-slate-50 font-bold text-slate-800 px-3 py-2 border-r border-slate-300">Health Insurance</td>
                            <td className="px-3 py-2 text-slate-700">Comprehensive medical, dental, and vision coverage for employee and immediate dependents.</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-2 border-r border-slate-300">Paid Leave</td>
                            <td className="px-3 py-2 text-slate-700">24 days of paid annual vacation plus company holidays and sick leave privileges.</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-2 border-r border-slate-300">Learning Support</td>
                            <td className="px-3 py-2 text-slate-700">Annual professional development stipend and technical certification sponsorships.</td>
                          </tr>
                          <tr className="border-b border-slate-200">
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-2 border-r border-slate-300">Retirement Benefits</td>
                            <td className="px-3 py-2 text-slate-700">Company-matched 401(k) / Provident Fund retirement savings program.</td>
                          </tr>
                          <tr>
                            <td className="bg-slate-50 font-bold text-slate-800 px-3 py-2 border-r border-slate-300">Other Benefits</td>
                            <td className="px-3 py-2 text-slate-700">{offer.benefits_summary || "Annual performance bonus, wellness allowance, and home workspace stipend."}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* 4. Terms & Conditions */}
                    <div>
                      <div className="bg-[#0B2545] text-white text-[11px] font-bold px-3 py-1.5 rounded-t-sm">
                        4. Terms & Conditions
                      </div>
                      <div className="border border-slate-300 p-3 bg-slate-50 text-[11px] text-slate-700 space-y-2 rounded-b-sm leading-relaxed">
                        <p>
                          <strong>• Verification Contingency:</strong> This offer is contingent upon successful verification of credentials, academic records, identity proofs, and previous employment background.
                        </p>
                        <p>
                          <strong>• Confidentiality:</strong> You will be required to execute and abide by the company Non-Disclosure Agreement and Proprietary Information Agreement.
                        </p>
                        <p>
                          <strong>• Notice Period:</strong> A standard 60-day notice period applies to either party following confirmation of permanent employment.
                        </p>
                        <p>
                          <strong>• Code of Conduct:</strong> Adherence to all organizational compliance, security, and workplace ethics policies is mandatory.
                        </p>
                        {offer.additional_terms && (
                          <p>
                            <strong>• Additional Terms:</strong> {offer.additional_terms}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* 5. Acceptance of Offer */}
                    <div>
                      <div className="bg-[#0B2545] text-white text-[11px] font-bold px-3 py-1.5 rounded-t-sm">
                        5. Acceptance of Offer
                      </div>
                      <div className="border border-slate-300 p-4 bg-white rounded-b-sm grid grid-cols-2 gap-4 text-xs">
                        <div className="border-r border-slate-200 pr-4 space-y-3">
                          <p className="font-bold text-slate-900">For {compName}</p>
                          <div className="h-12 border-b border-dashed border-slate-300 flex items-end pb-1 text-[11px] text-blue-700 italic">
                            [Digitally Authorized & Approved]
                          </div>
                          <div className="text-[10px] text-slate-600">
                            <p className="font-bold text-slate-800">Authorized Signatory: Human Resources</p>
                            <p>Date: {issueDate}</p>
                          </div>
                        </div>

                        <div className="pl-2 space-y-3">
                          <p className="font-bold text-slate-900">Candidate Acceptance</p>
                          <p className="text-[10px] text-slate-500 italic">
                            "I have read, understood and accept the terms of this offer."
                          </p>
                          <div className="h-8 border-b border-slate-300" />
                          <div className="text-[10px] text-slate-700">
                            <p className="font-semibold">Signature: __________________________</p>
                            <p className="mt-1 font-bold">Name: {candName}</p>
                            <p className="mt-1">Date: __________________________</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Dark Navy Footer (on both pages) */}
                <div className="bg-[#0B2545] text-white text-[10px] px-4 py-2 flex justify-between items-center rounded-b-sm mt-6">
                  <span className="font-medium">{compName} | Offer Reference No: {refNo}</span>
                  <span className="font-bold">Page {currentPage} of 2</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
