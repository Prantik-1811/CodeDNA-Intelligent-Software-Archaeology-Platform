"""Integration tests for the FastAPI API endpoints."""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from fastapi.testclient import TestClient
from codna.api import create_app


def test_register_and_list_repositories():
    app = create_app()
    client = TestClient(app)

    resp = client.post("/repositories", json={
        "local_path": ".",
        "status": "registered",
    })
    assert resp.status_code == 201
    repo = resp.json()
    assert repo["local_path"] == "."
    assert repo["status"] == "registered"
    assert "id" in repo
    assert "id" in repo

    resp = client.get("/repositories")
    assert resp.status_code == 200
    repos = resp.json()
    assert len(repos) >= 1


def test_get_nonexistent_repository():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/repositories/99999")
    assert resp.status_code == 404


def test_start_analysis():
    app = create_app()
    client = TestClient(app)

    resp = client.post("/repositories", json={
        "local_path": ".",
        "status": "registered",
    })
    assert resp.status_code == 201
    repo = resp.json()
    repo_id = repo["id"]

    resp = client.post(f"/analysis/{repo_id}")
    assert resp.status_code == 202
    job = resp.json()
    assert job["repo_id"] == repo_id
    assert job["status"] == "completed"
    assert "id" in job

    # Poll briefly (analysis runs in background)
    for _ in range(10):
        resp = client.get(f"/analysis/{job['id']}")
        job = resp.json()
        if job["status"] in ("completed", "failed"):
            break

    assert job["status"] in ("completed", "failed")
    if job["status"] == "completed":
        assert job["result_json"] is not None
        import json
        result = json.loads(job["result_json"])
        assert "scan" in result
        assert "risk" in result


def test_graph_endpoint():
    app = create_app()
    client = TestClient(app)

    resp = client.post("/repositories", json={
        "local_path": ".",
        "status": "registered",
    })
    repo_id = resp.json()["id"]

    resp = client.get(f"/graph/{repo_id}")
    assert resp.status_code == 200
    graph = resp.json()
    assert "nodes" in graph
    assert "edges" in graph
    assert "metrics" in graph


def test_repository_tree_endpoint(tmp_path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    source_file = source_dir / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Example\n", encoding="utf-8")
    ignored_dir = tmp_path / "node_modules"
    ignored_dir.mkdir()
    (ignored_dir / "ignored.js").write_text("", encoding="utf-8")
    cache_dir = tmp_path / ".pytest_cache"
    cache_dir.mkdir()
    (cache_dir / "ignored.txt").write_text("", encoding="utf-8")

    client = TestClient(create_app())
    response = client.post(
        "/repositories",
        json={"local_path": str(tmp_path), "status": "registered"},
    )
    repo_id = response.json()["id"]

    response = client.get(f"/repositories/{repo_id}/tree")

    assert response.status_code == 200
    tree = response.json()
    assert tree["root"] == tmp_path.name
    assert tree["file_count"] == 2
    assert tree["directory_count"] == 1
    assert tree["languages"] == {"python": 1, "markdown": 1}
    assert {
        "path": "src/main.py",
        "name": "main.py",
        "extension": ".py",
        "size": source_file.stat().st_size,
        "language": "python",
        "is_source": True,
    } in tree["files"]
    assert tree["last_analyzed_at"] is None


def test_risk_endpoint():
    app = create_app()
    client = TestClient(app)

    resp = client.post("/repositories", json={
        "local_path": ".",
        "status": "registered",
    })
    repo_id = resp.json()["id"]

    resp = client.get(f"/risk/{repo_id}")
    assert resp.status_code == 200
    risk = resp.json()
    assert "summary" in risk
    assert "modules" in risk


def test_impact_endpoint():
    app = create_app()
    client = TestClient(app)

    resp = client.post("/repositories", json={
        "local_path": ".",
        "status": "registered",
    })
    repo_id = resp.json()["id"]

    resp = client.get(f"/impact/{repo_id}", params={
        "target": "authenticate_user",
        "target_file": "",
    })
    assert resp.status_code == 200
    impact = resp.json()
    assert "target_type" in impact
    assert "risk_score" in impact
    assert "risk_level" in impact
    assert "direct_callers" in impact
    assert "review_components" in impact


def test_summary_endpoint():
    app = create_app()
    client = TestClient(app)

    resp = client.post("/repositories", json={
        "local_path": ".",
        "status": "registered",
    })
    repo_id = resp.json()["id"]

    resp = client.get(f"/repositories/{repo_id}/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert "repository" in summary
    assert summary["repository"]["id"] == repo_id
