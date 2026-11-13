import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

export function ActivateAccount() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [form, setForm] = useState({ password: "", confirm_password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverMessage, setServerMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setErrors((prev) => ({ ...prev, [e.target.name]: "" }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!form.password) newErrors.password = "Password is required";
    else if (form.password.length < 8) newErrors.password = "Password must be at least 8 characters";
    if (form.password !== form.confirm_password) newErrors.confirm_password = "Passwords do not match";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerMessage("");
    if (!validate()) return;
    if (!token) {
      setServerMessage("Invalid activation link.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch("/api/v1/access-requests/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password: form.password, confirm_password: form.confirm_password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("error");
        setServerMessage(data.error?.message || data.detail || "Activation failed");
      } else {
        setStatus("success");
        setServerMessage(data.message);
      }
    } catch {
      setStatus("error");
      setServerMessage("Network error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />

        <div className="card relative w-full max-w-md p-8 text-center animate-scale-in">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600 ring-1 ring-inset ring-red-100">
            <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
          </div>
          <h2 className="page-title text-xl sm:text-2xl">Invalid Link</h2>
          <p className="mt-2 text-gray-600">This activation link is invalid or missing a token.</p>
          <div className="divider my-6" aria-hidden="true" />
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-600 transition-colors hover:text-primary-700"
          >
            <span aria-hidden="true">&larr;</span>
            Back to Login
          </Link>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />

        <div className="card relative w-full max-w-md p-8 text-center animate-scale-in">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100">
            <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="page-title text-xl sm:text-2xl">Account Activated</h2>
          <p className="mt-2 text-gray-600">{serverMessage}</p>
          <div className="divider my-6" aria-hidden="true" />
          <Link to="/login" className="btn-primary btn-md">
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400 to-primary-400 opacity-15 blur-3xl animate-float [animation-delay:2.5s]" aria-hidden="true" />

      <div className="card relative w-full max-w-md p-8 animate-entrance">
        <div className="mb-6 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-gradient shadow-glow-sm">
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <h1 className="mt-4 font-display text-2xl font-bold tracking-tight text-gray-900">Activate Your Account</h1>
          <p className="mt-1 text-sm text-gray-500">Set your password to complete registration</p>
        </div>

        {serverMessage && (
          <div className="error-banner mb-4" role="alert">
            {serverMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="field-label">Password</label>
            <Input
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="Min. 8 characters"
              error={errors.password}
            />
          </div>

          <div>
            <label className="field-label">Confirm Password</label>
            <Input
              name="confirm_password"
              type="password"
              value={form.confirm_password}
              onChange={handleChange}
              placeholder="Re-enter password"
              error={errors.confirm_password}
            />
          </div>

          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? "Activating..." : "Activate Account"}
          </Button>
        </form>
      </div>
    </div>
  );
}
