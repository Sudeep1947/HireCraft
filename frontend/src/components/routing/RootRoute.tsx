import { Navigate } from "react-router-dom";

import { LoadingSpinner } from "../ui/LoadingSpinner";
import { useAuth } from "../../hooks/useAuth";
import { getDashboardPath } from "../../utils/roleRouting";
import type { RoleName } from "../../types/auth";
import { LandingPage } from "../../pages/LandingPage";

/**
 * Entry route for "/".
 *
 * - While the auth state is being restored (refresh token check), render a
 *   loading screen to avoid flashing the landing page for logged-in users.
 * - Authenticated users go straight to their role dashboard using the
 *   canonical role-routing helper (multi-role aware).
 * - Unauthenticated visitors see the public landing page. The page itself
 *   makes zero API calls, so it renders instantly.
 */
export function RootRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white">
        {/* Branded boot screen: quiet gradient atmosphere behind the spinner. */}
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400 to-primary-400 opacity-15 blur-3xl animate-float [animation-delay:2.5s]" aria-hidden="true" />
        <div className="relative">
          <LoadingSpinner size="lg" />
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={getDashboardPath((user?.roles as RoleName[]) || [])} replace />;
  }

  return <LandingPage />;
}
