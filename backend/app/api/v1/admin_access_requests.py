"""Admin API endpoints for managing access requests.

Requires authentication + admin role in the organization.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.logging import get_logger
from app.domain.access_request_schemas import (
    AccessRequestActionResponse,
    AccessRequestAdminListResponse,
    AccessRequestAdminResponse,
    AccessRequestApprove,
    AccessRequestReject,
)
from app.services.access_request_service import AccessRequestService
from app.api.deps import get_current_user, require_role
from app.domain.models import User

logger = get_logger(__name__)

router = APIRouter()


@router.get("/access-requests", response_model=AccessRequestAdminListResponse)
async def list_access_requests(
    status: str | None = Query(None, description="Filter by status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_role("organization_admin", "super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestAdminListResponse:
    """List all pending access requests for the admin's organizations."""
    service = AccessRequestService(db)

    # Get all orgs the admin belongs to
    from app.repositories.membership import OrganizationMembershipRepository
    membership_repo = OrganizationMembershipRepository(db)
    memberships = await membership_repo.get_user_organizations(current_user.id)

    all_requests = []
    total = 0
    for membership in memberships:
        requests, org_total = await service.list_requests(
            organization_id=membership.organization_id,
            status=status,
            offset=0,
            limit=1000,  # Get all for aggregation
        )
        for req in requests:
            all_requests.append(req)
        total += org_total

    # Apply pagination after aggregation
    paginated = all_requests[offset : offset + limit]

    return AccessRequestAdminListResponse(
        requests=[
            AccessRequestAdminResponse(
                id=req.id,
                full_name=req.full_name,
                email=req.email,
                organization_id=req.organization_id,
                organization_name="Organization",
                requested_role=req.requested_role,
                status=req.status,
                email_verified_at=req.email_verified_at,
                approved_role=req.approved_role,
                reviewed_by_id=req.reviewed_by_id,
                reviewed_at=req.reviewed_at,
                rejection_reason=req.rejection_reason,
                created_user_id=req.created_user_id,
                created_at=req.created_at,
                updated_at=req.updated_at,
            )
            for req in paginated
        ],
        total=total,
    )


@router.get("/access-requests/{request_id}", response_model=AccessRequestAdminResponse)
async def get_access_request_detail(
    request_id: str,
    current_user: User = Depends(require_role("organization_admin", "super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestAdminResponse:
    """Get detailed information about a specific access request."""
    import uuid as _uuid

    service = AccessRequestService(db)

    # Get all orgs the admin belongs to
    from app.repositories.membership import OrganizationMembershipRepository
    membership_repo = OrganizationMembershipRepository(db)
    memberships = await membership_repo.get_user_organizations(current_user.id)

    # Try each org
    for membership in memberships:
        try:
            req = await service.get_request(_uuid.UUID(request_id), membership.organization_id)
            return AccessRequestAdminResponse(
                id=req.id,
                full_name=req.full_name,
                email=req.email,
                organization_id=req.organization_id,
                organization_name="Organization",
                requested_role=req.requested_role,
                status=req.status,
                email_verified_at=req.email_verified_at,
                approved_role=req.approved_role,
                reviewed_by_id=req.reviewed_by_id,
                reviewed_at=req.reviewed_at,
                rejection_reason=req.rejection_reason,
                created_user_id=req.created_user_id,
                created_at=req.created_at,
                updated_at=req.updated_at,
            )
        except Exception:
            continue

    from app.core.exceptions import NotFoundError
    raise NotFoundError(detail="Access request not found.")


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequestActionResponse)
async def approve_access_request(
    request_id: str,
    body: AccessRequestApprove,
    current_user: User = Depends(require_role("organization_admin", "super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestActionResponse:
    """Approve an access request with a specific role.

    Generates an activation token. Send the activation link to the employee.
    """
    import uuid as _uuid

    service = AccessRequestService(db)

    from app.repositories.membership import OrganizationMembershipRepository
    membership_repo = OrganizationMembershipRepository(db)
    memberships = await membership_repo.get_user_organizations(current_user.id)

    for membership in memberships:
        try:
            req = await service.approve_request(
                request_id=_uuid.UUID(request_id),
                organization_id=membership.organization_id,
                approved_role=body.approved_role,
                reviewed_by_id=current_user.id,
            )

            raw_activation_token = getattr(req, "_raw_activation_token", None)

            if raw_activation_token:
                from app.domain.enums import AccessRequestRole
                from app.notifications.email_tasks import queue_access_request_approved_email
                role_label = {
                    AccessRequestRole.HR_MANAGER.value: "HR Manager",
                    AccessRequestRole.RECRUITER.value: "Recruiter",
                }.get(body.approved_role, body.approved_role)
                queue_access_request_approved_email(
                    to_email=req.email,
                    full_name=req.full_name,
                    organization_name=str(req.organization_id),
                    role_label=role_label,
                    raw_activation_token=raw_activation_token,
                    request_id=str(req.id),
                )

            return AccessRequestActionResponse(
                status="approved",
                message="Access request approved. Send the activation link to the employee.",
                request_id=req.id,
            )
        except Exception:
            continue

    from app.core.exceptions import NotFoundError
    raise NotFoundError(detail="Access request not found or cannot be approved.")


@router.post("/access-requests/{request_id}/reject", response_model=AccessRequestActionResponse)
async def reject_access_request(
    request_id: str,
    body: AccessRequestReject,
    current_user: User = Depends(require_role("organization_admin", "super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestActionResponse:
    """Reject an access request."""
    import uuid as _uuid

    service = AccessRequestService(db)

    from app.repositories.membership import OrganizationMembershipRepository
    membership_repo = OrganizationMembershipRepository(db)
    memberships = await membership_repo.get_user_organizations(current_user.id)

    for membership in memberships:
        try:
            req = await service.reject_request(
                request_id=_uuid.UUID(request_id),
                organization_id=membership.organization_id,
                reviewed_by_id=current_user.id,
                reason=body.reason,
            )

            from app.domain.enums import AccessRequestRole
            from app.notifications.email_tasks import queue_access_request_rejected_email
            role_label = {
                AccessRequestRole.HR_MANAGER.value: "HR Manager",
                AccessRequestRole.RECRUITER.value: "Recruiter",
            }.get(req.requested_role or "", req.requested_role or "Team Member")
            queue_access_request_rejected_email(
                to_email=req.email,
                full_name=req.full_name,
                organization_name=str(req.organization_id),
                role_label=role_label,
                reason=body.reason,
            )

            return AccessRequestActionResponse(
                status="rejected",
                message="Access request rejected.",
                request_id=req.id,
            )
        except Exception:
            continue

    from app.core.exceptions import NotFoundError
    raise NotFoundError(detail="Access request not found or cannot be rejected.")
