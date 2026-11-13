"""Unit tests for Phase 7 — Fairness Impact Simulation.

Tests the FairnessImpactAnalyzer service including:
- Selection rate calculation per group
- Statistical Parity Difference (SPD)
- Disparate Impact Ratio (DI)
- Group aggregation and demographics
- Candidate transitions (entered/exited/retained)
- Reference group selection
- Missing demographic data handling
- Zero denominators
- Small sample groups
- Zero candidates
- Identical baseline/simulation
- Changed selection outcomes
- Multiple groups
- Insights generation
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.simulation.fairness_impact_analyzer import (
    FairnessImpactAnalyzer,
    _safe_divide,
    _safe_percentage,
)


# ─── Test Helpers ────────────────────────────────────────────────


def _make_result(
    baseline_shortlisted: bool = False,
    simulation_shortlisted: bool = False,
    candidate_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock SimulationResult."""
    r = MagicMock()
    r.candidate_id = candidate_id or uuid.uuid4()
    r.baseline_shortlisted = baseline_shortlisted
    r.simulation_shortlisted = simulation_shortlisted
    return r


def _make_results(
    group_configs: dict[str, list[tuple[bool, bool]]],
) -> list[MagicMock]:
    """Create mock results grouped by name.

    Args:
        group_configs: dict of group_name -> list of (baseline_shortlisted, simulation_shortlisted)
    """
    results = []
    for group_name, configs in group_configs.items():
        for base, sim in configs:
            r = _make_result(baseline_shortlisted=base, simulation_shortlisted=sim)
            r._group_name = group_name  # for debugging
            results.append(r)
    return results


# ─── Safe Division Tests ─────────────────────────────────────────


class TestSafeDivide:
    def test_normal_division(self):
        assert _safe_divide(10, 2) == 5.0

    def test_zero_denominator(self):
        assert _safe_divide(10, 0) == 0.0

    def test_zero_denominator_custom_default(self):
        assert _safe_divide(10, 0, -1.0) == -1.0

    def test_zero_numerator(self):
        assert _safe_divide(0, 5) == 0.0

    def test_both_zero(self):
        assert _safe_divide(0, 0) == 0.0

    def test_float_result(self):
        assert _safe_divide(1, 3) == pytest.approx(0.333333, abs=0.001)


class TestSafePercentage:
    def test_normal_percentage(self):
        assert _safe_percentage(25, 100) == 25.0

    def test_zero_total(self):
        assert _safe_percentage(5, 0) == 0.0

    def test_partial_percentage(self):
        assert _safe_percentage(1, 3) == pytest.approx(33.33, abs=0.01)


# ─── Group Metric Tests ──────────────────────────────────────────


class TestGroupMetrics:
    """Test per-group fairness metric computation."""

    def test_two_groups_both_available(self):
        """Two groups with enough members produce available metrics."""
        male_results = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(True, False),
            _make_result(False, False),
            _make_result(False, True),
        ]
        female_results = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
        ]

        groups = {"male": male_results, "female": female_results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )

        male_metrics = next(m for m in metrics if m.group_value == "male")
        female_metrics = next(m for m in metrics if m.group_value == "female")

        assert male_metrics.metric_status == "available"
        assert female_metrics.metric_status == "available"
        assert male_metrics.sample_size == 5
        assert female_metrics.sample_size == 5

        # male: 3 baseline selected / 5 = 0.6, 3 sim selected / 5 = 0.6
        assert male_metrics.baseline_selected_count == 3
        assert male_metrics.simulation_selected_count == 3

        # female: 3 baseline selected / 5 = 0.6, 3 sim selected / 5 = 0.6
        assert female_metrics.baseline_selected_count == 3
        assert female_metrics.simulation_selected_count == 3

    def test_group_below_minimum_size(self):
        """Groups below minimum size are marked insufficient_sample."""
        small_group = [
            _make_result(True, True),
            _make_result(False, False),
        ]
        groups = {"other": small_group}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=5,
        )

        assert len(metrics) == 1
        assert metrics[0].metric_status == "insufficient_sample"
        assert "2 candidate(s)" in metrics[0].status_reason

    def test_unknown_gender_group(self):
        """Unknown gender candidates get no_demographic_data status."""
        unknown_results = [
            _make_result(True, True),
            _make_result(False, False),
        ]
        groups = {"unknown": unknown_results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=1,
        )

        assert len(metrics) == 1
        assert metrics[0].metric_status == "no_demographic_data"

    def test_candidate_transitions(self):
        """Transitions are correctly counted."""
        results = [
            _make_result(True, True),   # retained
            _make_result(True, True),   # retained
            _make_result(True, False),  # exited
            _make_result(False, True),  # entered
            _make_result(False, True),  # entered
            _make_result(False, False), # unchanged
        ]
        groups = {"female": results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "female", minimum_group_size=2,
        )

        gm = metrics[0]
        assert gm.retained_selection == 2
        assert gm.entered_selection == 2
        assert gm.exited_selection == 1

    def test_selection_rate_calculation(self):
        """Selection rates are correctly computed."""
        results = [
            _make_result(True, False),   # baseline yes, sim no
            _make_result(True, True),    # baseline yes, sim yes
            _make_result(False, True),   # baseline no, sim yes
            _make_result(False, False),  # baseline no, sim no
            _make_result(False, True),   # baseline no, sim yes
        ]
        groups = {"test": results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "test", minimum_group_size=2,
        )

        gm = metrics[0]
        # baseline: 2/5 = 0.4
        assert gm.baseline_selection_rate == pytest.approx(0.4, abs=0.01)
        # simulation: 3/5 = 0.6
        assert gm.simulation_selection_rate == pytest.approx(0.6, abs=0.01)
        # change: 0.2
        assert gm.selection_rate_change == pytest.approx(0.2, abs=0.01)


# ─── Cross-Group Metric Tests ────────────────────────────────────


class TestCrossGroupMetrics:
    """Test SPD and DI calculations."""

    def _make_analyzer_with_groups(
        self, groups: dict[str, list[MagicMock]], ref: str | None, min_size: int = 2,
    ):
        """Helper to compute cross-group metrics."""
        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        return FairnessImpactAnalyzer._compute_cross_group_metrics(
            analyzer, groups, ref, min_size,
        )

    def test_spd_computed_with_two_groups(self):
        """SPD and DI are computed when two groups meet minimum size."""
        male = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
        ]
        female = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
            _make_result(False, False),
        ]
        groups = {"male": male, "female": female}

        metrics = self._make_analyzer_with_groups(groups, "male", min_size=2)

        assert len(metrics) == 2
        spd = next(m for m in metrics if m.metric_name == "statistical_parity_difference")
        di = next(m for m in metrics if m.metric_name == "disparate_impact_ratio")

        assert spd.metric_status == "available"
        assert di.metric_status == "available"
        assert spd.reference_group == "male"
        assert spd.baseline_value is not None
        assert spd.simulation_value is not None

    def test_no_reference_group(self):
        """No reference group produces no_reference_group status."""
        groups = {"male": [_make_result() for _ in range(5)]}

        metrics = self._make_analyzer_with_groups(groups, None, min_size=2)

        assert len(metrics) == 2
        for m in metrics:
            assert m.metric_status == "no_reference_group"

    def test_reference_group_too_small(self):
        """Reference group below minimum size produces insufficient_data."""
        groups = {
            "male": [_make_result() for _ in range(2)],
            "female": [_make_result() for _ in range(10)],
        }

        # Reference group "female" is fine (10), but male is below threshold
        # But reference group needs to be in the known groups
        # If ref = "female" and male has 2 < min_size=5, only female qualifies
        metrics = self._make_analyzer_with_groups(groups, "male", min_size=5)

        assert len(metrics) == 2
        for m in metrics:
            assert m.metric_status == "insufficient_data"

    def test_identical_rates(self):
        """When all groups have identical selection rates, DI is identical_rates."""
        male = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
        ]
        female = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
        ]
        groups = {"male": male, "female": female}

        metrics = self._make_analyzer_with_groups(groups, "male", min_size=2)

        di = next(m for m in metrics if m.metric_name == "disparate_impact_ratio")
        assert di.metric_status == "identical_rates"

    def test_fewer_than_two_groups(self):
        """Fewer than 2 qualifying groups produces insufficient_data."""
        groups = {"male": [_make_result() for _ in range(10)]}

        metrics = self._make_analyzer_with_groups(groups, "male", min_size=2)

        assert len(metrics) == 2
        for m in metrics:
            assert m.metric_status == "insufficient_data"

    def test_spd_values_correct(self):
        """SPD absolute change is correctly computed."""
        # male: 3/5 baseline (0.6), 4/5 sim (0.8)
        male = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, True),
            _make_result(False, False),
        ]
        # female: 1/5 baseline (0.2), 1/5 sim (0.2)
        female = [
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
            _make_result(False, False),
            _make_result(False, False),
        ]
        groups = {"male": male, "female": female}

        metrics = self._make_analyzer_with_groups(groups, "male", min_size=2)
        spd = next(m for m in metrics if m.metric_name == "statistical_parity_difference")

        # Baseline: |0.2 - 0.6| = 0.4
        assert spd.baseline_value == pytest.approx(0.4, abs=0.01)
        # Simulation: |0.2 - 0.8| = 0.6
        assert spd.simulation_value == pytest.approx(0.6, abs=0.01)
        # Change: 0.2
        assert spd.absolute_change == pytest.approx(0.2, abs=0.01)


# ─── Reference Group Tests ───────────────────────────────────────


class TestReferenceGroup:
    def test_largest_group_is_reference(self):
        """The largest known-gender group is selected as reference."""
        from app.services.simulation.fairness_impact_analyzer import FairnessImpactAnalyzer

        groups = {
            "male": [_make_result() for _ in range(10)],
            "female": [_make_result() for _ in range(5)],
            "other": [_make_result() for _ in range(3)],
        }

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        ref = FairnessImpactAnalyzer._determine_reference_group(analyzer, groups)
        assert ref == "male"

    def test_no_known_groups(self):
        """No known groups returns None."""
        from app.services.simulation.fairness_impact_analyzer import FairnessImpactAnalyzer

        groups = {"unknown": [_make_result() for _ in range(5)]}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        ref = FairnessImpactAnalyzer._determine_reference_group(analyzer, groups)
        assert ref is None

    def test_unknown_excluded_from_reference(self):
        """Unknown group is excluded from reference selection."""
        from app.services.simulation.fairness_impact_analyzer import FairnessImpactAnalyzer

        groups = {
            "unknown": [_make_result() for _ in range(100)],
            "female": [_make_result() for _ in range(5)],
        }

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        ref = FairnessImpactAnalyzer._determine_reference_group(analyzer, groups)
        assert ref == "female"


# ─── Missing Data Tests ─────────────────────────────────────────


class TestMissingData:
    def test_all_unknown_demographics(self):
        """All candidates with unknown demographics produce only no_demographic_data."""
        results = [_make_result(True, True) for _ in range(10)]
        demographics = {}  # No demographics loaded

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        groups = FairnessImpactAnalyzer._group_by_gender(analyzer, results, demographics)

        assert "unknown" in groups
        assert len(groups) == 1

    def test_partial_demographics(self):
        """Mix of known and unknown demographics."""
        ids = [uuid.uuid4() for _ in range(6)]
        results = [_make_result(True, True, candidate_id=cid) for cid in ids]
        demographics = {
            ids[0]: "male",
            ids[1]: "male",
            ids[2]: "female",
            ids[3]: None,
        }

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        groups = FairnessImpactAnalyzer._group_by_gender(analyzer, results, demographics)

        assert "male" in groups
        assert "female" in groups
        assert "unknown" in groups
        assert len(groups["male"]) == 2
        assert len(groups["female"]) == 1
        assert len(groups["unknown"]) == 3


# ─── Insights Tests ──────────────────────────────────────────────


class TestInsights:
    def test_insights_generated_for_rate_changes(self):
        """Insights are generated when selection rates change."""
        from app.domain.fairness_impact_schemas import (
            FairnessGroupMetric,
            FairnessCrossGroupMetric,
        )

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)

        group_metrics = [
            FairnessGroupMetric(
                group_dimension="gender",
                group_value="male",
                sample_size=10,
                eligible_count=10,
                baseline_selected_count=3,
                simulation_selected_count=6,
                baseline_selection_rate=0.3,
                simulation_selection_rate=0.6,
                selection_rate_change=0.3,
                entered_selection=3,
                exited_selection=0,
                retained_selection=3,
                metric_status="available",
            ),
            FairnessGroupMetric(
                group_dimension="gender",
                group_value="female",
                sample_size=10,
                eligible_count=10,
                baseline_selected_count=4,
                simulation_selected_count=5,
                baseline_selection_rate=0.4,
                simulation_selection_rate=0.5,
                selection_rate_change=0.1,
                entered_selection=1,
                exited_selection=0,
                retained_selection=4,
                metric_status="available",
            ),
        ]

        cross_metrics = [
            FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=0.1,
                simulation_value=0.2,
                absolute_change=0.1,
                reference_group="male",
                metric_status="available",
            ),
        ]

        insights = FairnessImpactAnalyzer._generate_insights(
            analyzer,
            group_metrics,
            cross_metrics,
            "male",
            total_candidates=20,
            candidates_with_demo=20,
            candidates_missing_demo=0,
        )

        # Should have insights for rate changes, transitions, and cross-group
        assert len(insights) > 0
        rate_insights = [i for i in insights if i.type == "selection_rate_change"]
        assert len(rate_insights) == 2

    def test_insight_for_missing_demographics(self):
        """Insight generated when candidates have missing demographics."""
        from app.domain.fairness_impact_schemas import FairnessGroupMetric

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)

        insights = FairnessImpactAnalyzer._generate_insights(
            analyzer,
            group_metrics=[],
            cross_group_metrics=[],
            reference_group=None,
            total_candidates=10,
            candidates_with_demo=7,
            candidates_missing_demo=3,
        )

        demo_insights = [i for i in insights if i.type == "demographic_coverage"]
        assert len(demo_insights) == 1
        assert "3" in demo_insights[0].message

    def test_insight_for_insufficient_sample_groups(self):
        """Insight generated for groups below minimum size."""
        from app.domain.fairness_impact_schemas import FairnessGroupMetric

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)

        group_metrics = [
            FairnessGroupMetric(
                group_dimension="gender",
                group_value="other",
                sample_size=2,
                eligible_count=2,
                baseline_selected_count=0,
                simulation_selected_count=0,
                metric_status="insufficient_sample",
                status_reason="Group has 2 candidate(s).",
            ),
        ]

        insights = FairnessImpactAnalyzer._generate_insights(
            analyzer,
            group_metrics=group_metrics,
            cross_group_metrics=[],
            reference_group="male",
            total_candidates=20,
            candidates_with_demo=18,
            candidates_missing_demo=2,
        )

        sample_insights = [i for i in insights if i.type == "insufficient_sample"]
        assert len(sample_insights) == 1

    def test_cross_group_metric_unchanged(self):
        """Cross-group metric with zero change generates unchanged insight."""
        from app.domain.fairness_impact_schemas import FairnessCrossGroupMetric

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)

        cross_metrics = [
            FairnessCrossGroupMetric(
                metric_name="statistical_parity_difference",
                metric_label="Statistical Parity Difference",
                baseline_value=0.0,
                simulation_value=0.0,
                absolute_change=0.0,
                reference_group="male",
                metric_status="available",
            ),
        ]

        insights = FairnessImpactAnalyzer._generate_insights(
            analyzer,
            group_metrics=[],
            cross_group_metrics=cross_metrics,
            reference_group="male",
            total_candidates=10,
            candidates_with_demo=10,
            candidates_missing_demo=0,
        )

        unchanged = [i for i in insights if "remained unchanged" in i.message]
        assert len(unchanged) == 1


# ─── Edge Case Tests ─────────────────────────────────────────────


class TestEdgeCases:
    def test_zero_candidates(self):
        """Empty results produce empty group metrics."""
        groups: dict[str, list] = {}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, None, minimum_group_size=5,
        )
        assert len(metrics) == 0

    def test_single_candidate(self):
        """Single candidate group is below typical minimum."""
        groups = {"male": [_make_result(True, True)]}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=5,
        )
        assert len(metrics) == 1
        assert metrics[0].metric_status == "insufficient_sample"

    def test_all_shortlisted(self):
        """All candidates shortlisted in both baseline and simulation."""
        results = [_make_result(True, True) for _ in range(5)]
        groups = {"female": results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "female", minimum_group_size=2,
        )

        gm = metrics[0]
        assert gm.baseline_selection_rate == pytest.approx(1.0)
        assert gm.simulation_selection_rate == pytest.approx(1.0)
        assert gm.selection_rate_change == pytest.approx(0.0)
        assert gm.retained_selection == 5
        assert gm.entered_selection == 0
        assert gm.exited_selection == 0

    def test_none_shortlisted(self):
        """No candidates shortlisted."""
        results = [_make_result(False, False) for _ in range(5)]
        groups = {"male": results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )

        gm = metrics[0]
        assert gm.baseline_selection_rate == pytest.approx(0.0)
        assert gm.simulation_selection_rate == pytest.approx(0.0)

    def test_multiple_groups_mixed_sizes(self):
        """Multiple groups with different sizes."""
        groups = {
            "male": [_make_result(True, False) for _ in range(10)],
            "female": [_make_result(False, True) for _ in range(8)],
            "other": [_make_result(True, True) for _ in range(3)],
        }

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=5,
        )

        statuses = {m.group_value: m.metric_status for m in metrics}
        assert statuses["male"] == "available"
        assert statuses["female"] == "available"
        assert statuses["other"] == "insufficient_sample"

    def test_identical_baseline_simulation(self):
        """Identical baseline and simulation produces zero changes."""
        results = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
            _make_result(False, False),
        ]
        groups = {"male": results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)
        metrics = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )

        gm = metrics[0]
        assert gm.selection_rate_change == pytest.approx(0.0)
        assert gm.entered_selection == 0
        assert gm.exited_selection == 0
        assert gm.retained_selection == 2


# ─── Schema Tests ────────────────────────────────────────────────


class TestSchemas:
    def test_fairness_group_metric_schema(self):
        """FairnessGroupMetric schema validates correctly."""
        from app.domain.fairness_impact_schemas import FairnessGroupMetric

        m = FairnessGroupMetric(
            group_dimension="gender",
            group_value="male",
            sample_size=10,
            eligible_count=10,
            baseline_selected_count=3,
            simulation_selected_count=5,
            baseline_selection_rate=0.3,
            simulation_selection_rate=0.5,
            selection_rate_change=0.2,
            entered_selection=2,
            exited_selection=0,
            retained_selection=3,
            metric_status="available",
        )
        d = m.model_dump()
        assert d["group_dimension"] == "gender"
        assert d["baseline_selection_rate"] == 0.3

    def test_fairness_cross_group_metric_schema(self):
        """FairnessCrossGroupMetric schema validates correctly."""
        from app.domain.fairness_impact_schemas import FairnessCrossGroupMetric

        m = FairnessCrossGroupMetric(
            metric_name="statistical_parity_difference",
            metric_label="Statistical Parity Difference",
            baseline_value=0.1,
            simulation_value=0.2,
            absolute_change=0.1,
            reference_group="male",
            metric_status="available",
        )
        d = m.model_dump()
        assert d["metric_name"] == "statistical_parity_difference"

    def test_fairness_insight_schema(self):
        """FairnessInsight schema validates correctly."""
        from app.domain.fairness_impact_schemas import FairnessInsight

        i = FairnessInsight(
            type="selection_rate_change",
            message="Test message",
            metric_value=0.15,
            metric_unit="rate",
        )
        d = i.model_dump()
        assert d["type"] == "selection_rate_change"

    def test_fairness_impact_response_schema(self):
        """FairnessImpactResponse schema validates correctly."""
        from app.domain.fairness_impact_schemas import FairnessImpactResponse

        r = FairnessImpactResponse(
            simulation_id=uuid.uuid4(),
            execution_id=uuid.uuid4(),
            execution_status="completed",
            scenario_name="Test",
            job_title="Engineer",
            company="Corp",
            engine_version="v1",
            completed_at=None,
            group_dimension="gender",
            reference_group="male",
            total_candidates=10,
            candidates_with_demographic=8,
            candidates_missing_demographic=2,
            minimum_group_size=5,
            group_metrics=[],
            cross_group_metrics=[],
        )
        d = r.model_dump()
        assert d["total_candidates"] == 10

    def test_unavailable_metric_with_status_reason(self):
        """Metrics with unavailable status include reason."""
        from app.domain.fairness_impact_schemas import FairnessGroupMetric

        m = FairnessGroupMetric(
            group_dimension="gender",
            group_value="other",
            sample_size=2,
            eligible_count=2,
            baseline_selected_count=0,
            simulation_selected_count=0,
            metric_status="insufficient_sample",
            status_reason="Group has 2 candidate(s).",
        )
        assert m.status_reason is not None
        assert "2 candidate(s)" in m.status_reason


# ─── Deterministic Output Tests ──────────────────────────────────


class TestDeterministicOutput:
    def test_same_inputs_same_outputs(self):
        """Same inputs always produce same outputs."""
        results = [
            _make_result(True, True),
            _make_result(True, False),
            _make_result(False, True),
            _make_result(False, False),
            _make_result(True, True),
        ]
        groups = {"male": results}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)

        metrics1 = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )
        metrics2 = FairnessImpactAnalyzer._compute_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )

        assert metrics1[0].baseline_selection_rate == metrics2[0].baseline_selection_rate
        assert metrics1[0].simulation_selection_rate == metrics2[0].simulation_selection_rate
        assert metrics1[0].selection_rate_change == metrics2[0].selection_rate_change

    def test_cross_group_deterministic(self):
        """Cross-group metrics are deterministic."""
        male = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
        ]
        female = [
            _make_result(True, True),
            _make_result(True, True),
            _make_result(False, False),
            _make_result(False, False),
            _make_result(False, False),
        ]
        groups = {"male": male, "female": female}

        analyzer = MagicMock(spec=FairnessImpactAnalyzer)

        metrics1 = FairnessImpactAnalyzer._compute_cross_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )
        metrics2 = FairnessImpactAnalyzer._compute_cross_group_metrics(
            analyzer, groups, "male", minimum_group_size=2,
        )

        for m1, m2 in zip(metrics1, metrics2):
            assert m1.baseline_value == m2.baseline_value
            assert m1.simulation_value == m2.simulation_value
            assert m1.absolute_change == m2.absolute_change
