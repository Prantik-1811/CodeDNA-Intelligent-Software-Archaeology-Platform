"""Unit tests for the risk engine."""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from codna.risk_engine import RiskEngine, FEATURE_WEIGHTS


def test_feature_weights_sum_to_one():
    total = sum(FEATURE_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


def test_risk_engine_empty():
    engine = RiskEngine(graph=None, graph_data=None, metrics_by_path={}, git_history_data=None)
    report = engine.analyze()
    assert report.modules == []
    assert report.summary["total_modules"] == 0


def test_risk_levels():
    engine = RiskEngine(graph=None, graph_data=None, metrics_by_path={}, git_history_data=None)
    assert engine._risk_level(80) == "critical"
    assert engine._risk_level(60) == "high"
    assert engine._risk_level(30) == "medium"
    assert engine._risk_level(5) == "low"


def test_bug_fix_detection():
    engine = RiskEngine(graph=None, graph_data=None, metrics_by_path={}, git_history_data=None)
    assert engine._is_bug_fix("fix bug in login") is True
    assert engine._is_bug_fix("resolve issue #42") is True
    assert engine._is_bug_fix("hotfix for production") is True
    assert engine._is_bug_fix("add new feature") is False
    assert engine._is_bug_fix("refactor code") is False


def test_risk_report_structure():
    # Minimal metrics for one file
    metrics = {
        "foo.py": type("M", (), {
            "cyclomatic_complexity": 50,
            "code_lines": 100,
            "complexity_density": 0.5,
            "function_count": 3,
            "class_count": 1,
        })(),
    }
    engine = RiskEngine(
        graph=None, graph_data=None, metrics_by_path=metrics, git_history_data=None
    )
    report = engine.analyze()
    assert len(report.modules) == 1
    m = report.modules[0]
    assert m.path == "foo.py"
    assert m.risk_level in ("low", "medium", "high", "critical")
    assert m.investigation_priority == 1
    assert len(m.features) == 6
    assert m.explanation != ""

    # Summary should have expected keys
    s = report.summary
    assert "total_modules" in s
    assert "average_risk_score" in s
    assert "max_risk_score" in s
    assert "critical_count" in s
