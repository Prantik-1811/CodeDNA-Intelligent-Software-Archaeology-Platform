"""FastAPI backend for CodeDNA.

Endpoints:
- POST /repositories         - register a repository (URL or local path)
- GET  /repositories         - list registered repositories
- GET  /repositories/{id}/commits - paginated Git commit history
- GET  /repositories/{id}/tree - list repository files and metadata
- POST /analysis/{repo_id}   - start a full analysis job (background)
- GET  /analysis/{job_id}    - get analysis job status/result
- GET  /graph/{repo_id}      - get dependency graph JSON
- GET  /risk/{repo_id}       - get module risk report
- GET  /impact/{repo_id}     - get change impact for a target function/file
- GET  /repositories/{repo_id}/summary  - combined repository summary
"""

from __future__ import annotations

import json
import ast
import logging
import re
import os
import hashlib
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from .change_impact import ChangeImpactAnalyzer
from .database import (
    AnalysisJob,
    AuthSession,
    ImpactReport,
    ModuleRisk,
    Repository,
    RepositorySnapshot,
    User,
    get_session,
    init_db,
    utc_now,
)
from .auth import (
    create_oauth_state,
    exchange_oauth_code,
    hash_password,
    oauth_authorization_url,
    verify_oauth_state,
    verify_password,
)
from .dependency_graph import DependencyGraph
from .git_history import GitHistoryAnalyzer
from .file_history import branch_files, file_history
from .risk_engine import RiskEngine
from .repository_ingestion import (
    RepositoryFetchError,
    RepositoryUnavailableError,
    extract_repository_files,
    ingest_public_github_repository,
    public_repository_data,
)
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
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


def _session_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _public_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "provider": user.provider}


def _merge_conflict_analysis(repository_path: Path, base_branch: str, compare_branch: str) -> dict[str, Any]:
    from .file_history import _branches
    from git import Repo as GitRepo

    repo = GitRepo(repository_path)
    branches = _branches(repo)
    if base_branch not in branches or compare_branch not in branches:
        raise KeyError("Branch not found.")
    base_refs = repo.merge_base(branches[base_branch], branches[compare_branch])
    if not base_refs:
        raise ValueError("Branches have no common ancestor.")
    base = base_refs[0]
    ours = branches[base_branch]
    theirs = branches[compare_branch]
    try:
        output = repo.git.merge_tree(base.hexsha, ours, theirs)
    except GitCommandError as exc:
        output = exc.stdout or exc.stderr or ""

    conflicting_files = set()
    conflict_block = False
    for line in output.splitlines():
        if line.startswith("CONFLICT ") and " in " in line:
            conflicting_files.add(line.rsplit(" in ", 1)[1].strip())
        elif line.strip() in {"changed in both", "added in both"}:
            conflict_block = True
        elif conflict_block and line.strip().startswith(("our ", "their ", "base ")):
            parts = line.split()
            if len(parts) >= 4:
                conflicting_files.add(" ".join(parts[3:]))
        elif conflict_block and line and not line.startswith((" ", "\t")):
            conflict_block = False
    conflicting_files = sorted(conflicting_files)
    relationships = []
    for index, path in enumerate(conflicting_files):
        for other in conflicting_files[index + 1:]:
            if Path(path).parent == Path(other).parent:
                relationships.append({
                    "files": [path, other],
                    "relationship": "same directory conflict cluster",
                })

    discussion = []
    for branch_name, ref in ((base_branch, ours), (compare_branch, theirs)):
        for commit in list(repo.iter_commits(ref, max_count=5)):
            discussion.append({
                "branch": branch_name,
                "author": commit.author.name or "Unknown author",
                "message": commit.message.strip(),
                "date": commit.committed_datetime.isoformat(),
            })
    return {
        "base_branch": base_branch,
        "compare_branch": compare_branch,
        "conflicting_files": [{"path": path, "status": "conflict"} for path in conflicting_files],
        "conflict_relationships": relationships,
        "developer_discussion": discussion,
        "ai_explanation": (
            f"{len(conflicting_files)} file(s) have competing changes between "
            f"{base_branch} and {compare_branch}. Review the listed branch commits "
            "and resolve each conflict while preserving the intended behavior from both sides."
            if conflicting_files
            else f"No textual merge conflicts were detected between {base_branch} and {compare_branch}."
        ),
    }


def _summarize_source_file(root: Path, relative_path: str, language: str | None) -> str:
    """Describe source structure without executing repository code."""
    path = root / relative_path
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")[:250_000]
    except OSError:
        return "Source file could not be read during analysis."

    suffix = path.suffix.casefold()
    if suffix == ".py":
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return "Python source file with syntax that could not be parsed."
        imports = []
        classes = []
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
        parts = []
        if classes:
            parts.append(f"defines classes {', '.join(classes[:5])}")
        if functions:
            parts.append(f"implements functions {', '.join(functions[:6])}")
        if imports:
            parts.append(f"uses {', '.join(list(dict.fromkeys(imports))[:6])}")
        return "Python module that " + "; ".join(parts) + "." if parts else "Python module with executable module-level logic."

    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        imports = re.findall(
            r"""(?m)^\s*import\s+(?:.+?\sfrom\s+)?['"]([^'"]+)['"]|^\s*(?:const|let|var)\s+.+?=\s*require\(\s*['"]([^'"]+)['"]""",
            source,
        )
        imports = [value for match in imports for value in match if value]
        exports = re.findall(r"\bexport\s+(?:default\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)", source)
        functions = re.findall(r"\b(?:function|async\s+function)\s+([A-Za-z_$][\w$]*)", source)
        components = re.findall(r"\b(?:function|const)\s+([A-Z][A-Za-z0-9_]*)", source)
        parts = []
        if components:
            parts.append(f"defines UI/components or major symbols {', '.join(list(dict.fromkeys(components))[:6])}")
        elif functions:
            parts.append(f"implements functions {', '.join(list(dict.fromkeys(functions))[:6])}")
        if exports:
            parts.append(f"exports {', '.join(list(dict.fromkeys(exports))[:6])}")
        if imports:
            parts.append(f"depends on {', '.join(list(dict.fromkeys(imports))[:6])}")
        return "JavaScript/TypeScript module that " + "; ".join(parts) + "." if parts else "JavaScript/TypeScript module with module-level logic."

    if suffix in {".md", ".rst"}:
        headings = re.findall(r"(?m)^\s{0,3}#{1,3}\s+(.+)$", source)
        return f"Documentation covering {', '.join(headings[:5])}." if headings else "Project documentation."

    if path.name.casefold() in {"package.json", "pyproject.toml", "requirements.txt", "cargo.toml", "go.mod"}:
        return "Project manifest describing dependencies, scripts, and runtime configuration."
    if path.name.casefold() in {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}:
        return "Container configuration describing how the project is built or run."
    return f"{language or 'Text'} file analyzed from its source structure."


def _file_relationships(root: Path, relative_path: str, language: str | None) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError("File not found.")
    source = path.read_text(encoding="utf-8", errors="ignore")[:250_000]
    files, _, _ = extract_repository_files(root)
    tracked = {item["path"]: item for item in files}
    file_record = tracked.get(relative_path, {})
    summary = _summarize_source_file(root, relative_path, language)
    imports: list[str] = []
    if path.suffix.casefold() == ".py":
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
        except SyntaxError:
            pass
    elif path.suffix.casefold() in {".js", ".jsx", ".ts", ".tsx"}:
        imports = [
            value
            for match in re.findall(
                r"""(?m)^\s*import\s+(?:.+?\sfrom\s+)?['"]([^'"]+)['"]|^\s*(?:const|let|var)\s+.+?=\s*require\(\s*['"]([^'"]+)['"]""",
                source,
            )
            for value in match
            if value
        ]
    local_imports = [value for value in dict.fromkeys(imports) if value.startswith((".", "/"))]
    relationships = []
    for imported in local_imports:
        candidate = (path.parent / imported).resolve()
        candidates = [candidate] + [
            candidate.with_suffix(suffix)
            for suffix in (".py", ".js", ".jsx", ".ts", ".tsx")
        ] + [candidate / "index.ts", candidate / "index.tsx", candidate / "__init__.py"]
        match = next(
            (item for item in candidates if item.is_file() and item.is_relative_to(root)),
            None,
        )
        if match:
            relationships.append({
                "path": match.relative_to(root).as_posix(),
                "type": "imports",
            })
    dependents = []
    for item_path, item in tracked.items():
        if item_path == relative_path:
            continue
        try:
            text = (root / item_path).read_text(encoding="utf-8", errors="ignore")[:100_000]
        except OSError:
            continue
        if Path(relative_path).stem in text and (
            relative_path in text or Path(relative_path).stem in text
        ):
            dependents.append({"path": item_path, "type": "references"})
    stem = path.stem.replace("_", " ").replace("-", " ")
    purpose = (
        f"It exists to implement the {stem} module in the repository."
        if stem
        else "It exists as part of the repository's implementation."
    )
    role = (
        "It is an application/source module that contributes executable behavior."
        if file_record.get("is_source")
        else "It is a supporting repository file used by tooling, configuration, or documentation."
    )
    return {
        "path": relative_path,
        "what": summary,
        "why": purpose,
        "role": role,
        "architecture": {
            "imports": relationships,
            "referenced_by": dependents[:40],
        },
    }


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(title="CodeDNA API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    init_db()

    @app.get("/")
    def api_root():
        return {"name": "CodeDNA API", "status": "ok", "docs": "/docs"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_repo_or_404(db, repo_id: int) -> Repository:
        repo = db.get(Repository, repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        return repo

    def _current_user(request: Request, db) -> User:
        token = request.cookies.get("codna_session")
        if not token:
            raise HTTPException(status_code=401, detail="Sign in required.")
        session = (
            db.query(AuthSession)
            .filter(
                AuthSession.token_hash == _session_hash(token),
                AuthSession.expires_at > utc_now(),
            )
            .first()
        )
        if session is None:
            raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
        user = db.get(User, session.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User account not found.")
        return user

    def _start_session(response: Response, db, user: User) -> None:
        token = secrets.token_urlsafe(32)
        db.add(
            AuthSession(
                token_hash=_session_hash(token),
                user_id=user.id,
                expires_at=utc_now() + timedelta(days=30),
            )
        )
        db.commit()
        response.set_cookie(
            "codna_session",
            token,
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
            secure=os.getenv("CODNA_COOKIE_SECURE", "").lower() == "true",
        )

    @app.post("/auth/register", status_code=201)
    def register(request_data: RegisterRequest, response: Response):
        db = get_session()
        try:
            email = request_data.email.strip().lower()
            if "@" not in email:
                raise HTTPException(status_code=422, detail="Enter a valid email address.")
            if db.query(User).filter(User.email == email).first():
                raise HTTPException(status_code=409, detail="An account with that email already exists.")
            user = User(
                email=email,
                display_name=request_data.display_name.strip(),
                password_hash=hash_password(request_data.password),
                provider="email",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            _start_session(response, db, user)
            return _public_user(user)
        finally:
            db.close()

    @app.post("/auth/login")
    def login(request_data: LoginRequest, response: Response):
        db = get_session()
        try:
            user = db.query(User).filter(User.email == request_data.email.strip().lower()).first()
            if user is None or not user.password_hash or not verify_password(request_data.password, user.password_hash):
                raise HTTPException(status_code=401, detail="Invalid email or password.")
            _start_session(response, db, user)
            return _public_user(user)
        finally:
            db.close()

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request, response: Response):
        db = get_session()
        try:
            token = request.cookies.get("codna_session")
            if token:
                db.query(AuthSession).filter(AuthSession.token_hash == _session_hash(token)).delete()
                db.commit()
            response.delete_cookie("codna_session")
        finally:
            db.close()

    @app.get("/auth/me")
    def me(request: Request):
        db = get_session()
        try:
            return _public_user(_current_user(request, db))
        finally:
            db.close()

    @app.get("/auth/{provider}/start")
    def oauth_start(provider: str):
        if provider not in {"google", "github"}:
            raise HTTPException(status_code=404, detail="Unsupported sign-in provider.")
        try:
            return RedirectResponse(oauth_authorization_url(provider, create_oauth_state(provider)))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/auth/{provider}/callback")
    def oauth_callback(request: Request, provider: str, code: str, state: str):
        if provider not in {"google", "github"}:
            raise HTTPException(status_code=400, detail="Invalid OAuth callback.")
        try:
            if not verify_oauth_state(state, provider):
                raise HTTPException(status_code=400, detail="Invalid OAuth callback.")
            profile = exchange_oauth_code(provider, code)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("OAuth exchange failed for %s", provider)
            raise HTTPException(status_code=502, detail="OAuth sign-in failed.") from exc
        email = (profile.get("email") or "").strip().lower()
        subject = str(profile.get("sub") or profile.get("id") or "")
        display_name = profile.get("name") or profile.get("login") or email
        if not email or not subject:
            raise HTTPException(status_code=400, detail="OAuth provider did not return a usable profile.")
        db = get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(email=email, display_name=display_name, provider=provider, provider_subject=subject)
                db.add(user)
                db.commit()
                db.refresh(user)
            frontend = os.getenv("CODNA_FRONTEND_URL") or str(request.base_url).rstrip("/") + "/dashboard"
            redirect = RedirectResponse(f"{frontend}/?auth=success")
            _start_session(redirect, db, user)
            return redirect
        finally:
            db.close()

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
    @app.post("/repositories", status_code=201)
    def register_repository(repo_in: RepositoryCreate):
        if repo_in.repo_url:
            from .git_utils import parse_github_url

            try:
                parse_github_url(repo_in.repo_url)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Invalid GitHub repository URL. Please enter a URL such "
                        "as https://github.com/user/repository."
                    ),
                ) from exc

            default_data_root = Path("/tmp/codna-data") if os.getenv("VERCEL") else Path.home() / ".codedna"
            data_root = Path(os.getenv("CODNA_DATA_DIR", default_data_root))
            try:
                metadata, local_path = ingest_public_github_repository(
                    repo_in.repo_url, data_root
                )
            except RepositoryUnavailableError as exc:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Repository could not be found. It may be private or "
                        "inaccessible; public repositories are currently supported."
                    ),
                ) from exc
            except RepositoryFetchError as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Unable to fetch repository. Please try again.",
                ) from exc

            db = get_session()
            try:
                repository = Repository(
                    repo_url=metadata["url"],
                    local_path=str(local_path),
                    status="ingested",
                )
                db.add(repository)
                db.flush()
                db.add(RepositorySnapshot(
                    repo_id=repository.id,
                    metadata_json=json.dumps(metadata),
                ))
                db.commit()
                db.refresh(repository)
                return {"id": repository.id, **public_repository_data(metadata)}
            except Exception:
                db.rollback()
                logger.exception("Failed to persist ingested repository %s", metadata["url"])
                raise
            finally:
                db.close()

        if not repo_in.local_path.strip():
            raise HTTPException(
                status_code=422,
                detail="Provide a public GitHub repository URL or a local directory path.",
            )

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

    @app.get("/repositories/{repo_id}/tree")
    def get_repository_tree(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(
                    status_code=400, detail="Repository path not found"
                )

            files, directories, languages = extract_repository_files(root)

            last_job = (
                db.query(AnalysisJob)
                .filter(
                    AnalysisJob.repo_id == repo_id,
                    AnalysisJob.status == "completed",
                )
                .order_by(AnalysisJob.completed_at.desc())
                .first()
            )
            snapshot = (
                db.query(RepositorySnapshot)
                .filter_by(repo_id=repo_id)
                .first()
            )
            return {
                "root": root.name,
                "files": files,
                "file_count": len(files),
                "directory_count": len(directories),
                "languages": languages,
                "last_analyzed_at": (
                    last_job.completed_at.isoformat()
                    if last_job and last_job.completed_at
                    else snapshot.created_at.isoformat()
                    if snapshot
                    else None
                ),
            }
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/commits")
    def get_repository_commits(
        repo_id: int,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ):
        db = get_session()
        try:
            _get_repo_or_404(db, repo_id)
            snapshot = (
                db.query(RepositorySnapshot)
                .filter_by(repo_id=repo_id)
                .first()
            )
            commits = (
                json.loads(snapshot.metadata_json).get("commits", [])
                if snapshot
                else []
            )
            return {
                "total": len(commits),
                "offset": offset,
                "limit": limit,
                "commits": [
                    {
                        key: value
                        for key, value in commit.items()
                        if key != "author_email"
                    }
                    for commit in commits[offset : offset + limit]
                ],
            }
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/components")
    def get_repository_components(repo_id: int):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            snapshot = (
                db.query(RepositorySnapshot)
                .filter_by(repo_id=repo_id)
                .first()
            )
            metadata = json.loads(snapshot.metadata_json) if snapshot else {}
            files = metadata.get("files", [])
            languages = metadata.get("languages", {})
            name = metadata.get("name") or repo.repo_url or "This repository"
            root = Path(repo.local_path).resolve()

            ranked = sorted(
                files,
                key=lambda item: (
                    not item.get("is_source", False),
                    item.get("size", 0) == 0,
                    -item.get("size", 0),
                    item.get("path", "").casefold(),
                ),
            )
            major_files = [
                {
                    "path": item.get("path", ""),
                    "language": item.get("language"),
                    "size": item.get("size", 0),
                    "description": _summarize_source_file(
                        root, item.get("path", ""), item.get("language")
                    ),
                }
                for item in ranked[:40]
            ]
            language_names = sorted(
                languages.items(), key=lambda item: item[1], reverse=True
            )
            primary_language = language_names[0][0] if language_names else "multiple languages"
            return {
                "name": name,
                "gist": (
                    f"{name} is a {primary_language} repository with "
                    f"{len(files)} tracked files across {len(metadata.get('directories', []))} directories. "
                    "Its structure is summarized below from the analyzed repository inventory."
                ),
                "file_count": len(files),
                "directory_count": len(metadata.get("directories", [])),
                "commit_count": metadata.get("commit_count", 0),
                "languages": dict(language_names),
                "major_files": major_files,
            }
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/files/analysis")
    def get_file_analysis(repo_id: int, path: str):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=404, detail="Repository is unavailable.")
            if not path or "\\" in path or ":" in path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise HTTPException(status_code=422, detail="Invalid repository path.")
            try:
                snapshot = db.query(RepositorySnapshot).filter_by(repo_id=repo_id).first()
                files = json.loads(snapshot.metadata_json).get("files", []) if snapshot else []
                file = next((item for item in files if item.get("path") == path), None)
                return _file_relationships(root, path, file.get("language") if file else None)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="File not found.") from exc
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/branches/files")
    def get_branch_files(repo_id: int, branch: str):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=404, detail="Repository is unavailable.")
            try:
                return branch_files(root, branch)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Branch not found.") from exc
            except (
                ValueError,
                GitCommandError,
                InvalidGitRepositoryError,
                NoSuchPathError,
            ) as exc:
                raise HTTPException(
                    status_code=400, detail="Git history is unavailable for this repository."
                ) from exc
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/merge-conflicts")
    def get_merge_conflicts(repo_id: int, base_branch: str, compare_branch: str):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=404, detail="Repository is unavailable.")
            try:
                return _merge_conflict_analysis(root, base_branch, compare_branch)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Branch not found.") from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except (GitCommandError, InvalidGitRepositoryError, NoSuchPathError) as exc:
                raise HTTPException(
                    status_code=400, detail="Git conflict analysis is unavailable."
                ) from exc
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/branches/history")
    def get_branch_history(
        repo_id: int,
        max_commits: int = Query(300, ge=1, le=1000),
        max_branches: int = Query(100, ge=1, le=500),
    ):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=404, detail="Repository is unavailable.")

            from git import Repo as GitRepo

            try:
                git_repo = GitRepo(root)
                remote_refs = {
                    ref.remote_head: ref
                    for remote in git_repo.remotes
                    for ref in remote.refs
                    if ref.remote_head != "HEAD"
                }
                refs = remote_refs or {branch.name: branch for branch in git_repo.branches}
                default_branch = (
                    git_repo.active_branch.name
                    if not git_repo.head.is_detached
                    else None
                )
                branches = []
                sorted_refs = sorted(
                    refs.items(),
                    key=lambda item: item[0] == default_branch,
                    reverse=True,
                )[:max_branches]
                for name, ref in sorted_refs:
                    commits = list(git_repo.iter_commits(ref, max_count=max_commits))
                    branches.append({
                        "name": name,
                        "is_default": name == default_branch,
                        "commits": [
                            {
                                "hash": commit.hexsha,
                                "short_hash": commit.hexsha[:8],
                                "message": commit.message.strip().splitlines()[0],
                                "author": commit.author.name or "",
                                "date": commit.committed_datetime.isoformat(),
                                "parents": [parent.hexsha for parent in commit.parents],
                            }
                            for commit in reversed(commits)
                        ],
                    })
                return {"default_branch": default_branch, "branches": branches}
            except (
                GitCommandError,
                InvalidGitRepositoryError,
                NoSuchPathError,
            ) as exc:
                raise HTTPException(
                    status_code=400, detail="Git history is unavailable for this repository."
                ) from exc
        finally:
            db.close()

    @app.get("/repositories/{repo_id}/files/history")
    def get_file_history(
        repo_id: int,
        path: str,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        db = get_session()
        try:
            repo = _get_repo_or_404(db, repo_id)
            root = Path(repo.local_path).resolve()
            if not root.is_dir():
                raise HTTPException(status_code=404, detail="Repository is unavailable.")
            try:
                return file_history(root, path, limit)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Invalid repository path.") from exc
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="File or directory not found.") from exc
            except (
                GitCommandError,
                InvalidGitRepositoryError,
                NoSuchPathError,
            ) as exc:
                raise HTTPException(
                    status_code=400, detail="Git history is unavailable for this repository."
                ) from exc
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
            job.completed_at = utc_now()
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
            snapshot = (
                db.query(RepositorySnapshot)
                .filter_by(repo_id=repo_id)
                .first()
            )
            return {
                "repository": {
                    "id": repo.id,
                    "repo_url": repo.repo_url,
                    "local_path": repo.local_path,
                    "status": repo.status,
                },
                "ingestion": (
                    {
                        **public_repository_data(json.loads(snapshot.metadata_json)),
                        "ingested_at": snapshot.created_at.isoformat(),
                    }
                    if snapshot
                    else None
                ),
                "message": (
                    "Repository metadata is available from the GitHub ingestion snapshot."
                    if snapshot
                    else "No GitHub ingestion snapshot is available for this repository."
                ),
            }
        finally:
            db.close()

    return app


app = create_app()
