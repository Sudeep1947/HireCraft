import { formatDate } from "../utils/dateTime";
import { useCallback, useEffect, useState } from "react";

import { CreateOrganizationCard } from "../components/organization/CreateOrganizationCard";
import { getServerErrorMessage } from "../utils/error";
import { Button } from "../components/ui/Button";
import { useAuth } from "../hooks/useAuth";
import type { Organization, OrganizationMembership, Invitation } from "../types/auth";
import * as authApi from "../api/auth";

const ROLE_LABELS: Record<string, string> = {
  organization_admin: "Org Admin",
  hr_manager: "HR Manager",
  recruiter: "Recruiter",
  candidate: "Candidate",
};

export function TeamManagement() {
  const { user } = useAuth();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrganizationMembership[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [successBanner, setSuccessBanner] = useState("");
  const [inviteForm, setInviteForm] = useState({ email: "", role: "recruiter" });
  const [inviteError, setInviteError] = useState("");
  const [inviteSuccess, setInviteSuccess] = useState("");
  const [isInviting, setIsInviting] = useState(false);

  const loadData = useCallback(async (orgId: string) => {
    try {
      const [membersResp, invitationsResp] = await Promise.all([
        authApi.getOrgMembers(orgId),
        authApi.getOrgInvitations(orgId),
      ]);
      setMembers(membersResp.items);
      setInvitations(invitationsResp.items);
    } catch {
      console.error("Failed to load team data");
    }
  }, []);

  useEffect(() => {
    async function init() {
      try {
        const orgs = await authApi.getMyOrganizations();
        setOrganizations(orgs);
        if (orgs.length > 0) {
          setSelectedOrg(orgs[0]);
          await loadData(orgs[0].id);
        }
      } catch {
        console.error("Failed to load organizations");
      } finally {
        setIsLoading(false);
      }
    }
    init();
  }, [loadData]);

  const handleOrgChange = async (orgId: string) => {
    const org = organizations.find((o) => o.id === orgId);
    if (org) {
      setSelectedOrg(org);
      await loadData(org.id);
    }
  };

  const handleOrganizationCreated = async (newOrg: Organization) => {
    setIsCreateOpen(false);
    setSuccessBanner(`Organization "${newOrg.name}" created successfully.`);
    let createdOrg = newOrg;
    try {
      const orgs = await authApi.getMyOrganizations();
      setOrganizations(orgs);
      createdOrg = orgs.find((o) => o.id === newOrg.id) ?? newOrg;
    } catch {
      setOrganizations((prev) =>
        prev.some((o) => o.id === newOrg.id) ? prev : [newOrg, ...prev]
      );
    }

    setSelectedOrg(createdOrg);
    await loadData(createdOrg.id);
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError("");
    setInviteSuccess("");
    if (!selectedOrg) return;

    setIsInviting(true);
    try {
      const invitation = await authApi.inviteMember(selectedOrg.id, inviteForm.email, inviteForm.role);
      if (invitation.email_status === "skipped" || invitation.email_status === "error") {
        setInviteSuccess(
          invitation.accept_url
            ? `Invitation created for ${inviteForm.email}! (Email delivery skipped/pending. Direct link: ${invitation.accept_url})`
            : `Invitation created for ${inviteForm.email}! (Email delivery skipped/pending)`
        );
      } else {
        setInviteSuccess(`Invitation sent to ${inviteForm.email}`);
      }
      setInviteForm({ email: "", role: "recruiter" });
      await loadData(selectedOrg.id);
    } catch (err: any) {
      setInviteError(getServerErrorMessage(err, "Failed to send invitation"));
    } finally {
      setIsInviting(false);
    }
  };

  const handleRevokeInvitation = async (invitationId: string) => {
    if (!selectedOrg) return;
    try {
      await authApi.revokeInvitation(selectedOrg.id, invitationId);
      await loadData(selectedOrg.id);
    } catch {
      console.error("Failed to revoke invitation");
    }
  };

  const handleResendInvitation = async (invitationId: string) => {
    if (!selectedOrg) return;
    try {
      await authApi.resendInvitation(selectedOrg.id, invitationId);
      await loadData(selectedOrg.id);
    } catch {
      console.error("Failed to resend invitation");
    }
  };

  const handleToggleMemberStatus = async (membershipId: string, currentStatus: string) => {
    if (!selectedOrg) return;
    const newStatus = currentStatus === "active" ? "suspended" : "active";
    try {
      await authApi.updateMemberStatus(selectedOrg.id, membershipId, newStatus);
      await loadData(selectedOrg.id);
    } catch {
      console.error("Failed to update member status");
    }
  };

  const isSuperAdmin = user?.roles?.includes("super_admin") || user?.roles?.includes("admin");
  const isOrgAdmin = isSuperAdmin || user?.roles?.includes("organization_admin");

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <div className="skeleton h-8 w-56" />
          <div className="skeleton h-4 w-72" />
        </div>
        <div className="card space-y-4 p-6 bg-white rounded-2xl border border-gray-100 shadow-xs">
          <div className="skeleton h-5 w-44" />
          <div className="flex gap-4">
            <div className="skeleton h-10 flex-1" />
            <div className="skeleton h-10 w-48" />
          </div>
        </div>
        <div className="card divide-y divide-gray-100 bg-white rounded-2xl border border-gray-100 shadow-xs">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center justify-between p-4">
              <div className="space-y-2">
                <div className="skeleton h-4 w-40" />
                <div className="skeleton h-3 w-56" />
              </div>
              <div className="skeleton h-5 w-24 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!isOrgAdmin) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="card w-full max-w-md space-y-4 p-8 text-center bg-white rounded-2xl border border-gray-100 shadow-xs">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600 ring-1 ring-inset ring-red-100">
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900">Access Denied</h2>
          <p className="text-sm text-gray-500">You need organization admin privileges to manage teams.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 tracking-tight">Team Management</h1>
          <p className="mt-1 text-sm text-gray-500">Manage your organization's team members and invitations.</p>
        </div>
        {isSuperAdmin && (
          <Button
            onClick={() => {
              setSuccessBanner("");
              setIsCreateOpen(true);
            }}
            className="flex items-center gap-2 self-start sm:self-auto rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm px-4 py-2.5 shadow-sm transition-all"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            + Create Organization
          </Button>
        )}
      </div>

      {successBanner && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 shadow-xs" role="status">
          {successBanner}
        </div>
      )}

      {/* Modal for Organization Creation */}
      {isCreateOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-fade-in overflow-y-auto"
          role="dialog"
          aria-modal="true"
        >
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <CreateOrganizationCard
              onCreated={handleOrganizationCreated}
              onCancel={() => setIsCreateOpen(false)}
            />
          </div>
        </div>
      )}

      {/* 1. Organization Selector Card — Exactly matching Image 2 */}
      {organizations.length > 0 ? (
        <div className="card p-6 bg-white rounded-2xl border border-gray-100 shadow-xs">
          <label className="block text-xs font-semibold text-gray-700 mb-2">Organization</label>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <select
              value={selectedOrg?.id || ""}
              onChange={(e) => handleOrgChange(e.target.value)}
              className="rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-800 bg-white w-full max-w-md focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
              aria-label="Organization selector"
            >
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
            {isSuperAdmin && (
              <button
                type="button"
                onClick={() => {
                  setSuccessBanner("");
                  setIsCreateOpen(true);
                }}
                className="text-xs font-medium text-indigo-600 hover:text-indigo-800 hover:underline self-start sm:self-auto"
              >
                + New Organization
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="card p-8 text-center bg-white rounded-2xl border border-gray-100 shadow-xs">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
            </svg>
          </div>
          <h3 className="text-base font-bold text-gray-900">No Organizations Found</h3>
          <p className="mt-1 text-sm text-gray-500 max-w-md mx-auto">
            {isSuperAdmin
              ? "No organizations exist in the system yet. Click '+ Create Organization' to create one."
              : "A platform administrator must create an organization before you can manage a team."}
          </p>
          {isSuperAdmin && (
            <Button
              onClick={() => {
                setSuccessBanner("");
                setIsCreateOpen(true);
              }}
              size="sm"
              className="mt-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm"
            >
              Create First Organization
            </Button>
          )}
        </div>
      )}

      {selectedOrg && (
        <>
          {/* 2. Invite Team Member Card — Exactly matching Image 2 */}
          <div className="card p-6 bg-white rounded-2xl border border-gray-100 shadow-xs">
            <h2 className="text-base font-bold text-gray-900 mb-4">Invite Team Member to {selectedOrg.name}</h2>
            <form onSubmit={handleInvite} className="flex flex-col gap-4 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className="block text-xs font-semibold text-gray-700 mb-2">Email</label>
                <input
                  type="email"
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm((p) => ({ ...p, email: e.target.value }))}
                  placeholder="colleague@company.com"
                  required
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
                />
              </div>
              <div className="w-full sm:w-48">
                <label className="block text-xs font-semibold text-gray-700 mb-2">Role</label>
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm((p) => ({ ...p, role: e.target.value }))}
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-800 bg-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
                  aria-label="Role"
                >
                  <option value="recruiter">Recruiter</option>
                  <option value="hr_manager">HR Manager</option>
                  <option value="organization_admin">Org Admin</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={isInviting}
                className="rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm px-6 py-2.5 shadow-sm transition-all disabled:opacity-50 h-[42px]"
              >
                {isInviting ? "Sending..." : "Send Invitation"}
              </button>
            </form>
            {inviteError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 mt-3 text-sm text-red-700 font-medium" role="alert">
                {inviteError}
              </div>
            )}
            {inviteSuccess && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 mt-3 text-sm text-emerald-700 font-medium" role="status">
                {inviteSuccess}
              </div>
            )}
          </div>

          {/* 3. Team Members Card — Exactly matching Image 2 */}
          <div className="card bg-white rounded-2xl border border-gray-100 shadow-xs overflow-hidden">
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-base font-bold text-gray-900">Team Members ({members.length})</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {members.map((m) => (
                <div key={m.id} className="flex flex-col gap-3 p-4 px-6 transition-colors hover:bg-slate-50/60 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white shadow-xs">
                      {(m.user?.full_name || m.user?.email || "?").charAt(0).toUpperCase()}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-gray-900 text-sm">{m.user?.full_name || "Unknown User"}</p>
                      <p className="truncate text-xs text-gray-500">{m.user?.email}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
                    <span className="inline-flex items-center rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200/50">
                      {ROLE_LABELS[m.role] || m.role}
                    </span>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      m.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                    }`}>
                      {m.status}
                    </span>
                    {m.user?.id !== user?.id && (
                      <button
                        onClick={() => handleToggleMemberStatus(m.id, m.status)}
                        className={`text-xs font-semibold ml-2 hover:underline transition-colors ${
                          m.status === "active"
                            ? "text-gray-400 hover:text-red-600"
                            : "text-emerald-600 hover:text-emerald-700"
                        }`}
                      >
                        {m.status === "active" ? "Suspend" : "Reactivate"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {members.length === 0 && (
                <div className="p-8 text-center text-sm text-gray-500">
                  No team members found.
                </div>
              )}
            </div>
          </div>

          {/* 4. Organizations Overview Cards Grid */}
          <div className="card p-6 bg-white rounded-2xl border border-gray-100 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-gray-900">Organizations ({organizations.length})</h2>
                <p className="text-xs text-gray-500">All registered organizations under administration.</p>
              </div>
              {selectedOrg && (
                <span className="text-xs text-gray-500">
                  Active: <strong className="text-indigo-600">{selectedOrg.name}</strong>
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {organizations.map((org) => {
                const isSelected = selectedOrg?.id === org.id;
                return (
                  <div
                    key={org.id}
                    onClick={() => handleOrgChange(org.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        handleOrgChange(org.id);
                      }
                    }}
                    className={`relative cursor-pointer p-5 rounded-xl border transition-all hover:border-indigo-300 hover:shadow-sm ${
                      isSelected
                        ? "border-indigo-500 ring-2 ring-indigo-500/20 bg-indigo-50/10"
                        : "border-gray-200 bg-white"
                    }`}
                    aria-pressed={isSelected}
                    aria-label={`Select ${org.name}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        {org.logo_url ? (
                          <img
                            src={org.logo_url}
                            alt={`${org.name} logo`}
                            className="h-10 w-10 shrink-0 rounded-xl object-contain bg-slate-50 p-1 border border-gray-200"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              const fallback = e.currentTarget.parentElement?.querySelector(".team-fallback-avatar") as HTMLElement;
                              if (fallback) fallback.classList.remove("hidden");
                            }}
                          />
                        ) : null}
                        <span
                          className={`team-fallback-avatar flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold text-white shadow-xs ${org.logo_url ? "hidden" : ""}`}
                        >
                          {org.name.charAt(0).toUpperCase()}
                        </span>
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold text-gray-900 text-sm">{org.name}</h3>
                          <p className="truncate text-xs text-gray-500">@{org.slug}</p>
                        </div>
                      </div>
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold shrink-0 ${
                          org.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {org.status}
                      </span>
                    </div>

                    <div className="mt-3 space-y-1 text-xs text-gray-600 border-t border-gray-100 pt-3">
                      {org.industry && (
                        <p className="flex items-center gap-1.5 truncate">
                          <span className="text-gray-400">Industry:</span>
                          <span className="font-medium text-gray-700">{org.industry}</span>
                        </p>
                      )}
                      {org.location && (
                        <p className="flex items-center gap-1.5 truncate">
                          <span className="text-gray-400">Location:</span>
                          <span className="font-medium text-gray-700">{org.location}</span>
                        </p>
                      )}
                      {org.website && (
                        <p className="flex items-center gap-1.5 truncate">
                          <span className="text-gray-400">Website:</span>
                          <a
                            href={org.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="truncate text-indigo-600 hover:underline"
                          >
                            {org.website.replace(/^https?:\/\//, "")}
                          </a>
                        </p>
                      )}
                      {org.description && (
                        <p className="text-xs text-gray-500 line-clamp-2 mt-1">
                          {org.description}
                        </p>
                      )}
                    </div>

                    <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-2 text-xs">
                      <span className="text-gray-400">
                        {formatDate(org.created_at, "")}
                      </span>
                      {isSelected ? (
                        <span className="font-semibold text-indigo-600">Selected</span>
                      ) : (
                        <span className="text-gray-400 hover:text-gray-600">Click to select</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 5. Pending Invitations Card */}
          <div className="card bg-white rounded-2xl border border-gray-100 shadow-xs overflow-hidden">
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-base font-bold text-gray-900">
                Pending Invitations ({invitations.filter((i) => i.status === "pending").length})
              </h2>
            </div>
            <div className="divide-y divide-gray-100">
              {invitations.filter((i) => i.status === "pending").map((inv) => (
                <div key={inv.id} className="flex flex-col gap-3 p-4 px-6 transition-colors hover:bg-slate-50/60 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-gray-900 text-sm">{inv.email}</p>
                    <p className="text-xs text-gray-500">
                      {ROLE_LABELS[inv.role] || inv.role} • Expires {formatDate(inv.expires_at, "N/A")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleResendInvitation(inv.id)}
                      className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition-colors"
                    >
                      Resend
                    </button>
                    <button
                      onClick={() => handleRevokeInvitation(inv.id)}
                      className="text-xs font-semibold text-red-600 hover:text-red-800 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
                    >
                      Revoke
                    </button>
                  </div>
                </div>
              ))}
              {invitations.filter((i) => i.status === "pending").length === 0 && (
                <div className="p-8 text-center text-sm text-gray-500">
                  No pending invitations.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
