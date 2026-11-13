import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { candidateApi } from "../../api/candidate";
import { useToast } from "../../contexts/ToastContext";
import type { SyncDiffResponse, SyncDiffItem } from "../../types/candidate";

export function ProfileSync() {
  const { id } = useParams<{ id: string }>();
  const { addToast } = useToast();
  const [syncData, setSyncData] = useState<SyncDiffResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [applying, setApplying] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const resumeId = id;
    async function load() {
      try {
        const data = await candidateApi.getSyncDiff(resumeId);
        setSyncData(data);
      } catch {
        setError("Failed to load sync data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleAccept(section: string, index: number, field?: string) {
    if (!id) return;
    setApplying(`${section}-${index}`);
    try {
      await candidateApi.acceptSync(id, section, index, field);
      addToast(`Accepted ${section} item`, "success");
      const data = await candidateApi.getSyncDiff(id);
      setSyncData(data);
    } catch {
      addToast("Failed to accept", "error");
    } finally {
      setApplying(null);
    }
  }

  async function handleReject(section: string, index: number, field?: string) {
    if (!id) return;
    setApplying(`${section}-${index}`);
    try {
      await candidateApi.rejectSync(id, section, index, field);
      addToast(`Rejected ${section} item`, "info");
    } catch {
      addToast("Failed to reject", "error");
    } finally {
      setApplying(null);
    }
  }

  if (loading)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="skeleton h-9 w-72" />
        <div className="skeleton h-44 w-full" />
        <div className="skeleton h-44 w-full" />
      </div>
    );
  if (error)
    return (
      <div className="space-y-6 animate-fade-up">
        <div className="error-banner">{error}</div>
      </div>
    );

  const sections = [
    { key: "personal_info", label: "Personal Info", items: syncData?.personal_info || [] },
    { key: "education", label: "Education", items: syncData?.education || [] },
    { key: "experience", label: "Experience", items: syncData?.experience || [] },
    { key: "skills", label: "Skills", items: syncData?.skills || [] },
    { key: "projects", label: "Projects", items: syncData?.projects || [] },
    { key: "certifications", label: "Certifications", items: syncData?.certifications || [] },
    { key: "languages", label: "Languages", items: syncData?.languages || [] },
  ];

  const hasDiffs = sections.some((s) => s.items.length > 0);

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">Profile Synchronization</h1>
        <p className="page-subtitle">
          Compare parsed resume data with your profile and sync changes
        </p>
      </div>

      {!hasDiffs ? (
        <div className="empty-state">
          <CheckCircle2 className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-sm text-gray-500">
            No differences found. Your profile is already in sync with this resume.
          </p>
        </div>
      ) : (
        sections.map(
          (section) =>
            section.items.length > 0 && (
              <div key={section.key} className="card p-6">
                <h2 className="section-title mb-4">{section.label}</h2>
                <div className="space-y-3">
                  {section.items.map((item: SyncDiffItem, idx: number) => (
                    <div
                      key={`${section.key}-${idx}`}
                      className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white/70 p-3.5 transition-colors duration-200 hover:border-primary-200 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="section-label">
                          {item.field}
                        </p>
                        <div className="mt-1.5 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 sm:gap-4">
                          <div>
                            <span className="text-gray-400">Resume: </span>
                            <span className="font-medium text-emerald-700">
                              {item.parsed_value || "—"}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">Profile: </span>
                            <span className="font-medium text-primary-700">
                              {item.profile_value || "—"}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 sm:ml-4">
                        <button
                          onClick={() => handleAccept(section.key, idx, item.field)}
                          disabled={applying === `${section.key}-${idx}`}
                          className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-all duration-200 hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Accept
                        </button>
                        <button
                          onClick={() => handleReject(section.key, idx, item.field)}
                          disabled={applying === `${section.key}-${idx}`}
                          className="btn-secondary btn-sm disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ),
        )
      )}
    </div>
  );
}
