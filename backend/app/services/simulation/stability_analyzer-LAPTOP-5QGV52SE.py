"""StabilityAnalyzer — ranking and shortlist stability across experiment runs.

READ-ONLY: operates on persisted experiment results.
"""

from __future__ import annotations

import statistics
from typing import Any

from app.domain.simulation_experiment_schemas import (
    CandidateStabilityMetrics,
    StabilityAnalysisResponse,
)


class StabilityAnalyzer:
    """Analyzes candidate ranking and shortlist stability across experiment runs."""

    def analyze(
        self,
        experiment_id: str,
        results: list[dict[str, Any]],
    ) -> StabilityAnalysisResponse:
        """Compute ranking stability, shortlist stability, and candidate stability."""
        ranking_stability = self._compute_ranking_stability(results)
        shortlist_stability = self._compute_shortlist_stability(results)
        candidate_stability = self._compute_candidate_stability(results)
        summary = self._build_summary(ranking_stability, shortlist_stability, candidate_stability)

        return StabilityAnalysisResponse(
            experiment_id=experiment_id,
            ranking_stability=ranking_stability,
            shortlist_stability=shortlist_stability,
            candidate_stability=candidate_stability,
            summary=summary,
        )

    def _compute_ranking_stability(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze how rankings change across configurations."""
        all_ranks: list[list[int]] = []
        for result in results:
            metrics = result.get("metrics") or {}
            rank_data = metrics.get("candidate_ranks") or []
            if rank_data:
                all_ranks.append(sorted(rank_data))

        if not all_ranks:
            return {"available": False, "reason": "No rank data available."}

        # Compute average rank standard deviation per position
        max_len = max(len(r) for r in all_ranks)
        position_variance: list[float] = []
        for pos in range(max_len):
            vals = [r[pos] for r in all_ranks if pos < len(r)]
            if len(vals) > 1:
                position_variance.append(statistics.variance(vals))

        avg_variance = statistics.mean(position_variance) if position_variance else 0
        top_k_overlaps = self._compute_top_k_overlaps(results)

        return {
            "available": True,
            "configurations_analyzed": len(results),
            "avg_rank_variance": round(avg_variance, 4),
            "position_variance": [round(v, 4) for v in position_variance[:20]],
            "top_k_overlaps": top_k_overlaps,
            "stability_level": self._classify_stability(avg_variance),
        }

    def _compute_shortlist_stability(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze shortlist overlap across configurations."""
        shortlists: list[set[str]] = []
        for result in results:
            metrics = result.get("metrics") or {}
            sl = metrics.get("shortlisted_candidates") or []
            if sl:
                shortlists.append(set(str(c) for c in sl))

        if len(shortlists) < 2:
            return {"available": False, "reason": "Insufficient shortlist data."}

        # Pairwise overlaps
        overlaps: list[float] = []
        for i in range(len(shortlists)):
            for j in range(i + 1, len(shortlists)):
                common = shortlists[i] & shortlists[j]
                union = shortlists[i] | shortlists[j]
                if union:
                    overlaps.append(len(common) / len(union))

        avg_overlap = statistics.mean(overlaps) if overlaps else 0

        # Per-candidate frequency
        candidate_counts: dict[str, int] = {}
        for sl in shortlists:
            for c in sl:
                candidate_counts[c] = candidate_counts.get(c, 0) + 1

        total = len(shortlists)
        high_freq = sum(1 for v in candidate_counts.values() if v == total)
        mid_freq = sum(1 for v in candidate_counts.values() if total / 2 <= v < total)

        return {
            "available": True,
            "configurations_analyzed": len(shortlists),
            "avg_jaccard_similarity": round(avg_overlap, 4),
            "candidates_always_shortlisted": high_freq,
            "candidates_frequently_shortlisted": mid_freq,
            "unique_candidates": len(candidate_counts),
            "stability_level": self._classify_stability(1 - avg_overlap),
        }

    def _compute_candidate_stability(
        self, results: list[dict[str, Any]],
    ) -> list[CandidateStabilityMetrics]:
        """Compute per-candidate stability metrics."""
        candidate_data: dict[str, dict[str, list[float]]] = {}

        for result in results:
            candidate_metrics = result.get("candidate_metrics") or {}
            for cand_id, info in candidate_metrics.items():
                if cand_id not in candidate_data:
                    candidate_data[cand_id] = {
                        "name": [info.get("name", cand_id)],
                        "scores": [],
                        "ranks": [],
                        "qualified": [],
                        "shortlisted": [],
                        "appeared": [],
                    }
                cd = candidate_data[cand_id]
                cd["name"].append(info.get("name", cand_id))
                if info.get("score") is not None:
                    cd["scores"].append(float(info["score"]))
                if info.get("rank") is not None:
                    cd["ranks"].append(float(info["rank"]))
                cd["qualified"].append(1.0 if info.get("qualified") else 0.0)
                cd["shortlisted"].append(1.0 if info.get("shortlisted") else 0.0)
                cd["appeared"].append(1.0)

        total_configs = len(results) or 1
        metrics_list: list[CandidateStabilityMetrics] = []

        for cand_id, data in candidate_data.items():
            scores = data["scores"]
            ranks = data["ranks"]
            name = data["name"][0] if data["name"] else cand_id

            metrics_list.append(CandidateStabilityMetrics(
                candidate_id=cand_id,
                candidate_name=name,
                appearance_frequency=round(len(data["appeared"]) / total_configs, 4),
                shortlist_frequency=round(sum(data["shortlisted"]) / total_configs, 4),
                rank_range_min=int(min(ranks)) if ranks else 0,
                rank_range_max=int(max(ranks)) if ranks else 0,
                rank_range=int(max(ranks) - min(ranks)) if len(ranks) > 1 else 0,
                rank_variance=round(statistics.variance(ranks), 4) if len(ranks) > 1 else 0.0,
                qualification_frequency=round(sum(data["qualified"]) / total_configs, 4),
                score_range_min=min(scores) if scores else 0.0,
                score_range_max=max(scores) if scores else 0.0,
            ))

        metrics_list.sort(key=lambda m: m.rank_variance, reverse=True)
        return metrics_list[:50]

    def _compute_top_k_overlaps(
        self, results: list[dict[str, Any]], k: int = 10,
    ) -> list[dict[str, Any]]:
        """Compute top-k overlap between pairs of results."""
        top_k_sets: list[set[str]] = []
        for result in results:
            metrics = result.get("metrics") or {}
            candidates = metrics.get("top_k_candidates") or []
            top_k_sets.append(set(str(c) for c in candidates[:k]))

        overlaps: list[dict[str, Any]] = []
        for i in range(min(len(top_k_sets), 5)):
            for j in range(i + 1, min(len(top_k_sets), 5)):
                common = top_k_sets[i] & top_k_sets[j]
                overlaps.append({
                    "config_a": i,
                    "config_b": j,
                    "overlap_count": len(common),
                    "overlap_ratio": round(len(common) / k, 4) if k > 0 else 0,
                })

        return overlaps

    def _classify_stability(self, variance: float) -> str:
        if variance < 1.0:
            return "high"
        if variance < 5.0:
            return "moderate"
        return "low"

    def _build_summary(
        self,
        ranking: dict[str, Any],
        shortlist: dict[str, Any],
        candidates: list[CandidateStabilityMetrics],
    ) -> dict[str, Any]:
        high_stable = sum(1 for c in candidates if c.rank_variance < 2.0)
        return {
            "ranking_stability": ranking.get("stability_level", "unknown"),
            "shortlist_stability": shortlist.get("stability_level", "unknown"),
            "candidates_analyzed": len(candidates),
            "highly_stable_candidates": high_stable,
        }
