"""Code complexity metrics.

Calculates cyclomatic complexity, lines of code, and related source-code
metrics using Python's built-in ``ast`` module for reliable, dependency-free
analysis.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class CodeMetrics:
    """Metrics for a single source file."""

    path: str
    relative_path: str
    language: str
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    cyclomatic_complexity: int = 1
    function_count: int = 0
    class_count: int = 0
    decision_points: list[dict[str, object]] = field(default_factory=list)

    @property
    def complexity_density(self) -> float:
        """Cyclomatic complexity per code line."""
        if self.code_lines == 0:
            return 0.0
        return self.cyclomatic_complexity / self.code_lines


class ComplexityCalculator(ast.NodeVisitor):
    """Walk a Python AST to compute cyclomatic complexity."""

    def __init__(self) -> None:
        self.decision_points: list[dict[str, object]] = []

    def calculate(self, tree: ast.AST) -> int:
        """Return cyclomatic complexity for the given AST."""
        self.decision_points = []
        self.visit(tree)
        return 1 + len(self.decision_points)

    def _add(self, node: ast.AST) -> None:
        self.decision_points.append(
            {"type": type(node).__name__, "line": getattr(node, "lineno", 0)}
        )

    def visit_If(self, node: ast.If) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_case(self, node: ast.match_case) -> None:
        self._add(node)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each 'and'/'or' operator adds a decision point.
        self._add(node)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        for generator in node.generators:
            if generator.ifs:
                self._add(node)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        for generator in node.generators:
            if generator.ifs:
                self._add(node)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        for generator in node.generators:
            if generator.ifs:
                self._add(node)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        for generator in node.generators:
            if generator.ifs:
                self._add(node)
        self.generic_visit(node)


def compute_file_metrics(file_ast, source: bytes, language: str = "python") -> CodeMetrics:
    """Compute all code metrics for a parsed file."""
    try:
        tree = ast.parse(source.decode("utf-8", errors="replace"))
    except SyntaxError:
        return _fallback_metrics(file_ast, source)

    calc = ComplexityCalculator()
    cc = calc.calculate(tree)

    # Count lines by type.
    lines = source.split(b"\n")
    total_lines = len(lines)
    code_lines = 0
    comment_lines = 0
    blank_lines = 0
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            blank_lines += 1
        elif stripped.startswith(b"#"):
            comment_lines += 1
        else:
            code_lines += 1

    function_count = len(file_ast.functions)
    class_count = len(file_ast.classes)

    return CodeMetrics(
        path=getattr(file_ast, "path", ""),
        relative_path=file_ast.relative_path,
        language=language,
        total_lines=total_lines,
        code_lines=code_lines,
        comment_lines=comment_lines,
        blank_lines=blank_lines,
        cyclomatic_complexity=cc,
        function_count=function_count,
        class_count=class_count,
        decision_points=calc.decision_points,
    )


def _fallback_metrics(file_ast, source: bytes) -> CodeMetrics:
    lines = source.split(b"\n")
    code_lines = comment_lines = blank_lines = 0
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            blank_lines += 1
        elif stripped.startswith(b"#"):
            comment_lines += 1
        else:
            code_lines += 1
    return CodeMetrics(
        path=getattr(file_ast, "path", ""),
        relative_path=file_ast.relative_path,
        language="python",
        total_lines=len(lines),
        code_lines=code_lines,
        comment_lines=comment_lines,
        blank_lines=blank_lines,
        cyclomatic_complexity=1,
        function_count=len(file_ast.functions),
        class_count=len(file_ast.classes),
    )
