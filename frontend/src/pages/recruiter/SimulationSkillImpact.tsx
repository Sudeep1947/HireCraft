import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { simulationApi } from "../../api/simulations";
import type {
  SkillImpactResponse,
  CandidateSkillImpact,
} from "../../types/skillImpact";
import {
  CHANGE_TYPE_LABELS,
  CHANGE_TYPE_COLORS,
  REQUIREMENT_LABELS,
  REQUIREMENT_COLORS,
  QUALIFICATION_COLORS,
  INSIGHT_TYPE_ICONS,
  formatCoverage,
  formatGap,
  formatScoreChange,
  getScoreColor,
  getCoverageColor,
} from "../../types/skillImpact";

export function SimulationSkillImpact() {
  const { simulationId } = useParams<{ simulationId: string }>();
  const [searchParams] = useSearchParams();
  const executionId = searchParams.get("execution_id") || undefined;

  const [loading, setLoading] = useState(true);
  const [impact, setImpact] = useState<SkillImpactResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "skills" | "coverage" | "gaps" | "candidates"
  >("overview");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterChangeType, setFilterChangeType] = useState<string>("all");
  const [selectedCandidate, setSelectedCandidate] =
    useState<CandidateSkillImpact | null>(null);

  useEffect(() => {
    if (!simulationId) return;
    setLoading(true);
    setError(null);
    simulationApi
      .getSkillImpact(simulationId, executionId)
      .then(setImpact)
      .catch((err) => {
        console.error(err);
        setError(err?.response?.data?.detail || "Failed to load skill impact");
      })
      .finally(() => setLoading(false));
  }, [simulationId, executionId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (!impact) return null;

  const { summary, skill_changes, skill_coverage, skill_gaps, candidates, insights } =
    impact;

  const filteredSkills = skill_changes.filter((sc) => {
    const matchesSearch =
      !searchQuery ||
      sc.skill_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter =
      filterChangeType === "all" || sc.change_type === filterChangeType;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Skill Impact</h1>
        <p className="text-sm text-gray-500 mt-1">
          {impact.scenario_name} &middot; {impact.job_title}
          {impact.company && ` \u00B7 ${impact.company}`}
        </p>
      </div>

      {/* What-if banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          <strong>What-if analysis</strong> &mdash; These results show how
          candidate skill matching and skill-related outcomes could change under
          a hypothetical hiring configuration. No live hiring data was modified
          by this simulation.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard label="Skills Analyzed" value={summary.total_skills_analyzed} />
        <StatCard label="Added" value={summary.skills_added} color="text-green-600" />
        <StatCard label="Removed" value={summary.skills_removed} color="text-red-600" />
        <StatCard label="Promoted" value={summary.skills_promoted} color="text-blue-600" />
        <StatCard label="Demoted" value={summary.skills_demoted} color="text-amber-600" />
        <StatCard
          label="Candidates Affected"
          value={summary.candidates_affected}
          color="text-purple-600"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {(["overview", "skills", "coverage", "gaps", "candidates"] as const).map(
            (tab) => (
              <button
                key={tab}
                className={`py-2 px-1 border-b-2 text-sm font-medium capitalize transition-colors ${
                  activeTab === tab
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ),
          )}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Skill changes */}
          <SkillChangeTable skills={filteredSkills} />

          {/* Insights */}
          {insights.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Insights
              </h3>
              <ul className="space-y-2">
                {insights.map((ins, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-gray-400 mt-0.5">
                      {INSIGHT_TYPE_ICONS[ins.type] || "\u2022"}
                    </span>
                    <span className="text-gray-700">{ins.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {activeTab === "skills" && (
        <div className="space-y-4">
          {/* Search and filter */}
          <div className="flex flex-wrap gap-3">
            <input
              type="text"
              placeholder="Search skills..."
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm flex-1 min-w-[200px]"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <select
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
              value={filterChangeType}
              onChange={(e) => setFilterChangeType(e.target.value)}
            >
              <option value="all">All Changes</option>
              <option value="added">Added</option>
              <option value="removed">Removed</option>
              <option value="promoted">Promoted</option>
              <option value="demoted">Demoted</option>
              <option value="unchanged">Unchanged</option>
            </select>
          </div>

          <SkillChangeTable skills={filteredSkills} />
        </div>
      )}

      {activeTab === "coverage" && (
        <SkillCoverageTable coverage={skill_coverage} />
      )}

      {activeTab === "gaps" && (
        <SkillGapTable gaps={skill_gaps} />
      )}

      {activeTab === "candidates" && (
        <div className="space-y-4">
          {selectedCandidate ? (
            <CandidateDetail
              candidate={selectedCandidate}
              onBack={() => setSelectedCandidate(null)}
            />
          ) : (
            <CandidateImpactTable
              candidates={candidates}
              onSelect={setSelectedCandidate}
            />
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Sub-components ──────────────────────────────────────────── */

function StatCard({
  label,
  value,
  color = "text-gray-900",
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function SkillChangeTable({ skills }: { skills: SkillImpactResponse["skill_changes"] }) {
  if (skills.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No skill changes detected.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Skill</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Change</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Baseline</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Simulation</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Baseline Match</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Sim Match</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Coverage Change</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Affected</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {skills.map((sc) => (
            <tr key={sc.skill_name} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium text-gray-900">
                {sc.skill_name}
              </td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${CHANGE_TYPE_COLORS[sc.change_type]}`}
                >
                  {CHANGE_TYPE_LABELS[sc.change_type]}
                </span>
              </td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${REQUIREMENT_COLORS[sc.baseline_requirement]}`}
                >
                  {REQUIREMENT_LABELS[sc.baseline_requirement]}
                </span>
              </td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${REQUIREMENT_COLORS[sc.simulation_requirement]}`}
                >
                  {REQUIREMENT_LABELS[sc.simulation_requirement]}
                </span>
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {sc.baseline_candidates_match}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {sc.simulation_candidates_match}
              </td>
              <td
                className={`px-3 py-2 text-right font-medium ${getCoverageColor(sc.coverage_change)}`}
              >
                {sc.coverage_change !== 0
                  ? `${sc.coverage_change > 0 ? "+" : ""}${formatCoverage(sc.coverage_change)}`
                  : "\u2014"}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {sc.candidates_affected}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkillCoverageTable({
  coverage,
}: {
  coverage: SkillImpactResponse["skill_coverage"];
}) {
  if (coverage.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No coverage data available.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Skill</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Baseline</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Simulation</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Change</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Baseline #</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Sim #</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Mandatory (B/S)</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Preferred (B/S)</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {coverage.map((sc) => (
            <tr key={sc.skill_name} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium text-gray-900">
                {sc.skill_name}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {formatCoverage(sc.baseline_coverage)}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {formatCoverage(sc.simulation_coverage)}
              </td>
              <td
                className={`px-3 py-2 text-right font-medium ${getCoverageColor(sc.coverage_change)}`}
              >
                {sc.coverage_change !== 0
                  ? `${sc.coverage_change > 0 ? "+" : ""}${formatCoverage(sc.coverage_change)}`
                  : "\u2014"}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {sc.baseline_candidates_match}/{sc.total_eligible}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {sc.simulation_candidates_match}/{sc.total_eligible}
              </td>
              <td className="px-3 py-2 text-center text-xs text-gray-500">
                {sc.is_mandatory_baseline ? "Y" : "N"} /{" "}
                {sc.is_mandatory_simulation ? "Y" : "N"}
              </td>
              <td className="px-3 py-2 text-center text-xs text-gray-500">
                {sc.is_preferred_baseline ? "Y" : "N"} /{" "}
                {sc.is_preferred_simulation ? "Y" : "N"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkillGapTable({ gaps }: { gaps: SkillImpactResponse["skill_gaps"] }) {
  if (gaps.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No gap data available.
      </div>
    );
  }

  const sorted = [...gaps].sort((a, b) => b.simulation_gap - a.simulation_gap);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Skill</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Baseline Gap</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Simulation Gap</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Change</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Required</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sorted.map((sg) => (
            <tr key={sg.skill_name} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium text-gray-900">
                {sg.skill_name}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {formatGap(sg.baseline_gap)}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {formatGap(sg.simulation_gap)}
              </td>
              <td
                className={`px-3 py-2 text-right font-medium ${
                  sg.gap_change > 0
                    ? "text-red-600"
                    : sg.gap_change < 0
                      ? "text-green-600"
                      : "text-gray-500"
                }`}
              >
                {sg.gap_change !== 0
                  ? `${sg.gap_change > 0 ? "+" : ""}${formatGap(sg.gap_change)}`
                  : "\u2014"}
              </td>
              <td className="px-3 py-2 text-center">
                {sg.is_required ? (
                  <span className="text-red-600 text-xs font-medium">Required</span>
                ) : (
                  <span className="text-gray-400 text-xs">Preferred</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CandidateImpactTable({
  candidates,
  onSelect,
}: {
  candidates: SkillImpactResponse["candidates"];
  onSelect: (c: CandidateSkillImpact) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No candidates affected by skill changes.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Candidate</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Skill Match Change</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Skills Gained</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Skills Lost</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Score Change</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Rank Change</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500">Qualification</th>
            <th className="px-3 py-2 text-center font-medium text-gray-500"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {candidates.map((c) => (
            <tr key={c.candidate_id} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium text-gray-900">
                {c.candidate_name}
              </td>
              <td
                className={`px-3 py-2 text-center font-medium ${getScoreColor(c.skill_match_change)}`}
              >
                {c.skill_match_change > 0 ? "+" : ""}
                {c.skill_match_change}
              </td>
              <td className="px-3 py-2 text-center text-green-600 text-xs">
                {c.skills_gained.length > 0
                  ? c.skills_gained.slice(0, 3).join(", ") +
                    (c.skills_gained.length > 3 ? "..." : "")
                  : "\u2014"}
              </td>
              <td className="px-3 py-2 text-center text-red-600 text-xs">
                {c.skills_lost.length > 0
                  ? c.skills_lost.slice(0, 3).join(", ") +
                    (c.skills_lost.length > 3 ? "..." : "")
                  : "\u2014"}
              </td>
              <td
                className={`px-3 py-2 text-right font-medium ${getScoreColor(c.score_change)}`}
              >
                {formatScoreChange(c.score_change)}
              </td>
              <td
                className={`px-3 py-2 text-right font-medium ${getScoreColor(-c.rank_change)}`}
              >
                {c.rank_change !== 0
                  ? `${c.rank_change > 0 ? "+" : ""}${c.rank_change}`
                  : "\u2014"}
              </td>
              <td className="px-3 py-2 text-center">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${QUALIFICATION_COLORS[c.qualification_change]}`}
                >
                  {c.qualification_change.replace(/_/g, " ")}
                </span>
              </td>
              <td className="px-3 py-2 text-center">
                <button
                  className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                  onClick={() => onSelect(c)}
                >
                  Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CandidateDetail({
  candidate,
  onBack,
}: {
  candidate: CandidateSkillImpact;
  onBack: () => void;
}) {
  return (
    <div className="space-y-4">
      <button
        className="text-blue-600 hover:text-blue-800 text-sm font-medium"
        onClick={onBack}
      >
        &larr; Back to candidates
      </button>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {candidate.candidate_name}
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div>
            <p className="text-xs text-gray-500">Score</p>
            <p className="text-sm">
              <span className="text-gray-600">{candidate.baseline_score}</span>
              <span className="text-gray-400 mx-1">&rarr;</span>
              <span className="font-medium">{candidate.simulation_score}</span>
              <span
                className={`ml-2 text-xs font-medium ${getScoreColor(candidate.score_change)}`}
              >
                ({formatScoreChange(candidate.score_change)})
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Rank</p>
            <p className="text-sm">
              <span className="text-gray-600">#{candidate.baseline_rank}</span>
              <span className="text-gray-400 mx-1">&rarr;</span>
              <span className="font-medium">#{candidate.simulation_rank}</span>
              <span
                className={`ml-2 text-xs font-medium ${getScoreColor(-candidate.rank_change)}`}
              >
                ({candidate.rank_change > 0 ? "+" : ""}
                {candidate.rank_change})
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Skill Match</p>
            <p className="text-sm">
              <span className="text-gray-600">
                {candidate.baseline_matched_skills.length}
              </span>
              <span className="text-gray-400 mx-1">&rarr;</span>
              <span className="font-medium">
                {candidate.simulation_matched_skills.length}
              </span>
              <span
                className={`ml-2 text-xs font-medium ${getScoreColor(candidate.skill_match_change)}`}
              >
                ({candidate.skill_match_change > 0 ? "+" : ""}
                {candidate.skill_match_change})
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Qualification</p>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${QUALIFICATION_COLORS[candidate.qualification_change]}`}
            >
              {candidate.qualification_change.replace(/_/g, " ")}
            </span>
          </div>
        </div>

        {/* Skills gained/lost */}
        {(candidate.skills_gained.length > 0 || candidate.skills_lost.length > 0) && (
          <div className="grid grid-cols-2 gap-4 mb-4">
            {candidate.skills_gained.length > 0 && (
              <div>
                <p className="text-xs font-medium text-green-700 mb-1">
                  Skills Gained
                </p>
                <div className="flex flex-wrap gap-1">
                  {candidate.skills_gained.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-green-700 bg-green-100"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {candidate.skills_lost.length > 0 && (
              <div>
                <p className="text-xs font-medium text-red-700 mb-1">
                  Skills Lost
                </p>
                <div className="flex flex-wrap gap-1">
                  {candidate.skills_lost.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-red-700 bg-red-100"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Required skills satisfied/unsatisfied */}
        {(candidate.newly_satisfied_required.length > 0 ||
          candidate.newly_unsatisfied_required.length > 0) && (
          <div className="grid grid-cols-2 gap-4">
            {candidate.newly_satisfied_required.length > 0 && (
              <div>
                <p className="text-xs font-medium text-green-700 mb-1">
                  Newly Satisfied Required
                </p>
                <div className="flex flex-wrap gap-1">
                  {candidate.newly_satisfied_required.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-green-700 bg-green-100"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {candidate.newly_unsatisfied_required.length > 0 && (
              <div>
                <p className="text-xs font-medium text-red-700 mb-1">
                  Newly Unsatisfied Required
                </p>
                <div className="flex flex-wrap gap-1">
                  {candidate.newly_unsatisfied_required.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-red-700 bg-red-100"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
