import { useCallback, useEffect, useState } from "react";
import { GraduationCap, Pencil, Trash2 } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { Education as EducationType, EducationFormData } from "../../types/candidate";

export function CandidateEducation() {
  const [records, setRecords] = useState<EducationType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<EducationFormData>({ institution: "", degree: "" });

  const fetch = useCallback(async () => {
    try {
      const data = await candidateApi.listEducation();
      setRecords(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const resetForm = () => setForm({ institution: "", degree: "" });

  const handleEdit = (r: EducationType) => {
    setEditing(r.id);
    setForm({
      institution: r.institution,
      degree: r.degree,
      branch: r.branch || "",
      specialization: r.specialization || "",
      cgpa: r.cgpa,
      start_date: r.start_date,
      end_date: r.end_date,
      is_current: r.is_current,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) {
        await candidateApi.updateEducation(editing, form);
      } else {
        await candidateApi.createEducation(form);
      }
      resetForm();
      setEditing(null);
      await fetch();
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (id: string) => {
    await candidateApi.deleteEducation(id);
    await fetch();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Education</h1>
          <p className="page-subtitle">Add your educational background</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <h2 className="section-title">
          {editing ? "Edit Education" : "Add Education"}
        </h2>
        <Input label="Institution" value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} required />
        <Input label="Degree" value={form.degree} onChange={(e) => setForm({ ...form, degree: e.target.value })} required />
        <Input label="Branch" value={form.branch || ""} onChange={(e) => setForm({ ...form, branch: e.target.value })} />
        <Input label="Specialization" value={form.specialization || ""} onChange={(e) => setForm({ ...form, specialization: e.target.value })} />
        <div className="grid grid-cols-2 gap-4">
          <Input label="CGPA / Percentage" type="number" step="0.1" value={form.cgpa ?? ""} onChange={(e) => setForm({ ...form, cgpa: e.target.value ? parseFloat(e.target.value) : null })} />
          <div className="flex items-end pb-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={form.is_current || false} onChange={(e) => setForm({ ...form, is_current: e.target.checked })} className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
              Currently studying
            </label>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Date" type="date" value={form.start_date || ""} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          <Input label="End Date" type="date" value={form.end_date || ""} onChange={(e) => setForm({ ...form, end_date: e.target.value })} disabled={form.is_current} />
        </div>
        <div className="flex gap-2 pt-1">
          <Button type="submit">{editing ? "Update" : "Add"}</Button>
          {editing && <Button variant="ghost" onClick={() => { resetForm(); setEditing(null); }}>Cancel</Button>}
        </div>
      </form>

      <div className="space-y-3">
        {records.length === 0 && (
          <div className="empty-state">
            <GraduationCap className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
            <p className="text-sm text-gray-500">No education records added yet.</p>
          </div>
        )}
        {records.map((r) => (
          <div key={r.id} className="card card-hover flex items-start justify-between gap-3 p-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 shadow-soft" aria-hidden="true">
                <GraduationCap className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="font-medium text-gray-900">{r.degree}</p>
                <p className="text-sm text-gray-500">{r.institution}</p>
                {r.cgpa && <p className="mt-0.5 text-xs text-gray-400">CGPA: {r.cgpa}</p>}
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
