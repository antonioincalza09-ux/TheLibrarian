from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any


try:  # pragma: no cover - exercised when networkx is installed.
    import networkx as nx
except ModuleNotFoundError:  # pragma: no cover - covered indirectly in minimal envs.
    nx = None


class MiniDiGraph:
    """Small fallback used only when networkx is not installed yet."""

    def __init__(self) -> None:
        self.graph: dict[str, Any] = {}
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[tuple[str, str], dict[str, Any]] = {}

    def add_node(self, node_id: str, **attrs: Any) -> None:
        existing = self._nodes.setdefault(node_id, {})
        existing.update(attrs)

    def add_edge(self, source: str, target: str, **attrs: Any) -> None:
        self._edges[(source, target)] = dict(attrs)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def nodes(self, data: bool = False) -> Iterable[str] | Iterable[tuple[str, dict[str, Any]]]:
        return self._nodes.items() if data else self._nodes.keys()

    def edges(self, data: bool = False) -> Iterable[tuple[str, str]] | Iterable[tuple[str, str, dict[str, Any]]]:
        if data:
            return ((source, target, attrs) for (source, target), attrs in self._edges.items())
        return self._edges.keys()

    def number_of_nodes(self) -> int:
        return len(self._nodes)

    def number_of_edges(self) -> int:
        return len(self._edges)


def new_digraph():
    if nx is not None:
        return nx.DiGraph()
    return MiniDiGraph()


def iter_nodes(graph) -> Iterator[tuple[str, dict[str, Any]]]:
    yield from graph.nodes(data=True)


def iter_edges(graph) -> Iterator[tuple[str, str, dict[str, Any]]]:
    yield from graph.edges(data=True)
