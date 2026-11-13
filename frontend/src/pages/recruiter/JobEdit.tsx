import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { recruiterJobApi } from "../../api/jobs";
import type { JobFormData } from "../../types/jobs";

export function RecruiterJobEdit() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<JobFormData | null>(null);
  const [skillInput, setSkillInput] = useState("");
  const [prefSkillInput, setPrefSkillInput] = useState("");

  useEffect(() => {
    if (!id) return;
    async function load() {
      try {
        const job = await recruiterJobApi.getJob(id!);
        setForm({
          title: job.title,
          company: job.company,
          department: job.department || "",
          employment_type: job.employment_type,
          experience_required: job.experience_required || "",
          education_required: job.education_required || "",
          required_skills: job.required_skills || [],
          preferred_skills: job.preferred_skills || [],
          location: job.location,
          salary_min: job.salary_min,
          salary_max: job.salary_max,
          salary_currency: job.salary_currency,
          description: job.description,
          benefits: job.benefits || "",
          application_deadline: job.application_deadline,
          status: job.status,
        });
      } catch {
        setError("Failed to load job");
        addToast("Failed to load job data", "error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, addToast]);

  function addRequiredSkill() {
    if (!form) return;
    if (skillInput.trim() && !form.required_skills.includes(skillInput.trim())) {
      setForm({ ...form, required_skills: [...form.required_skills, skillInput.trim()] });
    }
    setSkillInput("");
  }

  function addPreferredSkill() {
    if (!form) return;
    if (prefSkillInput.trim() && !form.preferred_skills.includes(prefSkillInput.trim())) {
      setForm({ ...form, preferred_skills: [...form.preferred_skills, prefSkillInput.trim()] });
    }
    setPrefSkillInput("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!id || !form) return;
    setSaving(true);
    setError("");
    try {
      await recruiterJobApi.updateJob(id, form);
      navigate(`/recruiter/jobs/${id}`);
    } catch {
      setError("Failed to update job");
      addToast("Failed to save changes", "error");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;
  if (!form)
    return (
      <div className="empty-state mt-10">
        <p className="text-gray-500">Job not found</p>
      </div>
    );

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-up">
      <div>
        <button onClick={() => navigate(`/recruiter/jobs/${id}`)} className="btn-ghost btn-sm -ml-3 mb-2 text-primary-600 hover:text-primary-700">
          &larr; Back to Job
        </button>
        <h1 className="page-title">Edit Job</h1>
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card p-6">
          <h2 className="section-title mb-4">Basic Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label">Job Title *</label>
              <input required className="field"
                value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div>
              <label className="field-label">Company *</label>
              <input required className="field"
                value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
            </div>
            <div>
              <label className="field-label">Department</label>
              <input className="field"
                value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
            </div>
            <div>
              <label className="field-label">Employment Type</label>
              <select className="field"
                value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })}>
                <option value="full_time">Full Time</option>
                <option value="part_time">Part Time</option>
                <option value="contract">Contract</option>
                <option value="internship">Internship</option>
                <option value="freelance">Freelance</option>
              </select>
            </div>
            <div>
              <label className="field-label">Location *</label>
              <input required className="field"
                value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </div>
            <div>
              <label className="field-label">Experience Required</label>
              <input className="field"
                value={form.experience_required || ""} onChange={(e) => setForm({ ...form, experience_required: e.target.value })} />
            </div>
            <div>
              <label className="field-label">Education Required</label>
              <input className="field"
                value={form.education_required || ""} onChange={(e) => setForm({ ...form, education_required: e.target.value })} />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="section-title mb-4">Salary</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="field-label">Min Salary</label>
              <input type="number" className="field"
                value={form.salary_min ?? ""} onChange={(e) => setForm({ ...form, salary_min: e.target.value ? Number(e.target.value) : null })} />
            </div>
            <div>
              <label className="field-label">Max Salary</label>
              <input type="number" className="field"
                value={form.salary_max ?? ""} onChange={(e) => setForm({ ...form, salary_max: e.target.value ? Number(e.target.value) : null })} />
            </div>
            <div>
              <label className="field-label">Currency</label>
              <select className="field"
                value={form.salary_currency} onChange={(e) => setForm({ ...form, salary_currency: e.target.value })}>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="INR">INR</option>
              </select>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="section-title mb-4">Skills</h2>
          <div className="mb-4">
            <label className="field-label">Required Skills</label>
            <div className="mt-1 flex gap-2">
              <input className="field flex-1"
                value={skillInput} onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRequiredSkill())} placeholder="Type and press Enter" />
              <button type="button" onClick={addRequiredSkill} className="btn-primary btn-md">Add</button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {form.required_skills.map((s) => (
                <span key={s} className="badge badge-primary gap-1.5 px-3 py-1">
                  {s}
                  <button type="button" onClick={() => setForm({ ...form, required_skills: form.required_skills.filter((x) => x !== s) })} className="text-primary-600 hover:text-primary-800" aria-label={`Remove ${s}`}>&times;</button>
                </span>
              ))}
            </div>
          </div>
          <div>
            <label className="field-label">Preferred Skills</label>
            <div className="mt-1 flex gap-2">
              <input className="field flex-1"
                value={prefSkillInput} onChange={(e) => setPrefSkillInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPreferredSkill())} placeholder="Type and press Enter" />
              <button type="button" onClick={addPreferredSkill} className="btn-primary btn-md">Add</button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {form.preferred_skills.map((s) => (
                <span key={s} className="badge badge-neutral gap-1.5 px-3 py-1">
                  {s}
                  <button type="button" onClick={() => setForm({ ...form, preferred_skills: form.preferred_skills.filter((x) => x !== s) })} className="text-gray-600 hover:text-gray-800" aria-label={`Remove ${s}`}>&times;</button>
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="section-title mb-4">Description</h2>
          <div className="space-y-4">
            <div>
              <label className="field-label">Job Description *</label>
              <textarea required rows={6} className="field"
                value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div>
              <label className="field-label">Benefits</label>
              <textarea rows={4} className="field"
                value={form.benefits || ""} onChange={(e) => setForm({ ...form, benefits: e.target.value })} />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="section-title mb-4">Settings</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label">Application Deadline</label>
              <input type="date" className="field"
                value={form.application_deadline || ""} onChange={(e) => setForm({ ...form, application_deadline: e.target.value || null })} />
            </div>
            <div>
              <label className="field-label">Status</label>
              <select className="field"
                value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="closed">Closed</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button type="button" onClick={() => navigate(`/recruiter/jobs/${id}`)}
            className="btn-secondary btn-md">
            Cancel
          </button>
          <button type="submit" disabled={saving}
            className="btn-primary btn-md">
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
