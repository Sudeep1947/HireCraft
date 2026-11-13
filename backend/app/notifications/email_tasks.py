"""Notification helpers for firing Celery email tasks."""
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ROLE_LABELS = {
    "hr_manager": "HR Manager",
    "organization_admin": "Organization Admin",
    "recruiter": "Recruiter",
    "candidate": "Candidate",
    "super_admin": "Super Admin",
    "admin": "Platform Admin",
}


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


def _send_sync(template_name: str, to_email: str, subject: str, **context: str) -> dict:
    from app.services.email_service import EmailService
    email_svc = EmailService()
    html_body = email_svc.render_template(template_name, **context)
    return email_svc.send_html(to_email=to_email, subject=subject, html_body=html_body)


# ── Invitation emails (existing) ──────────────────────────────────


def _send_invitation_email_sync(
    to_email: str,
    invited_by_name: str,
    organization_name: str,
    role_label: str,
    accept_url: str,
    expires_at_str: str,
    app_name: str,
) -> dict:
    return _send_sync(
        "invitation_email.html",
        to_email=to_email,
        subject=f"You've been invited to join {organization_name}",
        invited_by_name=invited_by_name,
        organization_name=organization_name,
        role_label=role_label,
        accept_url=accept_url,
        expires_at=expires_at_str,
        app_name=app_name,
    )


def queue_invitation_email(
    to_email: str,
    invited_by_name: str,
    organization_name: str,
    role: str,
    raw_token: str,
    expires_at_str: str,
) -> dict:
    settings = get_settings()
    accept_url = settings.frontend_url(f"/invite/{raw_token}")
    role_label = ROLE_LABELS.get(role, role)
    app_name = settings.app_name

    if not _celery_available():
        logger.info(
            "Celery broker unavailable — sending invitation email synchronously (to=%s, org=%s)",
            to_email,
            organization_name,
        )
        try:
            result = _send_invitation_email_sync(
                to_email=to_email,
                invited_by_name=invited_by_name,
                organization_name=organization_name,
                role_label=role_label,
                accept_url=accept_url,
                expires_at_str=expires_at_str,
                app_name=app_name,
            )
            return {
                "status": result.get("status", "sent"),
                "reason": result.get("reason"),
            }
        except Exception:
            logger.exception("Synchronous invitation email failed for %s", to_email)
            return {"status": "error", "reason": "sync_send_failed"}

    try:
        from app.workers.tasks import send_invitation_email

        result = send_invitation_email.delay(
            to_email=to_email,
            invited_by_name=invited_by_name,
            organization_name=organization_name,
            role_label=role_label,
            accept_url=accept_url,
            expires_at=expires_at_str,
            app_name=app_name,
        )
        logger.info(
            "Invitation email queued: to=%s task_id=%s",
            to_email,
            result.id,
        )
        return {"status": "queued", "task_id": result.id}
    except Exception:
        logger.exception("Failed to queue invitation email to %s", to_email)
        return {"status": "queue_error"}


# ── Access request emails ──────────────────────────────────────────


def queue_access_request_verification_email(
    to_email: str,
    full_name: str,
    organization_name: str,
    role_label: str,
    raw_token: str,
    request_id: str,
) -> dict:
    settings = get_settings()
    verify_url = settings.frontend_url(f"/verify-email?token={raw_token}&request_id={request_id}")
    app_name = settings.app_name

    if not _celery_available():
        try:
            result = _send_sync(
                "access_request_verification_email.html",
                to_email=to_email,
                subject=f"Verify your email to join {organization_name}",
                full_name=full_name,
                organization_name=organization_name,
                role_label=role_label,
                verify_url=verify_url,
                expires_in="24 hours",
                app_name=app_name,
            )
            return {"status": result.get("status", "sent")}
        except Exception:
            logger.exception("Sync verification email failed for %s", to_email)
            return {"status": "error", "reason": "sync_send_failed"}

    try:
        from app.workers.tasks import send_access_request_verification_email
        result = send_access_request_verification_email.delay(
            to_email=to_email,
            full_name=full_name,
            organization_name=organization_name,
            role_label=role_label,
            verify_url=verify_url,
            expires_in="24 hours",
            app_name=app_name,
        )
        logger.info("Verification email queued: to=%s task_id=%s", to_email, result.id)
        return {"status": "queued", "task_id": result.id}
    except Exception:
        logger.exception("Failed to queue verification email to %s", to_email)
        return {"status": "queue_error"}


def queue_access_request_admin_notification_email(
    to_email: str,
    requester_name: str,
    requester_email: str,
    organization_name: str,
    role_label: str,
    request_id: str,
) -> dict:
    settings = get_settings()
    admin_url = settings.frontend_url("/admin/access-requests")
    app_name = settings.app_name

    if not _celery_available():
        try:
            result = _send_sync(
                "access_request_admin_notification_email.html",
                to_email=to_email,
                subject=f"New access request from {requester_name}",
                requester_name=requester_name,
                requester_email=requester_email,
                organization_name=organization_name,
                role_label=role_label,
                admin_url=admin_url,
                request_id=str(request_id),
                app_name=app_name,
            )
            return {"status": result.get("status", "sent")}
        except Exception:
            logger.exception("Sync admin notification email failed for %s", to_email)
            return {"status": "error", "reason": "sync_send_failed"}

    try:
        from app.workers.tasks import send_access_request_admin_notification_email
        result = send_access_request_admin_notification_email.delay(
            to_email=to_email,
            requester_name=requester_name,
            requester_email=requester_email,
            organization_name=organization_name,
            role_label=role_label,
            admin_url=admin_url,
            request_id=str(request_id),
            app_name=app_name,
        )
        logger.info("Admin notification email queued: to=%s task_id=%s", to_email, result.id)
        return {"status": "queued", "task_id": result.id}
    except Exception:
        logger.exception("Failed to queue admin notification email to %s", to_email)
        return {"status": "queue_error"}


def queue_access_request_approved_email(
    to_email: str,
    full_name: str,
    organization_name: str,
    role_label: str,
    raw_activation_token: str,
    request_id: str,
) -> dict:
    settings = get_settings()
    activate_url = settings.frontend_url(f"/activate?token={raw_activation_token}&request_id={request_id}")
    app_name = settings.app_name

    if not _celery_available():
        try:
            result = _send_sync(
                "access_request_approved_email.html",
                to_email=to_email,
                subject=f"Your access request for {organization_name} has been approved",
                full_name=full_name,
                organization_name=organization_name,
                role_label=role_label,
                activate_url=activate_url,
                expires_in="7 days",
                app_name=app_name,
            )
            return {"status": result.get("status", "sent")}
        except Exception:
            logger.exception("Sync approved email failed for %s", to_email)
            return {"status": "error", "reason": "sync_send_failed"}

    try:
        from app.workers.tasks import send_access_request_approved_email
        result = send_access_request_approved_email.delay(
            to_email=to_email,
            full_name=full_name,
            organization_name=organization_name,
            role_label=role_label,
            activate_url=activate_url,
            expires_in="7 days",
            app_name=app_name,
        )
        logger.info("Approved email queued: to=%s task_id=%s", to_email, result.id)
        return {"status": "queued", "task_id": result.id}
    except Exception:
        logger.exception("Failed to queue approved email to %s", to_email)
        return {"status": "queue_error"}


def queue_access_request_rejected_email(
    to_email: str,
    full_name: str,
    organization_name: str,
    role_label: str,
    reason: str | None = None,
) -> dict:
    settings = get_settings()
    app_name = settings.app_name

    if not _celery_available():
        try:
            result = _send_sync(
                "access_request_rejected_email.html",
                to_email=to_email,
                subject=f"Your access request for {organization_name}",
                full_name=full_name,
                organization_name=organization_name,
                role_label=role_label,
                reason=reason or "",
                app_name=app_name,
            )
            return {"status": result.get("status", "sent")}
        except Exception:
            logger.exception("Sync rejected email failed for %s", to_email)
            return {"status": "error", "reason": "sync_send_failed"}

    try:
        from app.workers.tasks import send_access_request_rejected_email
        result = send_access_request_rejected_email.delay(
            to_email=to_email,
            full_name=full_name,
            organization_name=organization_name,
            role_label=role_label,
            reason=reason or "",
            app_name=app_name,
        )
        logger.info("Rejected email queued: to=%s task_id=%s", to_email, result.id)
        return {"status": "queued", "task_id": result.id}
    except Exception:
        logger.exception("Failed to queue rejected email to %s", to_email)
        return {"status": "queue_error"}
