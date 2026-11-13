import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { candidateJobApi } from "../../api/jobs";
import { candidateApi } from "../../api/candidate";
import type { Job } from "../../types/jobs";

export function CandidateJobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [job, setJob] = useState<Job | null>(null);
  const [resumes, setResumes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [showApply, setShowApply] = useState(false);
  const [resumeId, setResumeId] = useState("");
  const [coverLetter, setCoverLetter] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [hasApplied, setHasApplied] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (!id) return;
    async function load() {
      try {
        const [jobData, resumeData] = await Promise.all([
          candidateJobApi.getJob(id!),
          candidateApi.listResumes(),
        ]);
        setJob(jobData);
        setResumes(resumeData);
        const primary = resumeData.find((r) => r.is_primary);
        if (primary) setResumeId(primary.id);

        try {
          const myApps = await candidateJobApi.getMyApplications();
          setHasApplied(myApps.some((a) => a.job_id === id && a.status !== "withdrawn"));
        } catch { /* ignore */ }

        try {
          const saved = await candidateJobApi.getSavedJobs();
          setIsSaved(saved.some((j) => j.id === id));
        } catch { /* ignore */ }
      } catch {
        setError("Failed to load job details");
        addToast("Failed to load job details", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, addToast]);

  async function handleApply() {
    if (!id) return;
    setApplying(true);
    setError("");
    try {
      await candidateJobApi.apply(id, resumeId || undefined, coverLetter || undefined);
      setSuccess("Application submitted successfully!");
      setShowApply(false);
      setHasApplied(true);
      addToast("Application submitted!", "success");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to submit application";
      setError(msg);
      addToast(msg, "error");
    } finally {
      setApplying(false);
    }
  }

  async function handleSave() {
    if (!id) return;
    try {
      await candidateJobApi.saveJob(id);
      setSuccess("Job saved!");
      setIsSaved(true);
      addToast("Job saved", "success");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to save job";
      setError(msg);
      addToast(msg, "error");
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (!job) return <div className="empty-state mt-10 text-gray-500">Job not found</div>;

  return (
    <div className="mx-auto max-w-4xl animate-fade-up space-y-6">
      <button onClick={() => navigate("/candidate/jobs")} className="btn-ghost">
        &larr; Back to Jobs
      </button>

      {error && <div className="error-banner" role="alert">{error}</div>}
      {success && <div className="success-banner" role="status">{success}</div>}

      <div className="card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="page-title">{job.title}</h1>
            <p className="mt-1 text-lg text-gray-600">{job.company}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="badge-info">
                {job.employment_type.replace(/_/g, " ")}
              </span>
              <span className="badge-neutral">
                {job.location}
              </span>
              {job.salary_min && job.salary_max && (
                <span className="badge-success">
                  {job.salary_currency} {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                </span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <button
              onClick={() => navigate(`/candidate/mock-interview?jobId=${id}`)}
              className="btn-secondary"
            >
              Mock Interview
            </button>
            <button
              onClick={handleSave}
              disabled={isSaved}
              className="btn-secondary"
            >
              {isSaved ? "Saved" : "Save"}
            </button>
            {hasApplied ? (
              <span className="inline-flex items-center rounded-lg bg-green-100 px-4 py-2 text-sm font-medium text-green-800">
                Applied
              </span>
            ) : (
              <button onClick={() => setShowApply(true)} className="btn-primary">
                Apply Now
              </button>
            )}
          </div>
        </div>

        {(job.experience_required || job.education_required || job.department) && (
          <div className="mt-6 grid grid-cols-1 gap-4 border-t border-gray-100 pt-6 sm:grid-cols-3">
            {job.department && (
              <div>
                <p className="section-label">Department</p>
                <p className="mt-1 text-sm text-gray-900">{job.department}</p>
              </div>
            )}
            {job.experience_required && (
              <div>
                <p className="section-label">Experience</p>
                <p className="mt-1 text-sm text-gray-900">{job.experience_required}</p>
              </div>
            )}
            {job.education_required && (
              <div>
                <p className="section-label">Education</p>
                <p className="mt-1 text-sm text-gray-900">{job.education_required}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {job.required_skills.length > 0 && (
        <div className="card">
          <h2 className="section-title mb-3">Required Skills</h2>
          <div className="flex flex-wrap gap-2">
            {job.required_skills.map((s) => (
              <span key={s} className="chip">{s}</span>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <h2 className="section-title mb-3">Job Description</h2>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">{job.description}</p>
      </div>

      {job.benefits && (
        <div className="card">
          <h2 className="section-title mb-3">Benefits</h2>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">{job.benefits}</p>
        </div>
      )}

      {job.application_deadline && (
        <div className="card">
          <p className="text-sm text-gray-600">
            <span className="font-medium">Application Deadline:</span> {job.application_deadline}
          </p>
        </div>
      )}

      {showApply && (
        <div className="card shadow-lg ring-1 ring-indigo-100">
          <h2 className="section-title mb-4">Apply for this Job</h2>
          <div className="space-y-4">
            <div>
              <label className="field-label">Resume</label>
              <select
                className="field"
                value={resumeId}
                onChange={(e) => setResumeId(e.target.value)}
              >
                <option value="">Select a resume</option>
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.original_filename} ({r.status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label">Cover Letter (Optional)</label>
              <textarea
                rows={5}
                className="field resize-y"
                value={coverLetter}
                onChange={(e) => setCoverLetter(e.target.value)}
                placeholder="Write a brief cover letter..."
              />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setShowApply(false)} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleApply} disabled={applying} className="btn-primary">
                {applying ? "Submitting..." : "Submit Application"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
