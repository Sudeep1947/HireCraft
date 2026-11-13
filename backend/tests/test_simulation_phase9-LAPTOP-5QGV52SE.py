"""Unit tests for Phase 9 — Skill Impact Simulation.

Tests the SkillImpactAnalyzer service including:
- Skill change detection (added, removed, promoted, demoted, unchanged)
- Skill coverage computation
- Skill gap computation
- Candidate skill impact
- Skill enrichment
- Skill Graph relationships
- Summary computation
- Insight generation
- Edge cases
- Deterministic output
- Schema validation
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.simulation.skill_impact_analyzer import (
    SkillImpactAnalyzer,
    _detect_skill_changes,
    _normalize_skill,
    _safe_divide,
    _skill_list,
    _skill_list_raw,
)


# ─── Test Helpers ────────────────────────────────────────────────


BASELINE_CONFIG = {
    "requirements": {
        "mandatory_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker", "AWS"],
    },
    "scoring_weights": {
        "skills": 0.40, "experience": 0.25, "education": 0.15,
        "projects": 0.20, "certifications": 0.0, "location": 0.0,
        "employment_type": 0.0, "semantic": 0.0,
    },
    "threshold": 70,
    "shortlist_size": 10,
}

SIMULATION_CONFIG_PROMOTE_DOCKER = {
    "requirements": {
        "mandatory_skills": ["Python", "Docker"],
        "preferred_skills": ["PostgreSQL", "AWS"],
    },
    "scoring_weights": {
        "skills": 0.30, "experience": 0.40, "education": 0.10,
        "projects": 0.20, "certifications": 0.0, "location": 0.0,
        "employment_type": 0.0, "semantic": 0.0,
    },
    "threshold": 70,
    "shortlist_size": 10,
}

SIMULATION_CONFIG_ADD_KUBERNETES = {
    "requirements": {
        "mandatory_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker", "AWS", "Kubernetes"],
    },
    "scoring_weights": {
        "skills": 0.40, "experience": 0.25, "education": 0.15,
        "projects": 0.20, "certifications": 0.0, "location": 0.0,
        "employment_type": 0.0, "semantic": 0.0,
    },
    "threshold": 70,
    "shortlist_size": 10,
}

SIMULATION_CONFIG_REMOVE_SKILL = {
    "requirements": {
        "mandatory_skills": ["Python"],
        "preferred_skills": ["AWS"],
    },
    "scoring_weights": {
        "skills": 0.40, "experience": 0.25, "education": 0.15,
        "projects": 0.20, "certifications": 0.0, "location": 0.0,
        "employment_type": 0.0, "semantic": 0.0,
    },
    "threshold": 70,
    "shortlist_size": 10,
}

SIMULATION_CONFIG_IDENTICAL = {
    "requirements": {
        "mandatory_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker", "AWS"],
    },
    "scoring_weights": {
        "skills": 0.40, "experience": 0.25, "education": 0.15,
        "projects": 0.20, "certifications": 0.0, "location": 0.0,
        "employment_type": 0.0, "semantic": 0.0,
    },
    "threshold": 70,
    "shortlist_size": 10,
}


def _make_analyzer() -> SkillImpactAnalyzer:
    return SkillImpactAnalyzer(session=AsyncMock())


def _make_result(
    candidate_id: uuid.UUID | None = None,
    candidate_name: str = "Test Candidate",
    baseline_score: int = 70,
    simulation_score: int = 80,
    score_change: int = 10,
    baseline_rank: int = 10,
    simulation_rank: int = 5,
    rank_change: int = -5,
    baseline_status: str = "qualified",
    simulation_status: str = "qualified",
    baseline_shortlisted: bool = True,
    simulation_shortlisted: bool = True,
    baseline_matched_skills: list | None = None,
    simulation_matched_skills: list | None = None,
    baseline_missing_required: list | None = None,
    simulation_missing_required: list | None = None,
    baseline_missing_preferred: list | None = None,
    simulation_missing_preferred: list | None = None,
) -> MagicMock:
    r = MagicMock()
    r.candidate_id = candidate_id or uuid.uuid4()
    r.candidate_name = candidate_name
    r.baseline_score = baseline_score
    r.simulation_score = simulation_score
    r.score_change = score_change
    r.baseline_rank = baseline_rank
    r.simulation_rank = simulation_rank
    r.rank_change = rank_change
    r.baseline_status = baseline_status
    r.simulation_status = simulation_status
    r.baseline_shortlisted = baseline_shortlisted
    r.simulation_shortlisted = simulation_shortlisted
    r.baseline_matched_skills = baseline_matched_skills or ["Python"]
    r.simulation_matched_skills = simulation_matched_skills or ["Python"]
    r.baseline_missing_required = baseline_missing_required or []
    r.simulation_missing_required = simulation_missing_required or []
    r.baseline_missing_preferred = baseline_missing_preferred or []
    r.simulation_missing_preferred = simulation_missing_preferred or []
    return r


# ─── Safe Division Tests ─────────────────────────────────────────


class TestSafeDivide:
    def test_normal(self):
        assert _safe_divide(10, 2) == 5.0

    def test_zero_denominator(self):
        assert _safe_divide(10, 0) == 0.0

    def test_zero_denominator_custom_default(self):
        assert _safe_divide(10, 0, -1.0) == -1.0

    def test_zero_numerator(self):
        assert _safe_divide(0, 5) == 0.0


# ─── Normalize Skill Tests ───────────────────────────────────────


class TestNormalizeSkill:
    def test_lowercase(self):
        assert _normalize_skill("Python") == "python"

    def test_whitespace(self):
        assert _normalize_skill("  Docker  ") == "docker"

    def test_empty(self):
        assert _normalize_skill("") == ""


# ─── Skill List Tests ────────────────────────────────────────────


class TestSkillList:
    def test_extracts_mandatory(self):
        result = _skill_list(BASELINE_CONFIG, "mandatory_skills")
        assert set(result) == {"python", "postgresql"}

    def test_extracts_preferred(self):
        result = _skill_list(BASELINE_CONFIG, "preferred_skills")
        assert set(result) == {"docker", "aws"}

    def test_missing_key(self):
        result = _skill_list({}, "mandatory_skills")
        assert result == []

    def test_raw_preserves_case(self):
        result = _skill_list_raw(BASELINE_CONFIG, "mandatory_skills")
        assert "Python" in result
        assert "PostgreSQL" in result


# ─── Skill Change Detection Tests ────────────────────────────────


class TestDetectSkillChanges:
    def test_identical_configs_no_changes(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_IDENTICAL)
        assert all(c.change_type == "unchanged" for c in changes)

    def test_promoted_skill(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        docker_change = next(c for c in changes if c.skill_name.lower() == "docker")
        assert docker_change.change_type == "promoted"
        assert docker_change.baseline_requirement == "preferred"
        assert docker_change.simulation_requirement == "mandatory"

    def test_demoted_skill(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        pg_change = next(c for c in changes if c.skill_name.lower() == "postgresql")
        assert pg_change.change_type == "demoted"
        assert pg_change.baseline_requirement == "mandatory"
        assert pg_change.simulation_requirement == "preferred"

    def test_added_skill(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_ADD_KUBERNETES)
        k8s_change = next(c for c in changes if c.skill_name.lower() == "kubernetes")
        assert k8s_change.change_type == "added"
        assert k8s_change.baseline_requirement == "not_required"
        assert k8s_change.simulation_requirement == "preferred"

    def test_removed_skill(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_REMOVE_SKILL)
        removed = [c for c in changes if c.change_type == "removed"]
        removed_names = {c.skill_name.lower() for c in removed}
        assert "postgresql" in removed_names or "docker" in removed_names

    def test_unchanged_skills(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        python_change = next(c for c in changes if c.skill_name.lower() == "python")
        assert python_change.change_type == "unchanged"

    def test_all_change_types_detected(self):
        changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        change_types = {c.change_type for c in changes}
        assert "promoted" in change_types
        assert "demoted" in change_types
        assert "unchanged" in change_types

    def test_empty_configs(self):
        changes = _detect_skill_changes({}, {})
        assert changes == []


# ─── Coverage Tests ──────────────────────────────────────────────


class TestSkillCoverage:
    def test_coverage_computed(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python", "Docker"],
                simulation_matched_skills=["Python", "Docker", "PostgreSQL"],
            ),
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python", "Docker"],
            ),
            _make_result(
                baseline_matched_skills=["Python", "PostgreSQL"],
                simulation_matched_skills=["Python", "PostgreSQL"],
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        coverage = analyzer._compute_skill_coverage(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        assert len(coverage) > 0
        python_cov = next(c for c in coverage if c.skill_name.lower() == "python")
        assert python_cov.total_eligible == 3
        assert python_cov.baseline_candidates_match == 3
        assert python_cov.simulation_candidates_match == 3

    def test_empty_results(self):
        analyzer = _make_analyzer()
        coverage = analyzer._compute_skill_coverage([], [], BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        assert coverage == []

    def test_coverage_change_computed(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python", "Docker"],
            ),
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python"],
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        coverage = analyzer._compute_skill_coverage(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        docker_cov = next(c for c in coverage if c.skill_name.lower() == "docker")
        # Baseline: 0/2=0.0, Sim: 1/2=0.5, change: 0.5
        assert docker_cov.coverage_change == pytest.approx(0.5, abs=0.01)


# ─── Gap Tests ───────────────────────────────────────────────────


class TestSkillGaps:
    def test_gaps_computed_from_coverage(self):
        from app.domain.skill_impact_schemas import SkillCoverage

        coverage = [
            SkillCoverage(
                skill_name="Python",
                baseline_coverage=1.0,
                simulation_coverage=1.0,
                coverage_change=0.0,
                total_eligible=10,
                is_mandatory_simulation=True,
            ),
            SkillCoverage(
                skill_name="Docker",
                baseline_coverage=0.5,
                simulation_coverage=0.7,
                coverage_change=0.2,
                total_eligible=10,
                is_mandatory_simulation=True,
            ),
        ]
        analyzer = _make_analyzer()
        gaps = analyzer._compute_skill_gaps(coverage)

        assert len(gaps) == 2
        py_gap = next(g for g in gaps if g.skill_name == "Python")
        assert py_gap.baseline_gap == 0.0
        assert py_gap.simulation_gap == 0.0

        docker_gap = next(g for g in gaps if g.skill_name == "Docker")
        assert docker_gap.baseline_gap == pytest.approx(0.5, abs=0.01)
        assert docker_gap.simulation_gap == pytest.approx(0.3, abs=0.01)
        assert docker_gap.gap_change == pytest.approx(-0.2, abs=0.01)


# ─── Candidate Impact Tests ──────────────────────────────────────


class TestCandidateImpacts:
    def test_candidates_with_changes_included(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python", "Docker"],
                score_change=5,
            ),
            _make_result(
                baseline_matched_skills=["Python", "Docker"],
                simulation_matched_skills=["Python"],
                score_change=-3,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        assert len(impacts) == 2

    def test_skills_gained_detected(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python", "Docker"],
                score_change=5,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        assert len(impacts) == 1
        assert "docker" in impacts[0].skills_gained

    def test_skills_lost_detected(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python", "Docker"],
                simulation_matched_skills=["Python"],
                score_change=-3,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        assert len(impacts) == 1
        assert "docker" in impacts[0].skills_lost

    def test_qualification_change(self):
        results = [
            _make_result(
                baseline_status="unqualified",
                simulation_status="qualified",
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python", "PostgreSQL"],
                score_change=15,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        assert len(impacts) == 1
        assert impacts[0].qualification_change == "newly_qualified"

    def test_sorted_by_abs_score_change(self):
        results = [
            _make_result(score_change=3, baseline_matched_skills=["Python"], simulation_matched_skills=["Python", "Docker"]),
            _make_result(score_change=-20, baseline_matched_skills=["Python"], simulation_matched_skills=["Python"]),
            _make_result(score_change=10, baseline_matched_skills=["Python"], simulation_matched_skills=["Python", "Docker"]),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        score_changes = [abs(i.score_change) for i in impacts]
        assert score_changes == sorted(score_changes, reverse=True)


# ─── Skill Enrichment Tests ─────────────────────────────────────


class TestSkillEnrichment:
    def test_enrichment_adds_metrics(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python", "Docker"],
                simulation_matched_skills=["Python", "Docker"],
            ),
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python", "Docker"],
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        analyzer._enrich_skill_changes(
            skill_changes, results, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        docker = next(sc for sc in skill_changes if sc.skill_name.lower() == "docker")
        assert docker.simulation_candidates_match == 2

    def test_enrichment_empty_results(self):
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        analyzer._enrich_skill_changes(
            skill_changes, [], BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )
        # Should not raise, enrichment just does nothing


# ─── Summary Tests ───────────────────────────────────────────────


class TestSummary:
    def test_summary_computed(self):
        from app.domain.skill_impact_schemas import CandidateSkillImpact

        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)

        candidates = [
            MagicMock(
                qualification_change="newly_qualified",
                skill_match_change=1,
            ),
            MagicMock(
                qualification_change="remained_qualified",
                skill_match_change=0,
            ),
        ]

        summary = analyzer._compute_summary(skill_changes, candidates, [])

        assert summary.total_skills_analyzed == len(skill_changes)
        assert summary.candidates_affected == 2
        assert summary.candidates_newly_qualified == 1
        assert summary.candidates_newly_disqualified == 0

    def test_empty_summary(self):
        analyzer = _make_analyzer()
        summary = analyzer._compute_summary([], [], [])
        assert summary.total_skills_analyzed == 0
        assert summary.candidates_affected == 0


# ─── Insights Tests ──────────────────────────────────────────────


class TestInsights:
    def test_added_skills_insight(self):
        from app.domain.skill_impact_schemas import SkillImpactSummary, SkillGap

        analyzer = _make_analyzer()
        summary = SkillImpactSummary(skills_added=2)
        skill_changes = [
            MagicMock(change_type="added", skill_name="Kubernetes"),
            MagicMock(change_type="added", skill_name="Terraform"),
        ]
        insights = analyzer._generate_insights(summary, skill_changes, [], [])

        added_insights = [i for i in insights if i.type == "skills_added"]
        assert len(added_insights) == 1
        assert "Kubernetes" in added_insights[0].message

    def test_largest_gap_insight(self):
        from app.domain.skill_impact_schemas import SkillImpactSummary, SkillGap

        analyzer = _make_analyzer()
        summary = SkillImpactSummary()
        gaps = [
            SkillGap(skill_name="Python", simulation_gap=0.18, is_required=True),
            SkillGap(skill_name="Kubernetes", simulation_gap=0.58, is_required=True),
        ]
        insights = analyzer._generate_insights(summary, [], gaps, [])

        gap_insights = [i for i in insights if i.type == "largest_skill_gap"]
        assert len(gap_insights) == 1
        assert "Kubernetes" in gap_insights[0].message


# ─── Skill Graph Tests ──────────────────────────────────────────


class TestSkillGraph:
    def test_graph_relationships_computed(self):
        analyzer = _make_analyzer()
        skill_changes = [
            MagicMock(change_type="promoted", skill_name="Docker"),
            MagicMock(change_type="unchanged", skill_name="Python"),
        ]
        relationships = analyzer._compute_graph_relationships(skill_changes)

        # Should only find relationships for changed skills (Docker)
        # The actual relationships depend on the SkillGraph data
        for rel in relationships:
            assert rel.source_skill.lower() == "docker"

    def test_no_relationships_for_unchanged(self):
        analyzer = _make_analyzer()
        skill_changes = [
            MagicMock(change_type="unchanged", skill_name="Python"),
        ]
        relationships = analyzer._compute_graph_relationships(skill_changes)
        assert len(relationships) == 0


# ─── Edge Case Tests ─────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_results_no_crash(self):
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts(
            [], _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER),
            BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )
        assert impacts == []

    def test_all_candidates_unchanged(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python"],
                simulation_matched_skills=["Python"],
                score_change=0,
                rank_change=0,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )
        assert len(impacts) == 0

    def test_identical_configs(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python", "Docker"],
                simulation_matched_skills=["Python", "Docker"],
                score_change=0,
                rank_change=0,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_IDENTICAL)
        impacts = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_IDENTICAL,
        )
        assert len(impacts) == 0

    def test_missing_requirements_key(self):
        changes = _detect_skill_changes({"requirements": {}}, {"requirements": {}})
        assert changes == []

    def test_empty_skill_lists(self):
        changes = _detect_skill_changes(
            {"requirements": {"mandatory_skills": [], "preferred_skills": []}},
            {"requirements": {"mandatory_skills": [], "preferred_skills": []}},
        )
        assert changes == []


# ─── Schema Tests ────────────────────────────────────────────────


class TestSchemas:
    def test_skill_change_schema(self):
        from app.domain.skill_impact_schemas import SkillChange

        sc = SkillChange(
            skill_name="Docker",
            change_type="promoted",
            baseline_requirement="preferred",
            simulation_requirement="mandatory",
        )
        d = sc.model_dump()
        assert d["skill_name"] == "Docker"
        assert d["change_type"] == "promoted"

    def test_skill_coverage_schema(self):
        from app.domain.skill_impact_schemas import SkillCoverage

        cov = SkillCoverage(
            skill_name="Python",
            baseline_coverage=0.82,
            simulation_coverage=0.82,
            coverage_change=0.0,
            total_eligible=50,
        )
        d = cov.model_dump()
        assert d["baseline_coverage"] == 0.82

    def test_skill_gap_schema(self):
        from app.domain.skill_impact_schemas import SkillGap

        gap = SkillGap(
            skill_name="Kubernetes",
            baseline_gap=0.58,
            simulation_gap=0.42,
            gap_change=-0.16,
            is_required=True,
        )
        d = gap.model_dump()
        assert d["gap_change"] == -0.16

    def test_summary_schema(self):
        from app.domain.skill_impact_schemas import SkillImpactSummary

        s = SkillImpactSummary(
            total_skills_analyzed=10,
            skills_added=2,
            skills_removed=1,
            skills_promoted=1,
            skills_demoted=1,
            skills_unchanged=5,
            candidates_affected=18,
        )
        d = s.model_dump()
        assert d["total_skills_analyzed"] == 10

    def test_candidate_impact_schema(self):
        from app.domain.skill_impact_schemas import CandidateSkillImpact

        c = CandidateSkillImpact(
            candidate_id=uuid.uuid4(),
            candidate_name="Test",
            skills_gained=["Docker"],
            skills_lost=["AWS"],
            qualification_change="newly_qualified",
        )
        d = c.model_dump()
        assert d["qualification_change"] == "newly_qualified"


# ─── Deterministic Output Tests ──────────────────────────────────


class TestDeterministicOutput:
    def test_same_inputs_same_outputs(self):
        results = [
            _make_result(
                baseline_matched_skills=["Python", "Docker"],
                simulation_matched_skills=["Python", "Docker", "AWS"],
                score_change=5,
            ),
        ]
        analyzer = _make_analyzer()
        skill_changes = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)

        impacts1 = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )
        impacts2 = analyzer._compute_candidate_impacts(
            results, skill_changes, BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER,
        )

        for i1, i2 in zip(impacts1, impacts2):
            assert i1.skills_gained == i2.skills_gained
            assert i1.skills_lost == i2.skills_lost
            assert i1.score_change == i2.score_change

    def test_skill_changes_deterministic(self):
        changes1 = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        changes2 = _detect_skill_changes(BASELINE_CONFIG, SIMULATION_CONFIG_PROMOTE_DOCKER)
        for c1, c2 in zip(changes1, changes2):
            assert c1.change_type == c2.change_type
            assert c1.skill_name == c2.skill_name
