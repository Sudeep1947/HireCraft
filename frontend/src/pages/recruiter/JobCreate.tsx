import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { recruiterJobApi } from "../../api/jobs";
import { useToast } from "../../contexts/ToastContext";
import type { JobFormData } from "../../types/jobs";

export function RecruiterJobCreate() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<JobFormData>({
    title: "",
    company: "",
    department: "",
    employment_type: "full_time",
    experience_required: "",
    education_required: "",
    required_skills: [],
    preferred_skills: [],
    location: "",
    salary_min: null,
    salary_max: null,
    salary_currency: "USD",
    description: "",
    benefits: "",
    application_deadline: null,
    status: "draft",
  });
  const [skillInput, setSkillInput] = useState("");
  const [prefSkillInput, setPrefSkillInput] = useState("");

  function addRequiredSkill() {
    if (skillInput.trim() && !form.required_skills.includes(skillInput.trim())) {
      setForm({ ...form, required_skills: [...form.required_skills, skillInput.trim()] });
    }
    setSkillInput("");
  }

  function addPreferredSkill() {
    if (prefSkillInput.trim() && !form.preferred_skills.includes(prefSkillInput.trim())) {
      setForm({ ...form, preferred_skills: [...form.preferred_skills, prefSkillInput.trim()] });
    }
    setPrefSkillInput("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const job = await recruiterJobApi.createJob(form);
      addToast("Job created successfully", "success");
      navigate(`/recruiter/jobs/${job.id}`);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } } };
      const msg = apiErr?.response?.data?.detail || "Failed to create job. Please try again.";
      const displayMsg = typeof msg === "string" ? msg : JSON.stringify(msg);
      setError(displayMsg);
      addToast(displayMsg, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Create Job Posting</h1>
          <p className="page-subtitle">Fill in the details to create a new job posting</p>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card p-6">
          <h2 className="section-title mb-4">Basic Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label">Job Title *</label>
              <input
                required
                className="field"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Company *</label>
              <input
                required
                className="field"
                value={form.company}
                onChange={(e) => setForm({ ...form, company: e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Department</label>
              <input
                className="field"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Employment Type *</label>
              <select
                className="field"
                value={form.employment_type}
                onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
              >
                <option value="full_time">Full Time</option>
                <option value="part_time">Part Time</option>
                <option value="contract">Contract</option>
                <option value="internship">Internship</option>
                <option value="freelance">Freelance</option>
              </select>
            </div>
            <div>
              <label className="field-label">Location *</label>
              <input
                required
                className="field"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Experience Required</label>
              <input
                className="field"
                value={form.experience_required || ""}
                onChange={(e) => setForm({ ...form, experience_required: e.target.value })}
                placeholder="e.g. 3-5 years"
              />
            </div>
            <div>
              <label className="field-label">Education Required</label>
              <input
                className="field"
                value={form.education_required || ""}
                onChange={(e) => setForm({ ...form, education_required: e.target.value })}
                placeholder="e.g. Bachelor's in CS"
              />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="section-title mb-4">Salary</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="field-label">Min Salary</label>
              <input
                type="number"
                className="field"
                value={form.salary_min ?? ""}
                onChange={(e) => setForm({ ...form, salary_min: e.target.value ? Number(e.target.value) : null })}
              />
            </div>
            <div>
              <label className="field-label">Max Salary</label>
              <input
                type="number"
                className="field"
                value={form.salary_max ?? ""}
                onChange={(e) => setForm({ ...form, salary_max: e.target.value ? Number(e.target.value) : null })}
              />
            </div>
            <div>
              <label className="field-label">Currency</label>
              <select
                className="field"
                value={form.salary_currency}
                onChange={(e) => setForm({ ...form, salary_currency: e.target.value })}
              >
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
              <input
                className="field flex-1"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRequiredSkill())}
                placeholder="Type a skill and press Enter"
              />
              <button type="button" onClick={addRequiredSkill} className="btn-primary btn-md">
                Add
              </button>
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
              <input
                className="field flex-1"
                value={prefSkillInput}
                onChange={(e) => setPrefSkillInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPreferredSkill())}
                placeholder="Type a skill and press Enter"
              />
              <button type="button" onClick={addPreferredSkill} className="btn-primary btn-md">
                Add
              </button>
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
              <textarea
                required
                rows={6}
                className="field"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Benefits</label>
              <textarea
                rows={4}
                className="field"
                value={form.benefits || ""}
                onChange={(e) => setForm({ ...form, benefits: e.target.value })}
              />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="section-title mb-4">Additional Settings</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label">Application Deadline</label>
              <input
                type="date"
                className="field"
                value={form.application_deadline || ""}
                onChange={(e) => setForm({ ...form, application_deadline: e.target.value || null })}
              />
            </div>
            <div>
              <label className="field-label">Status</label>
              <select
                className="field"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate("/recruiter/jobs")}
            className="btn-secondary btn-md"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="btn-primary btn-md"
          >
            {saving ? "Creating..." : "Create Job"}
          </button>
        </div>
      </form>
    </div>
  );
}
