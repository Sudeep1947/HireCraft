import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { oauthCallback } from "../api/auth";
import { useAuth } from "../hooks/useAuth";
import { getDashboardPath } from "../utils/roleRouting";
import { getServerErrorMessage } from "../utils/error";



export function OAuthCallback() {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleOAuthSuccess } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const executedRef = useRef(false);

  const providerName = provider?.toLowerCase() === "microsoft" ? "Microsoft" : "Google";

  useEffect(() => {
    if (executedRef.current) return;
    executedRef.current = true;

    const errorParam = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (errorParam) {
      setLoading(false);
      if (errorParam === "access_denied" || errorParam === "consent_required") {
        setError(`${providerName} Sign-In was cancelled or access was denied. You can sign in using your password or try again.`);
      } else {
        setError(errorDescription || `Authentication error from ${providerName}: ${errorParam}`);
      }
      return;
    }

    if (!code) {
      setLoading(false);
      setError(`No authorization code returned from ${providerName}. Please try signing in again.`);
      return;
    }

    async function completeSignIn() {
      try {
        setLoading(true);
        setError(null);
        const redirectUri = `${window.location.origin}/auth/callback/${provider}`;
        const tokens = await oauthCallback(provider || "google", {
          code: code!,
          state: state || undefined,
          redirect_uri: redirectUri,
        });

        if (!handleOAuthSuccess) {
          throw new Error("Authentication handler is not available");
        }
        const loggedInUser = await handleOAuthSuccess(tokens);
        const target = getDashboardPath(loggedInUser.roles || []);
        navigate(target, { replace: true });
      } catch (err: unknown) {
        setLoading(false);
        setError(
          getServerErrorMessage(
            err,
            `Failed to complete ${providerName} Sign-In. Please check your credentials or contact an administrator.`,
          ),
        );
      }
    }

    completeSignIn();
  }, [provider, providerName, searchParams, handleOAuthSuccess, navigate]);

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-[#f8faff] p-4 text-slate-900">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-600">
            {providerName === "Google" ? (
              <svg className="h-6 w-6" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
            ) : (
              <svg className="h-6 w-6" viewBox="0 0 21 21">
                <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
              </svg>
            )}
          </div>

          <h2 className="text-xl font-bold tracking-tight text-slate-900">
            {loading ? `Signing in with ${providerName}` : error ? "Authentication Failed" : "Signed In"}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {loading ? "Verifying your credentials with secure OpenID Connect..." : ""}
          </p>
        </div>

        {loading && (
          <div className="mt-8 flex flex-col items-center justify-center space-y-3">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            <span className="text-xs text-slate-400">Communicating with {providerName}...</span>
          </div>
        )}

        {error && (
          <div className="mt-6 space-y-4">
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
              <p className="font-semibold">Unable to complete sign-in</p>
              <p className="mt-1 text-xs text-rose-700">{error}</p>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <Link
                to="/login"
                className="flex w-full items-center justify-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
              >
                Return to Sign In
              </Link>
              <Link
                to="/"
                className="flex w-full items-center justify-center rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
              >
                Back to Home
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
