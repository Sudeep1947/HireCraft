import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import {
  simulationReportApi,
  type SimulationReportListResponse,
} from "../../api/simulationReports";

const PAGE_SIZE = 20;

const REPORT_TYPE_LABELS: Record<string, string> = {
  simulation: "Simulation Report",
  candidate_impact: "Candidate Impact",
  fairness_impact: "Fairness Impact",
  comparison: "Strategy Comparison",
  sandbox: "Sandbox Report",
  executive: "Executive Summary",
  technical: "Technical Report",
};

const STATUS_STYLES: Record<string, string> = {
  requested: "badge-warning",
  generating: "badge-info",
  completed: "badge-success",
  failed: "badge-danger",
};

export default function SimulationReportsList() {
  const { addToast } = useToast();
  const [data, setData] = useState<SimulationReportListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      const result = await simulationReportApi.list({ page, page_size: PAGE_SIZE });
      setData(result);
    } catch {
      addToast("Failed to load reports", "error");
    } finally {
      setLoading(false);
    }
  }, [page, addToast]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this report?")) return;
    try {
      await simulationReportApi.delete(id);
      addToast("Report deleted", "success");
      fetchReports();
    } catch {
      addToast("Failed to delete report", "error");
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4 animate-fade-up">
        <div className="skeleton h-8 w-64" />
        <div className="skeleton h-4 w-80 max-w-full" />
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Simulation Reports</h1>
          <p className="page-subtitle">
            View and export structured simulation analysis reports
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <FileText className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="text-base font-semibold text-gray-900">No reports generated yet.</p>
          <p className="mt-1 text-sm text-gray-500">
            Generate a report from any completed simulation.
          </p>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    Title
                  </th>
                  <th>
                    Type
                  </th>
                  <th>
                    Status
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
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        to={`/simulations/reports/${item.id}`}
                        className="font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
                      >
                        {item.title}
                      </Link>
                      {item.scenario_name && (
                        <p className="mt-0.5 text-xs text-gray-400">
                          {item.scenario_name}
                        </p>
                      )}
                    </td>
                    <td className="whitespace-nowrap text-gray-600">
                      {REPORT_TYPE_LABELS[item.report_type] ?? item.report_type}
                    </td>
                    <td className="whitespace-nowrap">
                      <span className={STATUS_STYLES[item.status] ?? "badge-neutral"}>
                        {item.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap text-gray-500">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap text-right text-sm">
                      <Link
                        to={`/simulations/reports/${item.id}`}
                        className="mr-3 font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
                      >
                        View
                      </Link>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="font-medium text-red-600 transition-colors duration-200 hover:text-red-700"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Showing {(page - 1) * PAGE_SIZE + 1}–
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
