# Contributing to CodeDNA

Thank you for your interest in contributing to CodeDNA! We welcome contributions
from the community and are grateful for your time and effort.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [How to Contribute](#how-to-contribute)
- [Commit Guidelines](#commit-guidelines)
- [Code Review](#code-review)
- [License](#license)

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/CodeDNA-Intelligent-Software-Archaeology-Platform.git
   cd CodeDNA-Intelligent-Software-Archaeology-Platform
   ```
3. Create a new branch for your contribution:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Backend (Python)

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

### Frontend (React Dashboard)

```bash
cd dashboard
npm install
```

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

## How to Contribute

### Reporting Bugs

Please use the GitHub issue tracker to report bugs. Include:
- A clear title and description
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment (OS, Python version, etc.)
- Any relevant error messages or logs

### Suggesting Enhancements

Open an issue describing your proposed enhancement, including:
- The problem it solves
- A detailed description of the solution
- Any trade-offs or alternatives considered

### Submitting Pull Requests

1. Ensure your fork is up to date with `main`
2. Create a feature branch from `main`
3. Make your changes
4. Run tests: `python -m pytest tests/`
5. Run type check: `npx tsc --noEmit` (for frontend changes)
6. Commit your changes with a descriptive message
7. Push to your fork and open a pull request

## Commit Guidelines

We follow conventional commit messages:

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`

Example: `feat(ast-parser): add support for function decorators`

## Code Review

All pull requests require review from at least one maintainer. Please be
patient and responsive to review feedback.

## License

By contributing to CodeDNA, you agree that your contributions will be licensed
under the project's LICENSE.
