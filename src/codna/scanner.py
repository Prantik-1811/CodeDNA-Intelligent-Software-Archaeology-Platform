"""Repository scanner orchestration and JSON summary generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .git_utils import get_git_info
from .language import detect_language, group_files_by_language, is_source_file
from .metadata import extract_metadata
from .walker import RepoWalker


@dataclass
class ScanResult:
    repository: dict[str, Any]
    files: list[dict[str, Any]]
    summary: dict[str, Any]


class RepositoryScanner:
    """Scan a GitHub URL or local directory and produce structured JSON metadata."""

    def __init__(self, root: Path, repo_url: str | None = None) -> None:
        self.root = root.resolve()
        self.repo_url = repo_url

    def scan(self) -> ScanResult:
        walker = RepoWalker(self.root)
        files = walker.walk_files()

        file_records: list[dict[str, Any]] = []
        language_counts: dict[str, int] = {}
        source_count = 0
        total_size = 0
        total_lines = 0

        for file_path in files:
            lang = detect_language(file_path)
            meta = extract_metadata(file_path, self.root)
            meta.language = lang.name if lang else None
            meta.is_source = is_source_file(file_path)

            record = asdict(meta)
            file_records.append(record)

            if lang:
                language_counts[lang.name] = language_counts.get(lang.name, 0) + 1
            if meta.is_source:
                source_count += 1
            total_size += meta.size
            total_lines += meta.line_count

        grouped = group_files_by_language(files)

        git_info = get_git_info(self.root)

        repository = {
            "repo_url": self.repo_url or git_info.repo_url,
            "local_path": str(git_info.local_path),
            "commit_hash": git_info.commit_hash,
            "branch": git_info.branch,
        }

        summary = {
            "total_files": len(files),
            "source_files": source_count,
            "total_size_bytes": total_size,
            "total_lines": total_lines,
            "languages": language_counts,
            "files_by_language": {
                lang: [str(p.relative_to(self.root)) for p in paths]
                for lang, paths in grouped.items()
            },
        }

        return ScanResult(
            repository=repository,
            files=file_records,
            summary=summary,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self.scan()), indent=2, sort_keys=True)

    def save_json(self, output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.write_text(self.to_json(), encoding="utf-8")
