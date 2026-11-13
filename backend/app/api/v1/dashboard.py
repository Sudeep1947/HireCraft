import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.domain.models import (
    AuditLog,
    CandidateRanking,
    Job,
    JobApplication,
    ScreeningResult,
    User,
    UserRole,
)
from app.domain.schemas import (
    AdminDashboardResponse,
    AdminUserListItem,
    AuditLogResponse,
    CandidateDashboardResponse,
    HRDashboardResponse,
    RecruiterDashboardResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _get_primary_role(user: User) -> str:
    if user.roles:
        return user.roles[0].role.name
    return "candidate"


# ─── Candidate Dashboard ─────────────────────────────────────────────


@router.get("/candidate", response_model=CandidateDashboardResponse)
async def candidate_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("candidate")),
):
    app_count = await db.execute(
        select(func.count(JobApplication.id)).where(JobApplication.candidate_id == current_user.id),
    )
    total_applications = app_count.scalar() or 0

    profile_completion = 0

    try:
        from app.domain.models import SavedJob
        saved_result = await db.execute(
            select(func.count(SavedJob.candidate_id)).where(
                SavedJob.candidate_id == current_user.id
            ),
        )
        saved_jobs = saved_result.scalar() or 0
    except Exception:
        saved_jobs = 0

    recent_apps_result = await db.execute(
        select(JobApplication)
        .where(JobApplication.candidate_id == current_user.id)
        .order_by(JobApplication.created_at.desc())
        .limit(5)
    )
    recent_apps = recent_apps_result.scalars().all()
    recent_applications = [
        {
            "id": str(a.id),
            "job_id": str(a.job_id),
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a in recent_apps
    ]

    return CandidateDashboardResponse(
        total_applications=total_applications,
        saved_jobs=saved_jobs,
        profile_completion=profile_completion,
        recent_applications=recent_applications,
    )


# ─── Recruiter Dashboard ─────────────────────────────────────────────


@router.get("/recruiter", response_model=RecruiterDashboardResponse)
async def recruiter_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "recruiter")),
):
    job_count = await db.execute(
        select(func.count(Job.id)).where(Job.recruiter_id == current_user.id),
    )
    total_jobs = job_count.scalar() or 0

    active_count = await db.execute(
        select(func.count(Job.id)).where(
            Job.recruiter_id == current_user.id, Job.status == "published",
        ),
    )
    active_jobs = active_count.scalar() or 0

    app_count = await db.execute(
        select(func.count(JobApplication.id))
        .join(Job, Job.id == JobApplication.job_id)
        .where(Job.recruiter_id == current_user.id),
    )
    total_applications = app_count.scalar() or 0

    screened_count = await db.execute(
        select(func.count(ScreeningResult.id))
        .join(Job, Job.id == ScreeningResult.job_id)
        .where(Job.recruiter_id == current_user.id),
    )
    candidates_screened = screened_count.scalar() or 0

    pipeline_result = await db.execute(
        select(JobApplication.status, func.count(JobApplication.id))
        .join(Job, Job.id == JobApplication.job_id)
        .where(Job.recruiter_id == current_user.id)
        .group_by(JobApplication.status)
    )
    interview_pipeline = {row[0]: row[1] for row in pipeline_result.all()}

    recent_apps_result = await db.execute(
        select(JobApplication, Job.title)
        .join(Job, Job.id == JobApplication.job_id)
        .where(Job.recruiter_id == current_user.id)
        .order_by(JobApplication.created_at.desc())
        .limit(10)
    )
    recent_applications = [
        {
            "id": str(a.id),
            "job_id": str(a.job_id),
            # Named so the dashboard can show "Application … · Senior Backend
            # Engineer" rather than an unexplained truncated UUID. The query is
            # already scoped to this recruiter's own jobs.
            "job_title": job_title or "",
            "candidate_id": str(a.candidate_id),
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a, job_title in recent_apps_result.all()
    ]

    top_result = await db.execute(
        select(CandidateRanking, User.full_name)
        .join(Job, Job.id == CandidateRanking.job_id)
        .join(User, User.id == CandidateRanking.candidate_id)
        .where(Job.recruiter_id == current_user.id)
        .order_by(CandidateRanking.overall_score.desc())
        .limit(5)
    )
    # `candidate_name` is carried alongside `candidate_id` so the UI can label
    # the identifier as belonging to a person instead of using a truncated UUID
    # as a stand-in name. The join is inner on a user the ranking already
    # references (FK, cascade delete), and the rows remain scoped to this
    # recruiter's own jobs.
    top_candidates = [
        {
            "candidate_id": str(r.candidate_id),
            "candidate_name": full_name or "",
            "overall_score": r.overall_score,
            "rank": r.rank,
            "strength_level": r.strength_level,
        }
        for r, full_name in top_result.all()
    ]

    return RecruiterDashboardResponse(
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        total_applications=total_applications,
        candidates_screened=candidates_screened,
        top_candidates=top_candidates,
        interview_pipeline=interview_pipeline,
        recent_applications=recent_applications,
    )


# ─── HR Dashboard ────────────────────────────────────────────────────


@router.get("/hr", response_model=HRDashboardResponse)
async def hr_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("hr", "hr_manager")),
):
    open_positions = await db.execute(
        select(func.count(Job.id)).where(Job.status == "published"),
    )
    open_positions_count = open_positions.scalar() or 0

    try:
        from app.domain.models import Role
        cand_role = await db.execute(
            select(Role.id).where(Role.name == "candidate")
        )
        cand_role_id = cand_role.scalar()
        if cand_role_id:
            tc = await db.execute(
                select(func.count(UserRole.user_id)).where(UserRole.role_id == cand_role_id)
            )
            total_candidates = tc.scalar() or 0
        else:
            total_candidates = 0

        rec_role = await db.execute(
            select(Role.id).where(Role.name == "recruiter")
        )
        rec_role_id = rec_role.scalar()
        if rec_role_id:
            tr = await db.execute(
                select(func.count(UserRole.user_id)).where(UserRole.role_id == rec_role_id)
            )
            total_recruiters = tr.scalar() or 0
        else:
            total_recruiters = 0
    except Exception:
        total_candidates = 0
        total_recruiters = 0

    app_status_result = await db.execute(
        select(JobApplication.status, func.count(JobApplication.id))
        .group_by(JobApplication.status)
    )
    hiring_funnel = {row[0]: row[1] for row in app_status_result.all()}

    dept_result = await db.execute(
        select(Job.department, func.count(Job.id))
        .where(Job.department.isnot(None))
        .group_by(Job.department)
    )
    department_hiring = [
        {"department": row[0], "count": row[1]} for row in dept_result.all() if row[0]
    ]

    return HRDashboardResponse(
        open_positions=open_positions_count,
        total_candidates=total_candidates,
        total_recruiters=total_recruiters,
        hiring_funnel=hiring_funnel,
        department_hiring=department_hiring,
    )


# ─── Admin Dashboard ─────────────────────────────────────────────────


@router.get("/admin", response_model=AdminDashboardResponse)
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active.is_(True))
    )
    active_users = active_users_result.scalar() or 0

    role_counts = {}
    for role_name in ["candidate", "recruiter", "hr", "admin"]:
        try:
            from app.domain.models import Role
            role_result = await db.execute(
                select(Role.id).where(Role.name == role_name)
            )
            role_id = role_result.scalar()
            if role_id:
                count_result = await db.execute(
                    select(func.count(UserRole.user_id)).where(UserRole.role_id == role_id)
                )
                role_counts[role_name] = count_result.scalar() or 0
            else:
                role_counts[role_name] = 0
        except Exception:
            role_counts[role_name] = 0

    recent_logins_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "login")
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_logins = [
        {
            "user_id": str(l.user_id) if l.user_id else None,
            "success": l.success,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        }
        for l in recent_logins_result.scalars().all()
    ]

    return AdminDashboardResponse(
        total_users=total_users,
        active_users=active_users,
        total_candidates=role_counts.get("candidate", 0),
        total_recruiters=role_counts.get("recruiter", 0),
        total_hr=role_counts.get("hr", 0),
        total_admins=role_counts.get("admin", 0),
        recent_logins=recent_logins,
    )


# ─── Admin: User Management ──────────────────────────────────────────


@router.get("/admin/users", response_model=list[AdminUserListItem])
async def admin_list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    from sqlalchemy.orm import selectinload

    offset = (page - 1) * page_size
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    users = result.scalars().unique().all()
    return [
        AdminUserListItem(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            is_active=u.is_active,
            is_verified=u.is_verified,
            roles=[ur.role.name for ur in u.roles],
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]


# ─── Admin: Audit Logs ───────────────────────────────────────────────


@router.get("/admin/audit-logs", response_model=list[AuditLogResponse])
async def admin_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    logs = result.scalars().all()
    return [
        AuditLogResponse(
            id=l.id,
            user_id=l.user_id,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            details=l.details,
            ip_address=l.ip_address,
            success=l.success,
            created_at=l.created_at,
        )
        for l in logs
    ]


# ─── Admin: System Stats ─────────────────────────────────────────────


@router.get("/admin/stats")
async def admin_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    job_count = await db.execute(select(func.count(Job.id)))
    app_count = await db.execute(select(func.count(JobApplication.id)))
    screening_count = await db.execute(select(func.count(ScreeningResult.id)))

    return {
        "total_jobs": job_count.scalar() or 0,
        "total_applications": app_count.scalar() or 0,
        "total_screenings": screening_count.scalar() or 0,
    }
