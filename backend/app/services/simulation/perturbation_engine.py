"""PerturbationEngine — generates controlled configuration variants.

READ-ONLY: produces hypothetical configurations that pass the existing
SimulationConfigurationValidator. Never modifies live data.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from app.domain.enums import PerturbationType, SensitivityDimension
from app.domain.simulation_experiment_schemas import PerturbationSpec, ParameterRange
from app.services.simulation.configuration_validator import (
    SimulationConfigurationValidator,
    WEIGHT_DIMENSIONS,
)
from app.domain.simulation_schemas import SimulationConfiguration


class PerturbationEngine:
    """Generates perturbed configurations around a base simulation config."""

    MAX_WEIGHT_TOTAL = 1.0
    WEIGHT_TOLERANCE = 1e-3

    def generate_sweep_values(
        self,
        prange: ParameterRange,
    ) -> list[Any]:
        """Convert a ParameterRange into an explicit list of values."""
        if prange.values is not None:
            return list(prange.values)

        if prange.start is not None and prange.end is not None and prange.step is not None:
            if prange.step <= 0:
                raise ValueError("Step must be positive.")
            values: list[Any] = []
            current = prange.start
            while current <= prange.end + 1e-9:
                values.append(round(current, 6))
                current += prange.step
            return values

        raise ValueError(
            f"Parameter range for {prange.dimension.value} must specify "
            "either 'values' or 'start', 'end', and 'step'."
        )

    def apply_perturbation(
        self,
        base_config: dict[str, Any],
        dimension: SensitivityDimension,
        value: Any,
    ) -> dict[str, Any]:
        """Apply a single parameter value to a base configuration."""
        config = copy.deepcopy(base_config)
        sim_config = config.get("simulation") or config
        reqs = sim_config.get("requirements") or {}

        if dimension == SensitivityDimension.THRESHOLD:
            sim_config["threshold"] = int(value)
        elif dimension == SensitivityDimension.SHORTLIST_SIZE:
            sim_config["shortlist_size"] = int(value)
        elif dimension in self._weight_dimension_map():
            key = self._weight_dimension_map()[dimension]
            weights = sim_config.get("scoring_weights") or {}
            weights[key] = float(value)
            sim_config["scoring_weights"] = weights
        elif dimension == SensitivityDimension.MANDATORY_SKILLS:
            if isinstance(value, list):
                reqs["mandatory_skills"] = value
            else:
                current = reqs.get("mandatory_skills") or []
                if value not in current:
                    current.append(str(value))
                reqs["mandatory_skills"] = current
        elif dimension == SensitivityDimension.PREFERRED_SKILLS:
            if isinstance(value, list):
                reqs["preferred_skills"] = value
            else:
                current = reqs.get("preferred_skills") or []
                if value not in current:
                    current.append(str(value))
                reqs["preferred_skills"] = current
        elif dimension == SensitivityDimension.EXPERIENCE_MIN:
            exp = reqs.get("experience") or {}
            exp["min"] = int(value)
            reqs["experience"] = exp
        elif dimension == SensitivityDimension.EDUCATION_LEVEL:
            edu = reqs.get("education") or {}
            edu["level"] = str(value)
            reqs["education"] = edu

        sim_config["requirements"] = reqs
        config["simulation"] = sim_config
        return config

    def generate_neighborhood(
        self,
        base_config: dict[str, Any],
        perturbations: list[PerturbationSpec],
    ) -> list[dict[str, Any]]:
        """Generate a scenario neighborhood from perturbation specs."""
        configs: list[dict[str, Any]] = []
        for spec in perturbations:
            if spec.perturbation_type == PerturbationType.NUMERIC_DELTA:
                if spec.delta is None:
                    continue
                base_val = self._get_param_value(base_config, spec.dimension)
                if base_val is None:
                    continue
                for d in [spec.delta, -spec.delta]:
                    new_val = base_val + d
                    if self._validate_param_range(spec.dimension, new_val):
                        configs.append(
                            self.apply_perturbation(base_config, spec.dimension, new_val)
                        )
            elif spec.perturbation_type == PerturbationType.NUMERIC_PERCENTAGE:
                if spec.percentage is None:
                    continue
                base_val = self._get_param_value(base_config, spec.dimension)
                if base_val is None:
                    continue
                for pct in [spec.percentage, -spec.percentage]:
                    new_val = base_val * (1 + pct / 100)
                    if self._validate_param_range(spec.dimension, new_val):
                        configs.append(
                            self.apply_perturbation(base_config, spec.dimension, round(new_val, 4))
                        )
            elif spec.perturbation_type == PerturbationType.NUMERIC_EXPLICIT:
                if spec.values:
                    for v in spec.values:
                        configs.append(
                            self.apply_perturbation(base_config, spec.dimension, v)
                        )

        return configs

    def normalize_weights(self, config: dict[str, Any]) -> dict[str, Any]:
        """Normalize scoring weights to sum to 1.0."""
        c = copy.deepcopy(config)
        sim = c.get("simulation") or c
        weights = sim.get("scoring_weights") or {}
        total = sum(weights.get(k, 0.0) for k in WEIGHT_DIMENSIONS)
        if total > 0:
            for k in WEIGHT_DIMENSIONS:
                if k in weights:
                    weights[k] = round(weights[k] / total, 4)
            sim["scoring_weights"] = weights
        c["simulation"] = sim
        return c

    def configuration_hash(self, config: dict[str, Any]) -> str:
        """Deterministic fingerprint for deduplication."""
        serialized = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def validate_configuration(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate using the existing SimulationConfigurationValidator."""
        flat = config.get("simulation") or config
        is_valid, issues = SimulationConfigurationValidator.validate(flat)
        return is_valid, [i.message for i in issues]

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _weight_dimension_map() -> dict[SensitivityDimension, str]:
        return {
            SensitivityDimension.SKILLS_WEIGHT: "skills",
            SensitivityDimension.EXPERIENCE_WEIGHT: "experience",
            SensitivityDimension.EDUCATION_WEIGHT: "education",
            SensitivityDimension.PROJECTS_WEIGHT: "projects",
            SensitivityDimension.CERTIFICATIONS_WEIGHT: "certifications",
            SensitivityDimension.LOCATION_WEIGHT: "location",
            SensitivityDimension.EMPLOYMENT_TYPE_WEIGHT: "employment_type",
            SensitivityDimension.SEMANTIC_WEIGHT: "semantic",
        }

    def _get_param_value(
        self, config: dict[str, Any], dimension: SensitivityDimension,
    ) -> float | None:
        sim = config.get("simulation") or config
        if dimension == SensitivityDimension.THRESHOLD:
            return float(sim.get("threshold", 70))
        if dimension == SensitivityDimension.SHORTLIST_SIZE:
            return float(sim.get("shortlist_size", 10))
        wmap = self._weight_dimension_map()
        if dimension in wmap:
            weights = sim.get("scoring_weights") or {}
            return float(weights.get(wmap[dimension], 0.0))
        return None

    def _validate_param_range(self, dimension: SensitivityDimension, value: float) -> bool:
        if dimension == SensitivityDimension.THRESHOLD:
            return 0 <= value <= 100
        if dimension == SensitivityDimension.SHORTLIST_SIZE:
            return 1 <= value <= 500
        wmap = self._weight_dimension_map()
        if dimension in wmap:
            return 0.0 <= value <= 1.0
        return True
