import { useEffect, useState } from "react";
import { Award, Briefcase, GraduationCap, Layers } from "lucide-react";
import { candidateApi } from "../../api/candidate";
import type { CandidateIntelligence as Intel } from "../../types/candidate";

const LEVEL_LABELS: Record<string, string> = {
  not_specified: "Not specified",
  high_school: "High School",
  associate: "Associate Degree",
  bachelor: "Bachelor's Degree",
  master: "Master's Degree",
  doctorate: "Doctorate",
};

export function CandidateIntelligence() {
  const [data, setData] = useState<Intel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const result = await candidateApi.getIntelligence();
        setData(result);
      } catch {
        setError("Failed to load intelligence data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-72" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="skeleton h-28 w-full" />
          <div className="skeleton h-28 w-full" />
          <div className="skeleton h-28 w-full" />
          <div className="skeleton h-28 w-full" />
        </div>
        <div className="skeleton h-32 w-full" />
      </div>
    );
  if (error)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="error-banner">{error}</div>
      </div>
    );
  if (!data) return null;

  const strengthColor =
    data.profile_strength >= 80
      ? "text-emerald-600"
      : data.profile_strength >= 50
        ? "text-amber-500"
        : "text-red-500";

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">Candidate Intelligence</h1>
        <p className="page-subtitle">
          AI-powered insights derived from your profile and resumes
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox label="Total Experience" value={`${data.total_experience_years} yrs`} sub={`${data.total_experience_months} months`} color="blue" />
        <StatBox label="Highest Qualification" value={data.highest_qualification || "N/A"} sub={LEVEL_LABELS[data.education_level] || data.education_level} color="green" />
        <StatBox label="Projects" value={String(data.project_count)} sub="total" color="purple" />
        <StatBox label="Certifications" value={String(data.certification_count)} sub="earned" color="amber" />
      </div>

      <div className="card p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="section-title">Profile Strength</h2>
          <span className={`font-display text-3xl font-bold ${strengthColor}`}>{data.profile_strength}%</span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-gray-100">
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              data.profile_strength >= 80
                ? "bg-gradient-to-r from-emerald-400 to-emerald-600"
                : data.profile_strength >= 50
                  ? "bg-gradient-to-r from-amber-400 to-amber-600"
                  : "bg-gradient-to-r from-red-400 to-red-600"
            }`}
            style={{ width: `${data.profile_strength}%` }}
          />
        </div>
      </div>

      {Object.keys(data.skills_by_category).length > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-4">Skills by Category</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(data.skills_by_category).map(([category, skills]) => (
              <div key={category} className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
                <h3 className="section-label mb-2">
                  {category.replace(/_/g, " ")}
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {skills.map((skill) => (
                    <span key={skill} className="badge-primary">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.recommendations.length > 0 && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 p-6 shadow-xs">
          <h2 className="mb-3 text-lg font-semibold text-amber-900">Recommendations</h2>
          <ul className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-amber-800">
                <span className="mt-0.5 text-amber-500">&bull;</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.missing_sections.length > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-3">Missing Sections</h2>
          <div className="flex flex-wrap gap-2">
            {data.missing_sections.map((section) => (
              <span key={section} className="badge-danger">
                {section.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  const colorMap: Record<string, { well: string; Icon: typeof Briefcase }> = {
    blue: { well: "bg-primary-50 text-primary-600", Icon: Briefcase },
    green: { well: "bg-emerald-50 text-emerald-600", Icon: GraduationCap },
    purple: { well: "bg-violet-50 text-violet-600", Icon: Layers },
    amber: { well: "bg-amber-50 text-amber-600", Icon: Award },
  };
  const { well, Icon } = colorMap[color] || colorMap.blue;
  return (
    <div className="card card-hover p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
          <p className="mt-1.5 font-display text-2xl font-bold text-gray-900">{value}</p>
          <p className="mt-1 text-xs text-gray-400">{sub}</p>
        </div>
        <span className={`shrink-0 rounded-xl p-2.5 ${well}`}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}
