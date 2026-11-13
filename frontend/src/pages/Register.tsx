import { Navigate, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useAuth } from "../hooks/useAuth";
import { getErrorMessage } from "../utils/error";
import { validateRegisterForm, getPasswordStrengthIssues, getPasswordStrengthLevel } from "../utils/validation";
import { getDashboardPath } from "../utils/roleRouting";
import { useState } from "react";



export function Register() {
  const navigate = useNavigate();
  const { register, isAuthenticated, user } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm_password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  if (isAuthenticated) {
    return <Navigate to={getDashboardPath(user?.roles || [])} replace />;
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setErrors((prev) => ({ ...prev, [e.target.name]: "" }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");

    if (form.password !== form.confirm_password) {
      setErrors({ confirm_password: "Passwords do not match" });
      return;
    }

    const validationErrors = validateRegisterForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsLoading(true);
    try {
      await register({ full_name: form.full_name, email: form.email, password: form.password });
      navigate("/login");
    } catch (err) {
      setServerError(getErrorMessage(err, "Registration failed. Please try again."));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
      {/* Aurora backdrop */}
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(85,87,230,0.10),transparent)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-gradient opacity-20 blur-3xl animate-float" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-gradient-to-tr from-violet-400 to-primary-400 opacity-20 blur-3xl animate-float [animation-delay:2.5s]" aria-hidden="true" />

      <div className="relative z-10 w-full max-w-md space-y-6 animate-entrance">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-gradient shadow-glow">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
            </svg>
          </div>
          <h1 className="mt-5 font-display text-2xl font-bold tracking-tight">
            <span className="text-gradient">Create candidate account</span>
          </h1>
          <p className="mt-1.5 text-sm text-gray-500">
            Register to explore job opportunities
          </p>
          <p className="mt-2 text-xs text-gray-400">
            Looking to join a hiring team? You'll need an invitation from your organization admin.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4 p-7">
          {serverError && (
            <div className="error-banner" role="alert">
              {serverError}
            </div>
          )}

          <Input
            label="Full Name"
            type="text"
            name="full_name"
            value={form.full_name}
            onChange={handleChange}
            error={errors.full_name}
            placeholder="John Doe"
          />

          <Input
            label="Email"
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            error={errors.email}
            placeholder="you@example.com"
          />

          <Input
            label="Password"
            type="password"
            name="password"
            value={form.password}
            onChange={handleChange}
            error={errors.password}
            placeholder="At least 8 characters"
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
                          ? level === "weak"
                            ? "bg-red-500"
                            : level === "fair"
                              ? "bg-amber-400"
                              : "bg-emerald-500"
                          : "bg-gray-200"
                      }`}
                    />
                  );
                })}
              </div>
              <p className="text-xs text-gray-500">
                {getPasswordStrengthIssues(form.password).length === 0
                  ? "Strong password"
                  : `Needs ${getPasswordStrengthIssues(form.password).join(", ")}`}
              </p>
            </div>
          )}

          <Input
            label="Confirm Password"
            type="password"
            name="confirm_password"
            value={form.confirm_password}
            onChange={handleChange}
            error={errors.confirm_password}
            placeholder="Re-enter your password"
          />

          <Button type="submit" isLoading={isLoading} className="w-full">
            Create Candidate Account
          </Button>
        </form>

        <p className="text-center text-sm text-gray-500">
          Already have an account?{" "}
          <a href="/login" className="font-semibold text-primary-600 transition-colors hover:text-primary-700">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}
