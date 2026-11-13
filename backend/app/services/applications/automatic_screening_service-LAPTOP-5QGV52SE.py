"""Automatic application screening worker (Phase 3).

Orchestrates the *execution state* of an automatic screening run while
delegating every score to the existing Phase 2 ``ApplicationScreeningService``
(which in turn uses the Phase 1 matching engine). This module adds no second
screening engine.

Guarantees:
- Idempotent: a run is claimed with a compare-and-swap on
  ``JobApplication.screening_status``; a completed or in-flight run is a no-op.
- Bounded and non-fatal: failures are recorded on the application as ``FAILED``
  (with the reason) and never roll back application creation. A savepoint keeps
  the surrounding transaction usable if the engine raises mid-write.
- No lifecycle change: screening never rejects/shortlists/hires anyone.
- Auditable: system runs write an ``application_screened`` audit entry with
  ``user_id=None`` and an ``actor=system`` marker; failures write an
  ``application_screening_failed`` entry.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import AuditEventType, ScreeningStatus
from app.repositories.jobs.job import JobApplicationRepository
from app.services.applications.application_screening_service import (
    ApplicationScreeningService,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Statuses a worker is allowed to (re)claim. ``FAILED`` is claimable so a
# bounded Celery retry can re-run a transient failure; ``COMPLETED`` and
# ``RUNNING`` are not, which makes concurrent claims idempotent.
_CLAIMABLE = [
    ScreeningStatus.NOT_STARTED.value,
    ScreeningStatus.QUEUED.value,
    ScreeningStatus.FAILED.value,
]


class AutomaticScreeningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.application_repo = JobApplicationRepository(session)
        self.audit_service = AuditService(session)

    async def mark_queued(
        self, application_id: uuid.UUID, task_id: str | None = None,
    ) -> None:
        await self.application_repo.set_screening_queued(application_id, task_id)

    async def process(self, application_id: uuid.UUID) -> str:
        """Run (or re-run) the automatic screening. Returns the resulting status.

        Never raises for expected screening problems: the outcome is always
        persisted on the application so the caller (request or worker) can
        continue safely.
        """
        now = datetime.now(timezone.utc)
        claimed = await self.application_repo.claim_screening(
            application_id, expected_statuses=_CLAIMABLE, started_at=now,
        )
        if claimed is None:
            app = await self.application_repo.get(application_id)
            status = app.screening_status if app else "missing"
            logger.info(
                "Automatic screening skipped (not claimable): application=%s status=%s",
                application_id, status,
            )
            return status

        try:
            async with self.session.begin_nested():
                await ApplicationScreeningService(
                    self.session,
                ).screen_application_system(application_id)
        except ConflictError:
            # Application was finalized before the worker ran — nothing to do.
            await self._finish(application_id, ScreeningStatus.SKIPPED, "Application finalized")
            return ScreeningStatus.SKIPPED.value
        except (ValidationError, ValueError, NotFoundError) as exc:
            await self._fail(application_id, str(exc))
            return ScreeningStatus.FAILED.value
        except Exception as exc:  # noqa: BLE001 - record, never propagate
            logger.exception("Automatic screening crashed: application=%s", application_id)
            await self._fail(application_id, str(exc))
            return ScreeningStatus.FAILED.value

        await self._finish(application_id, ScreeningStatus.COMPLETED)
        logger.info("Automatic screening completed: application=%s", application_id)
        return ScreeningStatus.COMPLETED.value

    async def _finish(
        self,
        application_id: uuid.UUID,
        status: ScreeningStatus,
        error: str | None = None,
    ) -> None:
        await self.application_repo.finish_screening(
            application_id, status, datetime.now(timezone.utc), error=error,
        )

    async def _fail(self, application_id: uuid.UUID, error: str) -> None:
        truncated = (error or "")[:1000]
        await self._finish(application_id, ScreeningStatus.FAILED, truncated)
        await self.audit_service.log(
            event_type=AuditEventType.APPLICATION_SCREENING_FAILED,
            action="application_screening_failed",
            user_id=None,
            resource_type="job_application",
            resource_id=str(application_id),
            details={"error": truncated, "trigger": "automatic", "actor": "system"},
            success=False,
        )
