"""Directory walking utilities with ignore rules for build folders and VCS."""

from __future__ import annotations

import os
from pathlib import Path

import pathspec


DEFAULT_IGNORE_PATTERNS = [
    "**/.git/**",
    "**/.pytest_cache/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "*.py[cod]",
    "**/.venv/**",
    "**/venv/**",
    "**/env/**",
    "**/ENV/**",
    "**/build/**",
    "**/dist/**",
    "**/coverage/**",
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
        patterns = DEFAULT_IGNORE_PATTERNS if ignore_patterns is None else ignore_patterns
        self._spec = pathspec.GitIgnoreSpec.from_lines(patterns)

    def _should_ignore(self, path: Path) -> bool:
        rel = path.relative_to(self.root)
        return self._spec.match_file(rel.as_posix())

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
