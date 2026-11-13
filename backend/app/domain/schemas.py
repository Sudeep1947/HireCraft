import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class OrganizationMembershipBrief(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    role: str
    status: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool
    is_verified: bool
    roles: list[str] = []
    organization_memberships: list[OrganizationMembershipBrief] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    remember_me: bool = Field(default=False)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenUserInfo(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool
    is_verified: bool
    roles: list[str] = []
    organization_memberships: list[OrganizationMembershipBrief] | None = None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: TokenUserInfo | None = None


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    roles: list[str] = []
    exp: datetime
    type: str


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
    extra: dict | None = None


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        return v.strip()


class RoleListResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class CandidateDashboardResponse(BaseModel):
    total_applications: int = 0
    saved_jobs: int = 0
    resume_score: int = 0
    ats_score: int = 0
    profile_completion: int = 0
    recommended_jobs_count: int = 0
    recent_applications: list[dict] = []
    ai_suggestions: list[str] = []


class RecruiterDashboardResponse(BaseModel):
    total_jobs: int = 0
    active_jobs: int = 0
    total_applications: int = 0
    candidates_screened: int = 0
    top_candidates: list[dict] = []
    interview_pipeline: dict = {}
    hiring_status: dict = {}
    recent_applications: list[dict] = []


class HRDashboardResponse(BaseModel):
    open_positions: int = 0
    total_candidates: int = 0
    total_recruiters: int = 0
    hiring_funnel: dict = {}
    department_hiring: list[dict] = []
    recent_activity: list[dict] = []
    time_to_hire_avg: float = 0.0
    hiring_trends: list[dict] = []


class AdminDashboardResponse(BaseModel):
    total_users: int = 0
    active_users: int = 0
    total_candidates: int = 0
    total_recruiters: int = 0
    total_hr: int = 0
    total_admins: int = 0
    system_health: dict = {}
    recent_logins: list[dict] = []
    user_growth: list[dict] = []


class AdminUserListItem(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool
    is_verified: bool
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict | None
    ip_address: str | None
    success: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OAuthUrlResponse(BaseModel):
    provider: str
    url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1)
    state: str | None = None
    redirect_uri: str | None = None


class DevOAuthLoginRequest(BaseModel):
    email: EmailStr
    provider: str = Field(default="google")
    full_name: str | None = None

