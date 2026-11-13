import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useAuth } from "../hooks/useAuth";
import { getErrorMessage } from "../utils/error";
import { formatDate } from "../utils/dateTime";
import { getPasswordStrengthIssues, getPasswordStrengthLevel } from "../utils/validation";
import * as authApi from "../api/auth";

interface InvitationInfo {
  valid: boolean;
  email?: string;
  role?: string;
  organization_name?: string;
  expires_at?: string;
  status?: string;
  existing_user?: boolean;
}

const ROLE_LABELS: Record<string, string> = {
  hr_manager: "HR Manager",
  recruiter: "Recruiter",
  organization_admin: "Organization Admin",
};

function emailsMatch(a?: string, b?: string): boolean {
  return !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase();
}

export function InviteAccept() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [form, setForm] = useState({ full_name: "", password: "", confirm_password: "" });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    async function validate() {
      if (!token) {
        setInvitation({ valid: false });
        setIsLoading(false);
        return;
      }
      try {
        const info = await authApi.validateInvitation(token);
        setInvitation(info);
      } catch {
        setInvitation({ valid: false });
      } finally {
        setIsLoading(false);
      }
    }
    validate();
  }, [token]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setFormErrors((prev) => ({ ...prev, [e.target.name]: "" }));
  };

  const handleNewUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");
    if (!token) return;

    if (form.password !== form.confirm_password) {
      setFormErrors({ confirm_password: "Passwords do not match" });
      return;
    }

    const issues = getPasswordStrengthIssues(form.password);
    if (issues.length > 0) {
      setFormErrors({ password: `Password must contain ${issues.join(", ")}` });
      return;
    }

    setIsSubmitting(true);
    try {
      await authApi.acceptInvitation({
        token,
        full_name: form.full_name,
        password: form.password,
        confirm_password: form.confirm_password,
      });
      setSuccess(true);
    } catch (err) {
      setServerError(getErrorMessage(err, "Failed to accept invitation. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignedInAccept = async () => {
    if (!token) return;
    setServerError("");
    setIsSubmitting(true);
    try {
      await authApi.acceptSignedInInvitation(token);
      setSuccess(true);
    } catch (err) {
      setServerError(getErrorMessage(err, "Failed to accept invitation. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (success) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />

        <div className="relative w-full max-w-md space-y-6 text-center animate-scale-in">
          <div
            className="rounded-2xl border border-emerald-200/80 bg-emerald-50/80 p-6 shadow-xs"
            role="status"
            aria-live="polite"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600">
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-emerald-800">Invitation Accepted!</h2>
            <p className="mt-2 text-sm text-emerald-700">
              You are now a member of {invitation?.organization_name}.
            </p>
            {invitation?.role && (
              <p className="mt-2 text-sm text-emerald-700">
                You've been onboarded as{" "}
                <strong>{ROLE_LABELS[invitation.role] || invitation.role}</strong>.
              </p>
            )}
          </div>
          {!isAuthenticated && (
            <Link to="/login" className="inline-block">
              <Button>Go to Sign In</Button>
            </Link>
          )}
          {isAuthenticated && (
            <Button onClick={() => navigate("/dashboard")}>Go to Dashboard</Button>
          )}
        </div>
      </div>
    );
  }

  if (!invitation?.valid) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />

        <div className="relative w-full max-w-md space-y-6 text-center animate-scale-in">
          <div
            className="rounded-2xl border border-red-200/80 bg-red-50/80 p-6 shadow-xs"
            role="alert"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-red-600">
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-red-800">Invalid Invitation</h2>
            <p className="mt-2 text-sm text-red-700">
              This invitation link is invalid, expired, revoked, or has already been used.
            </p>
          </div>
          <Link to="/login" className="inline-block">
            <Button variant="secondary">Go to Sign In</Button>
          </Link>
        </div>
      </div>
    );
  }

  const isExistingUserFlow = invitation.existing_user === true;
  const signedInEmailMatches = isAuthenticated && emailsMatch(user?.email, invitation.email);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400 to-primary-400 opacity-15 blur-3xl animate-float [animation-delay:2.5s]" aria-hidden="true" />

      <div className="relative z-10 w-full max-w-md space-y-6 animate-entrance">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-gradient shadow-glow-sm">
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
            </svg>
          </div>
          <h1 className="mt-4 font-display text-2xl font-bold tracking-tight text-gray-900">Accept Invitation</h1>
          <div className="panel-brand mt-4 p-4 text-left">
            <p className="text-sm text-blue-800">
              You've been invited to join <strong>{invitation.organization_name}</strong> as{" "}
              <strong>{ROLE_LABELS[invitation.role || ""] || invitation.role}</strong>
            </p>
            <p className="mt-1 text-xs text-blue-600">
              Invited email: {invitation.email}
            </p>
            {invitation.expires_at && (
              <p className="mt-1 text-xs text-blue-600">
                Expires: {formatDate(invitation.expires_at)}
              </p>
            )}
          </div>
        </div>

        {serverError && (
          <div className="error-banner" role="alert">
            {serverError}
          </div>
        )}

        {isExistingUserFlow ? (
          /* ── Existing-user flow ─────────────────────────────── */
          <div className="space-y-4">
            <div
              className="rounded-xl border border-amber-200/80 bg-amber-50/80 p-4 text-sm text-amber-800 shadow-xs"
              role="status"
            >
              An account already exists for this email. Sign in with{" "}
              <strong>{invitation.email}</strong> to accept this invitation.
            </div>

            {!isAuthenticated && (
              <Link
                to={`/login?redirect=${encodeURIComponent(`/invite/${token}`)}`}
                className="block"
              >
                <Button className="w-full">Sign In to Accept Invitation</Button>
              </Link>
            )}

            {isAuthenticated && !signedInEmailMatches && (
              <div className="error-banner" role="alert">
                This invitation was sent to <strong>{invitation.email}</strong>, but you are
                signed in as <strong>{user?.email}</strong>. Please sign in with the invited
                email address.
              </div>
            )}

            {signedInEmailMatches && (
              <Button
                onClick={handleSignedInAccept}
                isLoading={isSubmitting}
                disabled={isSubmitting}
                className="w-full"
              >
                Accept Invitation as {user?.email}
              </Button>
            )}
          </div>
        ) : (
          /* ── New-user flow ──────────────────────────────────── */
          <form onSubmit={handleNewUserSubmit} className="card space-y-4 p-7">
            <p className="text-center text-sm font-medium text-gray-600">Create your account</p>

            <Input
              label="Email"
              type="email"
              name="email"
              value={invitation.email || ""}
              onChange={() => {}}
              error={undefined}
              placeholder={invitation.email}
              disabled
            />

            <Input
              label="Full Name"
              type="text"
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              error={formErrors.full_name}
              placeholder="Your full name"
              required
            />

            <Input
              label="Password"
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              error={formErrors.password}
              placeholder="At least 8 characters"
              required
            />

            {form.password.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex gap-1">
                  {(["weak", "fair", "strong"] as const).map((level) => {
                    const current = getPasswordStrengthLevel(form.password);
                    const levels = ["weak", "fair", "strong"];
                    const active = levels.indexOf(current) >= levels.indexOf(level);
                    return (
                      <div
                        key={level}
                        className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                          active
                            ? level === "weak" ? "bg-red-500" : level === "fair" ? "bg-amber-400" : "bg-emerald-500"
                            : "bg-gray-200"
                        }`}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            <Input
              label="Confirm Password"
              type="password"
              name="confirm_password"
              value={form.confirm_password}
              onChange={handleChange}
              error={formErrors.confirm_password}
              placeholder="Re-enter your password"
              required
            />

            <Button
              type="submit"
              isLoading={isSubmitting}
              disabled={isSubmitting}
              className="w-full"
            >
              Accept Invitation &amp; Create Account
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
