"""Data structures for the dependency graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """A node in the dependency graph."""

    id: str
    type: str  # "file", "function", "class"
    label: str
    file_path: str
    line: int
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge in the dependency graph."""

    source: str
    target: str
    type: str  # "imports", "calls", "inherits", "contains"
    line: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyGraphData:
    """Serializable graph representation."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "label": n.label,
                    "file_path": n.file_path,
                    "line": n.line,
                    "language": n.language,
                    "metadata": n.metadata,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.type,
                    "line": e.line,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
            "cycles": self.cycles,
            "metrics": self.metrics,
        }
