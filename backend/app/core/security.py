import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()

# ── Password Validation ─────────────────────────────────────────────

_PASSWORD_RULES: list[tuple[str, Any]] = [
    ("at least 8 characters", lambda p: len(p) >= 8),
    ("an uppercase letter", lambda p: any(c.isupper() for c in p)),
    ("a lowercase letter", lambda p: any(c.islower() for c in p)),
    ("a digit", lambda p: any(c.isdigit() for c in p)),
]


def validate_password_strength(password: str) -> list[str]:
    """Return a list of unmet password requirements."""
    return [desc for desc, check in _PASSWORD_RULES if not check(password)]


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ─────────────────────────────────────────────────────────────


def create_access_token(
    subject: str,
    roles: list[str],
    email: str = "",
    full_name: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "full_name": full_name,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
        "token_id": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str, remember_me: bool = False) -> str:
    now = datetime.now(timezone.utc)
    expiry_days = 30 if remember_me else settings.refresh_token_expire_days
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(days=expiry_days),
        "type": "refresh",
        "token_id": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise ValueError("Invalid or expired token")



