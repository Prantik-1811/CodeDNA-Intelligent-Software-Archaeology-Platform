"""Git history intelligence.

Analyzes repository evolution through Git commit history:
- Commit histories
- Frequently modified files
- Contributors
- Co-changing files
- Files repeatedly modified together
- Changes to functions and classes across commits
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from git import Commit, Repo

try:
    import ast as _ast
except Exception:  # pragma: no cover
    _ast = None


@dataclass
class CommitInfo:
    """Information about a single commit."""

    hash: str
    short_hash: str
    author_name: str
    author_email: str
    author_date: datetime
    committer_name: str
    committer_email: str
    committer_date: datetime
    message: str
    parents: list[str]
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


@dataclass
class FileHistory:
    """History of changes for a single file."""

    path: str
    change_count: int
    first_commit: Optional[str]
    last_commit: Optional[str]
    contributors: list[str] = field(default_factory=list)
    total_insertions: int = 0
    total_deletions: int = 0


@dataclass
class ContributorInfo:
    """Information about a contributor."""

    name: str
    email: str
    commit_count: int
    files_changed: list[str] = field(default_factory=list)
    first_commit: Optional[str] = None
    last_commit: Optional[str] = None


@dataclass
class CoChangeInfo:
    """Information about two files that change together."""

    file_a: str
    file_b: str
    change_count: int
    commits: list[str] = field(default_factory=list)


@dataclass
class SymbolChange:
    """A change to a function or class across commits."""

    symbol_name: str
    symbol_type: str  # "function" or "class"
    file_path: str
    commit_hash: str
    commit_date: datetime
    author: str
    change_type: str  # "added", "modified", "deleted"


@dataclass
class GitHistoryData:
    """Complete Git history analysis data."""

    commits: list[CommitInfo] = field(default_factory=list)
    file_histories: dict[str, FileHistory] = field(default_factory=dict)
    contributors: dict[str, ContributorInfo] = field(default_factory=dict)
    co_changes: list[CoChangeInfo] = field(default_factory=list)
    symbol_changes: list[SymbolChange] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class GitHistoryAnalyzer:
    """Analyzes Git repository history."""

    def __init__(self, repo: Repo) -> None:
        self.repo = repo

    # ------------------------------------------------------------------
    # Commit history
    # ------------------------------------------------------------------
    def extract_commit_history(
        self,
        max_commits: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[CommitInfo]:
        """Extract commit history from the repository."""
        commits: list[CommitInfo] = []

        try:
            iter_commits = self.repo.iter_commits(
                max_count=max_commits, since=since, until=until
            )
        except Exception:
            return commits

        for commit in iter_commits:
            files_changed = []
            try:
                if commit.parents:
                    diff = commit.parents[0].diff(commit)
                else:
                    diff = commit.diff(None)
                for d in diff:
                    if d.a_path:
                        files_changed.append(d.a_path)
                    if d.b_path and d.b_path != d.a_path:
                        files_changed.append(d.b_path)
            except Exception:
                pass

            insertions = 0
            deletions = 0
            try:
                stats = commit.stats.total
                insertions = stats.get("insertions", 0)
                deletions = stats.get("deletions", 0)
            except Exception:
                pass

            commits.append(
                CommitInfo(
                    hash=commit.hexsha,
                    short_hash=commit.hexsha[:8],
                    author_name=commit.author.name or "",
                    author_email=commit.author.email or "",
                    author_date=commit.authored_date,
                    committer_name=commit.committer.name or "",
                    committer_email=commit.committer.email or "",
                    committer_date=commit.committed_date,
                    message=commit.message or "",
                    parents=[p.hexsha for p in commit.parents],
                    files_changed=list(set(files_changed)),
                    insertions=insertions,
                    deletions=deletions,
                )
            )

        return commits

    # ------------------------------------------------------------------
    # Frequently modified files
    # ------------------------------------------------------------------
    def file_change_frequencies(self, commits: list[CommitInfo]) -> dict[str, int]:
        """Count how many times each file was modified."""
        frequencies: dict[str, int] = {}
        for commit in commits:
            for file_path in commit.files_changed:
                frequencies[file_path] = frequencies.get(file_path, 0) + 1
        return dict(sorted(frequencies.items(), key=lambda x: x[1], reverse=True))

    # ------------------------------------------------------------------
    # Contributors
    # ------------------------------------------------------------------
    def extract_contributors(self, commits: list[CommitInfo]) -> dict[str, ContributorInfo]:
        """Extract contributor information from commits."""
        contributors: dict[str, ContributorInfo] = {}

        for commit in commits:
            key = commit.author_email or commit.author_name
            if key not in contributors:
                contributors[key] = ContributorInfo(
                    name=commit.author_name,
                    email=commit.author_email,
                    commit_count=0,
                )
            contrib = contributors[key]
            contrib.commit_count += 1
            contrib.files_changed.extend(commit.files_changed)
            if contrib.first_commit is None or commit.author_date < datetime.fromtimestamp(
                contrib.first_commit_timestamp if hasattr(contrib, "first_commit_timestamp") else 0
            ):
                pass  # handled below

        # Track first/last commit dates
        contributor_dates: dict[str, list[float]] = {}
        for commit in commits:
            key = commit.author_email or commit.author_name
            contributor_dates.setdefault(key, []).append(commit.author_date)

        for key, dates in contributor_dates.items():
            contrib = contributors[key]
            contrib.first_commit = datetime.fromtimestamp(min(dates)).isoformat()
            contrib.last_commit = datetime.fromtimestamp(max(dates)).isoformat()
            contrib.files_changed = sorted(set(contrib.files_changed))

        return dict(
            sorted(contributors.items(), key=lambda x: x[1].commit_count, reverse=True)
        )

    # ------------------------------------------------------------------
    # File histories
    # ------------------------------------------------------------------
    def build_file_histories(self, commits: list[CommitInfo]) -> dict[str, FileHistory]:
        """Build per-file change histories."""
        file_data: dict[str, dict] = {}

        for commit in commits:
            for file_path in commit.files_changed:
                if file_path not in file_data:
                    file_data[file_path] = {
                        "change_count": 0,
                        "first_commit": commit.hash,
                        "last_commit": commit.hash,
                        "contributors": set(),
                        "total_insertions": 0,
                        "total_deletions": 0,
                    }
                data = file_data[file_path]
                data["change_count"] += 1
                data["last_commit"] = commit.hash
                data["contributors"].add(commit.author_email or commit.author_name)
                data["total_insertions"] += commit.insertions
                data["total_deletions"] += commit.deletions

        histories: dict[str, FileHistory] = {}
        for path, data in file_data.items():
            histories[path] = FileHistory(
                path=path,
                change_count=data["change_count"],
                first_commit=data["first_commit"],
                last_commit=data["last_commit"],
                contributors=sorted(data["contributors"]),
                total_insertions=data["total_insertions"],
                total_deletions=data["total_deletions"],
            )

        return dict(
            sorted(histories.items(), key=lambda x: x[1].change_count, reverse=True)
        )

    # ------------------------------------------------------------------
    # Co-change analysis
    # ------------------------------------------------------------------
    def find_co_changing_files(self, commits: list[CommitInfo]) -> list[CoChangeInfo]:
        """Find files that are frequently modified together in the same commit."""
        pair_counts: dict[tuple[str, str], dict] = {}

        for commit in commits:
            files = commit.files_changed
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    a, b = sorted([files[i], files[j]])
                    key = (a, b)
                    if key not in pair_counts:
                        pair_counts[key] = {"count": 0, "commits": []}
                    pair_counts[key]["count"] += 1
                    pair_counts[key]["commits"].append(commit.short_hash)

        co_changes: list[CoChangeInfo] = []
        for (a, b), data in pair_counts.items():
            co_changes.append(
                CoChangeInfo(
                    file_a=a,
                    file_b=b,
                    change_count=data["count"],
                    commits=data["commits"],
                )
            )

        return sorted(co_changes, key=lambda x: x.change_count, reverse=True)

    # ------------------------------------------------------------------
    # Symbol change tracking (functions and classes across commits)
    # ------------------------------------------------------------------
    def _extract_symbols(self, source: bytes, file_path: str) -> dict[str, dict]:
        """Extract function and class symbols with line ranges from source."""
        if _ast is None:
            return {}
        try:
            tree = _ast.parse(source.decode("utf-8", errors="replace"))
        except SyntaxError:
            return {}

        symbols: dict[str, dict] = {}
        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef):
                symbols[node.name] = {
                    "type": "function",
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                }
            elif isinstance(node, _ast.ClassDef):
                symbols[node.name] = {
                    "type": "class",
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                }
        return symbols

    def track_symbol_changes(
        self, commits: list[CommitInfo], max_files: Optional[int] = None
    ) -> list[SymbolChange]:
        """Track changes to functions and classes across commits.

        Compares consecutive versions of each Python file to detect
        added/modified/deleted symbols.
        """
        symbol_changes: list[SymbolChange] = []

        # Group commits by file, ordered by date
        file_commits: dict[str, list[CommitInfo]] = {}
        for commit in commits:
            for file_path in commit.files_changed:
                if file_path and file_path.endswith(".py"):
                    file_commits.setdefault(file_path, []).append(commit)

        # Sort each file's commits by date (oldest first)
        for file_path in file_commits:
            file_commits[file_path].sort(key=lambda c: c.author_date)

        if max_files:
            file_paths = list(file_commits.keys())[:max_files]
        else:
            file_paths = list(file_commits.keys())

        # Track previous symbols per file
        prev_symbols: dict[str, dict[str, dict]] = {}

        for file_path in file_paths:
            commits_for_file = file_commits[file_path]
            current_symbols: dict[str, dict] = {}

            for commit in commits_for_file:
                try:
                    # Get the file content at this commit via the repo
                    git_commit = self.repo.commit(commit.hash)
                    blob = git_commit.tree[file_path]
                    source = blob.data_stream.read()
                except Exception:
                    continue

                new_symbols = self._extract_symbols(source, file_path)

                # Compare with previous symbols
                if file_path in prev_symbols:
                    prev = prev_symbols[file_path]
                    for name, info in new_symbols.items():
                        if name not in prev:
                            # New symbol added
                            symbol_changes.append(
                                SymbolChange(
                                    symbol_name=name,
                                    symbol_type=info["type"],
                                    file_path=file_path,
                                    commit_hash=commit.hash,
                                    commit_date=datetime.fromtimestamp(
                                        commit.author_date
                                    ),
                                    author=commit.author_name,
                                    change_type="added",
                                )
                            )
                        elif prev[name] != info:
                            # Symbol modified
                            symbol_changes.append(
                                SymbolChange(
                                    symbol_name=name,
                                    symbol_type=info["type"],
                                    file_path=file_path,
                                    commit_hash=commit.hash,
                                    commit_date=datetime.fromtimestamp(
                                        commit.author_date
                                    ),
                                    author=commit.author_name,
                                    change_type="modified",
                                )
                            )
                    for name in prev:
                        if name not in new_symbols:
                            # Symbol deleted
                            symbol_changes.append(
                                SymbolChange(
                                    symbol_name=name,
                                    symbol_type=prev[name]["type"],
                                    file_path=file_path,
                                    commit_hash=commit.hash,
                                    commit_date=datetime.fromtimestamp(
                                        commit.author_date
                                    ),
                                    author=commit.author_name,
                                    change_type="deleted",
                                )
                            )
                else:
                    # First time seeing this file - all symbols are "added"
                    for name, info in new_symbols.items():
                        symbol_changes.append(
                            SymbolChange(
                                symbol_name=name,
                                symbol_type=info["type"],
                                file_path=file_path,
                                commit_hash=commit.hash,
                                commit_date=datetime.fromtimestamp(
                                    commit.author_date
                                ),
                                author=commit.author_name,
                                change_type="added",
                            )
                        )

                prev_symbols[file_path] = new_symbols

        return symbol_changes

    # ------------------------------------------------------------------
    # Full analysis
    # ------------------------------------------------------------------
    def analyze(
        self,
        max_commits: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        track_symbols: bool = False,
        max_symbol_files: Optional[int] = None,
    ) -> GitHistoryData:
        """Run the full Git history analysis."""
        commits = self.extract_commit_history(max_commits, since, until)

        file_frequencies = self.file_change_frequencies(commits)
        contributors = self.extract_contributors(commits)
        file_histories = self.build_file_histories(commits)
        co_changes = self.find_co_changing_files(commits)

        symbol_changes: list[SymbolChange] = []
        if track_symbols:
            symbol_changes = self.track_symbol_changes(commits, max_symbol_files)

        total_insertions = sum(c.insertions for c in commits)
        total_deletions = sum(c.deletions for c in commits)

        summary = {
            "total_commits": len(commits),
            "total_contributors": len(contributors),
            "total_files_changed": len(file_histories),
            "total_insertions": total_insertions,
            "total_deletions": total_deletions,
            "top_modified_files": list(file_frequencies.items())[:10],
            "top_contributors": [
                (c.name, c.commit_count) for c in list(contributors.values())[:10]
            ],
            "top_co_changes": [
                (cc.file_a, cc.file_b, cc.change_count) for cc in co_changes[:10]
            ],
            "symbol_change_count": len(symbol_changes),
        }

        return GitHistoryData(
            commits=commits,
            file_histories=file_histories,
            contributors=contributors,
            co_changes=co_changes,
            symbol_changes=symbol_changes,
            summary=summary,
        )
