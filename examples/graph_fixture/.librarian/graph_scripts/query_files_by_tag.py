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
    tag_filter = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    graph = load_graph()
    nodes = nodes_by_id(graph)
    tag_nodes = {node["id"]: node for node in graph.get("nodes", []) if node.get("type") == "Tag"}
    found = False
    for edge in graph.get("edges", []):
        if edge.get("type") != "HAS_TAG":
            continue
        tag = tag_nodes.get(edge.get("target"), {})
        tag_label = tag.get("label", "")
        if tag_filter and tag_label.lower() != tag_filter:
            continue
        found = True
        source = nodes.get(edge.get("source"), {})
        print(f"{tag_label}: {file_label(source)}")
    if not found:
        print("No files found for tag." if tag_filter else "No tagged files found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
