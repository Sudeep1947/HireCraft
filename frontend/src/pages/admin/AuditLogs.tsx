import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { dashboardApi } from "../../api/dashboard";
import type { AuditLogItem } from "../../api/dashboard";
import { formatDateTime } from "../../utils/dateTime";

export function AuditLogs() {
  const { addToast } = useToast();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi
      .getAdminAuditLogs()
      .then(setLogs)
      .catch(() => addToast("Failed to load audit logs", "error"))
      .finally(() => setLoading(false));
  }, [addToast]);

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Logs</h1>
          <p className="page-subtitle">{logs.length} recent entries</p>
        </div>
        <span className="badge-primary self-start">
          <ScrollText className="h-3.5 w-3.5" aria-hidden="true" /> Security trail
        </span>
      </div>

      {logs.length === 0 ? (
        <div className="empty-state">
          <ScrollText className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
          <h3 className="text-base font-semibold text-gray-900">No audit logs recorded yet.</h3>
          <p className="mt-1 text-sm text-gray-500">
            Administrative actions will be recorded here as they happen.
          </p>
        </div>
      ) : (
        <div className="table-wrap animate-fade-in">
          <table className="data-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>User</th>
                <th>Resource</th>
                <th>Status</th>
                <th>IP</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="font-medium text-gray-900">{log.action}</td>
                  <td className="text-gray-500">{log.user_id || "N/A"}</td>
                  <td className="text-gray-500">
                    {log.resource_type ? `${log.resource_type}` : "N/A"}
                  </td>
                  <td>
                    <span className={log.success ? "badge-success" : "badge-danger"}>
                      {log.success ? "Success" : "Failed"}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-gray-500">{log.ip_address || "N/A"}</td>
                  <td className="text-gray-500">
                    {formatDateTime(log.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
