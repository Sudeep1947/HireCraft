"""Public API endpoints for employee access requests.

No authentication required — employees can request access without an account.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.logging import get_logger
from app.domain.access_request_schemas import (
    AccessRequestActivate,
    AccessRequestActivationResponse,
    AccessRequestAdminListResponse,
    AccessRequestAdminResponse,
    AccessRequestApprove,
    AccessRequestCreate,
    AccessRequestPendingResponse,
    AccessRequestReject,
    AccessRequestResendResponse,
    AccessRequestResponse,
    AccessRequestVerifyResponse,
)
from app.services.access_request_service import AccessRequestService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/access-requests", response_model=AccessRequestResponse, status_code=201)
async def create_access_request(
    body: AccessRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResponse:
    """Employee requests access to their organization.

    No authentication required. The employee submits their name, email, and
    organization identifier. A verification email is sent to their company email.
    """
    from app.domain.enums import AccessRequestRole
    from app.notifications.email_tasks import queue_access_request_verification_email

    service = AccessRequestService(db)
    access_request, raw_token = await service.create_request(
        full_name=body.full_name,
        email=body.email,
        organization_slug=body.organization_slug,
        requested_role=body.requested_role,
    )

    role_label = {
        AccessRequestRole.HR_MANAGER.value: "HR Manager",
        AccessRequestRole.RECRUITER.value: "Recruiter",
    }.get(body.requested_role or "", body.requested_role or "Team Member")

    await db.commit()

    queue_access_request_verification_email(
        to_email=body.email,
        full_name=body.full_name,
        organization_name=access_request.organization_id and str(access_request.organization_id),
        role_label=role_label,
        raw_token=raw_token,
        request_id=str(access_request.id),
    )

    return AccessRequestResponse(
        status="pending_email_verification",
        message="A verification link has been sent to your email. Please check your inbox.",
    )


@router.post("/access-requests/{request_id}/verify-email", response_model=AccessRequestVerifyResponse)
async def verify_access_request_email(
    request_id: str,
    token: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestVerifyResponse:
    """Verify the employee's company email via the token from the verification email."""
    import uuid as _uuid

    from app.notifications.email_tasks import queue_access_request_admin_notification_email
    from app.domain.enums import AccessRequestRole

    service = AccessRequestService(db)
    access_request = await service.verify_email(token)

    role_label = {
        AccessRequestRole.HR_MANAGER.value: "HR Manager",
        AccessRequestRole.RECRUITER.value: "Recruiter",
    }.get(access_request.requested_role or "", access_request.requested_role or "Team Member")

    queue_access_request_admin_notification_email(
        to_email=access_request.email,
        requester_name=access_request.full_name,
        requester_email=access_request.email,
        organization_name=str(access_request.organization_id),
        role_label=role_label,
        request_id=str(access_request.id),
    )

    return AccessRequestVerifyResponse(
        status="pending_admin_approval",
        message="Your email has been verified. Your request is now pending admin approval.",
        request_id=access_request.id,
        organization_name="Organization",
    )


@router.post("/access-requests/{request_id}/resend-verification", response_model=AccessRequestResendResponse)
async def resend_verification_email(
    request_id: str,
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResendResponse:
    """Resend the verification email for a pending request."""
    import uuid as _uuid

    from app.notifications.email_tasks import queue_access_request_verification_email
    from app.domain.enums import AccessRequestRole

    service = AccessRequestService(db)
    request_obj, raw_token = await service.resend_verification(_uuid.UUID(request_id))

    role_label = {
        AccessRequestRole.HR_MANAGER.value: "HR Manager",
        AccessRequestRole.RECRUITER.value: "Recruiter",
    }.get(request_obj.requested_role or "", request_obj.requested_role or "Team Member")

    await db.commit()

    queue_access_request_verification_email(
        to_email=request_obj.email,
        full_name=request_obj.full_name,
        organization_name=str(request_obj.organization_id),
        role_label=role_label,
        raw_token=raw_token,
        request_id=str(request_obj.id),
    )

    return AccessRequestResendResponse(
        status="pending_email_verification",
        message="A new verification link has been sent to your email.",
    )


@router.get("/access-requests/{request_id}", response_model=AccessRequestPendingResponse)
async def get_access_request_status(
    request_id: str,
    db: AsyncSession = Depends(get_db),
) -> AccessRequestPendingResponse:
    """Check the status of an access request (employee, no auth required)."""
    import uuid as _uuid

    from app.core.exceptions import NotFoundError
    from app.domain.models import AccessRequest

    service = AccessRequestService(db)
    access_request = await service.repo.get(_uuid.UUID(request_id))
    if not access_request:
        raise NotFoundError(detail="Access request not found.")

    return AccessRequestPendingResponse(
        request_id=access_request.id,
        full_name=access_request.full_name,
        email=access_request.email,
        organization_name="Organization",
        status=access_request.status,
        requested_role=access_request.requested_role,
        created_at=access_request.created_at,
    )


@router.post(
    "/access-requests/activate",
    response_model=AccessRequestActivationResponse,
)
async def activate_account(
    body: AccessRequestActivate,
    db: AsyncSession = Depends(get_db),
) -> AccessRequestActivationResponse:
    """Activate the employee's account after admin approval.

    The employee clicks the activation link from their approval email, sets their
    password, and their account is created with the approved role.
    """
    service = AccessRequestService(db)
    user = await service.activate_account(token=body.token, password=body.password)

    return AccessRequestActivationResponse(
        status="activated",
        message="Your account has been activated. You can now log in.",
    )
