"""Unit tests for code complexity metrics."""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from codna.metrics import compute_file_metrics, ComplexityCalculator
import ast as py_ast

ROOT = Path("src/codna")


def test_complexity_simple():
    tree = py_ast.parse("x = 1\n")
    calc = ComplexityCalculator()
    cc = calc.calculate(tree)
    assert cc == 1


def test_complexity_if():
    tree = py_ast.parse("if x:\n    y = 1\n")
    calc = ComplexityCalculator()
    cc = calc.calculate(tree)
    assert cc == 2


def test_complexity_for():
    tree = py_ast.parse("for i in range(10):\n    print(i)\n")
    calc = ComplexityCalculator()
    cc = calc.calculate(tree)
    assert cc == 2


def test_complexity_multiple():
    source = """
if a:
    pass
if b:
    pass
"""
    tree = py_ast.parse(source)
    calc = ComplexityCalculator()
    cc = calc.calculate(tree)
    assert cc == 3


def test_compute_file_metrics():
    from codna.ast_parser import parse_file

    ast = parse_file(ROOT / "walker.py", ROOT, language="python")
    source = (ROOT / "walker.py").read_bytes()
    m = compute_file_metrics(ast, source, language="python")
    assert m.total_lines > 0
    assert m.code_lines > 0
    assert m.cyclomatic_complexity >= 1
    assert m.function_count >= 0


def test_complexity_density():
    from codna.metrics import CodeMetrics

    m = CodeMetrics(
        path="x.py",
        relative_path="x.py",
        language="python",
        code_lines=100,
        cyclomatic_complexity=10,
    )
    assert m.complexity_density == 0.1

    m2 = CodeMetrics(
        path="y.py",
        relative_path="y.py",
        language="python",
        code_lines=0,
        cyclomatic_complexity=1,
    )
    assert m2.complexity_density == 0.0


def test_bool_op_complexity():
    source = "if a and b or c:\n    pass\n"
    tree = py_ast.parse(source)
    calc = ComplexityCalculator()
    cc = calc.calculate(tree)
    # base 1 + If (1) + 2 BoolOp nodes (2) = 4
    assert cc == 4
