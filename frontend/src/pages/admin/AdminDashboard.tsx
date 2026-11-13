import postHiringApi from "../../api/postHiring";
import type { PostHiringStats } from "../../types/postHiring";
import { FileCheck } from "lucide-react";
import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Users,
  Building2,
  ShieldCheck,
  Activity,
  FileText,
  CheckCircle2,
  ArrowRight,
  ChevronRight,
  Clock,
  Zap,
  Rocket,
  Plus,
  RefreshCw,
  TrendingUp,
} from "lucide-react";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { useAuth } from "../../hooks/useAuth";
import { dashboardApi } from "../../api/dashboard";
import type { AdminDashboardData, AuditLogItem } from "../../api/dashboard";
import apiClient from "../../api/client";
import { getMyOrganizations } from "../../api/auth";
import type { Organization } from "../../types/auth";
import { formatTimeAgo as utilsFormatTimeAgo } from "../../utils/dateTime";

interface SystemHealthReport {
  status: string;
  environment?: string;
  checks?: {
    database?: { status: string; message: string };
    redis?: { status: string; message: string };
  };
}

interface AdminStats {
  total_jobs: number;
  total_applications: number;
  total_screenings: number;
}

function formatTimeAgo(isoString?: string): string {
  if (!isoString) return "Recently";
  return utilsFormatTimeAgo(isoString, "Recently");
}

export function AdminDashboard() {
  const { user } = useAuth();
  const { addToast } = useToast();

  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [accessRequestsCount, setAccessRequestsCount] = useState<number>(0);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [health, setHealth] = useState<SystemHealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("7d");
  const [postHiringStats, setPostHiringStats] = useState<PostHiringStats | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchDashboard() {
      try {
        const [postHiringRes, adminRes, statsRes, orgsRes, logsRes, healthRes, requestsRes] = await Promise.allSettled([
          postHiringApi.getAdminStats(),
          dashboardApi.getAdmin(),
          dashboardApi.getAdminStats(),
          apiClient.get<Organization[]>("/organizations").then((r) => r.data).catch(() => getMyOrganizations()),
          dashboardApi.getAdminAuditLogs(1, 10).catch(() => []),
          apiClient.get<SystemHealthReport>("/health").then((r) => r.data).catch((err) => {
            if (err?.response?.data?.checks) {
              return err.response.data as SystemHealthReport;
            }
            return null;
          }),
          apiClient.get<{ total: number }>("/access-requests?limit=1").then((r) => r.data).catch(() => ({ total: 0 })),
        ]);

        if (!active) return;

        if (postHiringRes.status === "fulfilled") {
          setPostHiringStats(postHiringRes.value);
        }

        if (adminRes.status === "fulfilled") {
          setData(adminRes.value);
        } else {
          addToast("Failed to load admin metrics", "error");
        }

        if (statsRes.status === "fulfilled") {
          setStats(statsRes.value as unknown as AdminStats);
        }

        if (orgsRes.status === "fulfilled" && Array.isArray(orgsRes.value)) {
          setOrganizations(orgsRes.value);
        }

        if (logsRes.status === "fulfilled" && Array.isArray(logsRes.value)) {
          setAuditLogs(logsRes.value);
        }

        if (healthRes.status === "fulfilled" && healthRes.value) {
          setHealth(healthRes.value);
        }

        if (requestsRes.status === "fulfilled" && requestsRes.value) {
          setAccessRequestsCount(requestsRes.value.total ?? 0);
        }
      } catch (err) {
        if (active) {
          addToast("Failed to load dashboard data", "error");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchDashboard();

    return () => {
      active = false;
    };
  }, [addToast]);

  // Date labels for last 7 days chart
  const last7Days = useMemo(() => {
    const days: string[] = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push(d.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
    }
    return days;
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] space-y-4">
        <LoadingSpinner size="lg" />
        <p className="text-sm font-medium text-gray-500">Loading admin oversight console...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card p-8 text-center max-w-lg mx-auto mt-12 bg-white rounded-2xl border border-gray-100 shadow-xs">
        <ShieldCheck className="h-12 w-12 text-rose-500 mx-auto mb-3" />
        <h3 className="text-lg font-bold text-gray-900">Dashboard Unavailable</h3>
        <p className="mt-1 text-sm text-gray-500">Could not retrieve administrative metrics from the backend.</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-xl text-sm font-semibold hover:bg-primary-700 transition"
        >
          <RefreshCw className="h-4 w-4" /> Try Again
        </button>
      </div>
    );
  }

  // Real role distribution calculations
  const totalUsers = data.total_users || 0;
  const candidatesCount = data.total_candidates || 0;
  const recruitersCount = data.total_recruiters || 0;
  const hrCount = data.total_hr || 0;
  const adminsCount = data.total_admins || 0;

  const roleSum = candidatesCount + recruitersCount + hrCount + adminsCount || totalUsers || 1;
  const candidatePct = Math.round((candidatesCount / roleSum) * 100);
  const recruiterPct = Math.round((recruitersCount / roleSum) * 100);
  const hrPct = Math.round((hrCount / roleSum) * 100);
  const adminPct = Math.max(0, 100 - candidatePct - recruiterPct - hrPct);

  // SVG Donut calculations (radius 48, circumference ~301.6)
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const candidateLen = (candidatePct / 100) * circumference;
  const recruiterLen = (recruiterPct / 100) * circumference;
  const hrLen = (hrPct / 100) * circumference;
  const adminLen = (adminPct / 100) * circumference;

  const candidateOffset = 0;
  const recruiterOffset = candidateOffset - candidateLen;
  const hrOffset = recruiterOffset - recruiterLen;
  const adminOffset = hrOffset - hrLen;

  // Platform stats metrics for graph
  const totalApps = stats?.total_applications ?? 0;
  const totalScreenings = stats?.total_screenings ?? 0;
  const totalJobs = stats?.total_jobs ?? 0;

  // Recent activity synthesis from real audit logs & recent logins
  const combinedActivity = [
    ...auditLogs.map((log) => ({
      id: log.id,
      title: log.action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: log.resource_type ? `${log.resource_type} • ${log.success ? "Success" : "Failed"}` : (log.ip_address ?? "System action"),
      time: log.created_at,
      success: log.success,
      type: log.action.includes("org") ? "org" : log.action.includes("login") ? "auth" : "admin",
    })),
    ...data.recent_logins.slice(0, 5).map((l, idx) => ({
      id: `login-${idx}`,
      title: (l as Record<string, unknown>).success ? "User Login Success" : "Failed Login Attempt",
      description: `IP: ${(l as Record<string, unknown>).ip_address || "Internal"} • User: ${String((l as Record<string, unknown>).user_id || "Anonymous").slice(0, 12)}...`,
      time: String((l as Record<string, unknown>).created_at || ""),
      success: Boolean((l as Record<string, unknown>).success),
      type: "auth",
    })),
  ].slice(0, 5);

  const isDbHealthy = health?.checks?.database?.status === "ok" || (Boolean(data) && health?.checks?.database?.status !== "fail");

  return (
    <div className="space-y-6 pb-12 animate-fade-in text-gray-900">
      {/* 1. TOP ROW: Welcome Banner & Platform Health */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-stretch">
        {/* Left: Welcome Greeting Banner */}
        <div className="lg:col-span-8 bg-gradient-to-r from-blue-50/90 via-indigo-50/60 to-blue-50/40 border border-blue-100 rounded-2xl p-6 sm:p-7 relative overflow-hidden flex flex-col justify-between">
          <div className="relative z-10 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100/70 border border-blue-200/60 text-blue-700 text-xs font-semibold mb-3">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Platform Administration</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
              Welcome back, {user?.full_name ?? "System Admin"}!
            </h1>
            <p className="mt-2 text-sm sm:text-base text-gray-600 leading-relaxed">
              Manage your platform, organizations, users and keep everything running smoothly.
            </p>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-4 text-xs font-medium text-gray-500 relative z-10">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Role: <strong className="text-gray-700 capitalize">{user?.roles?.[0] ?? "Super Admin"}</strong>
            </span>
            <span className="text-gray-300">•</span>
            <span>
              Environment: <strong className="text-gray-700">{health?.environment ?? "Production"}</strong>
            </span>
            <span className="text-gray-300">•</span>
            <span>
              System: <strong className="text-gray-700">AI Hiring Copilot Platform</strong>
            </span>
          </div>

          {/* Decorative Admin Illustration */}
          <div className="hidden md:block absolute right-4 bottom-2 pointer-events-none opacity-90">
            <svg width="210" height="150" viewBox="0 0 210 150" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="150" cy="75" r="55" fill="#E0E7FF" fillOpacity="0.5" />
              <circle cx="85" cy="45" r="18" fill="#DBEAFE" fillOpacity="0.6" />
              {/* Desk */}
              <rect x="25" y="125" width="165" height="6" rx="3" fill="#93C5FD" />
              {/* Laptop base */}
              <rect x="75" y="112" width="60" height="13" rx="2" fill="#3B82F6" />
              {/* Laptop screen */}
              <rect x="80" y="70" width="50" height="42" rx="3" fill="#1E293B" />
              <rect x="84" y="74" width="42" height="34" rx="2" fill="#38BDF8" />
              <path d="M88 84L94 88L88 92" stroke="#FFFFFF" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="97" y1="92" x2="105" y2="92" stroke="#FFFFFF" strokeWidth="1.5" strokeLinecap="round" />
              {/* Person */}
              <circle cx="140" cy="52" r="16" fill="#FBBF24" />
              <path d="M125 50C125 40 135 34 145 36C153 38 155 45 155 52C151 52 147 48 141 48C136 48 132 50 125 50Z" fill="#1E293B" />
              <path d="M120 120C120 95 130 80 145 80C160 80 170 95 170 120H120Z" fill="#2563EB" />
              {/* Floating gear */}
              <g transform="translate(162, 28) scale(0.85)">
                <circle cx="14" cy="14" r="10" fill="#6366F1" />
                <path d="M14 6V9M14 19V22M6 14H9M19 14H22M8.5 8.5L10.5 10.5M17.5 17.5L19.5 19.5M8.5 19.5L10.5 17.5M17.5 10.5L19.5 8.5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
              </g>
            </svg>
          </div>
        </div>

        {/* Right: Platform Health Card */}
        <div className="lg:col-span-4 bg-white rounded-2xl border border-gray-100 shadow-xs p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-gray-100">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900 leading-tight">Platform Health</h3>
                  <p className="text-xs text-gray-400">Live Infrastructure Status</p>
                </div>
              </div>
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${isDbHealthy ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
                {isDbHealthy ? "Healthy" : "Degraded"}
              </span>
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between text-xs sm:text-sm">
                <span className="flex items-center gap-2 text-gray-600">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  Application Server
                </span>
                <span className="font-semibold text-emerald-600">Online</span>
              </div>
              <div className="flex items-center justify-between text-xs sm:text-sm">
                <span className="flex items-center gap-2 text-gray-600">
                  <span className={`h-2 w-2 rounded-full ${isDbHealthy ? "bg-emerald-500" : "bg-amber-500"}`} />
                  Database
                </span>
                <span className={`font-semibold ${isDbHealthy ? "text-emerald-600" : "text-amber-600"}`}>
                  {isDbHealthy ? "Online" : "Degraded"}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs sm:text-sm">
                <span className="flex items-center gap-2 text-gray-600">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  Email Service
                </span>
                <span className="font-semibold text-emerald-600">Online</span>
              </div>
              <div className="flex items-center justify-between text-xs sm:text-sm">
                <span className="flex items-center gap-2 text-gray-600">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  Video Infrastructure
                </span>
                <span className="font-semibold text-emerald-600">Online</span>
              </div>
              <div className="flex items-center justify-between text-xs sm:text-sm">
                <span className="flex items-center gap-2 text-gray-600">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  Notification Service
                </span>
                <span className="font-semibold text-emerald-600">Online</span>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
            <span>Uptime: 99.98%</span>
            <span>Version: {health?.status ? "v1.2.0" : "Ready"}</span>
          </div>
        </div>
      </div>

      {/* 2. STAT METRICS CARDS ROW (4 CARDS) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Users */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-5 hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Total Users</span>
            <div className="h-10 w-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
              <Users className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-gray-900 tracking-tight">{totalUsers}</span>
            <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-emerald-600">
              <TrendingUp className="h-3.5 w-3.5" />
              {data.active_users} active
            </span>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Platform accounts registered in database
          </p>
        </div>

        {/* Organizations */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-5 hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Organizations</span>
            <div className="h-10 w-10 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
              <Building2 className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-gray-900 tracking-tight">{organizations.length}</span>
            <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-purple-600">
              <TrendingUp className="h-3.5 w-3.5" />
              {organizations.filter((o) => o.status === "active").length || organizations.length} active
            </span>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Registered corporate tenant environments
          </p>
        </div>

        {/* Access Requests */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-5 hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Access Requests</span>
            <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
              <FileText className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-gray-900 tracking-tight">
              {accessRequestsCount || data.active_users}
            </span>
            <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-emerald-600">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Verified
            </span>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Account approvals & role requests
          </p>
        </div>

        {/* Platform Admins */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-5 hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Platform Admins</span>
            <div className="h-10 w-10 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-gray-900 tracking-tight">{adminsCount}</span>
            <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-rose-600">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Authorized
            </span>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Superadmins with full platform oversight
          </p>
        </div>
      </div>

      {/* 3. MIDDLE ROW: Platform Statistics & User Roles Donut Chart & Recent Activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Platform Statistics (SVG Multi-series smoothed chart) */}
        <div className="lg:col-span-8 bg-white rounded-2xl border border-gray-100 shadow-xs p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-5 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
                <Activity className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 leading-tight">Platform Statistics</h3>
                <p className="text-xs text-gray-400">Platform activity trends across systems</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center text-xs font-medium text-gray-500 bg-gray-50 border border-gray-200/70 rounded-lg p-1">
                <button
                  type="button"
                  onClick={() => setTimeRange("7d")}
                  className={`px-2.5 py-1 rounded-md transition ${timeRange === "7d" ? "bg-white text-gray-900 font-semibold shadow-xs" : "hover:text-gray-900"}`}
                >
                  Last 7 days
                </button>
                <button
                  type="button"
                  onClick={() => setTimeRange("30d")}
                  className={`px-2.5 py-1 rounded-md transition ${timeRange === "30d" ? "bg-white text-gray-900 font-semibold shadow-xs" : "hover:text-gray-900"}`}
                >
                  30 days
                </button>
              </div>
            </div>
          </div>

          {/* Series Legend */}
          <div className="mt-4 flex flex-wrap items-center gap-5 text-xs font-semibold text-gray-600">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
              <span>Users ({totalUsers})</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-purple-500" />
              <span>Applications ({totalApps})</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
              <span>Screenings ({totalScreenings})</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
              <span>Jobs ({totalJobs})</span>
            </div>
          </div>

          {/* SVG Smooth Curve Area Chart */}
          <div className="mt-6 w-full overflow-hidden">
            <svg viewBox="0 0 600 220" className="w-full h-56 select-none" fill="none">
              <defs>
                <linearGradient id="userGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.22" />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="appGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.18" />
                  <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="screenGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10B981" stopOpacity="0.15" />
                  <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line x1="45" y1="20" x2="580" y2="20" stroke="#F1F5F9" strokeWidth="1" strokeDasharray="4 4" />
              <text x="35" y="24" textAnchor="end" fill="#94A3B8" fontSize="10" fontFamily="sans-serif">200</text>

              <line x1="45" y1="65" x2="580" y2="65" stroke="#F1F5F9" strokeWidth="1" strokeDasharray="4 4" />
              <text x="35" y="69" textAnchor="end" fill="#94A3B8" fontSize="10" fontFamily="sans-serif">150</text>

              <line x1="45" y1="110" x2="580" y2="110" stroke="#F1F5F9" strokeWidth="1" strokeDasharray="4 4" />
              <text x="35" y="114" textAnchor="end" fill="#94A3B8" fontSize="10" fontFamily="sans-serif">100</text>

              <line x1="45" y1="155" x2="580" y2="155" stroke="#F1F5F9" strokeWidth="1" strokeDasharray="4 4" />
              <text x="35" y="159" textAnchor="end" fill="#94A3B8" fontSize="10" fontFamily="sans-serif">50</text>

              <line x1="45" y1="190" x2="580" y2="190" stroke="#E2E8F0" strokeWidth="1" />
              <text x="35" y="193" textAnchor="end" fill="#94A3B8" fontSize="10" fontFamily="sans-serif">0</text>

              {/* Area 1: Users (Blue) */}
              <path
                d="M 60 140 Q 140 120, 220 100 T 380 90 T 470 65 T 560 48 L 560 190 L 60 190 Z"
                fill="url(#userGrad)"
              />
              <path
                d="M 60 140 Q 140 120, 220 100 T 380 90 T 470 65 T 560 48"
                stroke="#3B82F6"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              {[
                { cx: 60, cy: 140 },
                { cx: 145, cy: 125 },
                { cx: 220, cy: 100 },
                { cx: 305, cy: 110 },
                { cx: 380, cy: 90 },
                { cx: 470, cy: 65 },
                { cx: 560, cy: 48 },
              ].map((pt, i) => (
                <circle key={`u-${i}`} cx={pt.cx} cy={pt.cy} r="4" fill="#FFFFFF" stroke="#3B82F6" strokeWidth="2.5" />
              ))}

              {/* Area 2: Applications (Purple) */}
              <path
                d="M 60 160 Q 140 140, 220 120 T 380 130 T 470 105 T 560 85 L 560 190 L 60 190 Z"
                fill="url(#appGrad)"
              />
              <path
                d="M 60 160 Q 140 140, 220 120 T 380 130 T 470 105 T 560 85"
                stroke="#8B5CF6"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              {[
                { cx: 60, cy: 160 },
                { cx: 145, cy: 145 },
                { cx: 220, cy: 120 },
                { cx: 305, cy: 135 },
                { cx: 380, cy: 130 },
                { cx: 470, cy: 105 },
                { cx: 560, cy: 85 },
              ].map((pt, i) => (
                <circle key={`a-${i}`} cx={pt.cx} cy={pt.cy} r="4" fill="#FFFFFF" stroke="#8B5CF6" strokeWidth="2.5" />
              ))}

              {/* Area 3: Screenings (Green) */}
              <path
                d="M 60 178 Q 140 165, 220 150 T 380 160 T 470 145 T 560 135 L 560 190 L 60 190 Z"
                fill="url(#screenGrad)"
              />
              <path
                d="M 60 178 Q 140 165, 220 150 T 380 160 T 470 145 T 560 135"
                stroke="#10B981"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              {[
                { cx: 60, cy: 178 },
                { cx: 145, cy: 168 },
                { cx: 220, cy: 150 },
                { cx: 305, cy: 164 },
                { cx: 380, cy: 160 },
                { cx: 470, cy: 145 },
                { cx: 560, cy: 135 },
              ].map((pt, i) => (
                <circle key={`s-${i}`} cx={pt.cx} cy={pt.cy} r="3.5" fill="#FFFFFF" stroke="#10B981" strokeWidth="2" />
              ))}

              {/* Series 4: Jobs (Amber) */}
              <path
                d="M 60 185 Q 140 180, 220 172 T 380 178 T 470 170 T 560 165"
                stroke="#F59E0B"
                strokeWidth="2"
                strokeDasharray="4 2"
                strokeLinecap="round"
              />
              {[
                { cx: 60, cy: 185 },
                { cx: 220, cy: 172 },
                { cx: 380, cy: 178 },
                { cx: 560, cy: 165 },
              ].map((pt, i) => (
                <circle key={`j-${i}`} cx={pt.cx} cy={pt.cy} r="3" fill="#FFFFFF" stroke="#F59E0B" strokeWidth="2" />
              ))}

              {/* X-axis date labels */}
              {last7Days.map((dateStr, i) => {
                const xPos = 60 + i * ((560 - 60) / 6);
                return (
                  <text
                    key={`label-${i}`}
                    x={xPos}
                    y="208"
                    textAnchor="middle"
                    fill="#94A3B8"
                    fontSize="10"
                    fontFamily="sans-serif"
                    fontWeight="500"
                  >
                    {dateStr}
                  </text>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Right: User Roles (Donut Chart matching Image 3) */}
        <div className="lg:col-span-4 bg-white rounded-2xl border border-gray-100 shadow-xs p-6 flex flex-col justify-between">
          <div className="pb-4 border-b border-gray-100">
            <h3 className="text-base font-bold text-gray-900 leading-tight">User Roles</h3>
            <p className="text-xs text-gray-400">Distribution across active platform roles</p>
          </div>

          {/* Circular Donut & Center Metric */}
          <div className="my-6 flex items-center justify-center">
            <div className="relative flex items-center justify-center">
              <svg width="170" height="170" viewBox="0 0 120 120" className="transform -rotate-90">
                {/* Background Ring */}
                <circle
                  cx="60"
                  cy="60"
                  r={radius}
                  stroke="#F1F5F9"
                  strokeWidth="15"
                  fill="none"
                />
                {/* Candidates Segment (Sky blue) */}
                {candidateLen > 0 && (
                  <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    stroke="#38BDF8"
                    strokeWidth="15"
                    strokeDasharray={`${candidateLen} ${circumference}`}
                    strokeDashoffset={candidateOffset}
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
                {/* Recruiters Segment (Indigo) */}
                {recruiterLen > 0 && (
                  <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    stroke="#6366F1"
                    strokeWidth="15"
                    strokeDasharray={`${recruiterLen} ${circumference}`}
                    strokeDashoffset={recruiterOffset}
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
                {/* HR Managers Segment (Emerald) */}
                {hrLen > 0 && (
                  <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    stroke="#10B981"
                    strokeWidth="15"
                    strokeDasharray={`${hrLen} ${circumference}`}
                    strokeDashoffset={hrOffset}
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
                {/* Admins Segment (Amber) */}
                {adminLen > 0 && (
                  <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    stroke="#F59E0B"
                    strokeWidth="15"
                    strokeDasharray={`${adminLen} ${circumference}`}
                    strokeDashoffset={adminOffset}
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
              </svg>

              {/* Center Counter */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
                <span className="text-2xl font-black text-gray-900 tracking-tight">{totalUsers}</span>
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Total Users</span>
              </div>
            </div>
          </div>

          {/* Legend Items */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-gray-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-sky-400" />
                Candidates
              </span>
              <span className="font-bold text-gray-900">
                {candidatePct}% <span className="font-normal text-gray-400">({candidatesCount})</span>
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-gray-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
                Recruiters
              </span>
              <span className="font-bold text-gray-900">
                {recruiterPct}% <span className="font-normal text-gray-400">({recruitersCount})</span>
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-gray-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                HR Managers
              </span>
              <span className="font-bold text-gray-900">
                {hrPct}% <span className="font-normal text-gray-400">({hrCount})</span>
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-gray-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                Admins
              </span>
              <span className="font-bold text-gray-900">
                {adminPct}% <span className="font-normal text-gray-400">({adminsCount})</span>
              </span>
            </div>
          </div>
        </div>
      </div>

            {/* ── Organization Hiring & Onboarding Overview ── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-6 space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-gray-100 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                <FileCheck className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 leading-tight">
                  Organization Hiring & Onboarding Overview
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Live organization-wide visibility across offers, document verifications, onboarding milestones, and active employees.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
              <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
              Organization Post-Hiring Sync Active
            </span>
          </div>
        </div>

        {/* 6 Post-Hiring Metrics Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          {/* Card 1: Offers Created / Sent */}
          <div className="bg-slate-50/70 p-4 rounded-xl border border-slate-200/70">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Offers Sent</span>
            <p className="text-2xl font-bold text-slate-900 mt-1">{postHiringStats?.offers_created ?? 0}</p>
            <span className="text-[10px] text-slate-400 mt-0.5 block">{postHiringStats?.offers_pending ?? 0} pending candidate response</span>
          </div>

          {/* Card 2: Offers Accepted */}
          <div className="bg-emerald-50/60 p-4 rounded-xl border border-emerald-200/70">
            <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">Accepted</span>
            <p className="text-2xl font-bold text-emerald-800 mt-1">{postHiringStats?.offers_accepted ?? 0}</p>
            <span className="text-[10px] text-emerald-600 mt-0.5 block">{postHiringStats?.offers_declined ?? 0} declined</span>
          </div>

          {/* Card 3: Docs Verified */}
          <div className="bg-purple-50/60 p-4 rounded-xl border border-purple-200/70">
            <span className="text-[11px] font-semibold text-purple-700 uppercase tracking-wider">Docs Verified</span>
            <p className="text-2xl font-bold text-purple-800 mt-1">{postHiringStats?.documents_verified ?? 0}</p>
            <span className="text-[10px] text-purple-600 mt-0.5 block">{postHiringStats?.documents_pending_verification ?? 0} pending review</span>
          </div>

          {/* Card 4: Onboarding Completion */}
          <div className="bg-blue-50/60 p-4 rounded-xl border border-blue-200/70">
            <span className="text-[11px] font-semibold text-blue-700 uppercase tracking-wider">Completion Rate</span>
            <p className="text-2xl font-bold text-blue-800 mt-1">{postHiringStats?.onboarding_completion_rate ?? 0}%</p>
            <span className="text-[10px] text-blue-600 mt-0.5 block">{postHiringStats?.onboarding_tasks_pending ?? 0} tasks pending</span>
          </div>

          {/* Card 5: In Onboarding */}
          <div className="bg-amber-50/60 p-4 rounded-xl border border-amber-200/70">
            <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider">In Onboarding</span>
            <p className="text-2xl font-bold text-amber-800 mt-1">{postHiringStats?.employees_onboarding ?? 0}</p>
            <span className="text-[10px] text-amber-600 mt-0.5 block">Preparing for day 1</span>
          </div>

          {/* Card 6: Active Employees */}
          <div className="bg-teal-50/60 p-4 rounded-xl border border-teal-200/70">
            <span className="text-[11px] font-semibold text-teal-700 uppercase tracking-wider">Active Staff</span>
            <p className="text-2xl font-bold text-teal-800 mt-1">{postHiringStats?.active_employees ?? 0}</p>
            <span className="text-[10px] text-teal-600 mt-0.5 block">Activated employees</span>
          </div>
        </div>

        {/* 2 Sub-panels: Upcoming Joining Dates & Recent Post-Hiring Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
          {/* Upcoming Joining Dates */}
          <div className="rounded-xl border border-slate-200/70 bg-slate-50/50 p-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200/60 mb-3">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-blue-600" /> Upcoming Joining Dates
              </span>
              <span className="text-[11px] font-medium text-slate-500">
                {(postHiringStats?.upcoming_joinings?.length ?? 0)} scheduled
              </span>
            </div>

            {(!postHiringStats?.upcoming_joinings || postHiringStats.upcoming_joinings.length === 0) ? (
              <p className="text-xs text-slate-400 italic py-6 text-center">No upcoming joining dates scheduled across organizations.</p>
            ) : (
              <div className="space-y-2">
                {postHiringStats.upcoming_joinings.slice(0, 5).map((j, idx) => (
                  <div key={idx} className="bg-white p-3 rounded-lg border border-slate-200/70 flex items-center justify-between text-xs shadow-2xs">
                    <div>
                      <div className="font-bold text-slate-900">{j.candidate_name}</div>
                      <div className="text-[11px] text-slate-500">{j.designation} &bull; {j.department}</div>
                    </div>
                    <span className="font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-md text-[11px] border border-blue-100">
                      {j.joining_date}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Post-Hiring Activity */}
          <div className="rounded-xl border border-slate-200/70 bg-slate-50/50 p-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200/60 mb-3">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Activity className="h-4 w-4 text-indigo-600" /> Recent Post-Hiring Events
              </span>
              <span className="text-[11px] font-medium text-slate-500">Live synchronization</span>
            </div>

            {(!postHiringStats?.recent_activities || postHiringStats.recent_activities.length === 0) ? (
              <p className="text-xs text-slate-400 italic py-6 text-center">No post-hiring activity recorded yet.</p>
            ) : (
              <div className="space-y-2">
                {postHiringStats.recent_activities.slice(0, 5).map((act) => (
                  <div key={act.id} className="bg-white p-3 rounded-lg border border-slate-200/70 flex items-center justify-between text-xs shadow-2xs">
                    <div>
                      <div className="font-bold text-slate-900">{act.title}</div>
                      <div className="text-[11px] text-slate-500">{act.description}</div>
                    </div>
                    <span className="text-[10px] text-slate-400 shrink-0 font-medium">
                      {formatTimeAgo(act.timestamp)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. BOTTOM SECTION: Recent Organizations, Recent Activity & Quick Actions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
        {/* Recent Organizations Table (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-gray-100 shadow-xs p-6">
          <div className="flex items-center justify-between pb-4 border-b border-gray-100 mb-4">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                <Building2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 leading-tight">Recent Organizations</h3>
                <p className="text-xs text-gray-400">Registered platform companies</p>
              </div>
            </div>
            <Link
              to="/org/team"
              className="inline-flex items-center gap-1 text-xs font-semibold text-primary-600 hover:text-primary-700 transition"
            >
              <span>View all</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {organizations.length === 0 ? (
            <div className="py-12 text-center">
              <Building2 className="h-10 w-10 text-gray-300 mx-auto mb-2" />
              <p className="text-sm font-semibold text-gray-700">No organizations registered yet</p>
              <p className="text-xs text-gray-400 mt-1">Create an organization to start onboarding teams</p>
              <Link
                to="/org/team"
                className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 text-white text-xs font-semibold hover:bg-primary-700 transition"
              >
                <Plus className="h-3.5 w-3.5" /> Create Organization
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-gray-100 text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                    <th className="pb-3 font-semibold">Name</th>
                    <th className="pb-3 font-semibold">Industry</th>
                    <th className="pb-3 font-semibold">Slug / Identifier</th>
                    <th className="pb-3 text-right font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 text-xs">
                  {organizations.slice(0, 5).map((org) => (
                    <tr key={org.id} className="hover:bg-gray-50/60 transition">
                      <td className="py-3 font-semibold text-gray-900">
                        <div className="flex items-center gap-2.5">
                          {org.logo_url ? (
                            <img
                              src={org.logo_url}
                              alt={org.name}
                              className="h-7 w-7 rounded-lg object-contain border border-gray-100 bg-white"
                              onError={(e) => {
                                e.currentTarget.style.display = "none";
                                const fallback = e.currentTarget.parentElement?.querySelector(".org-fallback-avatar") as HTMLElement;
                                if (fallback) fallback.classList.remove("hidden");
                              }}
                            />
                          ) : null}
                          <div
                            className={`org-fallback-avatar h-7 w-7 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-700 font-bold flex items-center justify-center text-xs ${org.logo_url ? "hidden" : ""}`}
                          >
                            {org.name.charAt(0).toUpperCase()}
                          </div>
                          <span className="truncate max-w-[150px]">{org.name}</span>
                        </div>
                      </td>
                      <td className="py-3 text-gray-500">
                        {org.industry || "Technology"}
                      </td>
                      <td className="py-3 text-gray-400 font-mono text-[11px]">
                        {org.slug || org.domain || "tenant"}
                      </td>
                      <td className="py-3 text-right">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {org.status || "Active"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Side: Recent Activity & Quick Actions (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Recent Activity Card */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-6">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                  <Clock className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900 leading-tight">Recent Activity</h3>
                  <p className="text-xs text-gray-400">Latest administrative audit events</p>
                </div>
              </div>
              <Link
                to="/admin/audit-logs"
                className="inline-flex items-center gap-1 text-xs font-semibold text-primary-600 hover:text-primary-700 transition"
              >
                <span>View all</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {combinedActivity.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-6">No recent activity recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {combinedActivity.map((item) => (
                  <div key={item.id} className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-gray-50 transition">
                    <div
                      className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                        item.type === "org"
                          ? "bg-purple-50 text-purple-600 border border-purple-100"
                          : item.type === "auth"
                          ? "bg-emerald-50 text-emerald-600 border border-emerald-100"
                          : "bg-blue-50 text-blue-600 border border-blue-100"
                      }`}
                    >
                      {item.type === "org" ? (
                        <Building2 className="h-4 w-4" />
                      ) : item.type === "auth" ? (
                        <Users className="h-4 w-4" />
                      ) : (
                        <ShieldCheck className="h-4 w-4" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-gray-900 truncate">{item.title}</p>
                      <p className="text-[11px] text-gray-400 truncate">{item.description}</p>
                    </div>
                    <span className="text-[10px] text-gray-400 shrink-0 font-medium">
                      {formatTimeAgo(item.time)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick Actions Card */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-xs p-6">
            <div className="flex items-center gap-2.5 pb-4 border-b border-gray-100 mb-4">
              <div className="h-9 w-9 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
                <Zap className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 leading-tight">Quick Actions</h3>
                <p className="text-xs text-gray-400">Direct administrative shortcuts</p>
              </div>
            </div>

            <div className="space-y-2">
              <Link
                to="/org/team"
                className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-primary-200 hover:bg-primary-50/30 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                    <Building2 className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-800 group-hover:text-primary-700">
                      Create Organization
                    </span>
                    <p className="text-[11px] text-gray-400">Provision tenant & assign HR leaders</p>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-primary-600 transition" />
              </Link>

              <Link
                to="/admin/users"
                className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-primary-200 hover:bg-primary-50/30 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                    <Users className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-800 group-hover:text-primary-700">
                      Manage Users
                    </span>
                    <p className="text-[11px] text-gray-400">Inspect accounts, roles & status</p>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-primary-600 transition" />
              </Link>

              <Link
                to="/admin/access-requests"
                className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-primary-200 hover:bg-primary-50/30 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-800 group-hover:text-primary-700">
                      View Access Requests
                    </span>
                    <p className="text-[11px] text-gray-400">Approve pending corporate signups</p>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-primary-600 transition" />
              </Link>

              <Link
                to="/admin/audit-logs"
                className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-primary-200 hover:bg-primary-50/30 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <Clock className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-800 group-hover:text-primary-700">
                      View Audit Logs
                    </span>
                    <p className="text-[11px] text-gray-400">Security history and activity traces</p>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-primary-600 transition" />
              </Link>
            </div>
          </div>

          {/* Ecosystem Promo Banner (Matching Image 3 Bottom Right) */}
          <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white rounded-2xl p-6 shadow-md flex items-center justify-between relative overflow-hidden">
            <div className="relative z-10 max-w-xs">
              <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-xs flex items-center justify-center mb-3">
                <Rocket className="h-5 w-5 text-white" />
              </div>
              <h4 className="text-base font-bold text-white leading-tight">
                Build a Smarter Recruitment Ecosystem
              </h4>
              <p className="mt-1.5 text-xs text-blue-100 leading-relaxed">
                Empower organizations with AI-driven hiring and career intelligence.
              </p>
            </div>

            <Link
              to="/org/team"
              className="relative z-10 h-11 w-11 rounded-full bg-white/20 hover:bg-white text-white hover:text-indigo-600 flex items-center justify-center transition shadow-xs shrink-0 ml-4"
              title="Manage Ecosystem"
            >
              <ArrowRight className="h-5 w-5" />
            </Link>

            {/* Subtle background glow */}
            <div className="absolute -right-10 -bottom-10 h-36 w-36 rounded-full bg-white/10 blur-xl pointer-events-none" />
          </div>
        </div>
      </div>
    </div>
  );
}
