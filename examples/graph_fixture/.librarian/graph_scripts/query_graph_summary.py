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
    node_types = Counter(node.get("type", "Node") for node in graph.get("nodes", []))
    edge_types = Counter(edge.get("type", "RELATED_TO") for edge in graph.get("edges", []))
    print("Graph summary")
    print(f"- nodes: {len(graph.get('nodes', []))}")
    print(f"- edges: {len(graph.get('edges', []))}")
    print("- top node types:")
    for name, count in node_types.most_common(10):
        print(f"  - {name}: {count}")
    print("- top edge types:")
    for name, count in edge_types.most_common(10):
        print(f"  - {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
