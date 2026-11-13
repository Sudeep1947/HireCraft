import { useCallback, useEffect, useState } from "react";
import { Button } from "../../components/ui/Button";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { notificationsApi } from "../../api/notifications";
import type { Notification } from "../../api/notifications";

export function RecruiterNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = useCallback(async () => {
    try {
      setNotifications(await notificationsApi.list());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkRead = async (id: string) => {
    await notificationsApi.markRead(id);
    await fetchNotifications();
  };

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead();
    await fetchNotifications();
  };

  const handleDelete = async (id: string) => {
    await notificationsApi.delete(id);
    await fetchNotifications();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">Stay updated with applications and activity</p>
        </div>
        {notifications.length > 0 && (
          <Button variant="ghost" size="sm" onClick={handleMarkAllRead}>
            Mark all read
          </Button>
        )}
      </div>

      <div className="space-y-2">
        {notifications.length === 0 && (
          <div className="empty-state">
            <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
            <p className="text-sm text-gray-500">No notifications yet</p>
          </div>
        )}
        {notifications.map((n) => (
          <div
            key={n.id}
            className={`card p-4 flex items-start justify-between gap-4 ${
              n.is_read ? "" : "border-primary-200 bg-primary-50/30"
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="font-medium text-sm text-gray-900">{n.title}</p>
                {!n.is_read && (
                  <span className="h-2 w-2 rounded-full bg-primary-500" aria-label="Unread" />
                )}
              </div>
              <p className="text-sm text-gray-500 mt-1">{n.message}</p>
              <p className="text-xs text-gray-400 mt-1">
                {new Date(n.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex gap-1">
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
