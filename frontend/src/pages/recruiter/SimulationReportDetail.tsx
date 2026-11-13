import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useToast } from "../../contexts/ToastContext";
import { SimulationReportSections } from "../../components/reports/SimulationReportSections";
import { simulationReportApi } from "../../api/simulationReports";
import type { SimulationReportResponse } from "../../api/simulationReports";

export default function SimulationReportDetail() {
  const { reportId = "" } = useParams();
  const { addToast } = useToast();
  const [report, setReport] = useState<SimulationReportResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadReport = useCallback(async () => {
    if (!reportId) return;
    setLoading(true);
    try {
      const result = await simulationReportApi.get(reportId);
      setReport(result);
    } catch {
      addToast("Failed to load report", "error");
    } finally {
      setLoading(false);
    }
  }, [reportId, addToast]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  if (loading && !report) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading report">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton h-9 w-96" />
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <h1 className="page-title">Report not found</h1>
        <Link to="/simulations/reports" className="mt-3 inline-block text-sm font-medium text-primary-600 hover:text-primary-700">
          Back to reports
        </Link>
      </div>
    );
  }

  const title = typeof report.title === "string" ? report.title : "Simulation Report";
  const reportData = report.report_data ?? {};

  return (
    <div className="mx-auto max-w-6xl animate-fade-up px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Link to="/simulations/reports" className="text-sm font-medium text-primary-600 hover:text-primary-700">
          Reports
        </Link>
        <h1 className="page-title mt-1">{title}</h1>
        {report.description && <p className="page-subtitle">{report.description}</p>}
      </div>

      <SimulationReportSections reportData={reportData} />
    </div>
  );
}
