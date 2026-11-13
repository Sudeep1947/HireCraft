import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Award,
  BadgeCheck,
  BarChart3,
  Bot,
  BrainCircuit,
  ChevronRight,
  ClipboardList,
  Code2,
  Eye,
  FileSearch,
  GitBranch,
  Globe,
  Database,
  Layers,
  LineChart,
  Lock,
  Menu,
  MessageSquareText,
  Scale,
  Server,
  ShieldCheck,
  Sparkles,
  Target,
  UserCheck,
  Users,
  X,
  Zap,
} from "lucide-react";

// ─── Shared bits ───────────────────────────────────────────────

const NAV_LINKS = [
  { label: "Platform", href: "#platform" },
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Responsible AI", href: "#responsible-ai" },
  { label: "Technology", href: "#technology" },
];

function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <Link to="/" className="group flex items-center gap-2.5" aria-label="AI Hiring Copilot home">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-gradient shadow-glow-sm transition-transform duration-200 group-hover:scale-105">
        <Zap className="h-5 w-5 text-white" aria-hidden="true" />
      </span>
      <span
        className={`font-display text-lg font-bold tracking-tight ${
          dark ? "text-white" : "text-gray-900"
        }`}
      >
        AI Hiring Copilot
      </span>
    </Link>
  );
}

function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200/70 bg-white/75 backdrop-blur-xl">
      <nav
        className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8"
        aria-label="Main navigation"
      >
        <Logo />

        <ul className="hidden items-center gap-1 lg:flex">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-lg px-3 py-2 text-sm font-medium text-gray-600 transition-all duration-200 hover:bg-primary-50 hover:text-primary-700"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="hidden items-center gap-2 lg:flex">
          <Link to="/login" className="btn-ghost btn-md">
            Sign In
          </Link>
          <Link to="/login" className="btn-primary btn-md group">
            Get Started
            <ChevronRight
              className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-gray-600 transition-colors hover:bg-primary-50 hover:text-primary-700 lg:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <X className="h-6 w-6" aria-hidden="true" />
          ) : (
            <Menu className="h-6 w-6" aria-hidden="true" />
          )}
        </button>
      </nav>

      {open && (
        <div className="border-t border-gray-200/70 bg-white/95 backdrop-blur-xl lg:hidden animate-fade-in">
          <div className="space-y-1 px-4 py-4">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-base font-medium text-gray-700 transition-colors hover:bg-primary-50 hover:text-primary-700"
              >
                {link.label}
              </a>
            ))}
            <div className="flex gap-3 pt-3">
              <Link
                to="/login"
                onClick={() => setOpen(false)}
                className="btn-secondary btn-md flex-1"
              >
                Sign In
              </Link>
              <Link
                to="/login"
                onClick={() => setOpen(false)}
                className="btn-primary btn-md flex-1"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}

// ─── Hero ──────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative overflow-hidden bg-brand-gradient-strong">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(65%_45%_at_50%_0%,rgba(0,210,255,0.12),transparent)]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -top-28 left-1/2 h-96 w-[46rem] -translate-x-1/2 rounded-full bg-gradient-to-r from-cyan-500/15 via-blue-600/20 to-violet-600/20 blur-3xl animate-float"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -bottom-32 -left-24 h-72 w-72 rounded-full bg-[#060d2e]/80 blur-3xl animate-float [animation-delay:1.5s]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -right-24 top-1/3 h-72 w-72 rounded-full bg-[#00d2ff]/10 blur-3xl animate-float [animation-delay:3s]"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-7xl px-4 pb-24 pt-20 sm:px-6 sm:pt-28 lg:px-8">
        <div className="mx-auto max-w-3xl text-center animate-entrance">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-4 py-1.5 text-xs font-semibold text-white shadow-glow-sm backdrop-blur">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            AI-Powered Talent Intelligence &amp; Recruitment Platform
          </span>
          <h1 className="mt-7 font-display text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl">
            Transform Recruitment with{" "}
            <span className="bg-gradient-to-r from-sky-300 via-primary-200 to-violet-300 bg-clip-text text-transparent">
              Responsible AI
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-primary-100">
            Screen candidates faster, understand AI decisions, reduce hiring bias, conduct intelligent
            assessments, and make data-driven hiring decisions from one unified platform.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              to="/login"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-white px-8 py-3.5 text-base font-semibold text-primary-800 shadow-lg shadow-primary-950/30 transition-all duration-200 hover:bg-primary-50 hover:shadow-glow focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-700 sm:w-auto"
            >
              Get Started
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </Link>
            <a
              href="#features"
              className="inline-flex w-full items-center justify-center rounded-xl border border-white/30 bg-white/10 px-8 py-3.5 text-base font-semibold text-white backdrop-blur transition-all duration-200 hover:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-700 sm:w-auto"
            >
              Explore Platform
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Problem → Solution ────────────────────────────────────────

const PROBLEMS = [
  "Manual resume screening",
  "Time-consuming candidate comparison",
  "Subjective evaluation",
  "Hidden AI decisions",
  "Potential hiring bias",
  "Unstructured interviews",
  "Scattered recruitment analytics",
];

const SOLUTIONS = [
  "AI Resume Screening",
  "Candidate Intelligence",
  "Explainable AI",
  "Fairness & Bias Detection",
  "AI Interview Intelligence",
  "Technical Assessments",
  "Recruitment Analytics",
  "Agentic AI HR Assistant",
];

function ProblemSolution() {
  return (
    <section id="platform" className="relative bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center animate-fade-up">
          <h2 className="font-display text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            From recruitment bottlenecks to intelligent hiring
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Traditional recruitment slows teams down and hides how decisions are made. Our platform
            replaces it end to end.
          </p>
          <div className="divider mx-auto mt-6 w-24" aria-hidden="true" />
        </div>

        <div className="mt-14 grid items-start gap-6 lg:grid-cols-[1fr_auto_1fr]">
          {/* Problem */}
          <div className="card p-7 animate-fade-up [animation-delay:60ms]">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-red-50 p-2.5 text-red-600 ring-1 ring-inset ring-red-100">
                <Target className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="section-title">The Problem</h3>
            </div>
            <ul className="mt-5 space-y-3">
              {PROBLEMS.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-gray-700">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Arrow */}
          <div className="flex items-center justify-center lg:h-full lg:min-h-[280px]">
            <div className="flex h-14 w-14 rotate-90 items-center justify-center rounded-full bg-brand-gradient text-white shadow-glow transition-transform duration-300 hover:scale-105 lg:rotate-0">
              <ChevronRight className="h-6 w-6" aria-hidden="true" />
            </div>
          </div>

          {/* Solution */}
          <div className="panel-brand p-7 shadow-soft animate-fade-up [animation-delay:120ms]">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-gradient p-2.5 text-white shadow-soft">
                <BrainCircuit className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="section-title">The AI Solution</h3>
            </div>
            <ul className="mt-5 space-y-3">
              {SOLUTIONS.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm font-medium text-gray-800">
                  <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Features ──────────────────────────────────────────────────

const FEATURES = [
  {
    icon: FileSearch,
    title: "AI Resume Intelligence",
    description:
      "Automatically parse resumes and extract skills, experience, education, projects, and certifications into structured candidate profiles.",
  },
  {
    icon: Layers,
    title: "AI Candidate Ranking",
    description:
      "Match candidates against job requirements and generate explainable ranking scores for every applicant.",
  },
  {
    icon: Eye,
    title: "Explainable AI",
    description:
      "Show recruiters exactly WHY a candidate received a particular score — every decision is transparent and traceable.",
  },
  {
    icon: Scale,
    title: "Responsible AI",
    description:
      "Detect potential bias and evaluate fairness across recruitment decisions before they impact people.",
  },
  {
    icon: MessageSquareText,
    title: "AI Interview Intelligence",
    description:
      "Generate technical questions, MCQs, aptitude tests, coding challenges, SQL tasks, behavioral prompts, and system design rounds.",
  },
  {
    icon: Code2,
    title: "AI Assessments",
    description:
      "Evaluate candidates on technical skills, problem solving, coding, aptitude, and SQL with auto-scored assessments.",
  },
  {
    icon: BarChart3,
    title: "Recruitment Analytics",
    description:
      "Track hiring funnel health, recruiter performance, skill demand, hiring trends, and interview outcomes.",
  },
  {
    icon: Bot,
    title: "Agentic AI HR Assistant",
    description:
      "Use natural language to search candidates, analyze hiring data, generate reports, explain scores, and run workflows.",
  },
];

function Features() {
  return (
    <section id="features" className="relative bg-gray-50/70 py-20 sm:py-24">
      <div
        className="pointer-events-none absolute inset-0 bg-brand-gradient-soft opacity-50"
        aria-hidden="true"
      />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center animate-fade-up">
          <h2 className="font-display text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Everything you need to hire smarter
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Eight integrated AI capabilities covering the full recruitment lifecycle.
          </p>
          <div className="divider mx-auto mt-6 w-24" aria-hidden="true" />
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature, i) => (
            <article
              key={feature.title}
              className={`card card-hover group relative flex flex-col p-6 animate-fade-up [animation-delay:${60 + i * 50}ms]`}
            >
              <span className="text-xs font-bold tracking-widest text-primary-400">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="mt-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary-50 text-primary-600 ring-1 ring-inset ring-primary-100 transition-all duration-300 group-hover:bg-brand-gradient group-hover:text-white group-hover:shadow-glow">
                <feature.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-base font-semibold text-gray-900">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">{feature.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── How It Works ──────────────────────────────────────────────

const STEPS = [
  {
    icon: ClipboardList,
    title: "Create Job",
    description: "Recruiter creates a job description.",
  },
  {
    icon: Users,
    title: "Candidates Apply",
    description: "Candidates upload their resumes.",
  },
  {
    icon: BrainCircuit,
    title: "AI Screening",
    description: "AI parses, analyzes, and ranks candidates.",
  },
  {
    icon: Code2,
    title: "AI Assessment & Interview",
    description: "Candidates complete technical assessments and interviews.",
  },
  {
    icon: LineChart,
    title: "Data-Driven Hiring",
    description:
      "Recruiters and HR receive AI insights, fairness reports, interview results, analytics, and recommendations.",
  },
];

function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center animate-fade-up">
          <h2 className="font-display text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            How it works
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            A connected five-stage pipeline from job posting to confident hiring decisions.
          </p>
          <div className="divider mx-auto mt-6 w-24" aria-hidden="true" />
        </div>

        <ol className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className={`card relative flex flex-col p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg animate-fade-up [animation-delay:${60 + i * 70}ms]`}
            >
              <div className="flex items-center justify-between">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-soft">
                  <step.icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="font-display text-4xl font-extrabold text-primary-100" aria-hidden="true">
                  {i + 1}
                </span>
              </div>
              <h3 className="mt-4 text-sm font-bold uppercase tracking-wide text-primary-700">
                Step {i + 1}: {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">{step.description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ─── Role cards ────────────────────────────────────────────────

const ROLES = [
  {
    icon: UserCheck,
    accent: "bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100 group-hover:bg-emerald-100",
    name: "Candidate",
    description:
      "Build your profile, apply for jobs, practice interviews, complete assessments, and understand your career strengths.",
    cta: "Candidate Experience",
  },
  {
    icon: Users,
    accent: "bg-blue-50 text-blue-600 ring-1 ring-inset ring-blue-100 group-hover:bg-blue-100",
    name: "Recruiter",
    description: "Find, screen, rank, assess, and interview candidates efficiently.",
    cta: "Recruiter Experience",
  },
  {
    icon: ShieldCheck,
    accent: "bg-purple-50 text-purple-600 ring-1 ring-inset ring-purple-100 group-hover:bg-purple-100",
    name: "HR",
    description: "Monitor hiring performance, fairness, workforce analytics, and recruitment outcomes.",
    cta: "HR Intelligence",
  },
  {
    icon: Lock,
    accent: "bg-red-50 text-red-600 ring-1 ring-inset ring-red-100 group-hover:bg-red-100",
    name: "Admin",
    description: "Manage users, organizations, security, audit logs, and platform operations.",
    cta: "Platform Administration",
  },
];

function RoleExperience() {
  return (
    <section className="bg-gray-50/70 py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center animate-fade-up">
          <h2 className="font-display text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            One platform, four tailored experiences
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Every role gets purpose-built tooling backed by the same responsible AI core.
          </p>
          <div className="divider mx-auto mt-6 w-24" aria-hidden="true" />
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {ROLES.map((role, i) => (
            <article
              key={role.name}
              className={`card card-hover group flex flex-col p-6 animate-fade-up [animation-delay:${60 + i * 70}ms]`}
            >
              <span
                className={`flex h-11 w-11 items-center justify-center rounded-xl p-2.5 transition-colors duration-300 ${role.accent}`}
              >
                <role.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">{role.name}</h3>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-gray-600">{role.description}</p>
              <Link
                to="/register"
                className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-primary-600 transition-colors hover:text-primary-700"
                aria-label={`${role.cta} — create an account`}
              >
                {role.cta}
                <ChevronRight
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Responsible AI ────────────────────────────────────────────

const TRUST_PILLARS = [
  {
    icon: Eye,
    title: "Explainability",
    description: "Every score comes with human-readable reasoning, not a black box.",
  },
  {
    icon: Scale,
    title: "Fairness",
    description: "Continuous bias detection and fairness metrics across hiring stages.",
  },
  {
    icon: GitBranch,
    title: "Auditability",
    description: "Complete audit trails for screening, scoring, and decisions.",
  },
  {
    icon: Globe,
    title: "Transparency",
    description: "Candidates and recruiters see how evaluations are performed.",
  },
  {
    icon: UserCheck,
    title: "Human Oversight",
    description: "Recommendations, never verdicts — people stay in control.",
  },
];

function ResponsibleAI() {
  return (
    <section id="responsible-ai" className="relative overflow-hidden bg-gray-950 py-20 sm:py-24">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(50%_50%_at_50%_0%,rgba(85,87,230,0.28),transparent)]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -bottom-32 left-1/2 h-80 w-[36rem] -translate-x-1/2 rounded-full bg-violet-500/20 blur-3xl animate-float"
        aria-hidden="true"
      />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center animate-fade-up">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary-400/30 bg-primary-400/10 px-3.5 py-1.5 text-xs font-semibold text-primary-300 backdrop-blur">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Responsible AI at the Core
          </span>
          <h2 className="mt-6 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            AI automation with human judgment
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-gray-300">
            The platform combines <strong className="font-semibold text-white">AI Automation</strong> +{" "}
            <strong className="font-semibold text-white">Explainable AI</strong> +{" "}
            <strong className="font-semibold text-white">Fairness</strong> +{" "}
            <strong className="font-semibold text-white">Human Decision Making</strong>.
          </p>
          <blockquote className="mx-auto mt-8 max-w-2xl rounded-2xl border border-white/10 bg-white/5 px-6 py-5 backdrop-blur-xl shadow-glow-sm">
            <p className="text-base font-medium italic text-gray-100 sm:text-lg">
              “AI assists hiring decisions. Humans remain responsible for final hiring decisions.”
            </p>
          </blockquote>
        </div>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {TRUST_PILLARS.map((pillar, i) => (
            <div
              key={pillar.title}
              className={`rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-xl transition-all duration-300 hover:border-primary-400/40 hover:bg-white/[0.07] animate-fade-up [animation-delay:${60 + i * 60}ms]`}
            >
              <span className="inline-flex rounded-xl bg-primary-400/10 p-2.5 text-primary-300 ring-1 ring-inset ring-primary-400/20">
                <pillar.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-3 text-sm font-semibold text-white">{pillar.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-gray-400">{pillar.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Technology ────────────────────────────────────────────────

const STACK = [
  {
    icon: Globe,
    category: "Frontend",
    items: ["React", "TypeScript", "Tailwind CSS"],
  },
  {
    icon: Server,
    category: "Backend",
    items: ["FastAPI", "Python", "SQLAlchemy"],
  },
  {
    icon: Database,
    category: "Database",
    items: ["PostgreSQL"],
  },
  {
    icon: BrainCircuit,
    category: "AI & ML",
    items: ["Sentence Transformers", "FAISS", "SHAP", "LIME", "LLM", "RAG", "LangGraph"],
  },
  {
    icon: Layers,
    category: "Infrastructure",
    items: ["Docker", "Redis", "Celery"],
  },
];

function Technology() {
  return (
    <section id="technology" className="bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center animate-fade-up">
          <h2 className="font-display text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Built on a Modern AI Engineering Stack
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Production-grade technology chosen for reliability, explainability, and scale.
          </p>
          <div className="divider mx-auto mt-6 w-24" aria-hidden="true" />
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {STACK.map((layer, i) => (
            <div
              key={layer.category}
              className={`card card-hover p-6 animate-fade-up [animation-delay:${60 + i * 60}ms]`}
            >
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-soft">
                  <layer.icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <h3 className="text-sm font-bold uppercase tracking-wide text-gray-900">{layer.category}</h3>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {layer.items.map((item) => (
                  <span key={item} className="chip">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Platform statistics (capability-based, no fabricated data) ──

const PLATFORM_STATS = [
  { icon: BrainCircuit, value: "8", label: "Integrated AI Capabilities" },
  { icon: ClipboardList, value: "5", label: "Connected Hiring Stages" },
  { icon: Users, value: "4", label: "Purpose-Built Role Experiences" },
  { icon: ShieldCheck, value: "100%", label: "Human Oversight on Decisions" },
];

function Stats() {
  return (
    <section className="relative border-y border-primary-100/70 bg-brand-gradient-soft py-14">
      <dl className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-4 sm:px-6 lg:grid-cols-4 lg:px-8">
        {PLATFORM_STATS.map((stat, i) => (
          <div
            key={stat.label}
            className={`flex flex-col items-center text-center animate-fade-up [animation-delay:${i * 60}ms]`}
          >
            <dt className="order-2 mt-2.5 flex items-center gap-1.5 text-sm font-medium text-gray-600">
              <stat.icon className="h-4 w-4 text-primary-500" aria-hidden="true" />
              {stat.label}
            </dt>
            <dd className="order-1 font-display text-4xl font-extrabold tracking-tight text-gradient">
              {stat.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

// ─── Final CTA ─────────────────────────────────────────────────

function FinalCTA() {
  return (
    <section className="bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="panel-dark relative overflow-hidden rounded-3xl px-6 py-16 text-center sm:px-16 animate-scale-in">
          <div
            className="pointer-events-none absolute inset-0 opacity-40 [background-image:radial-gradient(rgba(255,255,255,0.14)_1px,transparent_1px)] [background-size:22px_22px]"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -top-24 left-1/2 h-64 w-[32rem] -translate-x-1/2 rounded-full bg-gradient-to-r from-cyan-500/20 to-violet-600/20 blur-3xl"
            aria-hidden="true"
          />
          <div className="relative mx-auto max-w-2xl">
            <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Build a Smarter, Fairer Hiring Process
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-primary-100">
              Bring candidate intelligence, responsible AI, assessments, interviews, and recruitment
              analytics together in one platform.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                to="/login"
                className="inline-flex w-full items-center justify-center rounded-xl bg-white px-8 py-3.5 text-base font-semibold text-primary-800 shadow-lg transition-all duration-200 hover:bg-primary-50 hover:shadow-glow focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-800 sm:w-auto"
              >
                Get Started
              </Link>
              <Link
                to="/register"
                className="inline-flex w-full items-center justify-center rounded-xl border border-white/30 bg-white/10 px-8 py-3.5 text-base font-semibold text-white backdrop-blur transition-all duration-200 hover:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-800 sm:w-auto"
              >
                Create Account
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Footer ────────────────────────────────────────────────────

const FOOTER_SECTIONS = [
  {
    heading: "Platform",
    links: [
      { label: "Candidate Intelligence", href: "#platform" },
      { label: "AI Screening", href: "#features" },
      { label: "Assessments", href: "#features" },
      { label: "Interviews", href: "#how-it-works" },
      { label: "Analytics", href: "#features" },
    ],
  },
  {
    heading: "Responsible AI",
    links: [
      { label: "Explainability", href: "#responsible-ai" },
      { label: "Fairness", href: "#responsible-ai" },
      { label: "Transparency", href: "#responsible-ai" },
      { label: "Human Oversight", href: "#responsible-ai" },
    ],
  },
  {
    heading: "Access",
    links: [
      { label: "Candidate", href: "/login" },
      { label: "Recruiter", href: "/login" },
      { label: "HR", href: "/login" },
      { label: "Admin", href: "/login" },
    ],
  },
];

function Footer() {
  return (
    <footer className="bg-gray-950" role="contentinfo">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_repeat(3,1fr)]">
          <div>
            <Logo dark />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-gray-400">
              AI-assisted hiring with transparency and human oversight.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-gray-400 backdrop-blur">
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              Enterprise-grade security &amp; audit logging
            </div>
          </div>

          {FOOTER_SECTIONS.map((section) => (
            <nav key={section.heading} aria-label={`Footer — ${section.heading}`}>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-white">{section.heading}</h3>
              <ul className="mt-4 space-y-2.5">
                {section.links.map((link) =>
                  link.href.startsWith("/") ? (
                    <li key={link.label}>
                      <Link
                        to={link.href}
                        className="text-sm text-gray-400 transition-colors hover:text-white"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ) : (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        className="text-sm text-gray-400 transition-colors hover:text-white"
                      >
                        {link.label}
                      </a>
                    </li>
                  ),
                )}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-gray-800 pt-8 sm:flex-row">
          <p className="text-sm text-gray-500">© {new Date().getFullYear()} AI Hiring Copilot. All rights reserved.</p>
          <p className="flex items-center gap-1.5 text-xs text-gray-500">
            <Award className="h-3.5 w-3.5" aria-hidden="true" />
            Responsible AI by design
          </p>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ──────────────────────────────────────────────────────

export function LandingPage() {
  // Smooth-scroll for in-page anchors without global CSS side effects.
  useEffect(() => {
    document.documentElement.style.scrollBehavior = "smooth";
    return () => {
      document.documentElement.style.scrollBehavior = "";
    };
  }, []);

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main>
        <Hero />
        <ProblemSolution />
        <Features />
        <HowItWorks />
        <RoleExperience />
        <ResponsibleAI />
        <Technology />
        <Stats />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
