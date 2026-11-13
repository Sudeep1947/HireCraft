import { useCallback, useEffect, useState } from "react";
import { FolderGit2, Pencil, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { Project, ProjectFormData } from "../../types/candidate";

export function CandidateProjects() {
  const [records, setRecords] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<ProjectFormData>({ title: "" });

  const fetch = useCallback(async () => {
    try { setRecords(await candidateApi.listProjects()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const resetForm = () => setForm({ title: "" });
  const handleEdit = (r: Project) => {
    setEditing(r.id);
    setForm({
      title: r.title, description: r.description || "",
      technologies: r.technologies || "", github_link: r.github_link || "",
      live_demo: r.live_demo || "", start_date: r.start_date, end_date: r.end_date,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) { await candidateApi.updateProject(editing, form); }
      else { await candidateApi.createProject(form); }
      resetForm(); setEditing(null); await fetch();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    await candidateApi.deleteProject(id);
    await fetch();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-subtitle">Showcase your work</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <h2 className="section-title">{editing ? "Edit Project" : "Add Project"}</h2>
        <Input label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <div className="space-y-1.5">
          <label className="field-label" htmlFor="project-description">Description</label>
          <textarea
            id="project-description"
            value={form.description || ""}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
            className="field resize-y"
          />
        </div>
        <Input label="Technologies" value={form.technologies || ""} onChange={(e) => setForm({ ...form, technologies: e.target.value })} placeholder="React, Node.js, PostgreSQL" />
        <Input label="GitHub Link" value={form.github_link || ""} onChange={(e) => setForm({ ...form, github_link: e.target.value })} />
        <Input label="Live Demo" value={form.live_demo || ""} onChange={(e) => setForm({ ...form, live_demo: e.target.value })} />
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Date" type="date" value={form.start_date || ""} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          <Input label="End Date" type="date" value={form.end_date || ""} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
        </div>
        <div className="flex gap-2 pt-1">
          <Button type="submit">{editing ? "Update" : "Add"}</Button>
          {editing && <Button variant="ghost" onClick={() => { resetForm(); setEditing(null); }}>Cancel</Button>}
        </div>
      </form>

      <div className="space-y-3">
        {records.length === 0 && (
          <div className="empty-state">
            <FolderGit2 className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
            <p className="text-sm text-gray-500">No projects added yet.</p>
          </div>
        )}
        {records.map((r) => (
          <div key={r.id} className="card card-hover flex items-start justify-between gap-3 p-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600 shadow-soft" aria-hidden="true">
                <FolderGit2 className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="font-medium text-gray-900">{r.title}</p>
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
