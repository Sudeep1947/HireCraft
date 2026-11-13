import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { LoadingSpinner } from "./ui/LoadingSpinner";
import { AccessDenied } from "../pages/AccessDenied";
import type { RoleName } from "../types/auth";
import { isRoleAllowed } from "../utils/roleRouting";
import type { Permission } from "../types/permissions";
import { hasPermission, hasAnyPermission, hasAllPermissions } from "../types/permissions";

interface ProtectedRouteProps {
  children: React.ReactNode;
  roles?: RoleName[];
  permission?: Permission;
  anyPermission?: Permission[];
  allPermissions?: Permission[];
}

export function ProtectedRoute({
  children,
  roles,
  permission,
  anyPermission,
  allPermissions,
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (user) {
    if (roles) {
      if (!isRoleAllowed(roles, user.roles)) {
        return <AccessDenied requiredRoles={roles} />;
      }
    }

    if (permission && !hasPermission(user.roles, permission)) {
      return <AccessDenied requiredPermission={permission} />;
    }

    if (anyPermission && anyPermission.length > 0) {
      if (!hasAnyPermission(user.roles, anyPermission)) {
        return <AccessDenied requiredPermission={anyPermission[0]} />;
      }
    }

    if (allPermissions && allPermissions.length > 0) {
      if (!hasAllPermissions(user.roles, allPermissions)) {
        return <AccessDenied requiredPermissions={allPermissions} />;
      }
    }
  }

  return <>{children}</>;
}
