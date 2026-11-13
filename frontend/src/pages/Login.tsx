import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import heroVisual from "../assets/hero-visual.jpg";
import { Button } from "../components/ui/Button";
import { useAuth } from "../hooks/useAuth";
import { getErrorMessage } from "../utils/error";
import { devOAuthLogin } from "../api/auth";
import { validateLoginForm } from "../utils/validation";
import { getDashboardPath } from "../utils/roleRouting";



const roleHints = [
  {
    role: "admin",
    label: "Admin",
    icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
    color: "text-rose-700 bg-rose-50/80 border-rose-200/70",
  },
  {
    role: "hr",
    label: "HR",
    icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z",
    color: "text-purple-700 bg-purple-50/80 border-purple-200/70",
  },
  {
    role: "recruiter",
    label: "Recruiter",
    icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
    color: "text-blue-700 bg-blue-50/80 border-blue-200/70",
  },
  {
    role: "candidate",
    label: "Candidate",
    icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
    color: "text-emerald-700 bg-emerald-50/80 border-emerald-200/70",
  },
];

export function Login() {
  const navigate = useNavigate();
  const { login, isAuthenticated, user, handleOAuthSuccess } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [ssoNotice, setSsoNotice] = useState<string | null>(null);
  const [showForgotModal, setShowForgotModal] = useState(false);

  // Same-app redirect target (open-redirect safe: must be a relative path).
  const searchParams = new URLSearchParams(window.location.search);
  const rawRedirect = searchParams.get("redirect") || "";
  const redirectTarget = rawRedirect.startsWith("/") && !rawRedirect.startsWith("//") ? rawRedirect : "";

  if (isAuthenticated) {
    if (redirectTarget) return <Navigate to={redirectTarget} replace />;
    return <Navigate to={getDashboardPath(user?.roles || [])} replace />;
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setErrors((prev) => ({ ...prev, [e.target.name]: "" }));
    setServerError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");
    setSsoNotice(null);

    const validationErrors = validateLoginForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsLoading(true);
    try {
      const loggedInUser = await login({ ...form, remember_me: rememberMe });
      navigate(redirectTarget || getDashboardPath(loggedInUser.roles));
    } catch (err) {
      setServerError(getErrorMessage(err, "Login failed. Please check your credentials and try again."));
    } finally {
      setIsLoading(false);
    }
  };

  // SSO accounts
  const [ssoModalProvider, setSsoModalProvider] = useState<"Google" | "Microsoft" | null>(null);
  const [customSsoEmail, setCustomSsoEmail] = useState("");
  const [customSsoName, setCustomSsoName] = useState("");
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [ssoSubmitting, setSsoSubmitting] = useState(false);

  const googleAccounts = [
    { name: "Harish", email: "miniprojectcse000@gmail.com", role: "HR Manager", roleColor: "bg-purple-100 text-purple-700 border-purple-200" },
    { name: "Pankaja", email: "pankajanagaraj405@gmail.com", role: "Recruiter", roleColor: "bg-blue-100 text-blue-700 border-blue-200" },
    { name: "Nagendra N", email: "nagu22022002@gmail.com", role: "Candidate", roleColor: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    { name: "Gagan B", email: "gagan@gmail.com", role: "Candidate", roleColor: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    { name: "Santhosh", email: "santhosh@gmail.com", role: "Candidate", roleColor: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    { name: "Ullas N", email: "ullasnullas204@gmail.com", role: "Admin", roleColor: "bg-rose-100 text-rose-700 border-rose-200" },
  ];

  const microsoftAccounts = [
    { name: "Harish", email: "miniprojectcse000@gmail.com", role: "HR Manager", roleColor: "bg-purple-100 text-purple-700 border-purple-200" },
    { name: "Pankaja", email: "pankajanagaraj405@gmail.com", role: "Recruiter", roleColor: "bg-blue-100 text-blue-700 border-blue-200" },
    { name: "System Admin", email: "admin@hirecraft.ai", role: "Admin", roleColor: "bg-rose-100 text-rose-700 border-rose-200" },
    { name: "Nagendra N", email: "nagu22022002@gmail.com", role: "Candidate", roleColor: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    { name: "Gagan B", email: "gagan@gmail.com", role: "Candidate", roleColor: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    { name: "Santhosh", email: "santhosh@gmail.com", role: "Candidate", roleColor: "bg-emerald-100 text-emerald-700 border-emerald-200" },
  ];

  const handleSsoClick = (provider: "Google" | "Microsoft") => {
    setSsoNotice(null);
    setServerError("");
    setCustomSsoEmail("");
    setCustomSsoName("");
    setShowCustomInput(false);
    setSsoModalProvider(provider);
  };

  const handleSelectSsoAccount = async (email: string, provider: "google" | "microsoft", fullName?: string) => {
    setSsoSubmitting(true);
    setServerError("");
    setSsoNotice(null);
    try {
      const tokens = await devOAuthLogin(email, provider, fullName);
      if (handleOAuthSuccess) {
        const loggedInUser = await handleOAuthSuccess(tokens);
        setSsoModalProvider(null);
        navigate(redirectTarget || getDashboardPath(loggedInUser.roles));
      } else {
        setSsoModalProvider(null);
        navigate(redirectTarget || getDashboardPath(tokens.user?.roles || []));
      }
    } catch (err: unknown) {
      setServerError(getErrorMessage(err, `Failed to sign in with ${provider === "google" ? "Google" : "Microsoft"}. Please try again.`));
    } finally {
      setSsoSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#f8faff] text-slate-900 lg:grid lg:grid-cols-12">
      {/* ── Left Side: AI Hiring Copilot Hero Visual (Completely visible, fitted) ── */}
      <div className="relative hidden lg:col-span-6 lg:flex flex-col items-center justify-center overflow-hidden bg-[#001038] p-2 xl:p-4 text-white">
        {/* Seamless background gradient matching image palette */}
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#00123a] via-[#010e34] to-[#011442]"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -top-24 -left-24 h-96 w-96 rounded-full bg-blue-600/15 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-24 -right-24 h-96 w-96 rounded-full bg-violet-600/15 blur-3xl"
          aria-hidden="true"
        />

        <div className="relative z-10 flex h-full w-full items-center justify-center">
          <Link
            to="/"
            className="group flex h-full w-full items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
            title="AI Hiring Copilot - Return to Home"
          >
            <img
              src={heroVisual}
              alt="AI Hiring Copilot - AI Career Intelligence. Find Your Next Opportunity. Smarter hiring, better careers."
              loading="eager"
              className="max-h-full max-w-full w-auto h-auto object-contain object-center select-none drop-shadow-[0_20px_50px_rgba(0,0,0,0.5)] transition-transform duration-500 group-hover:scale-[1.008]"
            />
          </Link>
        </div>
      </div>

      {/* ── Right Side: Clean Modern Login Form ─────────────────────────── */}
      <div className="flex lg:col-span-6 flex-col justify-between p-6 sm:p-10 lg:p-12 xl:p-16 bg-white">
        {/* Top Header Bar */}
        <div className="flex items-center justify-between gap-4">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-[6px] border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-xs transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            aria-label="Back to Home"
          >
            <span aria-hidden="true">&larr;</span>
            <span>Back to Home</span>
          </Link>

          <div className="text-xs text-slate-500">
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
              className="font-semibold text-primary-600 transition-colors hover:text-primary-700 hover:underline"
            >
              Create Account
            </Link>
          </div>
        </div>

        {/* Center Form Container */}
        <div className="mx-auto w-full max-w-md py-8">
          {/* Mobile-only brand identifier */}
          <div className="mb-6 lg:hidden">
            <Link to="/" className="inline-flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-gradient-to-tr from-indigo-500 via-primary-500 to-violet-400 text-white shadow-xs">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="font-display text-lg font-bold tracking-tight text-slate-900">
                Skill2Job
              </span>
            </Link>
          </div>

          <div className="space-y-1.5">
            <h2 className="font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              Welcome back
            </h2>
            <p className="text-sm text-slate-500">
              Sign in to access your Skill2Job portal
            </p>
          </div>

          {serverError && (
            <div
              className="mt-5 rounded-[8px] border border-rose-200 bg-rose-50/90 p-3.5 text-sm text-rose-700 shadow-xs"
              role="alert"
            >
              {serverError}
            </div>
          )}

          {ssoNotice && (
            <div className="mt-4 flex items-start gap-2.5 rounded-[8px] border border-blue-200 bg-blue-50/80 p-3 text-xs text-blue-800 shadow-xs">
              <svg className="h-4 w-4 shrink-0 mt-0.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="flex-1">
                <p className="font-medium">{ssoNotice}</p>
              </div>
              <button
                type="button"
                onClick={() => setSsoNotice(null)}
                className="text-blue-500 hover:text-blue-700"
                aria-label="Dismiss notice"
              >
                &times;
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {/* Email Field */}
            <div className="space-y-1.5">
              <label htmlFor="email" className="block text-xs font-semibold uppercase tracking-wider text-slate-600">
                Email
              </label>
              <input
                id="email"
                type="email"
                name="email"
                autoComplete="email"
                value={form.email}
                onChange={handleChange}
                placeholder="you@company.com"
                className={`block w-full rounded-[8px] border bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-xs transition-all placeholder:text-slate-400 focus:outline-none focus:ring-1 ${
                  errors.email
                    ? "border-rose-300 focus:border-rose-400 focus:ring-rose-400"
                    : "border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                }`}
              />
              {errors.email && (
                <p className="text-xs font-medium text-rose-600">{errors.email}</p>
              )}
            </div>

            {/* Password Field with Show/Hide Toggle */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-wider text-slate-600">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  className="text-xs font-medium text-primary-600 hover:text-primary-700 hover:underline focus:outline-none"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  name="password"
                  autoComplete="current-password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  className={`block w-full rounded-[8px] border bg-white px-3.5 py-2.5 pr-10 text-sm text-slate-900 shadow-xs transition-all placeholder:text-slate-400 focus:outline-none focus:ring-1 ${
                    errors.password
                      ? "border-rose-300 focus:border-rose-400 focus:ring-rose-400"
                      : "border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                  }`}
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide" : "Show"}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600 focus:outline-none"
                >
                  {showPassword ? (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                    </svg>
                  ) : (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs font-medium text-rose-600">{errors.password}</p>
              )}
            </div>

            {/* Remember Me */}
            <div className="flex items-center justify-between pt-1">
              <label htmlFor="remember-me" className="flex cursor-pointer items-center gap-2.5 text-xs text-slate-600 select-none hover:text-slate-900">
                <input
                  type="checkbox"
                  id="remember-me"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded-[4px] border-slate-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Remember me</span>
              </label>
            </div>

            {/* Prominent Sign In Button */}
            <Button
              type="submit"
              isLoading={isLoading}
              className="w-full rounded-[8px] py-2.5 text-sm font-semibold shadow-md bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 text-white border-0"
            >
              Sign in
            </Button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center" aria-hidden="true">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase tracking-wider">
              <span className="bg-white px-3 font-medium text-slate-400">
                or continue with
              </span>
            </div>
          </div>

          {/* Google and Microsoft Sign-In Buttons */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <button
              type="button"
              aria-label="Google"
              onClick={() => handleSsoClick("Google")}
              disabled={ssoSubmitting || isLoading}
              className="inline-flex items-center justify-center gap-2.5 rounded-[8px] border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-700 shadow-xs transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z" />
                <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z" />
                <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.98 0 12s.45 3.82 1.25 5.42l4.03-3.15z" />
                <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z" />
              </svg>
              <span>Sign in with Google</span>
            </button>

            <button
              type="button"
              aria-label="Microsoft"
              onClick={() => handleSsoClick("Microsoft")}
              disabled={ssoSubmitting || isLoading}
              className="inline-flex items-center justify-center gap-2.5 rounded-[8px] border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-700 shadow-xs transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 21 21" aria-hidden="true">
                <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
              </svg>
              <span>Sign in with Microsoft</span>
            </button>
          </div>

          {/* Supported Roles Quick Reference */}
          <div className="mt-8 rounded-[8px] border border-slate-200/80 bg-slate-50/70 p-3.5 space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Supported Roles
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {roleHints.map((hint) => (
                <div
                  key={hint.role}
                  className={`flex items-center gap-1.5 rounded-[6px] border px-2 py-1 text-xs font-medium ${hint.color}`}
                >
                  <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={hint.icon} />
                  </svg>
                  <span>{hint.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Link Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 border-t border-slate-100 pt-4 text-xs text-slate-400">
          <span>&copy; {new Date().getFullYear()} Skill2Job. All rights reserved.</span>
          <span>Protected by enterprise encryption</span>
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-[8px] border border-slate-200 bg-white p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">Reset Your Password</h3>
              <button
                type="button"
                onClick={() => setShowForgotModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
                aria-label="Close"
              >
                &times;
              </button>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              If you have an active Skill2Job account, please enter your registered email address or contact your organization administrator to receive password recovery instructions.
            </p>
            <div className="rounded-[6px] border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              For support inquiries or administrator assistance, you can also{" "}
              <Link to="/request-access" className="font-semibold text-primary-600 hover:underline">
                request access assistance
              </Link>.
            </div>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setShowForgotModal(false)}
                className="rounded-[6px] border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    
      {/* ── Google & Microsoft SSO Account Chooser Modal ── */}
      {ssoModalProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 animate-scale-up">
            {/* Header with Provider Branding */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                {ssoModalProvider === "Google" ? (
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 border border-slate-100 shadow-xs">
                    <svg className="h-6 w-6" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                    </svg>
                  </div>
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 border border-slate-100 shadow-xs">
                    <svg className="h-6 w-6" viewBox="0 0 21 21">
                      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
                    </svg>
                  </div>
                )}
                <div>
                  <h3 className="text-base font-bold text-slate-900 tracking-tight">
                    {ssoModalProvider === "Google" ? "Sign in with Google" : "Sign in with Microsoft"}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {ssoModalProvider === "Google" ? "Choose an account to continue to Skill2Job" : "Pick an account to continue to Skill2Job"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSsoModalProvider(null)}
                className="rounded-lg p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                aria-label="Close"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Quick-Pick Account List */}
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {(ssoModalProvider === "Google" ? googleAccounts : microsoftAccounts).map((acc) => (
                <button
                  key={acc.email}
                  type="button"
                  disabled={ssoSubmitting}
                  onClick={() => handleSelectSsoAccount(acc.email, ssoModalProvider === "Google" ? "google" : "microsoft", acc.name)}
                  className="w-full flex items-center justify-between p-3 rounded-xl border border-slate-100 hover:border-slate-300 hover:bg-slate-50/80 active:bg-slate-100 transition-all text-left group disabled:opacity-60"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold text-sm shadow-xs">
                      {acc.name.charAt(0)}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors">
                        {acc.name}
                      </div>
                      <div className="text-xs text-slate-500 font-mono">
                        {acc.email}
                      </div>
                    </div>
                  </div>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${acc.roleColor}`}>
                    {acc.role}
                  </span>
                </button>
              ))}
            </div>

            {/* Use Another Account Toggle */}
            <div className="border-t border-slate-100 pt-3">
              {!showCustomInput ? (
                <button
                  type="button"
                  onClick={() => setShowCustomInput(true)}
                  className="flex items-center gap-2 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors w-full p-2 rounded-lg hover:bg-indigo-50/50"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <span>Use another {ssoModalProvider} account</span>
                </button>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!customSsoEmail) return;
                    handleSelectSsoAccount(customSsoEmail, ssoModalProvider === "Google" ? "google" : "microsoft", customSsoName || undefined);
                  }}
                  className="space-y-3 p-3 bg-slate-50 rounded-xl border border-slate-200"
                >
                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                      {ssoModalProvider} Email Address
                    </label>
                    <input
                      type="email"
                      required
                      placeholder={ssoModalProvider === "Google" ? "yourname@gmail.com" : "yourname@outlook.com"}
                      value={customSsoEmail}
                      onChange={(e) => setCustomSsoEmail(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                      Full Name (optional)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. John Doe"
                      value={customSsoName}
                      onChange={(e) => setCustomSsoName(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setShowCustomInput(false)}
                      className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 font-medium"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={ssoSubmitting || !customSsoEmail}
                      className="px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs transition-colors disabled:opacity-50"
                    >
                      {ssoSubmitting ? "Signing In..." : "Continue"}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Disclaimer */}
            <p className="text-[10px] text-slate-400 text-center leading-relaxed">
              To continue, {ssoModalProvider} will share your verified name and email address with Skill2Job.
            </p>
          </div>
        </div>
      )}

    </div>
  );
}