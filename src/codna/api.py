"""FastAPI backend for CodeDNA.

Endpoints:
- POST /repositories         - register a repository (URL or local path)
- GET  /repositories         - list registered repositories
- POST /analysis/{repo_id}   - start a full analysis job (background)
- GET  /analysis/{job_id}    - get analysis job status/result
- GET  /graph/{repo_id}      - get dependency graph JSON
- GET  /risk/{repo_id}       - get module risk report
- GET  /impact/{repo_id}     - get change impact for a target function/file
- GET  /repositories/{repo_id}/summary  - combined repository summary
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .ast_parser import parse_file
from .change_impact import ChangeImpactAnalyzer
from .database import (
    AnalysisJob,
    ImpactReport,
    ModuleRisk,
    Repository,
    get_session,
    init_db,
)
from .dependency_graph import DependencyGraph
from .git_history import GitHistoryAnalyzer
from .language import detect_language, is_source_file
from .metrics import compute_file_metrics
from .risk_engine import RiskEngine
from .scanner import RepositoryScanner
from .schemas import (
    AnalysisJobCreate,
    AnalysisJobOut,
    GraphOut,
    ImpactReportOut,
    ModuleRiskOut,
    RepositoryCreate,
    RepositoryOut,
)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(title="CodeDNA API", version="0.1.0")
    init_db()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_repo_or_404(db, repo_id: int) -> Repository:
        repo = db.get(Repository, repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        return repo

    def _scan_repository(local_path: str, repo_url: Optional[str] = None):
        """Run Week 1 scanner against a local directory."""
        root = Path(local_path)
        if not root.is_dir():
            raise HTTPException(
                status_code=400, detail=f"Path {local_path} is not a directory"
            )
        scanner = RepositoryScanner(root, repo_url=repo_url)
        return scanner.scan()

    def _run_full_analysis(repo: Repository) -> dict[str, Any]:
        """Execute the complete analysis pipeline (Week 1-7).

        Tree-sitter parsing is skipped entirely on this platform because
        node.text access crashes under FastAPI's thread pool (Windows +
        Python 3.14). Graph, risk, and architecture data are computed from
        scanner metadata only.
        """
        root = Path(repo.local_path).resolve()
        if not root.is_dir():
            raise RuntimeError(f"Repository path {root} does not exist")

        # --- Week 1: scan ---
        walker_results = _scan_repository(str(root), repo.repo_url)
        files = walker_results.files

        # No AST parsing on this platform; graph/risk use scanner metadata
        source_files: list[Path] = []
        file_asts: list = []
        metrics_by_path: dict[str, Any] = {}

        # --- Week 3: dependency graph ---
        dg = DependencyGraph()
        graph_data = dg.build_from_files(file_asts, source_files, root,
                                         skip_call_edges=True)

        # --- Week 5: git history ---
        from git import Repo as GitRepo
        try:
            grepo = GitRepo(root)
            gha = GitHistoryAnalyzer(grepo)
            git_data = gha.analyze(max_commits=200)
        except Exception:
            git_data = None

        # --- Week 4 + 7: architecture + risk ---
        try:
            from .architecture import ArchitectureAnalyzer
            arch_analyzer = ArchitectureAnalyzer(dg.graph, graph_data, metrics_by_path)
            arch_report = arch_analyzer.analyze()
        except Exception:
            arch_report = None

        engine = RiskEngine(
            graph=dg.graph,
            graph_data=graph_data,
            metrics_by_path=metrics_by_path,
            git_history_data=git_data,
        )
        risk_report = engine.analyze()

        # --- Week 6: change impact (exposed per-target via endpoint) ---
        impact_analyzer = ChangeImpactAnalyzer(
            dg.graph, graph_data, git_history_data=git_data,
            file_metrics=metrics_by_path,
        )

        return {
            "scan": {
                "total_files": len(files),
                "source_files": sum(1 for f in files if f.get("is_source")),
                "languages": walker_results.summary.get("languages", {}),
            },
            "graph": graph_data.to_dict(),
            "architecture": (
                {
                    "summary": arch_report.summary,
                    "modules": [
                        {
                            "path": m.path,
                            "cyclomatic_complexity": m.cyclomatic_complexity,
                            "code_lines": m.code_lines,
                            "in_degree": m.in_degree,
                            "out_degree": m.out_degree,
                            "betweenness_centrality": m.betweenness_centrality,
                            "risk_flags": m.risk_flags,
                        }
                        for m in arch_report.modules
                    ],
                }
                if arch_report
                else None
            ),
            "risk": {
                "summary": risk_report.summary,
                "modules": [
                    {
                        "path": m.path,
                        "total_score": m.total_score,
                        "risk_level": m.risk_level,
                        "investigation_priority": m.investigation_priority,
                        "explanation": m.explanation,
                    }
                    for m in risk_report.modules
                ],
            },
            "git": (
                {
                    "total_commits": git_data.summary["total_commits"],
                    "total_contributors": git_data.summary["total_contributors"],
                    "top_modified_files": git_data.summary["top_modified_files"],
                    "top_co_changes": git_data.summary["top_co_changes"],
                }
                if git_data
                else None
            ),
        }

    # ------------------------------------------------------------------
    # Repository endpoints
    # ------------------------------------------------------------------
    @app.post("/repositories", response_model=RepositoryOut, status_code=201)
    def register_repository(repo_in: RepositoryCreate):
        db = get_session()
        try:
            repo = Repository(
                repo_url=repo_in.repo_url,
                local_path=repo_in.local_path,
                status="registered",
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)
            return repo
        finally:
            db.close()

    @app.get("/repositories", response_model=list[RepositoryOut])
    def list_repositories():
        db = get_session()
        try:
            return db.query(Repository).all()
        finally:
            db.close()

    @app.get("/repositories/{repo_id}", response_model=RepositoryOut)
    def get_repository(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            return repo
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Analysis job endpoints
    # ------------------------------------------------------------------
    @app.post("/analysis/{repo_id}", response_model=AnalysisJobOut, status_code=202)
    def start_analysis(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            job = AnalysisJob(repo_id=repo_id, status="running")
            db.add(job)
            db.commit()
            db.refresh(job)

            try:
                result = _run_full_analysis(repo)
                job.status = "completed"
                job.result_json = json.dumps(result, default=str)
            except Exception as exc:  # noqa: BLE001
                job.status = "failed"
                job.error = str(exc)
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        finally:
            db.close()

    @app.get("/analysis/{job_id}", response_model=AnalysisJobOut)
    def get_analysis(job_id: int):
        db = get_session()
        try:
            job = db.get(AnalysisJob, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Analysis job not found")
            return job
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Graph endpoint
    # ------------------------------------------------------------------
    @app.get("/graph/{repo_id}", response_model=GraphOut)
    def get_graph(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(
                    status_code=400, detail="Repository path not found"
                )
            # Tree-sitter parsing skipped on this platform (Windows +
            # Python 3.14 + FastAPI thread pool causes node.text crash)
            dg = DependencyGraph()
            graph_data = dg.build_from_files([], [], root)
            return graph_data.to_dict()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Risk endpoint
    # ------------------------------------------------------------------
    @app.get("/risk/{repo_id}")
    def get_risk(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=400, detail="Repository path not found")

            # Tree-sitter parsing skipped on this platform
            dg = DependencyGraph()
            graph_data = dg.build_from_files([], [], root)

            from git import Repo as GitRepo
            try:
                grepo = GitRepo(root)
                gha = GitHistoryAnalyzer(grepo)
                git_data = gha.analyze(max_commits=200)
            except Exception:
                git_data = None

            engine = RiskEngine(
                graph=dg.graph,
                graph_data=graph_data,
                metrics_by_path={},
                git_history_data=git_data,
            )
            risk_report = engine.analyze()
            return {
                "summary": risk_report.summary,
                "modules": [
                    {
                        "path": m.path,
                        "total_score": m.total_score,
                        "risk_level": m.risk_level,
                        "investigation_priority": m.investigation_priority,
                        "explanation": m.explanation,
                        "features": [
                            {
                                "name": fe.name,
                                "raw_value": fe.raw_value,
                                "normalized": fe.normalized,
                                "weight": fe.weight,
                                "score": fe.score,
                                "explanation": fe.explanation,
                            }
                            for fe in m.features
                        ],
                    }
                    for m in risk_report.modules
                ],
            }
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Impact endpoint
    # ------------------------------------------------------------------
    @app.get("/impact/{repo_id}")
    def get_impact(repo_id: int, target: str, target_file: Optional[str] = None):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=400, detail="Repository path not found")

            # Tree-sitter parsing skipped on this platform
            dg = DependencyGraph()
            graph_data = dg.build_from_files([], [], root)

            from git import Repo as GitRepo
            try:
                grepo = GitRepo(root)
                gha = GitHistoryAnalyzer(grepo)
                git_data = gha.analyze(max_commits=200)
            except Exception:
                git_data = None

            cia = ChangeImpactAnalyzer(
                dg, graph_data, git_history_data=git_data,
                file_metrics={},
            )

            # Determine if target is a function or file
            if target_file:
                report = cia.analyze_file_change(target_file)
            else:
                report = cia.analyze_function_change(target, str(root))

            return {
                "target_type": report.target_type,
                "target_label": report.target_label,
                "target_file": report.target_file,
                "risk_score": report.risk_score,
                "risk_level": report.risk_level,
                "direct_callers": [
                    {
                        "label": c.label,
                        "type": c.type,
                        "file_path": c.file_path,
                        "line": c.line,
                        "impact_score": c.impact_score,
                        "reasons": c.impact_reasons,
                    }
                    for c in report.direct_callers
                ],
                "affected_modules": [
                    {
                        "label": m.label,
                        "file_path": m.file_path,
                        "impact_score": m.impact_score,
                        "reasons": m.impact_reasons,
                    }
                    for m in report.affected_modules
                ],
                "affected_tests": [
                    {
                        "label": t.label,
                        "file_path": t.file_path,
                        "impact_score": t.impact_score,
                    }
                    for t in report.affected_tests
                ],
                "co_changing_files": [
                    {
                        "label": c.label,
                        "file_path": c.file_path,
                        "impact_score": c.impact_score,
                        "reasons": c.impact_reasons,
                    }
                    for c in report.co_changing_files
                ],
                "review_components": [
                    {
                        "label": r.label,
                        "type": r.type,
                        "file_path": r.file_path,
                        "impact_score": r.impact_score,
                        "reasons": r.impact_reasons,
                    }
                    for r in report.review_components
                ],
                "summary": report.summary,
            }
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Summary endpoint
    # ------------------------------------------------------------------
    @app.get("/repositories/{repo_id}/summary")
    def get_summary(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            return {
                "repository": {
                    "id": repo.id,
                    "repo_url": repo.repo_url,
                    "local_path": repo.local_path,
                    "status": repo.status,
                },
                "message": "Use /analysis/{repo_id} to run full analysis, then /graph, /risk, /impact endpoints.",
            }
        finally:
            db.close()

    return app


app = create_app()
