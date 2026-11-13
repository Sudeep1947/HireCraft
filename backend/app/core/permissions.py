"""Enterprise RBAC Permission Model – Phase 1 Updated.

Defines fine-grained permissions for each role and provides
reusable utilities for permission checking across the platform.

Role Hierarchy:
    super_admin > organization_admin > hr_manager > recruiter > candidate
"""

from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    # ── Candidate ──────────────────────────────────────────────
    PROFILE_VIEW = "candidate:profile:view"
    PROFILE_EDIT = "candidate:profile:edit"
    RESUME_UPLOAD = "candidate:resume:upload"
    RESUME_VIEW = "candidate:resume:view"
    RESUME_DELETE = "candidate:resume:delete"
    RESUME_INTELLIGENCE = "candidate:resume:intelligence"
    JOB_BROWSE = "candidate:job:browse"
    JOB_SAVE = "candidate:job:save"
    JOB_APPLY = "candidate:job:apply"
    APPLICATION_VIEW = "candidate:application:view"
    NOTIFICATION_VIEW = "candidate:notification:view"
    NOTIFICATION_MANAGE = "candidate:notification:manage"
    SETTINGS_PASSWORD = "candidate:settings:password"
    SETTINGS_EMAIL = "candidate:settings:email"
    SETTINGS_ACCOUNT = "candidate:settings:account"
    INTELLIGENCE_VIEW = "candidate:intelligence:view"
    XAI_SELF_VIEW = "candidate:xai:self_view"
    XAI_SELF_RECOMMEND = "candidate:xai:self_recommend"
    FAIRNESS_SELF_VIEW = "candidate:fairness:self_view"
    INTERVIEW_MOCK_START = "candidate:interview:mock_start"
    INTERVIEW_MOCK_ANSWER = "candidate:interview:mock_answer"
    INTERVIEW_SELF_VIEW = "candidate:interview:self_view"
    INTERVIEW_SELF_SCORECARD = "candidate:interview:self_scorecard"

    # ── Recruiter ──────────────────────────────────────────────
    JOB_CREATE = "recruiter:job:create"
    JOB_EDIT = "recruiter:job:edit"
    JOB_DELETE = "recruiter:job:delete"
    JOB_PUBLISH = "recruiter:job:publish"
    JOB_CLOSE = "recruiter:job:close"
    APPLICANT_VIEW = "recruiter:applicant:view"
    APPLICANT_MANAGE = "recruiter:applicant:manage"
    RESUME_SCREEN = "recruiter:resume:screen"
    RESUME_DOWNLOAD = "recruiter:resume:download"
    CANDIDATE_RANK = "recruiter:candidate:rank"
    CANDIDATE_COMPARE = "recruiter:candidate:compare"
    AI_SEARCH = "recruiter:ai:search"
    AI_INSIGHTS = "recruiter:ai:insights"
    AI_RECOMMENDATIONS = "recruiter:ai:recommendations"
    XAI_EXPLAIN = "recruiter:xai:explain"
    XAI_COMPARE = "recruiter:xai:compare"
    FAIRNESS_VIEW = "recruiter:fairness:view"
    FAIRNESS_ANALYZE = "recruiter:fairness:analyze"
    FAIRNESS_ADVERSARIAL = "recruiter:fairness:adversarial"
    FAIRNESS_JD_ANALYSIS = "recruiter:fairness:jd_analysis"
    INTERVIEW_SCHEDULE = "recruiter:interview:schedule"
    INTERVIEW_GENERATE = "recruiter:interview:generate"
    INTERVIEW_EVALUATE = "recruiter:interview:evaluate"
    INTERVIEW_SCORECARD_VIEW = "recruiter:interview:scorecard_view"
    INTERVIEW_SCORECARD_MANAGE = "recruiter:interview:scorecard_manage"
    INTERVIEW_NOTES = "recruiter:interview:notes"
    NOTE_MANAGE = "recruiter:note:manage"
    RECRUITER_DASHBOARD = "recruiter:dashboard:view"
    RECRUITER_NOTIFICATION = "recruiter:notification:view"

    # ── HR Manager ─────────────────────────────────────────────
    HR_DASHBOARD = "hr:dashboard:view"
    HR_PIPELINE = "hr:pipeline:view"
    HR_PIPELINE_MANAGE = "hr:pipeline:manage"
    HR_REPORTS = "hr:reports:view"
    HR_ANALYTICS = "hr:analytics:view"
    HR_RECRUITER_VIEW = "hr:recruiter:view"
    HR_CANDIDATE_VIEW = "hr:candidate:view"
    HR_INTERVIEW_VIEW = "hr:interview:view"
    HR_INTERVIEW_ANALYTICS = "hr:interview:analytics"
    HR_INTERVIEW_SCORECARD_VIEW = "hr:interview:scorecard_view"
    HR_OFFER_VIEW = "hr:offer:view"

    # ── Organization Admin ─────────────────────────────────────
    ORG_TEAM_INVITE = "org:team:invite"
    ORG_TEAM_MANAGE = "org:team:manage"
    ORG_TEAM_VIEW = "org:team:view"
    ORG_SETTINGS = "org:settings:manage"
    ORG_SETTINGS_VIEW = "org:settings:view"
    ORG_ROLE_ASSIGN = "org:role:assign"
    ORG_MEMBERSHIP_SUSPEND = "org:membership:suspend"
    ORG_MEMBERSHIP_REVOKE = "org:membership:revoke"
    ORG_MEMBERSHIP_REACTIVATE = "org:membership:reactivate"

    # ── Super Admin (Platform) ─────────────────────────────────
    PLATFORM_ADMIN = "platform:admin"
    PLATFORM_USER_VIEW = "platform:user:view"
    PLATFORM_USER_MANAGE = "platform:user:manage"
    PLATFORM_ORG_VIEW = "platform:org:view"
    PLATFORM_ORG_MANAGE = "platform:org:manage"
    PLATFORM_AUDIT_VIEW = "platform:audit:view"
    PLATFORM_SYSTEM_VIEW = "platform:system:view"
    PLATFORM_SYSTEM_MANAGE = "platform:system:manage"

    # ── Legacy Admin (backward compat) ─────────────────────────
    ADMIN_DASHBOARD = "admin:dashboard:view"
    ADMIN_USER_VIEW = "admin:user:view"
    ADMIN_USER_MANAGE = "admin:user:manage"
    ADMIN_ROLE_VIEW = "admin:role:view"
    ADMIN_ROLE_MANAGE = "admin:role:manage"
    ADMIN_AUDIT_VIEW = "admin:audit:view"
    ADMIN_SYSTEM_VIEW = "admin:system:view"
    ADMIN_SYSTEM_MANAGE = "admin:system:manage"
    ADMIN_ANALYTICS = "admin:analytics:view"

    # ── Analytics (cross-role) ───────────────────────────────────
    ANALYTICS_CANDIDATE = "analytics:candidate:view"
    ANALYTICS_RECRUITER = "analytics:recruiter:view"
    ANALYTICS_HR = "analytics:hr:view"
    ANALYTICS_ADMIN = "analytics:admin:view"
    ANALYTICS_EXECUTIVE = "analytics:executive:view"
    ANALYTICS_PREDICTIONS = "analytics:predictions:view"
    ANALYTICS_INSIGHTS = "analytics:insights:view"
    ANALYTICS_REPORTS = "analytics:reports:manage"
    ANALYTICS_ALERTS = "analytics:alerts:manage"
    ANALYTICS_LAYOUT = "analytics:layout:manage"

    # ── Agentic AI Platform ─────────────────────────────────────
    AGENT_CHAT = "agent:chat"
    AGENT_WORKFLOW = "agent:workflow"
    AGENT_REPORT = "agent:report"
    AGENT_ACTIVITY = "agent:activity"
    AGENT_STATS = "agent:stats"
    AGENT_TOOLS = "agent:tools"


# ── Role → Permissions mapping ──────────────────────────────────

ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    "candidate": [
        Permission.PROFILE_VIEW,
        Permission.PROFILE_EDIT,
        Permission.RESUME_UPLOAD,
        Permission.RESUME_VIEW,
        Permission.RESUME_DELETE,
        Permission.RESUME_INTELLIGENCE,
        Permission.JOB_BROWSE,
        Permission.JOB_SAVE,
        Permission.JOB_APPLY,
        Permission.APPLICATION_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.NOTIFICATION_MANAGE,
        Permission.SETTINGS_PASSWORD,
        Permission.SETTINGS_EMAIL,
        Permission.SETTINGS_ACCOUNT,
        Permission.INTELLIGENCE_VIEW,
        Permission.XAI_SELF_VIEW,
        Permission.XAI_SELF_RECOMMEND,
        Permission.FAIRNESS_SELF_VIEW,
        Permission.INTERVIEW_MOCK_START,
        Permission.INTERVIEW_MOCK_ANSWER,
        Permission.INTERVIEW_SELF_VIEW,
        Permission.INTERVIEW_SELF_SCORECARD,
        Permission.ANALYTICS_CANDIDATE,
        Permission.ANALYTICS_INSIGHTS,
        Permission.AGENT_CHAT,
    ],
    "recruiter": [
        Permission.JOB_CREATE,
        Permission.JOB_EDIT,
        Permission.JOB_DELETE,
        Permission.JOB_PUBLISH,
        Permission.JOB_CLOSE,
        Permission.APPLICANT_VIEW,
        Permission.APPLICANT_MANAGE,
        Permission.RESUME_SCREEN,
        Permission.RESUME_DOWNLOAD,
        Permission.CANDIDATE_RANK,
        Permission.CANDIDATE_COMPARE,
        Permission.AI_SEARCH,
        Permission.AI_INSIGHTS,
        Permission.AI_RECOMMENDATIONS,
        Permission.XAI_EXPLAIN,
        Permission.XAI_COMPARE,
        Permission.FAIRNESS_VIEW,
        Permission.FAIRNESS_ANALYZE,
        Permission.FAIRNESS_ADVERSARIAL,
        Permission.FAIRNESS_JD_ANALYSIS,
        Permission.INTERVIEW_SCHEDULE,
        Permission.INTERVIEW_GENERATE,
        Permission.INTERVIEW_EVALUATE,
        Permission.INTERVIEW_SCORECARD_VIEW,
        Permission.INTERVIEW_SCORECARD_MANAGE,
        Permission.INTERVIEW_NOTES,
        Permission.NOTE_MANAGE,
        Permission.RECRUITER_DASHBOARD,
        Permission.RECRUITER_NOTIFICATION,
        Permission.ANALYTICS_RECRUITER,
        Permission.ANALYTICS_PREDICTIONS,
        Permission.ANALYTICS_INSIGHTS,
        Permission.ANALYTICS_REPORTS,
        Permission.ANALYTICS_ALERTS,
        Permission.AGENT_CHAT,
        Permission.AGENT_WORKFLOW,
        Permission.AGENT_REPORT,
    ],
    "hr": [
        Permission.HR_DASHBOARD,
        Permission.HR_PIPELINE,
        Permission.HR_PIPELINE_MANAGE,
        Permission.HR_REPORTS,
        Permission.HR_ANALYTICS,
        Permission.HR_RECRUITER_VIEW,
        Permission.HR_CANDIDATE_VIEW,
        Permission.HR_INTERVIEW_VIEW,
        Permission.HR_INTERVIEW_ANALYTICS,
        Permission.HR_INTERVIEW_SCORECARD_VIEW,
        Permission.HR_OFFER_VIEW,
        Permission.FAIRNESS_VIEW,
        Permission.FAIRNESS_ANALYZE,
        Permission.ANALYTICS_HR,
        Permission.ANALYTICS_EXECUTIVE,
        Permission.ANALYTICS_PREDICTIONS,
        Permission.ANALYTICS_INSIGHTS,
        Permission.ANALYTICS_REPORTS,
        Permission.ANALYTICS_ALERTS,
        Permission.AGENT_CHAT,
        Permission.AGENT_WORKFLOW,
        Permission.AGENT_REPORT,
        Permission.AGENT_ACTIVITY,
        Permission.AGENT_STATS,
    ],
    "hr_manager": [
        Permission.HR_DASHBOARD,
        Permission.HR_PIPELINE,
        Permission.HR_PIPELINE_MANAGE,
        Permission.HR_REPORTS,
        Permission.HR_ANALYTICS,
        Permission.HR_RECRUITER_VIEW,
        Permission.HR_CANDIDATE_VIEW,
        Permission.HR_INTERVIEW_VIEW,
        Permission.HR_INTERVIEW_ANALYTICS,
        Permission.HR_INTERVIEW_SCORECARD_VIEW,
        Permission.HR_OFFER_VIEW,
        Permission.FAIRNESS_VIEW,
        Permission.FAIRNESS_ANALYZE,
        Permission.ANALYTICS_HR,
        Permission.ANALYTICS_EXECUTIVE,
        Permission.ANALYTICS_PREDICTIONS,
        Permission.ANALYTICS_INSIGHTS,
        Permission.ANALYTICS_REPORTS,
        Permission.ANALYTICS_ALERTS,
        Permission.AGENT_CHAT,
        Permission.AGENT_WORKFLOW,
        Permission.AGENT_REPORT,
        Permission.AGENT_ACTIVITY,
        Permission.AGENT_STATS,
    ],
    "organization_admin": [
        p for p in Permission
        if not p.value.startswith("platform:")
    ],
    "super_admin": [p for p in Permission],
    "admin": [p for p in Permission],
}

ROLE_PERMISSIONS["hr"] = ROLE_PERMISSIONS["hr_manager"]


def get_permissions_for_role(role_name: str) -> list[Permission]:
    return ROLE_PERMISSIONS.get(role_name, [])


def role_has_permission(role_name: str, permission: Permission) -> bool:
    perms = ROLE_PERMISSIONS.get(role_name, [])
    return permission in perms


def user_has_permission(user_roles: list[str], permission: Permission) -> bool:
    for role in user_roles:
        if role_has_permission(role, permission):
            return True
    return False


def get_all_permissions_for_user(user_roles: list[str]) -> set[Permission]:
    result: set[Permission] = set()
    for role in user_roles:
        result.update(ROLE_PERMISSIONS.get(role, []))
    return result


# ── Legacy role compatibility helpers ────────────────────────────

LEGACY_ROLE_MAP: dict[str, str] = {
    "admin": "organization_admin",
    "hr": "hr_manager",
    "recruiter": "recruiter",
    "candidate": "candidate",
}


def normalize_role_name(role: str) -> str:
    return LEGACY_ROLE_MAP.get(role, role)


# ── Role equivalence for route guards ────────────────────────────
# Legacy route guards name a tier (e.g. require_role("hr")). These sets
# define which concrete roles satisfy each tier, mirroring the frontend
# role groups in App.tsx.

ROLE_EQUIVALENCE: dict[str, frozenset[str]] = {
    "admin": frozenset({"admin", "super_admin"}),
    "super_admin": frozenset({"admin", "super_admin"}),
    "hr": frozenset({"hr", "hr_manager", "organization_admin", "admin", "super_admin"}),
    "hr_manager": frozenset({"hr", "hr_manager", "organization_admin", "admin", "super_admin"}),
    "recruiter": frozenset({"recruiter", "hr", "hr_manager", "organization_admin", "admin", "super_admin"}),
    "organization_admin": frozenset({"organization_admin", "admin", "super_admin"}),
    "candidate": frozenset({"candidate"}),
}


def expand_required_roles(roles: tuple[str, ...] | list[str]) -> set[str]:
    """Expand guard role names into the full set of roles that satisfy them."""
    expanded: set[str] = set()
    for role in roles:
        expanded |= ROLE_EQUIVALENCE.get(role, {role})
    return expanded
