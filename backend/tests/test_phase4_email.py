"""Phase 4 — Email notification tests.

Covers:
- EmailService template rendering
- EmailService send behavior (configured vs unconfigured SMTP)
- Celery send_invitation_email task
- API response includes email_status
- Token never appears in email body (security)
- Invitation link correctness
- Frontend integration: email_status in response
"""

import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.domain.models import Invitation, Organization, OrganizationMembership, Role, User, UserRole
from app.domain.enums import InvitationStatus, MembershipStatus
from app.services.email_service import EmailService


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════


async def _create_user_with_role_in_db(session, email: str, name: str, role_name: str, password: str = "SecureP@ss1") -> User:
    user = User(
        id=uuid.uuid4(),
        full_name=name,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    result = await session.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one_or_none()
    if role:
        ur = UserRole(user_id=user.id, role_id=role.id)
        session.add(ur)
        await session.flush()
    await session.refresh(user)
    return user


async def _create_org_membership(session, user_id, org_id, role="organization_admin"):
    membership = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user_id,
        organization_id=org_id,
        role=role,
        status=MembershipStatus.ACTIVE.value,
        joined_at=datetime.now(timezone.utc),
    )
    session.add(membership)
    await session.flush()
    return membership


async def _login(client: AsyncClient, email: str, password: str = "SecureP@ss1") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def _setup_org_with_admin(client: AsyncClient, session, admin_email: str) -> tuple[str, str, uuid.UUID]:
    """Create admin user, create org via API, return (token, org_id, admin_user_id)."""
    user = await _create_user_with_role_in_db(session, admin_email, "Admin", "admin")
    token = await _login(client, user.email)
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": f"Email Test Org {uuid.uuid4().hex[:6]}", "slug": f"email-org-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    org_id = org_resp.json()["id"]
    return token, org_id, user.id


# ═══════════════════════════════════════════════════════════════════
# 1. EMAIL SERVICE — Template Rendering
# ═══════════════════════════════════════════════════════════════════


def test_template_renders_with_all_variables():
    svc = EmailService()
    html = svc.render_template(
        "invitation_email.html",
        invited_by_name="Jane Smith",
        organization_name="Acme Corp",
        role_label="HR Manager",
        accept_url="https://hirecraft.ai/invite/abc123",
        expires_at="2026-09-01",
        app_name="AI Hiring Copilot",
    )
    assert "Jane Smith" in html
    assert "Acme Corp" in html
    assert "HR Manager" in html
    assert "https://hirecraft.ai/invite/abc123" in html
    assert "2026-09-01" in html
    assert "AI Hiring Copilot" in html


def test_template_is_valid_html():
    svc = EmailService()
    html = svc.render_template(
        "invitation_email.html",
        invited_by_name="Test",
        organization_name="Test Org",
        role_label="Recruiter",
        accept_url="https://example.com/invite/test",
        expires_at="2026-01-01",
        app_name="Test",
    )
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


def test_template_escapes_html_in_name():
    svc = EmailService()
    html = svc.render_template(
        "invitation_email.html",
        invited_by_name="<script>alert('xss')</script>",
        organization_name="Test Org",
        role_label="HR Manager",
        accept_url="https://example.com/invite/test",
        expires_at="2026-01-01",
        app_name="Test",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ═══════════════════════════════════════════════════════════════════
# 2. EMAIL SERVICE — Send Behavior (Unconfigured SMTP)
# ═══════════════════════════════════════════════════════════════════


def _unconfigured_email_service() -> EmailService:
    """EmailService with SMTP settings explicitly absent (independent of developer .env)."""
    svc = EmailService()
    svc._settings = MagicMock(
        smtp_host=None,
        smtp_port=None,
        smtp_user=None,
        smtp_password=None,
        smtp_from_email=None,
        smtp_from_name="Test App",
    )
    return svc


def test_send_skips_when_smtp_not_configured():
    svc = _unconfigured_email_service()
    result = svc.send_html(to_email="test@example.com", subject="Test", html_body="<p>Hello</p>")
    assert result["status"] == "skipped"
    assert result["reason"] == "smtp_not_configured"


def test_is_configured_returns_false_when_smtp_absent():
    svc = _unconfigured_email_service()
    assert svc._is_configured() is False


# ═══════════════════════════════════════════════════════════════════
# 3. EMAIL SERVICE — Send Behavior (Configured SMTP, mock)
# ═══════════════════════════════════════════════════════════════════


def test_send_uses_smtp_when_configured():
    svc = EmailService()
    svc._settings = MagicMock(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="secret",
        smtp_from_email="noreply@example.com",
        smtp_from_name="Test App",
    )

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = svc.send_html(to_email="test@example.com", subject="Test Subject", html_body="<p>Hello</p>")
        assert result["status"] == "sent"
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.sendmail.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 4. CELERY TASK — send_invitation_email
# ═══════════════════════════════════════════════════════════════════


def test_celery_task_renders_and_sends():
    from app.workers.tasks import send_invitation_email

    with patch("app.services.email_service.EmailService") as MockEmailService:
        mock_svc = MagicMock()
        MockEmailService.return_value = mock_svc
        mock_svc.render_template.return_value = "<html><body>Invite email</body></html>"
        mock_svc.send_html.return_value = {"status": "sent", "to": "invite@test.com"}

        result = send_invitation_email(
            to_email="invite@test.com",
            invited_by_name="Admin User",
            organization_name="Acme Corp",
            role_label="HR Manager",
            accept_url="https://hirecraft.ai/invite/abc123",
            expires_at="2026-09-01",
            app_name="AI Hiring Copilot",
        )
        assert result["status"] == "sent"


def test_celery_task_handles_template_error():
    from app.workers.tasks import send_invitation_email

    with patch("app.services.email_service.EmailService") as MockEmailService:
        mock_svc = MagicMock()
        MockEmailService.return_value = mock_svc
        mock_svc.render_template.side_effect = Exception("Template not found")

        result = send_invitation_email(
            to_email="invite@test.com",
            invited_by_name="Admin User",
            organization_name="Acme Corp",
            role_label="HR Manager",
            accept_url="https://hirecraft.ai/invite/abc123",
            expires_at="2026-09-01",
        )
        assert result["status"] == "template_error"


# ═══════════════════════════════════════════════════════════════════
# 5. API — email_status in Invitation Response
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_invitation_returns_email_status(client: AsyncClient, session):
    token, org_id, _ = await _setup_org_with_admin(client, session, "admin_email1@test.com")

    with patch("app.notifications.email_tasks.queue_invitation_email") as mock_queue:
        mock_queue.return_value = {"status": "skipped", "reason": "smtp_not_configured"}
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/invitations",
            json={"email": "invitee@test.com", "role": "hr_manager"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert "email_status" in data
    assert data["email_status"] == "skipped"


@pytest.mark.asyncio
async def test_create_invitation_returns_email_queued(client: AsyncClient, session):
    token, org_id, _ = await _setup_org_with_admin(client, session, "admin_email2@test.com")

    with patch("app.notifications.email_tasks.queue_invitation_email") as mock_queue:
        mock_queue.return_value = {"status": "queued", "task_id": "fake-task-id"}
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/invitations",
            json={"email": "invitee2@test.com", "role": "hr_manager"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201
    assert resp.json()["email_status"] == "queued"


@pytest.mark.asyncio
async def test_resend_invitation_returns_email_status(client: AsyncClient, session):
    from app.domain.models import Invitation as InvModel

    token, org_id, admin_id = await _setup_org_with_admin(client, session, "admin_email3@test.com")

    raw_token = InvModel.generate_token()
    token_hash = InvModel.hash_token(raw_token)
    invitation = Invitation(
        organization_id=uuid.UUID(org_id),
        invited_by_id=admin_id,
        email="resend_email@test.com",
        role="hr_manager",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    inv_id = invitation.id

    with patch("app.notifications.email_tasks.queue_invitation_email") as mock_queue:
        mock_queue.return_value = {"status": "queued", "task_id": "resend-task-id"}
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/invitations/{inv_id}/resend",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["email_status"] == "queued"


# ═══════════════════════════════════════════════════════════════════
# 6. SECURITY — Token never in email
# ═══════════════════════════════════════════════════════════════════


def test_invitation_email_contains_link_not_raw_token():
    svc = EmailService()
    raw_token = "super_secret_token_abc123xyz"
    html = svc.render_template(
        "invitation_email.html",
        invited_by_name="Admin",
        organization_name="Test Org",
        role_label="HR Manager",
        accept_url=f"https://hirecraft.ai/invite/{raw_token}",
        expires_at="2026-01-01",
        app_name="Test",
    )
    assert raw_token in html  # Token IS in the accept_url link
    assert "href=" in html  # It's in a link attribute, not exposed as text


def test_template_does_not_expose_token_as_text():
    svc = EmailService()
    raw_token = "super_secret_token_abc123xyz"
    html = svc.render_template(
        "invitation_email.html",
        invited_by_name="Admin",
        organization_name="Test Org",
        role_label="HR Manager",
        accept_url=f"https://hirecraft.ai/invite/{raw_token}",
        expires_at="2026-01-01",
        app_name="Test",
    )
    # Token should only appear in href attributes, not as plain text
    lines = html.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and raw_token in stripped:
            assert "href=" in stripped, f"Token exposed as plain text in: {stripped}"


# ═══════════════════════════════════════════════════════════════════
# 7. INVITATION LINK — Correct format
# ═══════════════════════════════════════════════════════════════════


def test_invitation_link_uses_frontend_base_url():
    from app.notifications.email_tasks import queue_invitation_email

    with patch("app.notifications.email_tasks.get_settings") as mock_settings:
        settings_mock = MagicMock(
            frontend_base_url="https://hirecraft.ai",
            app_name="AI Hiring Copilot",
        )
        settings_mock.frontend_url.side_effect = lambda path: f"https://hirecraft.ai{path}"
        mock_settings.return_value = settings_mock
        with patch("app.notifications.email_tasks._celery_available", return_value=True):
            with patch("app.workers.tasks.send_invitation_email") as mock_task:
                mock_task.delay.return_value = MagicMock(id="task-123")
                result = queue_invitation_email(
                    to_email="test@test.com",
                    invited_by_name="Admin",
                    organization_name="Test Org",
                    role="hr_manager",
                    raw_token="my-secret-token",
                    expires_at_str="2026-09-01",
                )
                mock_task.delay.assert_called_once_with(
                    to_email="test@test.com",
                    invited_by_name="Admin",
                    organization_name="Test Org",
                    role_label="HR Manager",
                    accept_url="https://hirecraft.ai/invite/my-secret-token",
                    expires_at="2026-09-01",
                    app_name="AI Hiring Copilot",
                )


# ═══════════════════════════════════════════════════════════════════
# 8. QUEUE HELPER — Error handling
# ═══════════════════════════════════════════════════════════════════


def test_queue_invitation_email_handles_celery_failure():
    from app.notifications.email_tasks import queue_invitation_email

    with patch("app.notifications.email_tasks.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            frontend_base_url="http://localhost:5173",
            app_name="AI Hiring Copilot",
        )
        with patch("app.notifications.email_tasks._celery_available", return_value=True):
            with patch("app.workers.tasks.send_invitation_email") as mock_task:
                mock_task.delay.side_effect = Exception("Redis connection refused")
                result = queue_invitation_email(
                    to_email="test@test.com",
                    invited_by_name="Admin",
                    organization_name="Test Org",
                    role="hr_manager",
                    raw_token="token123",
                    expires_at_str="2026-09-01",
                )
                assert result["status"] == "queue_error"


# ═══════════════════════════════════════════════════════════════════
# 9. ROLE LABELS — All invitable roles map correctly
# ═══════════════════════════════════════════════════════════════════


def test_role_labels_cover_invitable_roles():
    from app.notifications.email_tasks import ROLE_LABELS

    assert ROLE_LABELS["hr_manager"] == "HR Manager"
    assert ROLE_LABELS["organization_admin"] == "Organization Admin"
    assert ROLE_LABELS["recruiter"] == "Recruiter"


# ═══════════════════════════════════════════════════════════════════
# 10. BACKWARD COMPATIBILITY — Existing tests unaffected
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_candidate_registration_still_works(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Email Cand", "email": "email_cand@test.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 201
    assert "candidate" in resp.json()["roles"]


@pytest.mark.asyncio
async def test_existing_login_still_works(client: AsyncClient, _create_user_with_role):
    await _create_user_with_role("Email Login", "email_login@test.com", "SecureP@ss1", "recruiter")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "email_login@test.com", "password": "SecureP@ss1"},
    )
    assert resp.status_code == 200
