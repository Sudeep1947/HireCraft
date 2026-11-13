"""Typed access-control errors + server-side authorization for screening reads."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MembershipStatus
from app.domain.models import (
    Job,
    JobApplication,
    OrganizationMembership,
    Role,
    User,
    UserRole,
)


class JobNotFoundError(ValueError):
    pass


class JobAccessDeniedError(PermissionError):
    pass


class CandidateNotAccessibleError(PermissionError):
    pass


class ApplicationAccessDeniedError(PermissionError):
    """The application exists but does not belong to the requesting user.

    Raised instead of leaking existence: a candidate asking for somebody
    else's application id must be indistinguishable from one asking for a
    non-existent id.
    """


async def authorize_application_ownership(
    session: AsyncSession,
    application_id: uuid.UUID,
    user: User,
    application: JobApplication | None = None,
) -> JobApplication:
    """Return the application when ``user`` is its candidate, otherwise raise.

    Candidate-facing reads (an application's explanation, status, evidence) are
    scoped by ownership alone. There is deliberately no organization or job
    check on this path: the candidate is not a member of the hiring
    organization, and the application row is the only link between the two.

    IDOR defence: the ``application_id`` in the path is untrusted input, so
    ownership is compared against the loaded row rather than trusted from the
    request. Raises the same error for "not yours" and "does not exist".
    """
    if application is None:
        application = await session.get(JobApplication, application_id)
    if application is None:
        raise ApplicationAccessDeniedError("Application not found")
    if application.candidate_id != user.id:
        raise ApplicationAccessDeniedError(
            "You do not have access to this application"
        )
    return application


# Roles that may read job-scoped intelligence within their organization.
_ORG_READ_ROLES = {"recruiter", "hr", "hr_manager", "organization_admin", "admin"}

# A platform admin may read across organizations; everyone else is scoped.
_PLATFORM_ADMIN_ROLE = "admin"


async def authorize_job_access(
    session: AsyncSession, job_id: uuid.UUID, user: User,
) -> Job:
    """Return the job if ``user`` may access it, otherwise raise.

    Allowed: the recruiter who owns the job, or an active member of the
    job's organization holding one of ``_ORG_READ_ROLES``. This is enforced
    server-side regardless of frontend filtering.
    """
    job = await session.get(Job, job_id)
    if not job:
        raise JobNotFoundError("Job not found")

    if job.recruiter_id == user.id:
        return job

    if job.organization_id is not None:
        stmt = select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == job.organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value,
        )
        membership = (await session.execute(stmt)).scalar_one_or_none()
        if membership and membership.role in _ORG_READ_ROLES:
            return job

    raise JobAccessDeniedError("You do not have access to this job")


async def authorized_job_ids(
    session: AsyncSession, user: User,
) -> list[uuid.UUID] | None:
    """Every job id ``user`` may read, or ``None`` for an unscoped platform view.

    Platform-wide fairness reads (``/fairness/overview``, ``/fairness/metrics``,
    ``/fairness/bias-alerts``) aggregate screening outcomes across every job in
    the database. Without a scope they hand one tenant a view of another
    tenant's candidate counts, score distributions and bias alerts, so callers
    pass the returned ids into the engine to constrain its queries.

    ``None`` means "do not restrict", and is returned only for a platform admin,
    who is already entitled to the cross-tenant view. Every other caller gets a
    possibly empty list -- an empty list is a valid, safe answer meaning "this
    user can read no jobs", and the engine then reports empty populations
    rather than falling back to unscoped queries.
    """
    user_roles: set[str] = set()
    if "roles" in user.__dict__:
        for ur in user.__dict__["roles"] or []:
            if "role" in getattr(ur, "__dict__", {}) and ur.__dict__["role"] is not None:
                user_roles.add(ur.__dict__["role"].name)
    if not user_roles:
        try:
            role_stmt = (
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
            )
            user_roles = set((await session.execute(role_stmt)).scalars().all())
        except Exception:
            pass
    if _PLATFORM_ADMIN_ROLE in user_roles:
        return None

    org_ids = select(OrganizationMembership.organization_id).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.role.in_(_ORG_READ_ROLES),
        OrganizationMembership.status == MembershipStatus.ACTIVE.value,
    )
    stmt = select(Job.id).where(
        or_(Job.recruiter_id == user.id, Job.organization_id.in_(org_ids))
    )
    return list((await session.execute(stmt)).scalars().all())


async def authorize_candidate_access(
    session: AsyncSession, candidate_id: uuid.UUID, user: User,
) -> None:
    """Raise unless ``user`` may read candidate-scoped intelligence.

    A recruiter/HR may view candidate-level intelligence only when the
    candidate applied to at least one job they can access (owned by them or
    shared through their organization with a read role). Enforced
    server-side regardless of frontend filtering.
    """
    org_ids = select(OrganizationMembership.organization_id).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.role.in_(_ORG_READ_ROLES),
        OrganizationMembership.status == MembershipStatus.ACTIVE.value,
    )
    stmt = (
        select(JobApplication.id)
        .join(Job, JobApplication.job_id == Job.id)
        .where(JobApplication.candidate_id == candidate_id)
        .where(
            or_(
                Job.recruiter_id == user.id,
                Job.organization_id.in_(org_ids),
            )
        )
        .limit(1)
    )
    application_id = (await session.execute(stmt)).scalar_one_or_none()
    if application_id is None:
        raise CandidateNotAccessibleError(
            "You do not have access to this candidate"
        )
