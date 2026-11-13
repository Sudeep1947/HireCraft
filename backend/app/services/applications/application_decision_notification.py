"""Phase 8 candidate notifications for application decisions.

Delivery is deliberately decoupled from the decision transaction:

1. The route records the decision and the request-scoped session commits it
   (status + decision history + audit) atomically.
2. Only then does the route hand the notification to
   :func:`queue_decision_notification`, which runs as a FastAPI background task
   and opens **its own** session.

That means a notification failure can never roll back or corrupt a committed
decision, and a decision can never be reported as failed just because the
candidate could not be notified.

Duplicate prevention uses the ``notifications.dedupe_key`` unique column with a
deterministic key derived from the business event
(``application_decision:<application_id>:<status>``). A retried or duplicated
submission, a replayed background task, and two concurrent dispatchers all
collapse onto the same key, so at most one notification exists per decision.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ApplicationStatus, NotificationType
from app.domain.models import Notification

logger = logging.getLogger(__name__)


def decision_dedupe_key(
    application_id: uuid.UUID, status: ApplicationStatus,
) -> str:
    """Deterministic idempotency key for one decision on one application."""
    return f"application_decision:{application_id}:{status.value}"


def _build_title(status: ApplicationStatus) -> str:
    return {
        ApplicationStatus.SHORTLISTED: "Application Shortlisted",
        # Phase 13: the positive decision. Reads as a selection, not a job offer
        # and not a hire, matching the status it is derived from.
        ApplicationStatus.SELECTED: "Application Selected",
        ApplicationStatus.HIRED: "Congratulations! You are Hired",
        ApplicationStatus.REJECTED: "Application Update",
    }.get(status, "Application Status Updated")


async def deliver_decision_notification(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    candidate_id: uuid.UUID,
    status: ApplicationStatus,
    candidate_message: str,
) -> bool:
    """Insert the decision notification in its own transaction.

    ``candidate_message`` is the approved projection produced by
    :mod:`app.domain.application_decision_schemas` and already returned to the
    recruiter by the decision endpoint, so the notification and the API response
    carry byte-identical wording. The internal recruiter note is never passed in
    here, so a notification cannot leak it.

    Returns ``True`` when a notification was created, ``False`` when it was
    suppressed as a duplicate or skipped. Never raises: notification delivery
    is best effort and must not surface as a decision failure.
    """
    dedupe_key = decision_dedupe_key(application_id, status)
    notification = Notification(
        user_id=candidate_id,
        title=_build_title(status),
        message=candidate_message,
        notification_type=NotificationType.APPLICATION_STATUS,
        dedupe_key=dedupe_key,
    )
    try:
        # A SAVEPOINT, so a unique-key collision unwinds only this insert and
        # leaves any surrounding work intact instead of poisoning it.
        async with session.begin_nested():
            session.add(notification)
            await session.flush()
        await session.commit()
    except IntegrityError:
        logger.info(
            "DECISION_NOTIFICATION_DEDUPED | application=%s status=%s",
            application_id, status.value,
        )
        return False
    except Exception:
        try:
            await session.rollback()
        except Exception:
            logger.debug("Rollback after notification failure was not possible")
        logger.warning(
            "DECISION_NOTIFICATION_FAILED | application=%s status=%s",
            application_id, status.value, exc_info=True,
        )
        return False
    logger.info(
        "DECISION_NOTIFICATION_SENT | application=%s status=%s candidate=%s",
        application_id, status.value, candidate_id,
    )
    return True


async def _deliver_with_own_session(
    application_id: uuid.UUID,
    candidate_id: uuid.UUID,
    status: ApplicationStatus,
    candidate_message: str,
) -> None:
    """Open an independent session and deliver the notification.

    Runs after the decision transaction has committed, and in its own session,
    so the decision can neither be rolled back by nor block on this write.
    """
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        await deliver_decision_notification(
            session,
            application_id=application_id,
            candidate_id=candidate_id,
            status=status,
            candidate_message=candidate_message,
        )


async def _run_notification_task(
    application_id: uuid.UUID,
    candidate_id: uuid.UUID,
    status: ApplicationStatus,
    candidate_message: str,
) -> None:
    """Scheduled task body: contains every failure mode.

    The containment lives here, at the scheduling boundary, so that any error
    raised by the delivery path — including a future change to it — is logged
    and swallowed instead of escaping into the background task runner. The
    recruiter who already committed the decision must never see a failure
    caused by notification delivery.
    """
    try:
        await _deliver_with_own_session(
            application_id, candidate_id, status, candidate_message,
        )
    except Exception:
        logger.warning(
            "DECISION_NOTIFICATION_TASK_FAILED | application=%s status=%s",
            application_id, status.value, exc_info=True,
        )


def queue_decision_notification(
    background_tasks: BackgroundTasks | None,
    *,
    application_id: uuid.UUID,
    candidate_id: uuid.UUID,
    status: ApplicationStatus,
    candidate_message: str,
) -> None:
    """Schedule the notification for after the decision transaction commits.

    If the caller cannot supply background tasks the notification is skipped
    rather than being written inside the decision transaction, which keeps the
    "a notification can never corrupt a decision" guarantee intact.
    """
    if background_tasks is None:
        logger.info(
            "DECISION_NOTIFICATION_DEFERRED | application=%s status=%s",
            application_id, status.value,
        )
        return
    background_tasks.add_task(
        _run_notification_task,
        application_id,
        candidate_id,
        status,
        candidate_message,
    )
