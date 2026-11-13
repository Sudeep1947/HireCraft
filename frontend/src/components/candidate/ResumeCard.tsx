import type { Resume } from "../../types/candidate";

interface ResumeCardProps {
  resume: Resume;
  onView?: (id: string) => void;
  onDelete?: (id: string) => void;
  onSetPrimary?: (id: string) => void;
}

const FILE_ICONS: Record<string, string> = {
  pdf: "\u{1F4C4}",
  docx: "\u{1F4DD}",
  doc: "\u{1F4DD}",
  txt: "\u{1F4C4}",
  html: "\u{1F310}",
  htm: "\u{1F310}",
  rtf: "\u{1F4C4}",
};

const STATUS_BADGES: Record<string, string> = {
  uploaded: "badge-warning",
  processing: "badge-info",
  parsed: "badge-success",
  failed: "badge-danger",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ResumeCard({ resume, onView, onDelete, onSetPrimary }: ResumeCardProps) {
  const icon = FILE_ICONS[resume.file_type] || "\u{1F4C4}";
  const statusBadge = STATUS_BADGES[resume.status] || "badge-neutral";

  return (
    <div className="card card-hover flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-xl shadow-soft"
          aria-hidden="true"
        >
          {icon}
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-gray-900">
            {resume.original_filename}
            {resume.is_primary && (
              <span className="badge-primary ml-2 align-middle">
                Primary
              </span>
            )}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span>{formatFileSize(resume.file_size)}</span>
            <span className="text-gray-300" aria-hidden="true">|</span>
            <span>{resume.file_type.toUpperCase()}</span>
            {resume.language && (
              <>
                <span className="text-gray-300" aria-hidden="true">|</span>
                <span>{resume.language.toUpperCase()}</span>
              </>
            )}
            <span className="text-gray-300" aria-hidden="true">|</span>
            <span>v{resume.version}</span>
            <span className="text-gray-300" aria-hidden="true">|</span>
            <span className={statusBadge}>{resume.status}</span>
          </div>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {!resume.is_primary && resume.status === "parsed" && onSetPrimary && (
          <button
            onClick={() => onSetPrimary(resume.id)}
            className="btn-ghost btn-sm text-primary-600 hover:text-primary-700"
          >
            Set Primary
          </button>
        )}
        {onView && (
          <button
            onClick={() => onView(resume.id)}
            className="btn-ghost btn-sm"
          >
            View
          </button>
        )}
        {onDelete && (
          <button
            onClick={() => onDelete(resume.id)}
            className="btn-ghost btn-sm text-red-600 hover:bg-red-50 hover:text-red-700"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
