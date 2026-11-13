import { formatDate } from "../../utils/dateTime";
import { useEffect, useState } from "react";
import { Inbox, CheckCircle2, XCircle, Search } from "lucide-react";

import { Button } from "../../components/ui/Button";

interface AccessRequest {
  id: string;
  full_name: string;
  email: string;
  organization_id: string;
  organization_name: string;
  requested_role: string | null;
  status: string;
  email_verified_at: string | null;
  approved_role: string | null;
  rejection_reason: string | null;
  created_at: string;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending_email_verification: { label: "Awaiting Email", color: "badge-warning" },
  email_verified: { label: "Email Verified", color: "badge-info" },
  pending_admin_approval: { label: "Needs Review", color: "badge-primary" },
  approved: { label: "Approved", color: "badge-success" },
  rejected: { label: "Rejected", color: "badge-danger" },
  account_activation_pending: { label: "Activation Pending", color: "badge-info" },
  activated: { label: "Activated", color: "badge-success" },
  expired: { label: "Expired", color: "badge-neutral" },
};

export function AdminAccessRequests() {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [approveModal, setApproveModal] = useState<string | null>(null);
  const [approveRole, setApproveRole] = useState<"hr_manager" | "recruiter">("recruiter");
  const [rejectModal, setRejectModal] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const fetchRequests = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ offset: String(page * 25), limit: "25" });
      if (filter) params.set("status", filter);
      const res = await fetch(`/api/v1/access-requests?${params}`);
      if (res.ok) {
        const data = await res.json();
        setRequests(data.requests || []);
        setTotal(data.total || 0);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchRequests(); }, [page, filter]);

  const handleApprove = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      const res = await fetch(`/api/v1/access-requests/${requestId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved_role: approveRole }),
      });
      if (res.ok) { fetchRequests(); setApproveModal(null); }
    } finally { setActionLoading(null); }
  };

  const handleReject = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      const res = await fetch(`/api/v1/access-requests/${requestId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: rejectReason || undefined }),
      });
      if (res.ok) { fetchRequests(); setRejectModal(null); setRejectReason(""); }
    } finally { setActionLoading(null); }
  };

  const pending = requests.filter((r) => r.status === "pending_admin_approval");

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Access Requests</h1>
          <p className="page-subtitle">
            {total} total request{total !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {pending.length > 0 && (
        <div className="info-banner">
          <Inbox className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            {pending.length} request{pending.length !== 1 ? "s" : ""} pending your review
          </p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {["", "pending_admin_approval", "approved", "rejected", "activated"].map((s) => (
          <button
            key={s}
            onClick={() => { setFilter(s); setPage(0); }}
            className={`chip ${filter === s ? "border-primary-300 bg-primary-50 text-primary-700" : ""}`}
          >
            {s ? STATUS_LABELS[s]?.label || s : "All"}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <div className="skeleton h-10 w-full" />
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 w-full" />
          ))}
        </div>
      ) : requests.length === 0 ? (
        <div className="empty-state">
          <Search className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <h3 className="text-base font-semibold text-gray-900">No access requests found.</h3>
          <p className="mt-1 text-sm text-gray-500">
            New registration requests will appear here for review.
          </p>
        </div>
      ) : (
        <div className="table-wrap animate-fade-in">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Date</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => {
                const statusInfo = STATUS_LABELS[req.status] || { label: req.status, color: "badge-neutral" };
                return (
                  <tr key={req.id}>
                    <td className="font-medium text-gray-900">{req.full_name}</td>
                    <td>{req.email}</td>
                    <td className="capitalize">
                      {req.requested_role ? req.requested_role.replace("_", " ") : "-"}
                    </td>
                    <td>
                      <span className={statusInfo.color}>{statusInfo.label}</span>
                    </td>
                    <td className="text-gray-500">{formatDate(req.created_at)}</td>
                    <td className="text-right">
                      {req.status === "pending_admin_approval" && (
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => setApproveModal(req.id)}
                            disabled={actionLoading === req.id}
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                            Approve
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => setRejectModal(req.id)}
                            disabled={actionLoading === req.id}
                          >
                            <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                            Reject
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {total > 25 && (
        <div className="flex items-center justify-center gap-3">
          <Button variant="secondary" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
            Previous
          </Button>
          <span className="text-sm text-gray-600">
            Page {page + 1} of {Math.ceil(total / 25)}
          </span>
          <Button variant="secondary" size="sm" onClick={() => setPage((p) => p + 1)} disabled={(page + 1) * 25 >= total}>
            Next
          </Button>
        </div>
      )}

      {approveModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/40 p-4 backdrop-blur-sm"
          onClick={() => setApproveModal(null)}
        >
          <div
            className="card-solid w-full max-w-sm animate-scale-in p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="section-title mb-4">Approve Access Request</h3>
            <label className="field-label" htmlFor="approve-role">Assign Role</label>
            <select
              id="approve-role"
              value={approveRole}
              onChange={(e) => setApproveRole(e.target.value as "hr_manager" | "recruiter")}
              className="field mb-4"
            >
              <option value="recruiter">Recruiter</option>
              <option value="hr_manager">HR Manager</option>
            </select>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setApproveModal(null)}>Cancel</Button>
              <Button variant="primary" onClick={() => approveModal && handleApprove(approveModal)} disabled={!!actionLoading}>
                Approve
              </Button>
            </div>
          </div>
        </div>
      )}

      {rejectModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/40 p-4 backdrop-blur-sm"
          onClick={() => setRejectModal(null)}
        >
          <div
            className="card-solid w-full max-w-sm animate-scale-in p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="section-title mb-4">Reject Access Request</h3>
            <label className="field-label" htmlFor="reject-reason">Reason (optional)</label>
            <textarea
              id="reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="field mb-4"
              rows={3}
              placeholder="Explain why this request was rejected..."
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => { setRejectModal(null); setRejectReason(""); }}>Cancel</Button>
              <Button variant="danger" onClick={() => rejectModal && handleReject(rejectModal)} disabled={!!actionLoading}>
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
