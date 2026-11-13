import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.db.session import get_db
from app.domain.candidate_schemas import (
    CandidateProfileResponse,
    CandidateProfileUpdate,
    CandidateSkillCreate,
    CandidateSkillResponse,
    CandidateSkillUpdate,
    CertificationCreate,
    CertificationResponse,
    CertificationUpdate,
    ChangePasswordRequest,
    EducationCreate,
    EducationResponse,
    EducationUpdate,
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
    LanguageCreate,
    LanguageResponse,
    LanguageUpdate,
    NotificationResponse,
    ProfileCompletionResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    UpdateEmailRequest,
)
from app.domain.schemas import MessageResponse
from app.domain.models import User
from app.domain.resume_schemas import (
    ParsedDataResponse,
    ResumeAnalysisResponse,
    ResumeDetailResponse,
    ResumeResponse,
    ResumeSetPrimary,
    ResumeUploadResponse,
)
from app.repositories.candidate.certification import CertificationRepository
from app.repositories.candidate.education import EducationRepository
from app.repositories.candidate.experience import ExperienceRepository
from app.repositories.candidate.language import LanguageRepository
from app.repositories.candidate.notification import NotificationRepository
from app.repositories.candidate.profile import CandidateProfileRepository
from app.repositories.candidate.resume import ResumeRepository, ParsedResumeDataRepository
from app.repositories.candidate.skill import CandidateSkillRepository, SkillRepository
from app.repositories.candidate.project import ProjectRepository
from app.repositories.user import UserRepository
from app.services.candidate.intelligence import CandidateIntelligenceService
from app.services.candidate.notification import NotificationService
from app.services.candidate.profile import ProfileService
from app.services.candidate.resume import ResumeService
from app.domain.intelligence_schemas import (
    CandidateIntelligence,
    ResumeCompareResponse,
    ResumeVersionResponse,
    SyncActionRequest,
    SyncActionResult,
    SyncDiffResponse,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = get_logger(__name__)

UPLOAD_DIR = Path("uploads/avatars")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _get_intelligence_service(db: AsyncSession = Depends(get_db)) -> CandidateIntelligenceService:
    return CandidateIntelligenceService(
        profile_repo=CandidateProfileRepository(db),
        education_repo=EducationRepository(db),
        experience_repo=ExperienceRepository(db),
        candidate_skill_repo=CandidateSkillRepository(db),
        skill_repo=SkillRepository(db),
        project_repo=ProjectRepository(db),
        certification_repo=CertificationRepository(db),
        language_repo=LanguageRepository(db),
        resume_repo=ResumeRepository(db),
        parsed_repo=ParsedResumeDataRepository(db),
    )


def _get_profile_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(
        profile_repo=CandidateProfileRepository(db),
        education_repo=EducationRepository(db),
        experience_repo=ExperienceRepository(db),
        candidate_skill_repo=CandidateSkillRepository(db),
        skill_repo=SkillRepository(db),
        project_repo=ProjectRepository(db),
        certification_repo=CertificationRepository(db),
        language_repo=LanguageRepository(db),
        notification_repo=NotificationRepository(db),
        user_repo=UserRepository(db),
    )


def _get_resume_service(db: AsyncSession = Depends(get_db)) -> ResumeService:
    return ResumeService(db)


def _get_notification_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(
        notification_repo=NotificationRepository(db),
    )


# --- Profile ---

@router.get("/profile", response_model=CandidateProfileResponse)
async def get_profile(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_profile(current_user.id)


@router.put("/profile", response_model=CandidateProfileResponse)
async def update_profile(
    body: CandidateProfileUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_profile(current_user.id, body)


@router.get("/dashboard", response_model=dict)
async def get_dashboard(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_dashboard(current_user.id)


@router.get("/profile/completion", response_model=ProfileCompletionResponse)
async def get_completion(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_completion(current_user.id)


# --- Avatar ---

@router.post("/avatar", response_model=CandidateProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5 MB limit")

    # Clean up any previous avatar files for this candidate
    for allowed_ext in ALLOWED_EXTENSIONS:
        old_file = UPLOAD_DIR / f"{current_user.id}{allowed_ext}"
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                pass

    filename = f"{current_user.id}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(contents)
    avatar_url = f"/uploads/avatars/{filename}"
    return await service.upload_avatar(current_user.id, avatar_url)


@router.delete("/avatar", response_model=CandidateProfileResponse)
async def remove_avatar(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    # Clean up avatar files from disk
    for allowed_ext in ALLOWED_EXTENSIONS:
        old_file = UPLOAD_DIR / f"{current_user.id}{allowed_ext}"
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                pass
    return await service.remove_avatar(current_user.id)


# --- Education ---

@router.get("/education", response_model=list[EducationResponse])
async def list_education(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_education(current_user.id)


@router.post("/education", response_model=EducationResponse, status_code=201)
async def create_education(
    body: EducationCreate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.create_education(current_user.id, body)


@router.put("/education/{edu_id}", response_model=EducationResponse)
async def update_education(
    edu_id: uuid.UUID,
    body: EducationUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_education(current_user.id, edu_id, body)


@router.delete("/education/{edu_id}", response_model=MessageResponse)
async def delete_education(
    edu_id: uuid.UUID,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.delete_education(current_user.id, edu_id)
    return MessageResponse(message="Education record deleted")


# --- Experience ---

@router.get("/experience", response_model=list[ExperienceResponse])
async def list_experiences(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_experiences(current_user.id)


@router.post("/experience", response_model=ExperienceResponse, status_code=201)
async def create_experience(
    body: ExperienceCreate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.create_experience(current_user.id, body)


@router.put("/experience/{exp_id}", response_model=ExperienceResponse)
async def update_experience(
    exp_id: uuid.UUID,
    body: ExperienceUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_experience(current_user.id, exp_id, body)


@router.delete("/experience/{exp_id}", response_model=MessageResponse)
async def delete_experience(
    exp_id: uuid.UUID,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.delete_experience(current_user.id, exp_id)
    return MessageResponse(message="Experience record deleted")


# --- Skills ---

@router.get("/skills", response_model=list[CandidateSkillResponse])
async def list_skills(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_skills(current_user.id)


@router.post("/skills", response_model=CandidateSkillResponse, status_code=201)
async def add_skill(
    body: CandidateSkillCreate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.add_skill(current_user.id, body)


@router.put("/skills/{skill_id}", response_model=CandidateSkillResponse)
async def update_skill(
    skill_id: int,
    body: CandidateSkillUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_skill(current_user.id, skill_id, body)


@router.delete("/skills/{skill_id}", response_model=MessageResponse)
async def remove_skill(
    skill_id: int,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.remove_skill(current_user.id, skill_id)
    return MessageResponse(message="Skill removed")


@router.get("/skills/search", response_model=list[dict])
async def search_skills(
    q: str,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.search_global_skills(q)


# --- Projects ---

@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_projects(current_user.id)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.create_project(current_user.id, body)


@router.put("/projects/{proj_id}", response_model=ProjectResponse)
async def update_project(
    proj_id: uuid.UUID,
    body: ProjectUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_project(current_user.id, proj_id, body)


@router.delete("/projects/{proj_id}", response_model=MessageResponse)
async def delete_project(
    proj_id: uuid.UUID,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.delete_project(current_user.id, proj_id)
    return MessageResponse(message="Project deleted")


# --- Certifications ---

@router.get("/certifications", response_model=list[CertificationResponse])
async def list_certifications(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_certifications(current_user.id)


@router.post("/certifications", response_model=CertificationResponse, status_code=201)
async def create_certification(
    body: CertificationCreate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.create_certification(current_user.id, body)


@router.put("/certifications/{cert_id}", response_model=CertificationResponse)
async def update_certification(
    cert_id: uuid.UUID,
    body: CertificationUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_certification(current_user.id, cert_id, body)


@router.delete("/certifications/{cert_id}", response_model=MessageResponse)
async def delete_certification(
    cert_id: uuid.UUID,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.delete_certification(current_user.id, cert_id)
    return MessageResponse(message="Certification deleted")


# --- Languages ---

@router.get("/languages", response_model=list[LanguageResponse])
async def list_languages(
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_languages(current_user.id)


@router.post("/languages", response_model=LanguageResponse, status_code=201)
async def create_language(
    body: LanguageCreate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.create_language(current_user.id, body)


@router.put("/languages/{lang_id}", response_model=LanguageResponse)
async def update_language(
    lang_id: uuid.UUID,
    body: LanguageUpdate,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_language(current_user.id, lang_id, body)


@router.delete("/languages/{lang_id}", response_model=MessageResponse)
async def delete_language(
    lang_id: uuid.UUID,
    service: ProfileService = Depends(_get_profile_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.delete_language(current_user.id, lang_id)
    return MessageResponse(message="Language deleted")


# --- Notifications ---

@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    service: NotificationService = Depends(_get_notification_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_notifications(current_user.id)


@router.put("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    service: NotificationService = Depends(_get_notification_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.mark_read(current_user.id, notification_id)


@router.put("/notifications/read-all", response_model=MessageResponse)
async def mark_all_notifications_read(
    service: NotificationService = Depends(_get_notification_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.mark_all_read(current_user.id)
    return MessageResponse(message="All notifications marked as read")


@router.delete("/notifications/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: uuid.UUID,
    service: NotificationService = Depends(_get_notification_service),
    current_user: User = Depends(require_role("candidate")),
):
    await service.delete_notification(current_user.id, notification_id)
    return MessageResponse(message="Notification deleted")


@router.get("/notifications/unread-count", response_model=dict)
async def get_unread_count(
    service: NotificationService = Depends(_get_notification_service),
    current_user: User = Depends(require_role("candidate")),
):
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


# --- Account Settings ---

@router.put("/settings/password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.security import hash_password, verify_password
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user_repo = UserRepository(db)
    await user_repo.update(current_user.id, password_hash=hash_password(body.new_password))
    return MessageResponse(message="Password changed successfully")


@router.put("/settings/email", response_model=MessageResponse)
async def update_email(
    body: UpdateEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_repo = UserRepository(db)
    existing = await user_repo.get_by_email(body.new_email)
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=409, detail="Email already in use")
    await user_repo.update(current_user.id, email=body.new_email)
    return MessageResponse(message="Email updated successfully")


@router.delete("/settings/account", response_model=MessageResponse)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_repo = UserRepository(db)
    await user_repo.update(current_user.id, is_active=False)
    return MessageResponse(message="Account deactivated successfully")


# --- Resume Management ---

@router.post("/resume/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    profile_repo = CandidateProfileRepository(db)
    profile = await profile_repo.get_by_user_id(current_user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="Complete your profile before uploading a resume")

    contents = await file.read()
    try:
        resume = await service.upload_resume(
            user_id=current_user.id,
            profile_id=profile.id,
            file_content=contents,
            original_filename=file.filename or "resume.pdf",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()

    try:
        await service.process_resume(resume.id)
        await db.commit()
        await db.refresh(resume)
    except Exception as exc:
        logger.warning("Resume processing failed for %s: %s", resume.id, exc)
        await db.commit()
        await db.refresh(resume)

    return resume


@router.get("/resumes", response_model=list[ResumeResponse])
async def list_resumes(
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_resumes(current_user.id)


# --- Resume Versions (must be before /resume/{resume_id}) ---

@router.get("/resume/versions", response_model=list[ResumeVersionResponse])
async def get_resume_versions(
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_resume_versions(current_user.id)


@router.get("/resume/versions/{version_id}", response_model=ResumeCompareResponse)
async def compare_resume_version(
    version_id: uuid.UUID,
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.compare_versions(version_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Resume not found")
    return result


# --- Resume Detail ---

@router.get("/resume/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.get_resume_detail(resume_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Resume not found")
    return result


@router.delete("/resume/{resume_id}", response_model=MessageResponse)
async def delete_resume(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    deleted = await service.delete_resume(resume_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resume not found")
    return MessageResponse(message="Resume deleted")


@router.put("/resume/primary", response_model=ResumeUploadResponse)
async def set_primary_resume(
    body: ResumeSetPrimary,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    resume = await service.set_primary_resume(body.resume_id, current_user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.get("/resume/{resume_id}/download")
async def download_resume(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.download_resume(resume_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Resume file not found")
    return FileResponse(
        path=result["path"],
        filename=result["filename"],
        media_type=result["mime_type"],
    )


@router.post("/resume/{resume_id}/retry", response_model=ResumeUploadResponse)
async def retry_resume(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
):
    try:
        resume = await service.retry_parsing(resume_id, current_user.id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.commit()
        raise
    return resume


@router.get("/resume/{resume_id}/status", response_model=dict)
async def get_resume_status(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    status = await service.get_resume_status(resume_id, current_user.id)
    if not status:
        raise HTTPException(status_code=404, detail="Resume not found")
    return status


@router.get("/resume/{resume_id}/parsed", response_model=dict)
async def get_parsed_resume_data(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    data = await service.get_parsed_data(resume_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="Parsed data not found")
    return data


@router.get("/resume/{resume_id}/analysis", response_model=dict)
async def get_resume_analysis(
    resume_id: uuid.UUID,
    service: ResumeService = Depends(_get_resume_service),
    current_user: User = Depends(require_role("candidate")),
):
    analysis = await service.get_analysis(resume_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


# --- Candidate Intelligence ---

@router.get("/intelligence", response_model=CandidateIntelligence)
async def get_candidate_intelligence(
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_intelligence(current_user.id)


# --- Profile Synchronization ---

@router.get("/resume/{resume_id}/sync-diff", response_model=SyncDiffResponse)
async def get_sync_diff(
    resume_id: uuid.UUID,
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.get_sync_diff(resume_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Resume or parsed data not found")
    return result


@router.post("/resume/sync-accept", response_model=SyncActionResult)
async def sync_accept(
    body: SyncActionRequest,
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.accept_sync(body, current_user.id)


@router.post("/resume/sync-reject", response_model=SyncActionResult)
async def sync_reject(
    body: SyncActionRequest,
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.reject_sync(body, current_user.id)


@router.post("/resume/sync-merge", response_model=SyncActionResult)
async def sync_merge(
    body: SyncActionRequest,
    service: CandidateIntelligenceService = Depends(_get_intelligence_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.merge_sync(body, current_user.id)



