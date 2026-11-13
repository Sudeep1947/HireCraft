"""RobustnessAnalyzer — strategy robustness profiles.

READ-ONLY: operates on persisted experiment results.
"""

from __future__ import annotations

from typing import Any

from app.domain.simulation_experiment_schemas import (
    RobustnessAnalysisResponse,
    RobustnessPerturbationResult,
    RobustnessProfile,
)


class RobustnessAnalyzer:
    """Analyzes how stable outcomes are under controlled perturbations."""

    def analyze(
        self,
        experiment_id: str,
        base_results: dict[str, Any] | None,
        perturbed_results: list[dict[str, Any]],
    ) -> RobustnessAnalysisResponse:
        """Build robustness profile from base + perturbed results."""
        perturbation_results = self._compute_perturbation_changes(
            base_results, perturbed_results,
        )
        profiles = self._build_profiles(perturbation_results)
        summary = self._build_summary(perturbation_results, profiles)

        return RobustnessAnalysisResponse(
            experiment_id=experiment_id,
            perturbation_results=perturbation_results,
            profiles=profiles,
            summary=summary,
        )

    def _compute_perturbation_changes(
        self,
        base_results: dict[str, Any] | None,
        perturbed_results: list[dict[str, Any]],
    ) -> list[RobustnessPerturbationResult]:
        changes: list[RobustnessPerturbationResult] = []
        if not base_results:
            return changes

        base_metrics = base_results.get("metrics") or {}
        base_qualified = base_metrics.get("qualified_count", 0)
        base_shortlist = base_metrics.get("shortlisted_count", 0)
        base_avg_score = base_metrics.get("avg_score", 0)

        for perturbed in perturbed_results:
            param_vals = perturbed.get("parameter_values") or {}
            perturbed_metrics = perturbed.get("metrics") or {}

            # Determine which dimension was perturbed
            dimension = self._detect_perturbed_dimension(param_vals, base_results)
            perturbation_type = "numeric_delta"
            delta = None

            if dimension:
                base_val = (base_results.get("parameter_values") or {}).get(dimension)
                perturbed_val = param_vals.get(dimension)
                if base_val is not None and perturbed_val is not None:
                    try:
                        delta = float(perturbed_val) - float(base_val)
                    except (ValueError, TypeError):
                        delta = None

            changes.append(RobustnessPerturbationResult(
                dimension=dimension or "unknown",
                perturbation_type=perturbation_type,
                delta=delta,
                ranking_change=self._safe_diff(
                    base_metrics.get("avg_rank"),
                    perturbed_metrics.get("avg_rank"),
                ),
                shortlist_change=self._safe_int_diff(
                    base_shortlist,
                    perturbed_metrics.get("shortlisted_count", 0),
                ),
                qualification_change=self._safe_int_diff(
                    base_qualified,
                    perturbed_metrics.get("qualified_count", 0),
                ),
                fairness_metric_change=self._safe_diff(
                    base_metrics.get("spd"),
                    perturbed_metrics.get("spd"),
                ),
            ))

        return changes

    def _build_profiles(
        self,
        changes: list[RobustnessPerturbationResult],
    ) -> list[RobustnessProfile]:
        profiles: list[RobustnessProfile] = []
        by_dimension: dict[str, list[RobustnessPerturbationResult]] = {}
        for c in changes:
            by_dimension.setdefault(c.dimension, []).append(c)

        for dim, dim_changes in by_dimension.items():
            rank_changes = [abs(c.ranking_change) for c in dim_changes if c.ranking_change is not None]
            shortlist_changes = [abs(c.shortlist_change) for c in dim_changes if c.shortlist_change is not None]
            fairness_changes = [abs(c.fairness_metric_change) for c in dim_changes if c.fairness_metric_change is not None]

            deltas = [c.delta for c in dim_changes if c.delta is not None]
            range_str = (
                f"{min(deltas):.2f} to {max(deltas):.2f}"
                if deltas else "N/A"
            )

            profiles.append(RobustnessProfile(
                parameter=dim,
                range_tested=range_str,
                rank_variation=max(rank_changes) if rank_changes else 0.0,
                shortlist_variation=max(shortlist_changes) if shortlist_changes else 0.0,
                fairness_variation=max(fairness_changes) if fairness_changes else None,
            ))

        return profiles

    def _build_summary(
        self,
        changes: list[RobustnessPerturbationResult],
        profiles: list[RobustnessProfile],
    ) -> dict[str, Any]:
        total = len(changes)
        dimensions_tested = len(profiles)
        high_variation = sum(
            1 for p in profiles
            if p.rank_variation > 5 or (p.shortlist_variation or 0) > 3
        )
        return {
            "total_perturbations": total,
            "dimensions_tested": dimensions_tested,
            "high_variation_dimensions": high_variation,
            "most_sensitive_dimension": (
                max(profiles, key=lambda p: p.rank_variation).parameter
                if profiles else None
            ),
        }

    def _detect_perturbed_dimension(
        self,
        param_vals: dict[str, Any],
        base_results: dict[str, Any],
    ) -> str | None:
        base_params = base_results.get("parameter_values") or {}
        for key, val in param_vals.items():
            if key in base_params and base_params[key] != val:
                return key
        return None

    @staticmethod
    def _safe_diff(a: Any, b: Any) -> float | None:
        try:
            return round(float(b) - float(a), 4)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int_diff(a: Any, b: Any) -> int | None:
        try:
            return int(b) - int(a)
        except (ValueError, TypeError):
            return None
