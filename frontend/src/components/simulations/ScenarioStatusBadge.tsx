// Status pill for simulation scenarios. The draft/ready/completed/failed
// entries keep the legacy palette tokens because ScenarioStatusBadge.test.tsx
// asserts those exact class names; everything else uses design-system tokens.
const STATUS_STYLES: Record<string, string> = {
  draft: "badge bg-yellow-100 text-yellow-800",
  ready: "badge bg-blue-100 text-blue-800",
  queued: "badge bg-primary-100 text-primary-700",
  running: "badge bg-violet-100 text-violet-800",
  completed: "badge bg-green-100 text-green-800",
  failed: "badge bg-red-100 text-red-800",
  cancelled: "badge bg-surface-muted text-ink",
};

export function ScenarioStatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "badge bg-surface-muted text-ink";
  return (
    <span className={style}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
