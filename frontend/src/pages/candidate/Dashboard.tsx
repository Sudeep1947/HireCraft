import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useToast } from "../../contexts/ToastContext";
import { useAuth } from "../../hooks/useAuth";
import { candidateApi } from "../../api/candidate";
import type {
  CandidateDashboard as DashboardData,
  CandidateProfile,
  CandidateSkill,
  ProfileCompletion as ProfileCompletionData,
} from "../../types/candidate";
import { candidateJobApi } from "../../api/jobs";
import type { JobApplication, JobListItem } from "../../types/jobs";
import { interviewApi } from "../../api/interview";
import type { InterviewListItem } from "../../types/interview";
import { resolveAvatarUrl } from "../../utils/avatar";
import { formatTimeAgo as utilsFormatTimeAgo, formatDateTime as utilsFormatDateTime } from "../../utils/dateTime";

function formatTimeAgo(isoString?: string): string {
  if (!isoString) return "Recently";
  return utilsFormatTimeAgo(isoString, "Recently");
}

function formatScheduledDate(isoString?: string | null): string {
  if (!isoString) return "Date TBD";
  return utilsFormatDateTime(isoString, "Date TBD");
}

export function CandidateDashboard() {
  const { user } = useAuth();
  const { addToast } = useToast();

  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [completion, setCompletion] = useState<ProfileCompletionData | null>(null);
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [skills, setSkills] = useState<CandidateSkill[]>([]);
  const [interviews, setInterviews] = useState<InterviewListItem[]>([]);
  const [recommendedJobs, setRecommendedJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [bannerAvatarError, setBannerAvatarError] = useState(false);
  const [profileAvatarError, setProfileAvatarError] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const [dashRes, compRes, profileRes, appsRes, skillsRes, interviewsRes, jobsRes] =
          await Promise.allSettled([
            candidateApi.getDashboard(),
            candidateApi.getProfileCompletion(),
            candidateApi.getProfile(),
            candidateJobApi.getMyApplications(),
            candidateApi.listSkills(),
            interviewApi.listInterviews(),
            candidateJobApi.searchJobs({ page: 1, page_size: 3 }),
          ]);

        if (!active) return;

        if (dashRes.status === "fulfilled") setDashboard(dashRes.value);
        if (compRes.status === "fulfilled") setCompletion(compRes.value);
        if (profileRes.status === "fulfilled") setProfile(profileRes.value);
        if (appsRes.status === "fulfilled") setApplications(appsRes.value || []);
        if (skillsRes.status === "fulfilled") setSkills(skillsRes.value || []);
        if (interviewsRes.status === "fulfilled" && interviewsRes.value?.items) {
          setInterviews(interviewsRes.value.items || []);
        }
        if (jobsRes.status === "fulfilled" && jobsRes.value?.items) {
          setRecommendedJobs(jobsRes.value.items.slice(0, 3));
        }
      } catch {
        if (active) addToast("Failed to load dashboard data", "error");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadData();
    return () => {
      active = false;
    };
  }, [addToast]);

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading candidate dashboard">
        <div className="skeleton h-10 w-72 rounded-xl" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-4 w-20 rounded" />
              <div className="skeleton mt-2 h-8 w-14 rounded" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 skeleton h-72 rounded-2xl" />
          <div className="lg:col-span-4 skeleton h-72 rounded-2xl" />
        </div>
      </div>
    );
  }

  // Greeting logic
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const candidateName = user?.full_name || dashboard?.full_name || "Candidate";
  const firstName = candidateName.split(" ")[0];

  // Real Database Metrics from Applications
  const totalApplied = applications.length;
  const shortlistedCount = applications.filter((a) => a.status === "shortlisted").length;
  const interviewCount =
    applications.filter((a) => a.status === "interview_scheduled" || a.status === "interviewed").length ||
    interviews.filter((i) => i.status === "scheduled" || i.status === "in_progress").length;
  const assessmentCount = applications.filter(
    (a) => a.screening_status === "completed" || Boolean((a as unknown as Record<string, unknown>).has_assessment)
  ).length;
  const offersCount = applications.filter(
    (a) => a.status === "selected" || a.status === "hired" || a.status === "offered"
  ).length;
  const rejectedCount = applications.filter((a) => a.status === "rejected").length;
  const inReviewCount = applications.filter((a) => a.status === "applied" || a.status === "under_review").length;

  // Real Percentages for Application Status
  const safeTotal = Math.max(totalApplied, 1);
  const appliedPct = totalApplied > 0 ? Math.round((inReviewCount / safeTotal) * 100) : 0;
  const shortlistedPct = totalApplied > 0 ? Math.round((shortlistedCount / safeTotal) * 100) : 0;
  const interviewPct = totalApplied > 0 ? Math.round((interviewCount / safeTotal) * 100) : 0;
  const assessmentPct = totalApplied > 0 ? Math.round((assessmentCount / safeTotal) * 100) : 0;
  const offerPct = totalApplied > 0 ? Math.round((offersCount / safeTotal) * 100) : 0;
  const rejectedPct = totalApplied > 0 ? Math.round((rejectedCount / safeTotal) * 100) : 0;

  // Profile completion rate
  const completionPct =
    completion?.completion_percentage ??
    profile?.profile_completion ??
    (profile?.current_role ? 75 : 40);

  const avatarUrl = resolveAvatarUrl(profile?.avatar_url);

  return (
    <div className="space-y-6">
      {/* ── Top Header + Candidate Profile Card ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Left: Welcome Greeting Banner */}
        <div className="lg:col-span-8 bg-gradient-to-br from-blue-600 via-indigo-600 to-indigo-700 rounded-2xl p-6 text-white shadow-xs relative overflow-hidden flex flex-col justify-between min-h-[170px]">
          <div className="relative z-10 max-w-[70%]">
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-snug">
              {greeting}, {firstName}!
            </h1>
            <p className="mt-2 text-sm text-blue-100 font-normal leading-relaxed">
              Your career journey matters. Keep going — new opportunities and matching roles are waiting for you!
            </p>
            <div className="mt-5 flex flex-wrap gap-2.5">
              <Link
                to="/candidate/jobs"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white text-blue-600 text-xs font-semibold shadow-xs hover:bg-blue-50 transition-colors"
              >
                Browse Open Roles →
              </Link>
              <Link
                to="/skill2job"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold backdrop-blur-xs transition-colors border border-white/20"
              >
                Explore Skill2Job
              </Link>
            </div>
          </div>

          {/* Candidate Profile Avatar Badge */}
          <div className="absolute right-4 bottom-0 top-0 w-44 pointer-events-none opacity-95 flex items-center justify-center">
            <div className="relative w-32 h-32 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full bg-white/10 animate-pulse" />
              <div className="absolute inset-3 rounded-full bg-white/15" />
              <div className="relative z-10 flex flex-col items-center justify-center">
                <div className="h-16 w-16 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white border border-white/30 shadow-lg overflow-hidden">
                  {avatarUrl && !bannerAvatarError ? (
                    <img
                      src={avatarUrl}
                      alt={candidateName}
                      className="h-full w-full object-cover"
                      onError={() => setBannerAvatarError(true)}
                    />
                  ) : (
                    <div className="h-full w-full flex items-center justify-center bg-gradient-to-tr from-blue-500 to-indigo-500 text-2xl font-bold text-white uppercase shadow-inner">
                      {candidateName.charAt(0) || "C"}
                    </div>
                  )}
                </div>
                <div className="absolute -top-1 -right-2 px-2 py-0.5 rounded-full bg-emerald-500 text-[9px] font-bold text-white shadow-xs">
                  Active
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Candidate Profile Overview Card (Image 1 Style) */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-100 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 text-white flex items-center justify-center text-lg font-bold shadow-md shadow-blue-500/20 shrink-0 overflow-hidden">
                  {avatarUrl && !profileAvatarError ? (
                    <img
                      src={avatarUrl}
                      alt={candidateName}
                      className="h-full w-full object-cover"
                      onError={() => setProfileAvatarError(true)}
                    />
                  ) : (
                    candidateName.charAt(0).toUpperCase()
                  )}
                </div>
                <div className="min-w-0">
                  <h3 className="text-base font-bold text-slate-900 truncate">{candidateName}</h3>
                  <p className="text-xs text-slate-500 truncate">
                    {profile?.current_role || "Candidate Profile"}
                  </p>
                  {user?.email && (
                    <p className="text-[10px] text-slate-400 font-mono truncate">{user.email}</p>
                  )}
                </div>
              </div>
              <Link
                to="/candidate/profile"
                className="px-2.5 py-1 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors shrink-0"
              >
                Edit Profile
              </Link>
            </div>

            {/* Profile Completeness Bar */}
            <div className="mt-4 pt-3 border-t border-slate-100">
              <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                <span className="text-slate-600">Profile Completeness</span>
                <span className="text-blue-600">{completionPct}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-600 h-full rounded-full transition-all duration-500"
                  style={{ width: `${completionPct}%` }}
                />
              </div>
            </div>
          </div>

          {/* Badges / Quick Details */}
          <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] text-slate-600 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-slate-400">📍</span>
              <span className="truncate">{profile?.location || "Location open"}</span>
            </div>
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-slate-400">💼</span>
              <span className="truncate">{profile?.current_role || "Available"}</span>
            </div>
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-slate-400">🎓</span>
              <span className="truncate">Candidate</span>
            </div>
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-slate-400">📄</span>
              <span className="truncate">{dashboard?.total_resumes ? `${dashboard.total_resumes} Resumes` : "Resume uploaded"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 5 Stat Cards (Image 1 Layout) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card 1: Applied Jobs */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-50 text-cyan-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Applied Jobs</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{totalApplied}</span>
              <span className="text-xs font-semibold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded-full">
                Active
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Total applications</span>
          </div>
        </div>

        {/* Card 2: Shortlisted */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Shortlisted</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{shortlistedCount}</span>
              <span className="text-xs font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full">
                Reviewing
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Passed initial screening</span>
          </div>
        </div>

        {/* Card 3: Interviews Scheduled */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Interviews</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{interviewCount}</span>
              <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                Scheduled
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Interview stage</span>
          </div>
        </div>

        {/* Card 4: Assessments */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Assessments</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{assessmentCount}</span>
              <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                Active
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Technical evaluations</span>
          </div>
        </div>

        {/* Card 5: Offers Received */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500">Offers Received</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-900">{offersCount}</span>
              <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full">
                Placed
              </span>
            </div>
            <span className="text-[10px] text-slate-400">Selected & offered</span>
          </div>
        </div>
      </div>

      {/* ── Middle Row: Application Status Donut + Skills Overview + Quick Links ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Card 1: Application Status (Donut Chart) */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-100 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-base font-bold text-slate-900">Application Status</h3>
            <span className="text-xs font-medium text-slate-500 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200/60">
              Live
            </span>
          </div>

          <div className="flex flex-col items-center justify-center my-auto py-2">
            <div className="relative flex items-center justify-center h-32 w-32">
              <svg className="h-full w-full transform -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="14" fill="transparent" stroke="#f1f5f9" strokeWidth="4.5" />
                {totalApplied > 0 && (
                  <>
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="transparent"
                      stroke="#3b82f6"
                      strokeWidth="4.5"
                      strokeDasharray={`${appliedPct} ${100 - appliedPct}`}
                      strokeDashoffset="0"
                    />
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="transparent"
                      stroke="#a855f7"
                      strokeWidth="4.5"
                      strokeDasharray={`${shortlistedPct} ${100 - shortlistedPct}`}
                      strokeDashoffset={`-${appliedPct}`}
                    />
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="transparent"
                      stroke="#06b6d4"
                      strokeWidth="4.5"
                      strokeDasharray={`${interviewPct} ${100 - interviewPct}`}
                      strokeDashoffset={`-${appliedPct + shortlistedPct}`}
                    />
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="transparent"
                      stroke="#f59e0b"
                      strokeWidth="4.5"
                      strokeDasharray={`${assessmentPct} ${100 - assessmentPct}`}
                      strokeDashoffset={`-${appliedPct + shortlistedPct + interviewPct}`}
                    />
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="transparent"
                      stroke="#10b981"
                      strokeWidth="4.5"
                      strokeDasharray={`${offerPct} ${100 - offerPct}`}
                      strokeDashoffset={`-${appliedPct + shortlistedPct + interviewPct + assessmentPct}`}
                    />
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="transparent"
                      stroke="#f43f5e"
                      strokeWidth="4.5"
                      strokeDasharray={`${rejectedPct} ${100 - rejectedPct}`}
                      strokeDashoffset={`-${appliedPct + shortlistedPct + interviewPct + assessmentPct + offerPct}`}
                    />
                  </>
                )}
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold text-slate-900 leading-tight">{totalApplied}</span>
                <span className="text-[10px] text-slate-400 font-medium">Total</span>
              </div>
            </div>

            {/* Status Legend with real numbers */}
            <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs text-slate-600 w-full px-2">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                <span className="truncate">Applied <span className="font-semibold text-slate-800">{inReviewCount}</span></span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-purple-500 shrink-0" />
                <span className="truncate">Shortlist <span className="font-semibold text-slate-800">{shortlistedCount}</span></span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-cyan-500 shrink-0" />
                <span className="truncate">Interview <span className="font-semibold text-slate-800">{interviewCount}</span></span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-amber-500 shrink-0" />
                <span className="truncate">Assessment <span className="font-semibold text-slate-800">{assessmentCount}</span></span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500 shrink-0" />
                <span className="truncate">Offers <span className="font-semibold text-slate-800">{offersCount}</span></span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-rose-400 shrink-0" />
                <span className="truncate">Rejected <span className="font-semibold text-slate-800">{rejectedCount}</span></span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Skills Overview (Image 1 Style) */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-100 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900">Skills Overview</h3>
            <Link to="/candidate/profile" className="text-xs font-semibold text-blue-600 hover:text-blue-700">
              View All →
            </Link>
          </div>

          <div className="space-y-3.5 my-auto">
            {skills.length > 0 ? (
              skills.slice(0, 5).map((sk, idx) => {
                const name = sk.skill?.name || `Skill #${sk.skill_id}`;
                const prof = (sk.proficiency || "intermediate").toLowerCase();
                const pct =
                  prof === "expert" ? 90 :
                  prof === "advanced" ? 75 :
                  prof === "intermediate" ? 55 : 35;
                const colors = [
                  "bg-blue-600",
                  "bg-indigo-500",
                  "bg-cyan-500",
                  "bg-amber-500",
                  "bg-emerald-500",
                ][idx % 5];

                return (
                  <div key={sk.skill_id || idx} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-medium">
                      <span className="text-slate-800 font-semibold">{name}</span>
                      <span className="text-slate-500 text-[11px] capitalize">{prof} ({pct}%)</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className={`${colors} h-full rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="py-8 text-center text-slate-400">
                <p className="text-xs">No skills registered yet.</p>
                <Link to="/candidate/profile" className="mt-1 text-xs font-semibold text-blue-600 hover:underline inline-block">
                  Add skills to your profile →
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Card 3: Quick Links (Image 1 Style) */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-100 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-slate-900">Quick Links</h3>
          </div>

          <div className="space-y-2.5 my-auto">
            <Link
              to="/candidate/applications"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-blue-50/20 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">My Applications</h4>
                  <p className="text-[11px] text-slate-400">Track your applications & status</p>
                </div>
              </div>
              <span className="text-slate-400 group-hover:text-blue-600 transition-colors">→</span>
            </Link>

            <Link
              to="/candidate/resume"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-100 hover:border-purple-200 hover:bg-purple-50/20 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">Resume & CV</h4>
                  <p className="text-[11px] text-slate-400">Manage versions & ATS analysis</p>
                </div>
              </div>
              <span className="text-slate-400 group-hover:text-purple-600 transition-colors">→</span>
            </Link>

            <Link
              to="/candidate/profile"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-100 hover:border-emerald-200 hover:bg-emerald-50/20 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">Skill Profile</h4>
                  <p className="text-[11px] text-slate-400">Update skills & certifications</p>
                </div>
              </div>
              <span className="text-slate-400 group-hover:text-emerald-600 transition-colors">→</span>
            </Link>

            <Link
              to="/skill2job"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-100 hover:border-cyan-200 hover:bg-cyan-50/20 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center shrink-0">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12l-2.731-8.875A59.769 59.769 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">Career Guidance</h4>
                  <p className="text-[11px] text-slate-400">Skill2Job intelligence & gap radar</p>
                </div>
              </div>
              <span className="text-slate-400 group-hover:text-cyan-600 transition-colors">→</span>
            </Link>
          </div>
        </div>
      </div>

      {/* ── Bottom Section: Recent Applications & Upcoming Interviews ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Recent Applications Table */}
        <div className="lg:col-span-8 bg-white rounded-2xl p-6 border border-slate-100 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Recent Applications</h3>
              <p className="text-xs text-slate-500">Your submitted job applications</p>
            </div>
            <Link to="/candidate/applications" className="text-xs font-semibold text-blue-600 hover:text-blue-700">
              View All ({applications.length}) →
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-slate-400 uppercase text-[10px] font-semibold tracking-wider">
                  <th className="pb-3 font-semibold">Job Title</th>
                  <th className="pb-3 font-semibold">Company</th>
                  <th className="pb-3 font-semibold">Applied On</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {applications.length > 0 ? (
                  applications.slice(0, 5).map((app, idx) => (
                    <tr key={app.id || idx} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 font-semibold text-slate-900">
                        <Link to={`/candidate/applications`} className="hover:text-blue-600 transition-colors">
                          {app.job_title || `Job Application #${app.id.slice(0, 8)}`}
                        </Link>
                      </td>
                      <td className="py-3 text-slate-600">{app.company || "Direct Hire"}</td>
                      <td className="py-3 text-slate-400">{formatTimeAgo(app.created_at)}</td>
                      <td className="py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize ${
                            app.status === "selected" || app.status === "hired"
                              ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500/20"
                              : app.status === "interview_scheduled" || app.status === "interviewed"
                              ? "bg-purple-50 text-purple-700 ring-1 ring-purple-500/20"
                              : app.status === "shortlisted"
                              ? "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-500/20"
                              : app.status === "rejected"
                              ? "bg-rose-50 text-rose-700 ring-1 ring-rose-500/20"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {app.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <Link
                          to="/candidate/applications"
                          className="text-xs font-semibold text-blue-600 hover:text-blue-700"
                        >
                          Track →
                        </Link>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      <p className="text-xs">You haven't submitted any job applications yet.</p>
                      <Link to="/candidate/jobs" className="mt-1 text-xs font-semibold text-blue-600 hover:underline inline-block">
                        Explore matching jobs now →
                      </Link>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Upcoming Interviews */}
        <div className="lg:col-span-4 bg-white rounded-2xl p-6 border border-slate-100 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Upcoming Interviews</h3>
              <p className="text-xs text-slate-500">Live interview schedule</p>
            </div>
            <Link to="/candidate/interview-history" className="text-xs font-semibold text-blue-600 hover:text-blue-700">
              View All →
            </Link>
          </div>

          <div className="space-y-3 my-auto">
            {interviews.length > 0 ? (
              interviews.slice(0, 3).map((item, idx) => (
                <div key={item.id || idx} className="p-3.5 rounded-xl border border-slate-100 bg-slate-50/40 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-xs font-bold text-slate-900 leading-tight">
                        {item.job_title || "Technical Interview"}
                      </h4>
                      <p className="text-[11px] text-slate-500 capitalize">{item.interview_type.replace(/_/g, " ")}</p>
                    </div>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                        item.status === "scheduled"
                          ? "bg-emerald-50 text-emerald-700"
                          : item.status === "in_progress"
                          ? "bg-amber-50 text-amber-700 animate-pulse"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-slate-200/60 text-[11px]">
                    <span className="text-slate-500 font-medium">{formatScheduledDate(item.scheduled_at)}</span>
                    <Link
                      to={`/interviews/${item.id}/room`}
                      className="font-bold text-blue-600 hover:text-blue-700"
                    >
                      Join Room →
                    </Link>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-slate-400">
                <div className="h-9 w-9 mx-auto rounded-xl bg-slate-50 flex items-center justify-center text-slate-400 mb-2">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                  </svg>
                </div>
                <p className="text-xs">No interviews scheduled yet.</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Invitations will appear here once scheduled.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Recommended Jobs For You (Real Database Jobs) ── */}
      {recommendedJobs.length > 0 && (
        <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Recommended Jobs For You</h3>
              <p className="text-xs text-slate-500">Live openings matching your skills</p>
            </div>
            <Link to="/candidate/jobs" className="text-xs font-semibold text-blue-600 hover:text-blue-700">
              View All Jobs →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {recommendedJobs.map((job) => (
              <div
                key={job.id}
                className="p-4 rounded-xl border border-slate-100 hover:border-blue-200 bg-slate-50/30 flex flex-col justify-between space-y-3 transition-colors"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900">{job.title}</h4>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold shrink-0">
                      {job.employment_type || "Full Time"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{job.company} • {job.location}</p>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800">
                    {job.salary_min && job.salary_max
                      ? `${job.salary_currency || "₹"} ${job.salary_min} - ${job.salary_max}`
                      : "Competitive"}
                  </span>
                  <Link
                    to={`/candidate/jobs/${job.id}`}
                    className="text-xs font-bold text-blue-600 hover:text-blue-700"
                  >
                    Apply →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
