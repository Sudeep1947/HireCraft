"""Tests for Phase 14 — Advanced Simulation & Research Intelligence.

Covers perturbation engine, configuration generation, sensitivity analysis,
robustness analysis, stability analysis, experiment CRUD, and immutability.
"""

import uuid

import pytest

from app.domain.enums import (
    ExperimentType,
    PerturbationType,
    SensitivityDimension,
)
from app.domain.simulation_experiment_schemas import (
    ExperimentCreate,
    MAX_CONFIGURATIONS_PER_EXPERIMENT,
    ParameterRange,
    PerturbationSpec,
)
from app.services.simulation.perturbation_engine import PerturbationEngine
from app.services.simulation.configuration_generator import ConfigurationGenerator
from app.services.simulation.sensitivity_analyzer import SensitivityAnalyzer
from app.services.simulation.robustness_analyzer import RobustnessAnalyzer
from app.services.simulation.stability_analyzer import StabilityAnalyzer


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    return PerturbationEngine()


@pytest.fixture
def generator():
    return ConfigurationGenerator()


@pytest.fixture
def base_config():
    return {
        "simulation": {
            "scoring_weights": {
                "skills": 0.35,
                "experience": 0.25,
                "education": 0.15,
                "projects": 0.15,
                "certifications": 0.05,
                "location": 0.0,
                "employment_type": 0.0,
                "semantic": 0.05,
            },
            "threshold": 70,
            "shortlist_size": 10,
            "requirements": {
                "mandatory_skills": ["python", "sql"],
                "preferred_skills": ["docker"],
                "experience": {"minimum_years": 2},
                "education": {"level": "bachelor", "requirement": "preferred"},
            },
        }
    }


# ── PerturbationEngine Tests ────────────────────────────────────────


class TestPerturbationEngine:
    def test_sweep_values_explicit(self, engine):
        prange = ParameterRange(
            dimension=SensitivityDimension.THRESHOLD,
            values=[65, 70, 75, 80],
        )
        values = engine.generate_sweep_values(prange)
        assert values == [65, 70, 75, 80]

    def test_sweep_values_numeric_range(self, engine):
        prange = ParameterRange(
            dimension=SensitivityDimension.THRESHOLD,
            start=65,
            end=75,
            step=5,
        )
        values = engine.generate_sweep_values(prange)
        assert values == [65, 70, 75]

    def test_sweep_values_invalid_step(self, engine):
        prange = ParameterRange(
            dimension=SensitivityDimension.THRESHOLD,
            start=65,
            end=75,
            step=-1,
        )
        with pytest.raises(ValueError, match="Step must be positive"):
            engine.generate_sweep_values(prange)

    def test_apply_threshold(self, engine, base_config):
        result = engine.apply_perturbation(
            base_config, SensitivityDimension.THRESHOLD, 80,
        )
        assert result["simulation"]["threshold"] == 80

    def test_apply_shortlist(self, engine, base_config):
        result = engine.apply_perturbation(
            base_config, SensitivityDimension.SHORTLIST_SIZE, 20,
        )
        assert result["simulation"]["shortlist_size"] == 20

    def test_apply_weight(self, engine, base_config):
        result = engine.apply_perturbation(
            base_config, SensitivityDimension.EXPERIENCE_WEIGHT, 0.40,
        )
        assert result["simulation"]["scoring_weights"]["experience"] == 0.40

    def test_normalize_weights(self, engine, base_config):
        result = engine.normalize_weights(base_config)
        weights = result["simulation"]["scoring_weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-3

    def test_configuration_hash_deterministic(self, engine, base_config):
        h1 = engine.configuration_hash(base_config)
        h2 = engine.configuration_hash(base_config)
        assert h1 == h2

    def test_configuration_hash_different(self, engine, base_config):
        h1 = engine.configuration_hash(base_config)
        modified = {**base_config, "extra": True}
        h2 = engine.configuration_hash(modified)
        assert h1 != h2

    def test_validate_configuration_valid(self, engine, base_config):
        is_valid, issues = engine.validate_configuration(base_config)
        assert is_valid is True
        assert len(issues) == 0

    def test_neighborhood_generation(self, engine, base_config):
        perturbations = [
            PerturbationSpec(
                dimension=SensitivityDimension.THRESHOLD,
                perturbation_type=PerturbationType.NUMERIC_DELTA,
                delta=5,
            ),
        ]
        configs = engine.generate_neighborhood(base_config, perturbations)
        assert len(configs) == 2  # +5 and -5
        thresholds = [c["simulation"]["threshold"] for c in configs]
        assert 75 in thresholds
        assert 65 in thresholds


# ── ConfigurationGenerator Tests ─────────────────────────────────────


class TestConfigurationGenerator:
    def test_threshold_sweep(self, generator, base_config):
        ranges = [
            ParameterRange(
                dimension=SensitivityDimension.THRESHOLD,
                start=65,
                end=80,
                step=5,
            ),
        ]
        configs = generator.generate_configurations(
            base_config, ranges, ExperimentType.THRESHOLD_SWEEP, max_configurations=20,
        )
        assert len(configs) == 4  # 65, 70, 75, 80
        thresholds = [c["simulation"]["threshold"] for c in configs]
        assert sorted(thresholds) == [65, 70, 75, 80]

    def test_multi_dimension(self, generator, base_config):
        ranges = [
            ParameterRange(
                dimension=SensitivityDimension.THRESHOLD,
                start=65,
                end=75,
                step=5,
            ),
            ParameterRange(
                dimension=SensitivityDimension.EXPERIENCE_WEIGHT,
                start=0.20,
                end=0.30,
                step=0.05,
            ),
        ]
        configs = generator.generate_configurations(
            base_config, ranges, ExperimentType.MULTI_PARAMETER_SENSITIVITY,
            max_configurations=20,
        )
        # 3 thresholds × 3 weight values = 9 total
        assert len(configs) == 9

    def test_max_configurations_limit(self, generator, base_config):
        ranges = [
            ParameterRange(
                dimension=SensitivityDimension.THRESHOLD,
                start=60,
                end=90,
                step=1,
            ),
        ]
        with pytest.raises(ValueError, match="exceeding the limit"):
            generator.generate_configurations(
                base_config, ranges, ExperimentType.THRESHOLD_SWEEP,
                max_configurations=10,
            )

    def test_too_many_dimensions(self, generator, base_config):
        ranges = [
            ParameterRange(dimension=SensitivityDimension.THRESHOLD, values=[70]),
            ParameterRange(dimension=SensitivityDimension.SHORTLIST_SIZE, values=[10]),
            ParameterRange(dimension=SensitivityDimension.SKILLS_WEIGHT, values=[0.35]),
            ParameterRange(dimension=SensitivityDimension.EXPERIENCE_WEIGHT, values=[0.25]),
            ParameterRange(dimension=SensitivityDimension.EDUCATION_WEIGHT, values=[0.15]),
            ParameterRange(dimension=SensitivityDimension.PROJECTS_WEIGHT, values=[0.15]),
        ]
        with pytest.raises(ValueError, match="maximum parameter dimensions"):
            generator.generate_configurations(
                base_config, ranges, ExperimentType.MULTI_PARAMETER_SENSITIVITY,
            )

    def test_deduplication(self, generator, base_config):
        ranges = [
            ParameterRange(
                dimension=SensitivityDimension.THRESHOLD,
                values=[70, 70, 70],
            ),
        ]
        configs = generator.generate_configurations(
            base_config, ranges, ExperimentType.THRESHOLD_SWEEP,
        )
        assert len(configs) == 1

    def test_robustness_configs(self, generator, base_config):
        configs = generator.generate_robustness_configs(base_config)
        assert len(configs) > 0
        # All should be different from base
        base_hash = PerturbationEngine().configuration_hash(base_config)
        for c in configs:
            h = PerturbationEngine().configuration_hash(c)
            assert h != base_hash

    def test_parameter_count(self, generator):
        ranges = [
            ParameterRange(dimension=SensitivityDimension.THRESHOLD, start=65, end=80, step=5),
            ParameterRange(dimension=SensitivityDimension.SHORTLIST_SIZE, start=5, end=15, step=5),
        ]
        count = generator.parameter_count(ranges)
        assert count == 12  # 4 thresholds × 3 shortlists


# ── SensitivityAnalyzer Tests ────────────────────────────────────────


class TestSensitivityAnalyzer:
    def test_analyze_basic(self):
        analyzer = SensitivityAnalyzer()
        results = [
            {"parameter_values": {"threshold": 65}, "metrics": {"qualified_count": 35}, "execution_status": "completed", "configuration_hash": "a"},
            {"parameter_values": {"threshold": 70}, "metrics": {"qualified_count": 30}, "execution_status": "completed", "configuration_hash": "b"},
            {"parameter_values": {"threshold": 75}, "metrics": {"qualified_count": 22}, "execution_status": "completed", "configuration_hash": "c"},
            {"parameter_values": {"threshold": 80}, "metrics": {"qualified_count": 15}, "execution_status": "completed", "configuration_hash": "d"},
        ]
        response = analyzer.analyze("test-id", results, {"threshold": {"values": [65, 70, 75, 80]}})
        assert len(response.curves) == 1
        assert response.curves[0].direction == "decreasing"
        assert response.curves[0].range_spread == 20.0

    def test_empty_results(self):
        analyzer = SensitivityAnalyzer()
        response = analyzer.analyze("test-id", [], {})
        assert len(response.curves) == 0

    def test_candidate_sensitivity(self):
        analyzer = SensitivityAnalyzer()
        results = [
            {"parameter_values": {}, "metrics": {}, "candidate_metrics": {"c1": {"score": 85, "rank": 1, "qualified": True, "shortlisted": True}}},
            {"parameter_values": {}, "metrics": {}, "candidate_metrics": {"c1": {"score": 80, "rank": 3, "qualified": True, "shortlisted": True}}},
            {"parameter_values": {}, "metrics": {}, "candidate_metrics": {"c1": {"score": 75, "rank": 5, "qualified": True, "shortlisted": False}}},
        ]
        stability = analyzer.analyze_candidate_sensitivity(results)
        assert "c1" in stability
        assert stability["c1"]["score_range"] == 10.0
        assert stability["c1"]["rank_range"] == 4.0


# ── RobustnessAnalyzer Tests ─────────────────────────────────────────


class TestRobustnessAnalyzer:
    def test_analyze_basic(self):
        analyzer = RobustnessAnalyzer()
        base = {"parameter_values": {"threshold": 70}, "metrics": {"qualified_count": 30, "shortlisted_count": 10, "avg_rank": 5.0}}
        perturbed = [
            {"parameter_values": {"threshold": 75}, "metrics": {"qualified_count": 25, "shortlisted_count": 8, "avg_rank": 5.5}},
            {"parameter_values": {"threshold": 65}, "metrics": {"qualified_count": 35, "shortlisted_count": 12, "avg_rank": 4.5}},
        ]
        response = analyzer.analyze("test-id", base, perturbed)
        assert len(response.perturbation_results) == 2
        assert len(response.profiles) == 1

    def test_empty_results(self):
        analyzer = RobustnessAnalyzer()
        response = analyzer.analyze("test-id", None, [])
        assert len(response.perturbation_results) == 0


# ── StabilityAnalyzer Tests ──────────────────────────────────────────


class TestStabilityAnalyzer:
    def test_analyze_basic(self):
        analyzer = StabilityAnalyzer()
        results = [
            {"parameter_values": {}, "metrics": {"candidate_ranks": [1, 2, 3, 4, 5]}, "candidate_metrics": {}},
            {"parameter_values": {}, "metrics": {"candidate_ranks": [1, 2, 3, 4, 6]}, "candidate_metrics": {}},
            {"parameter_values": {}, "metrics": {"candidate_ranks": [1, 2, 4, 5, 6]}, "candidate_metrics": {}},
        ]
        response = analyzer.analyze("test-id", results)
        assert response.ranking_stability["available"] is True
        assert response.ranking_stability["configurations_analyzed"] == 3

    def test_candidate_stability(self):
        analyzer = StabilityAnalyzer()
        results = [
            {"parameter_values": {}, "metrics": {}, "candidate_metrics": {
                "c1": {"name": "Alice", "score": 85, "rank": 1, "qualified": True, "shortlisted": True},
            }},
            {"parameter_values": {}, "metrics": {}, "candidate_metrics": {
                "c1": {"name": "Alice", "score": 83, "rank": 2, "qualified": True, "shortlisted": True},
            }},
        ]
        response = analyzer.analyze("test-id", results)
        assert len(response.candidate_stability) == 1
        c = response.candidate_stability[0]
        assert c.candidate_name == "Alice"
        assert c.appearance_frequency == 1.0
        assert c.shortlist_frequency == 1.0

    def test_empty_results(self):
        analyzer = StabilityAnalyzer()
        response = analyzer.analyze("test-id", [])
        assert response.ranking_stability["available"] is False


# ── Schema Validation Tests ─────────────────────────────────────────


class TestExperimentSchemas:
    def test_create_valid(self):
        e = ExperimentCreate(
            base_scenario_id=uuid.uuid4(),
            experiment_type=ExperimentType.THRESHOLD_SWEEP,
            parameter_ranges=[ParameterRange(
                dimension=SensitivityDimension.THRESHOLD,
                values=[70],
            )],
            name="Test Experiment",
        )
        assert e.name == "Test Experiment"
        assert e.experiment_type == ExperimentType.THRESHOLD_SWEEP
        assert len(e.parameter_ranges) == 1

    def test_parameter_range_values(self):
        pr = ParameterRange(
            dimension=SensitivityDimension.THRESHOLD,
            values=[65, 70, 75],
        )
        assert len(pr.values) == 3
        assert pr.dimension == SensitivityDimension.THRESHOLD

    def test_perturbation_spec(self):
        ps = PerturbationSpec(
            dimension=SensitivityDimension.THRESHOLD,
            perturbation_type=PerturbationType.NUMERIC_DELTA,
            delta=5,
        )
        assert ps.delta == 5


# ── Enum Tests ──────────────────────────────────────────────────────


class TestExperimentEnums:
    def test_experiment_type_values(self):
        types = [t.value for t in ExperimentType]
        assert "threshold_sweep" in types
        assert "weight_sweep" in types
        assert "robustness_test" in types
        assert "fairness_sensitivity" in types

    def test_sensitivity_dimension_values(self):
        dims = [d.value for d in SensitivityDimension]
        assert "threshold" in dims
        assert "skills_weight" in dims
        assert "experience_weight" in dims

    def test_perturbation_type_values(self):
        pts = [p.value for p in PerturbationType]
        assert "numeric_delta" in pts
        assert "numeric_percentage" in pts
        assert "requirement_add" in pts
