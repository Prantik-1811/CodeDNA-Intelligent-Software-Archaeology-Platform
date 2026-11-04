"""Unit tests for change impact analysis."""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from codna.graph_models import GraphNode, GraphEdge, DependencyGraphData
from codna.change_impact import ChangeImpactAnalyzer


def _build_fake_graph():
    """Build a minimal fake graph for testing change impact."""
    class FakeDiGraph:
        def __init__(self):
            self._nodes = {}
            self._edges = []

        def add_node(self, nid, **attrs):
            self._nodes[nid] = attrs

        def add_edge(self, src, dst, **attrs):
            self._edges.append((src, dst, attrs))

        @property
        def nodes(self):
            class View:
                def __init__(self, d):
                    self._d = d
                def __call__(self, data=False):
                    if data:
                        return list(self._d.items())
                    return list(self._d.keys())
                def __getitem__(self, nid):
                    return self._d[nid]
            return View(self._nodes)

        def edges(self, data=False):
            if data:
                return list(self._edges)
            return [(s, d) for s, d, _ in self._edges]

        def in_degree(self, nid):
            return sum(1 for s, d, _ in self._edges if d == nid)

        def out_degree(self, nid):
            return sum(1 for s, d, _ in self._edges if s == nid)

        def __contains__(self, nid):
            return nid in self._nodes

        @property
        def graph(self):
            return self

    graph = FakeDiGraph()
    graph.add_node("file:auth.py::auth.py", type="file", label="auth.py", file_path="auth.py", line=1, language="python")
    graph.add_node("file:api.py::api.py", type="file", label="api.py", file_path="api.py", line=1, language="python")
    graph.add_node("function:auth.py::authenticate_user", type="function", label="authenticate_user", file_path="auth.py", line=10, language="python")
    graph.add_node("function:api.py::login", type="function", label="login", file_path="api.py", line=20, language="python")

    graph.add_edge("file:auth.py::auth.py", "function:auth.py::authenticate_user", type="contains", line=10)
    graph.add_edge("file:api.py::api.py", "function:api.py::login", type="contains", line=20)
    graph.add_edge("function:api.py::login", "function:auth.py::authenticate_user", type="calls", line=25)
    graph.add_edge("file:api.py::api.py", "file:auth.py::auth.py", type="imports", line=5)

    nodes = [
        GraphNode(id=nid, type=d["type"], label=d["label"], file_path=d["file_path"], line=d.get("line", 0), language=d.get("language", "python"), metadata={})
        for nid, d in graph._nodes.items()
    ]
    edges = [GraphEdge(source=s, target=t, type=a.get("type", "unknown"), line=a.get("line", 0), metadata={}) for s, t, a in graph._edges]
    data = DependencyGraphData(nodes=nodes, edges=edges)
    return graph, data


def test_analyze_function_change():
    graph, data = _build_fake_graph()
    cia = ChangeImpactAnalyzer(graph, data, git_history_data=None, file_metrics={})
    report = cia.analyze_function_change("authenticate_user", "auth.py")

    assert report.target_type == "function"
    assert report.target_label == "authenticate_user"
    assert report.target_file == "auth.py"
    assert report.risk_level in ("low", "medium", "high", "critical")
    assert len(report.direct_callers) == 1  # login calls authenticate_user
    assert report.direct_callers[0].label == "login"
    assert report.summary["direct_caller_count"] == 1


def test_analyze_file_change():
    graph, data = _build_fake_graph()
    cia = ChangeImpactAnalyzer(graph, data, git_history_data=None, file_metrics={})
    report = cia.analyze_file_change("auth.py")

    assert report.target_type == "file"
    assert report.target_label == "auth.py"
    assert report.summary["target"] == "file:auth.py"
    assert report.summary["direct_caller_count"] >= 1


def test_impact_report_structure():
    graph, data = _build_fake_graph()
    cia = ChangeImpactAnalyzer(graph, data, git_history_data=None, file_metrics={})
    report = cia.analyze_function_change("authenticate_user", "auth.py")

    assert report.risk_score >= 0
    assert report.risk_level in ("low", "medium", "high", "critical")
    assert len(report.review_components) >= 1
    assert "risk_score" in report.summary
    assert "risk_level" in report.summary
    assert "top_review_targets" in report.summary
