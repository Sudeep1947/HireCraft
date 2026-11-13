import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ShieldCheck,
  CheckCircle,
  XCircle,
  RotateCcw,
  Eye,
  Clock,
  Search,
  FileText,
  UserCheck,
  Sparkles,
  ArrowRight,
    CheckCircle2,
} from "lucide-react";

import postHiringApi from "../../api/postHiring";
import type {
  CandidateDocument,
  DocumentVerificationStatus,
  Employee,
  EmployeeCreatePayload,
} from "../../types/postHiring";
import { useToast } from "../../contexts/ToastContext";
import { formatDate } from "../../utils/dateTime";

interface CandidateVerificationGroup {
  candidate_id: string;
  application_id: string;
  candidate_name: string;
  candidate_email: string;
  job_title?: string;
  department?: string;
  organization_name?: string;
  total_documents: number;
  verified_documents: number;
  all_verified: boolean;
  latest_verified_at?: string;
  is_already_onboarding: boolean;
}

export default function HRDocumentsPage() {
  const [searchParams] = useSearchParams();
  const filterAppId = searchParams.get("app_id");
  const { addToast } = useToast();
  const navigate = useNavigate();

  const [documents, setDocuments] = useState<CandidateDocument[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Action Modals for Document Review
  const [selectedDoc, setSelectedDoc] = useState<CandidateDocument | null>(null);
  const [actionType, setActionType] = useState<"resubmit" | "reject" | null>(null);
  const [remarks, setRemarks] = useState("");
  const [processing, setProcessing] = useState(false);

  // Start Onboarding Modal State
  const [onboardingCandidate, setOnboardingCandidate] = useState<CandidateVerificationGroup | null>(null);
  const [onboardingForm, setOnboardingForm] = useState<EmployeeCreatePayload>({
    candidate_id: "",
    application_id: "",
    designation: "",
    department: "Engineering",
    employment_type: "full_time",
    work_location: "Hybrid - Headquarters",
    reporting_manager: "",
    joining_date: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    checklist_template: "standard",
    onboarding_deadline: new Date(Date.now() + 24 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
  });
  const [startingOnboarding, setStartingOnboarding] = useState(false);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const [docsData, empsData] = await Promise.all([
        postHiringApi.getDocuments(filterAppId || undefined),
        postHiringApi.getEmployees(),
      ]);
      setDocuments(docsData);
      setEmployees(empsData);
    } catch (err) {
      addToast("Failed to load documents", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [filterAppId]);

  const handleVerify = async (doc: CandidateDocument) => {
    try {
      await postHiringApi.verifyDocument(doc.id, "verified", "Document verified and approved by HR.");
      addToast(`Verified ${doc.document_title}`, "success");
      await fetchDocuments();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to verify document", "error");
    }
  };

  const handleConfirmAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoc || !actionType) return;
    setProcessing(true);
    try {
      const status = actionType === "resubmit" ? "resubmission_required" : "rejected";
      await postHiringApi.verifyDocument(selectedDoc.id, status, remarks);
      addToast(
        actionType === "resubmit" ? "Resubmission requested from candidate" : "Document rejected",
        "success"
      );
      setSelectedDoc(null);
      setActionType(null);
      setRemarks("");
      await fetchDocuments();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to update document status", "error");
    } finally {
      setProcessing(false);
    }
  };

  // Group verified candidates to check for "All Documents Verified" banner
  const candidateGroups: Record<string, CandidateVerificationGroup> = {};
  documents.forEach((doc) => {
    const key = doc.application_id || doc.candidate_id;
    if (!candidateGroups[key]) {
      const isAlreadyOnboarding = employees.some(
        (e) => (e.application_id && e.application_id === doc.application_id) || e.user_id === doc.candidate_id
      );
      candidateGroups[key] = {
        candidate_id: doc.candidate_id,
        application_id: doc.application_id,
        candidate_name: doc.candidate_name || "Candidate",
        candidate_email: doc.candidate_email || "",
        job_title: "Selected Candidate",
        department: "Engineering",
        organization_name: "HireCraft AI",
        total_documents: 0,
        verified_documents: 0,
        all_verified: false,
        is_already_onboarding: isAlreadyOnboarding,
      };
    }
    candidateGroups[key].total_documents += 1;
    if (doc.status === "verified") {
      candidateGroups[key].verified_documents += 1;
      if (doc.verified_at && (!candidateGroups[key].latest_verified_at || doc.verified_at > candidateGroups[key].latest_verified_at!)) {
        candidateGroups[key].latest_verified_at = doc.verified_at;
      }
    }
  });

  // Candidate is fully verified if has >= 1 docs and all submitted docs are verified
  const verifiedCandidatesList = Object.values(candidateGroups).filter(
    (g) => g.total_documents > 0 && g.total_documents === g.verified_documents && !g.is_already_onboarding
  );

  const handleOpenStartOnboarding = (cand: CandidateVerificationGroup) => {
    setOnboardingCandidate(cand);
    setOnboardingForm({
      candidate_id: cand.candidate_id,
      application_id: cand.application_id,
      designation: cand.job_title || "Selected Candidate",
      department: cand.department || "Engineering",
      employment_type: "full_time",
      work_location: "Hybrid - Headquarters",
      reporting_manager: "",
      joining_date: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
      checklist_template: "standard",
      onboarding_deadline: new Date(Date.now() + 24 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    });
  };

  const handleStartOnboardingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onboardingCandidate) return;
    setStartingOnboarding(true);
    try {
      await postHiringApi.createEmployee({
        ...onboardingForm,
        joining_date: new Date(onboardingForm.joining_date).toISOString(),
        onboarding_deadline: onboardingForm.onboarding_deadline
          ? new Date(onboardingForm.onboarding_deadline).toISOString()
          : undefined,
      });
      addToast(`Onboarding initiated successfully for ${onboardingCandidate.candidate_name}!`, "success");
      setOnboardingCandidate(null);
      navigate("/hr/onboarding");
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to start onboarding", "error");
    } finally {
      setStartingOnboarding(false);
    }
  };

  const filteredDocs = documents.filter((doc) => {
    const matchesTab =
      activeTab === "all"
        ? true
        : activeTab === "pending"
        ? ["submitted", "under_review"].includes(doc.status)
        : doc.status === activeTab;

    const matchesSearch =
      (doc.candidate_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.document_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.document_type.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesTab && matchesSearch;
  });

  const getStatusBadge = (status: DocumentVerificationStatus) => {
    switch (status) {
      case "verified":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle className="w-3.5 h-3.5" /> Verified
          </span>
        );
      case "submitted":
      case "under_review":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Clock className="w-3.5 h-3.5" /> Submitted (Review)
          </span>
        );
      case "resubmission_required":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <RotateCcw className="w-3.5 h-3.5" /> Resubmit Req
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3.5 h-3.5" /> Rejected
          </span>
        );
      case "not_submitted":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            Pending Upload
          </span>
        );
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-blue-600" />
            Candidate Document Verification
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Review uploaded identity, educational, and employment credentials before initializing onboarding.
          </p>
        </div>
      </div>

      {/* "ALL DOCUMENTS VERIFIED" PROMINENT BANNER (Section 3 Requirement) */}
      {verifiedCandidatesList.length > 0 && (
        <div className="space-y-3">
          {verifiedCandidatesList.map((cand) => (
            <div
              key={cand.application_id || cand.candidate_id}
              className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 text-white rounded-2xl p-5 sm:p-6 shadow-md border border-emerald-500/40 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center font-bold text-white text-lg shrink-0">
                  {cand.candidate_name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-white text-emerald-800 uppercase tracking-wide">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> All Documents Verified
                    </span>
                    <span className="text-xs text-emerald-100 font-medium">
                      {cand.verified_documents} of {cand.total_documents} verified
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white mt-1">
                    {cand.candidate_name} &bull; <span className="font-normal text-emerald-100">{cand.candidate_email}</span>
                  </h3>
                  <p className="text-xs text-emerald-100 mt-0.5">
                    {cand.job_title} &bull; {cand.department} &bull; Verified on {cand.latest_verified_at ? formatDate(cand.latest_verified_at) : "Recently"}
                  </p>
                </div>
              </div>

              <button
                onClick={() => handleOpenStartOnboarding(cand)}
                className="inline-flex items-center gap-2 bg-white text-emerald-800 hover:bg-emerald-50 font-bold text-xs sm:text-sm px-5 py-2.5 rounded-xl shadow-sm transition-all hover:shadow cursor-pointer shrink-0"
              >
                <Sparkles className="w-4 h-4 text-emerald-600" />
                Start Onboarding
                <ArrowRight className="w-4 h-4 text-emerald-600" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Documents</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{documents.length}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-blue-600 uppercase tracking-wider">Pending Review</p>
          <p className="text-2xl font-bold text-blue-700 mt-1">
            {documents.filter((d) => ["submitted", "under_review"].includes(d.status)).length}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-emerald-600 uppercase tracking-wider">Verified Documents</p>
          <p className="text-2xl font-bold text-emerald-700 mt-1">
            {documents.filter((d) => d.status === "verified").length}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-amber-600 uppercase tracking-wider">Resubmit / Rejected</p>
          <p className="text-2xl font-bold text-amber-700 mt-1">
            {documents.filter((d) => ["resubmission_required", "rejected"].includes(d.status)).length}
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Tabs */}
        <div className="flex items-center gap-1 w-full sm:w-auto overflow-x-auto">
          {[
            { id: "all", label: "All Documents" },
            { id: "pending", label: "Pending Review" },
            { id: "verified", label: "Verified" },
            { id: "resubmission_required", label: "Resubmit Req" },
            { id: "rejected", label: "Rejected" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search candidate, document..."
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-slate-500 text-sm">Loading candidate documents...</div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">
            No documents found matching the filter criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Candidate</th>
                  <th className="py-3 px-4">Document Details</th>
                  <th className="py-3 px-4">Attachment</th>
                  <th className="py-3 px-4">Submitted On</th>
                  <th className="py-3 px-4">Status & Notes</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">{doc.candidate_name || "Unknown"}</div>
                      <div className="text-[11px] text-slate-500">{doc.candidate_email}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-800">{doc.document_title}</div>
                      <div className="text-[11px] text-slate-500 capitalize">{doc.document_type.replace(/_/g, " ")}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {doc.file_name ? (
                        <div>
                          <a
                            href={doc.file_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600 hover:underline font-medium flex items-center gap-1"
                          >
                            <FileText className="w-3.5 h-3.5" /> {doc.file_name}
                          </a>
                          <span className="text-[11px] text-slate-400">
                            {doc.file_size ? `${Math.round(doc.file_size / 1024)} KB` : ""}
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">No file attached</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {doc.submitted_at ? formatDate(doc.submitted_at) : "—"}
                    </td>
                    <td className="py-3 px-4">
                      <div>{getStatusBadge(doc.status)}</div>
                      {doc.hr_remarks && (
                        <p className="text-[11px] text-slate-500 mt-1 italic max-w-xs truncate" title={doc.hr_remarks}>
                          Note: {doc.hr_remarks}
                        </p>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      {doc.file_url && (
                        <a
                          href={doc.file_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-slate-600 hover:text-blue-600 font-medium"
                          title="View File"
                        >
                          <Eye className="w-3.5 h-3.5" /> View
                        </a>
                      )}

                      {["submitted", "under_review", "resubmission_required"].includes(doc.status) && (
                        <button
                          onClick={() => handleVerify(doc)}
                          className="inline-flex items-center gap-1 text-emerald-600 hover:text-emerald-700 font-semibold cursor-pointer"
                          title="Verify Document"
                        >
                          <CheckCircle className="w-3.5 h-3.5" /> Verify
                        </button>
                      )}

                      {["submitted", "under_review"].includes(doc.status) && (
                        <button
                          onClick={() => {
                            setSelectedDoc(doc);
                            setActionType("resubmit");
                            setRemarks("Please re-upload a clear, readable copy.");
                          }}
                          className="inline-flex items-center gap-1 text-amber-600 hover:text-amber-700 font-medium cursor-pointer"
                          title="Request Resubmission"
                        >
                          <RotateCcw className="w-3.5 h-3.5" /> Resubmit
                        </button>
                      )}

                      {["submitted", "under_review"].includes(doc.status) && (
                        <button
                          onClick={() => {
                            setSelectedDoc(doc);
                            setActionType("reject");
                            setRemarks("Document fails verification criteria.");
                          }}
                          className="inline-flex items-center gap-1 text-rose-600 hover:text-rose-700 font-medium cursor-pointer"
                          title="Reject"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Reject
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ACTION DIALOG: RESUBMISSION OR REJECT */}
      {selectedDoc && actionType && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in duration-150">
            <div className={`px-6 py-4 text-white flex items-center justify-between ${
              actionType === "resubmit" ? "bg-amber-600" : "bg-rose-600"
            }`}>
              <h3 className="font-semibold text-base flex items-center gap-2">
                {actionType === "resubmit" ? <RotateCcw className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                {actionType === "resubmit" ? "Request Document Resubmission" : "Reject Document"}
              </h3>
              <button
                onClick={() => { setSelectedDoc(null); setActionType(null); }}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>
            <form onSubmit={handleConfirmAction} className="p-6 space-y-4 text-xs">
              <div>
                <p className="text-slate-600">
                  Candidate: <strong>{selectedDoc.candidate_name}</strong>
                </p>
                <p className="text-slate-600">
                  Document: <strong>{selectedDoc.document_title}</strong>
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  {actionType === "resubmit" ? "Resubmission Instructions for Candidate *" : "Rejection Reason *"}
                </label>
                <textarea
                  required
                  rows={3}
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 p-2.5 focus:ring-2 focus:ring-blue-500 text-xs"
                  placeholder="Provide explicit instructions or reasoning..."
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => { setSelectedDoc(null); setActionType(null); }}
                  className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={processing}
                  className={`px-4 py-1.5 rounded-lg text-white font-medium cursor-pointer ${
                    actionType === "resubmit"
                      ? "bg-amber-600 hover:bg-amber-700"
                      : "bg-rose-600 hover:bg-rose-700"
                  }`}
                >
                  {processing ? "Sending..." : actionType === "resubmit" ? "Send Resubmission Request" : "Reject Document"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* START ONBOARDING MODAL (Section 3) */}
      {onboardingCandidate && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden animate-in fade-in duration-200">
            {/* Header */}
            <div className="bg-blue-600 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserCheck className="w-5 h-5 text-blue-200" />
                <h3 className="font-bold text-base">Start Employee Onboarding</h3>
              </div>
              <button
                onClick={() => setOnboardingCandidate(null)}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleStartOnboardingSubmit} className="p-6 space-y-4 text-xs">
              {/* Candidate Info Box */}
              <div className="p-3.5 bg-blue-50/70 border border-blue-200 rounded-xl flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-600 text-white font-bold flex items-center justify-center text-sm">
                  {onboardingCandidate.candidate_name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">{onboardingCandidate.candidate_name}</h4>
                  <p className="text-[11px] text-slate-600">{onboardingCandidate.candidate_email}</p>
                  <p className="text-[11px] text-emerald-700 font-semibold mt-0.5 flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" /> All {onboardingCandidate.total_documents} documents verified
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Designation / Job Title *
                  </label>
                  <input
                    type="text"
                    required
                    value={onboardingForm.designation}
                    onChange={(e) => setOnboardingForm({ ...onboardingForm, designation: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. Senior Software Engineer"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Department *
                  </label>
                  <select
                    value={onboardingForm.department}
                    onChange={(e) => setOnboardingForm({ ...onboardingForm, department: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Engineering">Engineering</option>
                    <option value="Product">Product</option>
                    <option value="Marketing">Marketing</option>
                    <option value="Sales">Sales</option>
                    <option value="Human Resources">Human Resources</option>
                    <option value="Design">Design</option>
                    <option value="Customer Success">Customer Success</option>
                    <option value="Operations">Operations</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Employment Type
                  </label>
                  <select
                    value={onboardingForm.employment_type}
                    onChange={(e) => setOnboardingForm({ ...onboardingForm, employment_type: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="full_time">Full Time</option>
                    <option value="part_time">Part Time</option>
                    <option value="contract">Contract</option>
                    <option value="internship">Internship</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Reporting Manager
                  </label>
                  <input
                    type="text"
                    value={onboardingForm.reporting_manager || ""}
                    onChange={(e) => setOnboardingForm({ ...onboardingForm, reporting_manager: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. Tech Lead / Director"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Proposed Joining Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={onboardingForm.joining_date}
                    onChange={(e) => setOnboardingForm({ ...onboardingForm, joining_date: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Onboarding Deadline
                  </label>
                  <input
                    type="date"
                    value={onboardingForm.onboarding_deadline || ""}
                    onChange={(e) => setOnboardingForm({ ...onboardingForm, onboarding_deadline: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Checklist Template Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Checklist Template *
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "standard", name: "Standard (7 tasks)", desc: "General documentation, IT setup, orientation" },
                    { id: "engineering", name: "Engineering (9 tasks)", desc: "Includes Git, Dev Env, Cloud IAM & CI/CD" },
                    { id: "sales_operations", name: "Sales / Ops (8 tasks)", desc: "Includes CRM access & Sales playbook" },
                    { id: "executive", name: "Executive (7 tasks)", desc: "Leadership sync & strategic review" },
                  ].map((tpl) => (
                    <label
                      key={tpl.id}
                      className={`p-2.5 rounded-xl border cursor-pointer transition-all ${
                        onboardingForm.checklist_template === tpl.id
                          ? "border-blue-600 bg-blue-50/70"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="checklist_template"
                          checked={onboardingForm.checklist_template === tpl.id}
                          onChange={() => setOnboardingForm({ ...onboardingForm, checklist_template: tpl.id })}
                          className="text-blue-600 focus:ring-blue-500"
                        />
                        <span className="font-bold text-slate-900 text-xs">{tpl.name}</span>
                      </div>
                      <p className="text-[10px] text-slate-500 mt-1 pl-5">{tpl.desc}</p>
                    </label>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setOnboardingCandidate(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={startingOnboarding}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold flex items-center gap-1.5 shadow-sm cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  {startingOnboarding ? "Initializing..." : "Start Onboarding"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
