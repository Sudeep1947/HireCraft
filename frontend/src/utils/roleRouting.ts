import type { RoleName } from "../types/auth";

export const ROLE_EXPANSIONS: Record<string, string[]> = {
  admin: ["admin", "super_admin"],
  super_admin: ["super_admin", "admin"],
  hr: ["hr", "hr_manager", "organization_admin", "admin", "super_admin"],
  hr_manager: ["hr_manager", "hr", "organization_admin", "admin", "super_admin"],
  recruiter: ["recruiter", "hr", "hr_manager", "organization_admin", "admin", "super_admin"],
  organization_admin: ["organization_admin", "admin", "super_admin"],
  candidate: ["candidate"],
};

export function isRoleAllowed(requiredRoles: RoleName[], userRoles: RoleName[]): boolean {
  return requiredRoles.some((req) => {
    const validRoles = ROLE_EXPANSIONS[req] || [req];
    return userRoles.some((ur) => validRoles.includes(ur));
  });
}

export function getDashboardPath(roles: RoleName[]): string {
  if (roles.includes("super_admin") || roles.includes("admin")) return "/admin/dashboard";
  if (roles.includes("hr_manager") || roles.includes("hr")) return "/hr/dashboard";
  if (roles.includes("organization_admin")) return "/org/team";
  if (roles.includes("recruiter")) return "/recruiter/dashboard";
  return "/skill2job";
}

export function getNotificationPath(roles: RoleName[]): string {
  if (roles.includes("super_admin") || roles.includes("admin")) return "/admin/dashboard";
  if (roles.includes("hr_manager") || roles.includes("hr")) return "/hr/dashboard";
  if (roles.includes("organization_admin")) return "/org/team";
  if (roles.includes("recruiter")) return "/recruiter/notifications";
  return "/candidate/notifications";
}

export function getRoleBadgeColor(roles: RoleName[]): string {
  if (roles.includes("super_admin")) return "bg-rose-50 text-rose-700 border border-rose-200/60";
  if (roles.includes("admin")) return "bg-rose-50 text-rose-700 border border-rose-200/60";
  if (roles.includes("organization_admin")) return "bg-amber-50 text-amber-700 border border-amber-200/60";
  if (roles.includes("hr_manager") || roles.includes("hr")) return "bg-purple-50 text-purple-700 border border-purple-200/60";
  if (roles.includes("recruiter")) return "bg-blue-50 text-blue-700 border border-blue-200/60";
  return "bg-emerald-50 text-emerald-700 border border-emerald-200/60";
}
