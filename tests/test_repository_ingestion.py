import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, "src")

from git import Actor, Repo
from fastapi.testclient import TestClient

import codna.api as api_module
from codna.api import create_app
from codna.database import RepositorySnapshot, get_session
from codna.database import User
from codna.auth import create_oauth_state, hash_password, verify_oauth_state, verify_password
from codna.file_history import branch_files, file_history
from codna.git_utils import parse_github_url
from codna.repository_ingestion import (
    RepositoryFetchError,
    RepositoryUnavailableError,
    extract_repository_data,
    public_repository_data,
)


def test_parse_github_url_accepts_public_https_urls():
    assert parse_github_url(" https://github.com/owner/project.git/ ") == (
        "owner",
        "project",
        "https://github.com/owner/project.git",
    )


def test_password_hashing_round_trip():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_email_auth_register_login_and_logout():
    client = TestClient(create_app())
    email = f"person-{secrets.token_hex(4)}@example.test"
    registered = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Person",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["email"] == email
    assert client.get("/auth/me").status_code == 200

    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401
    logged_in = client.post(
        "/auth/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert logged_in.status_code == 200
    assert client.get("/auth/me").json()["display_name"] == "Person"


def test_oauth_start_requires_provider_configuration(monkeypatch):
    monkeypatch.setenv("CODNA_AUTH_SECRET", "test-secret")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    response = TestClient(create_app()).get("/auth/google/start")
    assert response.status_code == 503
    assert "Google OAuth is not configured" in response.json()["detail"]


def test_oauth_state_is_provider_bound(monkeypatch):
    monkeypatch.setenv("CODNA_AUTH_SECRET", "test-secret")
    state = create_oauth_state("google")
    assert verify_oauth_state(state, "google")
    assert not verify_oauth_state(state, "github")


def test_parse_github_url_rejects_non_github_or_unsafe_urls():
    invalid_urls = [
        "http://github.com/owner/project",
        "https://github.com.evil.test/owner/project",
        "https://user@github.com/owner/project",
        "https://github.com/owner/project?redirect=example.com",
        "https://github.com/owner/project/issues",
        "git@github.com:owner/project.git",
    ]
    for url in invalid_urls:
        try:
            parse_github_url(url)
        except ValueError as exc:
            assert str(exc) == "Invalid GitHub repository URL."
        else:
            raise AssertionError(f"Expected URL validation to reject {url}")


def _create_multibranch_repository(tmp_path: Path) -> Path:
    source = Repo.init(tmp_path / "source", initial_branch="trunk")
    alice = Actor("Alice", "alice@example.test")
    bob = Actor("Bob", "bob@example.test")

    (tmp_path / "source" / "README.md").write_text("# Example\n", encoding="utf-8")
    source.index.add(["README.md"])
    source.index.commit("Initial commit", author=alice, committer=alice)

    (tmp_path / "source" / "src").mkdir()
    (tmp_path / "source" / "src" / "main.py").write_text(
        "print('main')\n", encoding="utf-8"
    )
    (tmp_path / "source" / "web").mkdir()
    (tmp_path / "source" / "web" / "app.ts").write_text(
        "export const app = false\n", encoding="utf-8"
    )
    source.index.add(["src/main.py", "web/app.ts"])
    source.index.commit("Add Python entry point", author=alice, committer=alice)

    feature = source.create_head("feature/api")
    source.head.reference = feature
    (tmp_path / "source" / "web" / "app.ts").write_text(
        "export const app = true\n", encoding="utf-8"
    )
    source.index.add(["web/app.ts"])
    source.index.commit("Add TypeScript app", author=bob, committer=bob)

    remote_path = tmp_path / "remote.git"
    bare = Repo.init(remote_path, bare=True)
    source.create_remote("origin", str(remote_path))
    source.remotes.origin.push(all=True)
    (remote_path / "HEAD").write_text("ref: refs/heads/trunk\n", encoding="ascii")

    clone_path = tmp_path / "clone"
    Repo.clone_from(str(remote_path), clone_path)
    return clone_path


def test_extract_repository_data_uses_actual_git_and_file_metadata(tmp_path):
    repo_path = _create_multibranch_repository(tmp_path)

    data = extract_repository_data(
        repo_path, "owner", "project", "https://github.com/owner/project"
    )

    assert data["name"] == "project"
    assert data["owner"] == "owner"
    assert data["default_branch"] == "trunk"
    assert data["current_head"] == Repo(repo_path).head.commit.hexsha
    assert data["commit_count"] == 3
    assert {
        "hash",
        "author_name",
        "author_email",
        "message",
        "date",
    } <= set(data["commits"][0])
    assert {branch["name"] for branch in data["branches"]} == {"trunk", "feature/api"}
    assert {item["name"]: item["commit_count"] for item in data["contributors"]} == {
        "Alice": 2,
        "Bob": 1,
    }
    assert next(item for item in data["contributors"] if item["name"] == "Bob")[
        "files_changed"
    ] == ["web/app.ts"]
    assert {"src", "web"} <= set(data["directories"])
    assert {item["language"] for item in data["files"]} >= {
        "python",
        "typescript",
        "markdown",
    }
    python_file = next(item for item in data["files"] if item["path"] == "src/main.py")
    assert python_file["name"] == "main.py"
    assert python_file["extension"] == ".py"
    assert python_file["size"] > 0
    assert "email" not in public_repository_data(data)["contributors"][0]
    assert "commits" not in public_repository_data(data)


def test_file_history_tracks_commits_contributors_and_branch_changes(tmp_path):
    repo_path = _create_multibranch_repository(tmp_path)

    history = file_history(repo_path, "web/app.ts")
    feature_files = branch_files(repo_path, "feature/api")
    main_files = branch_files(repo_path, "trunk")

    assert history["kind"] == "file"
    assert history["commit_count"] == 2
    assert history["last_modified_by"] == "Bob"
    assert set(history["contributors"]) == {"Alice", "Bob"}
    assert [commit["author"] for commit in history["commits"]] == ["Bob", "Alice"]
    assert history["branches"] == [{
        "name": "feature/api",
        "commit_count": 1,
        "status": "modified",
    }]
    assert feature_files["files"] == [{
        "path": "web/app.ts",
        "status": "modified",
        "commit_count": 1,
        "contributors": ["Bob"],
    }]
    assert main_files["files"] == []


def test_directory_activity_and_deleted_file_history(tmp_path):
    repo_path = _create_multibranch_repository(tmp_path)
    repo = Repo(repo_path)
    default = repo.remotes.origin.refs.trunk
    branch = repo.create_head("feature/delete-readme", default)
    repo.head.reference = branch
    repo.index.remove(["README.md"], working_tree=True)
    repo.index.commit(
        "Remove README",
        author=Actor("Bob", "bob@example.test"),
        committer=Actor("Bob", "bob@example.test"),
    )
    repo.git.checkout("feature/delete-readme")

    deleted = branch_files(repo_path, "feature/delete-readme")
    deleted_history = file_history(repo_path, "README.md")
    directory = file_history(repo_path, "web")

    assert deleted["files"] == [{
        "path": "README.md",
        "status": "deleted",
        "commit_count": 1,
        "contributors": ["Bob"],
    }]
    assert deleted_history["metadata"] is None
    assert deleted_history["commits"][0]["message"] == "Remove README"
    assert directory["kind"] == "directory"
    assert directory["metadata"] == {"file_count": 1, "subdirectory_count": 0}
    assert directory["commit_count"] == 2


def test_file_history_rejects_traversal_and_unknown_branch(tmp_path):
    repo_path = _create_multibranch_repository(tmp_path)

    try:
        file_history(repo_path, "../outside.py")
    except ValueError as exc:
        assert str(exc) == "Invalid repository path."
    else:
        raise AssertionError("Expected repository path traversal to be rejected")

    try:
        branch_files(repo_path, "feature/missing")
    except KeyError as exc:
        assert str(exc) == "'Branch not found.'"
    else:
        raise AssertionError("Expected unknown branch to be rejected")


def test_repository_file_history_and_branch_file_routes(tmp_path):
    repo_path = _create_multibranch_repository(tmp_path)
    client = TestClient(create_app())
    response = client.post(
        "/repositories",
        json={"local_path": str(repo_path), "status": "registered"},
    )
    repo_id = response.json()["id"]

    history = client.get(
        f"/repositories/{repo_id}/files/history",
        params={"path": "web/app.ts"},
    )
    branch = client.get(
        f"/repositories/{repo_id}/branches/files",
        params={"branch": "feature/api"},
    )
    analysis = client.get(
        f"/repositories/{repo_id}/files/analysis",
        params={"path": "web/app.ts"},
    )
    conflicts = client.get(
        f"/repositories/{repo_id}/merge-conflicts",
        params={"base_branch": "trunk", "compare_branch": "feature/api"},
    )
    invalid = client.get(
        f"/repositories/{repo_id}/files/history",
        params={"path": "../outside.py"},
    )
    missing_branch = client.get(
        f"/repositories/{repo_id}/branches/files",
        params={"branch": "feature/missing"},
    )

    assert history.status_code == 200
    assert history.json()["commit_count"] == 2
    assert branch.status_code == 200
    assert branch.json()["files"][0]["status"] == "modified"
    assert analysis.status_code == 200
    assert {
        "what",
        "why",
        "role",
        "architecture",
    } <= analysis.json().keys()
    assert conflicts.status_code == 200
    assert conflicts.json()["conflicting_files"] == []
    assert invalid.status_code == 422
    assert missing_branch.status_code == 404

    non_git_path = tmp_path / "not-a-repository"
    non_git_path.mkdir()
    non_git_id = client.post(
        "/repositories",
        json={"local_path": str(non_git_path), "status": "registered"},
    ).json()["id"]
    unavailable_history = client.get(
        f"/repositories/{non_git_id}/files/history",
        params={"path": "README.md"},
    )
    unavailable_branch = client.get(
        f"/repositories/{non_git_id}/branches/files",
        params={"branch": "main"},
    )
    assert unavailable_history.status_code == 400
    assert unavailable_branch.status_code == 400


def test_repository_branch_history_returns_visualization_data(tmp_path):
    repo_path = _create_multibranch_repository(tmp_path)
    client = TestClient(create_app())
    repo_id = client.post(
        "/repositories",
        json={"local_path": str(repo_path), "status": "registered"},
    ).json()["id"]

    response = client.get(f"/repositories/{repo_id}/branches/history")

    assert response.status_code == 200
    data = response.json()
    assert data["default_branch"] == "trunk"
    assert {branch["name"] for branch in data["branches"]} == {"trunk", "feature/api"}
    feature = next(branch for branch in data["branches"] if branch["name"] == "feature/api")
    assert feature["commits"][-1]["message"] == "Add TypeScript app"
    assert feature["commits"][-1]["parents"]


def test_repository_endpoint_validates_url_before_fetching(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("invalid URLs must not reach the fetcher")

    monkeypatch.setattr(api_module, "ingest_public_github_repository", fail_if_called)
    client = TestClient(create_app())

    response = client.post(
        "/repositories", json={"repo_url": "https://github.com.evil/owner/project"}
    )

    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid GitHub repository URL.")


def test_repository_endpoint_handles_missing_or_private_repositories(monkeypatch):
    def fail_fetch(*args, **kwargs):
        raise RepositoryUnavailableError

    monkeypatch.setattr(api_module, "ingest_public_github_repository", fail_fetch)
    client = TestClient(create_app())

    response = client.post(
        "/repositories", json={"repo_url": "https://github.com/owner/project"}
    )

    assert response.status_code == 404
    assert "private or inaccessible" in response.json()["detail"]


def test_repository_endpoint_handles_fetch_failures(monkeypatch):
    def fail_fetch(*args, **kwargs):
        raise RepositoryFetchError

    monkeypatch.setattr(api_module, "ingest_public_github_repository", fail_fetch)
    client = TestClient(create_app())

    response = client.post(
        "/repositories", json={"repo_url": "https://github.com/owner/project"}
    )

    assert response.status_code == 502
    assert "Unable to fetch repository" in response.json()["detail"]


def test_repository_endpoint_returns_and_persists_structured_metadata(
    tmp_path, monkeypatch
):
    metadata = {
        "name": "project",
        "owner": "owner",
        "url": "https://github.com/owner/project",
        "local_path": str(tmp_path),
        "default_branch": "main",
        "branches": [{"name": "main", "latest_commit": "abc", "commit_count": 1}],
        "current_head": "abc",
        "commit_count": 1,
        "commits": [{
            "hash": "abc",
            "author_name": "Alice",
            "author_email": "alice@example.test",
            "message": "initial",
            "date": "2026-01-01T00:00:00+00:00",
        }],
        "contributors": [{
            "name": "Alice",
            "email": "alice@example.test",
            "commit_count": 1,
            "files_changed": ["README.md"],
            "last_contribution": "2026-01-01T00:00:00+00:00",
        }],
        "files": [{"path": "README.md", "size": 1, "language": "markdown"}],
        "directories": [],
        "file_count": 1,
        "directory_count": 0,
    }
    monkeypatch.setattr(
        api_module,
        "ingest_public_github_repository",
        lambda repo_url, data_root: (metadata, tmp_path),
    )
    client = TestClient(create_app())

    response = client.post(
        "/repositories", json={"repo_url": "https://github.com/owner/project"}
    )

    assert response.status_code == 201
    assert response.json()["branches"] == metadata["branches"]
    assert "email" not in response.json()["contributors"][0]
    db = get_session()
    try:
        snapshot = (
            db.query(RepositorySnapshot)
            .filter_by(repo_id=response.json()["id"])
            .one()
        )
        assert json.loads(snapshot.metadata_json)["contributors"][0]["email"] == (
            "alice@example.test"
        )
    finally:
        db.close()

    summary = client.get(f"/repositories/{response.json()['id']}/summary").json()
    assert summary["ingestion"]["current_head"] == "abc"
    assert summary["ingestion"]["ingested_at"]
    assert "email" not in summary["ingestion"]["contributors"][0]
    assert "commits" not in summary["ingestion"]

    commits = client.get(
        f"/repositories/{response.json()['id']}/commits?offset=0&limit=1"
    ).json()
    assert commits["total"] == 1
    assert commits["commits"][0]["message"] == "initial"
    assert "author_email" not in commits["commits"][0]
