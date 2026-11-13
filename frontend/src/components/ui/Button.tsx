import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  children: ReactNode;
}

const variantClasses = {
  primary:
    "bg-brand-gradient text-white shadow-soft hover:brightness-110 hover:shadow-glow focus-visible:ring-primary-400",
  secondary:
    "bg-primary-50 text-primary-700 ring-1 ring-primary-200/70 hover:bg-primary-100 focus-visible:ring-primary-400",
  danger:
    "bg-gradient-to-br from-rose-500 to-red-600 text-white shadow-soft hover:brightness-110 focus-visible:ring-red-400",
  ghost:
    "bg-transparent text-ink-muted hover:bg-primary-50 hover:text-primary-700 focus-visible:ring-primary-300",
  outline:
    "bg-white/80 text-ink-muted border border-slate-200 backdrop-blur-sm hover:border-primary-300 hover:text-primary-700 hover:shadow-soft focus-visible:ring-primary-300",
};

const sizeClasses = {
  sm: "px-3 py-1.5 text-sm rounded-lg",
  md: "px-4 py-2 text-sm rounded-xl",
  lg: "px-6 py-3 text-base rounded-xl",
};

export function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  children,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}
