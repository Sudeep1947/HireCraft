import { useState } from "react";
import {
  ChevronLeft,
  Briefcase,
  GraduationCap,
  FolderGit2,
  Award,
  Languages,
  Wrench,
  Eye,
  EyeOff,
  Shield,
  AlertTriangle,
} from "lucide-react";
import type {
  PerceptionDetail,
  PerceptionSkill,
  PerceptionExperience,
  PerceptionEducation,
  PerceptionProject,
  PerceptionCertification,
  PerceptionLanguage,
} from "../../types/skill2job";

function SkillBadge({ skill }: { skill: PerceptionSkill }) {
  const catColor: Record<string, string> = {
    programming_language: "bg-blue-100 text-blue-700 ring-blue-200/70",
    frontend: "bg-purple-100 text-purple-700 ring-purple-200/70",
    backend: "bg-emerald-100 text-emerald-700 ring-emerald-200/70",
    database: "bg-amber-100 text-amber-700 ring-amber-200/70",
    cloud_devops: "bg-sky-100 text-sky-700 ring-sky-200/70",
    data_ml: "bg-pink-100 text-pink-700 ring-pink-200/70",
    tools: "bg-gray-100 text-gray-600 ring-gray-200/80",
    soft_skills: "bg-rose-100 text-rose-700 ring-rose-200/70",
    testing: "bg-lime-100 text-lime-700 ring-lime-200/70",
  };
  const color = catColor[skill.category ?? ""] ?? "bg-gray-100 text-gray-600 ring-gray-200/80";
  return (
    <span className={`badge ring-1 ring-inset ${color}`}>
      {skill.name}
      {skill.canonical && skill.canonical !== skill.name && (
        <span className="text-[10px] opacity-60">({skill.canonical})</span>
      )}
      {skill.inferred && <span className="text-[10px] opacity-50">*</span>}
    </span>
  );
}

function Section({ title, icon: Icon, count, children }: { title: string; icon: typeof Briefcase; count?: number; children: React.ReactNode }) {
  return (
    <div className="border-t border-gray-100 pt-5">
      <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
        <span className="rounded-lg bg-primary-50 p-1.5 text-primary-600">
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        {title}
        {count != null && <span className="text-xs font-normal text-gray-400">({count})</span>}
      </h4>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function ProvenanceBadge({ evidence, source }: { evidence?: string | null; source?: string | null }) {
  if (!evidence) return null;
  return (
    <span className="mt-1.5 inline-flex items-start gap-1 text-[11px] leading-relaxed text-gray-400" title={evidence}>
      <Shield className="mt-0.5 h-3 w-3 flex-shrink-0" aria-hidden="true" />
      <span>
        {source && <span className="font-medium">{source}:</span>}
        &ldquo;{evidence.length > 80 ? evidence.slice(0, 80) + "..." : evidence}&rdquo;
      </span>
    </span>
  );
}

export function PerceptionDetailPanel({ detail, onBack }: { detail: PerceptionDetail; onBack: () => void }) {
  const [showRaw, setShowRaw] = useState(false);
  const r = detail.result;

  return (
    <div className="space-y-4 animate-fade-up">
      {/* Header */}
      <div className="card p-6">
        <button
          onClick={onBack}
          className="btn-ghost btn-sm -ml-3 mb-3 justify-start"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Back to history
        </button>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 className="section-title truncate">
              {detail.original_filename || "Free Text Input"}
            </h3>
            <p className="mt-1 text-xs text-gray-500">
              {detail.input_type} &middot; {detail.parser_version} &middot; {detail.created_at ? new Date(detail.created_at).toLocaleString() : ""}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={
                detail.processing_status === "ok"
                  ? "badge-success"
                  : detail.processing_status === "partial"
                  ? "badge-warning"
                  : "badge-danger"
              }
            >
              {detail.processing_status}
            </span>
            {detail.field_confidence != null && (
              <span className="badge-neutral">
                {Math.round(detail.field_confidence * 100)}% confidence
              </span>
            )}
          </div>
        </div>
        {detail.processing_message && (
          <p className="mt-3 rounded-lg bg-amber-50/80 px-3 py-2 text-xs text-amber-700">{detail.processing_message}</p>
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        <StatCard label="Skills" value={r?.skills?.length ?? 0} />
        <StatCard label="Experience" value={r?.experience?.length ?? 0} />
        <StatCard label="Education" value={r?.education?.length ?? 0} />
        <StatCard label="Projects" value={r?.projects?.length ?? 0} />
        <StatCard label="Certs" value={r?.certifications?.length ?? 0} />
        <StatCard label="Languages" value={r?.languages?.length ?? 0} />
      </div>

      {r && (
        <div className="card space-y-6 p-6">
          {/* Summary */}
          {r.summary && (
            <div className="panel-brand p-4 text-sm leading-relaxed text-gray-700">{r.summary}</div>
          )}

          {/* Skills */}
          {r.skills.length > 0 && (
            <Section title="Extracted Skills" icon={Wrench} count={r.skills.length}>
              <div className="flex flex-wrap gap-1.5">
                {r.skills.map((s, i) => <SkillBadge key={i} skill={s} />)}
              </div>
              <p className="mt-2 text-[11px] text-gray-400">* = inferred from context (not explicitly listed)</p>
            </Section>
          )}

          {/* Experience */}
          {r.experience.length > 0 && (
            <Section title="Experience" icon={Briefcase} count={r.experience.length}>
              <div className="space-y-3">
                {r.experience.map((exp: PerceptionExperience, i: number) => (
                  <div key={i} className="rounded-xl border border-gray-100 bg-gray-50/70 p-4 shadow-xs">
                    <p className="text-sm font-semibold text-gray-900">{exp.job_title || "Unknown role"}</p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {exp.company || "Unknown company"} {exp.location ? `· ${exp.location}` : ""}
                    </p>
                    {(exp.start_date || exp.end_date) && (
                      <p className="mt-1 text-xs text-gray-400">
                        {exp.start_date || "?"} — {exp.is_current ? "Present" : exp.end_date || "?"}
                        {exp.duration_months ? ` (${exp.duration_months} months)` : ""}
                      </p>
                    )}
                    {exp.description.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {exp.description.map((d, j) => <li key={j} className="text-xs leading-relaxed text-gray-600">· {d}</li>)}
                      </ul>
                    )}
                    {exp.technologies.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {exp.technologies.map((t, j) => (
                          <span key={j} className="badge-primary">{t}</span>
                        ))}
                      </div>
                    )}
                    <ProvenanceBadge evidence={exp.provenance?.evidence} source={exp.provenance?.source} />
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Education */}
          {r.education.length > 0 && (
            <Section title="Education" icon={GraduationCap} count={r.education.length}>
              <div className="space-y-2">
                {r.education.map((edu: PerceptionEducation, i: number) => (
                  <div key={i} className="rounded-xl border border-gray-100 bg-gray-50/70 p-4 shadow-xs">
                    <p className="text-sm font-semibold text-gray-900">
                      {edu.degree || "Unknown degree"}{edu.field_of_study ? ` in ${edu.field_of_study}` : ""}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">{edu.institution || "Unknown institution"}</p>
                    {(edu.start_date || edu.end_date) && (
                      <p className="mt-1 text-xs text-gray-400">{edu.start_date || "?"} — {edu.end_date || "?"}</p>
                    )}
                    <ProvenanceBadge evidence={edu.provenance?.evidence} source={edu.provenance?.source} />
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Projects */}
          {r.projects.length > 0 && (
            <Section title="Projects" icon={FolderGit2} count={r.projects.length}>
              <div className="space-y-2">
                {r.projects.map((proj: PerceptionProject, i: number) => (
                  <div key={i} className="rounded-xl border border-gray-100 bg-gray-50/70 p-4 shadow-xs">
                    <p className="text-sm font-semibold text-gray-900">{proj.name || "Unnamed project"}</p>
                    {proj.description.length > 0 && (
                      <ul className="mt-1.5 space-y-1">
                        {proj.description.map((d, j) => <li key={j} className="text-xs leading-relaxed text-gray-600">· {d}</li>)}
                      </ul>
                    )}
                    {proj.technologies.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {proj.technologies.map((t, j) => (
                          <span key={j} className="badge-primary !bg-purple-50 !text-purple-700 !ring-purple-200/70">{t}</span>
                        ))}
                      </div>
                    )}
                    <ProvenanceBadge evidence={proj.provenance?.evidence} source={proj.provenance?.source} />
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Certifications */}
          {r.certifications.length > 0 && (
            <Section title="Certifications" icon={Award} count={r.certifications.length}>
              <div className="space-y-2">
                {r.certifications.map((cert: PerceptionCertification, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="rounded-lg bg-amber-50 p-1.5 text-amber-600">
                      <Award className="h-3 w-3" aria-hidden="true" />
                    </span>
                    <span className="font-medium">{cert.name || "Unknown cert"}</span>
                    {cert.issuer && <span className="text-xs text-gray-400">— {cert.issuer}</span>}
                    {cert.date && <span className="text-xs text-gray-400">({cert.date})</span>}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Languages */}
          {r.languages.length > 0 && (
            <Section title="Languages" icon={Languages} count={r.languages.length}>
              <div className="flex flex-wrap gap-2">
                {r.languages.map((lang: PerceptionLanguage, i: number) => (
                  <span key={i} className="badge-neutral !text-xs">
                    {lang.language || "Unknown"}
                    {lang.proficiency && <span className="text-gray-400">({lang.proficiency})</span>}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {/* Target Roles & Interests */}
          {(r.target_roles.length > 0 || r.interests.length > 0) && (
            <div className="border-t border-gray-100 pt-5">
              {r.target_roles.length > 0 && (
                <div className="mb-2">
                  <span className="section-label">Target Roles: </span>
                  <span className="text-xs text-gray-700">{r.target_roles.join(", ")}</span>
                </div>
              )}
              {r.interests.length > 0 && (
                <div>
                  <span className="section-label">Interests: </span>
                  <span className="text-xs text-gray-700">{r.interests.join(", ")}</span>
                </div>
              )}
            </div>
          )}

          {/* Quality Metrics */}
          {r.quality && (
            <div className="border-t border-gray-100 pt-5">
              <h4 className="section-label mb-3">Parsing Quality</h4>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <QualityBar label="Text" value={r.quality.text_quality} />
                <QualityBar label="Layout" value={r.quality.layout_quality} />
                <QualityBar label="Entity" value={r.quality.entity_quality} />
                <QualityBar label="Overall" value={r.quality.overall_confidence} />
              </div>
            </div>
          )}

          {/* Document Info */}
          {r.document && (
            <div className="border-t border-gray-100 pt-5">
              <h4 className="section-label mb-3">Document Info</h4>
              <div className="flex flex-wrap gap-2 text-xs text-gray-600">
                {r.document.format && <span className="badge-neutral">{r.document.format}</span>}
                {r.document.pages && <span className="badge-neutral">Pages: {r.document.pages}</span>}
                {r.document.extraction_method && <span className="badge-neutral">Method: {r.document.extraction_method}</span>}
                {r.document.tables_found > 0 && <span className="badge-neutral">Tables: {r.document.tables_found}</span>}
                {r.document.is_scanned && <span className="badge-warning">Scanned PDF</span>}
                {r.document.ocr_used && <span className="badge-warning">OCR used</span>}
              </div>
            </div>
          )}

          {/* Warnings */}
          {(detail.warnings.length > 0 || r.warnings.length > 0) && (
            <div className="rounded-xl border border-amber-200/70 bg-amber-50/70 p-4">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> Warnings
              </h4>
              <ul className="mt-2 space-y-1">
                {[...detail.warnings, ...r.warnings].map((w, i) => (
                  <li key={i} className="text-xs text-amber-700">· {w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Errors */}
          {r.errors.length > 0 && (
            <div className="error-banner">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
              <div>
                <h4 className="text-xs font-semibold">Errors</h4>
                <ul className="mt-1 space-y-1">
                  {r.errors.map((e, i) => (
                    <li key={i} className="text-xs">· [{e.code}] {e.message}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Raw Text Toggle */}
          {detail.extracted_text && (
            <div className="border-t border-gray-100 pt-5">
              <button
                onClick={() => setShowRaw(!showRaw)}
                className="btn-ghost btn-sm -ml-3 justify-start"
              >
                {showRaw ? <EyeOff className="h-3.5 w-3.5" aria-hidden="true" /> : <Eye className="h-3.5 w-3.5" aria-hidden="true" />}
                {showRaw ? "Hide" : "Show"} Raw Extracted Text ({detail.extracted_text.length.toLocaleString()} chars)
              </button>
              {showRaw && (
                <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl border border-gray-200 bg-gray-50 p-4 text-xs leading-relaxed text-gray-600 shadow-xs">
                  {detail.extracted_text}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="card card-hover p-3 text-center">
      <div className="font-display text-lg font-bold text-primary-600">{value}</div>
      <div className="mt-0.5 text-[11px] text-gray-500">{label}</div>
    </div>
  );
}

function QualityBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70
      ? "bg-gradient-to-br from-emerald-400 to-emerald-600"
      : pct >= 40
      ? "bg-gradient-to-br from-amber-400 to-amber-600"
      : "bg-gradient-to-br from-red-400 to-red-600";
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/70 p-3 shadow-xs">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">{label}</div>
      <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1 text-[10px] font-medium text-gray-400">{pct}%</div>
    </div>
  );
}
