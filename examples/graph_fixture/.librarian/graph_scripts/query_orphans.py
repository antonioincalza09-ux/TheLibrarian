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
    file_nodes = [
        node for node in graph.get("nodes", [])
        if node.get("type") in {"File", "CodeFile", "ConfigFile", "GeneratedFile", "VendorFile", "LockFile"}
    ]
    tagged = {edge.get("source") for edge in graph.get("edges", []) if edge.get("type") == "HAS_TAG"}
    documented = {edge.get("source") for edge in graph.get("edges", []) if edge.get("type") == "DOCUMENTED_BY"}
    orphans = [node for node in file_nodes if node.get("id") not in tagged and node.get("id") not in documented]
    if not orphans:
        print("No obvious graph orphans found.")
        return 0
    for node in orphans:
        print(file_label(node))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
