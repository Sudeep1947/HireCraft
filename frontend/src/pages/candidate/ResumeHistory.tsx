import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText } from "lucide-react";
import { candidateApi } from "../../api/candidate";
import type { ResumeVersion } from "../../types/candidate";

const STATUS_COLORS: Record<string, string> = {
  uploaded: "bg-amber-50 text-amber-700 ring-amber-200/70",
  processing: "bg-sky-50 text-sky-700 ring-sky-200/70",
  parsed: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
  failed: "bg-red-50 text-red-700 ring-red-200/70",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ResumeHistory() {
  const navigate = useNavigate();
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const data = await candidateApi.getResumeVersions();
        setVersions(data);
      } catch {
        setError("Failed to load resume history");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-56" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-24 w-full" />
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Resume History</h1>
          <p className="page-subtitle">
            View all versions of your uploaded resumes
          </p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {versions.length === 0 ? (
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
      ) : (
        <div className="space-y-3">
          {versions.map((v) => {
            const statusColor = STATUS_COLORS[v.status] || "bg-gray-100 text-gray-600 ring-gray-200/80";
            return (
              <div
                key={v.id}
                className="card card-hover flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-center gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-gradient-soft font-display text-sm font-bold text-primary-700">
                    v{v.version}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-gray-900">
                      {v.original_filename}
                      {v.is_primary && (
                        <span className="badge-primary ml-2 align-middle">
                          Primary
                        </span>
                      )}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                      <span>{formatFileSize(v.file_size)}</span>
                      <span className="text-gray-300">|</span>
                      <span>{v.file_type.toUpperCase()}</span>
                      <span className="text-gray-300">|</span>
                      <span>{new Date(v.created_at).toLocaleDateString()}</span>
                      <span className={`badge ${statusColor}`}>
                        {v.status}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => navigate(`/candidate/resume/${v.id}`)}
                  className="btn-secondary btn-sm shrink-0"
                >
                  View
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
