from typing import Any


class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"
    code: str = "internal_error"

    def __init__(self, detail: str | None = None, extra: dict[str, Any] | None = None) -> None:
        self.detail = detail or self.detail
        self.extra = extra or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"


class DatabaseError(AppError):
    status_code = 503
    code = "database_error"


class ExternalDependencyError(AppError):
    status_code = 503
    code = "dependency_unavailable"


class AIModelError(AppError):
    status_code = 503
    code = "ai_model_unavailable"


class SimulationError(AppError):
    status_code = 500
    code = "simulation_error"


class WorkerError(AppError):
    status_code = 503
    code = "worker_error"
