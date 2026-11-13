import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { notificationsApi } from "../../api/notifications";
import { getRoleBadgeColor } from "../../utils/roleRouting";
import { NotificationCenter } from "../notifications/NotificationCenter";

function getInitials(name?: string): string {
  if (!name) return "RS";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatRoleLabel(role?: string): string {
  if (!role) return "User";
  if (role === "super_admin") return "System Admin";
  if (role === "admin") return "Admin";
  if (role === "organization_admin") return "Org Admin";
  if (role === "hr_manager" || role === "hr") return "HR Manager";
  if (role === "recruiter") return "Recruiter";
  if (role === "candidate") return "Candidate";
  return role.charAt(0).toUpperCase() + role.slice(1);
}

export function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);
  const [isNotifOpen, setIsNotifOpen] = useState(false);

  useEffect(() => {
    if (!user) return;
    notificationsApi
      .getUnreadCount()
      .then((data) => {
        if (data && typeof data.count === "number") {
          setUnreadCount(data.count);
        }
      })
      .catch(() => {});
  }, [user]);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const displayName = user?.full_name || (user?.roles?.includes("super_admin") ? "System Admin" : user?.roles?.includes("admin") ? "Admin" : "User");
  const roleLabel = formatRoleLabel(user?.roles?.[0] || "recruiter");

  return (
    <header className="bg-white border-b border-slate-100 h-16 flex items-center justify-between px-6 md:px-8 sticky top-0 z-40 shrink-0 shadow-2xs">
      {/* Search Bar */}
      <div className="relative w-72 sm:w-80 md:w-96">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
          <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          placeholder="Search jobs, candidates, insights..."
          className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2 pl-10 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
        />
      </div>

      <div className="flex items-center gap-4 sm:gap-5">
        {/* Notifications Bell with Live Badge */}
        <button
          onClick={() => setIsNotifOpen((prev) => !prev)}
          className={`relative p-2 rounded-full transition-colors ${
            isNotifOpen ? "bg-blue-50 text-blue-600" : "text-slate-400 hover:text-slate-600 hover:bg-slate-50"
          }`}
          aria-label="Notifications"
          title="Open Notifications"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
          </svg>
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow-xs">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>

        {/* User Info & Avatar */}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 text-white font-bold text-xs shadow-xs ring-2 ring-blue-100">
            {getInitials(displayName)}
          </div>
          <div className="hidden sm:flex flex-col">
            <span className="text-sm font-semibold text-slate-900 leading-tight">
              {displayName}
            </span>
            <span className={`mt-0.5 inline-flex items-center self-start rounded-full px-2 py-0.5 text-[10px] font-semibold ${getRoleBadgeColor(user?.roles || [])}`}>
              {roleLabel}
            </span>
          </div>
        </div>

        {/* Sign out link on far right */}
        <button
          onClick={handleLogout}
          className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors ml-1"
        >
          Sign out
        </button>
      </div>

      {/* Centralized Post-Hiring Notification Center */}
      <NotificationCenter
        isOpen={isNotifOpen}
        onClose={() => setIsNotifOpen(false)}
        onUnreadCountChange={setUnreadCount}
      />
    </header>
  );
}
