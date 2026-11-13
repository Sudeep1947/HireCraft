import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Briefcase,
  Clock,
  GitBranch,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  Rocket,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { skill2jobApi } from "../../api/skill2job";
import type { Skill2JobOverview } from "../../types/skill2job";
import { useAuth } from "../../hooks/useAuth";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/skill2job", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/skill2job/profile", label: "My Profile", icon: UserRound },
  { to: "/skill2job/jobs", label: "Local Jobs", icon: Briefcase },
  { to: "/skill2job/skill-gaps", label: "Skill Gaps", icon: ListChecks },
  { to: "/skill2job/skill-graph", label: "Skill Graph", icon: GitBranch },
  { to: "/skill2job/opportunities", label: "Opportunities", icon: Rocket },
  { to: "/skill2job/learning", label: "Learning Path", icon: GraduationCap },
  { to: "/skill2job/time-to-ready", label: "Time to Ready", icon: Clock },
  { to: "/skill2job/skill-proof", label: "Skill Proof", icon: ShieldCheck },
];

const READINESS_STYLES: Record<string, { label: string; cls: string }> = {
  excellent: { label: "Excellent", cls: "badge-success" },
  strong: { label: "Strong", cls: "badge-success" },
  competitive: { label: "Competitive", cls: "badge-info" },
  developing: { label: "Developing", cls: "badge-warning" },
  needs_work: { label: "Needs Work", cls: "badge-warning" },
  locked: { label: "Locked", cls: "badge-neutral" },
};

function readinessStyleFor(score: number): { label: string; cls: string } {
  if (score >= 85) return READINESS_STYLES.excellent!;
  if (score >= 70) return READINESS_STYLES.strong!;
  if (score >= 55) return READINESS_STYLES.competitive!;
  if (score >= 40) return READINESS_STYLES.developing!;
  if (score > 0) return READINESS_STYLES.needs_work!;
  return READINESS_STYLES.locked!;
}

export default function Skill2JobLayout() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<Skill2JobOverview | null>(null);

  useEffect(() => {
    skill2jobApi
      .getOverview()
      .then(setOverview)
      .catch(() => undefined);
  }, []);

  const readiness = overview?.readiness;
  const readinessStyle = readiness ? readinessStyleFor(readiness.score) : null;

  return (
    <div className="space-y-6 animate-fade-up">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <div className="panel-dark relative overflow-hidden p-6 sm:p-8">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_85%_0%,rgba(255,255,255,0.18),transparent)]"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-white/10 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="section-label text-primary-200">
              Skill2Job · Candidate Career Intelligence
            </p>
            <h1 className="mt-1.5 font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
              {user?.full_name ? `${user.full_name.split(" ")[0]}'s Career Hub` : "Career Hub"}
            </h1>
            <p className="mt-2 max-w-xl text-sm text-primary-100">
              Perceive your skills, discover matched roles, close gaps, and follow a grounded plan to your next opportunity.
            </p>
          </div>
          {readinessStyle && (
            <div className="rounded-2xl border border-white/20 bg-white/10 px-5 py-4 text-right backdrop-blur">
              <p className="section-label text-primary-200">Career Readiness</p>
              <p className={`mt-2 text-sm ${readinessStyle.cls}`}>
                {readinessStyle.label} · {Math.round(readiness!.score)}%
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ─── Body ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Nav */}
        <nav
          aria-label="Career Intelligence"
          className="shrink-0 lg:w-60"
        >
          <div className="card flex flex-row gap-1.5 overflow-x-auto p-2 lg:sticky lg:top-4 lg:flex-col lg:gap-1 lg:overflow-visible">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all duration-200 ${
                    isActive
                      ? "bg-brand-gradient font-semibold text-white shadow-glow-sm"
                      : "font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`
                }
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
