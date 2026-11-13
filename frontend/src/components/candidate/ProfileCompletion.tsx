import { AlertCircle } from "lucide-react";

import type { ProfileCompletion as ProfileCompletionType } from "../../types/candidate";

interface ProfileCompletionProps {
  data: ProfileCompletionType;
}

export function ProfileCompletion({ data }: ProfileCompletionProps) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (data.completion_percentage / 100) * circumference;

  const sectionLabels: Record<string, string> = {
    personal_info: "Personal Info",
    education: "Education",
    experience: "Experience",
    skills: "Skills",
    projects: "Projects",
    certifications: "Certifications",
    languages: "Languages",
  };

  return (
    <div className="card p-5">
      <h3 className="section-title">Profile Completion</h3>
      <div className="mt-4 flex items-center gap-6">
        <div className="relative flex-shrink-0">
          <svg className="h-28 w-28 -rotate-90" viewBox="0 0 120 120" aria-hidden="true">
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#e5e7eb"
              strokeWidth="8"
            />
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#5557e6"
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-display text-xl font-bold text-gray-900">
              {data.completion_percentage}%
            </span>
          </div>
        </div>
        <div className="min-w-0 flex-1 space-y-1.5">
          {Object.entries(data.sections).map(([key, filled]) => (
            <div key={key} className="flex items-center gap-2 text-sm">
              <div
                className={`h-2 w-2 shrink-0 rounded-full ${
                  filled ? "bg-emerald-500" : "bg-gray-300"
                }`}
              />
              <span className={filled ? "text-gray-700" : "text-gray-400"}>
                {sectionLabels[key] || key}
              </span>
            </div>
          ))}
        </div>
      </div>
      {data.recommendations.length > 0 && (
        <div className="mt-4 space-y-1 rounded-xl bg-amber-50/70 p-3 ring-1 ring-inset ring-amber-200/60">
          {data.recommendations.map((rec, i) => (
            <p key={i} className="flex items-start gap-1.5 text-xs text-amber-700">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>{rec}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
