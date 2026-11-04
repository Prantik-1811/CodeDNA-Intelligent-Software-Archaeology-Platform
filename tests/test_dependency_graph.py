"""Unit tests for the dependency graph engine."""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from codna.dependency_graph import DependencyGraph
from codna.graph_models import GraphNode, GraphEdge, DependencyGraphData
from codna.ast_parser import parse_file

ROOT = Path("src/codna")


def test_graph_models_serialization():
    node = GraphNode(
        id="n1", type="file", label="foo.py", file_path="foo.py", line=1,
        language="python", metadata={"count": 5},
    )
    edge = GraphEdge(source="n1", target="n2", type="imports", line=5)
    data = DependencyGraphData(nodes=[node], edges=[edge])
    d = data.to_dict()
    assert len(d["nodes"]) == 1
    assert len(d["edges"]) == 1
    assert d["nodes"][0]["id"] == "n1"
    assert d["edges"][0]["type"] == "imports"


def test_build_graph_from_files():
    file_asts = []
    file_paths = []
    for f in [ROOT / "scanner.py", ROOT / "walker.py"]:
        ast = parse_file(f, ROOT, language="python")
        if ast:
            ast.path = str(f)
            file_asts.append(ast)
            file_paths.append(f)

    dg = DependencyGraph()
    data = dg.build_from_files(file_asts, file_paths, ROOT)
    assert data.metrics["node_count"] > 0
    assert data.metrics["file_count"] >= 2
    assert len(data.nodes) == data.metrics["node_count"]


def test_degrees():
    file_asts = []
    file_paths = []
    for f in [ROOT / "scanner.py", ROOT / "walker.py"]:
        ast = parse_file(f, ROOT, language="python")
        if ast:
            ast.path = str(f)
            file_asts.append(ast)
            file_paths.append(f)

    dg = DependencyGraph()
    dg.build_from_files(file_asts, file_paths, ROOT)
    deg = dg.degrees()
    assert len(deg) > 0
    for nid, d in deg.items():
        assert "in_degree" in d
        assert "out_degree" in d


def test_find_cycles():
    file_asts = []
    file_paths = []
    for f in [ROOT / "scanner.py", ROOT / "walker.py"]:
        ast = parse_file(f, ROOT, language="python")
        if ast:
            ast.path = str(f)
            file_asts.append(ast)
            file_paths.append(f)

    dg = DependencyGraph()
    dg.build_from_files(file_asts, file_paths, ROOT)
    cycles = dg.find_cycles()
    assert isinstance(cycles, list)
