import { formatDate } from "../utils/dateTime";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

interface AccessRequestStatus {
  request_id: string;
  full_name: string;
  email: string;
  organization_name: string;
  status: string;
  requested_role: string | null;
  created_at: string;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending_email_verification: { label: "Awaiting Email Verification", color: "badge-warning" },
  email_verified: { label: "Email Verified", color: "badge-info" },
  pending_admin_approval: { label: "Pending Admin Approval", color: "badge-primary" },
  approved: { label: "Approved", color: "badge-success" },
  rejected: { label: "Not Approved", color: "badge-danger" },
  account_activation_pending: { label: "Awaiting Account Activation", color: "badge-info" },
  activated: { label: "Account Activated", color: "badge-success" },
  expired: { label: "Request Expired", color: "badge-neutral" },
};

export function AccessRequestPending() {
  const { requestId } = useParams<{ requestId: string }>();
  const [request, setRequest] = useState<AccessRequestStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!requestId) return;
    fetch(`/api/v1/access-requests/${requestId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then(setRequest)
      .catch(() => setError("Could not load access request status."));
  }, [requestId]);

  if (error) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="card relative w-full max-w-md p-8 text-center animate-scale-in">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600 ring-1 ring-inset ring-red-100">
            <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <div className="error-banner justify-center" role="alert">
            {error}
          </div>
        </div>
      </div>
    );
  }

  if (!request) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="card w-full max-w-md space-y-5 p-8 animate-pulse-soft">
          <div className="skeleton h-6 w-56" />
          <div className="skeleton h-4 w-40" />
          <div className="skeleton h-8 w-44 rounded-full" />
          <div className="space-y-3">
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-5/6" />
            <div className="skeleton h-4 w-2/3" />
            <div className="skeleton h-4 w-4/5" />
          </div>
          <div className="skeleton h-20 w-full" />
        </div>
      </div>
    );
  }

  const statusInfo = STATUS_LABELS[request.status] || { label: request.status, color: "badge-neutral" };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />

      <div className="card w-full max-w-md p-8 animate-entrance">
        <div className="mb-6">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-soft">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
            </svg>
          </div>
          <h1 className="page-title text-xl sm:text-2xl">Access Request Status</h1>
          <p className="mt-1 text-sm text-gray-500">Request ID: {request.request_id.slice(0, 8)}...</p>
        </div>

        <div className={`badge ${statusInfo.color} mb-6 px-3 py-1 text-xs`}>
          {statusInfo.label}
        </div>

        <div className="space-y-3.5 text-sm">
          <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3.5">
            <span className="text-gray-500">Name</span>
            <span className="font-medium text-gray-900">{request.full_name}</span>
          </div>
          <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3.5">
            <span className="text-gray-500">Email</span>
            <span className="break-all text-right text-gray-900">{request.email}</span>
          </div>
          <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3.5">
            <span className="text-gray-500">Organization</span>
            <span className="text-right text-gray-900">{request.organization_name}</span>
          </div>
          {request.requested_role && (
            <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3.5">
              <span className="text-gray-500">Requested Role</span>
              <span className="capitalize text-gray-900">{request.requested_role.replace("_", " ")}</span>
            </div>
          )}
          <div className="flex items-center justify-between gap-4">
            <span className="text-gray-500">Submitted</span>
            <span className="text-gray-900">{formatDate(request.created_at)}</span>
          </div>
        </div>

        <div className="panel-brand mt-6 p-4 text-sm leading-relaxed text-gray-700">
          {request.status === "pending_email_verification" && (
            <p>Please check your inbox and verify your email to continue.</p>
          )}
          {request.status === "pending_admin_approval" && (
            <p>Your request is being reviewed by an organization administrator. You'll receive an email once a decision is made.</p>
          )}
          {request.status === "approved" && (
            <p>Your request has been approved! Check your email for the activation link.</p>
          )}
          {request.status === "rejected" && (
            <p>Your request was not approved. Please contact your organization administrator for more information.</p>
          )}
        </div>
      </div>
    </div>
  );
}
