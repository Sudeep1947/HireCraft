"""Pydantic schemas for employee access request flow."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Employee Access Request ─────────────────────────────────────────


class AccessRequestCreate(BaseModel):
    """Employee submits an access request."""

    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    organization_slug: str = Field(..., min_length=1, max_length=100, description="Organization slug or domain")
    requested_role: Literal["hr_manager", "recruiter"] | None = None


class AccessRequestResponse(BaseModel):
    """Public response after creating an access request."""

    status: str
    message: str


class AccessRequestVerifyResponse(BaseModel):
    """Response after email verification."""

    status: str
    message: str
    request_id: uuid.UUID | None = None
    organization_name: str | None = None


class AccessRequestPendingResponse(BaseModel):
    """Response showing pending request status."""

    request_id: uuid.UUID
    full_name: str
    email: str
    organization_name: str
    status: str
    requested_role: str | None = None
    created_at: datetime


class AccessRequestResendResponse(BaseModel):
    status: str
    message: str


# ── Admin Access Request Management ─────────────────────────────────


class AccessRequestAdminResponse(BaseModel):
    """Admin view of an access request."""

    id: uuid.UUID
    full_name: str
    email: str
    organization_id: uuid.UUID
    organization_name: str
    requested_role: str | None
    status: str
    email_verified_at: datetime | None
    approved_role: str | None
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    created_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AccessRequestAdminListResponse(BaseModel):
    requests: list[AccessRequestAdminResponse]
    total: int


class AccessRequestApprove(BaseModel):
    """Admin approves an access request with a specific role."""

    approved_role: Literal["hr_manager", "recruiter"]


class AccessRequestReject(BaseModel):
    """Admin rejects an access request."""

    reason: str | None = Field(None, max_length=500)


class AccessRequestActionResponse(BaseModel):
    status: str
    message: str
    request_id: uuid.UUID


# ── Account Activation ──────────────────────────────────────────────


class AccessRequestActivate(BaseModel):
    """Employee activates their account after approval."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "AccessRequestActivate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class AccessRequestActivationResponse(BaseModel):
    status: str
    message: str
