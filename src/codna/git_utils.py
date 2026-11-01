"""Git utilities for cloning and inspecting repositories."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from git import Repo


@dataclass(frozen=True)
class GitInfo:
    """Metadata about a Git repository."""

    repo_url: str | None
    local_path: Path
    commit_hash: str | None
    branch: str | None


def clone_repository(repo_url: str, destination: Path) -> Path:
    """Clone a GitHub repository into `destination`.

    Returns the path to the cloned repository root.
    """
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Destination {destination} is not empty")

    Repo.clone_from(repo_url, destination)
    return destination


def open_repository(path: Path) -> Repo:
    """Open an existing Git repository at `path`."""
    return Repo(path)


def get_git_info(path: Path) -> GitInfo:
    """Extract Git metadata for a local repository path."""
    repo = open_repository(path)
    commit_hash = None
    branch = None
    try:
        commit_hash = repo.head.commit.hexsha
    except Exception:
        commit_hash = None
    try:
        branch = repo.active_branch.name
    except Exception:
        branch = None
    repo_url = None
    try:
        origin = repo.remote(name="origin")
        repo_url = next(iter(origin.urls))
    except Exception:
        repo_url = None

    return GitInfo(
        repo_url=repo_url,
        local_path=path,
        commit_hash=commit_hash,
        branch=branch,
    )


def is_ignored_git(path: Path) -> bool:
    """Return True if the path is a `.git` directory or nested inside one."""
    parts = path.resolve().parts
    return ".git" in parts
