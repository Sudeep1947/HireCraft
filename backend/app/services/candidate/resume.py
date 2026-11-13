import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotificationType, ResumeStatus
from app.domain.models import CandidateProfile, Notification, Resume
from app.repositories.candidate.resume import (
    ParsedResumeDataRepository,
    ResumeAnalysisRepository,
    ResumeRepository,
)
from app.services.candidate.resume_analysis import ResumeAnalysisEngine
from app.services.candidate.resume_parser.engine import ResumeIntelligenceEngine

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")

UPLOAD_DIR = Path(os.getenv("RESUME_UPLOAD_DIR", "uploads/resumes"))
MAX_FILE_SIZE = 10 * 1024 * 1024
# Security: .html/.htm removed (stored XSS risk via static file serving).
# .rtf removed (known parser vulnerability vector).
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

# Magic byte signatures for allowed file types
_MAGIC_BYTES = {
    b"%PDF": ".pdf",
    b"PK": ".docx",  # ZIP-based (docx is a zip)
    b"\xd0\xcf\x11\xe0": ".doc",  # OLE2 compound
}
_MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
}


def _validate_file_content(content: bytes, expected_ext: str) -> str:
    """Validate file content matches expected extension via magic bytes.

    Returns the validated MIME type or raises ValueError.
    """
    if not content:
        raise ValueError("File is empty")

    detected_ext = None
    for signature, ext in _MAGIC_BYTES.items():
        if content[:len(signature)] == signature:
            detected_ext = ext
            break

    # Plain text files have no magic bytes — validate they are actually text
    if expected_ext == ".txt":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Text file contains invalid characters")
        return "text/plain"

    if detected_ext is None:
        raise ValueError(
            f"File content does not match any supported format. "
            f"Ensure the file is not corrupted or disguised."
        )

    if detected_ext != expected_ext:
        raise ValueError(
            f"File extension '{expected_ext}' does not match content type '{detected_ext}'"
        )

    return _MIME_MAP.get(detected_ext, "application/octet-stream")


class ResumeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.resume_repo = ResumeRepository(session)
        self.parsed_data_repo = ParsedResumeDataRepository(session)
        self.analysis_repo = ResumeAnalysisRepository(session)

    async def upload_resume(
        self,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
        file_content: bytes,
        original_filename: str,
    ) -> Resume:
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum of {MAX_FILE_SIZE // (1024*1024)} MB")

        file_hash = hashlib.sha256(file_content).hexdigest()
        existing = await self.resume_repo.find_by_hash(file_hash, user_id)
        if existing and existing.status != ResumeStatus.FAILED:
            raise ValueError("A resume with identical content already exists (duplicate)")
        if existing and existing.status == ResumeStatus.FAILED:
            await self.session.delete(existing)
            await self.session.flush()

        max_version = await self.resume_repo.get_max_version(user_id)
        storage_filename = f"{uuid.uuid4()}{ext}"
        storage_path = (UPLOAD_DIR / storage_filename).resolve()
        os.makedirs(storage_path.parent, exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(file_content)

        # Validate file content matches extension (prevents disguised files)
        mime_type = _validate_file_content(file_content, ext)
        resume = Resume(
            user_id=user_id,
            profile_id=profile_id,
            original_filename=original_filename,
            storage_path=str(storage_path),
            file_size=len(file_content),
            file_type=ext.lstrip("."),
            mime_type=mime_type,
            file_hash=file_hash,
            status=ResumeStatus.UPLOADED,
            version=max_version + 1,
        )
        is_first = await self.resume_repo.count_by_user(user_id) == 0
        resume.is_primary = is_first

        self.session.add(resume)
        await self.session.flush()

        AUDIT_LOGGER.info(
            "RESUME_UPLOAD | user=%s filename=%s size=%s hash=%s version=%s",
            user_id, original_filename, len(file_content), file_hash, max_version + 1,
        )

        return resume

    async def process_resume(self, resume_id: uuid.UUID) -> None:
        resume = await self.resume_repo.get(resume_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")

        await self.resume_repo.update_status(resume.id, ResumeStatus.PROCESSING)
        await self.session.flush()

        try:
            engine = ResumeIntelligenceEngine(resume.storage_path)
            profile, parsed = engine.parse()
            # Structured Phase-1 profile rides inside the existing JSON column
            # (no schema migration needed) alongside the legacy-compatible dict.
            parsed["resume_profile"] = profile.model_dump(mode="json")

            parsed_data = await self.parsed_data_repo.upsert_parsed(
                resume_id=resume.id,
                raw_text=parsed.get("raw_text"),
                parsed_json=parsed,
                personal_info=parsed.get("personal_info"),
                education=parsed.get("education"),
                experience=parsed.get("experience"),
                skills=parsed.get("skills"),
                projects=parsed.get("projects"),
                certifications=parsed.get("certifications"),
                languages=parsed.get("languages"),
            )

            analysis = ResumeAnalysisEngine.analyze(parsed, resume.file_type)
            await self.analysis_repo.upsert_analysis(resume_id=resume.id, **analysis)

            resume.language = parsed.get("language")
            resume.status = ResumeStatus.PARSED
            await self.session.flush()

        except Exception as e:
            logger.exception("Resume parsing failed for %s", resume_id)
            await self.resume_repo.update_status(resume_id, ResumeStatus.FAILED)
            await self.session.flush()
            raise

    async def get_resumes(self, user_id: uuid.UUID) -> list[Resume]:
        return await self.resume_repo.list_by_user(user_id)

    async def get_resume_detail(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None

        result = {"resume": resume}
        parsed = await self.parsed_data_repo.get_by_resume(resume_id)
        if parsed:
            full_json = parsed.parsed_json or {}
            result["parsed_data"] = {
                "id": parsed.id,
                "resume_id": parsed.resume_id,
                "personal_info": parsed.personal_info,
                "education": parsed.education,
                "experience": parsed.experience,
                "skills": parsed.skills,
                "projects": parsed.projects,
                "certifications": parsed.certifications,
                "languages": parsed.languages,
                "summary": full_json.get("summary"),
                "resume_profile": full_json.get("resume_profile"),
                "created_at": parsed.created_at,
            }

        analysis = await self.analysis_repo.get_by_resume(resume_id)
        if analysis:
            result["analysis"] = analysis

        return result

    async def delete_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return False

        # Best-effort file removal: a locked or missing file (e.g. cloud-sync
        # locks on Windows) must not prevent deleting the database record.
        storage_path = Path(resume.storage_path)
        try:
            if storage_path.exists():
                storage_path.unlink()
        except OSError as exc:
            logger.warning(
                "Could not remove resume file %s: %s", storage_path, exc
            )

        # Remove dependent rows explicitly so deletion works regardless of
        # DB-level cascade enforcement (ORM relationships also cascade now).
        parsed = await self.parsed_data_repo.get_by_resume(resume_id)
        if parsed:
            await self.session.delete(parsed)
        analysis = await self.analysis_repo.get_by_resume(resume_id)
        if analysis:
            await self.session.delete(analysis)

        await self.session.delete(resume)
        await self.session.flush()

        AUDIT_LOGGER.info(
            "RESUME_DELETE | user=%s resume_id=%s filename=%s",
            user_id, resume_id, resume.original_filename,
        )

        remaining = await self.resume_repo.list_by_user(user_id)
        if remaining and not any(r.is_primary for r in remaining):
            remaining[0].is_primary = True
            await self.session.flush()

        return True

    async def set_primary_resume(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> Resume | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None
        await self.resume_repo.set_primary(resume_id, user_id)
        await self.session.flush()
        return resume

    async def get_parsed_data(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None
        parsed = await self.parsed_data_repo.get_by_resume(resume_id)
        if not parsed:
            return None
        full_json = parsed.parsed_json or {}
        return {
            "resume_id": resume_id,
            "personal_info": parsed.personal_info,
            "education": parsed.education,
            "experience": parsed.experience,
            "skills": parsed.skills,
            "projects": parsed.projects,
            "certifications": parsed.certifications,
            "languages": parsed.languages,
            "summary": full_json.get("summary"),
            "resume_profile": full_json.get("resume_profile"),
        }

    async def get_analysis(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None
        analysis = await self.analysis_repo.get_by_resume(resume_id)
        if not analysis:
            return None
        return {
            "resume_id": resume_id,
            "quality_score": analysis.quality_score,
            "completeness_score": analysis.completeness_score,
            "readability_score": analysis.readability_score,
            "professionalism_score": analysis.professionalism_score,
            "keyword_optimization_score": analysis.keyword_optimization_score,
            "ats_score": analysis.ats_score,
            "missing_sections": analysis.missing_sections,
            "recommendations": analysis.recommendations,
            "section_scores": analysis.section_scores,
            "keyword_analysis": analysis.keyword_analysis,
            "formatting_issues": analysis.formatting_issues,
            "skill_analysis": analysis.skill_analysis,
            "industry_keywords": analysis.industry_keywords,
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
        }

    async def get_resume_status(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None

        progress_map = {
            ResumeStatus.UPLOADED: 10,
            ResumeStatus.PROCESSING: 50,
            ResumeStatus.PARSED: 100,
            ResumeStatus.FAILED: 100,
        }
        return {
            "id": resume.id,
            "status": resume.status.value,
            "progress": progress_map.get(resume.status, 0),
        }

    async def download_resume(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None
        storage_path = Path(resume.storage_path)
        if not storage_path.exists():
            return None
        return {
            "path": str(storage_path),
            "filename": resume.original_filename,
            "mime_type": resume.mime_type or "application/octet-stream",
        }

    async def retry_parsing(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume | None:
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if not resume:
            return None
        if resume.status != ResumeStatus.FAILED:
            raise ValueError("Only failed resumes can be retried")
        await self.process_resume(resume.id)
        return resume
