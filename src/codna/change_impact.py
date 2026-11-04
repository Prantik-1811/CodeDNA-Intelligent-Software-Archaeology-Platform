"""Change impact analysis.

Signature feature of CodeDNA: given a modified function or file, identify
which components are affected, rank them by risk, and surface review targets.

Builds on:
- Week 3 dependency graph (call edges, import edges, inheritance)
- Week 5 git history (co-changing files, symbol change history)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ImpactedComponent:
    """A component affected by a proposed change."""

    id: str
    type: str  # "function", "class", "file", "test"
    label: str
    file_path: str
    line: int
    impact_score: float
    impact_reasons: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)  # edge details


@dataclass
class ChangeImpactReport:
    """Full change impact report."""

    target_type: str  # "function" or "file"
    target_id: str
    target_label: str
    target_file: str

    direct_callers: list[ImpactedComponent] = field(default_factory=list)
    affected_modules: list[ImpactedComponent] = field(default_factory=list)
    affected_tests: list[ImpactedComponent] = field(default_factory=list)
    co_changing_files: list[ImpactedComponent] = field(default_factory=list)
    review_components: list[ImpactedComponent] = field(default_factory=list)

    risk_score: float = 0.0
    risk_level: str = "low"  # low, medium, high, critical

    summary: dict = field(default_factory=dict)


class ChangeImpactAnalyzer:
    """Analyzes the impact of a proposed change to a function or file."""

    TEST_PATH_PATTERNS = ("test", "tests", "testing")
    TEST_FILE_PREFIX = "test_"
    TEST_FILE_SUFFIX = "_test.py"

    def __init__(
        self,
        graph,
        graph_data,
        git_history_data=None,
        file_metrics=None,
    ) -> None:
        self.graph = graph
        self.graph_data = graph_data
        self.git_history_data = git_history_data
        self.file_metrics = file_metrics or {}

    # ------------------------------------------------------------------
    # Target resolution
    # ------------------------------------------------------------------
    def _find_node_by_label(self, label: str, node_type: str = "function") -> Optional[str]:
        for nid, data in self.graph.graph.nodes(data=True):
            if data.get("type") == node_type and data.get("label") == label:
                return nid
        return None

    def _find_file_node(self, file_path: str) -> Optional[str]:
        for nid, data in self.graph.graph.nodes(data=True):
            if data.get("type") == "file" and data.get("file_path") == file_path:
                return nid
        return None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def analyze_function_change(
        self,
        function_label: str,
        file_path: str,
    ) -> ChangeImpactReport:
        """Analyze the impact of changing a specific function.

        Args:
            function_label: The function label (e.g. "authenticate_user" or
                "ClassName.method_name").
            file_path: The file containing the function.
        """
        report = ChangeImpactReport(
            target_type="function",
            target_id=function_label,
            target_label=function_label,
            target_file=file_path,
        )

        target_nid = self._find_node_by_label(function_label, "function")
        if target_nid is None:
            # Try scoped label "ClassName.method_name"
            target_nid = self._find_node_by_label(function_label, "function")
        report.target_id = target_nid or function_label

        # 1. Direct callers (functions that call the target)
        report.direct_callers = self._find_direct_callers(target_nid, file_path)

        # 2. Affected modules (transitive through imports/calls)
        report.affected_modules = self._find_affected_modules(
            target_nid, file_path, report.direct_callers
        )

        # 3. Affected tests
        report.affected_tests = self._find_affected_tests(
            target_nid, file_path, report.direct_callers
        )

        # 4. Co-changing files (from git history)
        report.co_changing_files = self._find_co_changing_files(file_path)

        # 5. Review components & risk scoring
        report.review_components, report.risk_score, report.risk_level = (
            self._compute_review_and_risk(
                report.direct_callers,
                report.affected_modules,
                report.affected_tests,
                report.co_changing_files,
                file_path,
            )
        )

        report.summary = self._build_summary(report)
        return report

    def analyze_file_change(self, file_path: str) -> ChangeImpactReport:
        """Analyze the impact of changing an entire file."""
        report = ChangeImpactReport(
            target_type="file",
            target_id=file_path,
            target_label=file_path,
            target_file=file_path,
        )

        file_nid = self._find_file_node(file_path)
        report.target_id = file_nid or file_path

        # All functions/classes in the file are potentially affected targets
        file_functions: list[ImpactedComponent] = []
        for nid, data in self.graph.graph.nodes(data=True):
            if data.get("type") == "function" and data.get("file_path") == file_path:
                file_functions.append(
                    ImpactedComponent(
                        id=nid,
                        type="function",
                        label=data.get("label", ""),
                        file_path=file_path,
                        line=data.get("line", 0),
                        impact_score=0.0,
                        impact_reasons=["defined in changed file"],
                        evidence=[],
                    )
                )

        # Direct callers of all functions in the file
        all_callers: list[ImpactedComponent] = []
        seen: set[str] = set()
        for fc in file_functions:
            callers = self._find_direct_callers(fc.id, file_path)
            for c in callers:
                if c.id not in seen:
                    seen.add(c.id)
                    all_callers.append(c)
        report.direct_callers = all_callers

        report.affected_modules = self._find_affected_modules(
            file_nid, file_path, report.direct_callers
        )
        report.affected_tests = self._find_affected_tests(
            file_nid, file_path, report.direct_callers
        )
        report.co_changing_files = self._find_co_changing_files(file_path)

        report.review_components, report.risk_score, report.risk_level = (
            self._compute_review_and_risk(
                report.direct_callers,
                report.affected_modules,
                report.affected_tests,
                report.co_changing_files,
                file_path,
            )
        )

        report.summary = self._build_summary(report)
        return report

    # ------------------------------------------------------------------
    # Direct callers
    # ------------------------------------------------------------------
    def _find_direct_callers(
        self, target_nid: Optional[str], file_path: str
    ) -> list[ImpactedComponent]:
        """Find functions that directly call the target."""
        callers: list[ImpactedComponent] = []
        if target_nid is None or target_nid not in self.graph.graph:
            return callers

        for src, dst, data in self.graph.graph.edges(data=True):
            if dst != target_nid:
                continue
            if data.get("type") != "calls":
                continue
            src_data = self.graph.graph.nodes[src]
            caller = ImpactedComponent(
                id=src,
                type=src_data.get("type", "function"),
                label=src_data.get("label", src),
                file_path=src_data.get("file_path", ""),
                line=src_data.get("line", 0),
                impact_score=0.0,
                impact_reasons=["directly calls target function"],
                evidence=[
                    {
                        "edge_type": data.get("type"),
                        "line": data.get("line", 0),
                        "metadata": data.get("metadata", {}),
                    }
                ],
            )
            callers.append(caller)

        callers.sort(key=lambda c: c.line)
        return callers

    # ------------------------------------------------------------------
    # Affected modules (transitive)
    # ------------------------------------------------------------------
    def _find_affected_modules(
        self,
        target_nid: Optional[str],
        file_path: str,
        direct_callers: list[ImpactedComponent],
    ) -> list[ImpactedComponent]:
        """Find modules transitively affected via import/call edges."""
        affected: list[ImpactedComponent] = []
        seen: set[str] = set()

        # Start from direct callers' files, propagate through import edges
        seed_files: set[str] = set()
        for c in direct_callers:
            if c.file_path and c.file_path != file_path:
                seed_files.add(c.file_path)

        # Also include the target's own file's importers
        target_file_nid = self._find_file_node(file_path)
        if target_file_nid:
            for src, dst, data in self.graph.graph.edges(data=True):
                if dst == target_file_nid and data.get("type") == "imports":
                    src_data = self.graph.graph.nodes[src]
                    if src_data.get("type") == "file":
                        seed_files.add(src_data.get("file_path", ""))

        # Propagate one more level (modules that import the seed modules)
        for seed_file in list(seed_files):
            seed_nid = self._find_file_node(seed_file)
            if seed_nid is None:
                continue
            for src, dst, data in self.graph.graph.edges(data=True):
                if dst == seed_nid and data.get("type") == "imports":
                    src_data = self.graph.graph.nodes[src]
                    imp_file = src_data.get("file_path", "")
                    if imp_file and imp_file not in seen and imp_file != file_path:
                        seen.add(imp_file)
                        affected.append(
                            ImpactedComponent(
                                id=src,
                                type="file",
                                label=imp_file,
                                file_path=imp_file,
                                line=1,
                                impact_score=0.0,
                                impact_reasons=["imports affected module"],
                                evidence=[
                                    {
                                        "edge_type": data.get("type"),
                                        "line": data.get("line", 0),
                                        "metadata": data.get("metadata", {}),
                                    }
                                ],
                            )
                        )

        affected.sort(key=lambda a: a.label)
        return affected

    # ------------------------------------------------------------------
    # Affected tests
    # ------------------------------------------------------------------
    def _find_affected_tests(
        self,
        target_nid: Optional[str],
        file_path: str,
        direct_callers: list[ImpactedComponent],
    ) -> list[ImpactedComponent]:
        """Find test files/functions that might be affected."""
        tests: list[ImpactedComponent] = []
        seen: set[str] = set()

        def _is_test_file(path: str) -> bool:
            lower = path.lower()
            if any(p in lower for p in self.TEST_PATH_PATTERNS):
                return True
            name = Path(path).name.lower()
            return name.startswith(self.TEST_FILE_PREFIX) or name.endswith(
                self.TEST_FILE_SUFFIX
            )

        # Check direct callers that are in test files
        for c in direct_callers:
            if _is_test_file(c.file_path) and c.id not in seen:
                seen.add(c.id)
                tests.append(
                    ImpactedComponent(
                        id=c.id,
                        type="test",
                        label=c.label,
                        file_path=c.file_path,
                        line=c.line,
                        impact_score=0.0,
                        impact_reasons=["test directly calls target function"],
                        evidence=c.evidence,
                    )
                )

        # Check test files that import the target's file or its callers' files
        relevant_files = {file_path}
        for c in direct_callers:
            if c.file_path:
                relevant_files.add(c.file_path)

        for nid, data in self.graph.graph.nodes(data=True):
            if data.get("type") != "file":
                continue
            fpath = data.get("file_path", "")
            if not _is_test_file(fpath) or nid in seen:
                continue
            # Does this test import any relevant file?
            for src, dst, edge_data in self.graph.graph.edges(data=True):
                if src != nid:
                    continue
                if edge_data.get("type") != "imports":
                    continue
                dst_data = self.graph.graph.nodes[dst]
                if dst_data.get("file_path") in relevant_files:
                    seen.add(nid)
                    tests.append(
                        ImpactedComponent(
                            id=nid,
                            type="test",
                            label=fpath,
                            file_path=fpath,
                            line=data.get("line", 1),
                            impact_score=0.0,
                            impact_reasons=["imports affected file"],
                            evidence=[
                                {
                                    "edge_type": edge_data.get("type"),
                                    "line": edge_data.get("line", 0),
                                    "metadata": edge_data.get("metadata", {}),
                                }
                            ],
                        )
                    )
                    break

        tests.sort(key=lambda t: t.file_path)
        return tests

    # ------------------------------------------------------------------
    # Co-changing files
    # ------------------------------------------------------------------
    def _find_co_changing_files(self, file_path: str) -> list[ImpactedComponent]:
        """Find files that historically change alongside the target file."""
        co_changing: list[ImpactedComponent] = []
        if self.git_history_data is None:
            return co_changing

        seen: set[str] = set()
        for cc in self.git_history_data.co_changes:
            other = None
            if cc.file_a == file_path:
                other = cc.file_b
            elif cc.file_b == file_path:
                other = cc.file_a
            if other is None or other in seen:
                continue
            seen.add(other)

            # Compute a co-change strength score
            strength = min(cc.change_count / 10.0, 1.0)

            co_changing.append(
                ImpactedComponent(
                    id=other,
                    type="file",
                    label=other,
                    file_path=other,
                    line=1,
                    impact_score=strength,
                    impact_reasons=[
                        f"co-changed {cc.change_count} time(s) with target"
                    ],
                    evidence=[
                        {
                            "change_count": cc.change_count,
                            "commits": cc.commits[:5],
                        }
                    ],
                )
            )

        co_changing.sort(key=lambda c: c.impact_score, reverse=True)
        return co_changing

    # ------------------------------------------------------------------
    # Review components & risk scoring
    # ------------------------------------------------------------------
    def _compute_review_and_risk(
        self,
        direct_callers: list[ImpactedComponent],
        affected_modules: list[ImpactedComponent],
        affected_tests: list[ImpactedComponent],
        co_changing_files: list[ImpactedComponent],
        target_file: str,
    ) -> tuple[list[ImpactedComponent], float, str]:
        """Compute ranked review components and overall risk score."""
        review: list[ImpactedComponent] = []

        # Direct callers are top review priority
        for c in direct_callers:
            score = 10.0
            if c.file_path == target_file:
                score += 2.0  # same file = tighter coupling
            c.impact_score = score
            c.impact_reasons.append("direct caller - review required")
            review.append(c)

        # Affected tests are high priority (breaking tests is bad)
        for t in affected_tests:
            score = 8.0
            t.impact_score = score
            t.impact_reasons.append("test may break - review required")
            review.append(t)

        # Affected modules
        for m in affected_modules:
            score = 5.0 + min(len(m.impact_reasons), 3)
            m.impact_score = score
            m.impact_reasons.append("transitive dependency - review")
            review.append(m)

        # Co-changing files
        for cc in co_changing_files:
            cc.impact_score = cc.impact_score * 6.0
            cc.impact_reasons.append("historically co-changes - consider reviewing")
            review.append(cc)

        # Sort by impact score desc
        review.sort(key=lambda r: r.impact_score, reverse=True)

        # Overall risk score
        risk = 0.0
        risk += min(len(direct_callers) * 3.0, 15.0)  # caller count
        risk += min(len(affected_tests) * 4.0, 15.0)  # test exposure
        risk += min(len(affected_modules) * 2.0, 10.0)  # module exposure
        risk += min(len(co_changing_files) * 2.0, 10.0)  # co-change exposure

        # Factor in target file complexity if available
        metrics = self.file_metrics.get(target_file)
        if metrics:
            risk += min(metrics.cyclomatic_complexity / 5.0, 10.0)

        # Cap at 100
        risk = min(risk, 100.0)

        if risk >= 70:
            level = "critical"
        elif risk >= 45:
            level = "high"
        elif risk >= 20:
            level = "medium"
        else:
            level = "low"

        return review, risk, level

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _build_summary(self, report: ChangeImpactReport) -> dict:
        return {
            "target": f"{report.target_type}:{report.target_label}",
            "target_file": report.target_file,
            "direct_caller_count": len(report.direct_callers),
            "affected_module_count": len(report.affected_modules),
            "affected_test_count": len(report.affected_tests),
            "co_changing_file_count": len(report.co_changing_files),
            "review_component_count": len(report.review_components),
            "risk_score": round(report.risk_score, 1),
            "risk_level": report.risk_level,
            "top_review_targets": [
                {
                    "label": r.label,
                    "type": r.type,
                    "file_path": r.file_path,
                    "impact_score": round(r.impact_score, 1),
                }
                for r in report.review_components[:5]
            ],
        }
