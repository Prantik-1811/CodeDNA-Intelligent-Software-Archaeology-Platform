# CodeDNA Architecture & Limitations

## Architecture Overview

CodeDNA is a 10-week software archaeology platform built as a layered Python
application with a React TypeScript frontend.

### Layer 1: Repository Ingestion (Week 1)
- `src/codna/git_utils.py` — GitPython-based cloning and Git metadata
- `src/codna/walker.py` — Directory tree walking with ignore rules
- `src/codna/language.py` — Language detection from file extensions
- `src/codna/metadata.py` — File metadata (size, lines, SHA-256)
- `src/codna/scanner.py` — Orchestrates scanning, emits JSON summary
- `src/codna/cli.py` — CLI entry point (`--url` / `--path` / `--output`)

### Layer 2: AST Parsing Engine (Week 2)
- `src/codna/ast_parser.py` — Tree-sitter backed parser
  - Extracts functions, classes, methods, parameters, return types
  - Extracts imports and exports
  - Records file locations (line/column ranges)
- Data models: `Parameter`, `Function`, `Class`, `Import`, `FileAST`

### Layer 3: Dependency Graph Engine (Week 3)
- `src/codna/dependency_graph.py` — NetworkX DiGraph builder
  - File-level import dependencies with module resolution
  - Function-level call graph
  - Class inheritance mapping
  - Circular import detection
  - In-degree / out-degree computation
- `src/codna/graph_models.py` — `GraphNode`, `GraphEdge`, `GraphData`

### Layer 4: Code Complexity & Architecture (Week 4)
- `src/codna/metrics.py` — Cyclomatic complexity, LOC breakdown
- `src/codna/architecture.py` — ArchitectureAnalyzer
  - Graph centrality (degree, betweenness, closeness)
  - Highly connected modules, large & coupled files
  - Bottleneck detection

### Layer 5: Git History Intelligence (Week 5)
- `src/codna/git_history.py` — GitHistoryAnalyzer
  - Commit histories, file change frequencies
  - Contributor tracking
  - Co-changing file detection
  - Symbol change tracking (functions/classes across commits)

### Layer 6: Change Impact Analysis (Week 6)
- `src/codna/change_impact.py` — ChangeImpactAnalyzer
  - Direct callers, affected modules, affected tests
  - Co-changing files from git history
  - Ranked review components with risk scoring (0-100)

### Layer 7: Bug Prediction & Risk Engine (Week 7)
- `src/codna/risk_engine.py` — RiskEngine
  - Weighted scoring: complexity (25%), change frequency (20%),
    contributors (15%), dependency centrality (20%), bug-fix commits (10%),
    code churn (10%)
  - 0-100 risk score, critical/high/medium/low levels

### Layer 8: FastAPI Backend (Week 8)
- `src/codna/api.py` — REST API with 8 endpoints
- `src/codna/database.py` — SQLAlchemy models (Repository, AnalysisJob,
  ModuleRisk, ImpactReport)
- `src/codna/schemas.py` — Pydantic request/response schemas
- Background job processing via FastAPI BackgroundTasks

### Layer 9: React Dashboard (Week 9)
- `dashboard/` — React 18 + TypeScript + Vite + Tailwind CSS
- Screens: Repository List, Overview, Dependency Graph, Risk Heatmap,
  Change Impact Explorer

## Limitations

1. **Tree-sitter language support**: Currently only Python is fully supported.
   Other languages require additional tree-sitter grammars.

2. **Call graph resolution**: Function-level call resolution is limited to
   same-file calls and simple name matching. Cross-file call resolution
   relies on import-based name matching which may miss dynamic calls.

3. **Risk model transparency**: The risk engine uses a transparent weighted
   scoring model (not ML). Scores are investigation priorities, not proof
   that a file contains bugs. False positives and negatives are possible.

4. **Git history depth**: Symbol change tracking compares consecutive commits
   per file and may miss changes spanning multiple commits or rename detection.

5. **Performance**: Tree-sitter parsing creates a new Parser instance per file
   for stability, which can be slow for very large repositories. Graph
   operations (betweenness centrality) are O(N*M) and may be slow on very
   large graphs.

6. **Dashboard**: The React dashboard connects to a single repository at a
   time and does not yet support multi-repo comparison.

## Future Work

1. Add tree-sitter grammars for JavaScript, TypeScript, Java, Go, Rust, etc.
2. Implement ML-based bug prediction model to compare with heuristic scoring
3. Add cross-file call graph resolution using symbol tables
4. Add repository comparison and trend analysis views to dashboard
5. Add user authentication and role-based access control
6. Add scheduled/periodic re-analysis of registered repositories
7. Add export of analysis results (CSV, PDF, SARIF)
8. Add CI/CD integration (GitHub Actions, GitLab CI)

## Performance Benchmarks

Run `python benchmarks/parse_benchmark.py` to measure AST parsing and graph
building performance on the current codebase.

## Deployment

```bash
# Backend only
docker build -t codna-backend .
docker run -p 8000:8000 codna-backend

# Full stack
docker-compose up
```
