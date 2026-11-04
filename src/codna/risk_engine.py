"""Bug prediction and risk engine.

Develops a heuristic (weighted scoring) model to identify potentially risky
modules. Combines features from:
- Week 3: Dependency graph centrality
- Week 4: Code complexity metrics
- Week 5: Git history (change frequency, contributors, churn, bug-fix commits)
- Week 6: Change impact analysis

Scores are investigation priorities, not proof that a file contains a bug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskFeature:
    """A single risk feature value and its contribution."""

    name: str
    raw_value: float
    normalized: float  # 0..1
    weight: float
    score: float  # normalized * weight
    explanation: str


@dataclass
class ModuleRisk:
    """Risk assessment for a single module/file."""

    path: str
    total_score: float  # 0..100
    risk_level: str  # low, medium, high, critical
    features: list[RiskFeature] = field(default_factory=list)
    explanation: str = ""
    investigation_priority: int = 0  # 1 = highest


@dataclass
class RiskReport:
    """Full risk-ranked modules report."""

    modules: list[ModuleRisk] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# Feature weights (must sum to 1.0 for normalized scoring).
FEATURE_WEIGHTS = {
    "complexity": 0.25,
    "change_frequency": 0.20,
    "contributors": 0.15,
    "dependency_centrality": 0.20,
    "bug_fix_commits": 0.10,
    "code_churn": 0.10,
}

# Keywords that indicate a bug-fix commit.
BUG_FIX_KEYWORDS = [
    r"\bfix\b", r"\bfixs\b", r"\bfixed\b", r"\bfixes\b",
    r"\bbug\b", r"\bpatch\b", r"\bresolve\b", r"\bfixed\b",
    r"\bhotfix\b", r"\bissue\b", r"\bcorrect\b", r"\brepair\b",
    r"\bremediate\b", r"\berratum\b",
]


class RiskEngine:
    """Heuristic risk engine for bug prediction."""

    def __init__(
        self,
        graph=None,
        graph_data=None,
        metrics_by_path=None,
        git_history_data=None,
        change_impact_report=None,
    ) -> None:
        self.graph = graph
        self.graph_data = graph_data
        self.metrics_by_path = metrics_by_path or {}
        self.git_history_data = git_history_data
        self.change_impact_report = change_impact_report

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------
    def _complexity_feature(self, path: str) -> RiskFeature:
        metrics = self.metrics_by_path.get(path)
        cc = metrics.cyclomatic_complexity if metrics else 1
        # Normalize: CC of 50+ is max risk
        normalized = min(cc / 50.0, 1.0)
        weight = FEATURE_WEIGHTS["complexity"]
        return RiskFeature(
            name="complexity",
            raw_value=float(cc),
            normalized=normalized,
            weight=weight,
            score=normalized * weight * 100.0,
            explanation=(
                "cyclomatic complexity %d (normalized %.2f)" % (cc, normalized)
            ),
        )

    def _change_frequency_feature(self, path: str) -> RiskFeature:
        histories = {}
        if self.git_history_data:
            histories = self.git_history_data.file_histories
        fh = histories.get(path)
        count = fh.change_count if fh else 0
        normalized = min(count / 20.0, 1.0)  # 20+ changes = max
        weight = FEATURE_WEIGHTS["change_frequency"]
        return RiskFeature(
            name="change_frequency",
            raw_value=float(count),
            normalized=normalized,
            weight=weight,
            score=normalized * weight * 100.0,
            explanation="changed %d time(s) (normalized %.2f)" % (count, normalized),
        )

    def _contributors_feature(self, path: str) -> RiskFeature:
        histories = {}
        if self.git_history_data:
            histories = self.git_history_data.file_histories
        fh = histories.get(path)
        count = len(fh.contributors) if fh else 0
        normalized = min(count / 10.0, 1.0)  # 10+ contributors = max
        weight = FEATURE_WEIGHTS["contributors"]
        return RiskFeature(
            name="contributors",
            raw_value=float(count),
            normalized=normalized,
            weight=weight,
            score=normalized * weight * 100.0,
            explanation="%d contributor(s) (normalized %.2f)" % (count, normalized),
        )

    def _dependency_centrality_feature(self, path: str) -> RiskFeature:
        centrality = 0
        if self.graph and self.graph_data:
            for node in self.graph_data.nodes:
                if node.type == "file" and node.file_path == path:
                    nid = node.id
                    if self.graph:
                        centrality = self.graph.graph.in_degree(nid) + self.graph.graph.out_degree(nid)
                    break
        normalized = min(centrality / 15.0, 1.0)  # 15+ connections = max
        weight = FEATURE_WEIGHTS["dependency_centrality"]
        return RiskFeature(
            name="dependency_centrality",
            raw_value=float(centrality),
            normalized=normalized,
            weight=weight,
            score=normalized * weight * 100.0,
            explanation="%d dependency connections (normalized %.2f)" % (centrality, normalized),
        )

    def _bug_fix_feature(self, path: str) -> RiskFeature:
        count = 0
        if self.git_history_data:
            for commit in self.git_history_data.commits:
                if path in commit.files_changed:
                    if self._is_bug_fix(commit.message):
                        count += 1
        normalized = min(count / 5.0, 1.0)  # 5+ bug fixes = max
        weight = FEATURE_WEIGHTS["bug_fix_commits"]
        return RiskFeature(
            name="bug_fix_commits",
            raw_value=float(count),
            normalized=normalized,
            weight=weight,
            score=normalized * weight * 100.0,
            explanation="%d bug-fix commit(s) (normalized %.2f)" % (count, normalized),
        )

    def _code_churn_feature(self, path: str) -> RiskFeature:
        histories = {}
        if self.git_history_data:
            histories = self.git_history_data.file_histories
        fh = histories.get(path)
        churn = (fh.total_insertions + fh.total_deletions) if fh else 0
        normalized = min(churn / 500.0, 1.0)  # 500+ lines changed = max
        weight = FEATURE_WEIGHTS["code_churn"]
        return RiskFeature(
            name="code_churn",
            raw_value=float(churn),
            normalized=normalized,
            weight=weight,
            score=normalized * weight * 100.0,
            explanation="%d lines changed (normalized %.2f)" % (churn, normalized),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_bug_fix(message: str) -> bool:
        """Check if a commit message indicates a bug fix."""
        lower = message.lower()
        for pattern in BUG_FIX_KEYWORDS:
            if re.search(pattern, lower):
                return True
        return False

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 70:
            return "critical"
        if score >= 45:
            return "high"
        if score >= 20:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def analyze(self) -> RiskReport:
        """Run the risk engine across all files."""
        # Collect all file paths from graph data, metrics, and git history.
        all_paths: set[str] = set()

        if self.graph_data:
            for node in self.graph_data.nodes:
                if node.type == "file":
                    all_paths.add(node.file_path)

        all_paths.update(self.metrics_by_path.keys())

        if self.git_history_data:
            all_paths.update(self.git_history_data.file_histories.keys())

        module_risks: list[ModuleRisk] = []

        for path in sorted(all_paths):
            features = [
                self._complexity_feature(path),
                self._change_frequency_feature(path),
                self._contributors_feature(path),
                self._dependency_centrality_feature(path),
                self._bug_fix_feature(path),
                self._code_churn_feature(path),
            ]

            total_score = sum(f.score for f in features)
            risk_level = self._risk_level(total_score)

            # Build explanation string
            top_features = sorted(features, key=lambda f: f.score, reverse=True)[:3]
            explanation_parts = [
                "%s (%.1f)" % (f.name, f.score) for f in top_features if f.score > 0
            ]
            explanation = (
                ", ".join(explanation_parts)
                if explanation_parts
                else "no significant risk factors"
            )

            module_risks.append(
                ModuleRisk(
                    path=path,
                    total_score=round(total_score, 1),
                    risk_level=risk_level,
                    features=features,
                    explanation=explanation,
                )
            )

        # Sort by total score desc, assign investigation priority
        module_risks.sort(key=lambda m: m.total_score, reverse=True)
        for idx, mr in enumerate(module_risks):
            mr.investigation_priority = idx + 1

        report = RiskReport(modules=module_risks)
        report.summary = self._build_summary(module_risks)
        return report

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _build_summary(self, modules: list[ModuleRisk]) -> dict:
        if not modules:
            return {}

        critical = [m for m in modules if m.risk_level == "critical"]
        high = [m for m in modules if m.risk_level == "high"]
        medium = [m for m in modules if m.risk_level == "medium"]
        low = [m for m in modules if m.risk_level == "low"]

        avg_score = sum(m.total_score for m in modules) / len(modules)
        max_score = max(m.total_score for m in modules)

        return {
            "total_modules": len(modules),
            "average_risk_score": round(avg_score, 1),
            "max_risk_score": max_score,
            "critical_count": len(critical),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "critical_modules": [m.path for m in critical[:5]],
            "high_risk_modules": [m.path for m in high[:5]],
            "top_investigation_priorities": [
                {
                    "path": m.path,
                    "score": m.total_score,
                    "level": m.risk_level,
                    "priority": m.investigation_priority,
                }
                for m in modules[:5]
            ],
        }
