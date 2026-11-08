"""Git utilities for cloning and inspecting repositories."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError


@dataclass(frozen=True)
class GitInfo:
    """Metadata about a Git repository."""

    repo_url: str | None
    local_path: Path
    commit_hash: str | None
    branch: str | None


def parse_github_url(repo_url: str) -> tuple[str, str, str]:
    """Return owner, repository name, and a credential-free HTTPS clone URL."""
    try:
        parsed = urlparse(repo_url.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid GitHub repository URL.") from exc

    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or port is not None
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        raise ValueError("Invalid GitHub repository URL.")

    owner, name = parts
    if name.lower().endswith(".git"):
        name = name[:-4]
    if not owner or not name or any(
        part in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
        for part in (owner, name)
    ):
        raise ValueError("Invalid GitHub repository URL.")

    return owner, name, f"https://github.com/{owner}/{name}.git"


def clone_repository(repo_url: str, destination: Path) -> Path:
    """Clone a GitHub repository into `destination`.

    Returns the path to the cloned repository root.
    """
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Destination {destination} is not empty")

    depth_value = os.getenv("CODNA_GIT_DEPTH", "300").strip()
    try:
        depth = int(depth_value) if depth_value else 300
    except ValueError as exc:
        raise ValueError("CODNA_GIT_DEPTH must be an integer") from exc
    if depth < 0:
        raise ValueError("CODNA_GIT_DEPTH must be zero or greater")
    clone_options = {"no_single_branch": True}
    if depth > 0:
        clone_options["depth"] = depth

    Repo.clone_from(
        repo_url,
        destination,
        **clone_options,
        env={
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "",
        },
    )
    return destination


def open_repository(path: Path) -> Repo:
    """Open an existing Git repository at `path`."""
    return Repo(path)


def get_git_info(path: Path) -> GitInfo:
    """Extract Git metadata for a local repository path."""
    try:
        repo = open_repository(path)
    except InvalidGitRepositoryError:
        return GitInfo(
            repo_url=None,
            local_path=path,
            commit_hash=None,
            branch=None,
        )

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
