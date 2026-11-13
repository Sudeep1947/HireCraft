import { useEffect, useState } from "react";
import {
  X,
  Clock,
  CheckCircle2,
  FileText,
  ShieldCheck,
  UserCheck,
  AlertCircle,
  Sparkles,
} from "lucide-react";

import { postHiringApi } from "../../api/postHiring";
import type { PostHiringTimelineEvent } from "../../types/postHiring";
import { formatDateTime, formatTimeAgo } from "../../utils/dateTime";
import { LoadingSpinner } from "../ui/LoadingSpinner";

interface PostHiringTimelineModalProps {
  applicationId: string | null;
  candidateName?: string;
  jobTitle?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function PostHiringTimelineModal({
  applicationId,
  candidateName,
  jobTitle,
  isOpen,
  onClose,
}: PostHiringTimelineModalProps) {
  const [events, setEvents] = useState<PostHiringTimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !applicationId) {
      setEvents([]);
      return;
    }

    setLoading(true);
    setError(null);
    postHiringApi
      .getTimeline(applicationId)
      .then((data) => {
        setEvents(data);
      })
      .catch((err) => {
        console.error("Failed to load timeline events", err);
        setError("Unable to load activity timeline. Please try again.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [isOpen, applicationId]);

  if (!isOpen) return null;

  const getEventIcon = (eventType: string) => {
    const type = eventType.toLowerCase();
    if (type.includes("offer")) {
      return <FileText className="h-4 w-4 text-blue-600" />;
    }
    if (type.includes("document") || type.includes("doc")) {
      return <ShieldCheck className="h-4 w-4 text-emerald-600" />;
    }
    if (type.includes("onboarding") || type.includes("task")) {
      return <CheckCircle2 className="h-4 w-4 text-indigo-600" />;
    }
    if (type.includes("employee") || type.includes("activat")) {
      return <UserCheck className="h-4 w-4 text-violet-600" />;
    }
    return <Clock className="h-4 w-4 text-slate-500" />;
  };

  const getEventBadgeClass = (eventType: string) => {
    const type = eventType.toLowerCase();
    if (type.includes("accepted") || type.includes("verified") || type.includes("active")) {
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
    if (type.includes("declined") || type.includes("rejected") || type.includes("withdrawn")) {
      return "bg-rose-50 text-rose-700 border-rose-200";
    }
    if (type.includes("sent") || type.includes("submitted")) {
      return "bg-blue-50 text-blue-700 border-blue-200";
    }
    return "bg-slate-100 text-slate-700 border-slate-200";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
      <div className="relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl bg-white shadow-2xl border border-slate-100 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white shadow-xs backdrop-blur-xs">
              <Sparkles className="h-5 w-5 text-blue-300" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white tracking-tight">
                Post-Hiring Activity Timeline
              </h2>
              <p className="text-xs text-slate-300">
                {candidateName ? <span className="font-medium text-white">{candidateName}</span> : "Candidate"}
                {jobTitle && <span> &bull; {jobTitle}</span>}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="py-16 flex flex-col items-center justify-center">
              <LoadingSpinner size="lg" />
              <p className="mt-3 text-sm text-slate-500 font-medium">Fetching real milestone timestamps...</p>
            </div>
          )}

          {error && !loading && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800">
              <AlertCircle className="h-5 w-5 shrink-0 text-rose-600 mt-0.5" />
              <div>
                <p className="text-sm font-semibold">Error Loading Timeline</p>
                <p className="text-xs text-rose-600 mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && events.length === 0 && (
            <div className="py-16 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 mb-3">
                <Clock className="h-6 w-6" />
              </div>
              <p className="text-sm font-semibold text-slate-800">No Post-Hiring Activity Logged Yet</p>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Once an offer is created, accepted, or documents are uploaded, each verified step will appear here in chronological order.
              </p>
            </div>
          )}

          {!loading && !error && events.length > 0 && (
            <div className="relative pl-6 before:absolute before:left-[17px] before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              <div className="space-y-6">
                {events.map((evt, idx) => (
                  <div key={idx} className="relative group">
                    {/* Step Node Icon */}
                    <div className="absolute -left-[30px] top-0 flex h-7 w-7 items-center justify-center rounded-full bg-white border-2 border-slate-300 shadow-xs group-hover:border-blue-500 transition-colors">
                      {getEventIcon(evt.event_type)}
                    </div>

                    {/* Step Card */}
                    <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4 transition-all hover:bg-white hover:shadow-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-semibold text-slate-900">{evt.title}</h4>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border ${getEventBadgeClass(
                              evt.event_type
                            )}`}
                          >
                            {evt.event_type.replace(/_/g, " ").toUpperCase()}
                          </span>
                        </div>
                        <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                          <Clock className="h-3 w-3 text-slate-400" />
                          {formatDateTime(evt.timestamp)} ({formatTimeAgo(evt.timestamp)})
                        </span>
                      </div>

                      <p className="text-xs text-slate-600 leading-relaxed">{evt.description}</p>

                      {/* Actor Information */}
                      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                        {evt.actor_name ? (
                          <span>
                            Triggered by <strong className="text-slate-700">{evt.actor_name}</strong>
                            {evt.actor_role && (
                              <span className="text-slate-400 ml-1">({evt.actor_role})</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">System Event</span>
                        )}

                        {evt.action_link && (
                          <span className="font-mono text-[10px] text-indigo-600 bg-indigo-50/70 px-1.5 py-0.5 rounded">
                            Actionable
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {events.length} event{events.length === 1 ? "" : "s"} recorded
          </span>
          <button
            onClick={onClose}
            className="rounded-lg bg-white border border-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
