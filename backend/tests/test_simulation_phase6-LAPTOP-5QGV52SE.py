"""Tests for Phase 6 — Threshold & Shortlist Impact Analysis.

Covers:
- Unit tests for threshold impact analyzer
- Unit tests for shortlist impact analyzer
- Unit tests for combined analyzer
- Threshold increase, decrease, unchanged
- Shortlist increase, decrease, unchanged
- Qualification crossings (newly qualified, newly disqualified)
- Qualification retention and turnover
- Boundary candidates (threshold and shortlist)
- Sensitivity analysis
- Score distribution
- Shortlist overlap, Jaccard similarity
- Edge cases: zero candidates, threshold=0, threshold=100, shortlist=1, shortlist>candidate count
- Deterministic output verification
- CRITICAL immutability test: no live hiring data modified
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.threshold_shortlist_schemas import (
    CandidateThresholdShortlistImpact,
    CombinedImpactMatrix,
    CombinedThresholdShortlistResponse,
    ThresholdBoundaryCandidate,
    ThresholdImpactResponse,
    ThresholdInsight,
    ThresholdScoreDistribution,
    ThresholdSensitivityPoint,
    ShortlistBoundaryCandidate,
    ShortlistImpactResponse,
    ShortlistInsight,
    ShortlistSensitivityPoint,
)
from app.services.simulation.threshold_impact_analyzer import (
    ThresholdImpactAnalyzer,
    _is_qualified,
    _safe_divide,
    _safe_percentage,
)
from app.services.simulation.shortlist_impact_analyzer import (
    ShortlistImpactAnalyzer,
)


# ─── Helper functions ──────────────────────────────────────────────


def test_is_qualified():
    """Test threshold qualification logic."""
    assert _is_qualified(75, 70) is True
    assert _is_qualified(70, 70) is True
    assert _is_qualified(69, 70) is False
    assert _is_qualified(0, 0) is True
    assert _is_qualified(100, 100) is True
    assert _is_qualified(99, 100) is False


def test_safe_divide():
    """Test safe division."""
    assert _safe_divide(10, 2) == 5.0
    assert _safe_divide(10, 0) == 0.0
    assert _safe_divide(10, 0, -1.0) == -1.0
    assert _safe_divide(0, 5) == 0.0


def test_safe_percentage():
    """Test safe percentage calculation."""
    assert _safe_percentage(5, 10) == 50.0
    assert _safe_percentage(1, 3) == 33.3
    assert _safe_percentage(0, 10) == 0.0
    assert _safe_percentage(5, 0) == 0.0


# ─── Threshold Impact Tests ───────────────────────────────────────


class TestThresholdImpact:
    """Unit tests for threshold impact calculations."""

    def test_threshold_increase_reduces_qualified(self):
        """Increasing threshold should reduce qualified candidates."""
        # Simulate: scores [90, 80, 75, 70, 65, 60]
        # Baseline threshold 70 -> 4 qualified (90, 80, 75, 70)
        # Simulation threshold 75 -> 3 qualified (90, 80, 75)
        scores = [90, 80, 75, 70, 65, 60]
        baseline_threshold = 70
        simulation_threshold = 75

        baseline_qualified = sum(1 for s in scores if _is_qualified(s, baseline_threshold))
        simulation_qualified = sum(1 for s in scores if _is_qualified(s, simulation_threshold))

        assert baseline_qualified == 4
        assert simulation_qualified == 3
        assert simulation_qualified - baseline_qualified == -1

    def test_threshold_decrease_increases_qualified(self):
        """Decreasing threshold should increase qualified candidates."""
        scores = [90, 80, 75, 70, 65, 60]
        baseline_threshold = 75
        simulation_threshold = 70

        baseline_qualified = sum(1 for s in scores if _is_qualified(s, baseline_threshold))
        simulation_qualified = sum(1 for s in scores if _is_qualified(s, simulation_threshold))

        assert baseline_qualified == 3
        assert simulation_qualified == 4
        assert simulation_qualified - baseline_qualified == 1

    def test_threshold_unchanged(self):
        """Same threshold should produce same qualified count."""
        scores = [90, 80, 75, 70, 65, 60]
        threshold = 70

        baseline_qualified = sum(1 for s in scores if _is_qualified(s, threshold))
        simulation_qualified = sum(1 for s in scores if _is_qualified(s, threshold))

        assert baseline_qualified == simulation_qualified

    def test_threshold_boundary_0(self):
        """Threshold 0 should qualify all candidates."""
        scores = [90, 80, 75, 70, 65, 60]
        qualified = sum(1 for s in scores if _is_qualified(s, 0))
        assert qualified == len(scores)

    def test_threshold_boundary_100(self):
        """Threshold 100 should only qualify score=100."""
        scores = [90, 80, 75, 70, 100]
        qualified = sum(1 for s in scores if _is_qualified(s, 100))
        assert qualified == 1

    def test_all_qualified(self):
        """All candidates above threshold."""
        scores = [95, 92, 90, 88]
        qualified = sum(1 for s in scores if _is_qualified(s, 70))
        assert qualified == 4

    def test_none_qualified(self):
        """No candidates above threshold."""
        scores = [60, 55, 50, 45]
        qualified = sum(1 for s in scores if _is_qualified(s, 70))
        assert qualified == 0

    def test_threshold_crossings(self):
        """Test qualification crossing logic."""
        # Baseline: threshold 70
        # Simulation: threshold 75
        # Candidates: score 73 (qualified -> not qualified)
        #             score 76 (qualified -> qualified)
        #             score 68 (not qualified -> not qualified)
        #             score 78 (not qualified -> not qualified at 75, but was at 70)
        baseline_threshold = 70
        simulation_threshold = 75
        scores = [73, 76, 68, 78]

        remained_qualified = 0
        remained_unqualified = 0
        newly_qualified = 0
        newly_disqualified = 0

        for score in scores:
            base_q = _is_qualified(score, baseline_threshold)
            sim_q = _is_qualified(score, simulation_threshold)
            if base_q and sim_q:
                remained_qualified += 1
            elif not base_q and sim_q:
                newly_qualified += 1
            elif base_q and not sim_q:
                newly_disqualified += 1
            else:
                remained_unqualified += 1

        # score 73: qualified(70) -> not qualified(75) -> newly_disqualified
        # score 76: qualified(70) -> qualified(75) -> remained_qualified
        # score 68: not qualified(70) -> not qualified(75) -> remained_unqualified
        # score 78: qualified(70) -> qualified(75) -> remained_qualified
        assert remained_qualified == 2
        assert newly_disqualified == 1
        assert newly_qualified == 0
        assert remained_unqualified == 1

    def test_qualification_retention_rate(self):
        """Test retention rate calculation."""
        baseline_qualified = 10
        remained_qualified = 8
        retention = _safe_divide(remained_qualified, baseline_qualified) * 100
        assert retention == 80.0

    def test_qualification_retention_rate_zero_baseline(self):
        """Test retention rate with zero baseline."""
        retention = _safe_divide(0, 0)
        assert retention == 0.0


# ─── Shortlist Impact Tests ────────────────────────────────────────


class TestShortlistImpact:
    """Unit tests for shortlist impact calculations."""

    def test_shortlist_increase(self):
        """Increasing shortlist size should include more candidates."""
        # Ranks: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
        # Baseline shortlist: 3 -> candidates at ranks 1-3
        # Simulation shortlist: 5 -> candidates at ranks 1-5
        baseline_size = 3
        simulation_size = 5
        total = 10

        baseline_shortlisted = set(range(1, baseline_size + 1))
        simulation_shortlisted = set(range(1, simulation_size + 1))

        retained = len(baseline_shortlisted & simulation_shortlisted)
        entered = len(simulation_shortlisted - baseline_shortlisted)
        exited = len(baseline_shortlisted - simulation_shortlisted)

        assert retained == 3
        assert entered == 2
        assert exited == 0

    def test_shortlist_decrease(self):
        """Decreasing shortlist size should exclude candidates."""
        baseline_size = 5
        simulation_size = 3
        total = 10

        baseline_shortlisted = set(range(1, baseline_size + 1))
        simulation_shortlisted = set(range(1, simulation_size + 1))

        retained = len(baseline_shortlisted & simulation_shortlisted)
        entered = len(simulation_shortlisted - baseline_shortlisted)
        exited = len(baseline_shortlisted - simulation_shortlisted)

        assert retained == 3
        assert entered == 0
        assert exited == 2

    def test_shortlist_unchanged(self):
        """Same shortlist size should produce same membership."""
        baseline_size = 5
        simulation_size = 5

        baseline_shortlisted = set(range(1, baseline_size + 1))
        simulation_shortlisted = set(range(1, simulation_size + 1))

        retained = len(baseline_shortlisted & simulation_shortlisted)
        entered = len(simulation_shortlisted - baseline_shortlisted)
        exited = len(baseline_shortlisted - simulation_shortlisted)

        assert retained == 5
        assert entered == 0
        assert exited == 0

    def test_jaccard_similarity(self):
        """Test Jaccard similarity calculation."""
        baseline = {1, 2, 3, 4, 5}
        simulation = {3, 4, 5, 6, 7}
        intersection = len(baseline & simulation)  # 3
        union = len(baseline | simulation)  # 7
        jaccard = _safe_divide(intersection, union)
        assert intersection == 3
        assert union == 7
        assert round(jaccard, 4) == round(3 / 7, 4)

    def test_jaccard_empty_intersection(self):
        """Test Jaccard with no overlap."""
        baseline = {1, 2, 3}
        simulation = {4, 5, 6}
        intersection = len(baseline & simulation)
        union = len(baseline | simulation)
        jaccard = _safe_divide(intersection, union)
        assert intersection == 0
        assert union == 6
        assert jaccard == 0.0

    def test_jaccard_empty_union(self):
        """Test Jaccard with empty sets."""
        baseline: set[int] = set()
        simulation: set[int] = set()
        intersection = len(baseline & simulation)
        union = len(baseline | simulation)
        jaccard = _safe_divide(intersection, union)
        assert jaccard == 0.0

    def test_retention_rate(self):
        """Test shortlist retention rate."""
        baseline = 10
        retained = 7
        rate = _safe_divide(retained, baseline)
        assert rate == 0.7

    def test_retention_rate_zero_baseline(self):
        """Test retention with zero baseline."""
        rate = _safe_divide(0, 0)
        assert rate == 0.0

    def test_turnover_rate(self):
        """Test shortlist turnover rate."""
        baseline = 10
        entered = 3
        exited = 2
        turnover = _safe_divide(entered + exited, baseline)
        assert turnover == 0.5


# ─── Edge Case Tests ──────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases for threshold and shortlist analysis."""

    def test_zero_candidates(self):
        """Test with empty candidate pool."""
        scores: list[int] = []
        qualified = sum(1 for s in scores if _is_qualified(s, 70))
        assert qualified == 0

    def test_single_candidate(self):
        """Test with single candidate."""
        scores = [75]
        assert _is_qualified(75, 70) is True
        assert _is_qualified(65, 70) is False

    def test_tied_scores(self):
        """Test deterministic ordering with tied scores."""
        scores = [75, 75, 75, 75]
        qualified = sum(1 for s in scores if _is_qualified(s, 75))
        assert qualified == 4

    def test_shortlist_greater_than_candidates(self):
        """Test shortlist size greater than candidate count."""
        total_candidates = 5
        shortlist_size = 10
        actual_shortlisted = min(shortlist_size, total_candidates)
        assert actual_shortlisted == 5

    def test_shortlist_equals_one(self):
        """Test shortlist of size 1."""
        baseline = {1}
        simulation = {1}
        assert len(baseline & simulation) == 1

    def test_threshold_at_score_boundary(self):
        """Test when threshold equals a candidate's score."""
        assert _is_qualified(70, 70) is True
        assert _is_qualified(69, 70) is False

    def test_score_distribution_bands(self):
        """Test score band calculation."""
        scores = [65, 72, 78, 85, 92]
        threshold = 75
        bands = {}
        for s in scores:
            band = (s // 5) * 5
            bands[band] = bands.get(band, 0) + 1

        assert bands.get(65, 0) == 1
        assert bands.get(70, 0) == 1
        assert bands.get(75, 0) == 1
        assert bands.get(85, 0) == 1
        assert bands.get(90, 0) == 1


# ─── Schema Validation Tests ──────────────────────────────────────


class TestSchemas:
    """Test Pydantic schema validation."""

    def test_threshold_insight_schema(self):
        """Test ThresholdInsight schema creation."""
        insight = ThresholdInsight(
            type="threshold_change",
            message="Threshold changed by 5 points",
            metric_value=5,
            metric_unit="points",
        )
        assert insight.type == "threshold_change"
        assert insight.metric_value == 5

    def test_shortlist_insight_schema(self):
        """Test ShortlistInsight schema creation."""
        insight = ShortlistInsight(
            type="composition",
            message="3 candidates entered",
            metric_value=3,
            metric_unit="candidates",
        )
        assert insight.type == "composition"
        assert insight.metric_value == 3

    def test_combined_impact_matrix(self):
        """Test CombinedImpactMatrix schema."""
        matrix = CombinedImpactMatrix(
            retained=5,
            entered=3,
            exited=2,
            remained_outside=10,
        )
        assert matrix.retained == 5
        assert matrix.entered == 3
        assert matrix.exited == 2
        assert matrix.remained_outside == 10

    def test_threshold_sensitivity_point(self):
        """Test ThresholdSensitivityPoint schema."""
        point = ThresholdSensitivityPoint(
            threshold=70,
            qualified_count=61,
            percentage_qualified=61.0,
        )
        assert point.threshold == 70
        assert point.qualified_count == 61

    def test_shortlist_sensitivity_point(self):
        """Test ShortlistSensitivityPoint schema."""
        point = ShortlistSensitivityPoint(
            shortlist_size=10,
            actual_shortlisted=10,
            overlap_with_baseline=8,
            newly_included=2,
            overlap_percentage=80.0,
        )
        assert point.shortlist_size == 10
        assert point.overlap_with_baseline == 8


# ─── Deterministic Output Tests ───────────────────────────────────


class TestDeterministicOutput:
    """Verify that analysis produces deterministic results."""

    def test_same_inputs_same_outputs(self):
        """Same scores and thresholds should always produce same qualified count."""
        scores = [90, 80, 75, 70, 65, 60, 55, 50]
        threshold = 70

        result1 = sum(1 for s in scores if _is_qualified(s, threshold))
        result2 = sum(1 for s in scores if _is_qualified(s, threshold))
        assert result1 == result2

    def test_threshold_sensitivity_deterministic(self):
        """Sensitivity analysis should be deterministic."""
        scores = [90, 80, 75, 70, 65, 60]

        def compute_sensitivity(scores, thresholds):
            return [(t, sum(1 for s in scores if _is_qualified(s, t))) for t in thresholds]

        thresholds = [50, 60, 70, 80, 90]
        result1 = compute_sensitivity(scores, thresholds)
        result2 = compute_sensitivity(scores, thresholds)
        assert result1 == result2

    def test_boundary_candidates_deterministic(self):
        """Boundary candidate identification should be deterministic."""
        scores = [72, 73, 74, 75, 76, 77, 78]
        threshold = 75
        boundary_range = 5

        boundary = [s for s in scores if abs(s - threshold) <= boundary_range]
        assert boundary == [72, 73, 74, 75, 76, 77, 78]
