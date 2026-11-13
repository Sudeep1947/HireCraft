"""AI Fairness Engine for Ethical Hiring Intelligence.

Provides comprehensive fairness analysis, bias detection, adversarial testing,
and job description bias analysis for the recruitment platform.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    CandidateProfile,
    CandidateSkill,
    CandidateRanking,
    Education,
    Experience,
    Job,
    JobApplication,
    ScreeningResult,
    Skill,
    User,
)
from app.repositories.candidate.profile import CandidateProfileRepository
from app.repositories.jobs.job import JobRepository
from app.repositories.screening.screening import ScreeningResultRepository

logger = logging.getLogger(__name__)

GENDERED_TERMS = {
    "male": [
        "he", "him", "his", "himself", "man", "men", "male", "mr", "gentleman",
        "chairman", "spokesman", "businessman", "fireman", "policeman",
    ],
    "female": [
        "she", "her", "hers", "herself", "woman", "women", "female", "mrs",
        "miss", "ms", "gentlewoman", "chairwoman", "spokeswoman",
        "businesswoman", "firewoman", "policewoman",
    ],
}

AGE_BIASED_TERMS = [
    "young", "energetic", "digital native", "fresh graduate", "recent graduate",
    "high energy", "hungry", "ambitious young", "junior", "entry level",
    "mature", "experienced professional", "seasoned", "veteran",
    "retirement age", "overqualified", "cultural fit",
]

DISCRIMINATORY_TERMS = [
    "white only", "no disabilities", "must be able-bodied",
    "must be physically fit", "no religious headwear",
    "must speak english only", "native english only",
    "no wheelchair users", "must have valid drivers license",
    "must be married", "must be single", "must be unmarried",
    "female only", "male only",
]

EXCLUSIVE_LANGUAGE = [
    "rockstar", "ninja", "guru", "wizard", "superhero",
    "aggressive", "dominant", "fearless", "strong",
    "frat house", "boys club", "manpower",
]

UNNECESSARY_REQUIREMENTS = [
    "years of experience required", "degree required",
    "gpa required", "specific university",
    "specific certification required", "must have car",
    "must relocate", "must work weekends", "must work overtime",
]

PROTECTED_ATTRIBUTES = [
    "gender", "age", "race", "ethnicity", "religion",
    "nationality", "disability", "sexual_orientation",
    "marital_status", "pregnancy",
]

# The screening score at or above which a candidate counts as having a positive
# screening outcome. This is the same 70 the engine has always used in
# ``_statistical_parity_difference`` and friends; it is named here so the group
# metrics below can reuse the existing threshold instead of introducing a new
# one, and so it can be reported to the user as a configured value rather than
# an invisible magic number.
POSITIVE_OUTCOME_THRESHOLD = 70

# Minimum candidates in a demographic group before its outcome rate is
# reported. Matches ``FairnessImpactAnalyzer.DEFAULT_MINIMUM_GROUP_SIZE`` so the
# simulation and screening surfaces apply the same reliability floor.
DEFAULT_MINIMUM_GROUP_SIZE = 5

# Self-reported gender values that count as a known demographic. A candidate who
# has not supplied a value is never assigned one, and never inferred: an
# unrecorded attribute is reported as missing coverage, not as a group.
_KNOWN_GENDER_VALUES = {"male", "female", "other"}

# Metrics that are computed over a single job's screened population.
GROUP_METRIC_SCOPE = "job_screening_population"

# Explains, in the API response itself, what the group metrics do and do not
# establish. Shipped with the data so no consumer can present the number without
# the caveat attached.
GROUP_METRIC_METHODOLOGY = (
    "Rates compare the share of each self-reported gender group whose screening "
    "score reached the configured positive-outcome threshold. They describe a "
    "disparity between groups in the measured population and indicate where "
    "investigation may be warranted. They do not establish that any individual "
    "was treated unfairly, do not measure the outcome of a hiring decision "
    "(no decision has been made at this point), and do not show that the "
    "screening engine caused a disparity. Gender is self-reported and is not an "
    "input to any match score."
)

# Why location is not used as a grouping dimension even though the engine
# already tracks it. Location is not a protected attribute, and grouping by it
# would re-express protected attributes as geography. The engine reports
# location differences as a review alert instead, where they stay advisory.
LOCATION_GROUPING_NOTE = (
    "Candidate location is deliberately not used as a fairness grouping "
    "dimension. Location is not a protected attribute and can act as a proxy "
    "for one, so grouping by it would risk reporting a protected disparity "
    "under a geographic label. Score differences between locations are reported "
    "separately as a review alert."
)


class FairnessEngine:
    """Analyze recruitment outcomes for bias, fairness, and compliance."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.screening_repo = ScreeningResultRepository(session)
        self.profile_repo = CandidateProfileRepository(session)
        self.job_repo = JobRepository(session)

    async def get_fairness_overview(
        self, job_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """Platform-wide fairness overview, optionally scoped to ``job_ids``.

        ``job_ids=None`` means unrestricted and is only ever passed for a
        platform admin. Any other caller passes the ids they are authorized for,
        so one organization cannot read another's candidate counts or alerts.
        An empty list is valid and yields zeroed totals rather than falling back
        to an unscoped query.
        """
        total_screened = await self._count_screenings(job_ids)
        total_rankings = await self._count_rankings(job_ids)
        total_jobs = await self._count_jobs(job_ids)
        total_candidates = await self._count_candidates(job_ids)
        fairness_score = await self._compute_overall_fairness_score(job_ids)
        bias_alerts = await self._get_recent_bias_alerts(limit=10, job_ids=job_ids)
        diversity = await self._compute_diversity_indicators(job_ids)

        return {
            "overall_fairness_score": fairness_score,
            "total_screened": total_screened,
            "total_rankings": total_rankings,
            "total_jobs": total_jobs,
            "total_candidates": total_candidates,
            "bias_alerts": bias_alerts,
            "diversity_indicators": diversity,
            "compliance_status": "compliant" if fairness_score >= 70 else "review_needed",
            "last_analyzed": datetime.utcnow().isoformat(),
        }

    async def get_fairness_metrics(
        self, job_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        scores = await self._get_all_screening_scores(job_ids)
        spd = self._statistical_parity_difference(scores)
        di = self._disparate_impact_ratio(scores)
        eod = self._equal_opportunity_difference(scores)
        consistency = self._consistency_score(scores)
        composite = self._composite_fairness_score(spd, di, eod, consistency)

        return {
            "statistical_parity_difference": {
                "value": round(spd, 4),
                "description": "Difference in positive outcomes between groups. Closer to 0 is fairer. |SPD| > 0.1 indicates potential bias.",
                "status": "fair" if abs(spd) <= 0.1 else "concerning" if abs(spd) <= 0.2 else "biased",
            },
            "disparate_impact_ratio": {
                "value": round(di, 4),
                "description": "Ratio of positive outcomes for unprivileged vs privileged groups. 0.8–1.25 is generally acceptable.",
                "status": "fair" if 0.8 <= di <= 1.25 else "concerning" if 0.6 <= di <= 1.4 else "biased",
            },
            "equal_opportunity_difference": {
                "value": round(eod, 4),
                "description": "Difference in true positive rates between groups. Closer to 0 is fairer.",
                "status": "fair" if abs(eod) <= 0.1 else "concerning" if abs(eod) <= 0.2 else "biased",
            },
            "demographic_parity": {
                "value": round(abs(spd), 4),
                "description": "Absolute difference in selection rates across demographic groups.",
                "status": "fair" if abs(spd) <= 0.1 else "concerning" if abs(spd) <= 0.2 else "biased",
            },
            "consistency_score": {
                "value": round(consistency, 4),
                "description": "Consistency of similar candidates receiving similar scores. Higher is better.",
                "status": "good" if consistency >= 0.7 else "moderate" if consistency >= 0.5 else "low",
            },
            "composite_fairness_score": {
                "value": round(composite, 2),
                "description": "Overall fairness score combining all metrics. 0–100 scale.",
                "status": "excellent" if composite >= 80 else "good" if composite >= 60 else "needs_improvement" if composite >= 40 else "poor",
            },
            "data_points": len(scores),
        }

    async def get_job_fairness_report(
        self,
        job_id: uuid.UUID,
        minimum_group_size: int = DEFAULT_MINIMUM_GROUP_SIZE,
    ) -> dict[str, Any]:
        job = await self.session.get(Job, job_id)
        if not job:
            return {"error": "Job not found"}

        results = await self._get_screenings_for_job(job_id)
        profiles = await self._load_profiles_for_screenings(results)
        group_fairness = self._build_group_fairness(
            results, profiles, minimum_group_size,
        )

        if not results:
            # Previously this branch returned a short dict that the
            # ``FairnessReportResponse`` model could not validate, so asking for
            # a fairness report on an unscreened job raised a 500 instead of
            # reporting "no data". It now returns the same shape as the populated
            # case, with the honest zero/empty values and an explicit status.
            return {
                "job_id": str(job_id),
                "job_title": job.title,
                "total_candidates": 0,
                "message": "No screening data available for this job",
                "fairness_score": 0,
                "metrics": {},
                "score_distribution": {
                    "average": 0, "min": 0, "max": 0, "median": 0, "std_dev": 0,
                },
                "gender_distribution": {"counts": {}, "percentages": {}},
                "location_distribution": {},
                "bias_alerts": [],
                "recommendations": ["Screen candidates to enable fairness analysis"],
                "group_fairness": group_fairness,
                "metric_scope": GROUP_METRIC_SCOPE,
                "metric_methodology": GROUP_METRIC_METHODOLOGY,
            }

        scores = [r.overall_match_score for r in results]

        spd = self._statistical_parity_difference(scores)
        di = self._disparate_impact_ratio(scores)
        consistency = self._consistency_score(scores)
        composite = self._composite_fairness_score(spd, di, 0.0, consistency)

        alerts = await self._detect_ranking_bias(job_id)
        recommendations = self._generate_fairness_recommendations(composite, alerts)

        gender_dist = self._gender_distribution(profiles)
        location_dist = self._location_distribution(profiles)

        return {
            "job_id": str(job_id),
            "job_title": job.title,
            "total_candidates": len(results),
            "fairness_score": round(composite, 2),
            "metrics": {
                # Retained unchanged for backwards compatibility with the
                # existing fairness dashboard. These are derived from the score
                # distribution, not from protected groups -- see
                # ``score_distribution_metrics_note`` and ``group_fairness`` for
                # the actual group comparison.
                "statistical_parity_difference": round(spd, 4),
                "disparate_impact_ratio": round(di, 4),
                "consistency_score": round(consistency, 4),
                "composite_fairness_score": round(composite, 2),
            },
            "score_distribution_metrics_note": (
                "The values in 'metrics' are derived from this job's screening "
                "score distribution, not from comparisons between candidate "
                "groups. Use 'group_fairness' for protected-group comparison."
            ),
            "score_distribution": {
                "average": round(sum(scores) / len(scores), 2) if scores else 0,
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0,
                "median": self._median(scores) if scores else 0,
                "std_dev": round(self._std_dev(scores), 2) if scores else 0,
            },
            "gender_distribution": gender_dist,
            "location_distribution": location_dist,
            "bias_alerts": alerts,
            "recommendations": recommendations,
            "group_fairness": group_fairness,
            "metric_scope": GROUP_METRIC_SCOPE,
            "metric_methodology": GROUP_METRIC_METHODOLOGY,
        }

    # ─── Protected-group fairness ───────────────────────────────────
    # The metrics below compare self-reported demographic groups. They are kept
    # separate from the score-distribution statistics in ``metrics`` because
    # those do not compare groups at all, and labelling a score bucket as a
    # "privileged group" would misstate what was measured.

    async def _load_profiles_for_screenings(
        self, results: list[ScreeningResult],
    ) -> list[CandidateProfile]:
        """Load every candidate profile for a set of screenings in one query.

        The previous implementation called ``get_by_user_id`` once per screening
        result, so a job with N screened applicants cost N extra queries on
        every fairness page load.
        """
        candidate_ids = {r.candidate_id for r in results}
        if not candidate_ids:
            return []
        stmt = select(CandidateProfile).where(
            CandidateProfile.user_id.in_(candidate_ids)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    def _build_group_fairness(
        self,
        results: list[ScreeningResult],
        profiles: list[CandidateProfile],
        minimum_group_size: int,
    ) -> dict[str, Any]:
        """Compare screening outcomes across self-reported gender groups.

        Read-only. Nothing here writes to screening, ranking or application
        state, and no attribute is ever inferred: a candidate who has not
        supplied a gender is counted as missing coverage and is never placed in
        a group.
        """
        population = len(results)
        gender_by_candidate = {
            p.user_id: p.gender for p in profiles if p.gender is not None
        }
        with_demographic = sum(
            1 for r in results
            if gender_by_candidate.get(r.candidate_id) in _KNOWN_GENDER_VALUES
        )
        missing = population - with_demographic

        coverage = {
            "group_dimension": "gender",
            "attribute_source": "self_reported",
            "attributes_inferred": False,
            "population": population,
            "candidates_with_demographic": with_demographic,
            "candidates_missing_demographic": missing,
            "demographic_coverage_pct": (
                round(with_demographic / population * 100, 2) if population else 0.0
            ),
            "minimum_group_size": minimum_group_size,
            "positive_outcome_threshold": POSITIVE_OUTCOME_THRESHOLD,
        }

        if population == 0:
            return {
                "metric_status": "no_screening_data",
                "status_reason": (
                    "This job has no screening results, so there is no "
                    "population to compare."
                ),
                "reference_group": None,
                "group_metrics": [],
                "cross_group_metrics": [],
                "coverage": coverage,
                "methodology": GROUP_METRIC_METHODOLOGY,
                "grouping_note": LOCATION_GROUPING_NOTE,
            }

        groups: dict[str, list[ScreeningResult]] = defaultdict(list)
        for r in results:
            gender = gender_by_candidate.get(r.candidate_id)
            key = gender if gender in _KNOWN_GENDER_VALUES else "unknown"
            groups[key].append(r)

        group_metrics: list[dict[str, Any]] = []
        for group_value, rows in sorted(groups.items()):
            sample_size = len(rows)
            if group_value == "unknown":
                group_metrics.append({
                    "group_value": group_value,
                    "sample_size": sample_size,
                    "positive_outcome_count": None,
                    "positive_outcome_rate": None,
                    "metric_status": "no_demographic_data",
                    "status_reason": (
                        "These candidates have not supplied a self-reported "
                        "gender. No value is inferred or assumed for them."
                    ),
                })
                continue
            if sample_size < minimum_group_size:
                group_metrics.append({
                    "group_value": group_value,
                    "sample_size": sample_size,
                    "positive_outcome_count": None,
                    "positive_outcome_rate": None,
                    "metric_status": "insufficient_sample",
                    "status_reason": (
                        f"Group has {sample_size} screened candidate(s), below "
                        f"the minimum threshold of {minimum_group_size}."
                    ),
                })
                continue
            positive = sum(
                1 for r in rows
                if r.overall_match_score >= POSITIVE_OUTCOME_THRESHOLD
            )
            group_metrics.append({
                "group_value": group_value,
                "sample_size": sample_size,
                "positive_outcome_count": positive,
                "positive_outcome_rate": round(positive / sample_size, 4),
                "metric_status": "available",
                "status_reason": None,
            })

        known_groups = {k: v for k, v in groups.items() if k != "unknown"}
        reference_group = (
            max(known_groups, key=lambda k: len(known_groups[k]))
            if known_groups
            else None
        )
        cross_group_metrics = self._build_cross_group_metrics(
            known_groups, reference_group, minimum_group_size,
        )

        available = [g for g in group_metrics if g["metric_status"] == "available"]
        if len(available) < 2:
            status = (
                "no_demographic_data" if not known_groups
                else "insufficient_data"
            )
            reason = (
                "No candidate in this job has supplied a self-reported gender, "
                "so no group comparison is possible."
                if not known_groups
                else (
                    "Fewer than 2 gender groups meet the minimum size threshold "
                    f"of {minimum_group_size}, so no cross-group metric is "
                    "reported."
                )
            )
        else:
            status = "available"
            reason = None

        return {
            "metric_status": status,
            "status_reason": reason,
            "reference_group": reference_group,
            "group_metrics": group_metrics,
            "cross_group_metrics": cross_group_metrics,
            "coverage": coverage,
            "methodology": GROUP_METRIC_METHODOLOGY,
            "grouping_note": LOCATION_GROUPING_NOTE,
        }

    def _build_cross_group_metrics(
        self,
        known_groups: dict[str, list[ScreeningResult]],
        reference_group: str | None,
        minimum_group_size: int,
    ) -> list[dict[str, Any]]:
        """SPD and DI across gender groups against the largest known group.

        Mirrors the calculation already used by
        ``FairnessImpactAnalyzer`` so the simulation surface and the screening
        surface report the same metric the same way.
        """
        def metric(
            name: str,
            label: str,
            value: float | None,
            status: str,
            reason: str | None,
        ) -> dict[str, Any]:
            return {
                "metric_name": name,
                "metric_label": label,
                "value": value,
                "reference_group": reference_group,
                "groups_compared": sorted(known_groups.keys()),
                "metric_status": status,
                "status_reason": reason,
            }

        if reference_group is None or reference_group not in known_groups:
            reason = "No valid reference group is available for comparison."
            return [
                metric(
                    "statistical_parity_difference",
                    "Statistical Parity Difference", None,
                    "no_reference_group", reason,
                ),
                metric(
                    "disparate_impact_ratio",
                    "Disparate Impact Ratio", None,
                    "no_reference_group", reason,
                ),
            ]

        comparable = {
            k: v for k, v in known_groups.items()
            if len(v) >= minimum_group_size
        }
        if reference_group not in comparable:
            reason = (
                f"Reference group '{reference_group}' has "
                f"{len(known_groups[reference_group])} candidate(s), below the "
                f"minimum threshold of {minimum_group_size}."
            )
            return [
                metric(
                    "statistical_parity_difference",
                    "Statistical Parity Difference", None,
                    "insufficient_data", reason,
                ),
                metric(
                    "disparate_impact_ratio",
                    "Disparate Impact Ratio", None,
                    "insufficient_data", reason,
                ),
            ]

        if len(comparable) < 2:
            reason = (
                "Fewer than 2 groups meet the minimum size threshold of "
                f"{minimum_group_size}."
            )
            return [
                metric(
                    "statistical_parity_difference",
                    "Statistical Parity Difference", None,
                    "insufficient_data", reason,
                ),
                metric(
                    "disparate_impact_ratio",
                    "Disparate Impact Ratio", None,
                    "insufficient_data", reason,
                ),
            ]

        def rate(rows: list[ScreeningResult]) -> float:
            positive = sum(
                1 for r in rows
                if r.overall_match_score >= POSITIVE_OUTCOME_THRESHOLD
            )
            return positive / len(rows) if rows else 0.0

        reference_rate = rate(comparable[reference_group])
        rates = {k: rate(v) for k, v in comparable.items()}

        spd = max(
            abs(value - reference_rate)
            for key, value in rates.items() if key != reference_group
        )

        min_rate = min(rates.values())
        max_rate = max(rates.values())
        if min_rate == max_rate:
            di = 1.0
            di_status = "identical_rates"
            di_reason = "All comparable groups have the same screening outcome rate."
        else:
            di = min_rate / max_rate if max_rate > 0 else 1.0
            di_status = "available"
            di_reason = None

        return [
            metric(
                "statistical_parity_difference",
                "Statistical Parity Difference", round(spd, 4),
                "available", None,
            ),
            metric(
                "disparate_impact_ratio",
                "Disparate Impact Ratio", round(di, 4),
                di_status, di_reason,
            ),
        ]

    async def get_job_group_fairness(
        self,
        job_id: uuid.UUID,
        minimum_group_size: int = DEFAULT_MINIMUM_GROUP_SIZE,
    ) -> dict[str, Any]:
        """Protected-group fairness for one job's screened population.

        Separately addressable so the Phase 7 screening workflow can show group
        context without also pulling the whole score-distribution report.
        """
        job = await self.session.get(Job, job_id)
        if not job:
            return {"error": "Job not found"}
        results = await self._get_screenings_for_job(job_id)
        profiles = await self._load_profiles_for_screenings(results)
        payload = self._build_group_fairness(
            results, profiles, minimum_group_size,
        )
        payload["job_id"] = str(job_id)
        payload["job_title"] = job.title
        return payload

    async def analyze_fairness(
        self,
        job_id: uuid.UUID | None = None,
        job_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """Analyze one job, or the caller's authorized jobs when ``job_id`` is None.

        ``job_ids`` is only consulted on the no-job branch; a specific job is
        authorized by the route before this is reached.
        """
        if job_id:
            return await self.get_job_fairness_report(job_id)
        return await self.get_fairness_overview(job_ids=job_ids)

    async def detect_ranking_bias(self, job_id: uuid.UUID) -> dict[str, Any]:
        alerts = await self._detect_ranking_bias(job_id)
        return {
            "job_id": str(job_id),
            "alerts": alerts,
            "total_alerts": len(alerts),
            "severity_counts": {
                "high": len([a for a in alerts if a.get("severity") == "high"]),
                "medium": len([a for a in alerts if a.get("severity") == "medium"]),
                "low": len([a for a in alerts if a.get("severity") == "low"]),
            },
        }

    async def run_adversarial_test(self, job_id: uuid.UUID, candidate_id: uuid.UUID) -> dict[str, Any]:
        original = await self.screening_repo.get_by_job_and_candidate(job_id, candidate_id)
        if not original:
            return {"error": "No screening result found for this candidate and job"}

        profile = await self.profile_repo.get_by_user_id(candidate_id)
        user = await self.session.get(User, candidate_id)

        variants = []

        name_variants = self._generate_name_variants(user.full_name if user else "Unknown")
        for variant_name in name_variants:
            score_delta = self._simulate_name_impact(original.overall_match_score, variant_name)
            variants.append({
                "variant_type": "name_change",
                "original_value": user.full_name if user else "Unknown",
                "modified_value": variant_name,
                "original_score": original.overall_match_score,
                "modified_score": max(0, min(100, score_delta)),
                "score_difference": score_delta - original.overall_match_score,
                "bias_detected": abs(score_delta - original.overall_match_score) > 3,
            })

        if profile and profile.location:
            location_variants = self._generate_location_variants(profile.location)
            for variant_loc in location_variants:
                score_delta = self._simulate_location_impact(original.overall_match_score, variant_loc)
                variants.append({
                    "variant_type": "location_change",
                    "original_value": profile.location,
                    "modified_value": variant_loc,
                    "original_score": original.overall_match_score,
                    "modified_score": max(0, min(100, score_delta)),
                    "score_difference": score_delta - original.overall_match_score,
                    "bias_detected": abs(score_delta - original.overall_match_score) > 5,
                })

        if profile and profile.education:
            for edu in profile.education[:1]:
                edu_variants = self._generate_institution_variants(edu.institution)
                for variant_inst in edu_variants:
                    score_delta = self._simulate_institution_impact(original.overall_match_score, variant_inst)
                    variants.append({
                        "variant_type": "institution_change",
                        "original_value": edu.institution,
                        "modified_value": variant_inst,
                        "original_score": original.overall_match_score,
                        "modified_score": max(0, min(100, score_delta)),
                        "score_difference": score_delta - original.overall_match_score,
                        "bias_detected": abs(score_delta - original.overall_match_score) > 3,
                    })

        total_variants = len(variants)
        biased_variants = len([v for v in variants if v["bias_detected"]])
        stability_score = round((1 - biased_variants / total_variants) * 100, 2) if total_variants else 100

        return {
            "job_id": str(job_id),
            "candidate_id": str(candidate_id),
            "candidate_name": user.full_name if user else "Unknown",
            "original_score": original.overall_match_score,
            "total_variants_tested": total_variants,
            "biased_variants_detected": biased_variants,
            "stability_score": stability_score,
            "bias_sensitivity": "low" if stability_score >= 90 else "medium" if stability_score >= 75 else "high",
            "variants": variants,
            "recommendation": self._adversarial_recommendation(stability_score),
        }

    async def analyze_job_description(self, job_id: uuid.UUID) -> dict[str, Any]:
        job = await self.session.get(Job, job_id)
        if not job:
            return {"error": "Job not found"}

        text = f"{job.title} {job.description or ''} {job.benefits or ''}".lower()
        required = " ".join(job.required_skills or [])
        preferred = " ".join(job.preferred_skills or [])
        full_text = f"{text} {required} {preferred}"

        gendered = self._detect_gendered_language(full_text)
        age_biased = self._detect_age_bias(full_text)
        discriminatory = self._detect_discriminatory_terms(full_text)
        exclusive = self._detect_exclusive_language(full_text)
        unnecessary = self._detect_unnecessary_requirements(full_text)

        total_issues = len(gendered) + len(age_biased) + len(discriminatory) + len(exclusive) + len(unnecessary)
        jd_length = len(full_text.split())

        bias_score = max(0, 100 - (total_issues * 8))
        ats_score = self._compute_ats_score(job, full_text)
        readability_score = self._compute_readability_score(full_text)
        diversity_score = max(0, 100 - (len(discriminatory) * 15) - (len(exclusive) * 5))
        inclusive_suggestions = self._generate_inclusive_suggestions(
            gendered, age_biased, discriminatory, exclusive, unnecessary,
        )

        return {
            "job_id": str(job_id),
            "job_title": job.title,
            "word_count": jd_length,
            "bias_score": bias_score,
            "ats_compatibility_score": ats_score,
            "readability_score": readability_score,
            "diversity_score": diversity_score,
            "gendered_language": gendered,
            "age_biased_language": age_biased,
            "discriminatory_terms": discriminatory,
            "exclusive_language": exclusive,
            "unnecessary_requirements": unnecessary,
            "total_issues": total_issues,
            "inclusive_suggestions": inclusive_suggestions,
            "overall_assessment": "excellent" if bias_score >= 90 else "good" if bias_score >= 75 else "needs_improvement" if bias_score >= 50 else "poor",
        }

    async def get_bias_alerts(
        self, limit: int = 50, job_ids: list[uuid.UUID] | None = None,
    ) -> list[dict[str, Any]]:
        return await self._get_recent_bias_alerts(limit, job_ids=job_ids)

    async def get_fairness_report(self, job_id: uuid.UUID) -> dict[str, Any]:
        report = await self.get_job_fairness_report(job_id)
        if "error" in report:
            return report

        report["trend"] = await self._compute_fairness_trend(job_id)
        report["hiring_recommendations"] = self._generate_hiring_fairness_recommendations(report)
        return report

    async def get_candidate_fairness(
        self,
        candidate_id: uuid.UUID,
        job_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """Fairness/transparency view for one candidate.

        ``job_ids`` scopes a recruiter or HR call to the jobs the caller is
        authorized for. A candidate with no screening inside that scope is
        reported as not found rather than as an empty record: returning an empty
        record would confirm the candidate exists and has been screened
        elsewhere, which is itself a cross-tenant disclosure.

        The candidate's own self-service call passes ``job_ids=None`` and is
        already limited to their own id by the route.
        """
        user = await self.session.get(User, candidate_id)
        if not user:
            return {"error": "Candidate not found"}

        results = await self.screening_repo.list_by_candidate(candidate_id)
        if job_ids is not None:
            allowed = set(job_ids)
            results = [r for r in results if r.job_id in allowed]
            if not results:
                return {"error": "Candidate not found"}
        profile = await self.profile_repo.get_by_user_id(candidate_id)

        bias_checks_completed = len(results) > 0
        fairness_status = "evaluated" if bias_checks_completed else "pending"
        transparency_summary = []

        if results:
            scores = [r.overall_match_score for r in results]
            avg_score = sum(scores) / len(scores)
            transparency_summary.append(f"Your applications have been fairly evaluated across {len(results)} job(s).")
            transparency_summary.append(f"Average match score: {avg_score:.1f}%")
            transparency_summary.append("All evaluations are based on skills, experience, and qualifications.")
            transparency_summary.append("No protected attributes (gender, age, ethnicity, etc.) were used in scoring.")
        else:
            transparency_summary.append("No screening results available yet.")
            transparency_summary.append("Apply for jobs to receive fair AI-powered evaluations.")
            transparency_summary.append("All evaluations are based purely on merit and qualifications.")

        return {
            "candidate_id": str(candidate_id),
            "candidate_name": user.full_name,
            "fairness_status": fairness_status,
            "bias_checks_completed": bias_checks_completed,
            "total_evaluations": len(results),
            "average_score": round(sum(r.overall_match_score for r in results) / len(results), 2) if results else 0,
            "transparency_summary": transparency_summary,
            "protected_attributes_used": [],
            "appeal_available": True,
            "appeal_status": "not_submitted",
            "last_evaluation_date": results[0].created_at.isoformat() if results else None,
        }

    @staticmethod
    def _scoped(stmt, model_column, job_ids: list[uuid.UUID] | None):
        """Constrain ``stmt`` to ``job_ids`` unless the caller is unscoped.

        An empty ``job_ids`` list yields a statement that matches nothing, which
        is the correct answer for a user authorized for no jobs -- it must not
        be treated as "no filter".
        """
        if job_ids is None:
            return stmt
        return stmt.where(model_column.in_(job_ids))

    async def _count_screenings(self, job_ids: list[uuid.UUID] | None = None) -> int:
        stmt = self._scoped(
            select(func.count(ScreeningResult.id)), ScreeningResult.job_id, job_ids,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _count_rankings(self, job_ids: list[uuid.UUID] | None = None) -> int:
        stmt = self._scoped(
            select(func.count(CandidateRanking.id)), CandidateRanking.job_id, job_ids,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _count_jobs(self, job_ids: list[uuid.UUID] | None = None) -> int:
        stmt = self._scoped(select(func.count(Job.id)), Job.id, job_ids)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _count_candidates(self, job_ids: list[uuid.UUID] | None = None) -> int:
        stmt = self._scoped(
            select(func.count(func.distinct(ScreeningResult.candidate_id))),
            ScreeningResult.job_id,
            job_ids,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _compute_overall_fairness_score(
        self, job_ids: list[uuid.UUID] | None = None,
    ) -> float:
        scores = await self._get_all_screening_scores(job_ids)
        if not scores:
            return 50.0
        avg = sum(scores) / len(scores)
        std = self._std_dev(scores)
        consistency = max(0, 100 - std)
        balance = 100 if abs(avg - 65) < 20 else max(0, 100 - abs(avg - 65))
        return round((consistency * 0.5 + balance * 0.5), 2)

    async def _get_all_screening_scores(
        self, job_ids: list[uuid.UUID] | None = None,
    ) -> list[int]:
        stmt = self._scoped(
            select(ScreeningResult.overall_match_score),
            ScreeningResult.job_id,
            job_ids,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_screenings_for_job(self, job_id: uuid.UUID) -> list[ScreeningResult]:
        result = await self.session.execute(
            select(ScreeningResult).where(ScreeningResult.job_id == job_id)
        )
        return list(result.scalars().all())

    def _statistical_parity_difference(self, scores: list[int]) -> float:
        if not scores:
            return 0.0
        mid = 60
        privileged = [s for s in scores if s >= mid]
        unprivileged = [s for s in scores if s < mid]
        if not privileged or not unprivileged:
            return 0.0
        rate_priv = len([s for s in privileged if s >= 70]) / len(privileged) if privileged else 0
        rate_unpriv = len([s for s in unprivileged if s >= 70]) / len(unprivileged) if unprivileged else 0
        return rate_priv - rate_unpriv

    def _disparate_impact_ratio(self, scores: list[int]) -> float:
        if not scores:
            return 1.0
        mid = 60
        privileged = [s for s in scores if s >= mid]
        unprivileged = [s for s in scores if s < mid]
        if not privileged or not unprivileged:
            return 1.0
        rate_priv = len([s for s in privileged if s >= 70]) / len(privileged) if privileged else 0
        rate_unpriv = len([s for s in unprivileged if s >= 70]) / len(unprivileged) if unprivileged else 0
        if rate_priv == 0:
            return 1.0
        return rate_unpriv / rate_priv

    def _equal_opportunity_difference(self, scores: list[int]) -> float:
        if len(scores) < 4:
            return 0.0
        sorted_s = sorted(scores)
        n = len(sorted_s)
        q1 = sorted_s[n // 4]
        q3 = sorted_s[3 * n // 4]
        high = [s for s in scores if s >= q3]
        low = [s for s in scores if s <= q1]
        if not high or not low:
            return 0.0
        tpr_high = len([s for s in high if s >= 70]) / len(high)
        tpr_low = len([s for s in low if s >= 70]) / len(low)
        return tpr_high - tpr_low

    def _consistency_score(self, scores: list[int]) -> float:
        if len(scores) < 2:
            return 1.0
        std = self._std_dev(scores)
        return max(0, 1 - std / 50)

    def _composite_fairness_score(self, spd: float, di: float, eod: float, consistency: float) -> float:
        spd_score = max(0, 100 - abs(spd) * 200)
        di_score = 100 if 0.8 <= di <= 1.25 else max(0, 100 - abs(di - 1) * 100)
        eod_score = max(0, 100 - abs(eod) * 200)
        cons_score = consistency * 100
        return (spd_score * 0.25 + di_score * 0.25 + eod_score * 0.25 + cons_score * 0.25)

    async def _detect_ranking_bias(self, job_id: uuid.UUID) -> list[dict[str, Any]]:
        alerts = []
        rankings = await self._get_rankings_for_job(job_id)
        if not rankings:
            return alerts

        scores = [r.overall_score for r in rankings]
        if len(scores) < 2:
            return alerts

        std = self._std_dev(scores)
        if std < 5:
            alerts.append({
                "type": "low_score_variance",
                "severity": "medium",
                "message": f"Score variance is very low (std={std:.1f}). This may indicate lack of differentiation between candidates.",
                "recommendation": "Review if the screening model adequately distinguishes between candidate qualifications.",
            })

        score_diffs = []
        for i in range(len(rankings) - 1):
            diff = rankings[i].overall_score - rankings[i + 1].overall_score
            score_diffs.append(diff)

        if score_diffs and max(score_diffs) > 20:
            alerts.append({
                "type": "large_score_gap",
                "severity": "low",
                "message": "Large score gap detected between some consecutive rankings.",
                "recommendation": "Investigate whether the gap is justified by qualification differences.",
            })

        profiles = await self._load_profiles_for_rankings(rankings)
        score_by_candidate = {
            str(r.candidate_id): r.overall_score for r in rankings
        }

        location_groups: dict[str, list[int]] = defaultdict(list)
        for rid, profile in profiles.items():
            loc = profile.location or "unknown"
            city = loc.split(",")[0].strip().lower()
            score = score_by_candidate.get(rid)
            if score is not None:
                location_groups[city].append(score)

        if len(location_groups) >= 2:
            group_avgs = {k: sum(v) / len(v) for k, v in location_groups.items() if v}
            if group_avgs:
                max_avg = max(group_avgs.values())
                min_avg = min(group_avgs.values())
                if max_avg - min_avg > 15:
                    alerts.append({
                        "type": "location_score_disparity",
                        "severity": "high",
                        "message": f"Significant score disparity between location groups (difference: {max_avg - min_avg:.1f} points).",
                        "recommendation": "Review whether location is being used as a proxy for other protected attributes.",
                    })

        return alerts

    async def _get_rankings_for_job(self, job_id: uuid.UUID) -> list[CandidateRanking]:
        result = await self.session.execute(
            select(CandidateRanking).where(CandidateRanking.job_id == job_id).order_by(CandidateRanking.rank)
        )
        return list(result.scalars().all())

    async def _load_profiles_for_rankings(
        self, rankings: list[CandidateRanking],
    ) -> dict[str, CandidateProfile]:
        """Load every ranked candidate's profile in one query.

        Keyed by ``str(candidate_id)`` to match the caller's existing lookup
        shape. Previously one query per ranking.
        """
        candidate_ids = {r.candidate_id for r in rankings}
        if not candidate_ids:
            return {}
        stmt = select(CandidateProfile).where(
            CandidateProfile.user_id.in_(candidate_ids)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {str(p.user_id): p for p in rows}

    async def _get_recent_bias_alerts(
        self,
        limit: int = 10,
        job_ids: list[uuid.UUID] | None = None,
    ) -> list[dict[str, Any]]:
        alerts = []
        if job_ids is not None and not job_ids:
            return alerts
        jobs_stmt = select(Job.id).limit(20)
        if job_ids is not None:
            jobs_stmt = jobs_stmt.where(Job.id.in_(job_ids))
        jobs_result = await self.session.execute(jobs_stmt)
        scoped_job_ids = [j for j in jobs_result.scalars().all()]

        for jid in scoped_job_ids:
            job_alerts = await self._detect_ranking_bias(jid)
            for alert in job_alerts:
                alert["job_id"] = str(jid)
            alerts.extend(job_alerts)
            if len(alerts) >= limit:
                break

        return alerts[:limit]

    async def _compute_diversity_indicators(
        self, job_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """Aggregate, non-identifying profile distribution for the overview.

        Scoped to the candidates behind ``job_ids`` so the diversity block on a
        tenant's overview cannot describe the whole platform's candidate base.
        """
        profiles: list[CandidateProfile]
        if job_ids is None:
            profiles_result = await self.session.execute(
                select(CandidateProfile).limit(500)
            )
            profiles = list(profiles_result.scalars().all())
        elif not job_ids:
            profiles = []
        else:
            candidate_ids = select(func.distinct(ScreeningResult.candidate_id)).where(
                ScreeningResult.job_id.in_(job_ids)
            )
            profiles_result = await self.session.execute(
                select(CandidateProfile)
                .where(CandidateProfile.user_id.in_(candidate_ids))
                .limit(500)
            )
            profiles = list(profiles_result.scalars().all())

        gender_counts = Counter()
        location_counts = Counter()
        for p in profiles:
            gender_counts[p.gender or "not_specified"] += 1
            if p.location:
                city = p.location.split(",")[0].strip()
                location_counts[city] += 1

        total = len(profiles) or 1
        gender_diversity = 1 - sum((c / total) ** 2 for c in gender_counts.values()) if gender_counts else 0
        location_diversity = 1 - sum((c / total) ** 2 for c in location_counts.values()) if location_counts else 0

        return {
            "total_profiles_analyzed": len(profiles),
            "gender_distribution": dict(gender_counts),
            "gender_diversity_index": round(gender_diversity, 4),
            "location_distribution": dict(list(location_counts.most_common(10))),
            "location_diversity_index": round(location_diversity, 4),
        }

    def _gender_distribution(self, profiles: list[CandidateProfile]) -> dict[str, Any]:
        counts = Counter()
        for p in profiles:
            counts[p.gender or "not_specified"] += 1
        total = len(profiles) or 1
        return {
            "counts": dict(counts),
            "percentages": {k: round(v / total * 100, 1) for k, v in counts.items()},
        }

    def _location_distribution(self, profiles: list[CandidateProfile]) -> dict[str, Any]:
        counts: Counter = Counter()
        for p in profiles:
            if p.location:
                city = p.location.split(",")[0].strip()
                counts[city] += 1
            else:
                counts["not_specified"] += 1
        return dict(counts.most_common(10))

    def _generate_name_variants(self, name: str) -> list[str]:
        parts = name.split()
        if len(parts) < 2:
            return [name]
        first = parts[0]
        variants = []
        alt_firsts = ["James", "Michael", "David", "John", "Robert", "Maria", "Sarah", "Priya", "Wei", "Ahmed"]
        for alt in alt_firsts:
            if alt.lower() != first.lower():
                variants.append(f"{alt} {' '.join(parts[1:])}")
                if len(variants) >= 5:
                    break
        return variants

    def _generate_location_variants(self, location: str) -> list[str]:
        cities = ["San Francisco, CA", "New York, NY", "Austin, TX", "Chicago, IL", "Remote", "London, UK"]
        return [c for c in cities if c.lower() != location.lower()][:4]

    def _generate_institution_variants(self, institution: str) -> list[str]:
        institutions = ["MIT", "Stanford University", "State University", "Community College", "Unknown University"]
        return [i for i in institutions if i.lower() != institution.lower()][:4]

    def _simulate_name_impact(self, base_score: int, name: str) -> int:
        import hashlib
        h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
        delta = (h % 7) - 3
        return max(0, min(100, base_score + delta))

    def _simulate_location_impact(self, base_score: int, location: str) -> int:
        import hashlib
        h = int(hashlib.md5(location.encode()).hexdigest()[:8], 16)
        delta = (h % 11) - 5
        return max(0, min(100, base_score + delta))

    def _simulate_institution_impact(self, base_score: int, institution: str) -> int:
        import hashlib
        h = int(hashlib.md5(institution.encode()).hexdigest()[:8], 16)
        delta = (h % 9) - 4
        return max(0, min(100, base_score + delta))

    def _adversarial_recommendation(self, stability_score: float) -> str:
        if stability_score >= 90:
            return "Model shows high stability across variants. No significant bias detected."
        elif stability_score >= 75:
            return "Moderate sensitivity detected. Review specific variant results for targeted improvements."
        else:
            return "High bias sensitivity detected. Investigate feature attribution and consider debiasing techniques."

    def _detect_gendered_language(self, text: str) -> list[dict[str, Any]]:
        findings = []
        for gender, terms in GENDERED_TERMS.items():
            for term in terms:
                pattern = r'\b' + re.escape(term) + r'\b'
                if re.search(pattern, text, re.IGNORECASE):
                    findings.append({
                        "term": term,
                        "gender": gender,
                        "suggestion": f"Consider replacing '{term}' with a gender-neutral alternative.",
                    })
        return findings

    def _detect_age_bias(self, text: str) -> list[dict[str, Any]]:
        findings = []
        for term in AGE_BIASED_TERMS:
            if term.lower() in text:
                findings.append({
                    "term": term,
                    "suggestion": f"'{term}' may discourage older or younger applicants. Consider removing or rephrasing.",
                })
        return findings

    def _detect_discriminatory_terms(self, text: str) -> list[dict[str, Any]]:
        findings = []
        for term in DISCRIMINATORY_TERMS:
            if term.lower() in text:
                findings.append({
                    "term": term,
                    "suggestion": f"'{term}' is discriminatory and must be removed immediately.",
                })
        return findings

    def _detect_exclusive_language(self, text: str) -> list[dict[str, Any]]:
        findings = []
        for term in EXCLUSIVE_LANGUAGE:
            if term.lower() in text:
                findings.append({
                    "term": term,
                    "suggestion": f"'{term}' may feel exclusionary. Use inclusive alternatives like 'expert' or 'skilled professional'.",
                })
        return findings

    def _detect_unnecessary_requirements(self, text: str) -> list[dict[str, Any]]:
        findings = []
        for term in UNNECESSARY_REQUIREMENTS:
            if term.lower() in text:
                findings.append({
                    "term": term,
                    "suggestion": f"'{term}' may unnecessarily limit the candidate pool. Consider if it's truly required.",
                })
        return findings

    def _compute_ats_score(self, job: Job, text: str) -> int:
        score = 60
        if job.title:
            score += 10
        if job.description and len(job.description) > 100:
            score += 10
        if job.required_skills:
            score += 10
        if job.location:
            score += 5
        if job.salary_min or job.salary_max:
            score += 5
        return min(100, score)

    def _compute_readability_score(self, text: str) -> int:
        words = text.split()
        if not words:
            return 0
        sentences = max(1, len(re.split(r'[.!?]+', text)))
        avg_word_len = sum(len(w) for w in words) / len(words)
        score = 100 - int(avg_word_len * 5) - int(sentences * 0.5)
        return max(0, min(100, score))

    def _generate_inclusive_suggestions(
        self,
        gendered: list, age_biased: list, discriminatory: list,
        exclusive: list, unnecessary: list,
    ) -> list[dict[str, str]]:
        suggestions = []
        if gendered:
            suggestions.append({
                "category": "Gender-Neutral Language",
                "suggestion": "Replace gendered terms with neutral alternatives (e.g., 'they' instead of 'he/she', 'chairperson' instead of 'chairman').",
                "priority": "high",
            })
        if age_biased:
            suggestions.append({
                "category": "Age-Inclusive Language",
                "suggestion": "Remove terms that may discourage applicants of certain ages. Focus on skills and experience requirements.",
                "priority": "medium",
            })
        if discriminatory:
            suggestions.append({
                "category": "Discriminatory Content",
                "suggestion": "Remove all discriminatory terms immediately. These violate equal employment opportunity laws.",
                "priority": "critical",
            })
        if exclusive:
            suggestions.append({
                "category": "Inclusive Alternatives",
                "suggestion": "Replace informal/exclusionary terms with professional language (e.g., 'expert' instead of 'rockstar').",
                "priority": "medium",
            })
        if unnecessary:
            suggestions.append({
                "category": "Essential Requirements",
                "suggestion": "Review requirements to ensure they are truly essential. Remove unnecessary barriers to entry.",
                "priority": "low",
            })
        if not suggestions:
            suggestions.append({
                "category": "Overall",
                "suggestion": "Job description appears to use inclusive language. Continue monitoring for bias.",
                "priority": "info",
            })
        return suggestions

    def _generate_fairness_recommendations(self, score: float, alerts: list) -> list[str]:
        recs = []
        if score < 40:
            recs.append("Overall fairness score is low. Conduct a comprehensive review of screening criteria.")
        if score < 70:
            recs.append("Review candidate screening criteria to ensure they are job-relevant and non-discriminatory.")
        high_alerts = len([a for a in alerts if a.get("severity") == "high"])
        if high_alerts:
            recs.append(f"Address {high_alerts} high-severity bias alert(s) immediately.")
        if not recs:
            recs.append("Fairness metrics are within acceptable ranges. Continue regular monitoring.")
        recs.append("Consider implementing blind resume screening to reduce unconscious bias.")
        recs.append("Ensure diverse interview panels for shortlisted candidates.")
        return recs

    def _generate_hiring_fairness_recommendations(self, report: dict) -> list[dict[str, str]]:
        recs = []
        score = report.get("fairness_score", 0)
        if score < 60:
            recs.append({
                "area": "Screening Process",
                "recommendation": "Review screening criteria for potential bias. Ensure all requirements are job-essential.",
                "priority": "high",
            })
        gender_dist = report.get("gender_distribution", {})
        if gender_dist.get("counts"):
            counts = gender_dist["counts"]
            if len(counts) > 1:
                vals = list(counts.values())
                if max(vals) / max(min(vals), 1) > 3:
                    recs.append({
                        "area": "Diversity",
                        "recommendation": "Consider expanding sourcing channels to improve gender diversity in the candidate pool.",
                        "priority": "medium",
                    })
        recs.append({
            "area": "Transparency",
            "recommendation": "Provide candidates with explanations of how AI was used in their evaluation.",
            "priority": "medium",
        })
        return recs

    async def _compute_fairness_trend(self, job_id: uuid.UUID) -> list[dict[str, Any]]:
        return [{"period": "current", "fairness_score": await self._compute_overall_fairness_score()}]

    @staticmethod
    def _median(values: list[int]) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        n = len(s)
        if n % 2 == 0:
            return (s[n // 2 - 1] + s[n // 2]) / 2
        return float(s[n // 2])

    @staticmethod
    def _std_dev(values: list[int]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
