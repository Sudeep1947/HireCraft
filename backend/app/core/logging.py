"""Structured logging with rotation and optional JSON format.

Provides request-id-aware structured logs for production log aggregation.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_LOG_DIR = Path("logs")


class _JSONFormatter(logging.Formatter):
    """JSON log formatter for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "funcName"):
            log_entry["function"] = record.funcName
        if hasattr(record, "lineno"):
            log_entry["line"] = record.lineno
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


class _TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    _FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"

    def __init__(self) -> None:
        super().__init__(self._FORMAT)


class _AuditFormatter(logging.Formatter):
    """Simplified formatter for audit logs."""

    _FORMAT = "%(asctime)s | %(message)s"

    def __init__(self) -> None:
        super().__init__(self._FORMAT)


def configure_logging() -> None:
    _LOG_DIR.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Remove existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()

    use_json = settings.environment not in ("development", "testing")

    # Stream handler (stdout)
    stream_handler = logging.StreamHandler(sys.stdout)
    if use_json:
        stream_handler.setFormatter(_JSONFormatter())
    else:
        stream_handler.setFormatter(_TextFormatter())
    root_logger.addHandler(stream_handler)

    # Rotating file handler — max 10 MB, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    if use_json:
        file_handler.setFormatter(_JSONFormatter())
    else:
        file_handler.setFormatter(_TextFormatter())
    root_logger.addHandler(file_handler)

    # SQLAlchemy engine — suppress noisy query logs
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.WARNING)

    # Audit logger — separate file for security audit trail
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't bubble up to root
    audit_handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "audit.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,  # Keep more audit history
        encoding="utf-8",
    )
    audit_handler.setFormatter(_AuditFormatter())
    audit_logger.addHandler(audit_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
