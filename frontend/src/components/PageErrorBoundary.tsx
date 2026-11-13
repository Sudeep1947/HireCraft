import { ErrorBoundary } from "./ErrorBoundary";

interface PageErrorBoundaryProps {
  children: React.ReactNode;
  pageName: string;
}

/**
 * Page-level error boundary. Catches errors in a single page/route
 * without crashing the entire application.
 */
export function PageErrorBoundary({ children, pageName }: PageErrorBoundaryProps) {
  return (
    <ErrorBoundary
      pageName={pageName}
      fallback={
        <div className="flex min-h-[500px] items-center justify-center p-6">
          <div className="card w-full max-w-md animate-scale-in p-8 text-center">
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-50 to-orange-100 shadow-soft">
              <svg
                className="h-7 w-7 text-amber-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.8}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m0 3.75h.008v.008H12v-.008zM21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h2 className="font-display text-xl font-bold tracking-tight text-gray-900">
              Page Error
            </h2>
            <p className="mt-2 text-sm text-gray-500">
              This page encountered an error and could not be displayed.
            </p>
            <p className="mt-2 text-xs font-medium text-gray-400">{pageName}</p>
            <div className="mt-6 flex justify-center gap-3">
              <button
                onClick={() => window.location.reload()}
                className="btn-primary btn-md"
              >
                Reload page
              </button>
              <a href="/" className="btn-secondary btn-md">
                Go to dashboard
              </a>
            </div>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}
