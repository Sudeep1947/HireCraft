"""Phase 12 candidate notifications for assessment lifecycle events.

Follows the exact delivery contract established by
:mod:`app.services.interview.application_interview_notification`, because
assessment notifications have the same two hard requirements:

1. **Never corrupt the business transaction.** The route commits the assignment
   (or the candidate's submission) in the request transaction, then hands the
   notification to :func:`queue_assessment_notification`, which runs as a FastAPI
   background task on **its own** session. A notification failure can therefore
   neither roll back a committed assignment nor make a successful one look
   failed.

2. **Exactly one notification per event.** Duplicate prevention uses the existing
   ``notifications.dedupe_key`` unique column with a deterministic key derived
   from the business event (``assessment:<attempt_id>:<event>``). A retried
   request, a replayed background task and two concurrent dispatchers all
   collapse onto one key.

The key is derived from the *attempt*, not the application and not the
assessment, because the same assessment can be assigned to one candidate more
than once (``allowed_attempts`` permits retakes) and two candidates can be
assigned the same assessment. Keying on either of those would silently suppress a
legitimate second notification.

Wording never implies a hiring outcome. An assigned assessment says the
candidate has an assessment to complete; a completed one says the result is
available. Neither says the candidate passed, failed, was selected or was
rejected -- the recruiter owns that decision, and a notification that implied it
would be a decision made by a background task.

No new email path is introduced. The platform's existing in-app
``Notification`` plus the Phase 10/11 delivery contract is the whole
architecture; the decision and interview phases send no email either, so adding
one only for assessments would create a third, inconsistent channel.
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

# The events a candidate is told about. Kept explicit rather than derived from
# the enum so a newly added enum member cannot silently start producing candidate
# notifications with no reviewed wording.
AssessmentEvent = Literal["assigned", "rescheduled", "completed"]

_EVENT_CONFIG: dict[str, tuple[NotificationType, str]] = {
    "assigned": (NotificationType.ASSESSMENT_ASSIGNED, "Assessment Scheduled"),
    # Its own type, and its own dedupe key. Reusing "assigned" would make a
    # reschedule collide with the original assignment of the same attempt and be
    # silently dropped as a duplicate -- so the candidate would be moved to a new
    # time without ever being told.
    "rescheduled": (
        NotificationType.ASSESSMENT_RESCHEDULED, "Assessment Rescheduled",
    ),
    "completed": (
        NotificationType.ASSESSMENT_COMPLETED, "Assessment Completed",
    ),
}


def assessment_dedupe_key(attempt_id: uuid.UUID, event: AssessmentEvent) -> str:
    """Deterministic idempotency key for one assessment event.

    Keyed on the attempt, so a retake of the same assessment by the same
    candidate is a distinct event with its own notification rather than being
    suppressed as a duplicate of the first attempt.
    """
    return f"assessment:{attempt_id}:{event}"


async def deliver_assessment_notification(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: AssessmentEvent,
    candidate_message: str,
    action_link: str | None = None,
) -> bool:
    """Insert the assessment notification in its own transaction.

    ``candidate_message`` is the approved candidate projection built by
    :mod:`app.services.assessment.application_assessment_service` and is
    byte-identical to what the API returned, so the notification and the UI can
    never disagree.

    ``action_link`` is where this notification's action goes, stored on the row so
    the candidate's notification page navigates to *this* assessment instead of
    inferring a destination from the notification type. It is a link the server
    issued for this candidate's own attempt, not an id supplied by a caller, so it
    cannot point at another candidate's assessment; the candidate-facing route it
    names still resolves the attempt server-side against the logged-in candidate,
    so a stale or hand-edited link reaches nothing.

    Returns ``True`` when a notification was created, ``False`` when suppressed
    as a duplicate or skipped. Never raises: delivery is best effort.
    """
    config = _EVENT_CONFIG.get(event)
    if config is None:
        logger.warning(
            "ASSESSMENT_NOTIFICATION_UNKNOWN_EVENT | attempt=%s event=%s",
            attempt_id, event,
        )
        return False
    notification_type, title = config

    dedupe_key = assessment_dedupe_key(attempt_id, event)
    notification = Notification(
        user_id=candidate_id,
        title=title,
        message=candidate_message,
        notification_type=notification_type,
        dedupe_key=dedupe_key,
        action_link=action_link,
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
            "ASSESSMENT_NOTIFICATION_DEDUPED | attempt=%s event=%s",
            attempt_id, event,
        )
        return False
    except Exception:
        try:
            await session.rollback()
        except Exception:
            logger.debug("Rollback after notification failure was not possible")
        logger.warning(
            "ASSESSMENT_NOTIFICATION_FAILED | attempt=%s event=%s",
            attempt_id, event, exc_info=True,
        )
        return False
    logger.info(
        "ASSESSMENT_NOTIFICATION_SENT | attempt=%s event=%s candidate=%s",
        attempt_id, event, candidate_id,
    )
    return True


async def _deliver_with_own_session(
    attempt_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: AssessmentEvent,
    candidate_message: str,
    action_link: str | None,
) -> None:
    """Open an independent session and deliver the notification.

    Runs after the business transaction has committed, and in its own session, so
    the assignment can neither be rolled back by nor block on this write.
    """
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        await deliver_assessment_notification(
            session,
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            event=event,
            candidate_message=candidate_message,
            action_link=action_link,
        )


async def _run_notification_task(
    attempt_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: AssessmentEvent,
    candidate_message: str,
    action_link: str | None,
) -> None:
    """Scheduled task body: contains every failure mode.

    The containment lives here, at the scheduling boundary, so any error raised by
    the delivery path is logged and swallowed instead of escaping into the
    background task runner. The recruiter who already committed the assignment
    must never see a failure caused by notification delivery.
    """
    try:
        await _deliver_with_own_session(
            attempt_id, candidate_id, event, candidate_message, action_link,
        )
    except Exception:
        logger.warning(
            "ASSESSMENT_NOTIFICATION_TASK_FAILED | attempt=%s event=%s",
            attempt_id, event, exc_info=True,
        )


def queue_assessment_notification(
    background_tasks: BackgroundTasks | None,
    *,
    attempt_id: uuid.UUID,
    candidate_id: uuid.UUID,
    event: AssessmentEvent,
    candidate_message: str,
    action_link: str | None = None,
) -> None:
    """Schedule the notification for after the transaction commits.

    If the caller cannot supply background tasks the notification is skipped
    rather than being written inside the business transaction, which keeps the
    "a notification can never corrupt an assignment" guarantee intact.
    """
    if background_tasks is None:
        logger.info(
            "ASSESSMENT_NOTIFICATION_DEFERRED | attempt=%s event=%s",
            attempt_id, event,
        )
        return
    background_tasks.add_task(
        _run_notification_task,
        attempt_id,
        candidate_id,
        event,
        candidate_message,
        action_link,
    )
