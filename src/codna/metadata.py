"""File metadata extraction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileMetadata:
    path: str
    relative_path: str
    language: str | None
    size: int
    line_count: int
    sha256: str
    is_source: bool


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def count_lines(file_path: Path) -> int:
    """Count the number of lines in a file."""
    try:
        with open(file_path, "rb") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return 0


def extract_metadata(file_path: Path, root: Path) -> FileMetadata:
    """Extract metadata for a single file relative to `root`."""
    rel = file_path.relative_to(root)
    size = file_path.stat().st_size
    return FileMetadata(
        path=str(file_path),
        relative_path=str(rel),
        language=None,
        size=size,
        line_count=count_lines(file_path),
        sha256=compute_sha256(file_path),
        is_source=False,
    )
