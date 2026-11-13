import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export function VerifyAccessEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const requestId = searchParams.get("request_id");

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Invalid verification link. No token provided.");
      return;
    }

    const verify = async () => {
      try {
        const verifyUrl = requestId
          ? `/api/v1/access-requests/${requestId}/verify-email?token=${encodeURIComponent(token)}`
          : `/api/v1/access-requests/verify-email?token=${encodeURIComponent(token)}`;
        const res = await fetch(verifyUrl, { method: "POST" });
        const data = await res.json();
        if (!res.ok) {
          setStatus("error");
          setMessage(data.error?.message || data.detail || "Verification failed");
        } else {
          setStatus("success");
          setMessage(data.message);
        }
      } catch {
        setStatus("error");
        setMessage("Network error. Please try again.");
      }
    };

    verify();
  }, [token, requestId]);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400 to-primary-400 opacity-15 blur-3xl animate-float [animation-delay:2.5s]" aria-hidden="true" />

      <div className="card relative w-full max-w-md p-8 text-center animate-scale-in">
        {status === "loading" && (
          <>
            <div className="relative mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 ring-1 ring-inset ring-primary-100">
              <svg
                className="absolute inset-0 m-auto h-14 w-14 animate-spin text-primary-400/40"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <svg className="h-6 w-6 animate-pulse-soft text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
            </div>
            <h2 className="page-title text-xl sm:text-2xl">Verifying Your Email...</h2>
            <p className="mt-2 text-gray-600">Please wait while we verify your company email.</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100">
              <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="page-title text-xl sm:text-2xl">Email Verified</h2>
            <p className="mt-2 text-gray-600">{message}</p>
            <div className="divider my-6" aria-hidden="true" />
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-600 transition-colors hover:text-primary-700"
            >
              <span aria-hidden="true">&larr;</span>
              Back to Login
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600 ring-1 ring-inset ring-red-100">
              <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="page-title text-xl sm:text-2xl">Verification Failed</h2>
            <p className="mt-2 text-gray-600">{message}</p>
            <div className="divider my-6" aria-hidden="true" />
            <Link
              to="/request-access"
              className="btn-primary btn-md"
            >
              Request New Access
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
