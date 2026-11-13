"""Phase 15 — Production Hardening Tests.

Covers: error handling, request correlation, security headers,
simulation immutability, file upload safety, configuration validation,
rate limiting, health endpoints.
"""

import os
import uuid

import pytest

from app.core.exceptions import (
    AppError,
    AIModelError,
    ConflictError,
    DatabaseError,
    ExternalDependencyError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    SimulationError,
    UnauthorizedError,
    ValidationError,
    WorkerError,
)


# ── Exception Hierarchy Tests ────────────────────────────────────────


class TestExceptionHierarchy:
    def test_app_error_defaults(self):
        exc = AppError()
        assert exc.status_code == 500
        assert exc.code == "internal_error"
        assert exc.detail == "Internal server error"
        assert exc.extra == {}

    def test_app_error_custom(self):
        exc = AppError(detail="custom", extra={"key": "val"})
        assert exc.detail == "custom"
        assert exc.extra == {"key": "val"}

    @pytest.mark.parametrize("exc_class,expected_code,expected_status", [
        (NotFoundError, "not_found", 404),
        (UnauthorizedError, "unauthorized", 401),
        (ForbiddenError, "forbidden", 403),
        (ConflictError, "conflict", 409),
        (ValidationError, "validation_error", 422),
        (RateLimitError, "rate_limit_exceeded", 429),
        (DatabaseError, "database_error", 503),
        (ExternalDependencyError, "dependency_unavailable", 503),
        (AIModelError, "ai_model_unavailable", 503),
        (SimulationError, "simulation_error", 500),
        (WorkerError, "worker_error", 503),
    ])
    def test_exception_codes_and_status(self, exc_class, expected_code, expected_status):
        exc = exc_class()
        assert exc.code == expected_code
        assert exc.status_code == expected_status

    def test_exception_is_app_error(self):
        for exc_class in [NotFoundError, UnauthorizedError, ForbiddenError,
                          ConflictError, ValidationError, RateLimitError,
                          DatabaseError, ExternalDependencyError, AIModelError,
                          SimulationError, WorkerError]:
            assert issubclass(exc_class, AppError)


# ── Configuration Validation Tests ───────────────────────────────────


class TestConfigurationValidation:
    def test_insecure_defaults_list(self):
        from app.core.config import _INSECURE_DEFAULTS
        assert "change-me-in-production" in _INSECURE_DEFAULTS
        assert "" in _INSECURE_DEFAULTS

    def test_secret_key_validator_rejects_insecure_in_production(self):
        from app.core.config import Settings
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(Exception):
                Settings(secret_key="change-me-in-production")

    def test_secret_key_validator_allows_insecure_in_development(self):
        from app.core.config import Settings
        # Test the validator classmethod directly (Pydantic Settings v2 doesn't accept kwargs)
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            result = Settings.validate_secret_key("change-me-in-production")
            assert result == "change-me-in-production"

    def test_database_url_normalization(self):
        from app.core.config import Settings
        # The validator runs at class definition time, so test the validator directly
        from app.core.config import Settings as S
        result = S.normalize_database_url("postgresql://user:pass@host/db")
        assert "postgresql+asyncpg://" in result

    def test_database_url_already_async(self):
        from app.core.config import Settings as S
        result = S.normalize_database_url("postgresql+asyncpg://user:pass@host/db")
        assert "postgresql+asyncpg://" in result


# ── Security Header Tests ────────────────────────────────────────────


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_security_headers_present(self, client):
        resp = await client.get("/api/v1/health/live")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Permissions-Policy" in resp.headers

    @pytest.mark.asyncio
    async def test_request_id_header(self, client):
        resp = await client.get("/api/v1/health/live")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_request_id_passthrough(self, client):
        custom_id = str(uuid.uuid4())
        resp = await client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": custom_id},
        )
        assert resp.headers.get("X-Request-ID") == custom_id


# ── Health Endpoint Tests ────────────────────────────────────────────


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_liveness(self, client):
        resp = await client.get("/api/v1/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_readiness(self, client):
        resp = await client.get("/api/v1/health/ready")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_full_health(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]


# ── Error Response Format Tests ──────────────────────────────────────


class TestErrorFormat:
    @pytest.mark.asyncio
    async def test_validation_error_format(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data


# ── Simulation Immutability Tests ────────────────────────────────────


class TestSimulationImmutability:
    """Verify that simulation infrastructure never modifies live hiring data."""

    def test_simulation_config_is_deep_copied(self):
        """Simulation operations must work on deep copies, not originals."""
        import copy

        original = {
            "simulation": {
                "scoring_weights": {"skills": 0.35, "experience": 0.25},
                "threshold": 70,
            }
        }
        copied = copy.deepcopy(original)
        copied["simulation"]["threshold"] = 80
        copied["simulation"]["scoring_weights"]["skills"] = 0.5

        assert original["simulation"]["threshold"] == 70
        assert original["simulation"]["scoring_weights"]["skills"] == 0.35

    def test_perturbation_engine_works_on_copies(self):
        """PerturbationEngine must never mutate the input config."""
        from app.services.simulation.perturbation_engine import PerturbationEngine
        from app.domain.enums import SensitivityDimension

        engine = PerturbationEngine()
        base = {
            "simulation": {
                "scoring_weights": {"skills": 0.35, "experience": 0.25},
                "threshold": 70,
            }
        }
        original_threshold = base["simulation"]["threshold"]
        result = engine.apply_perturbation(base, SensitivityDimension.THRESHOLD, 90)

        # Original must be unchanged
        assert base["simulation"]["threshold"] == original_threshold
        # Result must have new value
        assert result["simulation"]["threshold"] == 90

    def test_configuration_generator_preserves_original(self):
        """ConfigurationGenerator must not modify the base config."""
        from app.services.simulation.configuration_generator import ConfigurationGenerator
        from app.domain.enums import ExperimentType, SensitivityDimension
        from app.domain.simulation_experiment_schemas import ParameterRange

        gen = ConfigurationGenerator()
        base = {
            "simulation": {
                "scoring_weights": {"skills": 0.35, "experience": 0.25, "education": 0.15,
                                    "projects": 0.15, "certifications": 0.05,
                                    "location": 0.0, "employment_type": 0.0, "semantic": 0.05},
                "threshold": 70,
                "shortlist_size": 10,
                "requirements": {"mandatory_skills": ["python"], "preferred_skills": [],
                                 "experience": {"minimum_years": 2}},
            }
        }
        original_threshold = base["simulation"]["threshold"]

        ranges = [ParameterRange(dimension=SensitivityDimension.THRESHOLD, start=65, end=80, step=5)]
        configs = gen.generate_configurations(base, ranges, ExperimentType.THRESHOLD_SWEEP)

        assert len(configs) > 0
        assert base["simulation"]["threshold"] == original_threshold

    def test_normalize_weights_does_not_mutate(self):
        """Weight normalization must return a new config."""
        from app.services.simulation.perturbation_engine import PerturbationEngine

        engine = PerturbationEngine()
        config = {
            "simulation": {
                "scoring_weights": {"skills": 0.35, "experience": 0.25, "education": 0.15,
                                    "projects": 0.15, "certifications": 0.05,
                                    "location": 0.0, "employment_type": 0.0, "semantic": 0.05}
            }
        }
        original_total = sum(config["simulation"]["scoring_weights"].values())
        result = engine.normalize_weights(config)

        # Original total should be unchanged
        assert abs(sum(config["simulation"]["scoring_weights"].values()) - original_total) < 0.001
        # Result should be normalized
        assert abs(sum(result["simulation"]["scoring_weights"].values()) - 1.0) < 0.001


# ── Rate Limiter Tests ──────────────────────────────────────────────


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_rate_limit_cleanup(self):
        """Verify rate limiter cleanup prevents memory leaks."""
        from app.core.middleware import RateLimitMiddleware

        now = 1000000.0
        window = 60.0

        # Add stale entries
        RateLimitMiddleware._requests["stale_ip_1"] = [now - window * 10]
        RateLimitMiddleware._requests["stale_ip_2"] = [now - window * 10]
        RateLimitMiddleware._requests["fresh_ip"] = [now - 5]

        RateLimitMiddleware._cleanup(now, window)

        assert "stale_ip_1" not in RateLimitMiddleware._requests
        assert "stale_ip_2" not in RateLimitMiddleware._requests
        assert "fresh_ip" in RateLimitMiddleware._requests


# ── File Upload Security Tests ──────────────────────────────────────


class TestFileUploadSecurity:
    def test_html_not_in_allowed_extensions(self):
        from app.services.candidate.resume import ALLOWED_EXTENSIONS

        assert ".html" not in ALLOWED_EXTENSIONS
        assert ".htm" not in ALLOWED_EXTENSIONS
        assert ".rtf" not in ALLOWED_EXTENSIONS

    def test_safe_extensions_present(self):
        from app.services.candidate.resume import ALLOWED_EXTENSIONS

        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS
        assert ".doc" in ALLOWED_EXTENSIONS
        assert ".txt" in ALLOWED_EXTENSIONS

    def test_validate_file_content_pdf(self):
        from app.services.candidate.resume import _validate_file_content

        pdf_header = b"%PDF-1.4 fake content"
        mime = _validate_file_content(pdf_header, ".pdf")
        assert mime == "application/pdf"

    def test_validate_file_content_txt(self):
        from app.services.candidate.resume import _validate_file_content

        mime = _validate_file_content(b"Hello world", ".txt")
        assert mime == "text/plain"

    def test_validate_file_content_empty(self):
        from app.services.candidate.resume import _validate_file_content

        with pytest.raises(ValueError, match="empty"):
            _validate_file_content(b"", ".pdf")

    def test_validate_file_content_mismatch(self):
        from app.services.candidate.resume import _validate_file_content

        with pytest.raises(ValueError, match="does not match"):
            _validate_file_content(b"%PDF-fake", ".docx")

    def test_validate_file_content_no_magic_bytes(self):
        from app.services.candidate.resume import _validate_file_content

        with pytest.raises(ValueError, match="does not match any supported format"):
            _validate_file_content(b"\x89PNG\x0d\x0a\x1a\x0a", ".pdf")

    def test_magic_bytes_table_covered(self):
        from app.services.candidate.resume import _MAGIC_BYTES

        # Verify all expected magic bytes are defined
        assert b"%PDF" in _MAGIC_BYTES
        assert b"PK" in _MAGIC_BYTES
        assert b"\xd0\xcf\x11\xe0" in _MAGIC_BYTES


# ── Celery Configuration Tests ──────────────────────────────────────


class TestCeleryConfiguration:
    def test_celery_has_result_expiry(self):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.result_expires == 3600

    def test_celery_has_prefetch_limit(self):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_has_time_limits(self):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_time_limit == 30 * 60
        assert celery_app.conf.task_soft_time_limit == 25 * 60

    def test_celery_has_task_tracking(self):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_track_started is True


# ── Logging Configuration Tests ─────────────────────────────────────


class TestLoggingConfiguration:
    def test_configure_logging_creates_log_dir(self, tmp_path, monkeypatch):
        from app.core import logging as logging_mod
        monkeypatch.setattr(logging_mod, "_LOG_DIR", tmp_path)
        logging_mod.configure_logging()
        assert (tmp_path / "app.log").exists()
        assert (tmp_path / "audit.log").exists()

    def test_get_logger_returns_logger(self):
        from app.core.logging import get_logger
        logger = get_logger("test.module")
        assert logger is not None
        assert logger.name == "test.module"


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
        assert h1 != h2


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


# ── API Response Format Tests ────────────────────────────────────────


class TestAPIResponseFormat:
    @pytest.mark.asyncio
    async def test_error_responses_have_consistent_structure(self, client):
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


# ── Import needed for monkeypatch ────────────────────────────────────
from unittest.mock import patch
