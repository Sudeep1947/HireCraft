import { useCallback, useEffect, useState } from "react";
import { Award, Pencil, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { Certification, CertificationFormData } from "../../types/candidate";

export function CandidateCertifications() {
  const [records, setRecords] = useState<Certification[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<CertificationFormData>({ name: "", organization: "" });

  const fetch = useCallback(async () => {
    try { setRecords(await candidateApi.listCertifications()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const resetForm = () => setForm({ name: "", organization: "" });

  const handleEdit = (r: Certification) => {
    setEditing(r.id);
    setForm({ name: r.name, organization: r.organization, issue_date: r.issue_date, expiry_date: r.expiry_date, credential_id: r.credential_id || "", credential_url: r.credential_url || "" });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) { await candidateApi.updateCertification(editing, form); }
      else { await candidateApi.createCertification(form); }
      resetForm(); setEditing(null); await fetch();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    await candidateApi.deleteCertification(id);
    await fetch();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Certifications</h1>
          <p className="page-subtitle">Add your professional certifications</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <h2 className="section-title">{editing ? "Edit Certification" : "Add Certification"}</h2>
        <Input label="Certification Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <Input label="Organization" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} required />
        <div className="grid grid-cols-2 gap-4">
          <Input label="Issue Date" type="date" value={form.issue_date || ""} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} />
          <Input label="Expiry Date" type="date" value={form.expiry_date || ""} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
        </div>
        <Input label="Credential ID" value={form.credential_id || ""} onChange={(e) => setForm({ ...form, credential_id: e.target.value })} />
        <Input label="Credential URL" value={form.credential_url || ""} onChange={(e) => setForm({ ...form, credential_url: e.target.value })} />
        <div className="flex gap-2 pt-1">
          <Button type="submit">{editing ? "Update" : "Add"}</Button>
          {editing && <Button variant="ghost" onClick={() => { resetForm(); setEditing(null); }}>Cancel</Button>}
        </div>
      </form>

      <div className="space-y-3">
        {records.length === 0 && (
          <div className="empty-state">
            <Award className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
            <p className="text-sm text-gray-500">No certifications added yet.</p>
          </div>
        )}
        {records.map((r) => (
          <div key={r.id} className="card card-hover flex items-start justify-between gap-3 p-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600 shadow-soft" aria-hidden="true">
                <Award className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="font-medium text-gray-900">{r.name}</p>
                <p className="text-sm text-gray-500">{r.organization}</p>
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
