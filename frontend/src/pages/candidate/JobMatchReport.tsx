import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Target } from "lucide-react";

import { MatchScoreCard } from "../../components/screening/MatchScoreCard";
import { SkillGapReport } from "../../components/screening/SkillGapReport";
import { useToast } from "../../contexts/ToastContext";
import { getMyMatch } from "../../api/screening";
import type { CandidateMatchReport } from "../../types/screening";

export function CandidateJobMatchReport() {
  const { id } = useParams<{ id: string }>();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<CandidateMatchReport | null>(null);

  useEffect(() => {
    if (!id) return;
    async function load() {
      try {
        const data = await getMyMatch(id!);
        setReport(data);
      } catch {
        addToast("Failed to load match report", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, addToast]);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-64" />
        <div className="skeleton h-56 w-full" />
        <div className="skeleton h-44 w-full" />
      </div>
    );

  if (!report || !report.screening) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div>
          <h1 className="page-title">My Match Report</h1>
          <p className="page-subtitle">See how you match against this job</p>
        </div>
        <div className="empty-state">
          <Target className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm text-gray-500">No screening data available for this job yet. Apply and wait for the recruiter to run screening.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">My Match Report</h1>
        <p className="page-subtitle">Detailed breakdown of your match for {report.job_title}</p>
      </div>

      <MatchScoreCard
        screening={report.screening}
        candidateName={report.candidate_name}
        jobTitle={report.job_title}
      />

      {report.skill_gap && <SkillGapReport skillGap={report.skill_gap} />}

      {report.improvement_suggestions && report.improvement_suggestions.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-3">General Improvement Suggestions</h3>
          <ul className="space-y-1.5">
            {report.improvement_suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="mt-0.5 text-emerald-500">&#x2713;</span> {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
