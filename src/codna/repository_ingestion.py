"""Public GitHub repository ingestion."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from git import NULL_TREE, Repo
from git.exc import GitCommandError

from .git_utils import clone_repository, parse_github_url
from .language import detect_language
from .walker import RepoWalker

logger = logging.getLogger(__name__)


class RepositoryUnavailableError(Exception):
    """The repository could not be fetched without authentication."""


class RepositoryFetchError(Exception):
    """A public repository could not be fetched."""


def _git_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def extract_repository_files(
    repository_path: Path,
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    files = []
    directories: set[str] = set()
    languages: dict[str, int] = {}
    for path in RepoWalker(repository_path).walk_files():
        relative_path = path.relative_to(repository_path).as_posix()
        language = detect_language(path)
        files.append({
            "path": relative_path,
            "name": path.name,
            "extension": path.suffix,
            "size": path.lstat().st_size,
            "language": language.name if language else None,
            "is_source": language.is_source if language else False,
        })
        if language:
            languages[language.name] = languages.get(language.name, 0) + 1
        parent = Path(relative_path).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    return files, sorted(directories), languages


def extract_repository_data(
    repository_path: Path, owner: str, name: str, repo_url: str
) -> dict[str, Any]:
    """Extract branches, commits, contributors, and files from a cloned repository."""
    repo = Repo(repository_path)

    try:
        default_ref = repo.git.symbolic_ref("refs/remotes/origin/HEAD")
        default_branch = default_ref.removeprefix("refs/remotes/origin/")
    except GitCommandError:
        default_branch = repo.active_branch.name if not repo.head.is_detached else None

    branch_refs = {
        ref.remote_head: ref
        for ref in repo.remote("origin").refs
        if ref.remote_head != "HEAD"
    }
    if not branch_refs:
        branch_refs = {branch.name: branch for branch in repo.branches}

    branches = []
    for branch_name, branch_ref in sorted(branch_refs.items()):
        commits = list(repo.iter_commits(branch_ref))
        latest = commits[0] if commits else None
        branches.append({
            "name": branch_name,
            "latest_commit": latest.hexsha if latest else None,
            "commit_count": len(commits),
            "last_commit_date": (
                _git_timestamp(latest.committed_date) if latest else None
            ),
            "last_commit_author": (
                latest.author.name or "" if latest else None
            ),
        })

    commits_by_hash = {commit.hexsha: commit for commit in repo.iter_commits("--all")}
    commits = [
        {
            "hash": commit.hexsha,
            "author_name": commit.author.name or "",
            "author_email": commit.author.email or "",
            "message": commit.message.strip(),
            "date": _git_timestamp(commit.committed_date),
        }
        for commit in sorted(
            commits_by_hash.values(),
            key=lambda commit: commit.committed_date,
            reverse=True,
        )
    ]
    contributors: dict[str, dict[str, Any]] = {}
    for commit in commits_by_hash.values():
        name_from_git = commit.author.name or ""
        email = commit.author.email or ""
        key = email.casefold() or name_from_git.casefold()
        contributor = contributors.setdefault(key, {
            "name": name_from_git,
            "email": email,
            "commit_count": 0,
            "files_changed": set(),
            "last_contribution": None,
            "_last_timestamp": -1,
        })
        contributor["commit_count"] += 1
        parent = commit.parents[0] if commit.parents else NULL_TREE
        contributor["files_changed"].update(
            change.b_path or change.a_path for change in commit.diff(parent)
            if change.b_path or change.a_path
        )
        if commit.authored_date > contributor["_last_timestamp"]:
            contributor["_last_timestamp"] = commit.authored_date
            contributor["last_contribution"] = _git_timestamp(commit.authored_date)

    contributors_data = []
    for contributor in sorted(
        contributors.values(),
        key=lambda item: (-item["commit_count"], item["name"].casefold()),
    ):
        contributors_data.append({
            "name": contributor["name"],
            "email": contributor["email"],
            "commit_count": contributor["commit_count"],
            "files_changed": sorted(contributor["files_changed"]),
            "last_contribution": contributor["last_contribution"],
        })

    files, directories, languages = extract_repository_files(repository_path)

    current_head = repo.head.commit.hexsha if repo.head.is_valid() else None
    return {
        "name": name,
        "owner": owner,
        "url": repo_url,
        "local_path": str(repository_path.resolve()),
        "default_branch": default_branch,
        "branches": branches,
        "current_head": current_head,
        "commit_count": len(commits_by_hash),
        "commits": commits,
        "contributors": contributors_data,
        "files": files,
        "directories": directories,
        "languages": languages,
        "file_count": len(files),
        "directory_count": len(directories),
    }


def ingest_public_github_repository(
    repo_url: str, data_root: Path
) -> tuple[dict[str, Any], Path]:
    """Clone a public GitHub repository and return its extracted metadata."""
    owner, name, clone_url = parse_github_url(repo_url)
    canonical_url = f"https://github.com/{owner}/{name}"
    parent = data_root.resolve() / "repositories" / owner
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"{name}-{uuid.uuid4().hex[:12]}"

    try:
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            staged_repository = Path(temporary) / "repository"
            clone_repository(clone_url, staged_repository)
            metadata = extract_repository_data(
                staged_repository, owner, name, canonical_url
            )
            os.replace(staged_repository, destination)
    except GitCommandError as exc:
        details = f"{exc.stdout or ''}\n{exc.stderr or ''}\n{exc}".casefold()
        if any(text in details for text in (
            "repository not found",
            "authentication failed",
            "could not read username",
            "terminal prompts disabled",
        )):
            logger.info("GitHub repository is private or unavailable: %s", canonical_url)
            raise RepositoryUnavailableError from exc
        logger.exception("Failed to clone public repository %s", canonical_url)
        raise RepositoryFetchError from exc
    except OSError as exc:
        logger.exception("Failed to store public repository %s", canonical_url)
        raise RepositoryFetchError from exc
    except Exception as exc:
        logger.exception("Failed to extract public repository %s", canonical_url)
        raise RepositoryFetchError from exc

    metadata["local_path"] = str(destination.resolve())
    return metadata, destination


def public_repository_data(metadata: dict[str, Any]) -> dict[str, Any]:
    """Omit full commit history and commit emails from API responses."""
    return {
        **{key: value for key, value in metadata.items() if key != "commits"},
        "contributors": [
            {key: value for key, value in contributor.items() if key != "email"}
            for contributor in metadata["contributors"]
        ],
    }

