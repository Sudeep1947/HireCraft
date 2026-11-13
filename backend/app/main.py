from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text

from app.api.errors import register_error_handlers
from app.api.v1 import (
    auth, candidates, candidate_jobs, dashboard, health, notifications,
    recruiter_jobs, resume_intelligence, screening, users, ai_intelligence,
    xai, fairness, interview, interview_video, analytics, agent, demo,
    assessments, organizations, invitations, simulations, sandboxes, hr,
    simulation_reports, simulation_experiments, access_requests,
    admin_access_requests, post_hiring,
)
from app.skill2job import skill2job_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import register_middleware
from app.core.security_middleware import register_security_middleware
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.domain.enums import AccountStatus
from app.domain.models import Organization, OrganizationMembership, Role, User, UserRole
from app.repositories.user import UserRepository

settings = get_settings()
logger = get_logger(__name__)

DEFAULT_ROLES = [
    ("admin", "System administrator with full access"),
    ("super_admin", "Platform super administrator"),
    ("organization_admin", "Organization administrator"),
    ("hr", "Human resources personnel (legacy)"),
    ("hr_manager", "HR manager"),
    ("recruiter", "Recruitment specialist"),
    ("candidate", "Job applicant"),
]


async def _ensure_roles() -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Role))
        existing = {r.name for r in result.scalars().all()}
        for name, desc in DEFAULT_ROLES:
            if name not in existing:
                session.add(Role(name=name, description=desc))
        await session.commit()


async def _seed_admin() -> None:
    async with async_session_factory() as session:
        repo = UserRepository(session)
        admin_user = await repo.get_by_email("admin@hirecraft.ai")
        if not admin_user:
            admin_user = await repo.create(
                full_name="System Admin",
                email="admin@hirecraft.ai",
                password_hash=hash_password("Admin@12345"),
                is_active=True,
                is_verified=True,
                account_status=AccountStatus.ACTIVE.value,
            )
            admin_role = await repo.find_role_by_name("super_admin")
            if admin_role:
                await repo.assign_role(admin_user.id, admin_role.id)
            else:
                admin_role = await repo.find_role_by_name("admin")
                if admin_role:
                    await repo.assign_role(admin_user.id, admin_role.id)
            await session.commit()
            logger.info("Admin account seeded: admin@hirecraft.ai (super_admin)")


async def _seed_demo_organizations() -> None:
    """Create demo organizations and migrate existing privileged users into them."""
    from app.domain.enums import MembershipStatus, RoleName
    from app.repositories.membership import OrganizationMembershipRepository

    async with async_session_factory() as session:
        result = await session.execute(select(Organization))
        existing_orgs = {o.slug for o in result.scalars().all()}

        org_a = None
        org_b = None

        if "acme-corp" not in existing_orgs:
            org_a = Organization(
                name="Acme Corporation",
                slug="acme-corp",
                description="Demo organization A for testing tenant isolation",
                official_email="admin@acme-corp.example.com",
                domain="acme-corp.example.com",
                status="active",
            )
            session.add(org_a)
            await session.flush()
            logger.info("Demo Organization A created: Acme Corporation")

        if "globex-industries" not in existing_orgs:
            org_b = Organization(
                name="Globex Industries",
                slug="globex-industries",
                description="Demo organization B for testing tenant isolation",
                official_email="admin@globex-industries.example.com",
                domain="globex-industries.example.com",
                status="active",
            )
            session.add(org_b)
            await session.flush()
            logger.info("Demo Organization B created: Globex Industries")

        await session.commit()

        # Migrate existing privileged users into org A
        if org_a:
            membership_repo = OrganizationMembershipRepository(session)
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(User).options(selectinload(User.roles).selectinload(UserRole.role))
            )
            users = result.scalars().unique().all()
            for user in users:
                role_names = [ur.role.name for ur in user.roles]
                existing_membership = await membership_repo.get_active_membership(user.id, org_a.id)
                if existing_membership:
                    continue

                if "admin" in role_names or "super_admin" in role_names:
                    role = RoleName.ORG_ADMIN.value
                elif "hr" in role_names or "hr_manager" in role_names:
                    role = RoleName.HR_MANAGER.value
                elif "recruiter" in role_names:
                    role = RoleName.RECRUITER.value
                else:
                    continue

                from datetime import datetime, timezone
                membership = OrganizationMembership(
                    user_id=user.id,
                    organization_id=org_a.id,
                    role=role,
                    status=MembershipStatus.ACTIVE.value,
                    joined_at=datetime.now(timezone.utc),
                )
                session.add(membership)
                logger.info("Migrated user %s (%s) to Acme Corp as %s", user.email, user.id, role)

            await session.commit()


# Columns added to the model after their table was first created. `create_all`
# only creates missing tables and never adds columns to pre-existing ones, so
# older databases would otherwise be missing these. Applied additively and
# idempotently at startup (fresh DBs get them from the model metadata).
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("candidate_profiles", "interests", "JSON"),
    ("candidate_profiles", "avatar_url", "VARCHAR(500)"),
    ("job_applications", "decision_reason", "VARCHAR(255)"),
    ("job_applications", "decision_comment", "TEXT"),
    (
        "job_applications",
        "decided_by",
        "CHAR(32) REFERENCES users(id) ON DELETE SET NULL",
    ),
    ("job_applications", "decided_at", "DATETIME"),
    (
        "job_applications",
        "screening_status",
        "VARCHAR(20) NOT NULL DEFAULT 'not_started'",
    ),
    (
        "job_applications",
        "screening_attempts",
        "INTEGER NOT NULL DEFAULT 0",
    ),
    ("job_applications", "screening_task_id", "VARCHAR(255)"),
    ("job_applications", "screening_error", "TEXT"),
    ("job_applications", "screening_started_at", "DATETIME"),
    ("job_applications", "screening_completed_at", "DATETIME"),
    (
        "screening_results",
        "application_id",
        "CHAR(32) REFERENCES job_applications(id) ON DELETE CASCADE",
    ),
    (
        "skill2job_training_progress",
        "evidence_state",
        "VARCHAR(30) NOT NULL DEFAULT 'not_started'",
    ),
    ("skill2job_training_progress", "learning_hours", "FLOAT"),
    # Phase 14: the shared interview room. ``TIMESTAMP`` rather than the
    # ``DATETIME`` spelled by the entries above, because PostgreSQL has no
    # ``DATETIME`` type and accepts ``TIMESTAMP``, while SQLite accepts any type
    # name. The portable spelling costs nothing and works on both engines.
    ("interviews", "room_id", "VARCHAR(64)"),
    ("interviews", "timezone", "VARCHAR(64) NOT NULL DEFAULT 'UTC'"),
    ("interviews", "candidate_joined_at", "TIMESTAMP"),
    ("interviews", "recruiter_joined_at", "TIMESTAMP"),
    # Phase 15: interview stage + reschedule marker, and the application's HR
    # advancement marker. Additive and defaulted/nullable so older databases gain
    # them without a backfill and every existing row keeps its current meaning.
    ("interviews", "stage", "VARCHAR(20) NOT NULL DEFAULT 'recruiter'"),
    ("interviews", "rescheduled_at", "TIMESTAMP"),
    ("job_applications", "advanced_to_hr_at", "TIMESTAMP"),
    (
        "job_applications",
        "advanced_to_hr_by",
        "CHAR(32) REFERENCES users(id) ON DELETE SET NULL",
    ),
    ("organizations", "industry", "VARCHAR(255)"),
    ("organizations", "website", "VARCHAR(500)"),
    ("organizations", "location", "VARCHAR(255)"),
)


def _apply_additive_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    for table, column, ddl in _ADDITIVE_COLUMNS:
        if table not in existing_tables:
            continue
        if column in {c["name"] for c in inspector.get_columns(table)}:
            continue
        sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        logger.info("Added missing column %s.%s", table, column)

    if "interviews" in existing_tables:
        # ``ALTER TABLE ... ADD COLUMN`` cannot attach a uniqueness constraint, so
        # the one-room-per-interview guarantee is a separate idempotent index. Rows
        # that have not been joined yet hold NULL, and NULLs do not collide in
        # either engine, so the many un-assigned rooms are not a problem.
        sync_conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_interviews_room_id "
                "ON interviews (room_id)"
            )
        )

    if "screening_results" in existing_tables:
        sync_conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_screening_results_application_id "
                "ON screening_results (application_id)"
            )
        )
        sync_conn.execute(
            text(
                "UPDATE screening_results SET application_id = ("
                "SELECT ja.id FROM job_applications ja "
                "WHERE ja.job_id = screening_results.job_id "
                "AND ja.candidate_id = screening_results.candidate_id) "
                "WHERE application_id IS NULL"
            )
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    app.state.db_session = async_session_factory
    try:
        # Idempotent, additive: creates any tables missing from the existing DB.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_apply_additive_columns)
        await _ensure_roles()
        logger.info("Auth roles verified")
        await _seed_admin()
        await _seed_demo_organizations()
    except Exception:
        logger.exception("Failed to seed roles/startup data")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_middleware(app)
register_security_middleware(app)
register_error_handlers(app)

uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(resume_intelligence.router, prefix="/api/v1")
app.include_router(recruiter_jobs.router, prefix="/api/v1")
app.include_router(candidate_jobs.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(screening.router, prefix="/api/v1")
app.include_router(ai_intelligence.router, prefix="/api/v1")
app.include_router(xai.router, prefix="/api/v1")
app.include_router(fairness.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(interview.router, prefix="/api/v1")
app.include_router(interview_video.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(hr.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(demo.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(invitations.router, prefix="/api/v1")
app.include_router(simulations.router, prefix="/api/v1")
app.include_router(sandboxes.router, prefix="/api/v1")
app.include_router(simulation_reports.router, prefix="/api/v1")
app.include_router(simulation_experiments.router, prefix="/api/v1")
app.include_router(skill2job_router, prefix="/api/v1")
app.include_router(access_requests.router, prefix="/api/v1")
app.include_router(admin_access_requests.router, prefix="/api/v1")
app.include_router(post_hiring.router, prefix="/api/v1")
