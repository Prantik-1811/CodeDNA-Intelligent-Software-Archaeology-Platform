# Kilo Agent Instructions

This is the CodeDNA project - an Intelligent Software Archaeology Platform built over 10 weeks.

## Project Structure

```
src/codna/           # Python backend package
  git_utils.py       # Week 1: Git cloning & metadata
  walker.py          # Week 1: Directory walking with ignore rules
  language.py        # Week 1: Language detection
  metadata.py        # Week 1: File metadata extraction
  scanner.py         # Week 1: Repository scanner orchestrator
  cli.py             # Week 1: CLI entry point
  ast_parser.py      # Week 2: Tree-sitter AST parser
  dependency_graph.py # Week 3: NetworkX dependency graph builder
  graph_models.py    # Week 3: Graph data models
  metrics.py         # Week 4: Code complexity metrics
  architecture.py    # Week 4: Architecture analyzer
  git_history.py     # Week 5: Git history analyzer
  change_impact.py   # Week 6: Change impact analyzer
  risk_engine.py     # Week 7: Bug prediction risk engine
  api.py             # Week 8: FastAPI backend
  database.py        # Week 8: SQLAlchemy models
  schemas.py         # Week 8: Pydantic schemas
tests/               # Week 10: Unit tests (pytest)
benchmarks/          # Week 10: Performance benchmarks
dashboard/           # Week 9: React + TypeScript frontend
```

## Key Commands

### Backend (Python)
- `python -m pytest tests/` - Run unit tests
- `python -m pytest tests/test_api_integration.py` - Run API integration tests
- `python benchmarks/parse_benchmark.py` - Run performance benchmarks
- `uvicorn codna.api:app --reload --host 0.0.0.0 --port 8000` - Start API server
- `python -m codna.cli --path <dir> -o summary.json` - Scan a repository

### Frontend (dashboard/)
- `npm install` - Install dependencies
- `npm run dev` - Start Vite dev server (port 5173)
- `npx tsc --noEmit` - TypeScript type check

### Docker
- `docker build -t codna-backend .` - Build backend image
- `docker-compose up` - Start full stack

## Testing Conventions

- All tests live in `tests/` directory
- Unit tests use plain pytest (no fixtures needed for core modules)
- API integration tests use FastAPI TestClient
- Test files are named `test_<module>.py`
- Run `python -m pytest tests/` to execute all tests

## Branch Strategy

- `main` - Weeks 1-3 (scanner, AST parser, dependency graph)
- `week4-complexity-analysis` - Week 4
- `week5-git-history` - Week 5
- `week6-change-impact` - Week 6
- `week7-risk-engine` - Week 7 (merged weeks 4-7)
- `week8-fastapi-backend` - Week 8
- `week9-react-dashboard` - Week 9
- `week10-testing-deployment` - Week 10 (current)

## Important Notes

- Do not commit `node_modules/` or `.pytest_cache/`
- The dashboard connects to the FastAPI backend at `http://localhost:8000`
- Set `VITE_API_BASE_URL` to override the API base URL
- Tree-sitter parsing creates a fresh Parser per file for stability
- Risk scores are investigation priorities, not proof of bugs
