import { useEffect, useState } from "react";
import { Users, Search } from "lucide-react";

import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useToast } from "../../contexts/ToastContext";
import { dashboardApi } from "../../api/dashboard";
import type { AdminUserItem } from "../../api/dashboard";
import { formatDate } from "../../utils/dateTime";

export function UserManagement() {
  const { addToast } = useToast();
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    dashboardApi
      .getAdminUsers()
      .then(setUsers)
      .catch(() => addToast("Failed to load users", "error"))
      .finally(() => setLoading(false));
  }, [addToast]);

  const filtered = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()),
  );

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="page-subtitle">{users.length} total users</p>
        </div>
        <span className="badge-primary self-start">
          <Users className="h-3.5 w-3.5" aria-hidden="true" /> Directory
        </span>
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-gray-100 p-4">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
              aria-hidden="true"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search users..."
              className="field pl-10"
            />
          </div>
        </div>
        <div className="table-wrap border-0 shadow-none">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Roles</th>
                <th>Status</th>
                <th>Joined</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-violet-500 text-xs font-bold text-white">
                        {user.full_name.charAt(0).toUpperCase()}
                      </span>
                      <div className="text-sm font-medium text-gray-900">{user.full_name}</div>
                    </div>
                  </td>
                  <td className="text-gray-500">{user.email}</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {user.roles.map((role) => (
                        <span
                          key={role}
                          className={
                            role === "admin"
                              ? "badge-danger"
                              : role === "hr" || role === "hr_manager"
                                ? "badge-primary"
                                : role === "recruiter"
                                  ? "badge-info"
                                  : "badge-success"
                          }
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <span className={user.is_active ? "badge-success" : "badge-danger"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="empty-state border-0">
              <Search className="mb-3 h-10 w-10 text-gray-300" aria-hidden="true" />
              <h3 className="text-base font-semibold text-gray-900">No users found</h3>
              <p className="mt-1 text-sm text-gray-500">
                Try a different name or email search.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
