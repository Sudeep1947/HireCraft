import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { Notification } from "../../types/candidate";

/**
 * Where a notification's "View" action should take the candidate, or null when
 * the type has no destination.
 *
 * The notification row carries no link, so the destination is derived from the
 * type. Assessment events land on the assessment list, which is the only place
 * the candidate can act on them; nothing here deep-links to an attempt, so a
 * stale notification cannot navigate to an attempt that is not the candidate's.
 */
function notificationTarget(notification: Notification): string | null {
  switch (notification.notification_type) {
    case "assessment_assigned":
    case "assessment_completed":
      return "/candidate/assessments";
    case "interview_scheduled":
    case "interview_rescheduled":
    case "interview_cancelled":
    case "interview_completed":
      return "/candidate/applications";
    default:
      return null;
  }
}

export function CandidateNotifications() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try { setNotifications(await candidateApi.listNotifications()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleMarkRead = async (id: string) => {
    await candidateApi.markNotificationRead(id);
    await fetch();
  };

  const handleMarkAllRead = async () => {
    await candidateApi.markAllNotificationsRead();
    await fetch();
  };

  const handleDelete = async (id: string) => {
    await candidateApi.deleteNotification(id);
    await fetch();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl animate-fade-up space-y-6">
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">Stay updated with your activity</p>
        </div>
        {notifications.length > 0 && (
          <Button variant="ghost" size="sm" onClick={handleMarkAllRead}>
            Mark all read
          </Button>
        )}
      </div>

      <div className="space-y-3">
        {notifications.length === 0 && (
          <div className="empty-state card">
            <p className="text-sm text-gray-400">No notifications yet</p>
          </div>
        )}
        {notifications.map((n) => (
          <div
            key={n.id}
            className={`card flex items-start justify-between gap-4 transition-shadow hover:shadow-md ${
              n.is_read ? "" : "border-indigo-200 bg-indigo-50/40"
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-900">{n.title}</p>
                {!n.is_read && (
                  <span className="h-2 w-2 rounded-full bg-indigo-500" aria-label="Unread" />
                )}
              </div>
              <p className="mt-1 text-sm text-gray-500">{n.message}</p>
              <p className="mt-1 text-xs text-gray-400">
                {new Date(n.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex shrink-0 gap-1">
              {notificationTarget(n) ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate(notificationTarget(n) as string)}
                >
                  View
                </Button>
              ) : null}
              {!n.is_read && (
                <Button variant="ghost" size="sm" onClick={() => handleMarkRead(n.id)}>
                  Read
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => handleDelete(n.id)}>
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
