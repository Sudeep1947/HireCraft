import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  CheckCircle2,
  FileText,
  ShieldCheck,
  UserCheck,
  Clock,
  Trash2,
  X,
  ExternalLink,
  Sparkles,
} from "lucide-react";

import { notificationsApi } from "../../api/notifications";
import type { Notification } from "../../api/notifications";
import { formatTimeAgo } from "../../utils/dateTime";
import { useToast } from "../../contexts/ToastContext";

interface NotificationCenterProps {
  isOpen: boolean;
  onClose: () => void;
  onUnreadCountChange?: (count: number) => void;
}

export function NotificationCenter({
  isOpen,
  onClose,
  onUnreadCountChange,
}: NotificationCenterProps) {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<"all" | "offers" | "documents" | "onboarding" | "general">("all");

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.list();
      setNotifications(data);
      const unread = data.filter((n) => !n.is_read).length;
      if (onUnreadCountChange) onUnreadCountChange(unread);
    } catch {
      // Silently handle
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen]);

  const unreadCount = useMemo(() => {
    return notifications.filter((n) => !n.is_read).length;
  }, [notifications]);

  const filteredNotifications = useMemo(() => {
    if (activeCategory === "all") return notifications;
    if (activeCategory === "offers") {
      return notifications.filter((n) =>
        n.notification_type?.includes("offer") || n.title?.toLowerCase().includes("offer")
      );
    }
    if (activeCategory === "documents") {
      return notifications.filter((n) =>
        n.notification_type?.includes("doc") || n.title?.toLowerCase().includes("doc")
      );
    }
    if (activeCategory === "onboarding") {
      return notifications.filter((n) =>
        n.notification_type?.includes("onboarding") ||
        n.notification_type?.includes("employee") ||
        n.notification_type?.includes("joining") ||
        n.title?.toLowerCase().includes("onboarding") ||
        n.title?.toLowerCase().includes("employee")
      );
    }
    return notifications.filter((n) =>
      !n.notification_type?.includes("offer") &&
      !n.notification_type?.includes("doc") &&
      !n.notification_type?.includes("onboarding") &&
      !n.notification_type?.includes("employee")
    );
  }, [notifications, activeCategory]);

  const handleMarkAsRead = async (id: string, actionLink?: string) => {
    try {
      await notificationsApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      const newUnread = notifications.filter((n) => n.id !== id && !n.is_read).length;
      if (onUnreadCountChange) onUnreadCountChange(newUnread);

      if (actionLink) {
        onClose();
        navigate(actionLink);
      }
    } catch {
      // ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      if (onUnreadCountChange) onUnreadCountChange(0);
      addToast("All notifications marked as read", "success");
    } catch {
      addToast("Failed to mark all as read", "error");
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await notificationsApi.delete(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      const newUnread = notifications.filter((n) => n.id !== id && !n.is_read).length;
      if (onUnreadCountChange) onUnreadCountChange(newUnread);
    } catch {
      addToast("Failed to delete notification", "error");
    }
  };

  const getNotificationIcon = (type: string) => {
    if (type?.includes("offer")) {
      return (
        <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
          <FileText className="w-4 h-4" />
        </div>
      );
    }
    if (type?.includes("doc")) {
      return (
        <div className="w-9 h-9 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
          <ShieldCheck className="w-4 h-4" />
        </div>
      );
    }
    if (type?.includes("onboarding") || type?.includes("employee")) {
      return (
        <div className="w-9 h-9 rounded-xl bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
          <UserCheck className="w-4 h-4" />
        </div>
      );
    }
    return (
      <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center shrink-0">
        <Bell className="w-4 h-4" />
      </div>
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col border-l border-slate-200 animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="p-5 border-b border-slate-200/80 bg-slate-50/60 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shadow-xs">
                <Bell className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  Notifications
                  {unreadCount > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500 text-white shadow-xs">
                      {unreadCount} unread
                    </span>
                  )}
                </h2>
                <p className="text-[11px] text-slate-500">Live recruitment & onboarding activity</p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 px-2.5 py-1 rounded-md hover:bg-blue-50 transition-colors"
                >
                  Mark all read
                </button>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Category Filter Pills */}
          <div className="px-5 py-2.5 border-b border-slate-100 flex items-center gap-1.5 overflow-x-auto bg-white shrink-0 scrollbar-none">
            {(
              [
                { key: "all", label: "All" },
                { key: "offers", label: "Offers" },
                { key: "documents", label: "Documents" },
                { key: "onboarding", label: "Onboarding" },
                { key: "general", label: "General" },
              ] as const
            ).map((cat) => (
              <button
                key={cat.key}
                onClick={() => setActiveCategory(cat.key)}
                className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  activeCategory === cat.key
                    ? "bg-slate-900 text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200/70"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Notification List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2">
            {loading ? (
              <div className="py-20 text-center text-slate-400 text-xs">
                Loading notifications...
              </div>
            ) : filteredNotifications.length === 0 ? (
              <div className="py-24 px-6 text-center text-slate-400 space-y-2.5">
                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h4 className="text-xs font-bold text-slate-700">You're all caught up!</h4>
                <p className="text-[11px] text-slate-500">
                  No notifications matching this category.
                </p>
              </div>
            ) : (
              filteredNotifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => handleMarkAsRead(n.id, n.action_link)}
                  className={`p-3.5 rounded-xl transition-all cursor-pointer flex items-start gap-3 group relative ${
                    n.is_read
                      ? "hover:bg-slate-50/80 bg-white"
                      : "bg-blue-50/40 hover:bg-blue-50/70 border-l-3 border-blue-600"
                  }`}
                >
                  {getNotificationIcon(n.notification_type)}

                  <div className="flex-1 min-w-0 pr-6">
                    <div className="flex items-center justify-between gap-1">
                      <h4
                        className={`text-xs truncate ${
                          n.is_read ? "font-semibold text-slate-800" : "font-bold text-slate-900"
                        }`}
                      >
                        {n.title}
                      </h4>
                      {!n.is_read && (
                        <span className="w-2 h-2 rounded-full bg-blue-600 shrink-0" />
                      )}
                    </div>

                    <p className="text-[11px] text-slate-600 mt-0.5 line-clamp-2 leading-relaxed">
                      {n.message}
                    </p>

                    <div className="flex items-center gap-2 mt-2 text-[10px] text-slate-400">
                      <span className="flex items-center gap-1 font-medium">
                        <Clock className="w-3 h-3" />
                        {formatTimeAgo(n.created_at)}
                      </span>
                      {n.action_link && (
                        <span className="inline-flex items-center gap-0.5 text-blue-600 font-semibold group-hover:underline">
                          View <ExternalLink className="w-2.5 h-2.5" />
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Delete button on hover */}
                  <button
                    onClick={(e) => handleDelete(e, n.id)}
                    className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 rounded transition-all"
                    title="Delete notification"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="p-3.5 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
            <span className="text-[11px] flex items-center gap-1 text-slate-400">
              <Sparkles className="w-3 h-3 text-blue-500" /> Real-time activity sync
            </span>
            <button
              onClick={() => {
                fetchNotifications();
                addToast("Notifications refreshed", "info");
              }}
              className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 cursor-pointer"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NotificationCenter;
