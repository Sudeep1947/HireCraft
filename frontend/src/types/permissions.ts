export type Permission =
  // Candidate
  | "candidate:profile:view"
  | "candidate:profile:edit"
  | "candidate:resume:upload"
  | "candidate:resume:view"
  | "candidate:resume:delete"
  | "candidate:resume:intelligence"
  | "candidate:job:browse"
  | "candidate:job:save"
  | "candidate:job:apply"
  | "candidate:application:view"
  | "candidate:notification:view"
  | "candidate:notification:manage"
  | "candidate:settings:password"
  | "candidate:settings:email"
  | "candidate:settings:account"
  | "candidate:intelligence:view"
  | "candidate:xai:self_view"
  | "candidate:xai:self_recommend"
  | "candidate:fairness:self_view"
  | "candidate:interview:mock_start"
  | "candidate:interview:mock_answer"
  | "candidate:interview:self_view"
  | "candidate:interview:self_scorecard"
  // Recruiter
  | "recruiter:job:create"
  | "recruiter:job:edit"
  | "recruiter:job:delete"
  | "recruiter:job:publish"
  | "recruiter:job:close"
  | "recruiter:applicant:view"
  | "recruiter:applicant:manage"
  | "recruiter:resume:screen"
  | "recruiter:resume:download"
  | "recruiter:candidate:rank"
  | "recruiter:candidate:compare"
  | "recruiter:ai:search"
  | "recruiter:ai:insights"
  | "recruiter:ai:recommendations"
  | "recruiter:xai:explain"
  | "recruiter:xai:compare"
  | "recruiter:fairness:view"
  | "recruiter:fairness:analyze"
  | "recruiter:fairness:adversarial"
  | "recruiter:fairness:jd_analysis"
  | "recruiter:interview:schedule"
  | "recruiter:interview:generate"
  | "recruiter:interview:evaluate"
  | "recruiter:interview:scorecard_view"
  | "recruiter:interview:scorecard_manage"
  | "recruiter:interview:notes"
  | "recruiter:note:manage"
  | "recruiter:dashboard:view"
  | "recruiter:notification:view"
  // HR
  | "hr:dashboard:view"
  | "hr:pipeline:view"
  | "hr:pipeline:manage"
  | "hr:reports:view"
  | "hr:analytics:view"
  | "hr:recruiter:view"
  | "hr:candidate:view"
  | "hr:interview:view"
  | "hr:interview:analytics"
  | "hr:interview:scorecard_view"
  | "hr:offer:view"
  | "hr:fairness:view"
  | "hr:fairness:analyze"
  // Admin
  | "admin:dashboard:view"
  | "admin:user:view"
  | "admin:user:manage"
  | "admin:role:view"
  | "admin:role:manage"
  | "admin:audit:view"
  | "admin:system:view"
  | "admin:system:manage"
  | "admin:analytics:view"
  // Analytics (cross-role)
  | "analytics:candidate:view"
  | "analytics:recruiter:view"
  | "analytics:hr:view"
  | "analytics:admin:view"
  | "analytics:executive:view"
  | "analytics:predictions:view"
  | "analytics:insights:view"
  | "analytics:reports:manage"
  | "analytics:alerts:manage"
  | "analytics:layout:manage";

export const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  candidate: [
    "candidate:profile:view",
    "candidate:profile:edit",
    "candidate:resume:upload",
    "candidate:resume:view",
    "candidate:resume:delete",
    "candidate:resume:intelligence",
    "candidate:job:browse",
    "candidate:job:save",
    "candidate:job:apply",
    "candidate:application:view",
    "candidate:notification:view",
    "candidate:notification:manage",
    "candidate:settings:password",
    "candidate:settings:email",
    "candidate:settings:account",
    "candidate:intelligence:view",
    "candidate:xai:self_view",
    "candidate:xai:self_recommend",
    "candidate:fairness:self_view",
    "candidate:interview:mock_start",
    "candidate:interview:mock_answer",
    "candidate:interview:self_view",
    "candidate:interview:self_scorecard",
    "analytics:candidate:view",
    "analytics:insights:view",
  ],
  recruiter: [
    "recruiter:job:create",
    "recruiter:job:edit",
    "recruiter:job:delete",
    "recruiter:job:publish",
    "recruiter:job:close",
    "recruiter:applicant:view",
    "recruiter:applicant:manage",
    "recruiter:resume:screen",
    "recruiter:resume:download",
    "recruiter:candidate:rank",
    "recruiter:candidate:compare",
    "recruiter:ai:search",
    "recruiter:ai:insights",
    "recruiter:ai:recommendations",
    "recruiter:xai:explain",
    "recruiter:xai:compare",
    "recruiter:fairness:view",
    "recruiter:fairness:analyze",
    "recruiter:fairness:adversarial",
    "recruiter:fairness:jd_analysis",
    "recruiter:interview:schedule",
    "recruiter:interview:generate",
    "recruiter:interview:evaluate",
    "recruiter:interview:scorecard_view",
    "recruiter:interview:scorecard_manage",
    "recruiter:interview:notes",
    "recruiter:note:manage",
    "recruiter:dashboard:view",
    "recruiter:notification:view",
    "analytics:recruiter:view",
    "analytics:predictions:view",
    "analytics:insights:view",
    "analytics:reports:manage",
    "analytics:alerts:manage",
  ],
  hr: [
    "hr:dashboard:view",
    "hr:pipeline:view",
    "hr:pipeline:manage",
    "hr:reports:view",
    "hr:analytics:view",
    "hr:recruiter:view",
    "hr:candidate:view",
    "hr:interview:view",
    "hr:interview:analytics",
    "hr:interview:scorecard_view",
    "hr:offer:view",
    "hr:fairness:view",
    "hr:fairness:analyze",
    "analytics:hr:view",
    "analytics:executive:view",
    "analytics:predictions:view",
    "analytics:insights:view",
    "analytics:reports:manage",
    "analytics:alerts:manage",
  ],
  admin: [
    "admin:dashboard:view",
    "admin:user:view",
    "admin:user:manage",
    "admin:role:view",
    "admin:role:manage",
    "admin:audit:view",
    "admin:system:view",
    "admin:system:manage",
    "admin:analytics:view",
    "recruiter:fairness:view",
    "recruiter:fairness:analyze",
    "recruiter:fairness:adversarial",
    "recruiter:fairness:jd_analysis",
    "hr:fairness:view",
    "hr:fairness:analyze",
    "candidate:fairness:self_view",
    "analytics:candidate:view",
    "analytics:recruiter:view",
    "analytics:hr:view",
    "analytics:admin:view",
    "analytics:executive:view",
    "analytics:predictions:view",
    "analytics:insights:view",
    "analytics:reports:manage",
    "analytics:alerts:manage",
    "analytics:layout:manage",
  ],
};

ROLE_PERMISSIONS.hr_manager = ROLE_PERMISSIONS.hr;
ROLE_PERMISSIONS.super_admin = ROLE_PERMISSIONS.admin;
ROLE_PERMISSIONS.organization_admin = [
  ...ROLE_PERMISSIONS.hr,
  ...ROLE_PERMISSIONS.recruiter,
  "admin:user:view",
  "admin:audit:view",
  "admin:analytics:view",
];

export function getPermissionsForRoles(roles: string[]): Set<Permission> {
  const perms = new Set<Permission>();
  for (const role of roles) {
    const rolePerms = ROLE_PERMISSIONS[role] ?? [];
    for (const p of rolePerms) {
      perms.add(p);
    }
  }
  return perms;
}

export function hasPermission(userRoles: string[], permission: Permission): boolean {
  for (const role of userRoles) {
    if (ROLE_PERMISSIONS[role]?.includes(permission)) {
      return true;
    }
  }
  return false;
}

export function hasAnyPermission(userRoles: string[], permissions: Permission[]): boolean {
  return permissions.some((p) => hasPermission(userRoles, p));
}

export function hasAllPermissions(userRoles: string[], permissions: Permission[]): boolean {
  return permissions.every((p) => hasPermission(userRoles, p));
}
