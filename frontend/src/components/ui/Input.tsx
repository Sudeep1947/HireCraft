import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = "", id, ...props }: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="field-label">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`block w-full rounded-xl border bg-white/80 px-3.5 py-2.5 text-sm text-ink shadow-soft transition-all duration-200 placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:border-primary-400 ${
          error
            ? "border-rose-300 focus:border-rose-400 focus:ring-rose-400/40"
            : "border-slate-200 focus:ring-primary-400/40"
        } ${className}`}
        {...props}
      />
      {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
    </div>
  );
}
