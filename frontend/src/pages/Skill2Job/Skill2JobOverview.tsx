import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { RefreshCw, AlertCircle } from "lucide-react";
import { skill2jobApi } from "../../api/skill2job";
import type { Skill2JobOverview } from "../../types/skill2job";
import CareerHero from "./components/CareerHero";
import CareerReadinessCard from "./components/CareerReadinessCard";
import LocalOpportunities from "./components/LocalOpportunities";
import SkillGapIntelligence from "./components/SkillGapIntelligence";
import OpportunityUnlockCard from "./components/OpportunityUnlockCard";
import TimeToReadyMini from "./components/TimeToReadyMini";
import LearningProgressCard from "./components/LearningProgressCard";
import CareerInsightCard from "./components/CareerInsightCard";
import NextActionCard from "./components/NextActionCard";
import { CardSkeleton, ReadinessSkeleton, JobCardSkeleton, Skeleton } from "./components/Skeletons";
import { extractErrorMessage } from "./components/helpers";

const TAB_ROUTES: Record<string, string> = {
  perception: "/skill2job/profile",
  jobs: "/skill2job/jobs",
  match: "/skill2job/jobs",
  gaps: "/skill2job/skill-gaps",
  learning: "/skill2job/learning",
  ttr: "/skill2job/time-to-ready",
};

export default function Skill2JobOverview({
  onNavigate,
}: {
  onNavigate?: (tab: string) => void;
}) {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<Skill2JobOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const go = useCallback(
    (tab: string) => {
      const route = TAB_ROUTES[tab];
      if (route) {
        navigate(route);
        return;
      }
      onNavigate?.(tab);
    },
    [navigate, onNavigate]
  );

  const fetchOverview = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await skill2jobApi.getOverview();
      setOverview(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      await skill2jobApi.buildDossier();
      await skill2jobApi.runMatching();
      await skill2jobApi.analyzeSkillGaps();
      await fetchOverview();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleViewGap = () => {
    go("gaps");
  };

  // ─── Loading State ───────────────────────────────────────────────
  if (loading && !overview) {
    return (
      <div className="space-y-6">
        <div className="panel-dark relative overflow-hidden p-8">
          <div className="space-y-3">
            <Skeleton className="h-4 w-40 bg-white/20" />
            <Skeleton className="h-8 w-64 bg-white/25" />
            <Skeleton className="h-4 w-96 max-w-full bg-white/15" />
            <Skeleton className="h-3 w-80 max-w-full bg-white/15" />
          </div>
        </div>
        <ReadinessSkeleton />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <JobCardSkeleton key={i} />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <CardSkeleton lines={4} />
          <CardSkeleton lines={4} />
        </div>
      </div>
    );
  }

  // ─── Error State ─────────────────────────────────────────────────
  if (error && !overview) {
    return (
      <div className="card border-red-200/80 p-10 text-center animate-scale-in">
        <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-red-50 text-red-500">
          <AlertCircle className="h-6 w-6" aria-hidden="true" />
        </span>
        <h3 className="section-title text-red-700">
          Unable to load Career Intelligence
        </h3>
        <p className="mt-2 text-sm text-red-600">{error}</p>
        <button onClick={fetchOverview} className="btn-primary mt-5">
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Retry
        </button>
      </div>
    );
  }

  // ─── Empty State (No Profile) ────────────────────────────────────
  if (overview && !overview.profile.connected) {
    return (
      <div className="space-y-6 animate-fade-up">
        <CareerHero overview={overview} onAnalyze={handleAnalyze} analyzing={analyzing} />
        <div className="empty-state px-6 py-14">
          <div className="mb-4 text-4xl">&#127891;</div>
          <h3 className="text-lg font-semibold text-gray-900">
            Your career intelligence starts here.
          </h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
            Complete your profile to discover relevant jobs and personalized skill gaps.
          </p>
          <button onClick={() => go("perception")} className="btn-primary mt-5">
            Complete Profile
          </button>
        </div>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Hero */}
      <CareerHero overview={overview} onAnalyze={handleAnalyze} analyzing={analyzing} />

      {/* Error banner (non-blocking) */}
      {error && (
        <div className="error-banner" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            aria-label="Dismiss error"
            className="ml-auto -mr-1 rounded px-1 text-red-500 transition-colors hover:text-red-700 focus-visible:ring-0"
          >
            &times;
          </button>
        </div>
      )}

      {/* Career Readiness */}
      <CareerReadinessCard overview={overview} />

      {/* Local Opportunities */}
      <LocalOpportunities overview={overview} onViewGap={handleViewGap} />

      {/* Skill Gaps + Opportunity Unlock */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SkillGapIntelligence overview={overview} />
        <OpportunityUnlockCard overview={overview} />
      </div>

      {/* Time to Ready + Learning Progress */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TimeToReadyMini overview={overview} />
        <LearningProgressCard overview={overview} />
      </div>

      {/* Career Insight + Next Action */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CareerInsightCard overview={overview} />
        <NextActionCard overview={overview} />
      </div>

      {/* Refresh */}
      <div className="flex justify-center pt-2">
        <button
          onClick={fetchOverview}
          disabled={loading}
          className="btn-ghost btn-sm"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          Refresh Analysis
        </button>
      </div>
    </div>
  );
}
