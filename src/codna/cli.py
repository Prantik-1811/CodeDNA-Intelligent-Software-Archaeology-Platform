"""Command-line interface for CodeDNA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .git_utils import clone_repository
from .scanner import RepositoryScanner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codna", description="CodeDNA repository scanner"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="GitHub repository URL to clone and scan")
    group.add_argument("--path", help="Local project directory to scan")
    parser.add_argument(
        "--output",
        "-o",
        default="repository_summary.json",
        help="Output JSON file path",
    )
    args = parser.parse_args(argv)

    if args.url:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "repo"
            clone_repository(args.url, dest)
            scanner = RepositoryScanner(dest, repo_url=args.url)
            scanner.save_json(args.output)
    else:
        root = Path(args.path)
        if not root.is_dir():
            print(f"Error: {root} is not a directory", file=sys.stderr)
            return 1
        scanner = RepositoryScanner(root)
        scanner.save_json(args.output)

    print(f"Repository summary written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
