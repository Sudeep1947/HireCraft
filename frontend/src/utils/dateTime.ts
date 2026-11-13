/**
 * Date and Time utilities for Skill2Job / AI Hiring Copilot.
 * 
 * Handles timezone parsing safely:
 * - SQLite and backend APIs often return UTC datetimes without the trailing 'Z'
 *   (e.g., '2026-10-30T13:00:00' or '2026-10-30 13:00:00.123456').
 * - Browsers parse date strings without a timezone as LOCAL time, causing an
 *   unintended offset (e.g., 5.5 hours behind in IST / UTC+05:30).
 * - `parseUTCDate` normalizes any naive UTC string into an unambiguous UTC ISO string
 *   before parsing, ensuring accurate local time representation everywhere.
 */

export function parseUTCDate(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === "number") {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  let str = String(value).trim();
  if (!str) return null;

  // Normalise SQLite format: '2026-10-30 13:00:00' -> '2026-10-30T13:00:00'
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(str)) {
    str = str.replace(" ", "T");
  }

  // If ISO string without timezone indicator (Z or +HH:mm / -HH:mm), append Z so browser treats as UTC
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(str)) {
    str += "Z";
  }

  const parsed = new Date(str);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Format a datetime in the user's local timezone.
 * Example: 'Oct 30, 2026, 6:45 PM'
 */
export function formatDateTime(
  value: string | number | Date | null | undefined,
  fallback: string = "—",
  options?: Intl.DateTimeFormatOptions,
): string {
  const d = parseUTCDate(value);
  if (!d) return fallback;

  const defaultOptions: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  };

  try {
    return d.toLocaleString(undefined, options || defaultOptions);
  } catch {
    return fallback;
  }
}

/**
 * Format a date only in the user's local timezone.
 * Example: 'Oct 30, 2026'
 */
export function formatDate(
  value: string | number | Date | null | undefined,
  fallback: string = "—",
  options?: Intl.DateTimeFormatOptions,
): string {
  const d = parseUTCDate(value);
  if (!d) return fallback;

  const defaultOptions: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    year: "numeric",
  };

  try {
    return d.toLocaleDateString(undefined, options || defaultOptions);
  } catch {
    return fallback;
  }
}

/**
 * Format a time only in the user's local timezone (12-hour AM/PM).
 * Example: '6:45 PM'
 */
export function formatTime(
  value: string | number | Date | null | undefined,
  fallback: string = "—",
  options?: Intl.DateTimeFormatOptions,
): string {
  const d = parseUTCDate(value);
  if (!d) return fallback;

  const defaultOptions: Intl.DateTimeFormatOptions = {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  };

  try {
    return d.toLocaleTimeString(undefined, options || defaultOptions);
  } catch {
    return fallback;
  }
}

/**
 * Format relative time (e.g., 'Just now', '5m ago', '2h ago', 'Yesterday').
 */
export function formatTimeAgo(value: string | number | Date | null | undefined, fallback: string = "—"): string {
  const d = parseUTCDate(value);
  if (!d) return fallback;

  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0 && diffMs > -60000) {
    return "Just now";
  }

  const diffSec = Math.floor(Math.abs(diffMs) / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMs < 0) {
    // In future
    if (diffMin < 60) return `in ${Math.max(1, diffMin)}m`;
    if (diffHours < 24) return `in ${diffHours}h`;
    return `in ${diffDays}d`;
  }

  if (diffSec < 60) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;

  return formatDate(d, fallback);
}
