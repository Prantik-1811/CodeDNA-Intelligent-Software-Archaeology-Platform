"""Dependency graph engine.

Builds file-level and function-level dependency graphs from parsed ASTs,
maps class inheritance, detects circular imports, and computes in/out
degrees using NetworkX.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx

from .ast_parser import (
    Class,
    FileAST,
    Function,
    Import,
    PythonASTExtractor,
    TreeSitterParser,
    parse_source,
)
from .graph_models import DependencyGraphData, GraphEdge, GraphNode


class DependencyGraph:
    """Builds and analyzes a directed dependency graph."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self._node_id_counter = 0
        self._parser = TreeSitterParser()

    # ------------------------------------------------------------------
    # Node helpers
    # ------------------------------------------------------------------
    def _next_id(self) -> str:
        self._node_id_counter += 1
        return f"n{self._node_id_counter}"

    def _node_key(self, node_type: str, file_path: str, name: str) -> str:
        return f"{node_type}:{file_path}::{name}"

    def add_file_node(self, file_ast: FileAST) -> None:
        nid = self._node_key("file", file_ast.relative_path, file_ast.relative_path)
        self.graph.add_node(
            nid,
            type="file",
            label=file_ast.relative_path,
            file_path=file_ast.relative_path,
            line=1,
            language=file_ast.language,
            metadata={"function_count": len(file_ast.functions),
                      "class_count": len(file_ast.classes),
                      "import_count": len(file_ast.imports)},
        )

    def add_function_node(self, file_ast: FileAST, func: Function) -> None:
        scope = f"{func.class_name}." if func.class_name else ""
        label = f"{scope}{func.name}"
        nid = self._node_key("function", file_ast.relative_path, label)
        self.graph.add_node(
            nid,
            type="function",
            label=label,
            file_path=file_ast.relative_path,
            line=func.start_line,
            language=file_ast.language,
            metadata={
                "is_method": func.is_method,
                "class_name": func.class_name,
                "return_type": func.return_type,
                "parameter_count": len(func.parameters),
                "decorators": func.decorators,
                "end_line": func.end_line,
            },
        )

    def add_class_node(self, file_ast: FileAST, cls: Class) -> None:
        nid = self._node_key("class", file_ast.relative_path, cls.name)
        self.graph.add_node(
            nid,
            type="class",
            label=cls.name,
            file_path=file_ast.relative_path,
            line=cls.start_line,
            language=file_ast.language,
            metadata={
                "base_classes": cls.base_classes,
                "method_count": len(cls.methods),
                "decorators": cls.decorators,
                "end_line": cls.end_line,
            },
        )

    # ------------------------------------------------------------------
    # Edge helpers
    # ------------------------------------------------------------------
    def add_edge(self, source: str, target: str, edge_type: str, line: int = 0,
                 metadata: dict[str, Any] | None = None) -> None:
        self.graph.add_edge(
            source, target,
            type=edge_type,
            line=line,
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------
    # Build from parsed files
    # ------------------------------------------------------------------
    def build_from_files(
        self,
        file_asts: list[FileAST],
        file_paths: list[Path],
        root: Path,
        skip_call_edges: bool = False,
    ) -> DependencyGraphData:
        """Build the full dependency graph from parsed file ASTs."""
        # Index files by module path for import resolution
        module_index = self._build_module_index(file_paths, root)

        # Add all nodes
        for file_ast in file_asts:
            self.add_file_node(file_ast)
            file_nid = self._node_key("file", file_ast.relative_path,
                                      file_ast.relative_path)
            for func in file_ast.functions:
                self.add_function_node(file_ast, func)
                func_label = f"{func.class_name + '.' if func.class_name else ''}{func.name}"
                func_nid = self._node_key("function", file_ast.relative_path,
                                          func_label)
                self.add_edge(file_nid, func_nid, "contains", func.start_line)
            for cls in file_ast.classes:
                self.add_class_node(file_ast, cls)
                cls_nid = self._node_key("class", file_ast.relative_path, cls.name)
                self.add_edge(file_nid, cls_nid, "contains", cls.start_line)
                for method in cls.methods:
                    self.add_function_node(file_ast, method)
                    method_label = f"{cls.name}.{method.name}"
                    method_nid = self._node_key("function", file_ast.relative_path,
                                                method_label)
                    self.add_edge(cls_nid, method_nid, "contains", method.start_line)

        # Add import edges (file-level)
        for file_ast in file_asts:
            self._add_import_edges(file_ast, module_index)

        # Add call edges (function-level) - skipped on platforms where
        # tree-sitter node access crashes (e.g. Windows + Python 3.14)
        if not skip_call_edges:
            for file_ast in file_asts:
                self._add_call_edges(file_ast)

        # Add inheritance edges (class-level)
        for file_ast in file_asts:
            self._add_inheritance_edges(file_ast)

        return self._to_data()

    # ------------------------------------------------------------------
    # Module resolution
    # ------------------------------------------------------------------
    def _build_module_index(self, file_paths: list[Path], root: Path) -> dict[str, str]:
        """Map dotted module paths to relative file paths."""
        index: dict[str, str] = {}
        for path in file_paths:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            parts = list(rel.parts)
            # Drop extension
            if parts:
                parts[-1] = Path(parts[-1]).stem
            # Skip __init__
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                module = ".".join(parts)
                index[module] = str(rel)
                # Also index without leading package segments for short-name lookup
        return index

    def _resolve_import(self, imp: Import, current_file: str,
                        module_index: dict[str, str]) -> str | None:
        """Resolve an import to a target file path, or None."""
        module = imp.module
        if not module:
            return None

        # Relative imports: .foo, ..foo, .foo.bar
        if module.startswith("."):
            level = 0
            while module.startswith("."):
                level += 1
                module = module[1:]
            current_parts = Path(current_file).parts[:-1]  # drop file name
            if level <= len(current_parts):
                base = current_parts[:-level] if level < len(current_parts) else current_parts[:1]
                if module:
                    base = list(base) + module.split(".")
                resolved = ".".join(base)
            else:
                resolved = module
            return module_index.get(resolved)

        # Absolute imports
        # Try exact match, then try shortening from the end
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in module_index:
                return module_index[candidate]
        return None

    # ------------------------------------------------------------------
    # Import edges
    # ------------------------------------------------------------------
    def _add_import_edges(self, file_ast: FileAST,
                          module_index: dict[str, str]) -> None:
        source_nid = self._node_key("file", file_ast.relative_path,
                                    file_ast.relative_path)
        for imp in file_ast.imports:
            target_file = self._resolve_import(imp, file_ast.relative_path,
                                               module_index)
            if target_file is None:
                continue
            target_nid = self._node_key("file", target_file, target_file)
            self.add_edge(
                source_nid, target_nid, "imports", imp.line,
                metadata={"module": imp.module, "names": imp.names,
                          "is_from": imp.is_from},
            )
            # Also connect imported symbols to the source file's functions if resolvable
            for name in imp.names:
                target_func_nid = self._find_function_nid(target_file, name)
                if target_func_nid:
                    self.add_edge(
                        source_nid, target_func_nid, "imports", imp.line,
                        metadata={"module": imp.module, "symbol": name},
                    )

    def _find_function_nid(self, file_path: str, name: str) -> str | None:
        for nid, data in self.graph.nodes(data=True):
            if (data.get("type") == "function"
                    and data.get("file_path") == file_path
                    and data.get("label") == name):
                return nid
        return None

    # ------------------------------------------------------------------
    # Call edges (function-level)
    # ------------------------------------------------------------------
    def _add_call_edges(self, file_ast: FileAST) -> None:
        # Re-parse source to walk call expressions within functions
        source = Path(file_ast.path).read_bytes() if file_ast.path else b""
        if not source:
            # Try to locate file relative to cwd
            p = Path(file_ast.relative_path)
            if p.exists():
                source = p.read_bytes()
        if not source:
            return

        tree = self._parser.parse(source, "python")
        if tree is None:
            return

        root = tree.root_node

        # Map function definition nodes to their labels
        func_nodes: list[tuple[Any, str]] = []  # (node, label)
        self._collect_functions(root, file_ast.relative_path, func_nodes)

        for func_node, label in func_nodes:
            caller_nid = self._node_key("function", file_ast.relative_path, label)
            if caller_nid not in self.graph:
                continue
            calls = self._extract_calls(func_node, source)
            for callee_name, call_line in calls:
                target_nid = self._resolve_call_target(callee_name, file_ast,
                                                       caller_nid)
                if target_nid:
                    self.add_edge(
                        caller_nid, target_nid, "calls", call_line,
                        metadata={"callee": callee_name},
                    )

    def _collect_functions(self, node, file_path: str,
                           out: list[tuple[Any, str]]) -> None:
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                name_node = next((c for c in node.children
                                  if c.type == "identifier"), None)
            name = name_node.text.decode("utf-8", errors="replace") if name_node else "?"
            out.append((node, name))
        for child in node.children:
            self._collect_functions(child, file_path, out)

    def _extract_calls(self, func_node, source: bytes) -> list[tuple[str, int]]:
        calls: list[tuple[str, int]] = []
        stack = [func_node]
        seen: set[tuple[int, int, str]] = set()
        while stack:
            n = stack.pop()
            key = (n.start_byte, n.end_byte, n.type)
            if key in seen:
                continue
            seen.add(key)
            if n.type == "call":
                func_child = n.child_by_field_name("function")
                if func_child is None:
                    for c in n.children:
                        if c.type not in ("arguments", "(", ")", "argument_list"):
                            func_child = c
                            break
                callee = self._callee_name(func_child, source) if func_child else "?"
                calls.append((callee, n.start_point.row + 1))
            else:
                stack.extend(n.children)
        return calls

    def _callee_name(self, node, source: bytes, depth: int = 0) -> str:
        if node is None or depth > 10:
            return "?"
        if node.type == "identifier":
            return node.text.decode("utf-8", errors="replace")
        if node.type == "attribute":
            attr = node.child_by_field_name("attr")
            if attr is not None:
                return attr.text.decode("utf-8", errors="replace")
            return node.text.decode("utf-8", errors="replace")
        if node.type == "call":
            return self._callee_name(
                node.child_by_field_name("function"), source, depth + 1
            )
        return node.text.decode("utf-8", errors="replace")

    def _resolve_call_target(self, callee_name: str, file_ast: FileAST,
                             caller_nid: str) -> str | None:
        """Resolve a call to a target function node id."""
        # Same file functions first
        for func in file_ast.functions:
            if func.name == callee_name:
                scope = f"{func.class_name}." if func.class_name else ""
                label = f"{scope}{func.name}"
                return self._node_key("function", file_ast.relative_path, label)
        # Check methods in classes
        for cls in file_ast.classes:
            for method in cls.methods:
                if method.name == callee_name:
                    label = f"{cls.name}.{method.name}"
                    return self._node_key("function", file_ast.relative_path, label)
        return None

    # ------------------------------------------------------------------
    # Inheritance edges
    # ------------------------------------------------------------------
    def _add_inheritance_edges(self, file_ast: FileAST) -> None:
        for cls in file_ast.classes:
            cls_nid = self._node_key("class", file_ast.relative_path, cls.name)
            for base in cls.base_classes:
                # Try to find the base class in the same file or imported
                target_nid = self._find_class_nid(base, file_ast)
                if target_nid is None:
                    # Create an external class node reference
                    target_nid = self._node_key("class", "external", base)
                    if target_nid not in self.graph:
                        self.graph.add_node(
                            target_nid, type="class", label=base,
                            file_path="external", line=0,
                            language=None,
                            metadata={"external": True},
                        )
                self.add_edge(cls_nid, target_nid, "inherits", cls.start_line,
                              metadata={"base": base})

    def _find_class_nid(self, name: str, file_ast: FileAST) -> str | None:
        for cls in file_ast.classes:
            if cls.name == name:
                return self._node_key("class", file_ast.relative_path, cls.name)
        # Search graph for class with this label in any file
        for nid, data in self.graph.nodes(data=True):
            if data.get("type") == "class" and data.get("label") == name:
                return nid
        return None

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    def find_cycles(self) -> list[list[str]]:
        """Detect circular import cycles among file nodes."""
        cycles: list[list[str]] = []
        try:
            for cycle in nx.simple_cycles(self.graph):
                # Only keep cycles that are import edges between files
                if all(self.graph.nodes[n].get("type") == "file" for n in cycle):
                    cycles.append(list(cycle))
        except Exception:
            pass
        return cycles

    def degrees(self) -> dict[str, dict[str, int]]:
        """Return in-degree and out-degree for every node."""
        result: dict[str, dict[str, int]] = {}
        for nid in self.graph.nodes:
            result[nid] = {
                "in_degree": self.graph.in_degree(nid),
                "out_degree": self.graph.out_degree(nid),
            }
        return result

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _to_data(self) -> DependencyGraphData:
        nodes: list[GraphNode] = []
        for nid, data in self.graph.nodes(data=True):
            nodes.append(GraphNode(
                id=nid,
                type=data.get("type", "unknown"),
                label=data.get("label", nid),
                file_path=data.get("file_path", ""),
                line=data.get("line", 0),
                language=data.get("language"),
                metadata=data.get("metadata", {}),
            ))

        edges: list[GraphEdge] = []
        for src, dst, data in self.graph.edges(data=True):
            edges.append(GraphEdge(
                source=src,
                target=dst,
                type=data.get("type", "unknown"),
                line=data.get("line", 0),
                metadata=data.get("metadata", {}),
            ))

        cycles = self.find_cycles()
        deg = self.degrees()

        metrics = {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "file_count": sum(1 for n in nodes if n.type == "file"),
            "function_count": sum(1 for n in nodes if n.type == "function"),
            "class_count": sum(1 for n in nodes if n.type == "class"),
            "cycle_count": len(cycles),
            "max_in_degree": max((d["in_degree"] for d in deg.values()),
                                 default=0),
            "max_out_degree": max((d["out_degree"] for d in deg.values()),
                                  default=0),
        }

        return DependencyGraphData(
            nodes=nodes,
            edges=edges,
            cycles=cycles,
            metrics=metrics,
        )
