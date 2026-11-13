import type {
  FieldChangeKind,
  SimulationChangesResponse,
} from "../../types/simulations";

const KIND_STYLES: Record<FieldChangeKind, { badge: string; arrow: string }> = {
  unchanged: { badge: "badge-neutral", arrow: "=" },
  increased: { badge: "badge-success", arrow: "\u2191" },
  decreased: { badge: "badge-danger", arrow: "\u2193" },
  added: { badge: "badge-success", arrow: "+" },
  removed: { badge: "badge-danger", arrow: "\u2212" },
  changed: { badge: "badge-warning", arrow: "~" },
};

function ChangeBadge({ change }: { change: FieldChangeKind }) {
  const style = KIND_STYLES[change] ?? KIND_STYLES.unchanged;
  if (change === "unchanged") return null;
  return (
    <span className={style.badge}>
      <span aria-hidden="true">{style.arrow}</span>
      {change}
    </span>
  );
}

function SkillChips({ skills, tone }: { skills: string[]; tone: "added" | "removed" }) {
  if (skills.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {skills.map((skill) => (
        <span
          key={skill}
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
            tone === "added" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
          }`}
        >
          <span className="font-bold">{tone === "added" ? "+" : "\u2212"}</span>
          {skill}
        </span>
      ))}
    </div>
  );
}

interface ChangesSectionProps {
  changes: SimulationChangesResponse;
  title?: string;
}

export function ChangesSection({ changes, title = "Review changes" }: ChangesSectionProps) {
  const changedFields = changes.fields.filter((f) => f.change !== "unchanged");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            Baseline vs proposed simulation configuration (config v{changes.config_version})
          </p>
        </div>
        {changes.total_changes > 0 ? (
          <span className="badge-primary">
            {changes.total_changes} change{changes.total_changes === 1 ? "" : "s"}
          </span>
        ) : (
          <span className="badge-success">No changes</span>
        )}
      </div>

      {changes.total_changes === 0 ? (
        <p className="success-banner">
          The proposed configuration matches the baseline. Adjust the settings to create a
          &quot;what-if&quot; scenario.
        </p>
      ) : (
        <div className="space-y-3">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Setting</th>
                  <th>Baseline</th>
                  <th>Scenario</th>
                  <th className="text-right">Change</th>
                </tr>
              </thead>
              <tbody>
                {changedFields.map((field) => (
                  <tr key={field.key}>
                    <td className="font-medium text-ink">{field.label}</td>
                    <td>
                      {formatValue(field.key, field.baseline)}
                    </td>
                    <td className="font-medium text-ink">{formatValue(field.key, field.scenario)}</td>
                    <td className="text-right">
                      <ChangeBadge change={field.change} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {(changedFields.some((f) => f.key.startsWith("requirements.")) ||
            changes.skills.moved.length > 0 ||
            changes.skills.mandatory_added.length > 0 ||
            changes.skills.preferred_added.length > 0 ||
            changes.skills.mandatory_removed.length > 0 ||
            changes.skills.preferred_removed.length > 0) && (
            <div className="card p-4">
              <h4 className="section-label">
                Skill requirements
              </h4>
              <div className="mt-3 space-y-3">
                <div>
                  <p className="mb-1 text-xs font-medium text-ink-muted">Added</p>
                  {changes.skills.mandatory_added.length ||
                  changes.skills.preferred_added.length ? (
                    <SkillChips
                      skills={[...changes.skills.mandatory_added, ...changes.skills.preferred_added]}
                      tone="added"
                    />
                  ) : (
                    <p className="text-xs text-ink-subtle">None</p>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-ink-muted">Removed</p>
                  {changes.skills.mandatory_removed.length ||
                  changes.skills.preferred_removed.length ? (
                    <SkillChips
                      skills={[
                        ...changes.skills.mandatory_removed,
                        ...changes.skills.preferred_removed,
                      ]}
                      tone="removed"
                    />
                  ) : (
                    <p className="text-xs text-ink-subtle">None</p>
                  )}
                </div>
                {changes.skills.moved.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-ink-muted">Moved</p>
                    <div className="flex flex-wrap gap-1.5">
                      {changes.skills.moved.map((move) => (
                        <span
                          key={`${move.skill}-${move.from_list}-${move.to_list}`}
                          className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700"
                        >
                          {move.skill}: {move.from_list} &rarr; {move.to_list}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatValue(key: string, value: string | number | null): string {
  if (value === null || value === undefined) return "—";
  if (key.startsWith("scoring_weights.")) {
    return `${(Number(value) * 100).toFixed(0)}%`;
  }
  if (key === "threshold") return `${value}%`;
  if (typeof value === "number") return String(value);
  return value;
}