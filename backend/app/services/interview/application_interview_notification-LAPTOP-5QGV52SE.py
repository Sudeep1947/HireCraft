"""Phase 11 candidate notifications for interview lifecycle events.

Follows the exact delivery contract established by
:mod:`app.services.applications.application_decision_notification`, because
interview notifications have the same two hard requirements:

1. **Never corrupt the business transaction.** The route commits the interview
   change (and the application status flip) in the request transaction, then
   hands the notification to :func:`queue_interview_notification`, which runs as
   a FastAPI background task on **its own** session. A notification failure can
   therefore neither roll back a committed schedule nor make a successful
   schedule look failed.

2. **Exactly one notification per event.** Duplicate prevention uses the
   existing ``notifications.dedupe_key`` unique column with a deterministic key
   derived from the business event
   (``interview:<interview_id>:<event>``). A retried request, a replayed
   background task and two concurrent dispatchers all collapse onto one key.

Interview events use their own ``NotificationType`` values rather than
``APPLICATION_STATUS`` so a candidate can distinguish "your interview moved"
from "your application was decided", even though scheduling also flips the
application status.

The recruiter's internal cancellation ``reason`` is never passed in here -- only
the approved candidate projection -- so a private note cannot leak through a
notification.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotificationType
from app.domain.models import Notification

logger = logging.getLogger(__name__)

# The four events a candidate is told about. Kept explicit rather than derived
# from the enum so a newly added enum member cannot silently start producing
# candidate notifications with no reviewed wording.
InterviewEvent = Literal["scheduled", "rescheduled", "cancelled", "completed"]

_EVENT_CONFIG: dict[str, tuple[NotificationType, str]] = {
    "scheduled": (NotificationType.INTERVIEW_SCHEDULED, "Interview Scheduled"),
    "rescheduled": (
        NotificationType.INTERVIEW_RESCHEDULED, "Interview Rescheduled",
    ),
    "cancelled": (NotificationType.INTERVIEW_CANCELLED, "Interview Cancelled"),
    "completed": (NotificationType.INTERVIEW_COMPLETED, "Interview Completed"),
}


def interview_dedupe_key(interview_id: uuid.UUID, event: InterviewEvent) -> str:
    """Deterministic idempotency key for one interview event.

    Keyed on the interview, not the application, so a second interview on the
    same application produces its own notification instead of being suppressed
    as a duplicate of the first.
    """
    return f"interview:{interview_id}:{event}"


async def deliver_interview_notification(
    session: AsyncSession,
    *,
    interview_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: InterviewEvent,
    candidate_message: str,
) -> bool:
    """Insert the interview notification in its own transaction.

    ``candidate_message`` is the approved projection from
    :mod:`app.domain.application_interview_schemas` and is byte-identical to
    what the API returned to the recruiter, so the notification and the UI can
    never disagree.

    Returns ``True`` when a notification was created, ``False`` when suppressed
    as a duplicate or skipped. Never raises: delivery is best effort.
    """
    config = _EVENT_CONFIG.get(event)
    if config is None:
        logger.warning(
            "INTERVIEW_NOTIFICATION_UNKNOWN_EVENT | interview=%s event=%s",
            interview_id, event,
        )
        return False
    notification_type, title = config

    dedupe_key = interview_dedupe_key(interview_id, event)
    notification = Notification(
        user_id=candidate_id,
        title=title,
        message=candidate_message,
        notification_type=notification_type,
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
            "INTERVIEW_NOTIFICATION_DEDUPED | interview=%s event=%s",
            interview_id, event,
        )
        return False
    except Exception:
        try:
            await session.rollback()
        except Exception:
            logger.debug("Rollback after notification failure was not possible")
        logger.warning(
            "INTERVIEW_NOTIFICATION_FAILED | interview=%s event=%s",
            interview_id, event, exc_info=True,
        )
        return False
    logger.info(
        "INTERVIEW_NOTIFICATION_SENT | interview=%s event=%s candidate=%s",
        interview_id, event, candidate_id,
    )
    return True


async def _deliver_with_own_session(
    interview_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: InterviewEvent,
    candidate_message: str,
) -> None:
    """Open an independent session and deliver the notification.

    Runs after the interview transaction has committed, and in its own session,
    so the interview change can neither be rolled back by nor block on this
    write.
    """
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        await deliver_interview_notification(
            session,
            interview_id=interview_id,
            candidate_id=candidate_id,
            event=event,
            candidate_message=candidate_message,
        )


async def _run_notification_task(
    interview_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: InterviewEvent,
    candidate_message: str,
) -> None:
    """Scheduled task body: contains every failure mode.

    The containment lives here, at the scheduling boundary, so any error raised
    by the delivery path is logged and swallowed instead of escaping into the
    background task runner. The recruiter who already committed the change must
    never see a failure caused by notification delivery.
    """
    try:
        await _deliver_with_own_session(
            interview_id, candidate_id, event, candidate_message,
        )
    except Exception:
        logger.warning(
            "INTERVIEW_NOTIFICATION_TASK_FAILED | interview=%s event=%s",
            interview_id, event, exc_info=True,
        )


def queue_interview_notification(
    background_tasks: BackgroundTasks | None,
    *,
    interview_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: InterviewEvent,
    candidate_message: str,
) -> None:
    """Schedule the notification for after the interview transaction commits.

    If the caller cannot supply background tasks the notification is skipped
    rather than being written inside the business transaction, which keeps the
    "a notification can never corrupt a schedule" guarantee intact.
    """
    if background_tasks is None:
        logger.info(
            "INTERVIEW_NOTIFICATION_DEFERRED | interview=%s event=%s",
            interview_id, event,
        )
        return
    background_tasks.add_task(
        _run_notification_task,
        interview_id,
        candidate_id,
        event,
        candidate_message,
    )
