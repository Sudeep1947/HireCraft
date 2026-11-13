import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { DragDropUpload } from "../../components/candidate/DragDropUpload";
import { candidateApi } from "../../api/candidate";

export function ResumeUpload() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const pollingId = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const cancelledRef = useRef(false);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (pollingId.current) clearTimeout(pollingId.current);
    };
  }, []);

  async function handleFileSelect(file: File) {
    setUploading(true);
    setError(null);
    setProgress(10);

    try {
      const result = await candidateApi.uploadResume(file);
      setProgress(100);

      const checkStatus = async () => {
        if (cancelledRef.current) return;
        try {
          const status = await candidateApi.getResumeStatus(result.id);
          if (cancelledRef.current) return;
          if (status.status === "parsed" || status.status === "failed") {
            setUploading(false);
            navigate(`/candidate/resume/${result.id}`);
          } else {
            setProgress(status.progress);
            pollingId.current = setTimeout(checkStatus, 2000);
          }
        } catch {
          if (!cancelledRef.current) {
            setUploading(false);
            navigate(`/candidate/resume/${result.id}`);
          }
        }
      };
      pollingId.current = setTimeout(checkStatus, 1000);
    } catch (err: any) {
      if (!cancelledRef.current) {
        const detail = err?.response?.data?.detail || err?.message || "Upload failed";
        setError(detail);
        setUploading(false);
      }
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">Upload Resume</h1>
        <p className="page-subtitle">
          Upload your resume to get AI-powered parsing and analysis
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <DragDropUpload onFileSelect={handleFileSelect} disabled={uploading} />

      {uploading && (
        <div className="card p-5">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-gray-700">Uploading and processing...</span>
            <span className="font-semibold text-primary-700">{progress}%</span>
          </div>
          <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-brand-gradient transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="field-hint">
            Your resume is being parsed. This may take a moment.
          </p>
        </div>
      )}

      <button
        onClick={() => navigate("/candidate/resume")}
        className="btn-ghost btn-sm"
      >
        &larr; Back to Resumes
      </button>
    </div>
  );
}
