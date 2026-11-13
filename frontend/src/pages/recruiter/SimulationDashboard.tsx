import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { StatCard } from "../../components/dashboard/StatCard";
import { EmptySimulationState } from "../../components/simulations/EmptySimulationState";
import { ScenarioStatusBadge } from "../../components/simulations/ScenarioStatusBadge";
import { useToast } from "../../contexts/ToastContext";
import { simulationApi } from "../../api/simulations";
import { recruiterJobApi } from "../../api/jobs";
import type { SimulationScenarioListResponse } from "../../types/simulations";
import { isSimulationEditable } from "../../types/simulations";

export function SimulationDashboard() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [data, setData] = useState<SimulationScenarioListResponse | null>(null);
  const [jobCount, setJobCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [list, jobs] = await Promise.all([
        simulationApi.list(),
        recruiterJobApi.listJobs(),
      ]);
      setData(list);
      setJobCount(jobs.length);
    } catch {
      addToast("Failed to load simulations", "error");
    }
  }, [addToast]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await loadData();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadData]);

  async function handleDelete(id: string) {
    try {
      await simulationApi.remove(id);
      addToast("Simulation deleted", "success");
      await loadData();
    } catch {
      addToast("Failed to delete simulation", "error");
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 animate-fade-up">
        <div className="skeleton h-8 w-64" />
        <div className="skeleton h-4 w-96 max-w-full" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-24 w-full" />
          ))}
        </div>
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }

  const stats = data?.stats;
  const items = data?.items ?? [];

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Simulation Intelligence</h1>
          <p className="page-subtitle">
            Build hiring-strategy sandboxes to test &quot;what-if&quot; screening configurations
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            onClick={() => navigate("/simulations/reports")}
          >
            View Reports
          </Button>
          <Button
            variant="secondary"
            onClick={() => navigate("/simulations/research")}
          >
            Research
          </Button>
          <Button onClick={() => navigate("/recruiter/simulations/create")}>
            New Simulation
          </Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
          <StatCard title="Total" value={stats.total} color="primary" />
          <StatCard title="Drafts" value={stats.drafts} color="amber" />
          <StatCard title="Ready" value={stats.ready} color="blue" />
          <StatCard
            title="Running"
            value={stats.running}
            color="purple"
            subtitle={`${stats.queued} queued`}
          />
          <StatCard title="Completed" value={stats.completed} color="green" />
          <StatCard title="Failed" value={stats.failed} color="red" />
        </div>
      )}

      {items.length === 0 ? (
        jobCount === 0 ? (
          <EmptySimulationState
            title="No simulations yet."
            description="Simulations are built against a job posting. Create a job first."
            actionLabel="Post your first job"
            onAction={() => navigate("/recruiter/jobs/create")}
          />
        ) : (
          <EmptySimulationState
            title="No simulations yet."
            description="Create a hiring-strategy sandbox to test a different screening configuration."
            actionLabel="Create your first simulation"
            onAction={() => navigate("/recruiter/simulations/create")}
          />
        )
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  Simulation
                </th>
                <th>
                  Status
                </th>
                <th>
                  Created by
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
                  <td className="whitespace-nowrap">
                    <button
                      onClick={() => navigate(`/recruiter/simulations/${item.id}`)}
                      className="text-sm font-medium text-gray-900 transition-colors duration-200 hover:text-primary-600"
                    >
                      {item.name}
                    </button>
                    <div className="text-sm text-gray-500">
                      {item.job_title} · {item.company}
                    </div>
                  </td>
                  <td className="whitespace-nowrap">
                    <ScenarioStatusBadge status={item.status} />
                  </td>
                  <td className="whitespace-nowrap text-gray-500">
                    {item.created_by_name}
                  </td>
                  <td className="whitespace-nowrap text-gray-500">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="whitespace-nowrap text-right text-sm">
                    <div className="flex items-center justify-end gap-3">
                      <button
                        onClick={() => navigate(`/recruiter/simulations/${item.id}`)}
                        className="font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
                      >
                        View
                      </button>
                      {isSimulationEditable(item.status) && (
                        <button
                          onClick={() => handleDelete(item.id)}
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
      )}
    </div>
  );
}