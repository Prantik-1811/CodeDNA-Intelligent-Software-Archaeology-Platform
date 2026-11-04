"""Architecture analysis report.

Combines the dependency graph (Week 3) with code metrics (Week 4) to
identify highly connected modules, large/highly-coupled files, graph
centrality, and potential architectural bottlenecks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from .dependency_graph import DependencyGraph
from .graph_models import DependencyGraphData
from .metrics import CodeMetrics, compute_file_metrics


@dataclass
class ModuleInfo:
    """Analysis summary for a single module/file."""

    path: str
    language: str
    total_lines: int
    code_lines: int
    cyclomatic_complexity: int
    complexity_density: float
    function_count: int
    class_count: int
    in_degree: int
    out_degree: int
    degree_centrality: float
    betweenness_centrality: float
    closeness_centrality: float
    coupling_score: float
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class ArchitectureReport:
    """Full architecture analysis report."""

    modules: list[ModuleInfo] = field(default_factory=list)
    highly_connected: list[ModuleInfo] = field(default_factory=list)
    large_coupled_files: list[ModuleInfo] = field(default_factory=list)
    bottlenecks: list[ModuleInfo] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class ArchitectureAnalyzer:
    """Analyze repository architecture from graph + metrics."""

    def __init__(self, graph: DependencyGraph, graph_data: DependencyGraphData,
                 file_metrics: dict[str, CodeMetrics]) -> None:
        self.graph = graph
        self.graph_data = graph_data
        self.file_metrics = file_metrics
        self._centrality: dict[str, dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def analyze(self) -> ArchitectureReport:
        self._compute_centrality()
        modules = self._build_module_infos()
        report = ArchitectureReport(modules=modules)

        # Highly connected = top by total degree (in + out).
        report.highly_connected = sorted(
            modules, key=lambda m: m.in_degree + m.out_degree, reverse=True
        )[:10]

        # Large and highly coupled = high code_lines AND high coupling.
        report.large_coupled_files = sorted(
            modules, key=lambda m: m.code_lines * m.coupling_score, reverse=True
        )[:10]

        # Bottlenecks = high betweenness centrality (bridge nodes).
        report.bottlenecks = sorted(
            modules, key=lambda m: m.betweenness_centrality, reverse=True
        )[:10]

        report.summary = self._summary(modules)
        return report

    # ------------------------------------------------------------------
    # Centrality
    # ------------------------------------------------------------------
    def _compute_centrality(self) -> None:
        g = self.graph.graph
        if g.number_of_nodes() == 0:
            self._centrality = {}
            return

        try:
            degree = nx.degree_centrality(g)
        except Exception:
            degree = {n: 0.0 for n in g.nodes}
        try:
            betweenness = nx.betweenness_centrality(g)
        except Exception:
            betweenness = {n: 0.0 for n in g.nodes}
        try:
            closeness = nx.closeness_centrality(g)
        except Exception:
            closeness = {n: 0.0 for n in g.nodes}

        self._centrality = {
            n: {
                "degree": degree.get(n, 0.0),
                "betweenness": betweenness.get(n, 0.0),
                "closeness": closeness.get(n, 0.0),
            }
            for n in g.nodes
        }

    # ------------------------------------------------------------------
    # Module info
    # ------------------------------------------------------------------
    def _build_module_infos(self) -> list[ModuleInfo]:
        infos: list[ModuleInfo] = []
        for node in self.graph_data.nodes:
            if node.type != "file":
                continue
            metrics = self.file_metrics.get(node.file_path)
            if metrics is None:
                continue

            centrality = self._centrality.get(node.id, {})
            in_deg = self.graph.graph.in_degree(node.id)
            out_deg = self.graph.graph.out_degree(node.id)

            # Coupling score: normalize out-degree (dependencies) + fan-in.
            coupling_score = float(in_deg + out_deg)

            risk_flags: list[str] = []
            if metrics.cyclomatic_complexity > 10:
                risk_flags.append("high_complexity")
            if metrics.complexity_density > 0.05:
                risk_flags.append("high_complexity_density")
            if metrics.code_lines > 300:
                risk_flags.append("large_file")
            if coupling_score > 5:
                risk_flags.append("highly_coupled")
            if centrality.get("betweenness", 0) > 0.1:
                risk_flags.append("potential_bottleneck")

            infos.append(ModuleInfo(
                path=node.file_path,
                language=node.language or "unknown",
                total_lines=metrics.total_lines,
                code_lines=metrics.code_lines,
                cyclomatic_complexity=metrics.cyclomatic_complexity,
                complexity_density=metrics.complexity_density,
                function_count=metrics.function_count,
                class_count=metrics.class_count,
                in_degree=in_deg,
                out_degree=out_deg,
                degree_centrality=centrality.get("degree", 0.0),
                betweenness_centrality=centrality.get("betweenness", 0.0),
                closeness_centrality=centrality.get("closeness", 0.0),
                coupling_score=coupling_score,
                risk_flags=risk_flags,
            ))

        return infos

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _summary(self, modules: list[ModuleInfo]) -> dict[str, Any]:
        if not modules:
            return {}

        total_files = len(modules)
        total_lines = sum(m.code_lines for m in modules)
        avg_cc = sum(m.cyclomatic_complexity for m in modules) / total_files
        max_cc = max(m.cyclomatic_complexity for m in modules)
        high_complexity = [m for m in modules if "high_complexity" in m.risk_flags]
        large_files = [m for m in modules if "large_file" in m.risk_flags]
        highly_coupled = [m for m in modules if "highly_coupled" in m.risk_flags]
        bottlenecks = [m for m in modules if "potential_bottleneck" in m.risk_flags]

        return {
            "total_files": total_files,
            "total_code_lines": total_lines,
            "avg_cyclomatic_complexity": round(avg_cc, 2),
            "max_cyclomatic_complexity": max_cc,
            "high_complexity_count": len(high_complexity),
            "large_file_count": len(large_files),
            "highly_coupled_count": len(highly_coupled),
            "potential_bottleneck_count": len(bottlenecks),
            "high_complexity_files": [m.path for m in high_complexity[:5]],
            "large_files": [m.path for m in large_files[:5]],
            "highly_coupled_files": [m.path for m in highly_coupled[:5]],
            "bottleneck_files": [m.path for m in bottlenecks[:5]],
        }
