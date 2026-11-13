"""Unit tests for Phase 8 — Explainability Impact Simulation.

Tests the ExplainabilityImpactAnalyzer service including:
- Weight change computation
- Per-dimension weighted contribution calculation
- Contribution comparison between baseline and simulation
- Score change attribution
- Rank-only changes
- Threshold-only changes
- Impact type classification
- Feature alignment
- Missing dimensions
- Zero weights
- Edge cases
- Deterministic output
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.simulation.explainability_impact_analyzer import (
    ExplainabilityImpactAnalyzer,
    DIMENSION_KEYS,
    _safe_divide,
)


# ─── Test Helpers ────────────────────────────────────────────────

WEIGHTS = {
    "skills": 0.40, "experience": 0.25, "education": 0.15,
    "projects": 0.20, "certifications": 0.0, "location": 0.0,
    "employment_type": 0.0, "semantic": 0.0,
}

WEIGHTS_SIM = {
    "skills": 0.30, "experience": 0.40, "education": 0.10,
    "projects": 0.20, "certifications": 0.0, "location": 0.0,
    "employment_type": 0.0, "semantic": 0.0,
}


def _make_analyzer() -> ExplainabilityImpactAnalyzer:
    return ExplainabilityImpactAnalyzer(session=AsyncMock())


DEFAULT_BASE_DIMS = {
    "skill": 80, "experience": 60, "education": 70, "project": 50,
    "certification": 40, "location": 90, "employment_type": 80, "semantic": 60,
}
DEFAULT_SIM_DIMS = {
    "skill": 70, "experience": 80, "education": 65, "project": 55,
    "certification": 40, "location": 90, "employment_type": 80, "semantic": 60,
}


def _make_result(
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
    baseline_dimensions: dict | None = None,
    simulation_dimensions: dict | None = None,
    candidate_id: uuid.UUID | None = None,
    reason: str | None = None,
    _use_defaults: bool = True,
) -> MagicMock:
    r = MagicMock()
    r.candidate_id = candidate_id or uuid.uuid4()
    r.candidate_name = "Test Candidate"
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
    if baseline_dimensions is not None:
        r.baseline_dimensions = baseline_dimensions
    else:
        r.baseline_dimensions = dict(DEFAULT_BASE_DIMS)
    if simulation_dimensions is not None:
        r.simulation_dimensions = simulation_dimensions
    else:
        r.simulation_dimensions = dict(DEFAULT_SIM_DIMS)
    r.reason = reason
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


# ─── Weight Change Tests ────────────────────────────────────────


class TestWeightChanges:
    def test_weight_changes_computed(self):
        analyzer = _make_analyzer()
        changes = analyzer._compute_weight_changes(WEIGHTS, WEIGHTS_SIM)

        assert len(changes) == 8
        skills_change = next(c for c in changes if c.feature == "skill")
        assert skills_change.baseline_weight == 0.40
        assert skills_change.simulation_weight == 0.30
        assert skills_change.weight_change == pytest.approx(-0.10, abs=0.001)

        exp_change = next(c for c in changes if c.feature == "experience")
        assert exp_change.weight_change == pytest.approx(0.15, abs=0.001)

    def test_no_weight_changes(self):
        analyzer = _make_analyzer()
        changes = analyzer._compute_weight_changes(WEIGHTS, WEIGHTS)
        assert all(c.weight_change == 0.0 for c in changes)

    def test_all_weights_changed(self):
        analyzer = _make_analyzer()
        changes = analyzer._compute_weight_changes({}, WEIGHTS_SIM)
        for c in changes:
            expected_sw = WEIGHTS_SIM.get(
                {"skill": "skills", "experience": "experience", "education": "education",
                 "project": "projects", "certification": "certifications",
                 "location": "location", "employment_type": "employment_type",
                 "semantic": "semantic"}[c.feature], 0.0
            )
            assert c.simulation_weight == expected_sw


# ─── Weighted Contribution Tests ────────────────────────────────


class TestWeightedContributions:
    def test_contributions_computed(self):
        analyzer = _make_analyzer()
        dimensions = {"skill": 80, "experience": 60}
        weights = {"skills": 0.40, "experience": 0.25}

        contribs = analyzer._compute_weighted_contributions(dimensions, weights)

        assert contribs["skill"] == pytest.approx(32.0, abs=0.1)
        assert contribs["experience"] == pytest.approx(15.0, abs=0.1)

    def test_missing_dimension_defaults_to_zero(self):
        analyzer = _make_analyzer()
        contribs = analyzer._compute_weighted_contributions({}, {"skills": 0.40})
        assert contribs["skill"] == 0.0

    def test_zero_weight_produces_zero_contribution(self):
        analyzer = _make_analyzer()
        contribs = analyzer._compute_weighted_contributions({"skill": 100}, {"skills": 0.0})
        assert contribs["skill"] == 0.0

    def test_all_dimensions_present(self):
        analyzer = _make_analyzer()
        dims = {"skill": 80, "experience": 60, "education": 70, "project": 50,
                "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        contribs = analyzer._compute_weighted_contributions(dims, WEIGHTS)
        assert len(contribs) == 8
        assert contribs["skill"] == pytest.approx(0.40 * 80, abs=0.1)
        assert contribs["experience"] == pytest.approx(0.25 * 60, abs=0.1)


# ─── Candidate Impact Tests ──────────────────────────────────────


class TestCandidateImpacts:
    def test_score_changed_impact_type(self):
        result = _make_result(score_change=5, rank_change=-3)
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS_SIM)

        assert len(impacts) == 1
        assert impacts[0].impact_type == "score_changed"

    def test_rank_only_changed_impact_type(self):
        result = _make_result(score_change=0, rank_change=-3, baseline_score=80, simulation_score=80)
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert len(impacts) == 1
        assert impacts[0].impact_type == "rank_only_changed"

    def test_threshold_only_impact_type(self):
        result = _make_result(
            score_change=0, rank_change=0,
            baseline_status="unqualified", simulation_status="qualified",
            baseline_score=68, simulation_score=68,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert len(impacts) == 1
        assert impacts[0].impact_type == "threshold_only"

    def test_unchanged_impact_type(self):
        result = _make_result(
            score_change=0, rank_change=0,
            baseline_score=80, simulation_score=80,
            baseline_status="qualified", simulation_status="qualified",
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert len(impacts) == 1
        assert impacts[0].impact_type == "unchanged"

    def test_feature_contributions_computed(self):
        base_dims = {"skill": 80, "experience": 60, "education": 70, "project": 50,
                     "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        sim_dims = {"skill": 70, "experience": 80, "education": 65, "project": 55,
                    "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        result = _make_result(baseline_dimensions=base_dims, simulation_dimensions=sim_dims, score_change=5)

        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS_SIM)

        assert len(impacts) == 1
        impact = impacts[0]
        assert len(impact.feature_contributions) == 8

        # Skills: 0.4*80=32 -> 0.3*70=21, change = -11
        skills_fc = next(fc for fc in impact.feature_contributions if fc.feature == "skill")
        assert skills_fc.baseline_contribution == pytest.approx(32.0, abs=0.1)
        assert skills_fc.simulation_contribution == pytest.approx(21.0, abs=0.1)
        assert skills_fc.contribution_change == pytest.approx(-11.0, abs=0.1)

        # Experience: 0.25*60=15 -> 0.4*80=32, change = +17
        exp_fc = next(fc for fc in impact.feature_contributions if fc.feature == "experience")
        assert exp_fc.baseline_contribution == pytest.approx(15.0, abs=0.1)
        assert exp_fc.simulation_contribution == pytest.approx(32.0, abs=0.1)
        assert exp_fc.contribution_change == pytest.approx(17.0, abs=0.1)

    def test_top_positive_negative_changes(self):
        base_dims = {"skill": 80, "experience": 40, "education": 70, "project": 50,
                     "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        sim_dims = {"skill": 60, "experience": 90, "education": 60, "project": 70,
                    "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        result = _make_result(
            baseline_dimensions=base_dims, simulation_dimensions=sim_dims,
            score_change=10, rank_change=0,
            baseline_rank=5, simulation_rank=5,
        )

        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        impact = impacts[0]
        assert len(impact.top_positive_changes) > 0
        assert len(impact.top_negative_changes) > 0

        # Experience: 0.25*40=10 -> 0.25*90=22.5, change = +12.5
        exp_fc = next(fc for fc in impact.top_positive_changes if fc.feature == "experience")
        assert exp_fc.contribution_change > 0

    def test_qualification_change_tracking(self):
        result = _make_result(
            baseline_status="unqualified", simulation_status="qualified",
            score_change=15, rank_change=0,
            baseline_rank=5, simulation_rank=5,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert impacts[0].qualification_change == "unqualified_to_qualified"

    def test_qualified_to_unqualified(self):
        result = _make_result(
            baseline_status="qualified", simulation_status="unqualified",
            score_change=-5, rank_change=0,
            baseline_rank=5, simulation_rank=5,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)
        assert impacts[0].qualification_change == "qualified_to_unqualified"

    def test_candidates_sorted_by_abs_score_change(self):
        r1 = _make_result(score_change=5, candidate_id=uuid.uuid4(), rank_change=0, baseline_rank=5, simulation_rank=5)
        r2 = _make_result(score_change=-20, candidate_id=uuid.uuid4(), rank_change=0, baseline_rank=5, simulation_rank=5)
        r3 = _make_result(score_change=10, candidate_id=uuid.uuid4(), rank_change=0, baseline_rank=5, simulation_rank=5)

        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([r1, r2, r3], WEIGHTS, WEIGHTS)

        score_changes = [abs(i.score_change) for i in impacts]
        assert score_changes == sorted(score_changes, reverse=True)


# ─── Summary Tests ───────────────────────────────────────────────


class TestSummary:
    def test_summary_computed(self):
        from app.domain.explainability_impact_schemas import (
            CandidateExplainabilityImpact,
            FeatureContributionChange,
        )

        analyzer = _make_analyzer()

        candidates = [
            MagicMock(
                score_change=5, rank_change=-3, impact_type="score_changed",
                feature_contributions=[FeatureContributionChange(
                    feature="skill", feature_label="Skills",
                    baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
                    baseline_dimension_score=80, simulation_dimension_score=85,
                    dimension_score_change=5, baseline_contribution=32.0,
                    simulation_contribution=34.0, contribution_change=2.0,
                )],
            ),
            MagicMock(
                score_change=0, rank_change=-2, impact_type="rank_only_changed",
                feature_contributions=[FeatureContributionChange(
                    feature="skill", feature_label="Skills",
                    baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
                    baseline_dimension_score=80, simulation_dimension_score=80,
                    dimension_score_change=0, baseline_contribution=32.0,
                    simulation_contribution=32.0, contribution_change=0.0,
                )],
            ),
            MagicMock(
                score_change=0, rank_change=0, impact_type="unchanged",
                feature_contributions=[FeatureContributionChange(
                    feature="skill", feature_label="Skills",
                    baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
                    baseline_dimension_score=80, simulation_dimension_score=80,
                    dimension_score_change=0, baseline_contribution=32.0,
                    simulation_contribution=32.0, contribution_change=0.0,
                )],
            ),
        ]

        summary = analyzer._compute_summary(candidates)

        assert summary.total_candidates == 3
        assert summary.candidates_with_score_changes == 1
        assert summary.candidates_with_rank_changes == 2
        assert summary.candidates_unchanged == 1
        assert summary.largest_score_increase == 5
        assert summary.largest_score_decrease == 0

    def test_empty_candidates(self):
        analyzer = _make_analyzer()
        summary = analyzer._compute_summary([])

        assert summary.total_candidates == 0
        assert summary.average_score_change == 0.0
        assert summary.largest_score_increase == 0
        assert summary.largest_score_decrease == 0

    def test_all_score_increases(self):
        from app.domain.explainability_impact_schemas import FeatureContributionChange

        fc = FeatureContributionChange(
            feature="skill", feature_label="Skills",
            baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
            baseline_dimension_score=60, simulation_dimension_score=90,
            dimension_score_change=30, baseline_contribution=24.0,
            simulation_contribution=36.0, contribution_change=12.0,
        )
        candidates = [
            MagicMock(score_change=12, rank_change=-2, impact_type="score_changed",
                       feature_contributions=[fc]),
            MagicMock(score_change=5, rank_change=-1, impact_type="score_changed",
                       feature_contributions=[fc]),
        ]
        analyzer = _make_analyzer()
        summary = analyzer._compute_summary(candidates)
        assert summary.largest_score_increase == 12
        assert summary.largest_score_decrease == 0

    def test_all_score_decreases(self):
        from app.domain.explainability_impact_schemas import FeatureContributionChange

        fc = FeatureContributionChange(
            feature="skill", feature_label="Skills",
            baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
            baseline_dimension_score=80, simulation_dimension_score=60,
            dimension_score_change=-20, baseline_contribution=32.0,
            simulation_contribution=24.0, contribution_change=-8.0,
        )
        candidates = [
            MagicMock(score_change=-8, rank_change=3, impact_type="score_changed",
                       feature_contributions=[fc]),
            MagicMock(score_change=-3, rank_change=1, impact_type="score_changed",
                       feature_contributions=[fc]),
        ]
        analyzer = _make_analyzer()
        summary = analyzer._compute_summary(candidates)
        assert summary.largest_score_decrease == -8
        assert summary.largest_score_increase == 0


# ─── Insights Tests ──────────────────────────────────────────────


class TestInsights:
    def test_weight_change_insights(self):
        from app.domain.explainability_impact_schemas import (
            WeightChange,
            ExplainabilityImpactSummary,
        )

        analyzer = _make_analyzer()
        summary = ExplainabilityImpactSummary(
            total_candidates=10, candidates_with_score_changes=5,
            candidates_with_rank_changes=7, candidates_with_contribution_changes=5,
            candidates_unchanged=3, average_score_change=3.5,
            largest_score_increase=15, largest_score_decrease=-8,
        )
        weight_changes = [
            WeightChange(feature="skill", feature_label="Skills",
                         baseline_weight=0.40, simulation_weight=0.30, weight_change=-0.10),
            WeightChange(feature="experience", feature_label="Experience",
                         baseline_weight=0.25, simulation_weight=0.40, weight_change=0.15),
        ]

        insights = analyzer._generate_insights(summary, weight_changes, [])
        weight_insights = [i for i in insights if i.type == "weight_change"]
        assert len(weight_insights) == 2

    def test_rank_only_insight(self):
        from app.domain.explainability_impact_schemas import ExplainabilityImpactSummary

        analyzer = _make_analyzer()
        summary = ExplainabilityImpactSummary(
            total_candidates=5, candidates_with_score_changes=3,
            candidates_with_rank_changes=4, candidates_with_contribution_changes=3,
            candidates_unchanged=1, average_score_change=2.0,
            largest_score_increase=10, largest_score_decrease=-5,
        )
        candidates = [
            MagicMock(impact_type="rank_only_changed"),
            MagicMock(impact_type="rank_only_changed"),
        ]

        insights = analyzer._generate_insights(summary, [], candidates)
        rank_insights = [i for i in insights if i.type == "rank_only_change"]
        assert len(rank_insights) == 1
        assert rank_insights[0].metric_value == 2

    def test_threshold_only_insight(self):
        from app.domain.explainability_impact_schemas import ExplainabilityImpactSummary

        analyzer = _make_analyzer()
        summary = ExplainabilityImpactSummary(
            total_candidates=5, candidates_with_score_changes=0,
            candidates_with_rank_changes=0, candidates_with_contribution_changes=0,
            candidates_unchanged=5, average_score_change=0.0,
            largest_score_increase=0, largest_score_decrease=0,
        )
        candidates = [
            MagicMock(impact_type="threshold_only"),
            MagicMock(impact_type="threshold_only"),
            MagicMock(impact_type="threshold_only"),
        ]

        insights = analyzer._generate_insights(summary, [], candidates)
        threshold_insights = [i for i in insights if i.type == "threshold_only_change"]
        assert len(threshold_insights) == 1
        assert threshold_insights[0].metric_value == 3

    def test_score_change_insights(self):
        from app.domain.explainability_impact_schemas import (
            ExplainabilityImpactSummary,
            FeatureContributionChange,
        )

        fc = FeatureContributionChange(
            feature="skill", feature_label="Skills",
            baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
            baseline_dimension_score=80, simulation_dimension_score=85,
            dimension_score_change=5, baseline_contribution=32.0,
            simulation_contribution=34.0, contribution_change=2.0,
        )
        candidates = [
            MagicMock(score_change=10, impact_type="score_changed",
                       feature_contributions=[fc]),
        ]
        summary = ExplainabilityImpactSummary(
            total_candidates=10, candidates_with_score_changes=7,
            candidates_with_rank_changes=8, candidates_with_contribution_changes=7,
            candidates_unchanged=2, average_score_change=3.5,
            largest_score_increase=15, largest_score_decrease=-8,
        )
        analyzer = _make_analyzer()
        insights = analyzer._generate_insights(summary, [], candidates)

        score_insights = [i for i in insights if i.type == "score_change_summary"]
        assert len(score_insights) >= 2
        assert any("7 of 10" in i.message for i in score_insights)

    def test_no_weight_change_insights_when_identical(self):
        from app.domain.explainability_impact_schemas import ExplainabilityImpactSummary

        analyzer = _make_analyzer()
        summary = ExplainabilityImpactSummary(
            total_candidates=0, candidates_with_score_changes=0,
            candidates_with_rank_changes=0, candidates_with_contribution_changes=0,
            candidates_unchanged=0, average_score_change=0.0,
            largest_score_increase=0, largest_score_decrease=0,
        )
        insights = analyzer._generate_insights(summary, [], [])
        weight_insights = [i for i in insights if i.type == "weight_change"]
        assert len(weight_insights) == 0

    def test_dominant_feature_insight(self):
        from app.domain.explainability_impact_schemas import (
            ExplainabilityImpactSummary,
            FeatureContributionChange,
        )

        fc_skill = FeatureContributionChange(
            feature="skill", feature_label="Skills",
            baseline_weight=0.4, simulation_weight=0.4, weight_change=0.0,
            baseline_dimension_score=80, simulation_dimension_score=60,
            dimension_score_change=-20, baseline_contribution=32.0,
            simulation_contribution=24.0, contribution_change=-8.0,
        )
        fc_exp = FeatureContributionChange(
            feature="experience", feature_label="Experience",
            baseline_weight=0.25, simulation_weight=0.25, weight_change=0.0,
            baseline_dimension_score=60, simulation_dimension_score=80,
            dimension_score_change=20, baseline_contribution=15.0,
            simulation_contribution=20.0, contribution_change=5.0,
        )
        candidates = [
            MagicMock(score_change=-3, impact_type="score_changed",
                       feature_contributions=[fc_skill, fc_exp]),
            MagicMock(score_change=-5, impact_type="score_changed",
                       feature_contributions=[fc_skill, fc_exp]),
        ]
        summary = ExplainabilityImpactSummary(
            total_candidates=2, candidates_with_score_changes=2,
            candidates_with_rank_changes=2, candidates_with_contribution_changes=2,
            candidates_unchanged=0, average_score_change=-4.0,
            largest_score_increase=0, largest_score_decrease=-5,
        )
        analyzer = _make_analyzer()
        insights = analyzer._generate_insights(summary, [], candidates)

        dominant = [i for i in insights if i.type == "dominant_feature"]
        assert len(dominant) == 1
        assert "Skills" in dominant[0].message


# ─── Edge Case Tests ─────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_results(self):
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([], {}, {})
        assert len(impacts) == 0

    def test_all_dimensions_missing(self):
        result = _make_result(
            baseline_dimensions={},
            simulation_dimensions={},
            score_change=0,
            rank_change=0,
            baseline_rank=5,
            simulation_rank=5,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert len(impacts) == 1
        assert impacts[0].impact_type == "unchanged"
        assert all(fc.contribution_change == 0.0 for fc in impacts[0].feature_contributions)

    def test_identical_baseline_simulation(self):
        dims = {"skill": 80, "experience": 60, "education": 70, "project": 50,
                "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        result = _make_result(
            baseline_dimensions=dims, simulation_dimensions=dims,
            score_change=0, rank_change=0,
            baseline_score=80, simulation_score=80,
            baseline_rank=5, simulation_rank=5,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert impacts[0].impact_type == "unchanged"
        assert all(fc.contribution_change == 0.0 for fc in impacts[0].feature_contributions)

    def test_single_dimension_change(self):
        base_dims = {"skill": 80, "experience": 60, "education": 70, "project": 50,
                     "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        sim_dims = {"skill": 90, "experience": 60, "education": 70, "project": 50,
                    "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        result = _make_result(
            baseline_dimensions=base_dims, simulation_dimensions=sim_dims,
            score_change=4, rank_change=0, baseline_rank=5, simulation_rank=5,
        )
        weights = {"skills": 0.40, "experience": 0.0, "education": 0.0,
                   "projects": 0.0, "certifications": 0.0, "location": 0.0,
                   "employment_type": 0.0, "semantic": 0.0}
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], weights, weights)

        skills_fc = next(fc for fc in impacts[0].feature_contributions if fc.feature == "skill")
        assert skills_fc.contribution_change == pytest.approx(4.0, abs=0.1)

    def test_multiple_candidates(self):
        results = [_make_result(
            score_change=i, candidate_id=uuid.uuid4(),
            rank_change=0, baseline_rank=5, simulation_rank=5,
        ) for i in range(5)]
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts(results, WEIGHTS, WEIGHTS)
        assert len(impacts) == 5

    def test_negative_score_change(self):
        result = _make_result(
            baseline_score=80, simulation_score=60, score_change=-20,
            rank_change=5, baseline_rank=5, simulation_rank=10,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert impacts[0].impact_type == "score_changed"
        assert impacts[0].score_change == -20

    def test_shortlisted_change(self):
        result = _make_result(
            baseline_shortlisted=True, simulation_shortlisted=False,
            score_change=0, rank_change=0,
            baseline_rank=5, simulation_rank=5,
        )
        analyzer = _make_analyzer()
        impacts = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS)

        assert impacts[0].baseline_shortlisted is True
        assert impacts[0].simulation_shortlisted is False


# ─── Schema Tests ────────────────────────────────────────────────


class TestSchemas:
    def test_feature_contribution_change_schema(self):
        from app.domain.explainability_impact_schemas import FeatureContributionChange

        fc = FeatureContributionChange(
            feature="skill", feature_label="Skills",
            baseline_weight=0.40, simulation_weight=0.30, weight_change=-0.10,
            baseline_dimension_score=80, simulation_dimension_score=70,
            dimension_score_change=-10,
            baseline_contribution=32.0, simulation_contribution=21.0,
            contribution_change=-11.0,
        )
        d = fc.model_dump()
        assert d["feature"] == "skill"
        assert d["contribution_change"] == -11.0

    def test_weight_change_schema(self):
        from app.domain.explainability_impact_schemas import WeightChange

        wc = WeightChange(
            feature="experience", feature_label="Experience",
            baseline_weight=0.25, simulation_weight=0.40, weight_change=0.15,
        )
        d = wc.model_dump()
        assert d["feature"] == "experience"

    def test_explainability_insight_schema(self):
        from app.domain.explainability_impact_schemas import ExplainabilityInsight

        i = ExplainabilityInsight(
            type="weight_change",
            message="Test message",
            metric_value=0.15,
            metric_unit="weight_fraction",
        )
        d = i.model_dump()
        assert d["type"] == "weight_change"

    def test_summary_schema(self):
        from app.domain.explainability_impact_schemas import ExplainabilityImpactSummary

        s = ExplainabilityImpactSummary(
            total_candidates=10, candidates_with_score_changes=5,
            candidates_with_rank_changes=7, candidates_with_contribution_changes=5,
            candidates_unchanged=3, average_score_change=3.5,
            largest_score_increase=15, largest_score_decrease=-8,
        )
        d = s.model_dump()
        assert d["total_candidates"] == 10


# ─── Deterministic Output Tests ──────────────────────────────────


class TestDeterministicOutput:
    def test_same_inputs_same_outputs(self):
        base_dims = {"skill": 80, "experience": 60, "education": 70, "project": 50,
                     "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        sim_dims = {"skill": 70, "experience": 80, "education": 65, "project": 55,
                    "certification": 40, "location": 90, "employment_type": 80, "semantic": 60}
        result = _make_result(baseline_dimensions=base_dims, simulation_dimensions=sim_dims)

        analyzer = _make_analyzer()
        impacts1 = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS_SIM)
        impacts2 = analyzer._compute_candidate_impacts([result], WEIGHTS, WEIGHTS_SIM)

        for i1, i2 in zip(impacts1, impacts2):
            assert i1.score_change == i2.score_change
            for fc1, fc2 in zip(i1.feature_contributions, i2.feature_contributions):
                assert fc1.contribution_change == fc2.contribution_change

    def test_weight_changes_deterministic(self):
        analyzer = _make_analyzer()
        bw = {"skills": 0.40, "experience": 0.25}
        sw = {"skills": 0.30, "experience": 0.40}

        changes1 = analyzer._compute_weight_changes(bw, sw)
        changes2 = analyzer._compute_weight_changes(bw, sw)

        for c1, c2 in zip(changes1, changes2):
            assert c1.weight_change == c2.weight_change

    def test_contributions_deterministic(self):
        analyzer = _make_analyzer()
        dims = {"skill": 80, "experience": 60}
        weights = {"skills": 0.40, "experience": 0.25}

        c1 = analyzer._compute_weighted_contributions(dims, weights)
        c2 = analyzer._compute_weighted_contributions(dims, weights)
        assert c1 == c2


# ─── Dimension Keys Tests ────────────────────────────────────────


class TestDimensionKeys:
    def test_all_dimensions_mapped(self):
        assert len(DIMENSION_KEYS) == 8
        expected = {"skill", "experience", "education", "project",
                    "certification", "location", "employment_type", "semantic"}
        assert set(DIMENSION_KEYS.keys()) == expected

    def test_weight_keys_match(self):
        expected_weight_keys = {"skills", "experience", "education", "projects",
                                "certifications", "location", "employment_type", "semantic"}
        assert set(DIMENSION_KEYS.values()) == expected_weight_keys
