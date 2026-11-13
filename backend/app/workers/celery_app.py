"""Celery application configuration with production hardening.

Features:
- Task result expiry (prevents Redis memory growth)
- Structured retry policies
- Task state tracking
- Worker health monitoring
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hire",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task tracking
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 min hard limit
    task_soft_time_limit=25 * 60,  # 25 min soft limit
    # Result expiry — prevent Redis memory growth
    result_expires=3600,  # 1 hour
    result_persistent=False,
    # Worker configuration
    worker_prefetch_multiplier=1,  # Fair scheduling for long tasks
    worker_max_tasks_per_child=100,  # Prevent memory leaks
    worker_cancel_long_running_tasks_on_connection_loss=True,
    # Retry policy for broker connection
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=5,
    broker_transport_options={
        "visibility_timeout": 3600,  # 1 hour
        "fanout_prefix": True,
    },
)


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
