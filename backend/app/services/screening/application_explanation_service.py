"""Application-specific Explainable AI (Phase 6).

One authoritative explanation pipeline, two authorized presentation layers::

    JobApplication
        -> ScreeningResult                    the only score in existence
        -> XAIEngine.explain_screening_result()  feature importance, factors,
                                                 confidence, suggestions
        -> FitService                          requirement evidence, skill gaps
        -> CandidateIntelService               evidence strengths/gaps
        -> _build_explanation()                THE internal payload
             |
             +-> _project_recruiter()  -> RecruiterApplicationExplanationResponse
             +-> _project_candidate()  -> CandidateApplicationExplanationResponse

Rules enforced here:

* **No duplicate engines.** Scores come from ``ScreeningResult``; explainability
  from ``XAIEngine``; requirement evidence from ``FitService``; evidence
  intelligence from ``CandidateIntelService``. This module composes those
  contracts and computes nothing of its own.
* **No fabricated evidence.** Every value is copied from a stored artifact. A
  section that cannot be produced reports ``available=False`` with a reason.
* **One score.** ``overall_score`` is ``ScreeningResult.overall_match_score``,
  copied verbatim. No recomputation, here or in the frontend.
* **Application is the context.** The screening result is resolved by
  ``application_id`` (with a legacy natural-key fallback), so a candidate's
  other applications can never bleed into this explanation.
* **Explainability is not a decision.** No status changes, no decision is
  recorded, and the candidate projection contains no hiring verdict.
* **Fairness stays out (Phase 7 boundary).** No protected attribute or bias
  signal is read, and the candidate-safety assertion rejects such fields, so a
  later fairness integration cannot silently become candidate-facing.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes, selectinload

from app.core.exceptions import NotFoundError
from app.domain.enums import AuditEventType, ScreeningStatus
from app.domain.models import Job, JobApplication, User
from app.repositories.candidate.resume import ResumeRepository
from app.repositories.screening.screening import ScreeningResultRepository
from app.services.audit_service import AuditService
from app.services.jobs.recruiter_job_service import RecruiterJobService
from app.services.screening.access import (
    CandidateNotAccessibleError,
    JobAccessDeniedError,
    JobNotFoundError,
    authorize_application_ownership,
    authorize_job_access,
)
from app.services.screening.fit_service import FitService
from app.services.screening.intel_service import CandidateIntelService
from app.services.screening.screening_detail_service import SCREENING_DIMENSIONS
from app.services.screening.xai_engine import XAIEngine

logger = logging.getLogger(__name__)

# Candidate-facing message per screening state. Deliberately generic: the raw
# JobApplication.screening_error is internal operational detail (engine traces,
# timeouts) and is exposed to recruiters only.
STATE_MESSAGES: dict[str, str] = {
    ScreeningStatus.COMPLETED.value: (
        "This explanation is based on the stored screening result for your "
        "application."
    ),
    ScreeningStatus.NOT_STARTED.value: (
        "Screening has not started yet, so no match score exists for this "
        "application."
    ),
    ScreeningStatus.QUEUED.value: (
        "Screening is being prepared, so no match score exists for this "
        "application yet."
    ),
    ScreeningStatus.RUNNING.value: (
        "Screening is in progress, so no match score exists for this "
        "application yet."
    ),
    ScreeningStatus.SKIPPED.value: (
        "Screening was skipped for this application, so no match score is "
        "available."
    ),
    ScreeningStatus.FAILED.value: (
        "Screening could not be completed for this application, so no match "
        "score is available. The hiring team will review your application."
    ),
}

EXPLANATION_UNAVAILABLE = (
    "An explanation is not available for this application yet."
)

NOT_SCREENED_REASON = (
    "A detailed comparison is not available until screening has completed for "
    "this application."
)

RECRUITER_DISCLAIMER = (
    "AI-assisted screening explanation. Decision support for human review, "
    "not a hiring decision."
)

CANDIDATE_NOTICE = (
    "This is an automated review of the evidence in your resume against this "
    "role's requirements. It supports human review and is not a decision about "
    "your application."
)

NO_LLM_IN_PATH = (
    "This explanation is derived only from stored screening and resume evidence. "
    "No language model generates or alters any score, quote or factor in it."
)

NO_ENGINE_VERSION = (
    "The stored screening result does not record an algorithm or model version, "
    "so the algorithm that produced these values cannot be identified."
)

NO_STALENESS_FLAG = (
    "This release does not mark an explanation as stale when the job changes "
    "after screening ran."
)

RESUME_DRIFT_NOTE = (
    "A newer primary resume has been uploaded since this screening ran. The "
    "scores and evidence below describe the earlier resume that was actually "
    "screened."
)

EVIDENCE_RESUME_DIFFERS_NOTE = (
    "Requirement evidence was read from the current primary resume, which is a "
    "different version than the resume that was screened."
)

# Fields that must never reach a candidate. Defence in depth: the candidate
# projection is already an allowlist, so nothing here should ever match. It
# exists so a future field added to the recruiter payload fails loudly in tests
# instead of leaking quietly in production.
CANDIDATE_FORBIDDEN_KEY_TOKENS: tuple[str, ...] = (
    "recruiter_note",
    "internal_comment",
    "decision_comment",
    "decision_reason",
    "decided_by",
    "decided_at",
    "rank",
    "ranking",
    "shortlist",
    "pairwise",
    "other_candidate",
    "fairness",
    "bias",
    "protected_attribute",
    "gender",
    "ethnicity",
    "age_group",
    "religion",
    "disability",
    "fraud",
    "security_signal",
    "risk_factor",
    "interview_note",
    "audit",
    "formula",
    "weight",
    "review_flag",
    "screening_question",
    "prompts",
    "recommendation",
    "strength_level",
)


class CandidateSafetyError(RuntimeError):
    """Raised when a candidate projection would carry a forbidden field."""


def _list_of_strings(value: Any) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _dedupe_strings(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _walk_keys(payload: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Return ``(path, key)`` for every mapping key in a nested payload."""
    found: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            found.append((prefix or "payload", str(key)))
            found.extend(_walk_keys(value, path))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_walk_keys(item, prefix))
    return found


class ApplicationExplanationService:
    """One explanation from existing engines, projected for two audiences."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.screening_repo = ScreeningResultRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.xai = XAIEngine(session)
        self.fit_service = FitService(session)
        self.intel_service = CandidateIntelService(session)
        self.audit = AuditService(session)

    # ─── Public API ────────────────────────────────────────────────────

    async def get_recruiter_explanation(
        self, application_id: uuid.UUID, actor: User,
    ) -> dict[str, Any]:
        """Internal "Why This Score?" for a recruiter who may access the job."""
        application = await self._load_application(application_id)
        job = await authorize_job_access(self.session, application.job_id, actor)
        candidate = application.candidate or await self.session.get(
            User, application.candidate_id,
        )
        payload = await self._build_explanation(
            application, job, candidate, evidence_actor=actor,
        )
        projected = self._project_recruiter(application, payload)
        await self._audit(
            event=AuditEventType.APPLICATION_EXPLANATION_VIEWED,
            action="application_explanation_viewed",
            actor=actor,
            application=application,
            job=job,
            screening=payload["screening"],
        )
        return projected

    async def get_candidate_explanation(
        self, application_id: uuid.UUID, actor: User,
    ) -> dict[str, Any]:
        """Candidate-safe explanation, scoped to the candidate's own application.

        Fit and evidence intelligence are recruiter-internal services that
        authorize against the job and the candidate. They are invoked with the
        job owner as the acting identity, *after* this route has already proven
        the application belongs to ``actor``; the candidate is never granted
        those permissions directly.
        """
        loaded = await self._load_application(application_id)
        application = await authorize_application_ownership(
            self.session, application_id, actor, application=loaded,
        )
        job = application.job
        if job is None:
            raise NotFoundError("Job not found for this application")
        payload = await self._build_explanation(
            application, job, application.candidate, evidence_actor=None,
        )
        projected = self._project_candidate(application, payload)
        self._assert_candidate_safe(projected)
        await self._audit(
            event=AuditEventType.CANDIDATE_EXPLANATION_VIEWED,
            action="candidate_explanation_viewed",
            actor=actor,
            application=application,
            job=job,
            screening=payload["screening"],
        )
        return projected

    # ─── Loading ───────────────────────────────────────────────────────

    async def _load_application(self, application_id: uuid.UUID) -> JobApplication:
        result = await self.session.execute(
            select(JobApplication)
            .options(
                selectinload(JobApplication.candidate),
                selectinload(JobApplication.job),
            )
            .where(JobApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise NotFoundError("Application not found")
        return application

    async def _resolve_screening(self, application: JobApplication) -> Any:
        """Resolve this application's screening result, and only this one.

        Prefers the explicit ``application_id`` link. The ``(job_id, candidate)``
        fallback covers rows written before that link existed; the unique
        constraint on ``job_applications (job_id, candidate_id)`` means it can
        only ever resolve to *this* application's screening.
        """
        screening = await self.screening_repo.get_by_application(application.id)
        if screening is not None:
            return screening
        return await self.screening_repo.get_by_job_and_candidate(
            application.job_id, application.candidate_id,
        )

    async def _job_owner(self, job: Job) -> User | None:
        return await self.session.get(User, job.recruiter_id)

    # ─── THE authoritative pipeline ────────────────────────────────────

    async def _build_explanation(
        self,
        application: JobApplication,
        job: Job,
        candidate: User | None,
        *,
        evidence_actor: User | None,
    ) -> dict[str, Any]:
        """Assemble the single internal explanation payload.

        Optional intelligence sources are isolated: if one is missing or fails,
        its section is flagged and the rest of the explanation is still built.
        """
        screening = await self._resolve_screening(application)
        # Phase 5 does the same, so both surfaces agree that a stored result
        # means effective status "completed" even when the denormalized column
        # is stale (manual screening).
        attributes.set_committed_value(
            application,
            "screening_result",
            [screening] if screening is not None else [],
        )
        effective_status = RecruiterJobService.effective_screening_status(application)
        screened = screening is not None

        xai_payload: dict[str, Any] = {}
        explainability_error: str | None = None
        if screened:
            try:
                xai_payload = await self.xai.explain_screening_result(screening)
            except Exception as exc:  # noqa: BLE001 - one source must not break the page
                logger.warning(
                    "Explainability unavailable for application %s", application.id,
                    exc_info=True,
                )
                explainability_error = f"Explainability unavailable: {exc}"
        else:
            explainability_error = EXPLANATION_UNAVAILABLE

        # FitService / CandidateIntelService authorize internally, so the
        # recruiter path passes the caller and the candidate path passes the
        # job owner. Neither may fail the request on their own.
        #
        # Both are gated on a stored screening result: this endpoint explains a
        # screening. Presenting a fit score next to a null screening score would
        # read as two competing scores for one application.
        if screened:
            evidence_actor = evidence_actor or await self._job_owner(job)
            fit, fit_error = await self._load_fit(application, evidence_actor)
            intel_payload, intel_error = await self._load_intel(application, evidence_actor)
        else:
            fit, fit_error = None, NOT_SCREENED_REASON
            intel_payload, intel_error = None, NOT_SCREENED_REASON

        intel_profile = (
            (intel_payload or {}).get("candidate_intelligence")
            if intel_payload else None
        )
        if intel_payload and not isinstance(intel_profile, dict):
            intel_profile = None

        primary_resume = await self.resume_repo.get_primary(application.candidate_id)
        primary_resume_id = str(primary_resume.id) if primary_resume else None
        application_resume_id = (
            str(application.resume_id) if application.resume_id else None
        )
        screening_resume_id = (
            str(screening.resume_id) if screening and screening.resume_id else None
        )
        evidence_resume_id = (fit or {}).get("resume_id") or None

        # Resume drift is surfaced, never resolved by re-scoring: the scores
        # below describe the resume that was actually screened, which may no
        # longer be the candidate's primary resume.
        screening_resume_is_current: bool | None = None
        if screening_resume_id and primary_resume_id:
            screening_resume_is_current = screening_resume_id == primary_resume_id
        evidence_is_screening: bool | None = None
        if evidence_resume_id and screening_resume_id:
            evidence_is_screening = evidence_resume_id == screening_resume_id

        limitations = [NO_LLM_IN_PATH, NO_STALENESS_FLAG]
        if screened:
            limitations.append(NO_ENGINE_VERSION)
        else:
            limitations.append(EXPLANATION_UNAVAILABLE)
        if screening_resume_is_current is False:
            limitations.append(RESUME_DRIFT_NOTE)
        if evidence_is_screening is False:
            limitations.append(EVIDENCE_RESUME_DIFFERS_NOTE)
        if explainability_error and screened:
            limitations.append(explainability_error)

        # The candidate only ever sees limitations that describe their own
        # submission. Engine provenance and internal error strings stay inside.
        candidate_limitations = [NO_LLM_IN_PATH]
        if not screened:
            candidate_limitations.append(EXPLANATION_UNAVAILABLE)
        if screening_resume_is_current is False:
            candidate_limitations.append(RESUME_DRIFT_NOTE)
        if evidence_is_screening is False:
            candidate_limitations.append(EVIDENCE_RESUME_DIFFERS_NOTE)

        return {
            "application": application,
            "job": job,
            "candidate": candidate,
            "screening": screening,
            "effective_status": effective_status,
            "screened": screened,
            "xai": xai_payload,
            "explainability": {
                "available": bool(screened and xai_payload),
                "reason": explainability_error,
            },
            "fit": fit,
            "fit_section": {"available": fit is not None, "reason": fit_error},
            "intel": intel_profile,
            "intel_job_payload": intel_payload,
            "intel_section": {"available": intel_profile is not None, "reason": intel_error},
            "freshness": {
                "screening_resume_id": screening_resume_id,
                "application_resume_id": application_resume_id,
                "primary_resume_id": primary_resume_id,
                "evidence_resume_id": evidence_resume_id,
                "screening_resume_is_current_primary": screening_resume_is_current,
                "evidence_resume_is_screening_resume": evidence_is_screening,
                "screened_at": screening.created_at if screening else None,
                "fit_engine_version": (fit or {}).get("engine_version"),
                "evidence_engine_version": (intel_payload or {}).get("engine_version"),
                # Feature importance in this path is the engine's fixed
                # weight * stored dimension score; SHAP is not applied here.
                "explainability_method": "rule_based",
            },
            "limitations": limitations,
            "candidate_limitations": candidate_limitations,
        }

    async def _load_fit(
        self, application: JobApplication, evidence_actor: User | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if evidence_actor is None:
            return None, "Fit analysis unavailable: the job owner no longer exists."
        try:
            payload = await self.fit_service.get_fit(
                application.job_id, application.candidate_id, evidence_actor,
            )
        except (JobAccessDeniedError, JobNotFoundError, CandidateNotAccessibleError) as exc:
            return None, f"Fit analysis unavailable: {exc}"
        except Exception as exc:  # noqa: BLE001 - one source must not break the page
            logger.warning(
                "Fit analysis unavailable for application %s", application.id,
                exc_info=True,
            )
            return None, f"Fit analysis unavailable: {exc}"
        if not payload:
            return None, "Fit analysis unavailable for this application."
        return payload, None

    async def _load_intel(
        self, application: JobApplication, evidence_actor: User | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if evidence_actor is None:
            return None, (
                "Evidence intelligence unavailable: the job owner no longer exists."
            )
        try:
            payload = await self.intel_service.get_job_intel(
                application.job_id, application.candidate_id, evidence_actor,
            )
        except (JobAccessDeniedError, JobNotFoundError, CandidateNotAccessibleError) as exc:
            return None, f"Evidence intelligence unavailable: {exc}"
        except Exception as exc:  # noqa: BLE001 - one source must not break the page
            logger.warning(
                "Evidence intelligence unavailable for application %s",
                application.id, exc_info=True,
            )
            return None, f"Evidence intelligence unavailable: {exc}"
        if not payload:
            return None, "Evidence intelligence unavailable for this application."
        return payload, None

    # ─── Shared building blocks ────────────────────────────────────────

    def _score_block(self, screening: Any) -> dict[str, Any]:
        """The authoritative stored score, copied verbatim."""
        if screening is None:
            return {
                "overall_score": None,
                "recommendation": None,
                "strength_level": None,
                "screened_at": None,
                "source": "unavailable",
            }
        return {
            "overall_score": screening.overall_match_score,
            "recommendation": _enum_value(screening.recommendation),
            "strength_level": _enum_value(screening.strength_level),
            "screened_at": screening.created_at,
            "source": "screening_result",
        }

    def _screening_state_block(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload["effective_status"]
        return {
            "effective_status": status,
            "screened": payload["screened"],
            "message": STATE_MESSAGES.get(status, EXPLANATION_UNAVAILABLE),
        }

    @staticmethod
    def _match_breakdown(screening: Any) -> list[dict[str, Any]]:
        if screening is None:
            return []
        return [
            {
                "key": key,
                "label": label,
                "score": getattr(screening, column),
                "source_column": column,
            }
            for key, label, column in SCREENING_DIMENSIONS
        ]

    @staticmethod
    def _features(xai: dict[str, Any], *, include_weight: bool) -> list[dict[str, Any]]:
        out = []
        for item in xai.get("feature_importance") or []:
            entry: dict[str, Any] = {
                "category": str(item.get("category") or ""),
                "label": str(item.get("label") or ""),
                "score": int(item.get("score") or 0),
                "contribution_pct": float(item.get("contribution_pct") or 0.0),
                "impact": str(item.get("impact") or "neutral"),
                "impact_description": str(item.get("impact_description") or ""),
                "method": item.get("method"),
            }
            if include_weight:
                entry["weight"] = float(item.get("weight") or 0.0)
            out.append(entry)
        return out

    @staticmethod
    def _confidence(xai: dict[str, Any]) -> dict[str, Any] | None:
        raw = xai.get("confidence")
        if not isinstance(raw, dict):
            return None
        return {
            "score": int(raw.get("score") or 0),
            "level": str(raw.get("level") or "low"),
            "description": str(raw.get("description") or ""),
            "data_completeness_pct": float(raw.get("data_completeness_pct") or 0.0),
            "data_points_available": int(raw.get("data_points_available") or 0),
            "data_points_max": int(raw.get("data_points_max") or 0),
        }

    def _factors(
        self,
        xai: dict[str, Any],
        key: str,
        evidence_index: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """XAI factors plus whatever resume evidence actually supports them.

        Evidence is located by the skill/category the factor names, or by skill
        names quoted inside the factor's own reason text. When nothing is
        located, ``evidence`` stays empty and ``evidence_available`` is False —
        a factor never implies evidence that was not found.
        """
        out = []
        for item in xai.get(key) or []:
            category = str(item.get("category") or "")
            reason = str(item.get("reason") or "")
            evidence = self._lookup_evidence(category, reason, evidence_index)
            out.append({
                "category": category,
                "score": int(item.get("score") or 0),
                "contribution_pct": float(item.get("contribution_pct") or 0.0),
                "reason": reason,
                "evidence": evidence,
                "evidence_available": bool(evidence),
            })
        return out

    def _build_evidence_index(
        self, payload: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """Index resume evidence by the requirement/skill it belongs to."""
        index: dict[str, list[dict[str, Any]]] = {}

        def add(name: Any, evidence: Any) -> None:
            label = str(name or "").strip().lower()
            if not label:
                return
            index.setdefault(label, []).extend(self._clean_evidence(evidence or []))

        for requirement in (payload.get("fit") or {}).get("requirements") or []:
            add(requirement.get("requirement"), requirement.get("evidence"))
        intel = payload.get("intel") or {}
        for assessment in intel.get("skill_assessments") or []:
            add(assessment.get("skill"), assessment.get("evidence"))
        for strength in intel.get("strengths") or []:
            add(strength.get("title"), strength.get("evidence"))
        return index

    @staticmethod
    def _lookup_evidence(
        category: str,
        reason: str,
        index: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Attach only evidence genuinely about this factor."""
        found: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(items: list[dict[str, Any]]) -> None:
            for item in items:
                key = (item.get("source", ""), item.get("quote", ""))
                if key in seen:
                    continue
                seen.add(key)
                found.append(item)

        add(index.get((category or "").strip().lower(), []))
        if found or not reason:
            return found

        # Fallback: skills named inside the factor's own explanation, matched
        # on word boundaries so short names ("Go", "C") cannot match inside
        # unrelated words.
        lowered = reason.lower()
        for name, items in index.items():
            if not name or name not in lowered:
                continue
            if not re.search(rf"(?<!\w){re.escape(name)}(?!\w)", lowered):
                continue
            add(items)
        return found

    @staticmethod
    def _clean_evidence(items: Any) -> list[dict[str, Any]]:
        out = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            quote = str(item.get("quote") or item.get("text") or "").strip()
            if not quote:
                continue
            out.append({
                "source": str(item.get("source") or "resume_text"),
                "quote": quote,
                "context": item.get("context"),
                "section": item.get("section"),
            })
        return out

    def _skill_alignment(
        self, screening: Any, fit: dict[str, Any] | None,
    ) -> dict[str, list[str]]:
        """Required -> candidate -> matched/missing, from the existing engines."""
        gaps = (fit or {}).get("skill_gaps") or {}
        return {
            "matched_skills": _list_of_strings(
                getattr(screening, "matched_skills", None) if screening else None,
            ),
            "missing_required_skills": _list_of_strings(
                getattr(screening, "missing_required_skills", None) if screening else None,
            ),
            "missing_preferred_skills": _list_of_strings(
                getattr(screening, "missing_preferred_skills", None) if screening else None,
            ),
            "supported_skills": _list_of_strings(gaps.get("strengths")),
            "partial_evidence_skills": _list_of_strings(gaps.get("partial")),
            "skills_without_evidence": _list_of_strings(gaps.get("gaps")),
            "insufficient_information_skills": _list_of_strings(gaps.get("unknown")),
        }

    def _requirements(self, fit: dict[str, Any] | None) -> list[dict[str, Any]]:
        return [
            {
                "requirement": str(item.get("requirement") or ""),
                "requirement_type": str(item.get("requirement_type") or ""),
                "level": str(item.get("level") or ""),
                "category": item.get("category"),
                "status": str(item.get("status") or "unknown"),
                "evidence_strength": str(item.get("evidence_strength") or "none"),
                "reason": str(item.get("reason") or ""),
                "evidence": self._clean_evidence(item.get("evidence")),
            }
            for item in ((fit or {}).get("requirements") or [])
        ]

    @staticmethod
    def _experience_alignment(fit: dict[str, Any] | None) -> dict[str, Any] | None:
        raw = (fit or {}).get("experience_alignment")
        if not isinstance(raw, dict):
            return None
        return {
            "status": str(raw.get("status") or "unknown"),
            "required_years": raw.get("required_years"),
            "relevant_years": raw.get("relevant_years"),
            "total_years": raw.get("total_years"),
            "relevance_basis": raw.get("relevance_basis"),
            "reason": str(raw.get("reason") or ""),
        }

    def _evidence_gaps(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Where the stored evidence does not support a claim.

        Both sources say "no supporting evidence was found", never "the
        candidate lacks X".
        """
        out: list[dict[str, Any]] = []
        for gap in (payload.get("intel") or {}).get("evidence_gaps") or []:
            subject = str(gap.get("skill") or "").strip()
            if not subject:
                continue
            out.append({
                "subject": subject,
                "category": "skill_depth",
                "note": str(gap.get("note") or ""),
            })
        for item in (payload.get("fit") or {}).get("requirements") or []:
            if item.get("status") != "unknown":
                continue
            subject = str(item.get("requirement") or "").strip()
            if not subject:
                continue
            out.append({
                "subject": subject,
                "category": "requirement",
                "note": (
                    "This requirement is listed in the job description, and the "
                    "stored resume evidence does not say whether it is met."
                ),
            })
        return out

    def _evidence_strengths(
        self, payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        out = []
        for strength in (payload.get("intel") or {}).get("strengths") or []:
            title = str(strength.get("title") or "").strip()
            if not title:
                continue
            evidence = self._clean_evidence(strength.get("evidence"))
            out.append({
                "title": title,
                "category": strength.get("category"),
                "depth": str(strength.get("depth") or ""),
                "confidence": str(strength.get("confidence") or ""),
                "reason": str(strength.get("reason") or ""),
                "evidence": evidence,
                "evidence_available": bool(evidence),
            })
        return out

    @staticmethod
    def _suggestions(xai: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten the existing XAI suggestions; a category with no data
        contributes nothing rather than a generic filler line."""
        raw = xai.get("improvement_suggestions") or {}
        out: list[dict[str, Any]] = []
        for item in raw.get("skill_improvements") or []:
            if not isinstance(item, dict):
                continue
            out.append({
                "category": "skill",
                "subject": item.get("skill"),
                "text": str(item.get("reason") or ""),
                "priority": item.get("priority"),
            })
        for item in raw.get("certification_recommendations") or []:
            if not isinstance(item, dict):
                continue
            out.append({
                "category": "certification",
                "subject": item.get("area"),
                "text": str(item.get("suggestion") or ""),
                "priority": item.get("priority"),
            })
        for text in raw.get("project_suggestions") or []:
            out.append({
                "category": "project",
                "subject": None,
                "text": str(text),
                "priority": None,
            })
        for text in raw.get("resume_improvements") or []:
            out.append({
                "category": "resume",
                "subject": None,
                "text": str(text),
                "priority": None,
            })
        for text in raw.get("interview_preparation") or []:
            out.append({
                "category": "interview",
                "subject": None,
                "text": str(text),
                "priority": None,
            })
        return [item for item in out if item["text"]]

    @staticmethod
    def _all_resume_evidence(
        requirements: list[dict[str, Any]], index: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for group in (*[item["evidence"] for item in requirements], *index.values()):
            for item in group:
                key = (item.get("source", ""), item.get("quote", ""))
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
        return out

    # ─── Recruiter projection (internal view) ──────────────────────────

    def _project_recruiter(
        self, application: JobApplication, payload: dict[str, Any],
    ) -> dict[str, Any]:
        xai = payload["xai"]
        fit = payload.get("fit")
        screening = payload["screening"]
        job = payload["job"]
        candidate = payload.get("candidate")
        evidence_index = self._build_evidence_index(payload)
        overall = (fit or {}).get("overall") or {}
        intel = payload.get("intel") or {}
        score = self._score_block(screening)

        return {
            "application": {
                "id": str(application.id),
                "job_id": str(application.job_id),
                "candidate_id": str(application.candidate_id),
                "resume_id": str(application.resume_id) if application.resume_id else None,
                "status": _enum_value(application.status),
                "applied_at": application.created_at,
                "updated_at": application.updated_at,
                "screening_status": payload["effective_status"],
                "screening_attempts": application.screening_attempts or 0,
                "screening_error": application.screening_error,
                "screening_started_at": application.screening_started_at,
                "screening_completed_at": application.screening_completed_at,
            },
            "candidate": {
                "id": str(application.candidate_id),
                "name": candidate.full_name if candidate else "",
                "email": candidate.email if candidate else "",
            },
            "job": {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "required_skills": _list_of_strings(job.required_skills),
                "preferred_skills": _list_of_strings(job.preferred_skills),
                "experience_required": job.experience_required,
                "education_required": job.education_required,
            },
            "screening_state": self._screening_state_block(payload),
            "score": score,
            "match_breakdown": self._match_breakdown(screening),
            "feature_importance": self._features(xai, include_weight=True),
            "positive_factors": self._factors(
                xai, "positive_factors", evidence_index,
            ),
            "negative_factors": self._factors(
                xai, "negative_factors", evidence_index,
            ),
            "reasoning_summary": str(xai.get("reasoning_summary") or ""),
            "confidence": self._confidence(xai),
            "improvement_suggestions": self._suggestions(xai),
            "skill_alignment": self._skill_alignment(screening, fit),
            "requirements": self._requirements(fit),
            "experience_alignment": self._experience_alignment(fit),
            "evidence_gaps": self._evidence_gaps(payload),
            "evidence_strengths": self._evidence_strengths(payload),
            "fit_classification": overall.get("classification"),
            "fit_score": overall.get("score"),
            "fit_summary": overall.get("summary"),
            "fit_summary_source": overall.get("summary_source"),
            "fit_formula": (overall.get("breakdown") or {}).get("formula"),
            "fit_weights": (overall.get("breakdown") or {}).get("weights") or {},
            "review_flags": list(intel.get("review_flags") or []),
            "screening_questions": list(intel.get("screening_questions") or []),
            "evidence_snapshot": intel.get("snapshot"),
            "explainability": payload["explainability"],
            "evidence_intelligence": payload["intel_section"],
            "fit": payload["fit_section"],
            "freshness": payload["freshness"],
            "limitations": payload["limitations"],
            "disclaimer": RECRUITER_DISCLAIMER,
        }

    # ─── Candidate projection (explicit allowlist) ─────────────────────

    def _project_candidate(
        self, application: JobApplication, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the candidate view field by field.

        This is an allowlist, not a filter. Every key below is written
        explicitly; nothing from the recruiter payload is spread in, so an
        internal field cannot ride along.
        """
        xai = payload["xai"]
        fit = payload.get("fit")
        screening = payload["screening"]
        job = payload["job"]
        evidence_index = self._build_evidence_index(payload)
        alignment = self._skill_alignment(screening, fit)
        requirements = self._requirements(fit)
        score = self._score_block(screening)
        overall = (fit or {}).get("overall") or {}

        return {
            "application": {
                "id": str(application.id),
                "job_id": str(application.job_id),
                "status": _enum_value(application.status),
                "applied_at": application.created_at,
                "screening_status": payload["effective_status"],
            },
            "job": {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "required_skills": _list_of_strings(job.required_skills),
                "preferred_skills": _list_of_strings(job.preferred_skills),
                "experience_required": job.experience_required,
                "education_required": job.education_required,
            },
            "screening_state": self._screening_state_block(payload),
            "score": {
                "overall_score": score["overall_score"],
                "screened_at": score["screened_at"],
                "source": score["source"],
                "match_classification": overall.get("classification"),
                "match_score": overall.get("score"),
                "match_summary": overall.get("summary"),
                "match_summary_source": overall.get("summary_source"),
            },
            "matched_skills": alignment["matched_skills"],
            "areas_with_limited_evidence": _dedupe_strings(
                alignment["missing_required_skills"]
                + alignment["missing_preferred_skills"]
                + alignment["skills_without_evidence"]
                + alignment["insufficient_information_skills"]
            ),
            "skill_alignment": alignment,
            "aligned_areas": self._factors(xai, "positive_factors", evidence_index),
            "limited_areas": self._factors(xai, "negative_factors", evidence_index),
            "feature_importance": self._features(xai, include_weight=False),
            "requirements": requirements,
            "experience_alignment": self._experience_alignment(fit),
            "evidence_gaps": self._evidence_gaps(payload),
            "resume_evidence": self._all_resume_evidence(requirements, evidence_index),
            "improvement_suggestions": self._suggestions(xai),
            "confidence": self._confidence(xai),
            "explainability": {
                "available": payload["explainability"]["available"],
                "reason": (
                    None
                    if payload["explainability"]["available"]
                    else (
                        "A detailed explanation of this screening result is not "
                        "available right now."
                    )
                ),
            },
            "evidence_intelligence": {
                "available": payload["intel_section"]["available"],
                "reason": (
                    None
                    if payload["intel_section"]["available"]
                    else (
                        "A more detailed evidence review is not available for "
                        "this application right now."
                    )
                ),
            },
            "fit": {
                "available": payload["fit_section"]["available"],
                "reason": (
                    None
                    if payload["fit_section"]["available"]
                    else (
                        "A detailed requirement-by-requirement comparison is not "
                        "available for this application right now."
                    )
                ),
            },
            "freshness": payload["freshness"],
            "screening_notice": CANDIDATE_NOTICE,
            "limitations": payload["candidate_limitations"],
        }

    # ─── Candidate safety assertion ────────────────────────────────────

    def _assert_candidate_safe(self, projected: dict[str, Any]) -> None:
        """Fail closed if a candidate payload carries a forbidden field.

        The candidate projection is already an allowlist, so this is a
        regression guard rather than a runtime filter. It raises instead of
        stripping, so a regression fails loudly in tests and logs an
        alert-shaped error in production rather than silently serving an
        over-broad payload.
        """
        violations: list[str] = []
        for path, key in _walk_keys(projected):
            lowered = key.lower()
            for token in CANDIDATE_FORBIDDEN_KEY_TOKENS:
                if token in lowered:
                    violations.append(f"{path}.{key}")
                    break
        if violations:
            logger.error(
                "Candidate explanation safety violation: fields=%s", violations,
            )
            raise CandidateSafetyError(
                "Candidate explanation contains non-shareable fields: "
                + ", ".join(sorted(set(violations)))
            )

    # ─── Audit ─────────────────────────────────────────────────────────

    async def _audit(
        self,
        *,
        event: AuditEventType,
        action: str,
        actor: User,
        application: JobApplication,
        job: Job,
        screening: Any,
    ) -> None:
        """Audit the read without logging any explanation content.

        Only identifiers and the availability of the optional sections are
        recorded — never scores, factors, evidence quotes or resume text.
        """
        try:
            await self.audit.log(
                event_type=event,
                action=action,
                user_id=actor.id,
                organization_id=job.organization_id,
                resource_type="job_application",
                resource_id=str(application.id),
                details={
                    "job_id": str(job.id),
                    "candidate_id": str(application.candidate_id),
                    "screening_result_id": str(screening.id) if screening else None,
                    "screened": screening is not None,
                },
            )
        except Exception:  # noqa: BLE001 - auditing must not fail the read
            logger.warning(
                "Failed to audit %s for application %s", action, application.id,
                exc_info=True,
            )
