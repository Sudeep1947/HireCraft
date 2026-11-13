import { useState, useEffect } from "react";
import {
  getFairnessOverview,
  getFairnessMetrics,
  getBiasAlerts,
} from "../../api/fairness";
import {
  FairnessScoreCard,
  FairnessMetricsTable,
  BiasAlertPanel,
  DiversityStat,
} from "../../components/fairness/FairnessComponents";
import type { FairnessOverview, FairnessMetrics, BiasAlert } from "../../types/fairness";

export function RecruiterFairnessDashboard() {
  const [overview, setOverview] = useState<FairnessOverview | null>(null);
  const [metrics, setMetrics] = useState<FairnessMetrics | null>(null);
  const [alerts, setAlerts] = useState<BiasAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [ov, met, al] = await Promise.all([
          getFairnessOverview(),
          getFairnessMetrics(),
          getBiasAlerts(20),
        ]);
        setOverview(ov);
        setMetrics(met);
        setAlerts(al);
      } catch {
        setError("Failed to load fairness data. You may not have permission.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading fairness dashboard">
        <div className="skeleton h-9 w-80" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-4 w-24" />
              <div className="skeleton mt-2 h-8 w-16" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div className="skeleton h-64 w-full" />
          <div className="skeleton h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="error-banner" role="alert">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-up">
      <div>
        <h1 className="page-title">Fairness & Bias Dashboard</h1>
        <p className="page-subtitle">Monitor AI fairness, detect bias, and ensure ethical hiring.</p>
      </div>

      {overview && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
            <div className="col-span-1 flex justify-center md:col-span-2">
              <FairnessScoreCard score={overview.overall_fairness_score} label="Overall Fairness" />
            </div>
            <DiversityStat label="Total Screened" value={overview.total_screened} color="blue" />
            <DiversityStat label="Total Candidates" value={overview.total_candidates} color="green" />
            <DiversityStat label="Total Jobs" value={overview.total_jobs} color="purple" />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <DiversityStat
              label="Gender Diversity Index"
              value={overview.diversity_indicators?.gender_diversity_index?.toFixed(3) || "N/A"}
              color="orange"
            />
            <DiversityStat
              label="Location Diversity Index"
              value={overview.diversity_indicators?.location_diversity_index?.toFixed(3) || "N/A"}
              color="green"
            />
            <DiversityStat
              label="Compliance Status"
              value={overview.compliance_status?.replace(/_/g, " ") || "N/A"}
              color={overview.compliance_status === "compliant" ? "green" : "orange"}
            />
          </div>
        </>
      )}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {metrics && (
          <div className="card p-6">
            <h2 className="section-title mb-4">Fairness Metrics</h2>
            <FairnessMetricsTable
              metrics={{
                statistical_parity_difference: metrics.statistical_parity_difference,
                disparate_impact_ratio: metrics.disparate_impact_ratio,
                equal_opportunity_difference: metrics.equal_opportunity_difference,
                demographic_parity: metrics.demographic_parity,
                consistency_score: metrics.consistency_score,
                composite_fairness_score: metrics.composite_fairness_score,
              }}
            />
            <p className="mt-2 text-xs text-gray-500">Based on {metrics.data_points} data points</p>
          </div>
        )}

        <div className="card p-6">
          <h2 className="section-title mb-4">Bias Alerts</h2>
          <BiasAlertPanel alerts={alerts} />
        </div>
      </div>

      {overview?.diversity_indicators && (
        <div className="card p-6">
          <h2 className="section-title mb-4">Candidate Distribution</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-medium text-gray-700">Gender Distribution</h3>
              {Object.entries(overview.diversity_indicators.gender_distribution || {}).map(([gender, count]) => (
                <div key={gender} className="mb-1 flex items-center gap-2">
                  <span className="w-32 text-sm text-gray-600">{gender.replace(/_/g, " ")}</span>
                  <div className="h-2 flex-1 rounded-full bg-gray-100">
                    <div
                      className="h-2 rounded-full bg-sky-500"
                      style={{ width: `${(count / Math.max(overview.total_candidates, 1)) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 text-xs text-gray-500">{count}</span>
                </div>
              ))}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium text-gray-700">Location Distribution</h3>
              {Object.entries(overview.diversity_indicators.location_distribution || {}).map(([loc, count]) => (
                <div key={loc} className="mb-1 flex items-center gap-2">
                  <span className="w-32 truncate text-sm text-gray-600">{loc}</span>
                  <div className="h-2 flex-1 rounded-full bg-gray-100">
                    <div
                      className="h-2 rounded-full bg-violet-500"
                      style={{ width: `${(count / Math.max(overview.total_candidates, 1)) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 text-xs text-gray-500">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
