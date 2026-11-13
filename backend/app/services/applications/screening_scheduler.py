"""Dispatch automatic application screening.

Only the broker dispatch lives here. When no broker is reachable (typical for
dev and the test suite) screening runs inline within the SAME request session,
so the freshly created application row is visible without any cross-transaction
commit race. Inline runs are exception-isolated inside
``AutomaticScreeningService.process`` so a screening problem can never fail the
application request.
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.applications.automatic_screening_service import (
    AutomaticScreeningService,
)

logger = logging.getLogger(__name__)


def _celery_available() -> bool:
    try:
        import redis as _redis
        settings = get_settings()
        r = _redis.from_url(settings.celery_broker_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


def queue_application_screening(application_id: uuid.UUID) -> dict:
    """Dispatch a screening to Celery. Returns ``{"status": "queued" | "queue_error"}``."""
    try:
        from app.workers.tasks import screen_application

        result = screen_application.delay(str(application_id))
        logger.info(
            "Automatic screening queued: application=%s task=%s",
            application_id, result.id,
        )
        return {"status": "queued", "task_id": result.id}
    except Exception as exc:
        logger.exception("Failed to queue automatic screening: application=%s", application_id)
        return {"status": "queue_error", "task_id": None, "error": str(exc)[:500]}


async def dispatch_automatic_screening(
    session: AsyncSession, application_id: uuid.UUID,
) -> str:
    """Trigger automatic screening for a freshly created application.

    Enqueues to Celery when a broker is reachable, otherwise runs inline in the
    caller's session. Always returns the resulting screening status (or the
    current one when nothing was done).
    """
    service = AutomaticScreeningService(session)
    if _celery_available():
        dispatch = queue_application_screening(application_id)
        if dispatch.get("status") == "queued":
            await service.mark_queued(application_id, dispatch.get("task_id"))
            return "queued"
    try:
        return await service.process(application_id)
    except Exception:  # noqa: BLE001 - post-creation side effect must be safe
        logger.exception("Inline automatic screening failed: application=%s", application_id)
        return "failed"
