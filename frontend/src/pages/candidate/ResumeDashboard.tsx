import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Upload } from "lucide-react";

import { ResumeCard } from "../../components/candidate/ResumeCard";
import { candidateApi } from "../../api/candidate";
import type { Resume, CandidateIntelligence as Intel } from "../../types/candidate";

export function ResumeDashboard() {
  const navigate = useNavigate();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [intel, setIntel] = useState<Intel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [resumeData, intelData] = await Promise.allSettled([
        candidateApi.listResumes(),
        candidateApi.getIntelligence(),
      ]);
      if (resumeData.status === "fulfilled") setResumes(resumeData.value);
      if (intelData.status === "fulfilled") setIntel(intelData.value);
    } catch {
      setError("Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSetPrimary(id: string) {
    try {
      await candidateApi.setPrimaryResume(id);
      await load();
    } catch {
      setError("Failed to set primary resume");
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Delete this resume?")) return;
    try {
      await candidateApi.deleteResume(id);
      await load();
    } catch {
      setError("Failed to delete resume");
    }
  }

  function handleView(id: string) {
    navigate(`/candidate/resume/${id}`);
  }

  const parsed = resumes.filter((r) => r.status === "parsed");
  const processing = resumes.filter((r) => r.status === "processing" || r.status === "uploaded");
  const failed = resumes.filter((r) => r.status === "failed");

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-56" />
        <div className="skeleton h-28 w-full" />
        <div className="skeleton h-32 w-full" />
        <div className="skeleton h-32 w-full" />
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Resumes</h1>
          <p className="page-subtitle">
            Upload, manage, and analyze your resumes
          </p>
        </div>
        <button
          onClick={() => navigate("/candidate/resume/upload")}
          className="btn-primary btn-md"
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          Upload New Resume
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {intel && (
        <div className="panel-brand p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-primary-900">Candidate Intelligence</h2>
              <p className="mt-1 text-xs text-primary-700">
                {intel.total_experience_years > 0 && `${intel.total_experience_years} yrs experience`}
                {intel.highest_qualification && ` · ${intel.highest_qualification}`}
                {intel.project_count > 0 && ` · ${intel.project_count} projects`}
                {intel.certification_count > 0 && ` · ${intel.certification_count} certifications`}
              </p>
            </div>
            <div className="text-right">
              <span className="font-display text-3xl font-bold text-gradient">
                {intel.profile_strength}%
              </span>
              <p className="text-xs font-medium text-primary-600">Profile Strength</p>
            </div>
          </div>
          <button
            onClick={() => navigate("/candidate/intelligence")}
            className="mt-3 text-sm font-semibold text-primary-700 transition-colors duration-200 hover:text-primary-800"
          >
            View full intelligence report &rarr;
          </button>
        </div>
      )}

      {resumes.length === 0 && !loading && (
        <div className="empty-state">
          <FileText className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm text-gray-500">No resumes uploaded yet.</p>
          <button
            onClick={() => navigate("/candidate/resume/upload")}
            className="btn-primary btn-sm mt-4"
          >
            Upload your first resume
          </button>
        </div>
      )}

      {parsed.length > 0 && (
        <div>
          <h2 className="section-title mb-3">Parsed Resumes</h2>
          <div className="space-y-3">
            {parsed.map((r) => (
              <ResumeCard
                key={r.id}
                resume={r}
                onView={handleView}
                onDelete={handleDelete}
                onSetPrimary={handleSetPrimary}
              />
            ))}
          </div>
        </div>
      )}

      {processing.length > 0 && (
        <div>
          <h2 className="section-title mb-3">Processing</h2>
          <div className="space-y-3">
            {processing.map((r) => (
              <ResumeCard key={r.id} resume={r} />
            ))}
          </div>
        </div>
      )}

      {failed.length > 0 && (
        <div>
          <h2 className="section-title mb-3">Failed</h2>
          <div className="space-y-3">
            {failed.map((r) => (
              <ResumeCard key={r.id} resume={r} onDelete={handleDelete} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
