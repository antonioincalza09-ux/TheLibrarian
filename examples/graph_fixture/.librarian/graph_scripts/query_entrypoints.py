from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_graph() -> dict:
    graph_path = workspace_root() / ".librarian" / "graph.json"
    if not graph_path.exists():
        raise SystemExit("graph.json not found. Run `librarian graph build <path>` first.")
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"graph.json is invalid: {exc}") from exc


def nodes_by_id(graph: dict) -> dict:
    return {node["id"]: node for node in graph.get("nodes", [])}


def file_label(node: dict) -> str:
    props = node.get("properties", {})
    return props.get("current_path") or props.get("path") or node.get("label", node.get("id", "-"))



def main() -> int:
    graph = load_graph()
    nodes = nodes_by_id(graph)
    found = False
    for edge in graph.get("edges", []):
        if edge.get("type") != "HAS_ENTRYPOINT":
            continue
        found = True
        source = nodes.get(edge.get("source"), {})
        target = nodes.get(edge.get("target"), {})
        print(f"{file_label(source)} -> {target.get('label', '-')}")
    if not found:
        print("No entrypoints found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
