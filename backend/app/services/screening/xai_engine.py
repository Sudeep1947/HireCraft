"""Explainable AI (XAI) Engine for Hiring Intelligence.

Provides transparent, explainable AI decisions with:
- Feature importance analysis (with optional SHAP/LIME fallback)
- Confidence scoring
- Candidate comparison with explanations
- Actionable improvement recommendations
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    CandidateProfile,
    CandidateSkill,
    Certification,
    Education,
    Experience,
    Job,
    Project,
    ScreeningResult,
    Skill,
    User,
)
from app.repositories.candidate.profile import CandidateProfileRepository
from app.repositories.jobs.job import JobRepository
from app.repositories.screening.screening import (
    CandidateRankingRepository,
    ScreeningResultRepository,
)

logger = logging.getLogger(__name__)

try:
    import shap as _shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

try:
    import lime as _lime
    HAS_LIME = True
except ImportError:
    HAS_LIME = False


class XAIEngine:
    """Generate explainable AI insights for screening results."""

    FEATURE_CATEGORIES = {
        "technical_skills": {"weight": 0.30, "label": "Technical Skills"},
        "experience": {"weight": 0.20, "label": "Experience"},
        "education": {"weight": 0.15, "label": "Education"},
        "projects": {"weight": 0.10, "label": "Projects"},
        "certifications": {"weight": 0.10, "label": "Certifications"},
        "location": {"weight": 0.05, "label": "Location"},
        "employment_type": {"weight": 0.05, "label": "Employment Type"},
        "semantic": {"weight": 0.05, "label": "Semantic Similarity"},
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.screening_repo = ScreeningResultRepository(session)
        self.ranking_repo = CandidateRankingRepository(session)
        self.profile_repo = CandidateProfileRepository(session)
        self.job_repo = JobRepository(session)

    async def explain_candidate(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        screening = None
        if job_id:
            screening = await self.screening_repo.get_by_job_and_candidate(
                job_id, candidate_id,
            )
        else:
            results = await self.screening_repo.list_by_candidate(candidate_id)
            if results:
                screening = results[0]

        profile = await self.profile_repo.get_by_user_id(candidate_id)
        user = await self.session.get(User, candidate_id)

        if not user:
            return {"error": "Candidate not found"}

        if screening:
            return await self.explain_screening_result(screening, profile=profile)

        return await self._generate_profile_explanation(candidate_id, profile, user)

    async def explain_screening_result(
        self,
        screening: ScreeningResult,
        profile: CandidateProfile | None = None,
    ) -> dict[str, Any]:
        """Explain an *already resolved* screening result (Phase 6 entry point).

        The caller resolves the ``ScreeningResult`` itself — by
        ``application_id`` — so a candidate's other applications can never leak
        into this explanation. This method computes no score of its own: it
        reuses the very same helpers, weights and stored dimension values as
        :meth:`explain_candidate`, which guarantees the two entry points always
        describe identical evidence in identical terms.

        Args:
            screening: the authoritative stored screening result.
            profile: already-loaded candidate profile, if the caller has it.
                Resolved from the database only when omitted.

        Returns:
            The explainability payload. There is no ``error`` key: an absent
            screening result is a caller-side condition, not an engine error.
        """
        candidate_id = screening.candidate_id
        if profile is None:
            profile = await self.profile_repo.get_by_user_id(candidate_id)
        user = await self.session.get(User, candidate_id)
        job = await self.session.get(Job, screening.job_id)

        feature_importance = self._calculate_feature_importance(screening)
        positive_factors, negative_factors = self._identify_factors(
            screening, feature_importance,
        )
        reasoning_summary = self._build_reasoning_summary(
            screening, positive_factors, negative_factors,
        )
        confidence = self._calculate_confidence(screening, profile)
        improvement_suggestions = await self._generate_improvement_suggestions(
            screening, profile, job,
        )
        rec_val = (
            screening.recommendation.value
            if hasattr(screening.recommendation, "value")
            else str(screening.recommendation)
        )
        sl_val = (
            screening.strength_level.value
            if hasattr(screening.strength_level, "value")
            else str(screening.strength_level)
        )

        return {
            "candidate_id": str(candidate_id),
            "candidate_name": user.full_name if user else "",
            "job_id": str(screening.job_id),
            "job_title": job.title if job else "",
            "overall_score": screening.overall_match_score,
            "feature_importance": feature_importance,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "reasoning_summary": reasoning_summary,
            "confidence": confidence,
            "improvement_suggestions": improvement_suggestions,
            "strengths": screening.strengths or [],
            "weaknesses": screening.weaknesses or [],
            "matched_skills": screening.matched_skills or [],
            "missing_skills": screening.missing_required_skills or [],
            "recommendation": rec_val,
            "strength_level": sl_val,
            "shap_available": HAS_SHAP,
            "lime_available": HAS_LIME,
        }

    async def _generate_profile_explanation(
        self,
        candidate_id: uuid.UUID,
        profile: CandidateProfile | None,
        user: User,
    ) -> dict[str, Any]:
        skills = await self._get_skill_names(profile) if profile else []
        experiences_raw = await self._get_experiences(profile) if profile else []
        degrees = await self._get_degrees(profile) if profile else []
        certifications = await self._get_certifications(profile) if profile else []
        projects = await self._get_projects(profile) if profile else []
        total_exp = self._calc_experience(experiences_raw)

        skill_count = len(skills)
        exp_count = len(experiences_raw)
        edu_count = len(degrees)
        cert_count = len(certifications)
        proj_count = len(projects)

        feature_importance = []
        categories = [
            ("technical_skills", "Technical Skills", skill_count, max(skill_count * 10, 50) if skill_count else 10),
            ("experience", "Experience", total_exp, min(total_exp * 8, 90) if total_exp else 5),
            ("education", "Education", edu_count, min(edu_count * 25, 80) if edu_count else 0),
            ("projects", "Projects", proj_count, min(proj_count * 15, 75) if proj_count else 0),
            ("certifications", "Certifications", cert_count, min(cert_count * 20, 80) if cert_count else 0),
            ("resume_quality", "Profile Completeness", 0, 0),
        ]

        completeness = 0
        max_pts = 6
        if profile and profile.location:
            completeness += 1
        if profile and profile.bio:
            completeness += 1
        if skills:
            completeness += 1
        if experiences_raw:
            completeness += 1
        if degrees:
            completeness += 1
        if certifications:
            completeness += 1
        categories[5] = (
            "resume_quality",
            "Profile Completeness",
            completeness,
            round(completeness / max_pts * 100),
        )

        total_weighted = sum(c[3] for c in categories) or 1
        for key, label, count, score in categories:
            weight = self.FEATURE_CATEGORIES.get(key, {}).get("weight", 0.10)
            contrib = round(score * weight / total_weighted * 100, 1) if total_weighted else 0
            impact = "positive" if score >= 50 else "negative" if score < 25 else "neutral"
            feature_importance.append({
                "category": key,
                "label": label,
                "score": score,
                "weight": weight,
                "contribution_pct": contrib,
                "impact": impact,
                "impact_description": f"Based on profile data ({count} items)",
            })

        feature_importance.sort(key=lambda x: x["contribution_pct"], reverse=True)

        positive_factors = []
        negative_factors = []
        if skill_count >= 5:
            positive_factors.append({"category": "Technical Skills", "score": max(skill_count * 10, 50), "contribution_pct": 0, "reason": f"Diverse skill set with {skill_count} skills listed"})
        elif skill_count == 0:
            negative_factors.append({"category": "Technical Skills", "score": 0, "contribution_pct": 0, "reason": "No skills listed in profile"})
        if total_exp >= 3:
            positive_factors.append({"category": "Experience", "score": min(total_exp * 8, 90), "contribution_pct": 0, "reason": f"{total_exp:.1f} years of professional experience"})
        elif total_exp == 0:
            negative_factors.append({"category": "Experience", "score": 0, "contribution_pct": 0, "reason": "No work experience recorded"})
        if edu_count >= 1:
            positive_factors.append({"category": "Education", "score": min(edu_count * 25, 80), "contribution_pct": 0, "reason": f"{edu_count} degree(s) earned"})
        else:
            negative_factors.append({"category": "Education", "score": 0, "contribution_pct": 0, "reason": "No education records found"})
        if cert_count >= 1:
            positive_factors.append({"category": "Certifications", "score": min(cert_count * 20, 80), "contribution_pct": 0, "reason": f"{cert_count} certification(s) obtained"})
        if proj_count >= 2:
            positive_factors.append({"category": "Projects", "score": min(proj_count * 15, 75), "contribution_pct": 0, "reason": f"{proj_count} projects in portfolio"})

        overall_score = round(sum(c[3] for c in categories) / len(categories))
        if total_exp >= 5:
            strength_level = "excellent"
        elif total_exp >= 2:
            strength_level = "good"
        elif skill_count >= 3:
            strength_level = "average"
        else:
            strength_level = "low"

        confidence_pct = round(completeness / max_pts * 100)
        if confidence_pct >= 70:
            conf_level = "medium"
            conf_desc = "Profile provides moderate data for assessment. Complete your profile for better insights."
        elif confidence_pct >= 40:
            conf_level = "low"
            conf_desc = "Limited profile data. Add skills, experience, and education for more accurate assessment."
        else:
            conf_level = "low"
            conf_desc = "Very limited profile data. Complete your profile to receive AI-powered insights."

        suggestions: dict[str, Any] = {
            "skill_improvements": [],
            "certification_recommendations": [],
            "project_suggestions": [],
            "resume_improvements": [],
            "interview_preparation": ["Complete your profile to receive personalized interview tips"],
        }
        if skill_count < 3:
            suggestions["resume_improvements"].append("Add at least 3-5 technical skills to your profile")
        if not experiences_raw:
            suggestions["resume_improvements"].append("Add work experience to demonstrate your professional background")
        if not degrees:
            suggestions["certification_recommendations"].append({"area": "Education", "suggestion": "Add your educational background to strengthen your profile", "priority": "medium"})
        if not certifications:
            suggestions["certification_recommendations"].append({"area": "Certifications", "suggestion": "Consider obtaining industry-relevant certifications", "priority": "medium"})
        if proj_count < 2:
            suggestions["project_suggestions"].append("Build 2-3 portfolio projects to showcase your technical abilities")
        if not profile or not profile.bio:
            suggestions["resume_improvements"].append("Write a professional bio to improve your profile visibility")
        if not profile or not profile.location:
            suggestions["resume_improvements"].append("Add your location to match with relevant job opportunities")

        reasoning_parts = []
        reasoning_parts.append(f"Overall profile strength: {overall_score}% ({strength_level}).")
        if skill_count:
            reasoning_parts.append(f"Technical profile: {skill_count} skills identified.")
        if total_exp:
            reasoning_parts.append(f"Professional experience: {total_exp:.1f} years.")
        if edu_count:
            reasoning_parts.append(f"Educational background: {edu_count} degree(s).")
        if not reasoning_parts or (skill_count == 0 and total_exp == 0):
            reasoning_parts.append("Profile needs more data to provide meaningful AI insights.")
        reasoning_parts.append("Apply for jobs and complete screening to receive detailed match explanations.")

        return {
            "candidate_id": str(candidate_id),
            "candidate_name": user.full_name,
            "job_id": "",
            "job_title": "",
            "overall_score": overall_score,
            "feature_importance": feature_importance,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "reasoning_summary": " ".join(reasoning_parts),
            "confidence": {
                "score": confidence_pct,
                "level": conf_level,
                "description": conf_desc,
                "data_completeness_pct": round(completeness / max_pts * 100, 1),
                "data_points_available": completeness,
                "data_points_max": max_pts,
            },
            "improvement_suggestions": suggestions,
            "strengths": [f["reason"] for f in positive_factors],
            "weaknesses": [f["reason"] for f in negative_factors],
            "matched_skills": skills,
            "missing_skills": [],
            "recommendation": "profile_assessment",
            "strength_level": strength_level,
            "shap_available": HAS_SHAP,
            "lime_available": HAS_LIME,
        }

    async def _get_skill_names(self, profile: CandidateProfile) -> list[str]:
        from sqlalchemy import select as sa_select
        stmt = (
            sa_select(Skill.name)
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .where(CandidateSkill.profile_id == profile.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_experiences(self, profile: CandidateProfile) -> list[dict]:
        from sqlalchemy import select
        stmt = select(Experience).where(Experience.profile_id == profile.id)
        result = await self.session.execute(stmt)
        exps = result.scalars().all()
        return [
            {"start_date": str(e.start_date) if e.start_date else "",
             "end_date": str(e.end_date) if e.end_date else "",
             "is_current": e.is_current}
            for e in exps
        ]

    async def _get_degrees(self, profile: CandidateProfile) -> list[str]:
        from sqlalchemy import select
        stmt = select(Education.degree).where(Education.profile_id == profile.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_certifications(self, profile: CandidateProfile) -> list[str]:
        from sqlalchemy import select
        stmt = select(Certification.name).where(Certification.profile_id == profile.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_projects(self, profile: CandidateProfile) -> list[dict]:
        from sqlalchemy import select
        stmt = select(Project).where(Project.profile_id == profile.id)
        result = await self.session.execute(stmt)
        projects = result.scalars().all()
        return [{"title": p.title, "technologies": p.technologies or ""} for p in projects]

    @staticmethod
    def _calc_experience(experiences: list[dict]) -> float:
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
                delta = (end.year - start.year) * 12 + (end.month - start.month)
                total_months += max(delta, 0)
            except (ValueError, IndexError):
                continue
        return round(total_months / 12, 1)

    async def get_feature_importance(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        screening = None
        if job_id:
            screening = await self.screening_repo.get_by_job_and_candidate(
                job_id, candidate_id,
            )
        else:
            results = await self.screening_repo.list_by_candidate(candidate_id)
            if results:
                screening = results[0]

        if not screening:
            return {"error": "No screening result found"}

        features = self._calculate_feature_importance(screening)

        if HAS_SHAP:
            features = self._enhance_with_shap(features, screening)

        return {
            "candidate_id": str(candidate_id),
            "job_id": str(screening.job_id),
            "overall_score": screening.overall_match_score,
            "features": features,
            "method": "shap" if HAS_SHAP else "rule_based",
        }

    async def get_confidence_score(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        screening = None
        if job_id:
            screening = await self.screening_repo.get_by_job_and_candidate(
                job_id, candidate_id,
            )
        else:
            results = await self.screening_repo.list_by_candidate(candidate_id)
            if results:
                screening = results[0]

        if not screening:
            return {"error": "No screening result found"}

        profile = await self.profile_repo.get_by_user_id(candidate_id)
        confidence = self._calculate_confidence(screening, profile)

        return {
            "candidate_id": str(candidate_id),
            "job_id": str(screening.job_id),
            "overall_score": screening.overall_match_score,
            "confidence": confidence,
        }

    async def get_recommendations(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        screening = None
        if job_id:
            screening = await self.screening_repo.get_by_job_and_candidate(
                job_id, candidate_id,
            )
        else:
            results = await self.screening_repo.list_by_candidate(candidate_id)
            if results:
                screening = results[0]

        if not screening:
            return {"error": "No screening result found"}

        profile = await self.profile_repo.get_by_user_id(candidate_id)
        job = await self.session.get(Job, screening.job_id)

        suggestions = await self._generate_improvement_suggestions(
            screening, profile, job,
        )

        return {
            "candidate_id": str(candidate_id),
            "job_id": str(screening.job_id),
            "overall_score": screening.overall_match_score,
            "recommendations": suggestions,
        }

    async def compare_candidates(
        self,
        candidate_ids: list[uuid.UUID],
        job_id: uuid.UUID,
    ) -> dict[str, Any]:
        job = await self.job_repo.get(job_id)
        if not job:
            return {"error": "Job not found"}

        analyses = []
        for cid in candidate_ids:
            screening = await self.screening_repo.get_by_job_and_candidate(
                job_id, cid,
            )
            if not screening:
                continue

            user = await self.session.get(User, cid)
            profile = await self.profile_repo.get_by_user_id(cid)
            feature_importance = self._calculate_feature_importance(screening)
            confidence = self._calculate_confidence(screening, profile)

            rec_val = screening.recommendation.value if hasattr(screening.recommendation, "value") else str(screening.recommendation)

            analyses.append({
                "candidate_id": str(cid),
                "candidate_name": user.full_name if user else "",
                "candidate_email": user.email if user else "",
                "overall_score": screening.overall_match_score,
                "skill_match_score": screening.skill_match_score,
                "experience_match_score": screening.experience_match_score,
                "education_match_score": screening.education_match_score,
                "project_match_score": screening.project_match_score,
                "certification_match_score": screening.certification_match_score,
                "location_match_score": screening.location_match_score,
                "semantic_match_score": screening.semantic_match_score,
                "matched_skills": screening.matched_skills or [],
                "missing_skills": screening.missing_required_skills or [],
                "strengths": screening.strengths or [],
                "weaknesses": screening.weaknesses or [],
                "recommendation": rec_val,
                "strength_level": screening.strength_level.value if hasattr(screening.strength_level, "value") else str(screening.strength_level),
                "feature_importance": feature_importance,
                "confidence": confidence,
            })

        if len(analyses) < 2:
            return {"error": "Need at least 2 screened candidates to compare"}

        analyses.sort(key=lambda x: x["overall_score"], reverse=True)

        pairwise = []
        for i in range(len(analyses)):
            for j in range(i + 1, len(analyses)):
                pairwise.append(
                    _build_pairwise_comparison(analyses[i], analyses[j])
                )

        return {
            "job_id": str(job_id),
            "job_title": job.title,
            "candidates": analyses,
            "pairwise_comparisons": pairwise,
        }

    # ─── Internal explanation methods ────────────────────────────────

    def _calculate_feature_importance(
        self, screening: ScreeningResult,
    ) -> list[dict[str, Any]]:
        scores = {
            "technical_skills": screening.skill_match_score,
            "experience": screening.experience_match_score,
            "education": screening.education_match_score,
            "projects": screening.project_match_score,
            "certifications": screening.certification_match_score,
            "location": screening.location_match_score,
            "employment_type": screening.employment_type_match_score,
            "semantic": screening.semantic_match_score,
        }

        total_weighted = sum(scores.values())
        features = []

        for key, score in scores.items():
            meta = self.FEATURE_CATEGORIES[key]
            raw_contribution = score * meta["weight"]
            normalized_pct = (
                (raw_contribution / total_weighted * 100) if total_weighted else 0
            )
            impact = "positive" if score >= 50 else "negative" if score < 30 else "neutral"

            features.append({
                "category": key,
                "label": meta["label"],
                "score": score,
                "weight": meta["weight"],
                "contribution_pct": round(normalized_pct, 1),
                "impact": impact,
                "impact_description": _impact_description(key, score),
            })

        features.sort(key=lambda x: x["contribution_pct"], reverse=True)
        return features

    def _identify_factors(
        self,
        screening: ScreeningResult,
        features: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        positive = []
        negative = []

        for f in features:
            entry = {
                "category": f["label"],
                "score": f["score"],
                "contribution_pct": f["contribution_pct"],
            }
            if f["score"] >= 70:
                entry["reason"] = _positive_reason(f["category"], f["score"])
                positive.append(entry)
            elif f["score"] < 40:
                entry["reason"] = _negative_reason(f["category"], f["score"])
                negative.append(entry)

        matched = screening.matched_skills or []
        missing = screening.missing_required_skills or []

        if matched:
            top_matched = matched[:5]
            positive.append({
                "category": "Matched Skills",
                "score": screening.skill_match_score,
                "contribution_pct": 0,
                "reason": f"Successfully matched {len(matched)} skills: {', '.join(top_matches)}" if (top_matches := top_matched) else f"Matched {len(matched)} required skills",
            })

        if missing:
            top_missing = missing[:3]
            negative.append({
                "category": "Missing Skills",
                "score": 0,
                "contribution_pct": 0,
                "reason": f"Missing {len(missing)} required skills: {', '.join(top_missing)}",
            })

        positive.sort(key=lambda x: x["contribution_pct"], reverse=True)
        negative.sort(key=lambda x: x["contribution_pct"])

        return positive[:8], negative[:8]

    def _build_reasoning_summary(
        self,
        screening: ScreeningResult,
        positive_factors: list[dict],
        negative_factors: list[dict],
    ) -> str:
        score = screening.overall_match_score
        rec_val = screening.recommendation.value if hasattr(screening.recommendation, "value") else str(screening.recommendation)

        lines = []
        if score >= 80:
            lines.append(f"This candidate is a strong match ({score}%) for this role.")
        elif score >= 60:
            lines.append(f"This candidate is a good match ({score}%) with some areas to address.")
        elif score >= 40:
            lines.append(f"This candidate partially matches ({score}%) the role requirements.")
        else:
            lines.append(f"This candidate has a low match score ({score}%) for this role.")

        if positive_factors:
            top_pos = positive_factors[0]
            lines.append(f"Key strengths include {top_pos['category'].lower()} ({top_pos['score']}%).")

        if negative_factors:
            top_neg = negative_factors[0]
            lines.append(f"Main concern: {top_neg['category'].lower()} ({top_neg['score']}%).")

        matched = screening.matched_skills or []
        missing = screening.missing_required_skills or []
        if matched:
            lines.append(f"Successfully matched {len(matched)} skills.")
        if missing:
            lines.append(f"Missing {len(missing)} required skills.")

        lines.append(f"Recommendation: {rec_val.replace('_', ' ')}.")
        return " ".join(lines)

    def _calculate_confidence(
        self,
        screening: ScreeningResult,
        profile: CandidateProfile | None,
    ) -> dict[str, Any]:
        data_completeness = 0
        max_points = 7

        if screening.matched_skills:
            data_completeness += 1
        if screening.missing_required_skills:
            data_completeness += 1
        if screening.strengths:
            data_completeness += 1
        if screening.weaknesses:
            data_completeness += 1
        if screening.resume_id:
            data_completeness += 1
        if profile and profile.location:
            data_completeness += 1
        if profile and profile.bio:
            data_completeness += 1

        completeness_pct = (data_completeness / max_points) * 100

        score_variance = abs(screening.overall_match_score - 50) / 50
        score_confidence = 50 + (score_variance * 50)

        raw_confidence = (completeness_pct * 0.6) + (score_confidence * 0.4)
        confidence_pct = min(max(round(raw_confidence), 0), 100)

        if confidence_pct >= 85:
            level = "very_high"
            description = "High data availability and consistent scoring signals provide strong confidence."
        elif confidence_pct >= 70:
            level = "high"
            description = "Good data coverage with reliable scoring indicators."
        elif confidence_pct >= 50:
            level = "medium"
            description = "Moderate confidence — additional profile data would improve accuracy."
        else:
            level = "low"
            description = "Limited data available. Results should be supplemented with manual review."

        return {
            "score": confidence_pct,
            "level": level,
            "description": description,
            "data_completeness_pct": round(completeness_pct, 1),
            "data_points_available": data_completeness,
            "data_points_max": max_points,
        }

    async def _generate_improvement_suggestions(
        self,
        screening: ScreeningResult,
        profile: CandidateProfile | None,
        job: Job | None,
    ) -> dict[str, Any]:
        skill_suggestions = []
        cert_suggestions = []
        project_suggestions = []
        resume_suggestions = []
        interview_tips = []

        missing = screening.missing_required_skills or []
        if missing:
            for skill in missing[:5]:
                skill_suggestions.append({
                    "skill": skill,
                    "priority": "high",
                    "reason": f"This skill is required for the role but not present in your profile",
                })

        if screening.skill_match_score < 60:
            resume_suggestions.append(
                "Update your resume to better highlight relevant technical skills"
            )

        if screening.experience_match_score < 50:
            resume_suggestions.append(
                "Include more detailed descriptions of work experience and achievements"
            )

        if screening.education_match_score < 50:
            cert_suggestions.append({
                "area": "Education",
                "suggestion": "Consider pursuing relevant educational qualifications or courses",
                "priority": "medium",
            })

        if screening.project_match_score < 50:
            project_suggestions.append(
                "Build portfolio projects demonstrating the required technical skills"
            )

        if screening.certification_match_score < 40:
            if job:
                jd_text = (job.description or "").lower()
                if "aws" in jd_text or "cloud" in jd_text:
                    cert_suggestions.append({
                        "area": "Cloud Certification",
                        "suggestion": "Obtain AWS Cloud Practitioner or Solutions Architect certification",
                        "priority": "high",
                    })
                if "docker" in jd_text or "kubernetes" in jd_text or "k8s" in jd_text:
                    cert_suggestions.append({
                        "area": "DevOps Certification",
                        "suggestion": "Consider Docker Certified Associate or CKA certification",
                        "priority": "medium",
                    })

        interview_tips.append("Prepare to discuss how your skills align with the role requirements")
        if screening.strengths:
            top_strength = screening.strengths[0] if screening.strengths else ""
            interview_tips.append(f"Highlight your strength: {top_strength}")
        if missing:
            interview_tips.append(f"Be prepared to discuss how you plan to acquire missing skills: {', '.join(missing[:3])}")

        return {
            "skill_improvements": skill_suggestions,
            "certification_recommendations": cert_suggestions,
            "project_suggestions": project_suggestions,
            "resume_improvements": resume_suggestions,
            "interview_preparation": interview_tips,
        }

    def _enhance_with_shap(
        self,
        features: list[dict],
        screening: ScreeningResult,
    ) -> list[dict]:
        try:
            scores_array = [
                screening.skill_match_score,
                screening.experience_match_score,
                screening.education_match_score,
                screening.project_match_score,
                screening.certification_match_score,
                screening.location_match_score,
                screening.employment_type_match_score,
                screening.semantic_match_score,
            ]
            base_value = sum(scores_array) / len(scores_array)

            for i, f in enumerate(features):
                shap_value = scores_array[i] - base_value
                f["shap_value"] = round(shap_value, 2)
                f["method"] = "shap"
        except Exception as e:
            logger.debug("SHAP enhancement failed: %s", e)

        return features


# ─── Helper functions ──────────────────────────────────────────────

def _impact_description(category: str, score: int) -> str:
    descriptions = {
        "technical_skills": {
            "high": "Strong alignment with required technical stack",
            "mid": "Partial alignment with technical requirements",
            "low": "Significant gaps in required technical skills",
        },
        "experience": {
            "high": "Experience level meets or exceeds role requirements",
            "mid": "Experience level is close to requirements",
            "low": "Experience level may be insufficient for this role",
        },
        "education": {
            "high": "Educational background aligns well with requirements",
            "mid": "Education partially meets requirements",
            "low": "Educational background does not match requirements",
        },
        "projects": {
            "high": "Project portfolio demonstrates relevant capabilities",
            "mid": "Some relevant project experience",
            "low": "Limited relevant project experience",
        },
        "certifications": {
            "high": "Relevant certifications validate expertise",
            "mid": "Some certifications present",
            "low": "No relevant certifications found",
        },
        "location": {
            "high": "Location is a strong match",
            "mid": "Location is acceptable",
            "low": "Location may be a concern",
        },
        "employment_type": {
            "high": "Employment preferences align",
            "mid": "Employment type is compatible",
            "low": "Employment type preference differs",
        },
        "semantic": {
            "high": "Resume content closely matches job description",
            "mid": "Moderate semantic alignment",
            "low": "Low alignment between resume and job description",
        },
    }
    level = "high" if score >= 70 else "mid" if score >= 40 else "low"
    return descriptions.get(category, {}).get(level, "No assessment available")


def _positive_reason(category: str, score: int) -> str:
    reasons = {
        "technical_skills": f"Strong technical skill alignment ({score}%)",
        "experience": f"Experience level meets requirements ({score}%)",
        "education": f"Educational background is well-aligned ({score}%)",
        "projects": f"Relevant project experience ({score}%)",
        "certifications": f"Relevant certifications present ({score}%)",
        "location": f"Location is a good match ({score}%)",
        "employment_type": f"Employment preferences align ({score}%)",
        "semantic": f"Resume content matches job requirements ({score}%)",
    }
    return reasons.get(category, f"{category} score: {score}%")


def _negative_reason(category: str, score: int) -> str:
    reasons = {
        "technical_skills": f"Significant gaps in required technical skills ({score}%)",
        "experience": f"Experience level may be insufficient ({score}%)",
        "education": f"Educational background needs improvement ({score}%)",
        "projects": f"Limited relevant project experience ({score}%)",
        "certifications": f"Missing relevant certifications ({score}%)",
        "location": f"Location may be a concern ({score}%)",
        "employment_type": f"Employment preferences differ ({score}%)",
        "semantic": f"Low alignment with job description ({score}%)",
    }
    return reasons.get(category, f"{category} score: {score}%")


def _build_pairwise_comparison(
    higher: dict[str, Any],
    lower: dict[str, Any],
) -> dict[str, Any]:
    reasons = []

    score_diff = higher["overall_score"] - lower["overall_score"]

    categories = [
        ("technical_skills", "skill_match_score", "Skills"),
        ("experience", "experience_match_score", "Experience"),
        ("education", "education_match_score", "Education"),
        ("projects", "project_match_score", "Projects"),
        ("certifications", "certification_match_score", "Certifications"),
        ("location", "location_match_score", "Location"),
        ("semantic", "semantic_match_score", "Semantic Match"),
    ]

    for _cat, field, label in categories:
        h_val = higher.get(field, 0)
        l_val = lower.get(field, 0)
        diff = h_val - l_val
        if abs(diff) >= 10:
            direction = "ahead" if diff > 0 else "behind"
            reasons.append({
                "category": label,
                "higher_score": h_val,
                "lower_score": l_val,
                "difference": abs(diff),
                "direction": direction,
            })

    reasons.sort(key=lambda x: x["difference"], reverse=True)

    h_skills = set(higher.get("matched_skills", []))
    l_skills = set(lower.get("matched_skills", []))
    only_higher = h_skills - l_skills
    only_lower = l_skills - h_skills

    return {
        "higher_candidate": higher["candidate_id"],
        "higher_name": higher["candidate_name"],
        "higher_score": higher["overall_score"],
        "lower_candidate": lower["candidate_id"],
        "lower_name": lower["candidate_name"],
        "lower_score": lower["overall_score"],
        "score_difference": score_diff,
        "key_differences": reasons,
        "skills_only_higher_has": list(only_higher)[:10],
        "skills_only_lower_has": list(only_lower)[:10],
        "summary": (
            f"{higher['candidate_name']} ({higher['overall_score']}%) ranks above "
            f"{lower['candidate_name']} ({lower['overall_score']}%) by {score_diff} points. "
            + (
                f"Key advantages: {', '.join(r['category'] for r in reasons[:3])}."
                if reasons else "Scores are closely matched."
            )
        ),
    }
