import { Link } from "react-router-dom";

interface DashboardCardProps {
  title: string;
  children: React.ReactNode;
  action?: { label: string; href: string };
  className?: string;
}

export function DashboardCard({ title, children, action, className = "" }: DashboardCardProps) {
  return (
    <div className={`card p-6 ${className}`}>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="section-title">{title}</h2>
        {action && (
          <Link
            to={action.href}
            className="text-sm font-medium text-primary-600 transition-colors hover:text-primary-700"
          >
            {action.label}
          </Link>
        )}
      </div>
      {children}
    </div>
  );
}
