import type {
  RequirementChangeDetail,
  RequirementChangeType,
  ImpactCategory,
} from "../../types/requirementImpact";
import {
  CHANGE_TYPE_LABELS,
  CHANGE_TYPE_COLORS,
  IMPACT_CATEGORY_LABELS,
  IMPACT_CATEGORY_COLORS,
} from "../../types/requirementImpact";

interface RequirementImpactTableProps {
  requirements: RequirementChangeDetail[];
  onSelect?: (requirement: RequirementChangeDetail) => void;
}

function ChangeTypeBadge({ type }: { type: RequirementChangeType }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${CHANGE_TYPE_COLORS[type]}`}
    >
      {CHANGE_TYPE_LABELS[type]}
    </span>
  );
}

function ImpactBadge({ category }: { category: ImpactCategory }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${IMPACT_CATEGORY_COLORS[category]}`}
    >
      {IMPACT_CATEGORY_LABELS[category]}
    </span>
  );
}

function RequirementTypeIcon({ type }: { type: string }) {
  switch (type) {
    case "skill":
      return (
        <svg className="h-5 w-5 text-ink-subtle" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z" />
        </svg>
      );
    case "experience":
      return (
        <svg className="h-5 w-5 text-ink-subtle" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      );
    case "education":
      return (
        <svg className="h-5 w-5 text-ink-subtle" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
        </svg>
      );
    default:
      return null;
  }
}

export function RequirementImpactTable({ requirements, onSelect }: RequirementImpactTableProps) {
  if (requirements.length === 0) {
    return (
      <div className="empty-state">
        <p className="text-sm text-ink-muted">No requirement changes detected.</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden p-0">
      <div className="border-b border-slate-200/70 bg-surface-muted/60 px-5 py-3.5">
        <h3 className="text-sm font-semibold text-ink">Requirement Changes</h3>
        <p className="mt-0.5 text-xs text-ink-muted">
          {requirements.length} requirement(s) changed between baseline and simulation.
        </p>
      </div>
      <div className="table-wrap rounded-none border-0 shadow-none">
        <table className="data-table">
          <thead>
            <tr>
              <th>
                Requirement
              </th>
              <th>
                Type
              </th>
              <th>
                Change
              </th>
              <th>
                Before
              </th>
              <th>
                After
              </th>
              <th className="text-right">
                Affected
              </th>
              <th className="text-right">
                Newly Disqualified
              </th>
              <th className="text-right">
                Avg Score Impact
              </th>
              <th>
                Impact
              </th>
            </tr>
          </thead>
          <tbody>
            {requirements.map((req, idx) => (
              <tr
                key={`${req.requirement_type}-${req.requirement_name}-${idx}`}
                className={onSelect ? "cursor-pointer" : ""}
                onClick={() => onSelect?.(req)}
              >
                <td className="whitespace-nowrap">
                  <div className="flex items-center gap-3">
                    <RequirementTypeIcon type={req.requirement_type} />
                    <div>
                      <div className="text-sm font-medium text-ink">{req.requirement_name}</div>
                      <div className="text-xs text-ink-muted capitalize">{req.requirement_type}</div>
                    </div>
                  </div>
                </td>
                <td className="whitespace-nowrap">
                  <span className="text-sm text-ink-muted capitalize">{req.requirement_type}</span>
                </td>
                <td className="whitespace-nowrap">
                  <ChangeTypeBadge type={req.change_type} />
                </td>
                <td className="whitespace-nowrap">
                  {req.baseline_value}
                </td>
                <td className="whitespace-nowrap font-medium text-ink">
                  {req.simulation_value}
                </td>
                <td className="whitespace-nowrap text-right">
                  <span className="text-sm font-semibold text-ink">
                    {req.affected_candidates}
                  </span>
                </td>
                <td className="whitespace-nowrap text-right">
                  <span
                    className={`text-sm font-semibold ${
                      req.newly_disqualified > 0 ? "text-rose-600" : "text-ink-muted"
                    }`}
                  >
                    {req.newly_disqualified}
                  </span>
                </td>
                <td className="whitespace-nowrap text-right">
                  <span
                    className={`text-sm font-medium ${
                      req.avg_score_impact > 0
                        ? "text-emerald-600"
                        : req.avg_score_impact < 0
                          ? "text-rose-600"
                          : "text-ink-muted"
                    }`}
                  >
                    {req.avg_score_impact > 0 ? "+" : ""}
                    {req.avg_score_impact.toFixed(1)}
                  </span>
                </td>
                <td className="whitespace-nowrap">
                  <ImpactBadge category={req.impact_category} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
