import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

export function RequestAccess() {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    organization_slug: "",
    requested_role: "" as "" | "hr_manager" | "recruiter",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverMessage, setServerMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setErrors((prev) => ({ ...prev, [e.target.name]: "" }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!form.full_name.trim()) newErrors.full_name = "Full name is required";
    if (!form.email.trim()) newErrors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) newErrors.email = "Invalid email address";
    if (!form.organization_slug.trim()) newErrors.organization_slug = "Organization name is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerMessage("");
    if (!validate()) return;

    setIsLoading(true);
    try {
      const res = await fetch("/api/v1/access-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          organization_slug: form.organization_slug.trim(),
          requested_role: form.requested_role || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setServerMessage(data.error?.message || data.detail || "Failed to submit request");
      } else {
        setSubmitted(true);
        setServerMessage(data.message);
      }
    } catch {
      setServerMessage("Network error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
          aria-hidden="true"
        />
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-gradient opacity-15 blur-3xl animate-float" aria-hidden="true" />

        <div className="card relative w-full max-w-md p-8 text-center animate-scale-in">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100">
            <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="page-title text-xl sm:text-2xl">Check Your Email</h2>
          <p className="mt-2 text-gray-600">{serverMessage}</p>
          <p className="mt-4 text-sm text-gray-500">
            We sent a verification link to <strong className="font-semibold text-gray-700">{form.email}</strong>.
            Please check your inbox and verify your company email to continue.
          </p>
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
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
            </svg>
          </div>
          <h1 className="mt-4 font-display text-2xl font-bold tracking-tight text-gray-900">Request Access</h1>
          <p className="mt-1 text-sm text-gray-500">Join your organization as an HR or Recruiter</p>
        </div>

        {serverMessage && (
          <div className="error-banner mb-4" role="alert">
            {serverMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="field-label">Full Name</label>
            <Input
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              placeholder="Jane Smith"
              error={errors.full_name}
            />
          </div>

          <div>
            <label className="field-label">Work Email</label>
            <Input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="jane@company.com"
              error={errors.email}
            />
          </div>

          <div>
            <label className="field-label">Organization</label>
            <Input
              name="organization_slug"
              value={form.organization_slug}
              onChange={handleChange}
              placeholder="Company name, slug, or domain"
              error={errors.organization_slug}
            />
          </div>

          <div>
            <label className="field-label">Requested Role (optional)</label>
            <select
              name="requested_role"
              value={form.requested_role}
              onChange={handleChange}
              className="field"
            >
              <option value="">No preference</option>
              <option value="hr_manager">HR Manager</option>
              <option value="recruiter">Recruiter</option>
            </select>
          </div>

          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? "Submitting..." : "Request Access"}
          </Button>
        </form>

        <div className="divider my-6" aria-hidden="true" />

        <p className="text-center text-sm text-gray-500">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-primary-600 transition-colors hover:text-primary-700">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
