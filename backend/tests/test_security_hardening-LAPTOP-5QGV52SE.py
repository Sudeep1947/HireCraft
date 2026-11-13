"""Phase 15 — Security & Authorization Tests.

Verifies: unauthorized access, token behavior, input validation,
password security, API response consistency.
"""

import uuid

import pytest


# ── Password Security Tests ──────────────────────────────────────────


class TestPasswordSecurity:
    def test_hash_is_not_plaintext(self):
        from app.core.security import hash_password
        hashed = hash_password("Admin@12345")
        assert hashed != "Admin@12345"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        from app.core.security import hash_password, verify_password
        pw = "SecureP@ss123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_wrong_password(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("SecureP@ss123")
        assert verify_password("WrongPassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        from app.core.security import hash_password
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        # bcrypt uses random salt, so hashes should differ
        assert h1 != h2

    def test_empty_password_hashed(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("")
        assert verify_password("", hashed) is True


# ── JWT Token Tests ──────────────────────────────────────────────────


class TestJWTSecurity:
    def test_token_creation_and_decode(self):
        from app.core.security import create_access_token, decode_token
        token = create_access_token(
            subject=str(uuid.uuid4()),
            roles=["recruiter"],
            email="test@example.com",
        )
        decoded = decode_token(token)
        assert decoded["roles"] == ["recruiter"]
        assert decoded["email"] == "test@example.com"

    def test_invalid_token_rejected(self):
        from app.core.security import decode_token
        with pytest.raises(ValueError, match="Invalid"):
            decode_token("invalid.token.here")

    def test_tampered_token_rejected(self):
        from app.core.security import create_access_token, decode_token
        token = create_access_token(
            subject=str(uuid.uuid4()),
            roles=["recruiter"],
        )
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError, match="Invalid"):
            decode_token(tampered)

    def test_empty_token_rejected(self):
        from app.core.security import decode_token
        with pytest.raises(ValueError, match="Invalid"):
            decode_token("")


# ── Input Validation Tests ───────────────────────────────────────────


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_large_payload_rejected(self, client):
        """Requests exceeding 10MB should be rejected."""
        large_payload = "x" * (11 * 1024 * 1024)
        resp = await client.post(
            "/api/v1/auth/login",
            content=large_payload,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_null_byte_rejected(self, client):
        """JSON bodies with null bytes should be rejected."""
        resp = await client.post(
            "/api/v1/auth/login",
            content=b'{"email": "test@test.com", "password": "pass\x00word"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400


# ── Authentication Flow Tests ────────────────────────────────────────


class TestAuthenticationFlows:
    @pytest.mark.asyncio
    async def test_unauthenticated_access_to_protected_endpoint(self, client):
        """Accessing protected endpoints without auth should fail."""
        resp = await client.get("/api/v1/auth/me")
        # FastAPI dependency injection returns 422 for missing Authorization header
        assert resp.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_login_with_missing_fields(self, client):
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_with_invalid_body(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email"},
        )
        assert resp.status_code in (400, 401, 422)


# ── API Response Format Tests ────────────────────────────────────────


class TestAPIResponseFormat:
    @pytest.mark.asyncio
    async def test_error_responses_have_consistent_structure(self, client):
        """Validation error responses should follow the consistent error format."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={},
        )
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_json(self, client):
        resp = await client.get("/api/v1/health/live")
        assert resp.headers.get("content-type", "").startswith("application/json")
        data = resp.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_correlation_id_in_response(self, client):
        resp = await client.get("/api/v1/health/live")
        assert "X-Request-ID" in resp.headers

    @pytest.mark.asyncio
    async def test_error_response_has_request_id(self, client):
        """Validation errors should include a request_id for tracing."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={},
        )
        data = resp.json()
        # The new error format includes request_id in error object
        assert "error" in data
        error = data["error"]
        assert "request_id" in error
        assert len(error["request_id"]) > 0
