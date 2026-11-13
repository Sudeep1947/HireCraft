/**
 * Identifier display for the hiring workflow's canonical UUIDs.
 *
 * The recruiter used to have to go and find a candidate's UUID -- in the
 * database, in a URL, in a log -- before the interview form would accept it.
 * This component exists so an identifier is never shown as an unexplained
 * string, and never has to be retyped: the label says what the identifier
 * *identifies*, and one click copies it in full.
 *
 * Three decisions are load-bearing:
 *
 * 1. **Truncation is display-only.** The rendered text is shortened so a UUID
 *    does not dominate a layout, but the `title`, the `aria-label` and -- most
 *    importantly -- the value written to the clipboard are always the complete
 *    identifier. A copy that silently dropped the last characters would produce
 *    a UUID that 404s.
 *
 * 2. **Confirmation is local and polite.** "Copied" renders inline next to the
 *    button, announced through an `aria-live="polite"` region, and resets after
 *    a moment. No toast, no modal: a toast would interrupt a recruiter who is
 *    copying three identifiers in a row.
 *
 * 3. **The label is not optional.** A UUID is meaningless without knowing
 *    whether it identifies the candidate, the application, the job or the
 *    interview, so `label` is required. The full value is also exposed to
 *    assistive technology through the title, because a sighted user can hover
 *    to read it and a screen-reader user should not have to.
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";

/** How much of the identifier to show before eliding. */
const VISIBLE_PREFIX = 13;

export type IdentifierSize = "sm" | "md";

export interface IdentifierFieldProps {
  /**
   * What this identifier identifies, e.g. "Candidate ID". Required: a bare
   * UUID is not self-describing, and the whole point of the component is to
   * stop those from reaching the screen unlabelled.
   */
  label: string;
  /** The complete identifier. Rendered truncated; copied in full. */
  value: string | null | undefined;
  /** Shows the copy button. Off for identifiers a role should not copy out. */
  copyable?: boolean;
  /** Optional clarification under the label, e.g. "Identifies the person". */
  hint?: string;
  size?: IdentifierSize;
  /**
   * Force the value on screen in full. Use where a short reference is
   * expected to be readable (never for a 36-character UUID).
   */
  fullWidth?: boolean;
  className?: string;
}

function abbreviate(value: string): string {
  if (value.length <= VISIBLE_PREFIX + 4) return value;
  return `${value.slice(0, VISIBLE_PREFIX)}…`;
}

/**
 * A labelled, copyable identifier.
 *
 * Renders nothing when there is no value, so an optional identifier (an
 * interview with no application) does not render a "None" label that reads as
 * a real value.
 */
export function IdentifierField({
  label,
  value,
  copyable = false,
  hint,
  size = "md",
  fullWidth = false,
  className = "",
}: IdentifierFieldProps) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fieldId = useId();

  // Clear the timer on unmount so a pending reset cannot fire into a component
  // that is gone -- React would warn and the state update would be wasted.
  useEffect(
    () => () => {
      if (resetTimer.current) clearTimeout(resetTimer.current);
    },
    [],
  );

  const copy = useCallback(async () => {
    if (!value) return;
    setCopyFailed(false);
    try {
      // Fall back for insecure origins and older engines: the Clipboard API is
      // unavailable there, and a copy button that silently does nothing is
      // worse than one that degrades.
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const area = document.createElement("textarea");
        area.value = value;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
      }
      setCopied(true);
    } catch {
      // Report the failure on the button instead of claiming a copy happened.
      setCopyFailed(true);
    }
    if (resetTimer.current) clearTimeout(resetTimer.current);
    resetTimer.current = setTimeout(() => {
      setCopied(false);
      setCopyFailed(false);
    }, 2000);
  }, [value]);

  if (!value) return null;

  const textSize = size === "sm" ? "text-xs" : "text-sm";
  const shown = fullWidth ? value : abbreviate(value);

  return (
    <div className={`min-w-0 ${className}`} data-testid={`identifier-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>
      <label
        htmlFor={`${fieldId}-value`}
        className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-subtle"
      >
        {label}
      </label>
      <div className="mt-1 flex min-w-0 items-center gap-2">
        <code
          id={`${fieldId}-value`}
          title={value}
          className={`min-w-0 truncate rounded-md bg-gray-100/70 px-1.5 py-0.5 font-mono text-primary-900 ${textSize}`}
        >
          {shown}
        </code>
        {copyable ? (
          <button
            type="button"
            onClick={() => void copy()}
            aria-label={`Copy ${label.toLowerCase()}`}
            title={`Copy ${label.toLowerCase()}`}
            className={`shrink-0 rounded-md border px-2 py-0.5 text-[11px] font-semibold transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/60 focus-visible:ring-offset-1 ${
              copyFailed
                ? "border-red-200 bg-red-50 text-red-600"
                : copied
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-gray-200 bg-white text-gray-500 shadow-xs hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700"
            }`}
          >
            {copied ? "Copied" : copyFailed ? "Copy failed" : "Copy"}
          </button>
        ) : null}
      </div>
      {/* The confirmation is announced, not just drawn, and does not steal focus. */}
      <span
        role="status"
        aria-live="polite"
        className="sr-only"
        data-testid={`identifier-status-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
      >
        {copied ? `${label} copied to clipboard` : ""}
        {copyFailed ? `Could not copy ${label.toLowerCase()}` : ""}
      </span>
      {hint ? <p className="mt-0.5 text-xs text-ink-subtle">{hint}</p> : null}
    </div>
  );
}

export interface IdentifierGridItem {
  label: string;
  value: string | null | undefined;
  hint?: string;
  copyable?: boolean;
}

/**
 * A labelled group of identifiers.
 *
 * Exists so every surface presents them the same way and so the relationship
 * between the four identifiers stays obvious: candidate, application, job and
 * interview are four different things, and the grid keeps them side by side
 * rather than scattered through a page.
 */
export function IdentifierGrid({
  items,
  columns = 2,
  className = "",
}: {
  items: IdentifierGridItem[];
  columns?: 1 | 2 | 3 | 4;
  className?: string;
}) {
  const visible = items.filter((item) => Boolean(item.value));
  if (visible.length === 0) return null;
  const gridCols = {
    1: "sm:grid-cols-1",
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-2 lg:grid-cols-3",
    4: "sm:grid-cols-2 lg:grid-cols-4",
  }[columns];
  return (
    <div className={`grid grid-cols-1 gap-x-6 gap-y-3 ${gridCols} ${className}`}>
      {visible.map((item) => (
        <IdentifierField
          key={item.label}
          label={item.label}
          value={item.value}
          hint={item.hint}
          copyable={item.copyable ?? true}
        />
      ))}
    </div>
  );
}

export default IdentifierField;
