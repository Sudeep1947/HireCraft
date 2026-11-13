import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  FileText,
  Plus,
  Send,
  Download,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  Search,
} from "lucide-react";

import postHiringApi from "../../api/postHiring";
import type {
  ApprovedCandidateSummary,
  JobOffer,
  JobOfferCreatePayload,
  OfferStatus,
} from "../../types/postHiring";
import { useToast } from "../../contexts/ToastContext";
import { formatDate } from "../../utils/dateTime";
import OfferLetterModal from "../../components/postHiring/OfferLetterModal";

export default function HROffersPage() {
  const [searchParams] = useSearchParams();
  const highlightAppId = searchParams.get("app_id");
  const { addToast } = useToast();

  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [approvedCandidates, setApprovedCandidates] = useState<ApprovedCandidateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [previewOffer, setPreviewOffer] = useState<JobOffer | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState<JobOfferCreatePayload>({
    application_id: "",
    designation: "",
    department: "Engineering",
    employment_type: "full_time",
    offered_salary: 85000,
    currency: "USD",
    work_location: "Bengaluru, Karnataka",
    work_arrangement: "Hybrid",
    base_salary: 70000,
    variable_compensation: 5000,
    allowances: 10000,
    reporting_manager: "Anita Verma (Engineering Manager)",
    joining_date: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    probation_period_months: 6,
    benefits_summary: "Comprehensive health, dental & vision insurance, 401(k) matching, 20 days PTO, learning stipend.",
    additional_terms: "Offer contingent upon satisfactory completion of background verification and document submission.",
    offer_expiry_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    hr_remarks: "",
    send_immediately: true,
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [offersData, candsData] = await Promise.all([
        postHiringApi.getOffers(),
        postHiringApi.getApprovedCandidates(),
      ]);
      setOffers(offersData);
      setApprovedCandidates(candsData);

      // Pre-fill application if passed via URL param
      if (highlightAppId) {
        const found = candsData.find((c) => c.application_id === highlightAppId);
        if (found) {
          setFormData((prev) => ({
            ...prev,
            application_id: found.application_id,
            designation: found.job_title,
            department: found.department,
          }));
          setShowCreateModal(true);
        }
      }
    } catch (err) {
      addToast("Failed to load offer data", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [highlightAppId]);

  const handleSelectCandidate = (appId: string) => {
    const cand = approvedCandidates.find((c) => c.application_id === appId);
    if (cand) {
      setFormData((prev) => ({
        ...prev,
        application_id: cand.application_id,
        designation: cand.job_title,
        department: cand.department || "Engineering",
      }));
    }
  };

  const handleCreateOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.application_id) {
      addToast("Please select an approved candidate", "error");
      return;
    }
    setSubmitting(true);
    try {
      await postHiringApi.createOffer({
        ...formData,
        joining_date: new Date(formData.joining_date).toISOString(),
        offer_expiry_date: new Date(formData.offer_expiry_date).toISOString(),
      });
      addToast(formData.send_immediately ? "Offer created & sent successfully" : "Draft offer saved", "success");
      setShowCreateModal(false);
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to create offer", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendDraft = async (offerId: string) => {
    try {
      await postHiringApi.sendOffer(offerId);
      addToast("Official offer sent to candidate", "success");
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to send offer", "error");
    }
  };

  const handleWithdraw = async (offerId: string) => {
    if (!window.confirm("Are you sure you want to withdraw this offer?")) return;
    try {
      await postHiringApi.withdrawOffer(offerId);
      addToast("Offer has been withdrawn", "success");
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to withdraw offer", "error");
    }
  };

  const handleDownloadPDF = async (offer: JobOffer) => {
    setDownloadingId(offer.id);
    try {
      const blob = await postHiringApi.downloadOfferPdf(offer.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Job_Offer_${offer.candidate_name?.replace(/\s+/g, "_") || offer.id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      addToast("Offer letter downloaded", "success");
    } catch (err) {
      addToast("Failed to download offer PDF", "error");
    } finally {
      setDownloadingId(null);
    }
  };

  const filteredOffers = offers.filter((o) => {
    const matchesTab =
      activeTab === "all" ? true :
      activeTab === "pending" ? ["sent", "viewed", "draft"].includes(o.status) :
      o.status === activeTab;

    const matchesSearch =
      (o.candidate_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (o.designation || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (o.department || "").toLowerCase().includes(searchQuery.toLowerCase());

    return matchesTab && matchesSearch;
  });

  const getStatusBadge = (status: OfferStatus) => {
    switch (status) {
      case "accepted":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"><CheckCircle className="w-3.5 h-3.5" /> Accepted</span>;
      case "declined":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200"><XCircle className="w-3.5 h-3.5" /> Declined</span>;
      case "sent":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200"><Send className="w-3.5 h-3.5" /> Sent</span>;
      case "viewed":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200"><Eye className="w-3.5 h-3.5" /> Viewed</span>;
      case "draft":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-200"><Clock className="w-3.5 h-3.5" /> Draft</span>;
      case "withdrawn":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 border border-gray-200">Withdrawn</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <FileText className="w-6 h-6 text-blue-600" />
            Offer Letter Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Create, approve, issue official offers, and track candidate responses.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          Create New Offer
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Offers</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{offers.length}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-amber-600 uppercase tracking-wider">Pending Response</p>
          <p className="text-2xl font-bold text-amber-700 mt-1">
            {offers.filter((o) => ["sent", "viewed"].includes(o.status)).length}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-emerald-600 uppercase tracking-wider">Accepted</p>
          <p className="text-2xl font-bold text-emerald-700 mt-1">
            {offers.filter((o) => o.status === "accepted").length}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-rose-600 uppercase tracking-wider">Declined</p>
          <p className="text-2xl font-bold text-rose-700 mt-1">
            {offers.filter((o) => o.status === "declined").length}
          </p>
        </div>
      </div>

      {/* Filters and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Tabs */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg w-full sm:w-auto overflow-x-auto">
            {["all", "pending", "accepted", "declined", "draft"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-all ${
                  activeTab === tab
                    ? "bg-white text-blue-600 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search candidate, role..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Offers Table */}
        {loading ? (
          <div className="py-12 text-center text-slate-500 text-sm">Loading offers...</div>
        ) : filteredOffers.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">
            No offers match your criteria. Click "Create New Offer" to issue an offer to a selected candidate.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Candidate</th>
                  <th className="py-3 px-4">Role & Department</th>
                  <th className="py-3 px-4">Compensation</th>
                  <th className="py-3 px-4">Joining Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {filteredOffers.map((offer) => (
                  <tr key={offer.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900">{offer.candidate_name || "Candidate"}</div>
                      <div className="text-slate-400 text-[11px]">{offer.candidate_email}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">{offer.designation}</div>
                      <div className="text-slate-500 text-[11px]">{offer.department} • {offer.work_location}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-semibold text-slate-900">
                        {offer.currency} {offer.offered_salary.toLocaleString()}
                      </span>
                      <span className="text-slate-400 text-[11px]"> / year</span>
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      <div>{formatDate(offer.joining_date)}</div>
                      <div className="text-[11px] text-slate-400">
                        Expires: {formatDate(offer.offer_expiry_date)}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {getStatusBadge(offer.status)}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => setPreviewOffer(offer)}
                        className="inline-flex items-center gap-1 text-slate-600 hover:text-blue-600 font-medium transition-colors"
                        title="View Details"
                      >
                        <Eye className="w-3.5 h-3.5" /> View
                      </button>

                      <button
                        onClick={() => handleDownloadPDF(offer)}
                        disabled={downloadingId === offer.id}
                        className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium transition-colors"
                        title="Download Official PDF"
                      >
                        <Download className="w-3.5 h-3.5" />
                        {downloadingId === offer.id ? "PDF..." : "PDF"}
                      </button>

                      {offer.status === "draft" && (
                        <button
                          onClick={() => handleSendDraft(offer.id)}
                          className="inline-flex items-center gap-1 text-emerald-600 hover:text-emerald-700 font-medium transition-colors"
                          title="Send to Candidate"
                        >
                          <Send className="w-3.5 h-3.5" /> Send
                        </button>
                      )}

                      {["sent", "viewed"].includes(offer.status) && (
                        <button
                          onClick={() => handleWithdraw(offer.id)}
                          className="inline-flex items-center gap-1 text-rose-500 hover:text-rose-700 font-medium transition-colors"
                          title="Withdraw Offer"
                        >
                          Withdraw
                        </button>
                      )}

                      {offer.status === "accepted" && (
                        <Link
                          to={`/hr/employees?candidate_id=${offer.candidate_id}&app_id=${offer.application_id}`}
                          className="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white px-2 py-1 rounded text-[11px] font-medium transition-colors"
                        >
                          Create Employee
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE OFFER MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl my-8 overflow-hidden">
            <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-lg flex items-center gap-2">
                  <FileText className="w-5 h-5 text-blue-400" /> Create Official Offer Letter
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Select an approved candidate and configure official employment terms.
                </p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white text-xl font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateOffer} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              {/* Candidate Picker */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select Approved Candidate *
                </label>
                <select
                  value={formData.application_id}
                  onChange={(e) => handleSelectCandidate(e.target.value)}
                  required
                  className="w-full text-xs rounded-lg border border-slate-300 p-2.5 bg-white focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">-- Choose Candidate --</option>
                  {approvedCandidates.map((c) => (
                    <option key={c.application_id} value={c.application_id}>
                      {c.candidate_name} ({c.candidate_email}) — {c.job_title} [{c.application_status.toUpperCase()}]
                      {c.has_offer ? " (Has Offer)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              {/* Role & Department */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Designation / Title *</label>
                  <input
                    type="text"
                    required
                    value={formData.designation}
                    onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. Senior Software Engineer"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Department *</label>
                  <input
                    type="text"
                    required
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. Engineering"
                  />
                </div>
              </div>

              {/* Salary & Location */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Annual Salary *</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={formData.offered_salary}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value) || 0;
                      const base = Math.round(val * 0.8235);
                      const variable = Math.round(val * 0.0588);
                      const allow = Math.round(val - (base + variable));
                      setFormData({
                        ...formData,
                        offered_salary: val,
                        base_salary: base,
                        variable_compensation: variable,
                        allowances: allow,
                      });
                    }}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Currency *</label>
                  <select
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 bg-white focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="CAD">CAD ($)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Work Location *</label>
                  <input
                    type="text"
                    required
                    value={formData.work_location}
                    onChange={(e) => setFormData({ ...formData, work_location: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. Bengaluru, Karnataka"
                  />
                </div>
              </div>

              {/* Compensation Breakdown & Arrangement */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-blue-50/40 p-3 rounded-xl border border-blue-100">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">Base Salary</label>
                  <input
                    type="number"
                    value={formData.base_salary || 0}
                    onChange={(e) => setFormData({ ...formData, base_salary: parseFloat(e.target.value) || 0 })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-1.5 bg-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">Variable Comp</label>
                  <input
                    type="number"
                    value={formData.variable_compensation || 0}
                    onChange={(e) => setFormData({ ...formData, variable_compensation: parseFloat(e.target.value) || 0 })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-1.5 bg-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">Allowances</label>
                  <input
                    type="number"
                    value={formData.allowances || 0}
                    onChange={(e) => setFormData({ ...formData, allowances: parseFloat(e.target.value) || 0 })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-1.5 bg-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">Work Arrangement</label>
                  <select
                    value={formData.work_arrangement || "Hybrid"}
                    onChange={(e) => setFormData({ ...formData, work_arrangement: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-1.5 bg-white"
                  >
                    <option value="Hybrid">Hybrid</option>
                    <option value="Remote">Remote</option>
                    <option value="On-site">On-site</option>
                  </select>
                </div>
              </div>

              {/* Dates & Probation */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Joining Date *</label>
                  <input
                    type="date"
                    required
                    value={formData.joining_date}
                    onChange={(e) => setFormData({ ...formData, joining_date: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Offer Expiry Date *</label>
                  <input
                    type="date"
                    required
                    value={formData.offer_expiry_date}
                    onChange={(e) => setFormData({ ...formData, offer_expiry_date: e.target.value })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Probation (Months)</label>
                  <input
                    type="number"
                    min={0}
                    max={24}
                    value={formData.probation_period_months}
                    onChange={(e) => setFormData({ ...formData, probation_period_months: parseInt(e.target.value) || 0 })}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Benefits & Terms */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Benefits Summary</label>
                <textarea
                  rows={2}
                  value={formData.benefits_summary}
                  onChange={(e) => setFormData({ ...formData, benefits_summary: e.target.value })}
                  className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Additional Terms & Conditions</label>
                <textarea
                  rows={2}
                  value={formData.additional_terms}
                  onChange={(e) => setFormData({ ...formData, additional_terms: e.target.value })}
                  className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Action Checkbox */}
              <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={formData.send_immediately}
                    onChange={(e) => setFormData({ ...formData, send_immediately: e.target.checked })}
                    className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                  />
                  <span>Send offer immediately to candidate email & portal</span>
                </label>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    {submitting ? "Generating..." : formData.send_immediately ? "Generate & Send Offer" : "Save as Draft"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* OFFER LETTER SUMMARY & PDF PREVIEW MODAL */}
      {previewOffer && (
        <OfferLetterModal
          offer={previewOffer}
          onClose={() => setPreviewOffer(null)}
          onOfferUpdated={fetchData}
        />
      )}
    </div>
  );
}