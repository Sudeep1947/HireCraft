import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { ResumeScoreGauge } from "../../components/candidate/ResumeScoreGauge";
import { candidateApi } from "../../api/candidate";
import type { ResumeDetail as ResumeDetailType } from "../../types/candidate";

export function ResumeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<ResumeDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    if (!id) {
      setLoading(false);
      setError("No resume ID provided");
      return;
    }
    async function load() {
      try {
        const data = await candidateApi.getResume(id!);
        if (!cancelledRef.current) setDetail(data);
      } catch {
        if (!cancelledRef.current) setError("Failed to load resume details");
      } finally {
        if (!cancelledRef.current) setLoading(false);
      }
    }
    load();
    return () => { cancelledRef.current = true; };
  }, [id]);

  async function handleDelete() {
    if (!id || deleting) return;
    if (!window.confirm("Delete this resume?")) return;
    setDeleting(true);
    try {
      await candidateApi.deleteResume(id);
      if (!cancelledRef.current) navigate("/candidate/resume");
    } catch {
      if (!cancelledRef.current) setError("Failed to delete resume");
    } finally {
      if (!cancelledRef.current) setDeleting(false);
    }
  }

  async function handleRetry() {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const data = await candidateApi.retryResume(id);
      if (!cancelledRef.current) setDetail(data);
    } catch (err: any) {
      if (!cancelledRef.current) {
        setError(err?.response?.data?.detail || "Retry failed");
      }
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  }

  async function handleDownload() {
    if (!id) return;
    try {
      const response = await candidateApi.downloadResume(id);
      const url = window.URL.createObjectURL(new Blob([response]));
      const a = document.createElement("a");
      a.href = url;
      a.download = resume.original_filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Failed to download resume");
    }
  }

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-72" />
        <div className="skeleton h-56 w-full" />
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-64 w-full" />
      </div>
    );

  if (error || !detail) {
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="error-banner">
          {error || "Resume not found"}
        </div>
      </div>
    );
  }

  const { resume, parsed_data: parsed, analysis } = detail;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div className="min-w-0">
          <h1 className="page-title truncate">{resume.original_filename}</h1>
          <p className="page-subtitle">
            Uploaded on {new Date(resume.created_at).toLocaleDateString()} &middot; v{resume.version}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => navigate("/candidate/resume")}
            className="btn-secondary btn-sm"
          >
            &larr; Back
          </button>
          <button
            onClick={handleDownload}
            className="btn-secondary btn-sm"
          >
            Download
          </button>
          {resume.status === "failed" && (
            <button
              onClick={handleRetry}
              className="btn-secondary btn-sm border-amber-300 bg-amber-50 text-amber-700 hover:border-amber-400 hover:bg-amber-100 hover:text-amber-800"
            >
              Retry Parsing
            </button>
          )}
          {resume.status === "parsed" && (
            <>
              <button
                onClick={() => navigate(`/candidate/resume/${id}/intelligence`)}
                className="btn-primary btn-sm"
              >
                Intelligence Report
              </button>
              <button
                onClick={() => navigate(`/candidate/resume/${id}/sync`)}
                className="btn-secondary btn-sm"
              >
                Sync with Profile
              </button>
            </>
          )}
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="btn-danger btn-sm"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>

      {analysis && (
        <div className="card p-6">
          <h2 className="section-title mb-4">Analysis</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <ResumeScoreGauge score={analysis.quality_score} label="Quality Score" />
            <ResumeScoreGauge score={analysis.completeness_score ?? 0} label="Completeness" />
            <ResumeScoreGauge score={analysis.readability_score ?? 0} label="Readability" />
            <ResumeScoreGauge score={analysis.professionalism_score ?? 0} label="Professionalism" />
            <ResumeScoreGauge score={analysis.keyword_optimization_score ?? 0} label="Keyword Score" />
            <ResumeScoreGauge score={analysis.ats_score} label="ATS Score" />
          </div>
          {analysis.recommendations && analysis.recommendations.length > 0 && (
            <div className="mt-6">
              <h3 className="mb-2 text-sm font-semibold text-gray-900">Recommendations</h3>
              <ul className="space-y-1.5">
                {analysis.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                    <span className="mt-0.5 text-amber-500">&bull;</span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis.section_scores && (
            <div className="mt-6">
              <h3 className="mb-2 text-sm font-semibold text-gray-900">Section Scores</h3>
              <div className="space-y-2.5">
                {Object.entries(analysis.section_scores).map(([section, score]) => (
                  <div key={section} className="flex items-center gap-3">
                    <span className="w-32 text-sm capitalize text-gray-600">{section.replace(/_/g, " ")}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${score >= 20 ? "bg-gradient-to-r from-emerald-400 to-emerald-600" : score >= 10 ? "bg-gradient-to-r from-amber-400 to-amber-600" : "bg-gradient-to-r from-red-400 to-red-600"}`}
                        style={{ width: `${(score / 30) * 100}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-xs font-medium text-gray-500">{score}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="section-title">Resume Preview</h2>
          <span className="text-xs font-medium text-gray-400">
            v{resume.version} &middot; {resume.file_type.toUpperCase()}
          </span>
        </div>
        <div className="panel-brand flex flex-wrap items-center gap-4 rounded-xl p-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/80 text-primary-600 shadow-xs">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-gray-900">{resume.original_filename}</p>
            <p className="text-xs text-gray-500">
              {Math.round(resume.file_size / 1024)} KB &middot; Uploaded {new Date(resume.created_at).toLocaleDateString()}
            </p>
          </div>
          {resume.is_primary && (
            <span className="badge-primary ml-auto">
              Primary
            </span>
          )}
        </div>
      </div>

      {parsed && (
        <div className="card p-6">
          <h2 className="section-title mb-4">Parsed Data</h2>

          {parsed.summary && (
            <Section title="Summary">
              <p className="rounded-xl bg-gray-50 p-3.5 text-sm leading-relaxed text-gray-700">{parsed.summary}</p>
            </Section>
          )}

          {parsed.personal_info && Object.keys(parsed.personal_info).length > 0 && (
            <Section title="Personal Info">
              <InfoGrid data={parsed.personal_info as Record<string, unknown>} />
            </Section>
          )}

          {parsed.education && parsed.education.length > 0 && (
            <Section title="Education">
              {parsed.education.map((edu: any, i: number) => (
                <div key={i} className="mb-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-sm">
                  {edu.degree && <p className="font-semibold text-gray-900">{edu.degree}</p>}
                  {edu.institution && <p className="text-gray-600">{edu.institution}</p>}
                  {(edu.start_date || edu.end_date) && (
                    <p className="text-xs text-gray-400">
                      {edu.start_date || ""} - {edu.end_date || ""}
                    </p>
                  )}
                </div>
              ))}
            </Section>
          )}

          {parsed.experience && parsed.experience.length > 0 && (
            <Section title="Experience">
              {parsed.experience.map((exp: any, i: number) => (
                <div key={i} className="mb-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-sm">
                  {(exp.job_title || exp.title) && <p className="font-semibold text-gray-900">{exp.job_title || exp.title}</p>}
                  {exp.company && <p className="text-gray-600">{exp.company}</p>}
                  {((exp.start_date || exp.end_date) || exp.duration_label) && (
                    <p className="text-xs text-gray-400">
                      {exp.start_date || ""} - {exp.end_date || (exp.is_current ? "Present" : "")}
                      {exp.duration_label ? ` · ${exp.duration_label}` : ""}
                      {exp.employment_type ? ` · ${exp.employment_type}` : ""}
                    </p>
                  )}
                  {Array.isArray(exp.technologies) && exp.technologies.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {exp.technologies.slice(0, 10).map((t: string, j: number) => (
                        <span key={j} className="badge-neutral">{t}</span>
                      ))}
                    </div>
                  )}
                  {exp.description && Array.isArray(exp.description) && (
                    <ul className="mt-2 space-y-1">
                      {exp.description.slice(0, 3).map((d: string, j: number) => (
                        <li key={j} className="text-xs text-gray-500">&bull; {d}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </Section>
          )}

          {parsed.projects && parsed.projects.length > 0 && (
            <Section title="Projects">
              {parsed.projects.map((proj: any, i: number) => (
                <div key={i} className="mb-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3.5 text-sm">
                  {proj.name && <p className="font-semibold text-gray-900">{proj.name}</p>}
                  {Array.isArray(proj.technologies) && proj.technologies.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {proj.technologies.slice(0, 10).map((t: string, j: number) => (
                        <span key={j} className="badge-neutral">{t}</span>
                      ))}
                    </div>
                  )}
                  {Array.isArray(proj.description) && proj.description.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {proj.description.slice(0, 3).map((d: string, j: number) => (
                        <li key={j} className="text-xs text-gray-500">&bull; {d}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </Section>
          )}

          {parsed.skills && parsed.skills.length > 0 && (
            <Section title="Skills">
              <div className="flex flex-wrap gap-2">
                {parsed.skills.map((skill: any, i: number) => (
                  <span key={i} className="badge-primary">
                    {skill.display_name || skill.name}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {parsed.certifications && parsed.certifications.length > 0 && (
            <Section title="Certifications">
              {parsed.certifications.map((cert: any, i: number) => (
                <div key={i} className="mb-2 text-sm">
                  <p className="font-medium text-gray-900">{cert.name}</p>
                  {cert.issuer && <p className="text-xs text-gray-500">{cert.issuer}</p>}
                </div>
              ))}
            </Section>
          )}

          {parsed.languages && parsed.languages.length > 0 && (
            <Section title="Languages">
              {parsed.languages.map((lang: any, i: number) => (
                <div key={i} className="mb-2 text-sm">
                  <p className="font-medium text-gray-900">{lang.language}</p>
                  {lang.proficiency && (
                    <p className="text-xs capitalize text-gray-500">{lang.proficiency}</p>
                  )}
                </div>
              ))}
            </Section>
          )}
        </div>
      )}

      {!parsed && resume.status === "uploaded" && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-700 shadow-xs">
          This resume is being processed. Please check back shortly.
        </div>
      )}

      {!parsed && resume.status === "failed" && (
        <div className="error-banner">
          Resume parsing failed. Please try uploading again.
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6 last:mb-0">
      <h3 className="section-label mb-3">
        {title}
      </h3>
      {children}
    </div>
  );
}

function InfoGrid({ data }: { data: Record<string, unknown> }) {
  const labels: Record<string, string> = {
    name: "Name",
    email: "Email",
    phone: "Phone",
    location: "Location",
    linkedin: "LinkedIn",
    github: "GitHub",
    website: "Website",
  };

  return (
    <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
      {Object.entries(data).map(([key, value]) => {
        if (!value || key === "additional_urls") return null;
        return (
          <div key={key} className="rounded-xl bg-gray-50/70 px-3.5 py-2.5">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-400">{labels[key] || key}</span>
            <p className="font-medium text-gray-900">{String(value)}</p>
          </div>
        );
      })}
    </div>
  );
}
