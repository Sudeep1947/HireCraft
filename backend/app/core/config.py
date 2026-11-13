"""Application configuration with production safety validation.

All secrets must come from environment variables. The application refuses
to start in non-development environments with insecure defaults.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

from pydantic import Field, RedisDsn, field_validator
from pydantic_settings import BaseSettings


_INSECURE_DEFAULTS = {"change-me-in-production", "", "changeme", "secret", "password"}

# Hostnames that only ever resolve on one machine or inside one private network.
# An email link is opened on the *recipient's* network, so any of these produces
# a dead link for everyone outside the author's LAN.
_LOCAL_ONLY_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "::",
    "host.docker.internal",
    "backend",
    "api",
}
_INTERNAL_ONLY_SUFFIXES = (".local", ".localhost", ".internal", ".localdomain", ".cluster.local")


def non_public_frontend_reason(value: str) -> str | None:
    """Explain why ``value`` cannot be opened by an invitation recipient.

    Returns ``None`` when the address looks publicly routable. This is a
    configuration check, not a security control: it exists so a misconfigured
    deployment fails loudly at startup instead of silently emailing links that
    resolve nowhere.
    """
    raw = (value or "").strip()
    if not raw:
        return "it is empty"

    # Tolerate a bare "host" or "host:port" as well as a full URL.
    parsed = urlparse(raw if "//" in raw else f"//{raw}")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return "it has no host"

    if host in _LOCAL_ONLY_HOSTNAMES:
        return "it points at the local machine or an internal service name"
    if host.endswith(_INTERNAL_ONLY_SUFFIXES):
        return "it uses an internal-only hostname"

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A real DNS name: nothing to prove here, and we cannot resolve it
        # without turning startup into a network call.
        return None

    if ip.is_unspecified:
        return "it points at an unspecified address"
    if ip.is_loopback:
        return "it points at a loopback address"
    if ip.is_link_local:
        return "it points at a link-local address"
    if ip.is_private:
        return "it points at a private network address"
    if ip.is_reserved:
        return "it points at a reserved address"
    return None


class Settings(BaseSettings):
    app_name: str = "AI Hiring Copilot"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/hire",
        alias="DATABASE_URL",
    )
    database_echo: bool = False

    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    algorithm: str = "HS256"

    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        import json

        v = self.cors_origins
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", alias="CELERY_RESULT_BACKEND")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="meta-llama/llama-3.3-70b-instruct:free", alias="OPENROUTER_MODEL")

    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")
    ollama_model: str = Field(default="llama3.3", alias="OLLAMA_MODEL")

    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    llm_fallback_enabled: bool = True

    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")

    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(default=None, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: Optional[str] = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="AI Hiring Copilot", alias="SMTP_FROM_NAME")

    invitation_expiration_hours: int = Field(default=72, alias="INVITATION_EXPIRATION_HOURS")

    frontend_base_url: str = Field(default="http://localhost:5173", alias="FRONTEND_BASE_URL")

    # -- OAuth 2.0 / OpenID Connect Providers ------------------------------
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, alias="GOOGLE_REDIRECT_URI")

    microsoft_client_id: Optional[str] = Field(default=None, alias="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: Optional[str] = Field(default=None, alias="MICROSOFT_CLIENT_SECRET")
    microsoft_tenant_id: str = Field(default="common", alias="MICROSOFT_TENANT_ID")
    microsoft_redirect_uri: Optional[str] = Field(default=None, alias="MICROSOFT_REDIRECT_URI")

    # -- HR attention thresholds (Phase 14) --------------------------------
    # These are the *only* place the HR "needs attention" rules are
    # parameterized. They live on Settings (not in the service, and never in
    # the frontend) so one deployment can retune every rule without a code
    # change, and so the rules stay deterministic: given the same rows and the
    # same thresholds, the attention list is always identical.
    #
    # They are thresholds for *surfacing* a row to a human reviewer. Nothing
    # here approves, rejects, scores or otherwise decides anything about a
    # candidate -- a crossed threshold only means "look at this", and the
    # recruiter-owned write surface remains the only way to change state.
    #
    # `hr_attention_stale_application_days`: an application still in a live
    # (non-terminal) status with no status change for this many days.
    hr_attention_stale_application_days: int = Field(
        default=7, alias="HR_ATTENTION_STALE_APPLICATION_DAYS", ge=1
    )
    # `hr_attention_min_advancement_rate`: below this share of an employer's
    # applications reaching a screening/interview/decision milestone, the
    # employer's funnel is reported as needing attention.
    hr_attention_min_advancement_rate: float = Field(
        default=0.1, alias="HR_ATTENTION_MIN_ADVANCEMENT_RATE", ge=0.0, le=1.0
    )
    # `hr_attention_min_pipeline_apps`: an employer with at least this many
    # applications is only rate-checked once volume is meaningful.
    hr_attention_min_pipeline_apps: int = Field(
        default=5, alias="HR_ATTENTION_MIN_PIPELINE_APPS", ge=1
    )
    # `hr_attention_fairness_gap`: maximum absolute adverse-impact ratio
    # between a protected group and the reference group before a fairness
    # alert is surfaced. Mirrors the platform's existing fairness review
    # convention; it is a review trigger, not a compliance verdict.
    hr_attention_fairness_gap: float = Field(
        default=0.8, alias="HR_ATTENTION_FAIRNESS_GAP", ge=0.0, le=1.0
    )
    # `hr_attention_max_items`: cap on how many attention items a single
    # response may carry, so a large organization cannot pull an unbounded
    # list. The count of items that *did* qualify is reported separately so
    # truncation is never silent.
    hr_attention_max_items: int = Field(
        default=50, alias="HR_ATTENTION_MAX_ITEMS", ge=1
    )

    def frontend_url(self, path: str = "") -> str:
        """Build an absolute URL on the configured frontend origin.

        Always sourced from FRONTEND_BASE_URL so invitation/verification links
        never embed a hardcoded address. A leading slash on ``path`` is
        normalized so the result is `${frontend_base_url}/invite/${token}`.
        """
        base = (self.frontend_base_url or "").rstrip("/")
        if path.startswith("/"):
            path = path.lstrip("/")
        if not base:
            return path
        return f"{base}/{path}" if path else base

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        import os

        env = os.environ.get("ENVIRONMENT", "development")
        if env != "development" and v.lower().strip() in _INSECURE_DEFAULTS:
            raise ValueError(
                "SECRET_KEY must be a cryptographically random string in non-development environments. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("frontend_base_url")
    @classmethod
    def validate_frontend_base_url(cls, v: str, info) -> str:
        """Refuse to build email links from an address only the author can reach.

        Outside development every invitation, verification and activation link
        leaves this process by email and is opened somewhere else entirely, so a
        loopback, private or container-internal origin can only ever produce a
        dead link. Failing here surfaces the misconfiguration at startup instead
        of at the recipient's first click.

        Development is exempt on purpose: an author running the whole stack on
        one machine legitimately uses localhost, and the reachability tests rely
        on it.
        """
        environment = (info.data or {}).get("environment") or "development"
        if environment == "development":
            return v
        reason = non_public_frontend_reason(v)
        if reason:
            raise ValueError(
                "FRONTEND_BASE_URL must be the public frontend origin because "
                f"{reason}. Invitation and verification emails are opened on the "
                "recipient's own network, so this must be reachable from the "
                "public internet (for example https://app.example.com). "
                "localhost, 127.0.0.1, 10.x, 172.16-31.x, 192.168.x and internal "
                "hostnames are development-only."
            )
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
