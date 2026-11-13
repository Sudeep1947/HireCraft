import { useCallback, useEffect, useState } from "react";
import { Briefcase, Pencil, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { Experience as ExperienceType, ExperienceFormData } from "../../types/candidate";

export function CandidateExperience() {
  const [records, setRecords] = useState<ExperienceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<ExperienceFormData>({ company: "", job_title: "" });

  const fetch = useCallback(async () => {
    try { setRecords(await candidateApi.listExperience()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const resetForm = () => setForm({ company: "", job_title: "" });

  const handleEdit = (r: ExperienceType) => {
    setEditing(r.id);
    setForm({
      company: r.company, job_title: r.job_title,
      employment_type: r.employment_type || undefined,
      start_date: r.start_date, end_date: r.end_date,
      is_current: r.is_current, responsibilities: r.responsibilities || "",
      technologies: r.technologies || "",
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) { await candidateApi.updateExperience(editing, form); }
      else { await candidateApi.createExperience(form); }
      resetForm(); setEditing(null); await fetch();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    await candidateApi.deleteExperience(id);
    await fetch();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Experience</h1>
          <p className="page-subtitle">List your work experience</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <h2 className="section-title">{editing ? "Edit Experience" : "Add Experience"}</h2>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} required />
          <Input label="Job Title" value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} required />
        </div>
        <div className="space-y-1.5">
          <label className="field-label" htmlFor="experience-type">Employment Type</label>
          <select
            id="experience-type"
            value={form.employment_type || ""}
            onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
            className="field"
          >
            <option value="">Select</option>
            <option value="full_time">Full Time</option>
            <option value="part_time">Part Time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
            <option value="freelance">Freelance</option>
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Date" type="date" value={form.start_date || ""} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          <div className="space-y-2">
            <Input label="End Date" type="date" value={form.end_date || ""} onChange={(e) => setForm({ ...form, end_date: e.target.value })} disabled={form.is_current} />
            <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={form.is_current || false} onChange={(e) => setForm({ ...form, is_current: e.target.checked })} className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
              Currently working here
            </label>
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="field-label" htmlFor="experience-responsibilities">Responsibilities</label>
          <textarea
            id="experience-responsibilities"
            value={form.responsibilities || ""}
            onChange={(e) => setForm({ ...form, responsibilities: e.target.value })}
            rows={3}
            className="field resize-y"
          />
        </div>
        <Input label="Technologies Used" value={form.technologies || ""} onChange={(e) => setForm({ ...form, technologies: e.target.value })} placeholder="Python, React, AWS..." />
        <div className="flex gap-2 pt-1">
          <Button type="submit">{editing ? "Update" : "Add"}</Button>
          {editing && <Button variant="ghost" onClick={() => { resetForm(); setEditing(null); }}>Cancel</Button>}
        </div>
      </form>

      <div className="space-y-3">
        {records.length === 0 && (
          <div className="empty-state">
            <Briefcase className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
            <p className="text-sm text-gray-500">No experience added yet.</p>
          </div>
        )}
        {records.map((r) => (
          <div key={r.id} className="card card-hover flex items-start justify-between gap-3 p-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 shadow-soft" aria-hidden="true">
                <Briefcase className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="font-medium text-gray-900">{r.job_title}</p>
                <p className="text-sm text-gray-500">{r.company}</p>
                {r.technologies && <p className="mt-1 text-xs text-gray-400">{r.technologies}</p>}
              </div>
            </div>
            <div className="flex shrink-0 gap-1.5">
              <Button variant="ghost" size="sm" onClick={() => handleEdit(r)}>
                <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                Edit
              </Button>
              <Button variant="ghost" size="sm" className="text-red-600 hover:bg-red-50 hover:text-red-700" onClick={() => handleDelete(r.id)}>
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
