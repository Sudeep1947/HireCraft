import { FlaskConical } from "lucide-react";

interface EmptySimulationStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptySimulationState({
  title,
  description,
  actionLabel,
  onAction,
}: EmptySimulationStateProps) {
  return (
    <div className="empty-state">
      <FlaskConical className="mb-3 h-10 w-10 text-ink-subtle" aria-hidden="true" />
      <p className="text-base font-semibold text-ink">{title}</p>
      <p className="mt-1 text-sm text-ink-muted">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="btn-primary btn-sm mt-4"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
