import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Membership Brief (used inside auth responses) ────────────────────────────


class OrganizationMembershipBrief(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    role: str
    status: str

    model_config = {"from_attributes": True}


# ── User Brief (used inside membership responses) ────────────────────────────


class UserBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


# ── Organization schemas ─────────────────────────────────────────────────────


URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:[/?#]\S*)?$",
    re.IGNORECASE,
)
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganizationCreate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=2000)
    official_email: EmailStr | None = None
    domain: str | None = Field(None, max_length=255)
    logo_url: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=255)
    status: Literal["active", "inactive"] = "active"

    @field_validator(
        "name", "slug", "description", "official_email", "domain",
        "logo_url", "industry", "website", "location",
        mode="before",
    )
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        """Trim surrounding whitespace before any format validation runs."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            if not v:
                raise ValueError("Slug must not be empty")
            if not SLUG_PATTERN.match(v):
                raise ValueError(
                    "Slug must contain only lowercase letters, numbers, and single "
                    "hyphens, with no leading or trailing hyphen"
                )
        return v

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        if v is not None and v != "":
            if not URL_PATTERN.match(v):
                raise ValueError("Invalid website URL format. Must start with http:// or https://")
        return v or None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    official_email: EmailStr | None = None
    domain: str | None = Field(None, max_length=255)
    logo_url: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=255)
    status: Literal["active", "inactive", "suspended"] | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    official_email: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    industry: str | None = None
    website: str | None = None
    location: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    total: int


# ── Membership schemas ───────────────────────────────────────────────────────


class OrganizationMembershipResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    status: str
    invited_by_id: uuid.UUID | None = None
    joined_at: datetime | None = None
    created_at: datetime
    user: UserBrief | None = None

    model_config = {"from_attributes": True}


class MembershipListResponse(BaseModel):
    items: list[OrganizationMembershipResponse]
    total: int


class MembershipUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(active|suspended|inactive)$")


class MembershipRoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(owner|hr_manager|recruiter|viewer)$")


# ── Invitation schemas ───────────────────────────────────────────────────────


class InvitationCreate(BaseModel):
    email: EmailStr
    # Server-side role allowlist (Phase 4/5): only organization-scoped staff roles.
    # Candidate is public-registration-only; platform roles are never invitable.
    role: Literal["hr_manager", "organization_admin", "recruiter"]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    organization_id: uuid.UUID
    expires_at: datetime | None = None
    created_at: datetime
    accepted_at: datetime | None = None
    email_status: str | None = None
    accept_url: str | None = None  # Set only on create/resend; never in list responses.

    model_config = {"from_attributes": True}


class InvitationListResponse(BaseModel):
    items: list[InvitationResponse]
    total: int


class InvitationAcceptRequest(BaseModel):
    token: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "InvitationAcceptRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class InvitationValidateResponse(BaseModel):
    valid: bool
    email: str | None = None
    role: str | None = None
    organization_name: str | None = None
    expires_at: datetime | None = None
    status: str | None = None
    existing_user: bool | None = None


class SignedInInvitationAcceptRequest(BaseModel):
    token: str = Field(..., min_length=1)
