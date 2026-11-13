/**
 * Shared display helpers for the HR oversight screens (Revised Phase 14).
 *
 * The status label and colour maps mirror the backend's
 * ``ApplicationStatus`` vocabulary. They are presentation only: nothing here
 * decides or infers hiring state, and an unknown status renders as itself
 * rather than being coerced into a known stage, so a new lifecycle status can
 * never be silently mislabelled to the reader.
 */

import type { HRTimelineEvent } from "../../api/hrOversight";
import {
  formatDateTime as utilsFormatDateTime,
  formatDate as utilsFormatDate,
  formatTime as utilsFormatTime,
  formatTimeAgo as utilsFormatTimeAgo,
} from "../../utils/dateTime";

export { utilsFormatDate as formatDate, utilsFormatTime as formatTime, utilsFormatTimeAgo as formatTimeAgo };

/** Human labels for the canonical application statuses. */
export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  applied: "Applied",
  under_review: "Under Review",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview Scheduled",
  interviewed: "Interviewed",
  selected: "Selected",
  offered: "Offered",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export function applicationStatusLabel(status: string): string {
  return APPLICATION_STATUS_LABELS[status] ?? status;
}

const STATUS_BADGE_CLASSES: Record<string, string> = {
  applied: "bg-gray-100 text-gray-700",
  under_review: "bg-yellow-100 text-yellow-700",
  shortlisted: "bg-blue-100 text-blue-700",
  interview_scheduled: "bg-indigo-100 text-indigo-700",
  interviewed: "bg-indigo-100 text-indigo-700",
  selected: "bg-emerald-100 text-emerald-700",
  offered: "bg-green-100 text-green-700",
  hired: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  withdrawn: "bg-gray-100 text-gray-600",
};

export function applicationStatusBadgeClass(status: string): string {
  return STATUS_BADGE_CLASSES[status] ?? "bg-gray-100 text-gray-700";
}

export function formatDateTime(value: string | null | undefined): string {
  return utilsFormatDateTime(value, "—");
}

/** Human label for a composed timeline event. */
export function timelineEventLabel(event: HRTimelineEvent): string {
  if (event.source === "status_history") {
    if (!event.from_status) {
      return `Application created (${applicationStatusLabel(event.to_status ?? "")})`;
    }
    return `${applicationStatusLabel(event.from_status)} → ${applicationStatusLabel(
      event.to_status ?? "",
    )}`;
  }
  if (event.source === "interview") {
    return `Interview ${String(event.to_status ?? event.event).replace(/^interview_/, "")}`;
  }
  if (event.source === "assessment") {
    return `Assessment ${String(event.to_status ?? event.event).replace(/^assessment_/, "")}`;
  }
  return event.event;
}

/**
 * Render a rate that may genuinely have no denominator.
 *
 * `null` means the backend had nothing to divide by -- no applications, or no
 * screening results -- which is a different fact from "0%". Printing 0.0 there
 * would claim every candidate failed; printing an em dash reports the absence
 * of data, which is what actually happened.
 */
export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

/** Human labels for the deterministic attention rules. */
export const ATTENTION_RULE_LABELS: Record<string, string> = {
  screening_failed: "Screening failed",
  stale_application: "Stalled application",
  low_advancement: "Low advancement",
  fairness_gap: "Selection parity gap",
};

export function attentionRuleLabel(rule: string): string {
  return ATTENTION_RULE_LABELS[rule] ?? rule;
}

const SEVERITY_BADGE_CLASSES: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  warning: "bg-amber-100 text-amber-700",
  info: "bg-blue-100 text-blue-700",
};

export function attentionSeverityBadgeClass(severity: string): string {
  return SEVERITY_BADGE_CLASSES[severity] ?? "bg-gray-100 text-gray-700";
}

/**
 * Describe what a threshold in force actually means.
 *
 * The attention screen echoes the thresholds the backend applied so the numbers
 * can explain themselves; this gives each one a readable label rather than
 * leaving a bare `stale_application_days: 7` on screen.
 */
export const ATTENTION_THRESHOLD_LABELS: Record<string, string> = {
  stale_application_days: "Stalled after (days)",
  min_advancement_rate: "Minimum advancement rate",
  min_pipeline_applications: "Minimum applications to rate",
  fairness_gap: "Selection parity ratio floor",
};

export function attentionThresholdLabel(key: string): string {
  return ATTENTION_THRESHOLD_LABELS[key] ?? key;
}
