interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="py-12 text-center">
      {icon && (
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 ring-1 ring-primary-100">
          {icon}
        </div>
      )}
      <h3 className="section-title">{title}</h3>
      <p className="mt-1 text-sm text-ink-muted">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 rounded-xl bg-brand-gradient px-4 py-2 text-sm font-medium text-white shadow-soft transition-all hover:brightness-110 hover:shadow-glow"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
