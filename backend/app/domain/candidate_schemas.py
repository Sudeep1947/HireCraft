import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.domain.enums import EmploymentType, Gender, NotificationType, Proficiency, SkillCategory, SkillProficiency


class CandidateProfileCreate(BaseModel):
    phone: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None
    gender: Gender | None = None
    location: str | None = Field(None, max_length=255)
    nationality: str | None = Field(None, max_length=100)
    linkedin_url: str | None = Field(None, max_length=500)
    github_url: str | None = Field(None, max_length=500)
    portfolio_url: str | None = Field(None, max_length=500)
    website_url: str | None = Field(None, max_length=500)
    bio: str | None = None
    current_role: str | None = Field(None, max_length=255)
    interests: list[str] | None = Field(None, max_length=20)


class CandidateProfileUpdate(BaseModel):
    phone: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None
    gender: Gender | None = None
    location: str | None = Field(None, max_length=255)
    nationality: str | None = Field(None, max_length=100)
    linkedin_url: str | None = Field(None, max_length=500)
    github_url: str | None = Field(None, max_length=500)
    portfolio_url: str | None = Field(None, max_length=500)
    website_url: str | None = Field(None, max_length=500)
    bio: str | None = None
    current_role: str | None = Field(None, max_length=255)
    interests: list[str] | None = Field(None, max_length=20)


class CandidateProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    phone: str | None
    date_of_birth: date | None
    gender: str | None
    location: str | None
    nationality: str | None
    linkedin_url: str | None
    github_url: str | None
    portfolio_url: str | None
    website_url: str | None
    bio: str | None
    current_role: str | None
    interests: list[str] = Field(default_factory=list)
    avatar_url: str | None
    profile_completion: int
    created_at: datetime
    updated_at: datetime

    @field_validator("interests", mode="before")
    @classmethod
    def _normalize_interests(cls, value: object) -> list[str]:
        return list(value or [])

    model_config = {"from_attributes": True}


class CandidateDashboardResponse(BaseModel):
    profile: CandidateProfileResponse
    full_name: str
    email: str
    total_resumes: int = 0
    total_notifications: int = 0
    unread_notifications: int = 0
    recent_activity: list[dict] = []


class EducationCreate(BaseModel):
    institution: str = Field(..., min_length=1, max_length=255)
    degree: str = Field(..., min_length=1, max_length=255)
    branch: str | None = Field(None, max_length=255)
    specialization: str | None = Field(None, max_length=255)
    cgpa: float | None = Field(None, ge=0, le=10)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class EducationUpdate(BaseModel):
    institution: str | None = Field(None, min_length=1, max_length=255)
    degree: str | None = Field(None, min_length=1, max_length=255)
    branch: str | None = Field(None, max_length=255)
    specialization: str | None = Field(None, max_length=255)
    cgpa: float | None = Field(None, ge=0, le=10)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class EducationResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    institution: str
    degree: str
    branch: str | None
    specialization: str | None
    cgpa: float | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExperienceCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    job_title: str = Field(..., min_length=1, max_length=255)
    employment_type: EmploymentType | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    responsibilities: str | None = None
    technologies: str | None = None


class ExperienceUpdate(BaseModel):
    company: str | None = Field(None, min_length=1, max_length=255)
    job_title: str | None = Field(None, min_length=1, max_length=255)
    employment_type: EmploymentType | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    responsibilities: str | None = None
    technologies: str | None = None


class ExperienceResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    company: str
    job_title: str
    employment_type: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    responsibilities: str | None
    technologies: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: SkillCategory


class SkillResponse(BaseModel):
    id: int
    name: str
    category: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateSkillCreate(BaseModel):
    skill_id: int
    proficiency: SkillProficiency = SkillProficiency.INTERMEDIATE
    years_of_experience: float | None = Field(None, ge=0)


class CandidateSkillUpdate(BaseModel):
    proficiency: SkillProficiency | None = None
    years_of_experience: float | None = Field(None, ge=0)


class CandidateSkillResponse(BaseModel):
    profile_id: uuid.UUID
    skill_id: int
    proficiency: str
    years_of_experience: float | None
    skill: SkillResponse | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    technologies: str | None = None
    github_link: str | None = Field(None, max_length=500)
    live_demo: str | None = Field(None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    technologies: str | None = None
    github_link: str | None = Field(None, max_length=500)
    live_demo: str | None = Field(None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    title: str
    description: str | None
    technologies: str | None
    github_link: str | None
    live_demo: str | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CertificationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    organization: str = Field(..., min_length=1, max_length=255)
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = Field(None, max_length=255)
    credential_url: str | None = Field(None, max_length=500)


class CertificationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    organization: str | None = Field(None, min_length=1, max_length=255)
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = Field(None, max_length=255)
    credential_url: str | None = Field(None, max_length=500)


class CertificationResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    name: str
    organization: str
    issue_date: date | None
    expiry_date: date | None
    credential_id: str | None
    credential_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LanguageCreate(BaseModel):
    language: str = Field(..., min_length=1, max_length=100)
    reading: Proficiency = Proficiency.INTERMEDIATE
    writing: Proficiency = Proficiency.INTERMEDIATE
    speaking: Proficiency = Proficiency.INTERMEDIATE


class LanguageUpdate(BaseModel):
    language: str | None = Field(None, min_length=1, max_length=100)
    reading: Proficiency | None = None
    writing: Proficiency | None = None
    speaking: Proficiency | None = None


class LanguageResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    language: str
    reading: str
    writing: str
    speaking: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    notification_type: NotificationType = NotificationType.GENERAL


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime
    updated_at: datetime
    #: Where this notification's action goes, when one was recorded. Null for
    #: notifications written before the column existed and for types that have no
    #: destination, in which case the client falls back to routing by type exactly
    #: as it did before.
    action_link: str | None = None

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateEmailRequest(BaseModel):
    new_email: str = Field(..., max_length=255)


class ProfileCompletionResponse(BaseModel):
    completion_percentage: int
    sections: dict[str, bool]
    missing_sections: list[str]
    recommendations: list[str]
