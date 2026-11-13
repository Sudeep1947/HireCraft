import { useCallback, useEffect, useState } from "react";
import { Languages as LanguagesIcon, Pencil, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { Language, LanguageFormData } from "../../types/candidate";

const levels = ["beginner", "elementary", "intermediate", "advanced", "native"];

export function CandidateLanguages() {
  const [records, setRecords] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<LanguageFormData>({ language: "", reading: "intermediate", writing: "intermediate", speaking: "intermediate" });

  const fetch = useCallback(async () => {
    try { setRecords(await candidateApi.listLanguages()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const resetForm = () => setForm({ language: "", reading: "intermediate", writing: "intermediate", speaking: "intermediate" });

  const handleEdit = (r: Language) => {
    setEditing(r.id);
    setForm({ language: r.language, reading: r.reading, writing: r.writing, speaking: r.speaking });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) { await candidateApi.updateLanguage(editing, form); }
      else { await candidateApi.createLanguage(form); }
      resetForm(); setEditing(null); await fetch();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    await candidateApi.deleteLanguage(id);
    await fetch();
  };

  const LevelSelect = ({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) => (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={label}
      className="field px-2.5 py-2 text-xs"
    >
      {levels.map((l) => <option key={l} value={l}>{l}</option>)}
    </select>
  );

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Languages</h1>
          <p className="page-subtitle">Add languages you speak</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <h2 className="section-title">{editing ? "Edit Language" : "Add Language"}</h2>
        <Input label="Language" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} required placeholder="e.g. English, Spanish" />
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <span className="field-label block text-xs">Reading</span>
            <LevelSelect value={form.reading || "intermediate"} onChange={(v) => setForm({ ...form, reading: v })} label="Reading level" />
          </div>
          <div className="space-y-1.5">
            <span className="field-label block text-xs">Writing</span>
            <LevelSelect value={form.writing || "intermediate"} onChange={(v) => setForm({ ...form, writing: v })} label="Writing level" />
          </div>
          <div className="space-y-1.5">
            <span className="field-label block text-xs">Speaking</span>
            <LevelSelect value={form.speaking || "intermediate"} onChange={(v) => setForm({ ...form, speaking: v })} label="Speaking level" />
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Button type="submit">{editing ? "Update" : "Add"}</Button>
          {editing && <Button variant="ghost" onClick={() => { resetForm(); setEditing(null); }}>Cancel</Button>}
        </div>
      </form>

      <div className="space-y-3">
        {records.length === 0 && (
          <div className="empty-state">
            <LanguagesIcon className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
            <p className="text-sm text-gray-500">No languages added yet.</p>
          </div>
        )}
        {records.map((r) => (
          <div key={r.id} className="card card-hover flex items-start justify-between gap-3 p-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-50 text-sky-600 shadow-soft" aria-hidden="true">
                <LanguagesIcon className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="font-medium text-gray-900">{r.language}</p>
                <p className="mt-0.5 text-xs text-gray-400">R:{r.reading} W:{r.writing} S:{r.speaking}</p>
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
