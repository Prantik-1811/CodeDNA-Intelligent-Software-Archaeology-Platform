"""AST parsing engine built on Tree-sitter.

Converts source files into structured representations: functions, classes,
methods, parameters, return types, imports, exports, and source locations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tree_sitter import Language, Parser, Tree

try:  # pragma: no cover - optional grammar, loaded per language
    import tree_sitter_python as _tspython
except Exception:  # pragma: no cover
    _tspython = None

# Module-level cached Language (created once, reused for all parsers).
_cached_language: Optional[Language] = None


def _get_cached_language() -> Optional[Language]:
    """Create and cache a single Tree-sitter Language for Python.

    Creating the Language is the expensive step; a fresh Parser is created
    per parse() call to avoid resource issues on some platforms.
    """
    global _cached_language
    if _cached_language is not None:
        return _cached_language
    if _tspython is None:
        return None
    try:
        _cached_language = Language(_tspython.language())
    except Exception:
        return None
    return _cached_language


@dataclass
class Parameter:
    name: str
    type: Optional[str] = None
    default: Optional[str] = None


@dataclass
class Function:
    name: str
    parameters: list[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    start_column: int = 0
    end_column: int = 0
    is_method: bool = False
    class_name: Optional[str] = None
    decorators: list[str] = field(default_factory=list)


@dataclass
class Class:
    name: str
    base_classes: list[str] = field(default_factory=list)
    methods: list[Function] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    start_column: int = 0
    end_column: int = 0


@dataclass
class Import:
    module: str
    names: list[str] = field(default_factory=list)
    line: int = 0
    is_from: bool = False


@dataclass
class FileAST:
    path: str
    relative_path: str
    language: str
    functions: list[Function] = field(default_factory=list)
    classes: list[Class] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


def _point_line(point) -> int:
    """Tree-sitter points are 0-indexed rows; convert to 1-indexed lines."""
    return point.row + 1


def _point_column(point) -> int:
    return point.column


def _node_text(node, source: bytes) -> str:
    return node.text.decode("utf-8", errors="replace")


class TreeSitterParser:
    """Tree-sitter backed parser for supported languages."""

    LANGUAGE_MODULES = {
        "python": _tspython,
    }

    def __init__(self) -> None:
        pass

    def _ensure_language(self, language: str) -> Optional[Language]:
        if language != "python":
            return None
        return _get_cached_language()

    def parse(self, source: bytes, language: str) -> Optional[Tree]:
        lang = self._ensure_language(language)
        if lang is None:
            return None
        # Create a fresh Parser from the cached Language on each call.
        parser = Parser(lang)
        return parser.parse(source)


class PythonASTExtractor:
    """Extract structured code information from a parsed Python tree."""

    def __init__(self, parser: TreeSitterParser, source: bytes, tree: Tree) -> None:
        self.parser = parser
        self.source = source
        self.tree = tree
        self.file_ast: Optional[FileAST] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def extract(self, relative_path: str) -> FileAST:
        root = self.tree.root_node
        file_ast = FileAST(
            path="",
            relative_path=relative_path,
            language="python",
        )

        # Process top-level nodes; functions/classes nested inside classes
        # are attached as methods.
        for child in root.children:
            if child.type == "function_definition":
                func = self._extract_function(child, in_class=False)
                file_ast.functions.append(func)
                file_ast.exports.append(func.name)
            elif child.type == "class_definition":
                cls = self._extract_class(child)
                file_ast.classes.append(cls)
                file_ast.exports.append(cls.name)
            elif child.type in ("import_statement", "import_from_statement"):
                imp = self._extract_import(child)
                if imp is not None:
                    file_ast.imports.append(imp)
            elif child.type == "assignment":
                self._collect_exports(child, file_ast)

        self.file_ast = file_ast
        return file_ast

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _field_child(self, node, field_name: str):
        return node.child_by_field_name(field_name)

    def _children_by_type(self, node, type_name: str):
        return [c for c in node.children if c.type == type_name]

    def _identifier_text(self, node) -> Optional[str]:
        if node is None:
            return None
        id_node = node.child_by_field_name("name")
        if id_node is None:
            for child in node.children:
                if child.type == "identifier":
                    id_node = child
                    break
        if id_node is None:
            return None
        return _node_text(id_node, self.source)

    def _range(self, node) -> tuple[int, int, int, int]:
        return (
            _point_line(node.start_point),
            _point_line(node.end_point),
            _point_column(node.start_point),
            _point_column(node.end_point),
        )

    # ------------------------------------------------------------------
    # Decorators
    # ------------------------------------------------------------------
    def _extract_decorators(self, node) -> list[str]:
        decorators: list[str] = []
        for child in self._children_by_type(node, "decorator"):
            decorators.append(_node_text(child, self.source).strip())
        return decorators

    # ------------------------------------------------------------------
    # Functions / methods
    # ------------------------------------------------------------------
    def _extract_function(self, node, in_class: bool, class_name: Optional[str] = None) -> Function:
        start_line, end_line, start_column, end_column = self._range(node)
        name = self._identifier_text(node) or "anonymous"

        func = Function(
            name=name,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
            is_method=in_class,
            class_name=class_name,
            decorators=self._extract_decorators(node),
        )

        params_node = self._field_child(node, "parameters")
        if params_node is not None:
            func.parameters = self._extract_parameters(params_node)

        return_type_node = self._field_child(node, "return_type")
        if return_type_node is not None:
            func.return_type = _node_text(return_type_node, self.source).strip().lstrip("->").strip()

        return func

    def _extract_parameters(self, node) -> list[Parameter]:
        params: list[Parameter] = []
        for child in node.children:
            if child.type in ("default_parameter", "typed_parameter", "typed_default_parameter"):
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    name_node = next(
                        (c for c in child.children if c.type == "identifier"),
                        None,
                    )
                type_node = child.child_by_field_name("type")
                default_node = child.child_by_field_name("value")
                params.append(
                    Parameter(
                        name=_node_text(name_node, self.source) if name_node else "?",
                        type=_node_text(type_node, self.source).strip() if type_node else None,
                        default=_node_text(default_node, self.source).strip() if default_node else None,
                    )
                )
            elif child.type == "identifier":
                params.append(Parameter(name=_node_text(child, self.source)))
        return params

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------
    def _extract_class(self, node) -> Class:
        start_line, end_line, start_column, end_column = self._range(node)
        name = self._identifier_text(node) or "anonymous"

        cls = Class(
            name=name,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
            decorators=self._extract_decorators(node),
        )

        # Base classes
        superclasses_node = self._field_child(node, "superclasses")
        if superclasses_node is not None:
            for child in superclasses_node.children:
                if child.type in ("identifier", "dotted_name", "attribute"):
                    cls.base_classes.append(_node_text(child, self.source))

        # Methods
        block_node = self._field_child(node, "body")
        if block_node is None:
            block_node = self._field_child(node, "block")
        if block_node is not None:
            for child in block_node.children:
                if child.type == "function_definition":
                    method = self._extract_function(child, in_class=True, class_name=name)
                    cls.methods.append(method)
                    cls.exports if hasattr(cls, "exports") else None

        return cls

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------
    def _extract_import(self, node) -> Optional[Import]:
        if node.type == "import_statement":
            # import a.b, c.d as e
            names = []
            module_parts = []
            for child in node.children:
                if child.type == "dotted_name":
                    module_parts.append(_node_text(child, self.source))
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        names.append(_node_text(name_node, self.source))
            return Import(
                module=", ".join(module_parts),
                names=names,
                line=_point_line(node.start_point),
                is_from=False,
            )

        if node.type == "import_from_statement":
            # from x.y import z, w
            module_node = node.child_by_field_name("module_name")
            module = _node_text(module_node, self.source) if module_node else ""
            names: list[str] = []
            import_list = node.child_by_field_name("import_list")  # may be None
            if import_list is None:
                for child in node.children:
                    if child.type == "import_list":
                        import_list = child
                        break
            if import_list is not None:
                for child in import_list.children:
                    if child.type in ("identifier", "aliased_import", "dotted_name"):
                        if child.type == "aliased_import":
                            orig = child.child_by_field_name("name")
                            names.append(_node_text(orig, self.source) if orig else _node_text(child, self.source))
                        else:
                            names.append(_node_text(child, self.source))
            return Import(
                module=module,
                names=names,
                line=_point_line(node.start_point),
                is_from=True,
            )
        return None

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------
    def _collect_exports(self, node, file_ast: FileAST) -> None:
        # __all__ = [...]
        target = node.child_by_field_name("left")
        value = node.child_by_field_name("right")
        if target is None or value is None:
            return
        target_text = _node_text(target, self.source).strip()
        if target_text == "__all__":
            if value.type == "list":
                for child in value.children:
                    if child.type == "string":
                        file_ast.exports.append(
                            _node_text(child, self.source).strip("'\"")
                        )


def parse_source(source: bytes, relative_path: str, language: str = "python") -> Optional[FileAST]:
    """Parse a single source file and return its structured AST representation."""
    parser = TreeSitterParser()
    tree = parser.parse(source, language)
    if tree is None:
        return None
    if language == "python":
        extractor = PythonASTExtractor(parser, source, tree)
        file_ast = extractor.extract(relative_path)
        file_ast.path = relative_path
        return file_ast
    return None


def parse_file(file_path: Path, root: Path, language: str = "python") -> Optional[FileAST]:
    """Read and parse a file from disk."""
    try:
        source = file_path.read_bytes()
    except OSError:
        return None
    relative_path = str(file_path.relative_to(root))
    return parse_source(source, relative_path, language)
