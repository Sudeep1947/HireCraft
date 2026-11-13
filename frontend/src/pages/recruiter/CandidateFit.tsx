import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useToast } from "../../contexts/ToastContext";
import { getJobCandidateFit } from "../../api/screening";
import type {
  FitEvidenceItem,
  FitRequirementResult,
  JobFitResponse,
  MatchStatus,
} from "../../types/screening";

const STATUS_STYLES: Record<MatchStatus, string> = {
  match: "badge-success",
  partial: "badge-warning",
  gap: "badge-danger",
  unknown: "badge-neutral",
};

const CLASSIFICATION_STYLES: Record<string, string> = {
  strong_match: "badge-success",
  good_match: "badge-success",
  partial_match: "badge-warning",
  low_match: "badge-danger",
  insufficient_evidence: "badge-neutral",
};

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function EvidenceList({ evidence }: { evidence: FitEvidenceItem[] }) {
  if (evidence.length === 0) return null;
  return (
    <ul className="mt-2 space-y-2">
      {evidence.map((item, i) => (
        <li key={i} className="rounded-lg bg-gray-50 p-3">
          <div className="flex items-center gap-2">
            <span className="badge badge-primary">
              {formatLabel(item.source)}
            </span>
            {item.context && (
              <span className="text-xs text-gray-500">{item.context}</span>
            )}
          </div>
          <blockquote className="mt-1 border-l-2 border-gray-300 pl-2 text-sm italic text-gray-700">
            "{item.quote}"
          </blockquote>
        </li>
      ))}
    </ul>
  );
}

function RequirementRow({ requirement }: { requirement: FitRequirementResult }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const hasEvidence = requirement.evidence.length > 0;
  return (
    <div className="border-b border-gray-100 py-3 last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`badge uppercase ${STATUS_STYLES[requirement.status]}`}
        >
          {requirement.status}
        </span>
        <span className="text-sm font-medium text-gray-900">
          {requirement.requirement}
        </span>
        {requirement.level === "preferred" && (
          <span className="badge badge-info">
            preferred
          </span>
        )}
        {requirement.category && (
          <span className="text-xs text-gray-400">{requirement.category}</span>
        )}
        {hasEvidence && (
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className="ml-auto text-xs font-medium text-primary-600 hover:text-primary-800"
          >
            {showEvidence ? "Hide evidence" : `Evidence (${requirement.evidence.length})`}
          </button>
        )}
      </div>
      <p className="mt-1 text-sm text-gray-600">{requirement.reason}</p>
      {showEvidence && hasEvidence && <EvidenceList evidence={requirement.evidence} />}
    </div>
  );
}

export function CandidateFit() {
  const { id, candidateId } = useParams<{ id: string; candidateId: string }>();
  const { addToast } = useToast();
  const [fit, setFit] = useState<JobFitResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id || !candidateId) return;
    async function load() {
      try {
        const data = await getJobCandidateFit(id!, candidateId!);
        setFit(data);
      } catch {
        addToast("Failed to load job fit analysis", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, candidateId, addToast]);

  if (loading)
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading job fit analysis">
        <div className="skeleton h-9 w-64" />
        <div className="skeleton h-40 w-full" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="skeleton h-96 w-full lg:col-span-2" />
          <div className="skeleton h-96 w-full" />
        </div>
      </div>
    );
  if (!fit)
    return (
      <div className="empty-state mt-10 space-y-4">
        <p className="text-gray-500">Fit analysis unavailable.</p>
        <Link
          to={`/recruiter/jobs/${id}/applicants`}
          className="text-sm font-medium text-primary-600 hover:text-primary-800"
        >
          Back to applicants
        </Link>
      </div>
    );

  const classificationStyle =
    CLASSIFICATION_STYLES[fit.overall.classification] || "badge-neutral";

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Job Fit: {fit.candidate_name}</h1>
          <p className="page-subtitle">{fit.job_title}</p>
          <Link
            to={`/recruiter/jobs/${id}/candidates/${candidateId}/intelligence`}
            className="text-sm font-medium text-primary-600 hover:text-primary-800"
          >
            Full candidate intelligence →
          </Link>
        </div>
        <Link
          to={`/recruiter/jobs/${id}/applicants`}
          className="btn-secondary btn-sm"
        >
          Back to applicants
        </Link>
      </div>

      <div className="card p-6">
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`badge px-3 py-1 text-sm ${classificationStyle}`}
          >
            {formatLabel(fit.overall.classification)}
          </span>
          <span className="font-display text-2xl font-bold text-gray-900">{fit.overall.score}</span>
          <span className="text-sm text-gray-400">/ 100</span>
          {fit.cached && (
            <span className="badge badge-neutral ml-auto">
              cached result
            </span>
          )}
        </div>
        <p className="mt-3 text-sm text-gray-700">{fit.overall.summary}</p>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(fit.overall.breakdown.components).map(([name, value]) => (
            <div key={name} className="rounded-xl bg-gray-50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                {formatLabel(name)}
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900">
                {Math.round(value * 100)}%
              </p>
              <p className="text-xs text-gray-400">
                weight {Math.round((fit.overall.breakdown.weights[name] || 0) * 100)}%
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card p-6">
            <h2 className="section-title mb-2">Requirements</h2>
            <div>
              {fit.requirements.map((req, i) => (
                <RequirementRow key={i} requirement={req} />
              ))}
            </div>
          </div>

          {fit.responsibilities.length > 0 && (
            <div className="card p-6">
              <h2 className="section-title mb-2">Responsibilities</h2>
              {fit.responsibilities.map((resp, i) => (
                <ResponsibilityRow key={i} responsibility={resp} />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="card p-6">
            <h2 className="section-title mb-2">Experience</h2>
            <span
              className={`badge uppercase ${STATUS_STYLES[fit.experience_alignment.status]}`}
            >
              {fit.experience_alignment.status}
            </span>
            <dl className="mt-3 space-y-1.5 text-sm">
              {fit.experience_alignment.required_years != null && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Required</dt>
                  <dd className="font-medium text-gray-900">
                    {fit.experience_alignment.required_years} yrs
                  </dd>
                </div>
              )}
              {fit.experience_alignment.relevant_years != null && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Relevant</dt>
                  <dd className="font-medium text-gray-900">
                    {fit.experience_alignment.relevant_years} yrs
                  </dd>
                </div>
              )}
              {fit.experience_alignment.total_years != null && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Total</dt>
                  <dd className="font-medium text-gray-900">
                    {fit.experience_alignment.total_years} yrs
                  </dd>
                </div>
              )}
            </dl>
            <p className="mt-2 text-sm text-gray-600">{fit.experience_alignment.reason}</p>
          </div>

          <div className="card p-6">
            <h2 className="section-title mb-2">Skill Gaps</h2>
            <SkillGapGroup label="Strengths" skills={fit.skill_gaps.strengths} tone="green" />
            <SkillGapGroup label="Partial" skills={fit.skill_gaps.partial} tone="yellow" />
            <SkillGapGroup label="Gaps" skills={fit.skill_gaps.gaps} tone="red" />
            <SkillGapGroup label="Unknown" skills={fit.skill_gaps.unknown} tone="gray" />
          </div>

          <div className="card p-6">
            <h2 className="section-title mb-2">About this analysis</h2>
            <p className="text-xs italic text-gray-500">{fit.overall.disclaimer}</p>
            <p className="mt-2 text-xs text-gray-400">
              Engine {fit.engine_version} · Extracted{" "}
              {fit.requirements_info.extracted_count} requirements · Summary source:{" "}
              {formatLabel(fit.overall.summary_source)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ResponsibilityRow({ responsibility }: { responsibility: { responsibility: string; alignment: string; evidence: FitEvidenceItem[] } }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const alignmentStyles: Record<string, string> = {
    strong: "badge-success",
    moderate: "badge-warning",
    weak: "badge-warning",
    none: "badge-danger",
  };
  return (
    <div className="border-b border-gray-100 py-3 last:border-b-0">
      <div className="flex items-center gap-2">
        <span
          className={`badge capitalize ${
            alignmentStyles[responsibility.alignment] || "badge-neutral"
          }`}
        >
          {responsibility.alignment}
        </span>
        <span className="text-sm text-gray-900">{responsibility.responsibility}</span>
        {responsibility.evidence.length > 0 && (
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className="ml-auto text-xs font-medium text-primary-600 hover:text-primary-800"
          >
            {showEvidence ? "Hide evidence" : "Evidence"}
          </button>
        )}
      </div>
      {showEvidence && responsibility.evidence.length > 0 && (
        <EvidenceList evidence={responsibility.evidence} />
      )}
    </div>
  );
}

function SkillGapGroup({
  label,
  skills,
  tone,
}: {
  label: string;
  skills: string[];
  tone: "green" | "yellow" | "red" | "gray";
}) {
  if (skills.length === 0) return null;
  const tones = {
    green: "badge-success",
    yellow: "badge-warning",
    red: "badge-danger",
    gray: "badge-neutral",
  };
  return (
    <div className="mb-3 last:mb-0">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {skills.map((skill) => (
          <span
            key={skill}
            className={`badge ${tones[tone]}`}
          >
            {skill}
          </span>
        ))}
      </div>
    </div>
  );
}
