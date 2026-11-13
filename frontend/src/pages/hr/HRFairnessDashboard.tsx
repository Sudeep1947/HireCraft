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
  SeverityCounts,
} from "../../components/fairness/FairnessComponents";
import type { FairnessOverview, FairnessMetrics, BiasAlert } from "../../types/fairness";

export function HRFairnessDashboard() {
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
          getBiasAlerts(30),
        ]);
        setOverview(ov);
        setMetrics(met);
        setAlerts(al);
      } catch {
        setError("Failed to load HR fairness data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="page-header">
          <div>
            <div className="page-title">HR Fairness &amp; Ethics Dashboard</div>
            <p className="page-subtitle">
              Organization-wide fairness monitoring, diversity tracking, and compliance oversight.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="skeleton h-64 rounded-xl" />
          <div className="skeleton h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-8">
        <div className="page-header">
          <div>
            <div className="page-title">HR Fairness &amp; Ethics Dashboard</div>
            <p className="page-subtitle">
              Organization-wide fairness monitoring, diversity tracking, and compliance oversight.
            </p>
          </div>
        </div>
        <div className="error-banner">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  const severityCounts: Record<string, number> = { high: 0, medium: 0, low: 0 };
  alerts.forEach((a) => {
    severityCounts[a.severity] = (severityCounts[a.severity] || 0) + 1;
  });

  return (
    <div className="space-y-8">
      <div className="page-header">
        <div>
          <div className="page-title">HR Fairness &amp; Ethics Dashboard</div>
          <p className="page-subtitle">
            Organization-wide fairness monitoring, diversity tracking, and compliance oversight.
          </p>
        </div>
      </div>

      {overview && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="col-span-1 md:col-span-2 flex justify-center rounded-xl bg-white card p-6">
              <FairnessScoreCard score={overview.overall_fairness_score} label="Organization Fairness" />
            </div>
            <DiversityStat label="Total Screened" value={overview.total_screened} color="blue" />
            <DiversityStat label="Total Candidates" value={overview.total_candidates} color="green" />
            <DiversityStat label="Active Jobs" value={overview.total_jobs} color="purple" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
            <div className="card p-4 rounded-xl">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Bias Alerts</p>
              <div className="mt-2">
                <SeverityCounts counts={severityCounts} />
              </div>
            </div>
          </div>
        </>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {metrics && (
          <div className="card p-6 rounded-xl">
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
            <p className="text-xs text-slate-500 mt-2">Based on {metrics.data_points} data points</p>
          </div>
        )}

        <div className="card p-6 rounded-xl">
          <h2 className="section-title mb-4">Bias Alerts</h2>
          <BiasAlertPanel alerts={alerts} />
        </div>
      </div>

      {overview?.diversity_indicators && (
        <div className="card p-6 rounded-xl">
          <h2 className="section-title mb-4">Diversity Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-medium text-slate-700 mb-3">Gender Distribution</h3>
              {Object.entries(overview.diversity_indicators.gender_distribution || {}).map(([gender, count]) => {
                const total = overview.total_candidates || 1;
                const pct = ((count / total) * 100).toFixed(1);
                return (
                  <div key={gender} className="flex items-center gap-3 mb-2">
                    <span className="text-sm text-slate-600 w-36 capitalize">{gender.replace(/_/g, " ")}</span>
                    <div className="flex-1 bg-slate-100 rounded-full h-3">
                      <div
                        className="h-3 rounded-full bg-primary-500 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500 w-16 text-right">{count} ({pct}%)</span>
                  </div>
                );
              })}
            </div>
            <div>
              <h3 className="text-sm font-medium text-slate-700 mb-3">Location Distribution</h3>
              {Object.entries(overview.diversity_indicators.location_distribution || {}).map(([loc, count]) => {
                const total = overview.total_candidates || 1;
                const pct = ((count / total) * 100).toFixed(1);
                return (
                  <div key={loc} className="flex items-center gap-3 mb-2">
                    <span className="text-sm text-slate-600 w-36 truncate">{loc}</span>
                    <div className="flex-1 bg-slate-100 rounded-full h-3">
                      <div
                        className="h-3 rounded-full bg-violet-500 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500 w-16 text-right">{count} ({pct}%)</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="card p-6 rounded-xl">
        <h2 className="section-title mb-4">Compliance Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-medium text-emerald-700">Fair Hiring Practices</p>
            <p className="text-xs text-emerald-600 mt-1">All candidates evaluated using the same criteria. No protected attributes used in scoring.</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-medium text-emerald-700">Audit Trail</p>
            <p className="text-xs text-emerald-600 mt-1">All fairness analyses, bias alerts, and ranking changes are logged for compliance review.</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-medium text-emerald-700">Transparency</p>
            <p className="text-xs text-emerald-600 mt-1">Candidates can view their fairness status and request human review of AI decisions.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
