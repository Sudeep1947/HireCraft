"""Repository for employee access requests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.core.logging import get_logger
from app.repositories.base import BaseRepository
from app.domain.enums import AccessRequestStatus
from app.domain.models import AccessRequest

logger = get_logger(__name__)


class AccessRequestRepository(BaseRepository[AccessRequest]):
    def __init__(self, session):
        super().__init__(session, AccessRequest)

    async def get_by_verification_token_hash(self, token_hash: str) -> AccessRequest | None:
        result = await self._session.execute(
            select(AccessRequest).where(AccessRequest.verification_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_activation_token_hash(self, token_hash: str) -> AccessRequest | None:
        result = await self._session.execute(
            select(AccessRequest).where(AccessRequest.activation_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_active_by_email_and_org(self, email: str, org_id: uuid.UUID) -> AccessRequest | None:
        """Get a non-terminal access request for this email+org combination."""
        result = await self._session.execute(
            select(AccessRequest).where(
                AccessRequest.email == email.lower().strip(),
                AccessRequest.organization_id == org_id,
                AccessRequest.status.notin_(AccessRequestStatus.terminal()),
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_by_email_and_org(self, email: str, org_id: uuid.UUID) -> AccessRequest | None:
        """Get a request pending admin approval for this email+org."""
        result = await self._session.execute(
            select(AccessRequest).where(
                AccessRequest.email == email.lower().strip(),
                AccessRequest.organization_id == org_id,
                AccessRequest.status == AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_org(self, request_id: uuid.UUID, org_id: uuid.UUID) -> AccessRequest | None:
        result = await self._session.execute(
            select(AccessRequest).where(
                AccessRequest.id == request_id,
                AccessRequest.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        status: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[AccessRequest], int]:
        query = select(AccessRequest).where(AccessRequest.organization_id == org_id)
        count_query = select(func.count()).select_from(AccessRequest).where(AccessRequest.organization_id == org_id)

        if status:
            query = query.where(AccessRequest.status == status)
            count_query = count_query.where(AccessRequest.status == status)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(AccessRequest.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def update_status(self, request_id: uuid.UUID, status: AccessRequestStatus) -> bool:
        result = await self._session.execute(
            update(AccessRequest)
            .where(AccessRequest.id == request_id)
            .values(status=status.value)
        )
        return result.rowcount > 0

    async def set_verified(self, request_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.id == request_id,
                AccessRequest.status == AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
            )
            .values(
                status=AccessRequestStatus.EMAIL_VERIFIED.value,
                email_verified_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount > 0

    async def set_approved(self, request_id: uuid.UUID, approved_role: str, reviewed_by_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.id == request_id,
                AccessRequest.status == AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            )
            .values(
                status=AccessRequestStatus.APPROVED.value,
                approved_role=approved_role,
                reviewed_by_id=reviewed_by_id,
                reviewed_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount > 0

    async def set_rejected(self, request_id: uuid.UUID, reviewed_by_id: uuid.UUID, reason: str | None = None) -> bool:
        result = await self._session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.id == request_id,
                AccessRequest.status == AccessRequestStatus.PENDING_ADMIN_APPROVAL.value,
            )
            .values(
                status=AccessRequestStatus.REJECTED.value,
                reviewed_by_id=reviewed_by_id,
                reviewed_at=datetime.now(timezone.utc),
                rejection_reason=reason,
            )
        )
        return result.rowcount > 0

    async def set_activation_pending(self, request_id: uuid.UUID, activation_token_hash: str, expires_at: datetime) -> bool:
        result = await self._session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.id == request_id,
                AccessRequest.status == AccessRequestStatus.APPROVED.value,
            )
            .values(
                status=AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
                activation_token_hash=activation_token_hash,
                activation_expires_at=expires_at,
            )
        )
        return result.rowcount > 0

    async def set_activated(self, request_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(AccessRequest)
            .where(AccessRequest.id == request_id)
            .values(
                status=AccessRequestStatus.ACTIVATED.value,
                activated_at=datetime.now(timezone.utc),
                created_user_id=user_id,
            )
        )
        return result.rowcount > 0

    async def expire_stale_requests(self) -> int:
        """Expire requests past their verification or activation deadline."""
        now = datetime.now(timezone.utc)
        # Expire unverified requests (24h window)
        result1 = await self._session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.status == AccessRequestStatus.PENDING_EMAIL_VERIFICATION.value,
                AccessRequest.verification_expires_at < now,
            )
            .values(status=AccessRequestStatus.EXPIRED.value)
        )
        # Expire unactivated approval requests (7-day window)
        result2 = await self._session.execute(
            update(AccessRequest)
            .where(
                AccessRequest.status == AccessRequestStatus.ACCOUNT_ACTIVATION_PENDING.value,
                AccessRequest.activation_expires_at < now,
            )
            .values(status=AccessRequestStatus.EXPIRED.value)
        )
        return result1.rowcount + result2.rowcount
