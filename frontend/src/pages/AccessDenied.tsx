import { useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { usePermissions } from "../hooks/usePermissions";
import type { RoleName } from "../types/auth";
import type { Permission } from "../types/permissions";
import { getDashboardPath } from "../utils/roleRouting";

interface AccessDeniedProps {
  requiredRoles?: RoleName[];
  requiredPermission?: Permission;
  requiredPermissions?: Permission[];
}

export function AccessDenied({ requiredRoles, requiredPermission, requiredPermissions }: AccessDeniedProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { role } = usePermissions();

  const getRedirectPath = () => {
    if (!user) return "/login";
    return getDashboardPath(user.roles || []);
  };

  const getRoleLabel = (r: RoleName) => {
    const labels: Record<RoleName, string> = {
      admin: "Administrator",
      super_admin: "Super Administrator",
      organization_admin: "Organization Admin",
      hr: "HR Manager",
      hr_manager: "HR Manager",
      recruiter: "Recruiter",
      candidate: "Candidate",
    };
    return labels[r] ?? r;
  };

  const formatPermission = (p: Permission) => {
    const [domain, resource, action] = p.split(":");
    return `${action} ${resource} (${domain})`;
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-gradient-to-tr from-rose-400 to-red-400 opacity-10 blur-3xl animate-float [animation-delay:2.5s]" aria-hidden="true" />

      <div className="card relative w-full max-w-lg space-y-6 p-8 text-center animate-scale-in sm:p-10">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-red-50 text-red-600 ring-1 ring-inset ring-red-100">
          <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8.25h.008v.008H12V8.25zM11.25 11.25h1.5v1.5h-1.5v-1.5z" />
          </svg>
        </div>
        <div>
          <p className="font-display text-5xl font-extrabold tracking-tight text-red-500">403</p>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-gray-900">Access Denied</h1>
          <p className="mt-2 text-gray-500">
            You don&apos;t have the required permissions to access this page.
          </p>
        </div>

        {(requiredRoles || requiredPermission || requiredPermissions) && (
          <div className="rounded-xl border border-red-200/80 bg-red-50/80 p-4 text-left shadow-xs">
            <h2 className="text-sm font-semibold text-red-800">Required Access:</h2>
            <ul className="mt-2 space-y-1 text-sm text-red-700">
              {requiredRoles && (
                <li>
                  Role: {requiredRoles.map(getRoleLabel).join(" or ")}
                </li>
              )}
              {requiredPermission && (
                <li>Permission: {formatPermission(requiredPermission)}</li>
              )}
              {requiredPermissions && (
                <li>
                  Permissions: {requiredPermissions.map(formatPermission).join(", ")}
                </li>
              )}
            </ul>
            {user && (
              <div className="mt-3 border-t border-red-200 pt-3">
                <p className="text-xs text-red-600">
                  Your role: {role ? getRoleLabel(role) : "Unknown"} | Your roles:{" "}
                  {user.roles.map(getRoleLabel).join(", ")}
                </p>
              </div>
            )}
          </div>
        )}

        <p className="text-sm text-gray-400">
          Please contact your administrator if you believe this is an error.
        </p>

        <div className="flex justify-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="btn-secondary btn-md"
          >
            Go Back
          </button>
          <button
            onClick={() => navigate(getRedirectPath())}
            className="btn-primary btn-md"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
