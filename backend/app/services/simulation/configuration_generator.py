"""ConfigurationGenerator — builds validated experiment configurations.

READ-ONLY: produces hypothetical configurations. Never modifies live data.
"""

from __future__ import annotations

import copy
import itertools
from typing import Any

from app.domain.enums import ExperimentType, SensitivityDimension
from app.domain.simulation_experiment_schemas import (
    MAX_CONFIGURATIONS_PER_EXPERIMENT,
    ParameterRange,
)
from app.domain.simulation_schemas import SimulationConfiguration
from app.services.simulation.perturbation_engine import PerturbationEngine


class ConfigurationGenerator:
    """Generates a set of validated simulation configurations for an experiment."""

    def __init__(self) -> None:
        self._engine = PerturbationEngine()

    def generate_configurations(
        self,
        base_config: dict[str, Any],
        parameter_ranges: list[ParameterRange],
        experiment_type: ExperimentType,
        max_configurations: int = 20,
    ) -> list[dict[str, Any]]:
        """Generate experiment configurations from base config and parameter ranges."""
        if len(parameter_ranges) > 5:
            raise ValueError(
                "The requested experiment exceeds the maximum parameter dimensions (5). "
                "Reduce the number of parameters."
            )

        sweep_values: list[list[Any]] = []
        dimensions: list[SensitivityDimension] = []
        for prange in parameter_ranges:
            values = self._engine.generate_sweep_values(prange)
            if not values:
                raise ValueError(
                    f"No values generated for dimension {prange.dimension.value}. "
                    "Check the range definition."
                )
            sweep_values.append(values)
            dimensions.append(prange.dimension)

        total = 1
        for vals in sweep_values:
            total *= len(vals)

        if total > max_configurations:
            raise ValueError(
                f"The requested parameter space would generate {total} configurations, "
                f"exceeding the limit of {max_configurations}. "
                "Reduce the range or number of dimensions."
            )

        configs: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()

        for combo in itertools.product(*sweep_values):
            config = copy.deepcopy(base_config)
            for dim, val in zip(dimensions, combo):
                config = self._engine.apply_perturbation(config, dim, val)

            config = self._engine.normalize_weights(config)
            is_valid, _issues = self._engine.validate_configuration(config)
            if not is_valid:
                continue

            config_hash = self._engine.configuration_hash(config)
            if config_hash not in seen_hashes:
                seen_hashes.add(config_hash)
                configs.append(config)

        return configs[:max_configurations]

    def generate_robustness_configs(
        self,
        base_config: dict[str, Any],
        perturbation_percentages: list[float] | None = None,
        threshold_deltas: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate configs around the base for robustness testing."""
        if perturbation_percentages is None:
            perturbation_percentages = [5.0, -5.0, 10.0, -10.0]
        if threshold_deltas is None:
            threshold_deltas = [2, -2, 5, -5]

        configs: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Weight perturbations
        sim_config = base_config.get("simulation") or base_config
        weights = sim_config.get("scoring_weights") or {}
        for pct in perturbation_percentages:
            for key in ["skills", "experience"]:
                if key in weights:
                    new_val = weights[key] * (1 + pct / 100)
                    new_val = max(0.0, min(1.0, round(new_val, 4)))
                    c = self._engine.apply_perturbation(
                        base_config,
                        SensitivityDimension.SKILLS_WEIGHT if key == "skills"
                        else SensitivityDimension.EXPERIENCE_WEIGHT,
                        new_val,
                    )
                    c = self._engine.normalize_weights(c)
                    h = self._engine.configuration_hash(c)
                    if h not in seen:
                        seen.add(h)
                        configs.append(c)

        # Threshold perturbations
        base_threshold = sim_config.get("threshold", 70)
        for delta in threshold_deltas:
            new_val = base_threshold + delta
            if 0 <= new_val <= 100:
                c = self._engine.apply_perturbation(
                    base_config, SensitivityDimension.THRESHOLD, new_val,
                )
                h = self._engine.configuration_hash(c)
                if h not in seen:
                    seen.add(h)
                    configs.append(c)

        return configs

    def parameter_count(
        self, parameter_ranges: list[ParameterRange],
    ) -> int:
        """Estimate the number of configurations from parameter ranges."""
        total = 1
        for prange in parameter_ranges:
            values = self._engine.generate_sweep_values(prange)
            total *= max(len(values), 1)
        return total
