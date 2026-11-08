"""Unit tests for the repository scanner."""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

from codna.scanner import RepositoryScanner
from codna.walker import RepoWalker
from codna.language import detect_language, is_source_file, group_files_by_language
from codna.git_utils import is_ignored_git


def test_walker_ignores_git():
    walker = RepoWalker(Path("."))
    files = walker.walk_files()
    paths = [str(f) for f in files]
    # Check that no path part is exactly ".git" (VCS dir)
    assert not any(".git" == p for f in files for p in f.relative_to(Path(".").resolve()).parts)


def test_walker_ignores_node_modules():
    walker = RepoWalker(Path("."))
    files = walker.walk_files()
    paths = [str(f) for f in files]
    assert not any("node_modules" in p for p in paths)


def test_walker_ignores_generated_directories_and_supports_custom_patterns(tmp_path):
    ignored_names = [
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        "coverage",
    ]
    for name in ignored_names:
        directory = tmp_path / "nested" / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "ignored.py").write_text("", encoding="utf-8")
    keep = tmp_path / "src" / "keep.py"
    keep.parent.mkdir()
    keep.write_text("", encoding="utf-8")

    files = RepoWalker(tmp_path).walk_files()
    assert files == [keep]

    generated = tmp_path / "generated" / "file.py"
    generated.parent.mkdir()
    generated.write_text("", encoding="utf-8")
    assert generated in RepoWalker(tmp_path, ignore_patterns=[]).walk_files()
    assert generated not in RepoWalker(
        tmp_path, ignore_patterns=["generated/**"]
    ).walk_files()


def test_detect_language_python():
    lang = detect_language(Path("foo.py"))
    assert lang is not None
    assert lang.name == "python"


def test_detect_language_unknown():
    lang = detect_language(Path("foo.xyz"))
    assert lang is None


def test_is_source_file_python():
    assert is_source_file(Path("foo.py")) is True


def test_is_source_file_markdown():
    assert is_source_file(Path("README.md")) is False


def test_group_files_by_language():
    files = [Path("a.py"), Path("b.js"), Path("c.py"), Path("d.xyz")]
    grouped = group_files_by_language(files)
    assert "python" in grouped
    assert "javascript" in grouped
    assert "unknown" in grouped
    assert len(grouped["python"]) == 2


def test_is_ignored_git():
    assert is_ignored_git(Path("/foo/.git/config")) is True
    assert is_ignored_git(Path("/foo/.git/HEAD")) is True
    assert is_ignored_git(Path("/foo/bar.py")) is False


def test_scanner_produces_json():
    root = Path(".")
    scanner = RepositoryScanner(root)
    result = scanner.scan()
    assert "repo_url" in result.repository
    assert "local_path" in result.repository
    assert "total_files" in result.summary

    js = scanner.to_json()
    data = json.loads(js)
    assert "repository" in data
    assert "summary" in data
    assert "files" in data


def test_scanner_output_has_language_breakdown():
    root = Path(".")
    scanner = RepositoryScanner(root)
    result = scanner.scan()
    assert "languages" in result.summary
    assert "python" in result.summary["languages"]


def test_scanner_supports_non_git_directory_and_explicit_url(tmp_path):
    (tmp_path / "example.py").write_text("print('hello')\n", encoding="utf-8")

    result = RepositoryScanner(
        tmp_path, repo_url="https://example.com/example.git"
    ).scan()

    assert result.repository["repo_url"] == "https://example.com/example.git"
    assert result.summary["source_files"] == 1
