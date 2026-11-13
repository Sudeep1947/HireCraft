"""ReportCSVService — CSV export for simulation reports.

Generates CSV content from structured report data for tabular
sections like candidate impact, ranking, fairness, and skills.
"""

from __future__ import annotations

import csv
from io import StringIO


class ReportCSVService:
    """Generates CSV content from simulation report data."""

    def generate(self, report, section: str) -> str:
        """Generate CSV content for a specific report section."""
        data = report.report_data or {}

        generators = {
            "candidate_impact": self._generate_candidate_impact_csv,
            "ranking": self._generate_ranking_csv,
            "fairness": self._generate_fairness_csv,
            "skills": self._generate_skills_csv,
        }

        generator = generators.get(section)
        if not generator:
            return self._generate_candidate_impact_csv(data)

        return generator(data)

    def _generate_candidate_impact_csv(self, data: dict) -> str:
        """Generate CSV for candidate impact table."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Candidate ID", "Candidate Name",
            "Baseline Score", "Simulation Score", "Score Change",
            "Baseline Rank", "Simulation Rank", "Rank Change",
            "Shortlisted",
        ])

        table = data.get("candidate_impact_table", {})
        items = table.get("items", [])

        for item in items:
            writer.writerow([
                item.get("candidate_id", ""),
                item.get("candidate_name", ""),
                item.get("baseline_score", 0),
                item.get("simulation_score", 0),
                item.get("score_change", 0),
                item.get("baseline_rank", 0),
                item.get("simulation_rank", 0),
                item.get("rank_change", 0),
                item.get("shortlisted", False),
            ])

        return output.getvalue()

    def _generate_ranking_csv(self, data: dict) -> str:
        """Generate CSV for ranking impact data."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["Metric", "Value"])

        ranking = data.get("ranking_impact", {})
        overview = ranking.get("overview", {})
        for key, value in overview.items():
            writer.writerow([key, value])

        writer.writerow([])
        writer.writerow(["Score Movement", ""])
        score_mov = ranking.get("score_movement", {})
        for key, value in score_mov.items():
            writer.writerow([key, value])

        return output.getvalue()

    def _generate_fairness_csv(self, data: dict) -> str:
        """Generate CSV for fairness impact data."""
        output = StringIO()
        writer = csv.writer(output)

        fairness = data.get("fairness_impact", {})
        if not fairness.get("available"):
            writer.writerow(["Status", "Fairness data not available"])
            return output.getvalue()

        groups = fairness.get("groups", [])
        if groups:
            writer.writerow(["Group Data"])
            if groups:
                headers = list(groups[0].keys()) if isinstance(groups[0], dict) else []
                writer.writerow(headers)
                for group in groups:
                    if isinstance(group, dict):
                        writer.writerow([group.get(h, "") for h in headers])

        return output.getvalue()

    def _generate_skills_csv(self, data: dict) -> str:
        """Generate CSV for skill impact data."""
        output = StringIO()
        writer = csv.writer(output)

        skill = data.get("skill_impact", {})
        if not skill.get("available"):
            writer.writerow(["Status", "Skill impact data not available"])
            return output.getvalue()

        writer.writerow(["Metric", "Value"])
        writer.writerow(["Candidates Affected", skill.get("candidates_affected", 0)])

        gaps = skill.get("skill_gaps", [])
        if gaps:
            writer.writerow([])
            writer.writerow(["Skill Gaps"])
            for gap in gaps:
                if isinstance(gap, dict):
                    writer.writerow([gap.get("skill", ""), gap.get("count", 0)])

        return output.getvalue()
