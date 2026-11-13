from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HiringRecommendation, StrengthLevel
from app.domain.models import (
    CandidateProfile,
    CandidateRanking,
    CandidateSkill,
    Certification,
    Education,
    Experience,
    Job,
    JobApplication,
    ParsedResumeData,
    Project,
    ScreeningResult,
    Skill,
    SkillGapAnalysis,
    User,
)
from app.repositories.candidate.profile import CandidateProfileRepository
from app.repositories.candidate.resume import ParsedResumeDataRepository, ResumeRepository
from app.repositories.jobs.job import JobApplicationRepository, JobRepository
from app.repositories.screening.screening import (
    CandidateRankingRepository,
    ScreeningResultRepository,
    SkillGapAnalysisRepository,
)
from app.services.screening.matching_engine import MatchingEngine
from app.services.screening.skill_gap import SkillGapAnalyzer

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")


class ScreeningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.screening_repo = ScreeningResultRepository(session)
        self.ranking_repo = CandidateRankingRepository(session)
        self.skill_gap_repo = SkillGapAnalysisRepository(session)
        self.profile_repo = CandidateProfileRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.parsed_repo = ParsedResumeDataRepository(session)
        self.job_repo = JobRepository(session)
        self.app_repo = JobApplicationRepository(session)

    # ─── Screen a single candidate for a job ────────────────────────

    async def screen_candidate(
        self,
        job: Job,
        candidate_id: uuid.UUID,
        weights: dict[str, float] | None = None,
    ) -> ScreeningResult:
        profile = await self.profile_repo.get_by_user_id(candidate_id)
        if not profile:
            raise ValueError("Candidate profile not found")

        resume = await self.resume_repo.get_primary(candidate_id)
        parsed_data: dict | None = None
        if resume:
            parsed_data = await self.parsed_repo.get_by_resume(resume.id)

        candidate_skills = await self._get_candidate_skill_names(profile)
        experiences = await self._get_experiences(profile)
        jd_skills = job.required_skills or []
        jd_preferred = job.preferred_skills or []

        skill_score, matched, miss_req, miss_pref = MatchingEngine.calculate_skill_match(
            candidate_skills, jd_skills, jd_preferred,
        )
        candidate_years = self._calculate_total_experience(experiences)
        exp_score = MatchingEngine.calculate_experience_match(
            candidate_years, job.experience_required,
        )
        degrees = await self._get_candidate_degrees(profile)
        edu_score = MatchingEngine.calculate_education_match(
            degrees, job.education_required,
        )
        proj_count, proj_techs = await self._get_project_info(profile)
        proj_score = MatchingEngine.calculate_project_match(
            proj_count, proj_techs, jd_skills,
        )
        cert_names = await self._get_candidate_certifications(profile)
        cert_score = MatchingEngine.calculate_certification_match(cert_names, None)
        loc_score = MatchingEngine.calculate_location_match(
            profile.location, job.location,
        )
        emp_type = self._get_candidate_employment_preference(experiences)
        emp_score = MatchingEngine.calculate_employment_type_match(
            emp_type, job.employment_type.value if hasattr(job.employment_type, "value") else str(job.employment_type),
        )
        jd_text = f"{job.title} {job.description} {' '.join(jd_skills)} {' '.join(jd_preferred or [])}"
        resume_text = ""
        if parsed_data:
            resume_text = (
                parsed_data.get("raw_text", "")
                if isinstance(parsed_data, dict)
                else parsed_data.raw_text or ""
            )
        semantic_score = MatchingEngine.calculate_semantic_similarity(resume_text, jd_text)

        scores_dict = {
            "skill": skill_score,
            "experience": exp_score,
            "education": edu_score,
            "project": proj_score,
            "certification": cert_score,
            "location": loc_score,
            "employment_type": emp_score,
            "semantic": semantic_score,
        }
        overall = MatchingEngine.calculate_overall_score(
            skill=skill_score,
            experience=exp_score,
            education=edu_score,
            project=proj_score,
            certification=cert_score,
            location=loc_score,
            employment_type=emp_score,
            semantic=semantic_score,
            weights=weights,
        )
        strengths = MatchingEngine.identify_strengths(scores_dict, matched)
        weaknesses = MatchingEngine.identify_weaknesses(scores_dict, miss_req, miss_pref)
        recommendation = MatchingEngine.determine_recommendation(overall)
        strength_level = MatchingEngine.determine_strength_level(overall)

        # Resolve the application (unique on job+candidate) so the persisted
        # screening result is explicitly linked to it when one exists.
        application = await self.app_repo.get_by_job_and_candidate(job.id, candidate_id)
        application_id = application.id if application else None

        existing = await self.screening_repo.get_by_job_and_candidate(job.id, candidate_id)
        if existing:
            screening = await self.screening_repo.update(
                existing.id,
                application_id=application_id,
                overall_match_score=overall,
                skill_match_score=skill_score,
                experience_match_score=exp_score,
                education_match_score=edu_score,
                project_match_score=proj_score,
                certification_match_score=cert_score,
                location_match_score=loc_score,
                employment_type_match_score=emp_score,
                semantic_match_score=semantic_score,
                matched_skills=matched,
                missing_required_skills=miss_req,
                missing_preferred_skills=miss_pref,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendation=recommendation,
                strength_level=strength_level,
                resume_id=resume.id if resume else None,
            )
        else:
            screening = await self.screening_repo.create(
                job_id=job.id,
                candidate_id=candidate_id,
                application_id=application_id,
                resume_id=resume.id if resume else None,
                overall_match_score=overall,
                skill_match_score=skill_score,
                experience_match_score=exp_score,
                education_match_score=edu_score,
                project_match_score=proj_score,
                certification_match_score=cert_score,
                location_match_score=loc_score,
                employment_type_match_score=emp_score,
                semantic_match_score=semantic_score,
                matched_skills=matched,
                missing_required_skills=miss_req,
                missing_preferred_skills=miss_pref,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendation=recommendation,
                strength_level=strength_level,
            )

        gap_data = SkillGapAnalyzer.analyze(
            matched_skills=matched,
            missing_required=miss_req,
            missing_preferred=miss_pref,
            candidate_experience_years=candidate_years,
            required_experience_str=job.experience_required,
            candidate_degrees=degrees,
            required_education=job.education_required,
            candidate_certs=cert_names,
            overall_score=overall,
        )
        existing_gap = await self.skill_gap_repo.get_by_screening_result(screening.id)
        if existing_gap:
            await self.skill_gap_repo.update(existing_gap.id, **gap_data)
        else:
            await self.skill_gap_repo.create(
                screening_result_id=screening.id, **gap_data,
            )

        AUDIT_LOGGER.info(
            "SCREENING | job=%s candidate=%s score=%d recommendation=%s",
            job.id, candidate_id, overall, recommendation,
        )
        return screening

    # ─── Screen all applicants for a job ────────────────────────────

    async def screen_job_applicants(
        self,
        job_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        weights: dict[str, float] | None = None,
    ) -> tuple[Job, int]:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            raise ValueError("Job not found or access denied")
        applications = await self.app_repo.list_by_job(job_id)
        count = 0
        for app in applications:
            await self.screen_candidate(job, app.candidate_id, weights)
            count += 1
        await self.update_rankings(job_id)
        AUDIT_LOGGER.info(
            "SCREENING_BATCH | job=%s candidates_screened=%d", job_id, count,
        )
        return job, count

    # ─── Update rankings for a job ──────────────────────────────────

    async def update_rankings(self, job_id: uuid.UUID) -> list[CandidateRanking]:
        screeners = await self.screening_repo.list_by_job(job_id)
        old_rankings = await self.ranking_repo.list_by_job(job_id)
        old_map = {r.candidate_id: r for r in old_rankings}
        await self.ranking_repo.delete_by_job(job_id)

        ranked: list[CandidateRanking] = []
        for idx, scr in enumerate(screeners):
            rank = idx + 1
            old = old_map.get(scr.candidate_id)
            prev_rank = old.rank if old else None
            change = 0
            if prev_rank is not None:
                change = prev_rank - rank
            ranking = await self.ranking_repo.create(
                job_id=job_id,
                candidate_id=scr.candidate_id,
                screening_result_id=scr.id,
                rank=rank,
                previous_rank=prev_rank,
                rank_change=change,
                overall_score=scr.overall_match_score,
                strength_level=scr.strength_level,
            )
            ranked.append(ranking)
        return ranked

    # ─── Get ranked applicants ──────────────────────────────────────

    async def get_ranked_applicants(
        self,
        job_id: uuid.UUID,
        recruiter_id: uuid.UUID,
    ) -> tuple[Job, list[CandidateRanking]]:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            raise ValueError("Job not found or access denied")
        rankings = await self.ranking_repo.list_by_job(job_id)
        return job, rankings

    # ─── Compare candidates ─────────────────────────────────────────

    async def compare_candidates(
        self,
        job_id: uuid.UUID,
        candidate_ids: list[uuid.UUID],
        recruiter_id: uuid.UUID,
    ) -> dict:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            raise ValueError("Job not found or access denied")
        items = []
        for cid in candidate_ids:
            screening = await self.screening_repo.get_by_job_and_candidate(job_id, cid)
            if not screening:
                continue
            user = await self.session.get(User, cid)
            items.append({
                "candidate_id": cid,
                "candidate_name": user.full_name if user else "",
                "candidate_email": user.email if user else "",
                "overall_match_score": screening.overall_match_score,
                "skill_match_score": screening.skill_match_score,
                "experience_match_score": screening.experience_match_score,
                "education_match_score": screening.education_match_score,
                "project_match_score": screening.project_match_score,
                "certification_match_score": screening.certification_match_score,
                "matched_skills": screening.matched_skills,
                "missing_required_skills": screening.missing_required_skills,
                "strengths": screening.strengths,
                "weaknesses": screening.weaknesses,
                "recommendation": screening.recommendation,
                "strength_level": screening.strength_level,
            })
        return {
            "job_id": job_id,
            "job_title": job.title,
            "candidates": items,
        }

    # ─── Candidate match report ─────────────────────────────────────

    async def get_candidate_match_report(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> dict | None:
        screening = await self.screening_repo.get_by_job_and_candidate(job_id, candidate_id)
        if not screening:
            return None
        gap = await self.skill_gap_repo.get_by_screening_result(screening.id)
        job = await self.session.get(Job, job_id)
        user = await self.session.get(User, candidate_id)
        return {
            "job_id": job_id,
            "job_title": job.title if job else "",
            "candidate_id": candidate_id,
            "candidate_name": user.full_name if user else "",
            "screening": screening,
            "skill_gap": gap,
            "interview_readiness_score": gap.interview_readiness_score if gap else None,
            "improvement_suggestions": gap.improvement_suggestions if gap else None,
        }

    # ─── Candidate self-match view ──────────────────────────────────

    async def get_my_match_for_job(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> dict | None:
        job = await self.session.get(Job, job_id)
        if not job:
            return None
        return await self.get_candidate_match_report(job_id, candidate_id)

    # ─── Helpers ─────────────────────────────────────────────────────

    async def _get_candidate_skill_names(self, profile: CandidateProfile) -> list[str]:
        from sqlalchemy import select as sa_select
        stmt = (
            sa_select(CandidateSkill, Skill)
            .join(Skill, CandidateSkill.skill_id == Skill.id)
            .where(CandidateSkill.profile_id == profile.id)
        )
        result = await self.session.execute(stmt)
        pairs = result.all()
        return [pair[1].name for pair in pairs]

    async def _get_candidate_degrees(self, profile: CandidateProfile) -> list[str]:
        from sqlalchemy import select
        from app.domain.models import Education
        stmt = select(Education.degree).where(Education.profile_id == profile.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_project_info(self, profile: CandidateProfile) -> tuple[int, list[str]]:
        from sqlalchemy import select
        from app.domain.models import Project
        stmt = select(Project).where(Project.profile_id == profile.id)
        result = await self.session.execute(stmt)
        projects = list(result.scalars().all())
        all_techs: list[str] = []
        for p in projects:
            if p.technologies:
                all_techs.extend([t.strip() for t in p.technologies.split(",") if t.strip()])
        return len(projects), all_techs

    async def _get_candidate_certifications(self, profile: CandidateProfile) -> list[str]:
        from sqlalchemy import select
        from app.domain.models import Certification
        stmt = select(Certification.name).where(Certification.profile_id == profile.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_experiences(self, profile: CandidateProfile) -> list[dict]:
        from sqlalchemy import select
        stmt = select(Experience).where(Experience.profile_id == profile.id)
        result = await self.session.execute(stmt)
        exps = result.scalars().all()
        return [
            {
                "start_date": str(e.start_date) if e.start_date else "",
                "end_date": str(e.end_date) if e.end_date else "",
                "is_current": e.is_current,
                "employment_type": e.employment_type.value if hasattr(e.employment_type, "value") else str(e.employment_type) if e.employment_type else None,
            }
            for e in exps
        ]

    @staticmethod
    def _calculate_total_experience(experiences: list[dict]) -> float:
        from datetime import date
        total_months = 0.0
        for exp in experiences:
            start_str = exp.get("start_date", "")
            end_str = exp.get("end_date", "")
            is_current = exp.get("is_current", False)
            if not start_str:
                continue
            try:
                parts = start_str.split("-")
                start = date(int(parts[0]), int(parts[1]), int(parts[2]))
                if is_current:
                    end = date.today()
                elif end_str:
                    parts2 = end_str.split("-")
                    end = date(int(parts2[0]), int(parts2[1]), int(parts2[2]))
                else:
                    continue
                delta_months = (end.year - start.year) * 12 + (end.month - start.month)
                total_months += max(delta_months, 0)
            except (ValueError, IndexError):
                continue
        return round(total_months / 12, 1)

    @staticmethod
    def _get_candidate_employment_preference(experiences: list[dict]) -> str | None:
        for exp in experiences:
            if exp.get("is_current") and exp.get("employment_type"):
                return exp["employment_type"]
        return None
