from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.librarian.graph.builder import build_graph
from src.librarian.graph.exporters import export_graph_json, graph_to_payload


def load_graph_json(root: str | Path) -> dict[str, Any]:
    graph_path = Path(root).resolve() / ".librarian" / "graph.json"
    if not graph_path.exists():
        graph = build_graph(root)
        export_graph_json(graph, root)
    return json.loads(graph_path.read_text(encoding="utf-8"))


def build_payload(root: str | Path) -> dict[str, Any]:
    graph = build_graph(root)
    return graph_to_payload(graph).model_dump(mode="json")
