from __future__ import annotations

from pathlib import Path


def generate_graph_scripts(root: str | Path) -> list[Path]:
    resolved_root = Path(root).resolve()
    scripts_dir = resolved_root / ".librarian" / "graph_scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    scripts = {
        "query_graph_summary.py": _summary_script(),
        "query_entrypoints.py": _entrypoints_script(),
        "query_risks.py": _risks_script(),
        "query_dependencies.py": _dependencies_script(),
        "query_tests.py": _tests_script(),
        "query_files_by_tag.py": _files_by_tag_script(),
        "query_orphans.py": _orphans_script(),
    }
    written: list[Path] = []
    for name, content in scripts.items():
        path = scripts_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def _prelude() -> str:
    return '''from __future__ import annotations

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


'''


def _summary_script() -> str:
    return _prelude() + '''
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
'''


def _entrypoints_script() -> str:
    return _prelude() + '''
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
'''


def _risks_script() -> str:
    return _prelude() + '''
def main() -> int:
    graph = load_graph()
    nodes = nodes_by_id(graph)
    found = False
    for edge in graph.get("edges", []):
        if edge.get("type") not in {"HAS_RISK", "SHOULD_NOT_MODIFY"}:
            continue
        found = True
        source = nodes.get(edge.get("source"), {})
        target = nodes.get(edge.get("target"), {})
        print(f"{file_label(source)} -> {target.get('label', '-')} ({edge.get('type')})")
    if not found:
        print("No risks found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _dependencies_script() -> str:
    return _prelude() + '''
def main() -> int:
    graph = load_graph()
    nodes = nodes_by_id(graph)
    imports = [edge for edge in graph.get("edges", []) if edge.get("type") == "IMPORTS"]
    if not imports:
        print("No dependencies found.")
        return 0
    for edge in imports:
        source = nodes.get(edge.get("source"), {})
        target = nodes.get(edge.get("target"), {})
        print(f"{file_label(source)} imports {target.get('label', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _tests_script() -> str:
    return _prelude() + '''
def main() -> int:
    graph = load_graph()
    nodes = nodes_by_id(graph)
    tests = [node for node in graph.get("nodes", []) if node.get("type") == "Test"]
    if not tests:
        print("No tests found.")
        return 0
    targets = {edge.get("source"): edge.get("target") for edge in graph.get("edges", []) if edge.get("type") == "TESTS"}
    for test in tests:
        target = nodes.get(targets.get(test.get("id")), {})
        print(f"{test.get('label', '-')} -> {file_label(target) if target else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _files_by_tag_script() -> str:
    return _prelude() + '''
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
'''


def _orphans_script() -> str:
    return _prelude() + '''
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
'''
