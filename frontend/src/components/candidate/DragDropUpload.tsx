import { useCallback, useRef, useState } from "react";

interface DragDropUploadProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  maxSize?: number;
  disabled?: boolean;
}

const ALLOWED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "text/plain",
  "text/html",
  "application/rtf",
];

export function DragDropUpload({
  onFileSelect,
  accept = ".pdf,.docx,.doc,.txt,.html,.htm,.rtf",
  maxSize = 10 * 1024 * 1024,
  disabled = false,
}: DragDropUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback(
    (file: File): string | null => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      const allowed = accept.split(",").map((a) => a.trim().toLowerCase());
      if (!allowed.includes(ext) && !ALLOWED_TYPES.includes(file.type)) {
        return "Unsupported file type. Accepted: PDF, DOCX, DOC, TXT, HTML, RTF";
      }
      if (file.size > maxSize) {
        return `File too large. Maximum size is ${maxSize / (1024 * 1024)} MB`;
      }
      if (file.size === 0) {
        return "File is empty";
      }
      return null;
    },
    [accept, maxSize],
  );

  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      onFileSelect(file);
    },
    [validateFile, onFileSelect],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [disabled, handleFile],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setDragOver(true);
    },
    [disabled],
  );

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  return (
    <div className="w-full">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleClick();
          }
        }}
        aria-disabled={disabled}
        className={`relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-all duration-200 ${
          dragOver
            ? "border-primary-500 bg-primary-50/70 shadow-glow-sm"
            : "border-gray-300/80 bg-white/50 hover:border-primary-400 hover:bg-primary-50/50"
        } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <div
          className={`mb-3 flex h-14 w-14 items-center justify-center rounded-2xl transition-colors ${
            dragOver ? "bg-primary-100 text-primary-600" : "bg-primary-50 text-primary-500"
          }`}
        >
          <svg
            className="h-7 w-7"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        <p className="mb-1 text-sm font-medium text-gray-700">
          {dragOver ? "Drop your resume here" : "Drag & drop your resume, or click to browse"}
        </p>
        <p className="text-xs text-gray-500">
          PDF, DOCX, DOC, TXT, HTML, RTF (max {maxSize / (1024 * 1024)} MB)
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />
      </div>
      {error && (
        <p className="error-banner mt-2 items-center">
          <svg
            className="mt-0 h-4 w-4 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}
