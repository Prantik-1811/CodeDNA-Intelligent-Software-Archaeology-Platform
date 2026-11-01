"""Directory walking utilities with ignore rules for build folders and VCS."""

from __future__ import annotations

import os
from pathlib import Path

import pathspec


DEFAULT_IGNORE_PATTERNS = [
    ".git/**",
    "node_modules/**",
    "__pycache__/**",
    "*.py[cod]",
    ".venv/**",
    "venv/**",
    "env/**",
    "ENV/**",
    "build/**",
    "dist/**",
    "target/**",
    ".eggs/**",
    "*.egg-info/**",
    "src/**/*.egg-info/**",
    ".idea/**",
    ".vscode/**",
]


class RepoWalker:
    """Walk a directory tree, skipping ignored paths."""

    def __init__(
        self,
        root: Path,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        self.root = root.resolve()
        patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS
        self._spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def _should_ignore(self, path: Path) -> bool:
        rel = path.relative_to(self.root)
        if self._spec.match_file(str(rel)):
            return True
        parts = rel.parts
        ignored_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "ENV",
            "build",
            "dist",
            "target",
            ".eggs",
        }
        return any(part in ignored_dirs for part in parts) or any(
            part.endswith(".egg-info") for part in parts
        )

    def walk_files(self) -> list[Path]:
        """Return all non-ignored files under root, sorted."""
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirpath_path = Path(dirpath)
            dirnames[:] = [
                d for d in dirnames if not self._should_ignore(dirpath_path / d)
            ]
            for filename in filenames:
                file_path = dirpath_path / filename
                if not self._should_ignore(file_path):
                    files.append(file_path)
        return sorted(files)
