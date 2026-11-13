import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FlaskConical } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { experimentApi } from "../../api/experiments";
import type {
  ExperimentListItem,
  ExperimentListResponse,
} from "../../types/simulationExperiments";
import {
  EXPERIMENT_TYPE_LABELS,
  STATUS_COLORS,
} from "../../types/simulationExperiments";

const PAGE_SIZE = 20;

export function ResearchDashboard() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [data, setData] = useState<ExperimentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const fetchExperiments = useCallback(async () => {
    setLoading(true);
    try {
      const result = await experimentApi.list({ page, page_size: PAGE_SIZE });
      setData(result);
    } catch {
      addToast("Failed to load experiments", "error");
    } finally {
      setLoading(false);
    }
  }, [page, addToast]);

  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this experiment?")) return;
    try {
      await experimentApi.delete(id);
      addToast("Experiment deleted", "success");
      await fetchExperiments();
    } catch {
      addToast("Failed to delete experiment", "error");
    }
  }

  const experiments = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            Research Intelligence
          </h1>
          <p className="page-subtitle">
            Advanced what-if analysis: sensitivity, robustness, and stability
            experiments over simulation configurations.
          </p>
        </div>
        <Button onClick={() => navigate("/simulations/research/new")}>
          New Experiment
        </Button>
      </div>

      <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm font-medium text-amber-800 shadow-xs">
        <strong>Advanced What-if Analysis:</strong> These experiments evaluate
        hypothetical configurations. They do not modify live hiring data.
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="skeleton h-6 w-56" />
          <div className="skeleton h-64 w-full" />
        </div>
      ) : experiments.length === 0 ? (
        <div className="empty-state">
          <FlaskConical className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-base font-semibold text-gray-900">No experiments yet.</p>
          <p className="mt-1 text-sm text-gray-500">
            Create an experiment to analyze parameter sensitivity, robustness,
            or stability.
          </p>
          <Button
            className="mt-4"
            onClick={() => navigate("/simulations/research/new")}
          >
            Create your first experiment
          </Button>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    Experiment
                  </th>
                  <th>
                    Type
                  </th>
                  <th>
                    Status
                  </th>
                  <th>
                    Progress
                  </th>
                  <th>
                    Created
                  </th>
                  <th className="text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((exp: ExperimentListItem) => (
                  <tr key={exp.id}>
                    <td>
                      <button
                        onClick={() =>
                          navigate(`/simulations/research/${exp.id}`)
                        }
                        className="text-sm font-medium text-gray-900 transition-colors duration-200 hover:text-primary-600"
                      >
                        {exp.name}
                      </button>
                      <div className="text-sm text-gray-500">
                        {exp.job_title}
                        {exp.base_scenario_name &&
                          ` · ${exp.base_scenario_name}`}
                      </div>
                    </td>
                    <td className="whitespace-nowrap text-gray-600">
                      {EXPERIMENT_TYPE_LABELS[exp.experiment_type] ||
                        exp.experiment_type}
                    </td>
                    <td className="whitespace-nowrap">
                      <span
                        className={`badge ${
                          STATUS_COLORS[exp.status] || "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {exp.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap text-gray-600">
                      {exp.completed_configurations}/{exp.total_configurations}
                      {exp.failed_configurations > 0 && (
                        <span className="text-red-500">
                          {" "}
                          ({exp.failed_configurations} failed)
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap text-gray-500">
                      {new Date(exp.created_at).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap text-right text-sm">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          onClick={() =>
                            navigate(`/simulations/research/${exp.id}`)
                          }
                          className="font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
                        >
                          View
                        </button>
                        {exp.status === "draft" && (
                          <button
                            onClick={() => handleDelete(exp.id)}
                            className="font-medium text-red-600 transition-colors duration-200 hover:text-red-700"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                {Math.min(page * PAGE_SIZE, total)} of {total}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
