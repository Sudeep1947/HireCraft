import type { ReactNode } from "react";

/* ─── Type-safe helpers for the JSON-serialized report_data ─────────── */

type JsonObject = { [key: string]: unknown };

function recordOf(value: unknown): JsonObject | null {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as JsonObject;
  }
  return null;
}

function arrayOf(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function numOf(value: unknown): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}

function strOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/* ─── Display helpers ────────────────────────────────────────────────── */

const ACRONYMS = new Set(["spd", "dir", "id", "pp", "api", "url"]);

function humanizeKey(key: string): string {
  return key
    .split("_")
    .map((word) => (ACRONYMS.has(word) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(" ");
}

function fmtSigned(value: unknown): string {
  const n = numOf(value);
  if (n === null) return "—";
  return n > 0 ? `+${n}` : String(n);
}

function statTone(value: unknown): string {
  const n = numOf(value);
  if (n === null || n === 0) return "text-ink-muted";
  return n > 0 ? "text-emerald-600" : "text-rose-600";
}

function Cell({ value }: { value: unknown }) {
  if (typeof value === "boolean") {
    return (
      <span
        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
          value ? "bg-emerald-50 text-emerald-800 ring-emerald-200/70" : "bg-gray-100 text-gray-800 ring-gray-200/80"
        }`}
      >
        {value ? "Yes" : "No"}
      </span>
    );
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-ink-subtle">—</span>;
    return (
      <span className="flex flex-wrap gap-1">
        {value.map((item, index) => (
          <span key={index} className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-ink-muted ring-1 ring-inset ring-gray-200/70">
            {cellText(item)}
          </span>
        ))}
      </span>
    );
  }
  if (value !== null && typeof value === "object") {
    return <span className="font-mono text-xs text-ink-muted">{JSON.stringify(value)}</span>;
  }
  const n = numOf(value);
  const text = n !== null ? String(n) : value === null || value === undefined ? "—" : String(value);
  return <span>{text}</span>;
}

function cellText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value);
}

function Card({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: string; tone?: string }) {
  return (
    <div className="card card-hover p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-subtle">{label}</p>
      <div className={`mt-1 font-display text-2xl font-bold ${tone ?? "text-ink"}`}>{value}</div>
      {sub && <p className="mt-0.5 text-xs text-ink-subtle">{sub}</p>}
    </div>
  );
}

function StatGrid({ items }: { items: { label: string; value: unknown; sub?: string }[] }) {
  const filled = items.filter((item) => numOf(item.value) !== null);
  if (filled.length === 0) return null;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {filled.map((item) => (
        <Card key={item.label} label={item.label} value={cellText(item.value)} sub={item.sub} tone={statTone(item.value)} />
      ))}
    </div>
  );
}

function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-4">
      <h2 className="section-title">{children}</h2>
      {hint && <p className="mt-0.5 text-sm text-ink-muted">{hint}</p>}
    </div>
  );
}

function EmptyMessage() {
  return (
    <p className="rounded-xl bg-gray-50 px-3 py-2 text-sm text-ink-muted">No data recorded for this section.</p>
  );
}

function GenericTable({ rows }: { rows: JsonObject[] }) {
  if (rows.length === 0) return null;
  const keys: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!keys.includes(key)) keys.push(key);
    }
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200/70">
      <table className="min-w-full divide-y divide-slate-200/70">
        <thead className="bg-gray-50/80">
          <tr>
            {keys.map((key) => (
              <th
                key={key}
                className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ink-subtle"
              >
                {humanizeKey(key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200/70">
          {rows.map((row, index) => (
            <tr key={index} className="transition-colors hover:bg-gray-50">
              {keys.map((key) => (
                <td key={key} className="whitespace-nowrap px-3 py-2 text-sm text-ink-muted">
                  <Cell value={row[key]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StringList({ title, items }: { title: string; items: unknown[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <ul className="space-y-1">
        {items.map((item, index) => (
          <li key={index} className="flex items-start gap-2 text-sm text-ink-muted">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-500" />
            <span>{cellText(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ShortlistChip({ shortlisted }: { shortlisted: unknown }) {
  const on = shortlisted === true || shortlisted === "true";
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
        on ? "bg-emerald-50 text-emerald-800 ring-emerald-200/70" : "bg-gray-100 text-gray-800 ring-gray-200/80"
      }`}
    >
      {on ? "Shortlisted" : "Not shortlisted"}
    </span>
  );
}

interface MoverRow {
  candidate_name?: string;
  baseline_score?: number;
  simulation_score?: number;
  score_change?: number;
  baseline_rank?: number;
  simulation_rank?: number;
  rank_change?: number;
  shortlisted?: boolean;
}

function toMoverRows(value: unknown): MoverRow[] {
  return arrayOf(value).map((item) => (recordOf(item) ?? {}) as MoverRow);
}

function MoversTable({ rows, title }: { rows: MoverRow[]; title: string }) {
  if (rows.length === 0) return null;
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <div className="overflow-x-auto rounded-xl border border-slate-200/70">
        <table className="min-w-full divide-y divide-slate-200/70">
          <thead className="bg-gray-50/80">
            <tr>
              {["Candidate", "Base score", "Sim score", "Δ score", "Rank", "Shortlist"].map((header) => (
                <th
                  key={header}
                  className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ink-subtle"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200/70">
            {rows.map((row, index) => (
              <tr key={index} className="transition-colors hover:bg-gray-50">
                <td className="whitespace-nowrap px-3 py-2 text-sm font-medium text-ink">
                  {row.candidate_name ?? "—"}
                  <span className="ml-1 text-xs text-ink-subtle">
                    #{row.simulation_rank ?? "—"} (base #{row.baseline_rank ?? "—"})
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-sm text-ink-muted">{row.baseline_score ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm font-semibold text-ink">
                  {row.simulation_score ?? "—"}
                </td>
                <td className={`whitespace-nowrap px-3 py-2 text-sm font-medium ${statTone(row.score_change ?? 0)}`}>
                  {fmtSigned(row.score_change)}
                </td>
                <td className={`whitespace-nowrap px-3 py-2 text-sm font-medium ${statTone(row.rank_change ?? 0)}`}>
                  {fmtSigned(row.rank_change)}
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <ShortlistChip shortlisted={row.shortlisted} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChipList({ items }: { items: string[] }) {
  const filled = items.filter((item) => item.length > 0);
  if (filled.length === 0) return <p className="text-sm text-ink-subtle">No changes.</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {filled.map((item, index) => (
        <span key={index} className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-sm text-ink-muted ring-1 ring-inset ring-gray-200/70">
          {item}
        </span>
      ))}
    </div>
  );
}

function DiffRow({
  label,
  baseline,
  simulation,
  change,
}: {
  label: string;
  baseline: unknown;
  simulation: unknown;
  change: unknown;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200/70 bg-gray-50 px-3 py-2 text-sm">
      <span className="font-medium text-ink-muted">{label}</span>
      <span className="text-ink-muted">
        <span className="text-ink-muted">{cellText(baseline)}</span>
        <span className="mx-2 text-ink-subtle">→</span>
        <span className="font-semibold text-ink">{cellText(simulation)}</span>
        <span className={`ml-2 text-xs ${statTone(change)}`}>({cellText(change)})</span>
      </span>
    </div>
  );
}

/* ─── Section renderers ──────────────────────────────────────────────── */

function CandidateImpactSection({ data }: { data: JsonObject }) {
  return (
    <>
      <StatGrid
        items={[
          { label: "Total candidates", value: data.total_candidates },
          { label: "With score changes", value: data.candidates_with_score_changes },
          { label: "With rank changes", value: data.candidates_with_rank_changes },
          { label: "Entering shortlist", value: data.candidates_entering_shortlist },
          { label: "Leaving shortlist", value: data.candidates_leaving_shortlist },
          { label: "Retained shortlist", value: data.retained_shortlist_candidates },
          { label: "Qualification changes", value: data.qualification_changes },
          { label: "Largest score movement", value: data.largest_score_movement },
          { label: "Largest rank movement", value: data.largest_rank_movement },
          { label: "Avg score change", value: data.average_score_change },
          { label: "Avg rank change", value: data.average_rank_change },
        ]}
      />
      <MoversTable title="Top score increases" rows={toMoverRows(data.top_movers_increases)} />
      <MoversTable title="Top score decreases" rows={toMoverRows(data.top_movers_decreases)} />
      <MoversTable title="Top rank improvements" rows={toMoverRows(data.top_rank_improvements)} />
      <MoversTable title="Top rank declines" rows={toMoverRows(data.top_rank_declines)} />
    </>
  );
}

function RankingImpactSection({ data }: { data: JsonObject }) {
  const overview = recordOf(data.overview);
  const score = recordOf(data.score_movement);
  const distributions = recordOf(data.distributions);
  const rankMovement = recordOf(data.rank_movement);
  const shortlistImpact = recordOf(data.shortlist_impact);

  return (
    <>
      {overview && (
        <StatGrid
          items={[
            { label: "Total candidates", value: overview.total_candidates },
            { label: "Avg score change", value: overview.average_score_change },
            { label: "Median score change", value: overview.median_score_change },
            { label: "Avg rank change", value: overview.average_rank_change },
            { label: "Moved up", value: overview.candidates_moved_up },
            { label: "Moved down", value: overview.candidates_moved_down },
            { label: "Unchanged", value: overview.candidates_unchanged },
          ]}
        />
      )}
      {score && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Score movement</h3>
          <StatGrid
            items={[
              { label: "Average change", value: score.average_change },
              { label: "Minimum change", value: score.minimum_change },
              { label: "Maximum change", value: score.maximum_change },
              { label: "Positive count", value: score.positive_count },
              { label: "Negative count", value: score.negative_count },
            ]}
          />
        </div>
      )}
      {distributions && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Score distribution</h3>
          <StatGrid
            items={[
              { label: "Median", value: distributions.score_median },
              { label: "Mean", value: distributions.score_mean },
              { label: "Std dev", value: distributions.score_stdev },
            ]}
          />
        </div>
      )}
      {rankMovement && Object.keys(rankMovement).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Rank movement</h3>
          <StatGrid
            items={Object.entries(rankMovement).map(([key, value]) => ({ label: humanizeKey(key), value }))}
          />
        </div>
      )}
      {shortlistImpact && Object.keys(shortlistImpact).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Shortlist impact</h3>
          <StatGrid
            items={Object.entries(shortlistImpact).map(([key, value]) => ({ label: humanizeKey(key), value }))}
          />
        </div>
      )}
      {arrayOf(data.qualification_matrix).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Qualification matrix</h3>
          <GenericTable rows={arrayOf(data.qualification_matrix).map((item) => recordOf(item) ?? {})} />
        </div>
      )}
      <StringList title="Insights" items={arrayOf(data.insights)} />
    </>
  );
}

function RequirementImpactSection({ data }: { data: JsonObject }) {
  const perRequirement = arrayOf(data.per_requirement).map((item) => recordOf(item) ?? {});
  return (
    <>
      <StatGrid
        items={[
          { label: "Total requirements changed", value: data.total_changed },
          { label: "Candidates affected", value: data.candidates_affected },
        ]}
      />
      {(["added", "removed", "promoted", "demoted"] as const).map((key) => (
        <div key={key} className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">{humanizeKey(key)}</h3>
          <ChipList items={arrayOf(data[key]).map(cellText)} />
        </div>
      ))}
      {perRequirement.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Per-requirement changes</h3>
          <GenericTable rows={perRequirement} />
        </div>
      )}
    </>
  );
}

function ThresholdImpactSection({ data }: { data: JsonObject }) {
  return (
    <>
      <StatGrid
        items={[
          { label: "Baseline threshold", value: data.baseline_threshold, sub: "Minimum pass score" },
          { label: "Simulation threshold", value: data.simulation_threshold, sub: "Minimum pass score" },
          { label: "Qualified (baseline)", value: data.qualified_baseline },
          { label: "Qualified (simulation)", value: data.qualified_simulation },
          { label: "Newly qualified", value: data.newly_qualified },
          { label: "Newly disqualified", value: data.newly_disqualified },
        ]}
      />
      {data.qualification_change && (
        <p className="mt-3 text-sm text-ink-muted">
          Qualification outcome:{" "}
          <span className="font-semibold text-ink">{cellText(data.qualification_change)}</span>
        </p>
      )}
      {arrayOf(data.boundary_candidates).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Boundary candidates</h3>
          <GenericTable rows={arrayOf(data.boundary_candidates).map((item) => recordOf(item) ?? {})} />
        </div>
      )}
    </>
  );
}

function ShortlistImpactSection({ data }: { data: JsonObject }) {
  return (
    <>
      <StatGrid
        items={[
          { label: "Baseline shortlist size", value: data.baseline_shortlist_size },
          { label: "Simulation shortlist size", value: data.simulation_shortlist_size },
          { label: "Retained", value: data.retained },
          { label: "Entering", value: data.entering },
          { label: "Leaving", value: data.leaving },
          { label: "Overlap", value: data.overlap_percentage, sub: "percent" },
        ]}
      />
      {arrayOf(data.boundary_candidates).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Boundary candidates</h3>
          <GenericTable rows={arrayOf(data.boundary_candidates).map((item) => recordOf(item) ?? {})} />
        </div>
      )}
    </>
  );
}

function ConfigurationDiffSection({ data }: { data: JsonObject }) {
  const weights = arrayOf(data.weights).map((item) => recordOf(item) ?? {});
  const threshold = recordOf(data.threshold);
  const shortlist = recordOf(data.shortlist_size);
  const requirementChanges = arrayOf(data.requirement_changes).map((item) => recordOf(item) ?? {});

  if (weights.length === 0 && !threshold && !shortlist && requirementChanges.length === 0) return null;

  return (
    <>
      {weights.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200/70">
          <table className="min-w-full divide-y divide-slate-200/70">
            <thead className="bg-gray-50/80">
              <tr>
                {["Weight", "Baseline", "Simulation", "Change"].map((header) => (
                  <th
                    key={header}
                    className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ink-subtle"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/70">
              {weights.map((row, index) => (
                <tr key={index} className="transition-colors hover:bg-gray-50">
                  <td className="px-3 py-2 text-sm font-medium text-ink">
                    {cellText(row.weight_label ?? row.weight_name)}
                  </td>
                  <td className="px-3 py-2 text-sm text-ink-muted">{cellText(row.baseline)}</td>
                  <td className="px-3 py-2 text-sm font-semibold text-ink">{cellText(row.simulation)}</td>
                  <td className={`px-3 py-2 text-sm font-medium ${statTone(row.change)}`}>
                    {cellText(row.change_label ?? row.change)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(threshold || shortlist) && (
        <div className="mt-4 space-y-2">
          {threshold && (
            <DiffRow
              label={cellText(threshold.label)}
              baseline={threshold.baseline}
              simulation={threshold.simulation}
              change={threshold.change_label}
            />
          )}
          {shortlist && (
            <DiffRow
              label={cellText(shortlist.label)}
              baseline={shortlist.baseline}
              simulation={shortlist.simulation}
              change={shortlist.change_label}
            />
          )}
        </div>
      )}

      {requirementChanges.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Requirement changes</h3>
          <div className="space-y-1">
            {requirementChanges.map((row, index) => (
              <p key={index} className="text-sm text-ink-muted">
                <span className="font-semibold text-ink">{cellText(row.skill)}</span>
                <span className="mx-2 text-ink-subtle">
                  {cellText(row.from_status)} → {cellText(row.to_status)}
                </span>
              </p>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function FairnessImpactSection({ data }: { data: JsonObject }) {
  if (data.available === false && strOf(data.unavailable_reason)) {
    return (
      <p className="rounded-xl border border-amber-200/70 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        {cellText(data.unavailable_reason)}
      </p>
    );
  }
  return (
    <>
      {arrayOf(data.groups).length > 0 && (
        <div className="mt-2">
          <h3 className="mb-2 text-sm font-semibold text-ink">Groups</h3>
          <GenericTable rows={arrayOf(data.groups).map((item) => recordOf(item) ?? {})} />
        </div>
      )}
      {arrayOf(data.cross_group_metrics).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Cross-group metrics</h3>
          <GenericTable rows={arrayOf(data.cross_group_metrics).map((item) => recordOf(item) ?? {})} />
        </div>
      )}
      {arrayOf(data.selection_rate_changes).length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Selection rate changes</h3>
          <GenericTable rows={arrayOf(data.selection_rate_changes).map((item) => recordOf(item) ?? {})} />
        </div>
      )}
      <StringList title="Limitations" items={arrayOf(data.limitations)} />
      <StringList title="Small-sample warnings" items={arrayOf(data.small_sample_warnings)} />
    </>
  );
}

function ExplainabilityImpactSection({ data }: { data: JsonObject }) {
  if (data.available === false && strOf(data.unavailable_reason)) {
    return (
      <p className="rounded-xl border border-amber-200/70 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        {cellText(data.unavailable_reason)}
      </p>
    );
  }
  const sections: { key: string; label: string }[] = [
    { key: "feature_contribution_changes", label: "Feature contribution changes" },
    { key: "weight_changes", label: "Weight changes" },
    { key: "score_attribution", label: "Score attribution" },
    { key: "candidate_explanations", label: "Candidate explanations" },
  ];
  return (
    <>
      {sections.map(({ key, label }) => {
        const rows = arrayOf(data[key]).map((item) => recordOf(item) ?? {});
        if (rows.length === 0) return null;
        return (
          <div key={key} className="mt-2">
            <h3 className="mb-2 text-sm font-semibold text-ink">{label}</h3>
            <GenericTable rows={rows} />
          </div>
        );
      })}
    </>
  );
}

function SkillImpactSection({ data }: { data: JsonObject }) {
  if (data.available === false && strOf(data.unavailable_reason)) {
    return (
      <p className="rounded-xl border border-amber-200/70 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        {cellText(data.unavailable_reason)}
      </p>
    );
  }
  const sections: { key: string; label: string }[] = [
    { key: "changed_skills", label: "Changed skills" },
    { key: "skill_coverage_changes", label: "Skill coverage changes" },
    { key: "skill_gaps", label: "Skill gaps" },
  ];
  return (
    <>
      {numOf(data.candidates_affected) !== null && (
        <StatGrid items={[{ label: "Candidates affected", value: data.candidates_affected }]} />
      )}
      {sections.map(({ key, label }) => {
        const rows = arrayOf(data[key]).map((item) => recordOf(item) ?? {});
        if (rows.length === 0) return null;
        return (
          <div key={key} className="mt-4">
            <h3 className="mb-2 text-sm font-semibold text-ink">{label}</h3>
            <GenericTable rows={rows} />
          </div>
        );
      })}
    </>
  );
}

function ExecutiveSummarySection({ data }: { data: JsonObject }) {
  const hasContent =
    strOf(data.narrative).length > 0 ||
    numOf(data.total_candidates_evaluated) !== null ||
    arrayOf(data.key_configuration_changes).length > 0;

  if (!hasContent) return null;

  return (
    <>
      {strOf(data.narrative) && <p className="text-sm leading-relaxed text-ink-muted">{cellText(data.narrative)}</p>}
      <StringList title="Key configuration changes" items={arrayOf(data.key_configuration_changes)} />
      <StringList title="Major observed differences" items={arrayOf(data.major_observed_differences)} />
      {strOf(data.candidate_impact_summary) && (
        <p className="mt-3 text-sm text-ink-muted">
          <span className="font-semibold text-ink">Candidate impact:</span> {cellText(data.candidate_impact_summary)}
        </p>
      )}
      {strOf(data.fairness_summary) && (
        <p className="mt-2 text-sm text-ink-muted">
          <span className="font-semibold text-ink">Fairness:</span> {cellText(data.fairness_summary)}
        </p>
      )}
      <StringList title="Limitations" items={arrayOf(data.limitations)} />
    </>
  );
}

function LimitationsSection({ data }: { data: JsonObject }) {
  return (
    <>
      {strOf(data.simulation_isolation_notice) && (
        <div className="rounded-xl border border-primary-200/70 bg-primary-50/60 px-4 py-3 text-sm text-primary-800">
          {cellText(data.simulation_isolation_notice)}
        </div>
      )}
      <StringList title="Limitations" items={arrayOf(data.items)} />
      <StringList title="Data integrity" items={arrayOf(data.data_integrity_notes)} />
    </>
  );
}

function MetadataSection({ data }: { data: JsonObject }) {
  const rows = [
    { label: "Job", value: data.job_title },
    { label: "Scenario", value: data.scenario_name },
    { label: "Sandbox", value: data.sandbox_name },
    { label: "Generated by", value: data.generated_by },
    { label: "Generated at", value: data.generated_at },
    { label: "Report type", value: data.report_type },
    { label: "Report version", value: data.report_version },
    { label: "Engine version", value: data.engine_version },
  ].filter((row) => strOf(row.value).length > 0);

  if (rows.length === 0) return null;
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((row) => (
        <div key={row.label}>
          <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">{row.label}</dt>
          <dd className="mt-0.5 text-sm text-ink">{cellText(row.value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function GenericSection({ data }: { data: JsonObject }) {
  const entries = Object.entries(data).filter(([, value]) => {
    if (Array.isArray(value) && value.length === 0) return false;
    if (value === null || value === undefined) return false;
    if (typeof value === "object" && Object.keys(value as JsonObject).length === 0) return false;
    return true;
  });
  if (entries.length === 0) return <EmptyMessage />;
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {entries.map(([key, value]) => {
        const rows = arrayOf(value).map((item) => recordOf(item) ?? {});
        return (
          <div key={key} className="rounded-xl border border-slate-200/70 bg-gray-50 px-3 py-2">
            <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">{humanizeKey(key)}</dt>
            <dd className="mt-1 text-sm text-ink-muted">
              {rows.length > 0 ? <GenericTable rows={rows} /> : <Cell value={value} />}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/* ─── Public dispatcher ──────────────────────────────────────────────── */

const SECTION_LABELS: Record<string, string> = {
  header: "Report",
  executive_summary: "Executive Summary",
  configuration_diff: "Configuration Diff",
  candidate_impact: "Candidate Impact",
  candidate_impact_table: "Candidate Details",
  ranking_impact: "Ranking Impact",
  requirement_impact: "Requirement Impact",
  threshold_impact: "Threshold Impact",
  shortlist_impact: "Shortlist Impact",
  fairness_impact: "Fairness",
  explainability_impact: "Explainability",
  skill_impact: "Skill Impact",
  comparison_matrix: "Scenario Comparison",
  limitations: "Limitations & Data Integrity",
  audit_info: "Audit",
};

const SECTION_HINTS: Record<string, string> = {
  candidate_impact: "Overall effect of the hypothetical configuration on the candidate pool.",
  ranking_impact: "How scores and ranks moved between the baseline and the simulation.",
  requirement_impact: "Skills or requirements that changed between baseline and simulation.",
  threshold_impact: "Effect of the pass threshold on qualification.",
  shortlist_impact: "How shortlist membership changed between baseline and simulation.",
  limitations: "Caveats, data-integrity notes, and the what-if isolation guarantee.",
};

const SECTION_ORDER = [
  "header",
  "executive_summary",
  "configuration_diff",
  "candidate_impact",
  "candidate_impact_table",
  "ranking_impact",
  "requirement_impact",
  "threshold_impact",
  "shortlist_impact",
  "fairness_impact",
  "explainability_impact",
  "skill_impact",
  "comparison_matrix",
  "limitations",
  "audit_info",
] as const;

function renderSection(section: string, data: JsonObject): ReactNode {
  switch (section) {
    case "header":
    case "audit_info":
      return <MetadataSection data={data} />;
    case "executive_summary":
      return <ExecutiveSummarySection data={data} />;
    case "configuration_diff":
      return <ConfigurationDiffSection data={data} />;
    case "candidate_impact":
      return <CandidateImpactSection data={data} />;
    case "candidate_impact_table":
      return (
        <MoversTable title="All candidates by rank movement" rows={toMoverRows(data.items)} />
      );
    case "ranking_impact":
      return <RankingImpactSection data={data} />;
    case "requirement_impact":
      return <RequirementImpactSection data={data} />;
    case "threshold_impact":
      return <ThresholdImpactSection data={data} />;
    case "shortlist_impact":
      return <ShortlistImpactSection data={data} />;
    case "fairness_impact":
      return <FairnessImpactSection data={data} />;
    case "explainability_impact":
      return <ExplainabilityImpactSection data={data} />;
    case "skill_impact":
      return <SkillImpactSection data={data} />;
    case "limitations":
      return <LimitationsSection data={data} />;
    default:
      return <GenericSection data={data} />;
  }
}

export function SimulationReportSections({ reportData }: { reportData: Record<string, unknown> }) {
  return (
    <div className="space-y-6">
      {SECTION_ORDER.map((section) => {
        const raw = reportData[section];
        const data = recordOf(raw);
        if (!data) return null;
        const label = SECTION_LABELS[section] ?? humanizeKey(section);
        const hint = SECTION_HINTS[section];
        return (
          <section key={section} className="card p-6">
            <SectionTitle hint={hint}>{label}</SectionTitle>
            {renderSection(section, data)}
          </section>
        );
      })}
    </div>
  );
}
