"""On-demand Git history for repository files and branches."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from git import Repo
from git.exc import GitCommandError

from .repository_ingestion import extract_repository_files


def _date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("Invalid repository path.")
    return path.as_posix()


def _branches(repo: Repo) -> dict[str, Any]:
    branches = {
        ref.remote_head: ref
        for ref in repo.remotes.origin.refs
        if ref.remote_head != "HEAD"
    } if "origin" in repo.remotes else {}
    branches.update({branch.name: branches.get(branch.name, branch) for branch in repo.branches})
    return branches


def _branch_files(repo: Repo, branches: dict[str, Any], branch_name: str) -> dict[str, Any]:
    if branch_name not in branches:
        raise KeyError("Branch not found.")

    default_branch = None
    try:
        default_branch = repo.git.symbolic_ref("refs/remotes/origin/HEAD").removeprefix(
            "refs/remotes/origin/"
        )
    except GitCommandError:
        if not repo.head.is_detached:
            default_branch = repo.active_branch.name
    if default_branch not in branches:
        default_branch = next(iter(branches), None)

    selected = branches[branch_name]
    if branch_name == default_branch or default_branch is None:
        changes = []
        exclusive_commits = []
    else:
        try:
            base = repo.merge_base(branches[default_branch], selected)
        except GitCommandError:
            base = []
        base_commit = base[0] if base else repo.commit(default_branch)
        changes = list(base_commit.diff(selected))
        exclusive_commits = list(repo.iter_commits(f"{base_commit.hexsha}..{selected.name}"))

    commits_by_path: dict[str, list[Any]] = {}
    for commit in exclusive_commits:
        parent = commit.parents[0] if commit.parents else None
        if parent:
            diffs = commit.diff(parent)
        else:
            diffs = commit.diff(None)
        for diff in diffs:
            for path in {diff.a_path, diff.b_path} - {None}:
                commits_by_path.setdefault(path, []).append(commit)

    files = []
    for diff in changes:
        path = diff.b_path or diff.a_path
        commits = commits_by_path.get(path, [])
        files.append({
            "path": path,
            "status": {
                "A": "added",
                "M": "modified",
                "D": "deleted",
                "R": "renamed",
                "C": "copied",
            }.get(diff.change_type, "modified"),
            "commit_count": len({commit.hexsha for commit in commits}),
            "contributors": sorted({
                commit.author.name or "Unknown author" for commit in commits
            }),
        })

    return {"branch": branch_name, "default_branch": default_branch, "files": files}


def branch_files(repository_path: Path, branch_name: str) -> dict[str, Any]:
    repo = Repo(repository_path)
    return _branch_files(repo, _branches(repo), branch_name)


def file_history(repository_path: Path, value: str, limit: int = 50) -> dict[str, Any]:
    path = _relative_path(value)
    repository_path = repository_path.resolve()
    repo = Repo(repository_path)
    full_path = repository_path / Path(*PurePosixPath(path).parts)
    if not full_path.resolve().is_relative_to(repository_path):
        raise ValueError("Invalid repository path.")
    is_file = full_path.is_file()
    is_directory = full_path.is_dir()
    files, directories, _ = extract_repository_files(repository_path)
    file_records = {item["path"]: item for item in files}
    if not is_file and not is_directory:
        commits_for_deleted = list(repo.iter_commits("--all", paths=path))
        if path not in file_records and not commits_for_deleted:
            raise FileNotFoundError("File or directory not found.")
        is_directory = False

    commits = list(repo.iter_commits("--all", paths=path, topo_order=True))
    commits.sort(key=lambda commit: commit.committed_date, reverse=True)
    contributors = sorted({
        commit.author.name or "Unknown author" for commit in commits
    })
    branches_by_name = _branches(repo)
    branches = []
    for branch_name in branches_by_name:
        changes = _branch_files(repo, branches_by_name, branch_name)["files"]
        matching = [
            change for change in changes
            if change["path"] == path
            or (is_directory and change["path"].startswith(f"{path}/"))
        ]
        if matching:
            branches.append({
                "name": branch_name,
                "commit_count": sum(change["commit_count"] for change in matching),
                "status": matching[-1]["status"] if len(matching) == 1 else "modified",
            })

    if is_directory:
        prefix = f"{path}/"
        child_files = [item for item in files if item["path"].startswith(prefix)]
        child_directories = [
            item for item in directories
            if item.startswith(prefix) and "/" not in item[len(prefix):]
        ]
        metadata = {
            "file_count": len(child_files),
            "subdirectory_count": len(child_directories),
        }
    else:
        metadata = file_records.get(path)

    return {
        "path": path,
        "kind": "directory" if is_directory else "file",
        "metadata": metadata,
        "commit_count": len(commits),
        "last_modified": _date(commits[0].committed_date) if commits else None,
        "last_modified_by": (
            commits[0].author.name or "Unknown author" if commits else None
        ),
        "contributors": contributors,
        "branches": branches,
        "commits": [
            {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": commit.author.name or "Unknown author",
                "date": _date(commit.committed_date),
            }
            for commit in commits[:limit]
        ],
        "first_commit": (
            {
                "hash": commits[-1].hexsha,
                "date": _date(commits[-1].committed_date),
                "author": commits[-1].author.name or "Unknown author",
            }
            if commits
            else None
        ),
    }
