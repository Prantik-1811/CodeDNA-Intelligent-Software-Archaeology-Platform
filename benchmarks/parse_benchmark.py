"""Performance benchmarks for the CodeDNA analysis pipeline."""

import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from codna.walker import RepoWalker
from codna.language import detect_language, is_source_file
from codna.ast_parser import parse_file
from codna.dependency_graph import DependencyGraph
from codna.metrics import compute_file_metrics


def benchmark_parsing(root: Path = Path("src/codna")):
    """Benchmark AST parsing performance across all source files."""
    walker = RepoWalker(root)
    files = walker.walk_files()
    source_files = [
        f for f in files
        if is_source_file(f) and detect_language(f) is not None
    ]

    times = []
    for f in source_files:
        start = time.perf_counter()
        ast = parse_file(f, root, language=detect_language(f).name)
        elapsed = time.perf_counter() - start
        times.append((f.name, elapsed, ast is not None))

    total_time = sum(t for _, t, _ in times)
    success_count = sum(1 for _, _, ok in times if ok)

    print(f"Files parsed: {len(source_files)}")
    print(f"Successful: {success_count}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Average per file: {total_time / len(source_files) * 1000:.2f}ms")
    print(f"Fastest: {min(t for _, t, _ in times) * 1000:.2f}ms")
    print(f"Slowest: {max(t for _, t, _ in times) * 1000:.2f}ms")

    # Show slowest files
    sorted_times = sorted(times, key=lambda x: x[1], reverse=True)
    print("\nSlowest files:")
    for name, t, _ in sorted_times[:5]:
        print(f"  {name}: {t * 1000:.2f}ms")

    return total_time, len(source_files), success_count


def benchmark_graph_build(root: Path = Path("src/codna")):
    """Benchmark dependency graph building."""
    walker = RepoWalker(root)
    files = walker.walk_files()
    file_asts = []
    file_paths = []
    for f in files:
        lang = detect_language(f)
        if not is_source_file(f):
            continue
        ast = parse_file(f, root, language=lang.name)
        if ast:
            ast.path = str(f)
            file_asts.append(ast)
            file_paths.append(f)

    start = time.perf_counter()
    dg = DependencyGraph()
    data = dg.build_from_files(file_asts, file_paths, root)
    elapsed = time.perf_counter() - start

    print(f"\nGraph build:")
    print(f"  Nodes: {data.metrics['node_count']}")
    print(f"  Edges: {data.metrics['edge_count']}")
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Metrics: {data.metrics}")

    return elapsed, data.metrics


if __name__ == "__main__":
    print("=== CodeDNA Performance Benchmarks ===\n")
    benchmark_parsing()
    benchmark_graph_build()
