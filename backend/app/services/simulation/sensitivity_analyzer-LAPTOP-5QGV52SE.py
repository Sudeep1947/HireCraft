"""SensitivityAnalyzer — parameter sensitivity metrics across experiment runs.

READ-ONLY: operates on persisted experiment results.
"""

from __future__ import annotations

from typing import Any

from app.domain.simulation_experiment_schemas import (
    SensitivityAnalysisResponse,
    SensitivityCurve,
    SensitivityPoint,
)


class SensitivityAnalyzer:
    """Analyzes how metrics change across parameter values."""

    def analyze(
        self,
        experiment_id: str,
        results: list[dict[str, Any]],
        parameter_ranges: dict[str, Any],
    ) -> SensitivityAnalysisResponse:
        """Compute sensitivity curves from experiment results."""
        curves: list[SensitivityCurve] = []

        # Group results by each parameter dimension
        for dim_name, dim_values in parameter_ranges.items():
            points = self._build_curve_points(results, dim_name)
            if not points:
                continue

            metric_values = [p.metric_value for p in points]
            min_val = min(metric_values) if metric_values else 0
            max_val = max(metric_values) if metric_values else 0
            spread = max_val - min_val
            direction = self._determine_direction(metric_values)

            curves.append(SensitivityCurve(
                dimension=dim_name,
                points=points,
                min_value=min_val,
                max_value=max_val,
                range_spread=round(spread, 4),
                direction=direction,
            ))

        summary = self._build_summary(curves, results)
        return SensitivityAnalysisResponse(
            experiment_id=experiment_id,
            curves=curves,
            summary=summary,
        )

    def analyze_candidate_sensitivity(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze per-candidate score/rank sensitivity across configurations."""
        candidate_metrics: dict[str, dict[str, list[float]]] = {}

        for result in results:
            candidate_data = result.get("candidate_metrics") or {}
            param_vals = result.get("parameter_values") or {}

            for cand_id, cand_info in candidate_data.items():
                if cand_id not in candidate_metrics:
                    candidate_metrics[cand_id] = {
                        "scores": [],
                        "ranks": [],
                        "qualified": [],
                        "shortlisted": [],
                    }
                scores = candidate_metrics[cand_id]["scores"]
                ranks = candidate_metrics[cand_id]["ranks"]
                qualified = candidate_metrics[cand_id]["qualified"]
                shortlisted = candidate_metrics[cand_id]["shortlisted"]

                score = cand_info.get("score")
                if score is not None:
                    scores.append(float(score))
                rank = cand_info.get("rank")
                if rank is not None:
                    ranks.append(float(rank))
                qualified.append(1.0 if cand_info.get("qualified") else 0.0)
                shortlisted.append(1.0 if cand_info.get("shortlisted") else 0.0)

        stability = {}
        for cand_id, metrics in candidate_metrics.items():
            scores = metrics["scores"]
            ranks = metrics["ranks"]
            stability[cand_id] = {
                "score_range": (max(scores) - min(scores)) if len(scores) > 1 else 0,
                "score_variance": self._variance(scores),
                "rank_range": (max(ranks) - min(ranks)) if len(ranks) > 1 else 0,
                "rank_variance": self._variance(ranks),
                "qualification_rate": (
                    sum(metrics["qualified"]) / len(metrics["qualified"])
                    if metrics["qualified"] else 0
                ),
                "shortlist_rate": (
                    sum(metrics["shortlisted"]) / len(metrics["shortlisted"])
                    if metrics["shortlisted"] else 0
                ),
            }

        return stability

    # ── Private helpers ─────────────────────────────────────────────

    def _build_curve_points(
        self,
        results: list[dict[str, Any]],
        dimension: str,
    ) -> list[SensitivityPoint]:
        points: list[SensitivityPoint] = []
        for result in results:
            param_vals = result.get("parameter_values") or {}
            metrics = result.get("metrics") or {}
            param_value = param_vals.get(dimension)
            if param_value is None:
                continue

            # Extract primary metric (qualified count or avg score)
            metric_value = (
                metrics.get("qualified_count")
                or metrics.get("avg_score")
                or metrics.get("total_candidates")
                or 0
            )

            points.append(SensitivityPoint(
                parameter_value=param_value,
                metric_name="qualified_count",
                metric_value=float(metric_value),
                configuration_hash=result.get("configuration_hash"),
            ))

        points.sort(key=lambda p: float(p.parameter_value) if isinstance(p.parameter_value, (int, float)) else 0)
        return points

    def _determine_direction(self, values: list[float]) -> str:
        if len(values) < 2:
            return "stable"
        increasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
        decreasing = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
        if increasing:
            return "increasing"
        if decreasing:
            return "decreasing"
        return "mixed"

    def _build_summary(
        self,
        curves: list[SensitivityCurve],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_configs = len(results)
        completed = sum(1 for r in results if r.get("execution_status") == "completed")
        return {
            "total_configurations": total_configs,
            "completed_configurations": completed,
            "dimensions_analyzed": len(curves),
            "max_sensitivity_dimension": (
                max(curves, key=lambda c: c.range_spread).dimension
                if curves else None
            ),
        }

    @staticmethod
    def _variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)
