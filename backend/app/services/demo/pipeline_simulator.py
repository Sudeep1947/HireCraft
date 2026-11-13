"""Pipeline simulator - creates realistic demo entities by reusing the
existing repositories and services (users, profiles, resumes, jobs,
applications, screening, interviews, scorecards, analytics reports).
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.demo_models import DemoCompany
from app.domain.enums import (
    ApplicationStatus,
    EmploymentType,
    JobStatus,
    Proficiency,
    RoleName,
    SkillProficiency,
)
from app.domain.job_schemas import JobCreate
from app.domain.models import (
    CandidateProfile,
    CandidateSkill,
    Certification,
    Education,
    Experience,
    Interview,
    InterviewScorecard,
    Job,
    JobApplication,
    Language,
    Project,
    ScreeningResult,
    Skill,
    User,
)
from app.domain.analytics_schemas import ReportCreateRequest
from app.repositories.candidate.certification import CertificationRepository
from app.repositories.candidate.education import EducationRepository
from app.repositories.candidate.experience import ExperienceRepository
from app.repositories.candidate.language import LanguageRepository
from app.repositories.candidate.profile import CandidateProfileRepository
from app.repositories.candidate.project import ProjectRepository
from app.repositories.candidate.skill import CandidateSkillRepository, SkillRepository
from app.repositories.jobs.job import JobApplicationRepository
from app.repositories.user import UserRepository
from app.services.analytics.report_service import ReportService
from app.services.candidate.resume import ResumeService
from app.services.candidate.resume_parser.skill_database import SKILL_DATABASE
from app.services.demo import data_pool
from app.services.demo.resume_generator import build_resume_content
from app.services.interview.interview_service import InterviewService
from app.services.interview.mock_interview import MockInterviewService
from app.services.interview.scorecard_engine import ScorecardEngine
from app.services.jobs.recruiter_job_service import RecruiterJobService
from app.services.screening.screening_service import ScreeningService

PASSWORD = "Demo@12345"

RESUME_FORMATS = ["pdf", "docx", "txt"]

_INTERVIEW_ANSWERS: dict[str, list[str]] = {
    "technical": [
        "I would start by understanding the requirements and constraints, then design a modular "
        "solution that is easy to test and maintain. I have shipped similar systems in production "
        "and would reuse proven patterns like repository layers and background jobs.",
        "I approach technical problems by breaking them into small verifiable steps. I write tests "
        "first where it makes sense, monitor key metrics after deployment, and iterate based on "
        "observability data.",
    ],
    "behavioral": [
        "In a previous role I led a team through a tight deadline by prioritizing tasks and "
        "communicating early about risks. We shipped on time and the process improvements we made "
        "became the team standard.",
        "I once resolved a conflict between two teammates by facilitating a focused discussion "
        "around the shared goal. We aligned on ownership and the project progressed smoothly.",
    ],
    "situational": [
        "I would evaluate the impact and effort of each option, align with stakeholders on the "
        "trade-offs, and move forward with a reversible decision while keeping a fallback plan.",
        "I would gather the relevant context, propose a clear plan with a checkpoint to review, and "
        "escalate early if the risk grows beyond the team's control.",
    ],
    "hr": [
        "I am looking for a role where I can own meaningful problems, grow my craft, and "
        "contribute to a collaborative team. This position aligns well with my experience and goals.",
        "My strength is turning ambiguous requirements into reliable deliverables, and I enjoy "
        "mentoring others. I am working on deepening my expertise in distributed systems.",
    ],
    "coding": [
        "I would implement a straightforward solution first, then optimize the bottleneck based on "
        "measured performance. I would include unit tests covering the edge cases.",
        "Using a hash map for lookups and a two-pointer approach keeps it linear time. I would "
        "verify correctness with a few representative test cases before finalizing.",
    ],
    "system_design": [
        "I would design for horizontal scalability with stateless services, a replicated data layer, "
        "and caching at the hot paths. I would add monitoring and a clear failure model.",
        "The key is separating read and write paths, using an event-driven architecture, and "
        "planning for graceful degradation under load.",
    ],
    "problem_solving": [
        "I define the success criteria, generate a few candidate approaches, and pick the one with "
        "the best risk/reward. I validate assumptions with data before committing.",
        "I like to reason from first principles, prototype quickly, and use feedback loops to "
        "converge on a solution.",
    ],
}

_JOB_DESCRIPTIONS: dict[str, str] = {
    "Senior Software Engineer": (
        "We are looking for a senior engineer to own key services end to end, mentor teammates, "
        "and drive architecture decisions. You will work across the stack with a focus on "
        "reliability, performance, and clean design."
    ),
    "Data Scientist": (
        "Join our data team to build models and analyses that directly shape product decisions. "
        "You will collaborate with engineers to productionize ML pipelines and dashboards."
    ),
    "Machine Learning Engineer": (
        "Help us build and deploy machine learning systems at scale, from data pipelines to model "
        "serving. Experience with Python, ML frameworks, and cloud platforms is important."
    ),
    "DevOps Engineer": (
        "Own our CI/CD, infrastructure as code, and observability tooling. You will improve "
        "deployment speed and system reliability across the organization."
    ),
    "Frontend Engineer": (
        "Build delightful, accessible user interfaces with a modern stack. You will collaborate "
        "closely with design and product to ship polished experiences."
    ),
    "Backend Engineer": (
        "Design and build scalable APIs and services. You will work on high-throughput systems "
        "with a strong emphasis on correctness and performance."
    ),
    "Cloud Architect": (
        "Architect secure, cost-effective cloud solutions and lead the platform roadmap. You will "
        "guide teams on best practices for scalability and resilience."
    ),
}

_BENEFITS = (
    "Competitive salary, equity, health insurance, learning stipend, flexible remote policy, "
    "and generous paid time off."
)


def _skill_category(name: str) -> str:
    for category, skills in SKILL_DATABASE.items():
        for skill in skills:
            if skill["name"] == name:
                return category
    return "tools"


class PipelineSimulator:
    """Creates demo entities using the existing domain services/repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.profile_repo = CandidateProfileRepository(session)
        self.skill_repo = SkillRepository(session)
        self.candidate_skill_repo = CandidateSkillRepository(session)
        self.education_repo = EducationRepository(session)
        self.experience_repo = ExperienceRepository(session)
        self.project_repo = ProjectRepository(session)
        self.certification_repo = CertificationRepository(session)
        self.language_repo = LanguageRepository(session)
        self.application_repo = JobApplicationRepository(session)
        self.job_service = RecruiterJobService(session)
        self.resume_service = ResumeService(session)
        self.screening_service = ScreeningService(session)
        self.interview_service = InterviewService(session)
        self.mock_interview = MockInterviewService(session)
        self.scorecard_engine = ScorecardEngine(session)
        self.report_service = ReportService(session)

    # ─── Companies ──────────────────────────────────────────────────

    async def create_company(self, rng: random.Random, config: dict) -> DemoCompany:
        company = DemoCompany(
            name=config["name"],
            industry=config["industry"],
            headquarters=config["headquarters"],
            size_range=config["size_range"],
            description=config.get("description"),
        )
        self.session.add(company)
        await self.session.flush()
        return company

    # ─── Users & roles ───────────────────────────────────────────────

    async def create_user(
        self, rng: random.Random, role: str, email: str,
    ) -> User:
        from app.core.security import hash_password

        full_name = (
            f"{rng.choice(data_pool.FIRST_NAMES)} {rng.choice(data_pool.LAST_NAMES)}"
        )
        user = await self.user_repo.create(
            full_name=full_name,
            email=email,
            password_hash=hash_password(PASSWORD),
            is_active=True,
            is_verified=True,
        )
        role_row = await self.user_repo.find_role_by_name(role)
        if role_row:
            await self.user_repo.assign_role(user.id, role_row.id)
        await self.session.flush()
        return user

    # ─── Skills ──────────────────────────────────────────────────────

    async def ensure_skill(self, name: str) -> Skill:
        existing = await self.skill_repo.find_by_name(name)
        if existing:
            return existing
        skill = await self.skill_repo.create(name=name, category=_skill_category(name))
        await self.session.flush()
        return skill

    async def ensure_skills(self, names: list[str]) -> list[Skill]:
        return [await self.ensure_skill(name) for name in names]

    # ─── Candidate profile ───────────────────────────────────────────

    async def create_candidate_profile(
        self,
        rng: random.Random,
        user: User,
        job_title: str,
        skill_names: list[str],
        companies: list[str],
    ) -> CandidateProfile:
        location = rng.choice(data_pool.CITIES)
        profile = await self.profile_repo.upsert(
            user_id=user.id,
            phone=f"+1{rng.randint(200, 989):03d}{rng.randint(100, 999):03d}{rng.randint(1000, 9999)}",
            date_of_birth=date(rng.randint(1985, 2000), rng.randint(1, 12), rng.randint(1, 28)),
            gender=rng.choice(["male", "female", "other", "prefer_not_to_say"]),
            location=location,
            nationality=rng.choice(["United States", "India", "Canada", "United Kingdom", "Germany"]),
            linkedin_url=f"https://linkedin.com/in/{user.full_name.lower().replace(' ', '-')}",
            github_url=f"https://github.com/{user.full_name.lower().replace(' ', '-')}",
            portfolio_url=f"https://{user.full_name.lower().replace(' ', '')}.example.dev",
            website_url=f"https://{user.full_name.lower().replace(' ', '')}.example.dev",
            bio=rng.choice(data_pool.RESUME_SUMMARIES),
            current_role=job_title,
            profile_completion=100,
        )
        await self.session.flush()

        skill_rows = await self.ensure_skills(skill_names)
        for skill in skill_rows:
            await self.candidate_skill_repo.create(
                profile_id=profile.id,
                skill_id=skill.id,
                proficiency=rng.choice(
                    [SkillProficiency.BEGINNER.value, SkillProficiency.INTERMEDIATE.value,
                     SkillProficiency.ADVANCED.value, SkillProficiency.EXPERT.value]
                ),
                years_of_experience=float(rng.randint(1, 9)),
            )

        await self._add_education(rng, profile)
        await self._add_experience(rng, profile, job_title, companies)
        await self._add_projects(rng, profile, skill_names)
        await self._add_certifications(rng, profile)
        await self._add_languages(rng, profile)

        await self.session.flush()
        return profile

    async def _add_education(self, rng: random.Random, profile: CandidateProfile) -> None:
        degree = rng.choice(data_pool.DEGREES)
        institution = rng.choice(data_pool.UNIVERSITIES)
        end_year = rng.randint(2010, 2017)
        await self.education_repo.create(
            profile_id=profile.id,
            institution=institution,
            degree=degree,
            branch=degree.split(" in ")[-1] if " in " in degree else None,
            cgpa=round(rng.uniform(3.2, 3.9), 2),
            start_date=date(end_year - 4, 8, 1),
            end_date=date(end_year, 5, 31),
            is_current=False,
        )
        if rng.random() < 0.5:
            await self.education_repo.create(
                profile_id=profile.id,
                institution=rng.choice(data_pool.UNIVERSITIES),
                degree=rng.choice(
                    [d for d in data_pool.DEGREES if d != degree] or data_pool.DEGREES
                ),
                cgpa=round(rng.uniform(3.4, 4.0), 2),
                start_date=date(end_year + 1, 8, 1),
                end_date=date(end_year + 3, 5, 31),
                is_current=False,
            )

    async def _add_experience(
        self,
        rng: random.Random,
        profile: CandidateProfile,
        job_title: str,
        companies: list[str],
    ) -> None:
        num_roles = rng.randint(2, 4)
        start_year = rng.randint(2012, 2018)
        for idx in range(num_roles):
            role_title = job_title if idx == 0 else rng.choice(
                [t for t in data_pool.JOB_TITLES if t != job_title] or data_pool.JOB_TITLES
            )
            is_current = idx == num_roles - 1
            end_year = None if is_current else start_year + 2
            await self.experience_repo.create(
                profile_id=profile.id,
                company=rng.choice(companies),
                job_title=role_title,
                employment_type=EmploymentType.FULL_TIME.value,
                start_date=date(start_year, rng.randint(1, 12), 1),
                end_date=date(end_year, rng.randint(1, 12), 1) if end_year else None,
                is_current=is_current,
                responsibilities="; ".join(rng.sample(data_pool.EXPERIENCE_BULLETS, k=3)),
                technologies=", ".join(rng.sample(data_pool.TECHNICAL_SKILLS, k=4)),
            )
            start_year += 2

    async def _add_projects(
        self, rng: random.Random, profile: CandidateProfile, skill_names: list[str],
    ) -> None:
        for proj_name in rng.sample(data_pool.PROJECT_NAMES, k=2):
            await self.project_repo.create(
                profile_id=profile.id,
                title=proj_name,
                description="Built and shipped an end-to-end feature with automated tests.",
                technologies=", ".join(rng.sample(skill_names, k=min(3, len(skill_names)))),
                github_link=f"https://github.com/demo/{proj_name.lower().replace(' ', '-')}",
                start_date=date(2021, 1, 1),
                end_date=date(2021, 8, 1),
            )

    async def _add_certifications(self, rng: random.Random, profile: CandidateProfile) -> None:
        for cert_name in rng.sample(data_pool.CERTIFICATION_TEMPLATES, k=2):
            await self.certification_repo.create(
                profile_id=profile.id,
                name=cert_name,
                organization=cert_name.split(" ")[0] if cert_name.split(" ")[0].upper() in {
                    "AWS", "GOOGLE", "MICROSOFT", "CISCO", "PMP"
                } else "Demo Academy",
                issue_date=date(2022, 3, 15),
            )

    async def _add_languages(self, rng: random.Random, profile: CandidateProfile) -> None:
        langs = ["English"] + rng.sample(
            ["Hindi", "Spanish", "French", "German", "Mandarin"], k=1,
        )
        for lang in langs:
            await self.language_repo.create(
                profile_id=profile.id,
                language=lang,
                reading=rng.choice([Proficiency.ADVANCED.value, Proficiency.NATIVE.value]),
                writing=rng.choice([Proficiency.ADVANCED.value, Proficiency.NATIVE.value]),
                speaking=rng.choice([Proficiency.ADVANCED.value, Proficiency.NATIVE.value]),
            )

    # ─── Resumes ─────────────────────────────────────────────────────

    async def create_resume(
        self,
        rng: random.Random,
        user: User,
        profile: CandidateProfile,
        job_title: str,
        skill_names: list[str],
        companies: list[str],
        fmt: str,
    ) -> object:
        content = build_resume_content(
            rng=rng,
            full_name=user.full_name,
            title=job_title,
            email=user.email,
            phone=profile.phone or f"+1{rng.randint(200, 989):03d}{rng.randint(100, 999):03d}{rng.randint(1000, 9999)}",
            location=profile.location or rng.choice(data_pool.CITIES),
            skills=skill_names,
            companies=companies,
            education_degrees=data_pool.DEGREES,
            education_institutions=data_pool.UNIVERSITIES,
            certifications=data_pool.CERTIFICATION_TEMPLATES,
        )
        file_content, ext = content.render(fmt)
        original_filename = f"{user.full_name.lower().replace(' ', '-')}-resume{ext}"
        resume = await self.resume_service.upload_resume(
            user_id=user.id,
            profile_id=profile.id,
            file_content=file_content,
            original_filename=original_filename,
        )
        await self.resume_service.process_resume(resume.id)
        return resume

    # ─── Jobs ────────────────────────────────────────────────────────

    async def create_job(
        self,
        rng: random.Random,
        recruiter: User,
        company_name: str,
        title: str,
        required_skills: list[str],
        preferred_skills: list[str],
    ) -> Job:
        data = JobCreate(
            title=title,
            company=company_name,
            department=rng.choice(data_pool.DEPARTMENTS),
            employment_type=EmploymentType.FULL_TIME,
            experience_required=rng.choice(data_pool.EXPERIENCE_LEVELS),
            education_required=rng.choice(data_pool.EDUCATION_LEVELS),
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            location=rng.choice(data_pool.CITIES),
            salary_min=rng.choice([90_000, 110_000, 125_000]),
            salary_max=rng.choice([140_000, 160_000, 180_000]),
            salary_currency="USD",
            description=_JOB_DESCRIPTIONS.get(title, rng.choice(data_pool.COMPANY_SUMMARIES)),
            benefits=_BENEFITS,
            status=JobStatus.PUBLISHED,
        )
        return await self.job_service.create_job(recruiter.id, data)

    # ─── Applications ────────────────────────────────────────────────

    async def create_application(
        self, job, candidate: User, resume: object | None,
    ) -> JobApplication:
        app = await self.application_repo.create(
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume.id if resume else None,
            cover_letter="I am excited to apply for this role and believe my experience "
                         "and skills are a strong match for the team.",
            status=ApplicationStatus.APPLIED.value,
        )
        await self.job_service.lifecycle_service.record_creation(
            app, actor=candidate,
        )
        return app

    # ─── Screening ───────────────────────────────────────────────────

    async def screen_job(self, job_id: uuid.UUID, recruiter_id: uuid.UUID) -> int:
        _, count = await self.screening_service.screen_job_applicants(job_id, recruiter_id)
        return count

    # ─── Interviews ──────────────────────────────────────────────────

    async def run_interview(
        self,
        rng: random.Random,
        job,
        candidate: User,
        recruiter_id: uuid.UUID,
        difficulty: str = "medium",
        count: int = 10,
    ) -> dict:
        generated = await self.interview_service.generate_questions(
            job_id=job.id,
            recruiter_id=recruiter_id,
            categories=None,
            difficulty=difficulty,
            count=count,
            candidate_id=candidate.id,
        )
        interview = await self.mock_interview.start_mock(
            candidate_id=candidate.id,
            job_id=job.id,
            questions=generated["questions"],
        )

        questions = await self.interview_service.question_repo.list_by_interview(interview.id)
        for q in questions:
            answer_pool = _INTERVIEW_ANSWERS.get(q.category, _INTERVIEW_ANSWERS["behavioral"])
            answer_text = rng.choice(answer_pool)
            await self.mock_interview.submit_answer(
                question_id=q.id,
                answer_text=answer_text,
                time_taken_seconds=rng.randint(30, 180),
            )

        await self.mock_interview.complete_interview(interview.id)
        scorecard = await self.scorecard_engine.generate_scorecard(interview.id)
        return {
            "interview": interview,
            "scorecard": scorecard,
        }

    # ─── Reports ─────────────────────────────────────────────────────

    async def create_report(
        self, user: User, title: str, report_type: str,
    ) -> object:
        request = ReportCreateRequest(
            title=title,
            report_type=report_type,
            config={"source": "demo", "filters": {}},
            is_scheduled=False,
            schedule_cron=None,
        )
        return await self.report_service.create_report(user.id, request)

    # ─── Default config helper ───────────────────────────────────────

    def resolve_skill_pool(
        self, rng: random.Random, categories: list[str] | None = None,
    ) -> list[str]:
        """Phase 11: resolve the skill pool from selected categories.

        Falls back to the general technical pool when no (or unknown)
        categories are supplied. Unknown category names are ignored so a
        bad client payload can never produce an empty pool.
        """
        if categories:
            merged: list[str] = []
            for category in categories:
                merged.extend(data_pool.SKILL_CATEGORY_POOLS.get(category, []))
            # De-duplicate while preserving order.
            unique = list(dict.fromkeys(merged))
            if unique:
                return unique

        return rng.sample(
            data_pool.TECHNICAL_SKILLS, k=min(30, len(data_pool.TECHNICAL_SKILLS))
        )

    # ─── Hiring decisions (Phase 11, Modules 6 & 10) ────────────────

    async def run_hiring_decisions(
        self,
        rng: random.Random,
        job: Job,
        entries: list[dict],
        difficulty: str = "medium",
    ) -> dict:
        """Advance applications through shortlist → interview → offer → hire/reject.

        `entries` is a list of {"app": JobApplication, "candidate": User} for one
        job. Interview scorecards (when present) drive offers; screening scores
        rank the remainder. Returns aggregate counts for stats/events.
        """
        preset = data_pool.HIRING_DIFFICULTY_PRESETS.get(
            difficulty, data_pool.HIRING_DIFFICULTY_PRESETS["medium"],
        )

        # Interview outcomes per candidate (best score wins).
        interview_scores: dict[uuid.UUID, float] = {}
        interviews = (
            await self.session.execute(
                select(Interview).where(Interview.job_id == job.id)
            )
        ).scalars().all()
        if interviews:
            cards = (
                await self.session.execute(
                    select(InterviewScorecard).where(
                        InterviewScorecard.interview_id.in_([i.id for i in interviews])
                    )
                )
            ).scalars().all()
            card_by_interview = {c.interview_id: c for c in cards}
            for iv in interviews:
                card = card_by_interview.get(iv.id)
                if card and card.overall_score is not None:
                    existing = interview_scores.get(iv.candidate_id)
                    if existing is None or card.overall_score > existing:
                        interview_scores[iv.candidate_id] = float(card.overall_score)

        # Screening scores for ranking applicants without interviews.
        screening_scores: dict[uuid.UUID, float] = {}
        if entries:
            screens = (
                await self.session.execute(
                    select(ScreeningResult).where(ScreeningResult.job_id == job.id)
                )
            ).scalars().all()
            for s in screens:
                if s.overall_match_score is not None:
                    screening_scores[s.candidate_id] = float(s.overall_match_score)

        def _score(candidate_id: uuid.UUID) -> float:
            return interview_scores.get(
                candidate_id, screening_scores.get(candidate_id, 0.0),
            )

        def _entry_user(entry: dict) -> User:
            """Entries carry either a User or the orchestrator's candidate
            dict {"user": User, ...}."""
            candidate = entry["candidate"]
            return candidate["user"] if isinstance(candidate, dict) else candidate

        ranked = sorted(entries, key=lambda e: _score(_entry_user(e).id), reverse=True)
        shortlist_size = max(1, int(len(ranked) * preset["shortlist_ratio"]))

        counts = {
            "shortlisted": 0,
            "interview_scheduled": 0,
            "offered": 0,
            "hired": 0,
            "rejected": 0,
        }
        transitions: list[dict] = []
        actor = await self.user_repo.get(job.recruiter_id)

        for idx, entry in enumerate(ranked):
            app: JobApplication = entry["app"]
            cid = _entry_user(entry).id
            score = _score(cid)
            had_interview = cid in interview_scores
            path: list[str] = []
            target = ApplicationStatus.APPLIED.value

            if idx < shortlist_size or had_interview:
                counts["shortlisted"] += 1
                path.append("shortlisted")

                if had_interview:
                    counts["interview_scheduled"] += 1
                    path.append("interview_scheduled")
                    if score >= preset["hire_threshold"]:
                        counts["offered"] += 1
                        path.append("offered")
                        counts["hired"] += 1
                        path.append("hired")
                        target = ApplicationStatus.HIRED.value
                    else:
                        counts["rejected"] += 1
                        path.append("rejected")
                        target = ApplicationStatus.REJECTED.value
                else:
                    # Strong screen but no interview slot: offer by rate.
                    if rng.random() < preset["offer_rate_for_unscored_top"]:
                        counts["offered"] += 1
                        path.append("offered")
                        counts["hired"] += 1
                        path.append("hired")
                        target = ApplicationStatus.HIRED.value
                    else:
                        target = ApplicationStatus.UNDER_REVIEW.value
            else:
                if rng.random() < preset["rejection_rate_tail"]:
                    counts["rejected"] += 1
                    path.append("rejected")
                    target = ApplicationStatus.REJECTED.value
                else:
                    target = ApplicationStatus.APPLIED.value
                    path.append("kept_in_pipeline")

            if actor is None:
                raise ValueError(
                    f"Recruiter {job.recruiter_id} missing for demo job {job.id}"
                )
            await self._advance_via_lifecycle(app, actor, target, had_interview)

            transitions.append({
                "application_id": str(app.id),
                "candidate_id": str(cid),
                "from": ApplicationStatus.APPLIED.value,
                "to": target,
                "path": path,
                "score": round(score, 2),
            })

        await self.session.flush()
        return {"counts": counts, "transitions": transitions}

    async def _advance_via_lifecycle(
        self, app: JobApplication, actor: User, target: str, had_interview: bool,
    ) -> None:
        """Walk an application to ``target`` through the legal lifecycle funnel.

        Demo decisions must obey the same transition rules as real users: the
        demo may never write a status directly or skip the funnel. All demo
        applications start at ``applied``.
        """
        if target == ApplicationStatus.APPLIED.value:
            return
        if target == ApplicationStatus.UNDER_REVIEW.value:
            route = [ApplicationStatus.UNDER_REVIEW.value]
        elif target == ApplicationStatus.REJECTED.value:
            route = (
                [
                    ApplicationStatus.SHORTLISTED.value,
                    ApplicationStatus.INTERVIEW_SCHEDULED.value,
                    ApplicationStatus.REJECTED.value,
                ]
                if had_interview
                else [ApplicationStatus.REJECTED.value]
            )
        elif target == ApplicationStatus.HIRED.value:
            route = [
                ApplicationStatus.SHORTLISTED.value,
                ApplicationStatus.OFFERED.value,
                ApplicationStatus.HIRED.value,
            ]
            if had_interview:
                route.insert(1, ApplicationStatus.INTERVIEW_SCHEDULED.value)
        else:
            route = [target]

        lifecycle = self.job_service.lifecycle_service
        for step in route:
            await lifecycle.transition_application(
                app.id, step, actor, reason="demo_pipeline",
            )
            await self.session.refresh(app)
