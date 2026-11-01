"""Language detection based on file extensions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Language:
    name: str
    extensions: tuple[str, ...]
    is_source: bool


LANGUAGE_MAP: dict[str, Language] = {
    "python": Language("python", (".py", ".pyi", ".pyw"), True),
    "javascript": Language("javascript", (".js", ".jsx", ".mjs", ".cjs"), True),
    "typescript": Language("typescript", (".ts", ".tsx", ".mts", ".cts"), True),
    "java": Language("java", (".java",), True),
    "c": Language("c", (".c", ".h"), True),
    "cpp": Language("cpp", (".cpp", ".cc", ".cxx", ".hpp", ".hxx"), True),
    "csharp": Language("csharp", (".cs",), True),
    "go": Language("go", (".go",), True),
    "rust": Language("rust", (".rs",), True),
    "ruby": Language("ruby", (".rb", ".rake", ".gemspec"), True),
    "php": Language("php", (".php", ".phtml"), True),
    "swift": Language("swift", (".swift",), True),
    "kotlin": Language("kotlin", (".kt", ".kts"), True),
    "scala": Language("scala", (".scala", ".sc"), True),
    "html": Language("html", (".html", ".htm"), False),
    "css": Language("css", (".css", ".scss", ".sass", ".less"), False),
    "json": Language("json", (".json",), False),
    "yaml": Language("yaml", (".yaml", ".yml"), False),
    "toml": Language("toml", (".toml",), False),
    "xml": Language("xml", (".xml",), False),
    "markdown": Language("markdown", (".md", ".markdown", ".rst"), False),
    "sql": Language("sql", (".sql",), True),
    "shell": Language("shell", (".sh", ".bash", ".zsh", ".fish"), True),
    "dockerfile": Language("dockerfile", (".dockerfile", "Dockerfile"), True),
    "makefile": Language("makefile", ("Makefile", "makefile", "GNUmakefile"), True),
    "cmake": Language("cmake", (".cmake", "CMakeLists.txt"), True),
}


def detect_language(file_path: Path) -> Language | None:
    """Detect the programming language of a file from its name/extension."""
    name = file_path.name
    suffix = file_path.suffix.lower()

    # Exact filename matches first (Dockerfile, Makefile, CMakeLists.txt)
    for lang in LANGUAGE_MAP.values():
        if name.lower() in (e.lower() for e in lang.extensions if not e.startswith(".")):
            return lang

    # Extension-based matches
    for lang in LANGUAGE_MAP.values():
        if suffix in lang.extensions:
            return lang

    return None


def is_source_file(file_path: Path) -> bool:
    """Return True if the file is a recognized source code file."""
    lang = detect_language(file_path)
    return lang is not None and lang.is_source


def group_files_by_language(files: list[Path]) -> dict[str, list[Path]]:
    """Group files by detected language. Unknown languages go under 'unknown'."""
    grouped: dict[str, list[Path]] = {}
    for file_path in files:
        lang = detect_language(file_path)
        key = lang.name if lang else "unknown"
        grouped.setdefault(key, []).append(file_path)
    return grouped
