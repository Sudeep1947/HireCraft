import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Video,
  FileText,
  Clock,
  Award,
} from "lucide-react";

import { hrApi, hrDecisionApi } from "../../api/hrOversight";
import postHiringApi from "../../api/postHiring";
import type { PostHiringStats } from "../../types/postHiring";
import { ShieldCheck, UserCheck, FileCheck, CheckCircle } from "lucide-react";
import type { HROverview, HRInterviewItem } from "../../api/hrOversight";
import {
  StatCard,
  DashboardCard,
  PipelineCard,
  InfoRow,
} from "../../components/dashboard";
import { useToast } from "../../contexts/ToastContext";
import { useAuth } from "../../hooks/useAuth";
import { applicationStatusLabel, formatDateTime } from "./hrOversightFormat";

const SvgIcons = {
  positions: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A18.18 18.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
  ),
  applications: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
    </svg>
  ),
  recruiters: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  ),
  selected: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
};

/**
 * Revised Phase 14 -- the HR organization-level overview & interview pipeline.
 *
 * Reads `/hr/overview` and `/hr/interviews` concurrently. Every figure on this
 * screen is a real aggregate the backend computed over authorized organizations,
 * with live actions for HR interview joining, evaluations, and final decisions.
 */
export function HROversightDashboard() {
  const { user } = useAuth();
  const { addToast } = useToast();
  const [data, setData] = useState<HROverview | null>(null);
  const [interviews, setInterviews] = useState<HRInterviewItem[]>([]);
  const [interviewFilter, setInterviewFilter] = useState<
    "all" | "scheduled" | "in_progress" | "completed" | "cancelled" | "rescheduled" | "pending"
  >("all");
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [postHiringStats, setPostHiringStats] = useState<PostHiringStats | null>(null);

  useEffect(() => {
    let active = true;
    const fetchInterviews =
      typeof hrDecisionApi?.getHrInterviews === "function"
        ? hrDecisionApi.getHrInterviews().catch((err) => {
            console.warn("Failed to load HR interview pipeline:", err);
            return { items: [], total: 0 };
          })
        : Promise.resolve({ items: [], total: 0 });

    Promise.all([hrApi.getOverview(), fetchInterviews, postHiringApi.getStats().catch(() => null)])
      .then(([overviewRes, interviewRes, postHiringRes]) => {
        if (postHiringRes) setPostHiringStats(postHiringRes);
        if (active) {
          setData(overviewRes);
          setInterviews(interviewRes.items ?? []);
        }
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true);
          addToast("Failed to load HR overview", "error");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [addToast]);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-9 w-64" />
          <div className="skeleton h-4 w-52" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((tile) => (
            <div key={tile} className="skeleton h-32" />
          ))}
        </div>
        <div className="skeleton h-56 w-full" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="skeleton h-72" />
          <div className="skeleton h-72" />
        </div>
      </div>
    );
  }

  if (loadFailed || !data) {
    return (
      <div className="animate-fade-up">
        <div className="error-banner">
          <span>Failed to load HR overview</span>
        </div>
      </div>
    );
  }

  const { counts } = data;
  const scopeLabel = data.is_platform_scope
    ? "Platform-wide (all organizations)"
    : data.organization_ids.length === 1
      ? "Your organization"
      : `Your ${data.organization_ids.length} organizations`;

  const filteredInterviews = interviews.filter((item) => {
    if (interviewFilter === "pending") {
      return !item.id || item.status === "pending_schedule" || item.status === "pending";
    }
    if (interviewFilter === "scheduled") {
      return item.status === "scheduled";
    }
    if (interviewFilter === "in_progress") {
      return item.status === "in_progress";
    }
    if (interviewFilter === "completed") {
      return item.status === "completed" || item.is_terminal;
    }
    if (interviewFilter === "cancelled") {
      return item.status === "cancelled";
    }
    if (interviewFilter === "rescheduled") {
      return item.status === "rescheduled";
    }
    return true;
  });

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const hrName = user?.full_name ? user.full_name.split(" ")[0] : "HR";

  const totalCandidates = counts.distinct_candidates || counts.total_applications;
  const safeTotalCandidates = Math.max(totalCandidates, 1);
  const shortlistedRate = Math.round((counts.shortlisted / safeTotalCandidates) * 100);
  const interviewRate = Math.round(((counts.interview_scheduled_total || counts.interview_scheduled) / safeTotalCandidates) * 100);
  const hiredRate = Math.round((counts.hired / safeTotalCandidates) * 100);
  const rejectedRate = Math.round((counts.rejected / safeTotalCandidates) * 100);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* ── Top Row: Image 2 Greeting + AI Hero Banner ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        <div className="lg:col-span-8 bg-gradient-to-br from-blue-600 via-indigo-600 to-indigo-700 rounded-2xl p-6 text-white shadow-xs relative overflow-hidden flex flex-col justify-between min-h-[170px]">
          <div className="relative z-10 max-w-[70%]">
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-snug">
              {greeting}, {hrName}!
            </h1>
            <p className="mt-2 text-sm text-blue-100 font-normal leading-relaxed">
              Hire great people, build amazing teams. Here's what's happening with your organization's hiring pipeline.
            </p>
            <div className="mt-5 flex flex-wrap gap-2.5">
              <Link
                to="/hr/jobs"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white text-blue-600 text-xs font-semibold shadow-xs hover:bg-blue-50 transition-colors"
              >
                Browse Active Jobs →
              </Link>
              <Link
                to="/hr/recruiters"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold backdrop-blur-xs transition-colors border border-white/20"
              >
                View Recruiters
              </Link>
            </div>
          </div>

          {/* Decorative AI HR Illustration Graphic */}
          <div className="absolute right-4 bottom-0 top-0 w-44 pointer-events-none opacity-90 flex items-center justify-center">
            <div className="relative w-32 h-32 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full bg-white/10 animate-pulse" />
              <div className="absolute inset-3 rounded-full bg-white/15" />
              <div className="relative z-10 flex flex-col items-center justify-center">
                <div className="h-14 w-14 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white border border-white/30 shadow-lg">
                  <svg className="h-8 w-8" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2a5 5 0 105 5 5 5 0 00-5-5zm0 8a3 3 0 113-3 3 3 0 01-3 3zm9 11v-1a7 7 0 00-7-7h-4a7 7 0 00-7 7v1z" />
                  </svg>
                </div>
                <div className="absolute -top-1 -right-2 px-2 py-0.5 rounded-full bg-emerald-500 text-[9px] font-bold text-white shadow-xs">
                  HR Live
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* AI Hero Card (Image 2 Top Right) */}
        <div className="lg:col-span-4 bg-gradient-to-br from-indigo-700 via-purple-700 to-indigo-900 rounded-2xl p-6 text-white shadow-xs flex flex-col justify-between min-h-[170px]">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight leading-snug">
              Find the Right Talent Faster with AI
            </h3>
            <p className="mt-1.5 text-xs text-indigo-100 font-normal leading-relaxed">
              Let AI help you evaluate skills, monitor fairness, and build stronger teams with predictive hiring analytics.
            </p>
          </div>
          <div className="mt-4">
            <Link
              to="/hr/fairness"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white text-indigo-700 text-xs font-semibold shadow-xs hover:bg-indigo-50 transition-colors"
            >
              Explore Insights →
            </Link>
          </div>
        </div>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">HR Overview</h1>
          <p className="page-subtitle">{`Welcome back, ${user?.full_name ?? "HR"}`}</p>
        </div>
        <div className="flex gap-2">
          <Link to="/hr/jobs" className="btn-primary btn-md">
            Browse Jobs
          </Link>
        </div>
      </div>

      {/* The rest of the read-only oversight surface */}
      <nav className="flex flex-wrap gap-2" aria-label="HR oversight sections">
        {[
          { to: "/hr/recruiters", label: "Recruiters" },
          { to: "/hr/attention", label: "Needs Attention" },
          { to: "/hr/quality", label: "Hiring Quality" },
        ].map((item) => (
          <Link key={item.to} to={item.to} className="chip">
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="info-banner">Scope: {scopeLabel}</div>

      {/* ── 5 Headline Pipeline Stat Cards (Image 2) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Candidates */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Total Candidates</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{counts.distinct_candidates}</span>
              <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                Active
              </span>
            </div>
            <span className="text-[10px] text-slate-400">In organizational scope</span>
          </div>
        </div>

        {/* Shortlisted */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Shortlisted</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{counts.shortlisted}</span>
              <span className="text-xs font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full">
                {shortlistedRate}%
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Passed screening</span>
          </div>
        </div>

        {/* Interviews Scheduled */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Interviews Scheduled</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">
                {counts.interview_scheduled_total || counts.interview_scheduled}
              </span>
              <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                {interviewRate}%
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Interview stage</span>
          </div>
        </div>

        {/* Hired */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Hired</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{counts.hired}</span>
              <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded-full">
                {hiredRate}%
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Accepted offers</span>
          </div>
        </div>

        {/* Rejected */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Rejected</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{counts.rejected}</span>
              <span className="text-xs font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full">
                {rejectedRate}%
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Closed candidate files</span>
          </div>
        </div>
      </div>

      {/* ── Retained Tested StatCards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Open Positions"
          value={counts.open_positions}
          color="primary"
          icon={SvgIcons.positions}
        />
        <StatCard
          title="Total Applications"
          value={counts.total_applications}
          color="blue"
          icon={SvgIcons.applications}
        />
        <StatCard
          title="Recruiters Hiring"
          value={counts.distinct_recruiters}
          color="green"
          icon={SvgIcons.recruiters}
        />
        <StatCard
          title="Selected"
          value={counts.selected}
          color="purple"
          icon={SvgIcons.selected}
        />
      </div>

      {/* ── Post-Hiring, Offers & Onboarding Section ── */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <FileCheck className="w-5 h-5 text-blue-600" />
              Post-Hiring & Employee Onboarding Overview
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Track offer acceptances, credential verifications, and new hire onboarding milestones.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/hr/offers"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
            >
              <FileText className="w-3.5 h-3.5" /> Offers ({postHiringStats?.offers_created || 0})
            </Link>
            <Link
              to="/hr/documents"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-50 text-purple-700 hover:bg-purple-100 transition-colors"
            >
              <ShieldCheck className="w-3.5 h-3.5" /> Documents ({postHiringStats?.documents_pending_verification || 0})
            </Link>
            <Link
              to="/hr/onboarding"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors"
            >
              <Clock className="w-3.5 h-3.5" /> Onboarding ({postHiringStats?.employees_onboarding || 0})
            </Link>
            <Link
              to="/hr/employees"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors"
            >
              <UserCheck className="w-3.5 h-3.5" /> Directory ({postHiringStats?.active_employees || 0})
            </Link>
          </div>
        </div>

        {/* Post-Hiring Stat Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Offers Sent</span>
            <p className="text-xl font-bold text-slate-900 mt-1">{postHiringStats?.offers_created || 0}</p>
          </div>
          <div className="bg-amber-50/60 p-3.5 rounded-xl border border-amber-100">
            <span className="text-[11px] font-medium text-amber-700 uppercase tracking-wider">Pending Reply</span>
            <p className="text-xl font-bold text-amber-800 mt-1">{postHiringStats?.offers_pending || 0}</p>
          </div>
          <div className="bg-emerald-50/60 p-3.5 rounded-xl border border-emerald-100">
            <span className="text-[11px] font-medium text-emerald-700 uppercase tracking-wider">Accepted</span>
            <p className="text-xl font-bold text-emerald-800 mt-1">{postHiringStats?.offers_accepted || 0}</p>
          </div>
          <div className="bg-purple-50/60 p-3.5 rounded-xl border border-purple-100">
            <span className="text-[11px] font-medium text-purple-700 uppercase tracking-wider">Docs Pending</span>
            <p className="text-xl font-bold text-purple-800 mt-1">{postHiringStats?.documents_pending_verification || 0}</p>
          </div>
          <div className="bg-blue-50/60 p-3.5 rounded-xl border border-blue-100">
            <span className="text-[11px] font-medium text-blue-700 uppercase tracking-wider">Onboarding</span>
            <p className="text-xl font-bold text-blue-800 mt-1">{postHiringStats?.employees_onboarding || 0}</p>
          </div>
          <div className="bg-teal-50/60 p-3.5 rounded-xl border border-teal-100">
            <span className="text-[11px] font-medium text-teal-700 uppercase tracking-wider">Active Staff</span>
            <p className="text-xl font-bold text-teal-800 mt-1">{postHiringStats?.active_employees || 0}</p>
          </div>
        </div>

        {/* Upcoming Joinings & Recent Activity Rows */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Upcoming Joinings */}
          <div className="border border-slate-100 bg-slate-50/50 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-blue-600" /> Upcoming Joining Dates
              </h3>
              <Link to="/hr/onboarding" className="text-[11px] font-semibold text-blue-600 hover:underline">
                View All
              </Link>
            </div>
            {(!postHiringStats?.upcoming_joinings || postHiringStats.upcoming_joinings.length === 0) ? (
              <p className="text-xs text-slate-400 italic py-4 text-center">No upcoming joining dates scheduled.</p>
            ) : (
              <div className="space-y-2">
                {postHiringStats.upcoming_joinings.slice(0, 4).map((j, idx) => (
                  <div key={idx} className="bg-white p-2.5 rounded-lg border border-slate-200/80 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-semibold text-slate-900">{j.candidate_name}</div>
                      <div className="text-[11px] text-slate-500">{j.designation} • {j.department}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium text-slate-700">{formatDateTime(j.joining_date)}</div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold capitalize">
                        {j.status.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Hiring Activities */}
          <div className="border border-slate-100 bg-slate-50/50 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4 text-emerald-600" /> Recent Post-Hiring Activity
              </h3>
              <Link to="/hr/offers" className="text-[11px] font-semibold text-blue-600 hover:underline">
                View Offers
              </Link>
            </div>
            {(!postHiringStats?.recent_activities || postHiringStats.recent_activities.length === 0) ? (
              <p className="text-xs text-slate-400 italic py-4 text-center">No recent post-hiring activity recorded.</p>
            ) : (
              <div className="space-y-2">
                {postHiringStats.recent_activities.slice(0, 4).map((act) => (
                  <div key={act.id} className="bg-white p-2.5 rounded-lg border border-slate-200/80 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-semibold text-slate-900">{act.title}</div>
                      <div className="text-[11px] text-slate-500">{act.description}</div>
                    </div>
                    <span className="text-[10px] text-slate-400 whitespace-nowrap">
                      {formatDateTime(act.timestamp)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>


      {/* ── HR Interviews & Final Decision Pipeline ── */}
      <DashboardCard
        title={`HR Interviews & Final Decisions (${interviews.length})`}
        className="rounded-xl shadow-sm border border-slate-200"
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3">
            <p className="text-xs text-gray-500">
              Candidates advanced by recruiters for HR interview scheduling, live evaluation, and final hiring selection.
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: "all", label: `All (${interviews.length})` },
                { id: "scheduled", label: "Scheduled" },
                { id: "in_progress", label: "In Progress" },
                { id: "completed", label: "Completed" },
                { id: "cancelled", label: "Cancelled" },
                { id: "rescheduled", label: "Rescheduled" },
                { id: "pending", label: "Awaiting Schedule" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setInterviewFilter(tab.id as any)}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold capitalize transition ${
                    interviewFilter === tab.id
                      ? "bg-purple-100 text-purple-800"
                      : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {filteredInterviews.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-500">No candidates currently match this filter in the HR pipeline.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-gray-600">
                <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-3 py-2.5">Candidate & Role</th>
                    <th className="px-3 py-2.5">Recruiter Assessment</th>
                    <th className="px-3 py-2.5">HR Interview Schedule</th>
                    <th className="px-3 py-2.5">Status & Decision</th>
                    <th className="px-3 py-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredInterviews.map((item) => (
                    <tr key={item.application_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-3">
                          {item.candidate_avatar_url ? (
                            <img
                              src={item.candidate_avatar_url}
                              alt={item.candidate_name}
                              className="h-10 w-10 rounded-full object-cover border border-slate-200 shrink-0"
                            />
                          ) : (
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-purple-100 text-purple-700 font-bold text-sm border border-purple-200 shrink-0">
                              {item.candidate_name ? item.candidate_name.charAt(0).toUpperCase() : "C"}
                            </div>
                          )}
                          <div>
                            <div className="font-semibold text-gray-900">{item.candidate_name}</div>
                            <div className="text-[11px] text-gray-500">{item.candidate_email || "No email"}</div>
                            <div className="mt-0.5 text-[11px] text-slate-700">
                              <span className="font-medium">{item.job_title}</span>
                              {item.organization_name && <span className="text-gray-400"> • {item.organization_name}</span>}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          {item.recruiter_score !== null ? (
                            <span className="inline-flex items-center gap-1 rounded bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-700">
                              <Award className="h-3 w-3" />
                              {item.recruiter_score}/100
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                          {item.recruiter_recommendation && (
                            <span className="inline-block rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold uppercase text-emerald-700">
                              {item.recruiter_recommendation}
                            </span>
                          )}
                        </div>
                        {item.recruiter_notes && (
                          <p className="mt-1 line-clamp-2 max-w-xs text-[11px] text-gray-500" title={item.recruiter_notes}>
                            {item.recruiter_notes}
                          </p>
                        )}
                        {item.recruiter_name && (
                          <p className="mt-0.5 text-[10px] text-gray-400">
                            Recruiter: <span className="font-medium text-gray-600">{item.recruiter_name}</span>
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <div>
                          {item.id ? (
                            <div className="space-y-1">
                              <span
                                className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                                  item.status === "scheduled"
                                    ? "bg-indigo-100 text-indigo-700"
                                    : item.status === "in_progress"
                                      ? "bg-amber-100 text-amber-800 animate-pulse"
                                      : item.status === "completed"
                                        ? "bg-emerald-100 text-emerald-800"
                                        : "bg-gray-100 text-gray-700"
                                }`}
                              >
                                {item.status.replace(/_/g, " ")}
                              </span>
                              <div className="flex items-center gap-1 text-[11px] text-gray-700">
                                <Clock className="h-3 w-3 text-gray-400" />
                                <span>{formatDateTime(item.scheduled_at)}</span>
                                {item.duration_minutes && <span className="text-gray-400">({item.duration_minutes}m)</span>}
                              </div>
                              {item.interviewer_name && (
                                <div className="text-[10px] text-gray-500">
                                  Interviewer: <span className="font-medium text-gray-700">{item.interviewer_name}</span>
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="inline-block rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                              Awaiting Schedule
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div>
                          <span className="inline-block rounded bg-slate-100 px-2 py-0.5 text-[11px] font-bold uppercase text-slate-800">
                            {applicationStatusLabel(item.application_status)}
                          </span>
                          {item.hr_score !== null && (
                            <div className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-purple-700">
                              <span>HR: {item.hr_score}/100</span>
                              {item.hr_recommendation && <span className="uppercase">({item.hr_recommendation})</span>}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {item.id && (item.status === "scheduled" || item.status === "in_progress") && (
                            <Link
                              to={`/interviews/${item.id}/room`}
                              className="btn-primary btn-sm inline-flex items-center gap-1.5"
                            >
                              <Video className="h-3.5 w-3.5" />
                              Join HR Interview
                            </Link>
                          )}
                          <Link
                            to={`/hr/applications/${item.application_id}`}
                            className="btn-secondary btn-sm inline-flex items-center gap-1.5"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            View Candidate Details
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </DashboardCard>

      {/* The white backing keeps the frosted funnel card legible on the mesh
          background while it carries the stage drill-down links. */}
      <div className="rounded-xl bg-white">
        <PipelineCard
          title="Application Funnel"
          stages={data.applications_by_status}
          action={{ label: "View jobs", href: "/hr/jobs" }}
          color="purple"
          // Every bar drills into the applications behind that one stage.
          stageHref={(stage) => `/hr/pipeline/${stage}`}
          stageLabel={applicationStatusLabel}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DashboardCard title="Decisions" className="rounded-xl">
          <InfoRow
            items={[
              { label: "Shortlisted", value: counts.shortlisted },
              { label: "Selected", value: counts.selected },
              { label: "Offered", value: counts.offered },
              { label: "Hired", value: counts.hired },
              { label: "Rejected", value: counts.rejected },
              { label: "Withdrawn", value: counts.withdrawn },
              {
                label: "Closed applications",
                value: counts.hired + counts.rejected + counts.withdrawn,
              },
            ]}
          />
          <p className="mt-3 text-xs text-gray-500">
            Each row counts applications in that exact status. &ldquo;Closed applications&rdquo; is the
            sum of the terminal statuses only.
          </p>
        </DashboardCard>

        <DashboardCard title="Interviews & Assessments" className="rounded-xl">
          <InfoRow
            items={[
              {
                label: "Applications in interview",
                value: counts.interview_scheduled,
              },
              {
                label: "Interviews scheduled",
                value: counts.interview_scheduled_total,
              },
              { label: "Assessments assigned", value: counts.assessments_assigned },
              { label: "Assessment attempts", value: counts.assessment_attempts },
            ]}
          />
          {(Object.keys(data.interviews_by_status).length > 0 ||
            Object.keys(data.assessments_by_status).length > 0) && (
            <div className="mt-4 flex flex-wrap gap-2">
              {Object.entries(data.interviews_by_status).map(([status, count]) => (
                <span
                  key={`interview-${status}`}
                  className="badge-primary capitalize"
                >
                  {status.replace(/_/g, " ")}: {count}
                </span>
              ))}
              {Object.entries(data.assessments_by_status).map(([status, count]) => (
                <span
                  key={`assessment-${status}`}
                  className="badge-info capitalize"
                >
                  {status.replace(/_/g, " ")}: {count}
                </span>
              ))}
            </div>
          )}
        </DashboardCard>
      </div>

      <DashboardCard title="Scope & Data Notes" className="rounded-xl">
        <InfoRow
          items={[
            { label: "Distinct candidates", value: counts.distinct_candidates },
            {
              label: "Organizations in scope",
              value: data.organization_ids.length || (data.is_platform_scope ? "All" : 0),
            },
            {
              label: "View",
              value: data.is_platform_scope ? "Cross-organization" : "Organization-scoped",
            },
          ]}
        />
        <p className="mt-3 text-xs text-gray-500">
          Every count above is computed from live application records in your scope.
        </p>
      </DashboardCard>
    </div>
  );
}

/** Compact funnel legend reused by the job drill-down. */
export function HROversightStatusLegend({ statuses }: { statuses: Record<string, number> }) {
  const entries = Object.entries(statuses);
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([status, count]) => (
        <span key={status} className="badge-neutral">
          {applicationStatusLabel(status)}: {count}
        </span>
      ))}
    </div>
  );
}
