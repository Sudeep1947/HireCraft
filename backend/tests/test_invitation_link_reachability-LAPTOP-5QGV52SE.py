"""Invitation link reachability regression tests.

Guards against the "This site can't be reached" failure on admin-sent
invitation links (Recruiter AND HR). Verifies:
- ``accept_url`` returned by the API is built from the configurable
  ``FRONTEND_BASE_URL`` (never a hardcoded IP) and points at ``/invite/<token>``.
- Recruiter and HR (``hr_manager``) invitations both produce reachable links.
- Resend rotates the token and the new ``accept_url`` supersedes the old one.
- List responses never leak ``accept_url`` (token secrecy).
- Full round trip: create -> validate -> accept -> single-use enforced.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings, non_public_frontend_reason
from app.core.security import hash_password
from app.domain.models import Invitation, Role, User, UserRole

PASSWORD = "SecureP@ss1"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# HELPERS (mirroring Phase 4/5 test scaffolding)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def _create_user_with_role_in_db(session, email: str, name: str, role_name: str) -> User:
    user = User(
        id=uuid.uuid4(),
        full_name=name,
        email=email,
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    role = (
        await session.execute(select(Role).where(Role.name == role_name))
    ).scalar_one_or_none()
    if role:
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.flush()
    return user


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _setup_org_with_admin(client: AsyncClient, session) -> tuple[str, str]:
    user = await _create_user_with_role_in_db(
        session, f"adm_{uuid.uuid4().hex[:8]}@test.com", "Org Admin", "admin"
    )
    token = await _login(client, user.email)
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Link Reach Org", "slug": f"link-org-{uuid.uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return token, resp.json()["id"]


async def _invite_via_api(client: AsyncClient, token: str, org_id: str, email: str, role: str):
    with patch("app.notifications.email_tasks.queue_invitation_email") as mock_queue:
        mock_queue.return_value = {"status": "queued"}
        return await client.post(
            f"/api/v1/organizations/{org_id}/invitations",
            json={"email": email, "role": role},
            headers={"Authorization": f"Bearer {token}"},
        )


def _token_from_accept_url(accept_url: str) -> str:
    assert "/invite/" in accept_url, accept_url
    return accept_url.rsplit("/invite/", 1)[1]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 1. RECRUITER INVITATION LINK
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def test_recruiter_invitation_accept_url_is_reachable_and_config_driven(
    client: AsyncClient, session
):
    token, org_id = await _setup_org_with_admin(client, session)
    email = f"rec_{uuid.uuid4().hex[:8]}@test.com"

    resp = await _invite_via_api(client, token, org_id, email, "recruiter")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "recruiter"
    assert data["status"] == "pending"
    assert data["accept_url"], "accept_url must be present on create"

    base = get_settings().frontend_base_url.rstrip("/")
    assert data["accept_url"].startswith(f"{base}/invite/")
    assert "/invite/" in data["accept_url"]

    # The token embedded in the link must validate through the public endpoint.
    raw_token = _token_from_accept_url(data["accept_url"])
    validation = await client.get(f"/api/v1/invitations/validate/{raw_token}")
    assert validation.status_code == 200, validation.text
    v = validation.json()
    assert v["valid"] is True
    assert v["role"] == "recruiter"
    assert v["email"] == email
    assert v["existing_user"] is False


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 2. HR INVITATION LINK
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def test_hr_invitation_accept_url_is_reachable_and_config_driven(
    client: AsyncClient, session
):
    token, org_id = await _setup_org_with_admin(client, session)
    email = f"hr_{uuid.uuid4().hex[:8]}@test.com"

    resp = await _invite_via_api(client, token, org_id, email, "hr_manager")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "hr_manager"
    assert data["accept_url"]

    base = get_settings().frontend_base_url.rstrip("/")
    assert data["accept_url"].startswith(f"{base}/invite/")

    raw_token = _token_from_accept_url(data["accept_url"])
    validation = await client.get(f"/api/v1/invitations/validate/{raw_token}")
    assert validation.status_code == 200, validation.text
    v = validation.json()
    assert v["valid"] is True
    assert v["role"] == "hr_manager"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 3. NO HARDCODED IP IN BUSINESS LOGIC
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def test_accept_url_changes_with_config_no_hardcoded_ip(client: AsyncClient, session):
    token, org_id = await _setup_org_with_admin(client, session)
    email = f"cfg_{uuid.uuid4().hex[:8]}@test.com"

    fake_settings = SimpleNamespace(frontend_url=lambda p: f"https://app.hirecraft.example{p}")
    with patch("app.api.v1.organizations.get_settings", return_value=fake_settings):
        resp = await _invite_via_api(client, token, org_id, email, "recruiter")

    assert resp.status_code == 201, resp.text
    accept_url = resp.json()["accept_url"]
    assert accept_url.startswith("https://app.hirecraft.example/invite/")
    assert "10.163" not in accept_url and "192.168" not in accept_url


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 4. RESEND ROTATES THE LINK
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def test_resend_returns_new_accept_url_and_old_token_is_invalid(
    client: AsyncClient, session
):
    token, org_id = await _setup_org_with_admin(client, session)
    email = f"res_{uuid.uuid4().hex[:8]}@test.com"

    created = await _invite_via_api(client, token, org_id, email, "hr_manager")
    assert created.status_code == 201, created.text
    invitation_id = created.json()["id"]
    old_token = _token_from_accept_url(created.json()["accept_url"])

    with patch("app.notifications.email_tasks.queue_invitation_email") as mock_queue:
        mock_queue.return_value = {"status": "queued"}
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/invitations/{invitation_id}/resend",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200, resp.text
    new_token = _token_from_accept_url(resp.json()["accept_url"])
    assert new_token != old_token

    old_validation = await client.get(f"/api/v1/invitations/validate/{old_token}")
    assert old_validation.status_code == 200
    assert old_validation.json()["valid"] is False


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 5. LIST RESPONSES NEVER LEAK accept_url
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def test_list_invitations_does_not_expose_accept_url(client: AsyncClient, session):
    token, org_id = await _setup_org_with_admin(client, session)
    email = f"list_{uuid.uuid4().hex[:8]}@test.com"
    await _invite_via_api(client, token, org_id, email, "recruiter")

    resp = await client.get(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    for item in resp.json()["items"]:
        assert "accept_url" not in item or item["accept_url"] is None


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 7. A NON-PUBLIC FRONTEND_BASE_URL IS REFUSED OUTSIDE DEVELOPMENT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


# The addresses that produced the "This site can't be reached" failure: a LAN IP
# is fine for the machine that sent the mail and useless to everyone else.
UNREACHABLE_ORIGINS = [
    "http://10.228.245.1:5173",
    "http://192.168.1.20:5173",
    "http://172.16.4.9:5173",
    "http://172.31.255.254:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://0.0.0.0:5173",
    "http://[::1]:5173",
    "http://frontend.local",
    "http://backend:8000",
    "",
]

PUBLIC_ORIGINS = [
    "https://app.hirecraft.ai",
    "http://example.com",
    "https://staging.hirecraft.ai:8443",
    "https://8.8.8.8",
]


def test_unreachable_origins_are_all_detected():
    for origin in UNREACHABLE_ORIGINS:
        assert non_public_frontend_reason(origin) is not None, origin


def test_public_origins_are_accepted():
    for origin in PUBLIC_ORIGINS:
        assert non_public_frontend_reason(origin) is None, origin


def test_private_ranges_are_detected_without_a_full_ip_literal_check():
    """172.16-31.x is private; 172.32.x is not. The check has to use ranges."""
    assert non_public_frontend_reason("http://172.16.0.1") is not None
    assert non_public_frontend_reason("http://172.31.255.255") is not None
    assert non_public_frontend_reason("https://172.32.0.1") is None


def test_production_refuses_a_private_frontend_base_url():
    with pytest.raises(ValidationError) as excinfo:
        Settings(environment="production", FRONTEND_BASE_URL="http://10.228.245.1:5173")
    message = str(excinfo.value)
    assert "FRONTEND_BASE_URL" in message
    # The message must explain the problem without echoing anything sensitive.
    assert "private network address" in message


@pytest.mark.parametrize("environment", ["staging", "production", "test"])
def test_non_development_refuses_loopback_and_internal_names(environment):
    for origin in ("http://localhost:5173", "http://frontend.local", "http://127.0.0.1"):
        with pytest.raises(ValidationError):
            Settings(environment=environment, FRONTEND_BASE_URL=origin)


def test_non_development_accepts_a_public_frontend_base_url():
    for origin in PUBLIC_ORIGINS:
        assert Settings(environment="production", FRONTEND_BASE_URL=origin).frontend_base_url == origin


def test_development_still_allows_localhost():
    """An author running the whole stack on one machine is a supported setup."""
    settings = Settings(environment="development", FRONTEND_BASE_URL="http://localhost:5173")
    assert settings.frontend_url("/invite/abc123") == "http://localhost:5173/invite/abc123"


def test_generated_link_never_contains_a_private_address_in_production():
    settings = Settings(environment="production", FRONTEND_BASE_URL="https://app.hirecraft.ai")
    url = settings.frontend_url("/invite/some-token")
    assert url == "https://app.hirecraft.ai/invite/some-token"
    for needle in ("10.228.245.1", "192.168", "172.16", "127.0.0.1", "localhost"):
        assert needle not in url


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 8. FULL ROUND TRIP AND SINGLE USE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def test_accept_flow_round_trip_and_single_use(client: AsyncClient, session):
    token, org_id = await _setup_org_with_admin(client, session)
    email = f"full_{uuid.uuid4().hex[:8]}@test.com"

    created = await _invite_via_api(client, token, org_id, email, "recruiter")
    assert created.status_code == 201, created.text
    raw_token = _token_from_accept_url(created.json()["accept_url"])

    accept = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "New Recruiter",
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    assert accept.status_code == 200, accept.text

    second_validation = await client.get(f"/api/v1/invitations/validate/{raw_token}")
    assert second_validation.status_code == 200
    assert second_validation.json()["valid"] is False

    second_accept = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "full_name": "Again",
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    assert second_accept.status_code in (400, 409, 422), second_accept.text