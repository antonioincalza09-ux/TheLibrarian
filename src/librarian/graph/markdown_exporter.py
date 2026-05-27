from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from src.librarian.graph.exporters import graph_to_payload
from src.librarian.graph.graph_queries import query_entrypoints, query_modules, query_risks, query_tags
from src.librarian.graph.utils import markdown_escape


NOTE_FILES = [
    "index.md",
    "graph_summary.md",
    "entrypoints.md",
    "modules.md",
    "packages.md",
    "functions.md",
    "classes.md",
    "dependencies.md",
    "tests.md",
    "risks.md",
    "tags.md",
    "entities.md",
    "projects.md",
    "runnable_scripts.md",
    "agent_start_here.md",
]


def export_markdown_notes(graph, root: str | Path) -> Path:
    output_dir = Path(root).resolve() / ".librarian" / "graph_notes"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = graph_to_payload(graph)
    nodes_by_type: dict[str, list] = defaultdict(list)
    for node in payload.nodes:
        nodes_by_type[node.type].append(node)
    edges_by_type = Counter(edge.type for edge in payload.edges)

    files = [node for node in payload.nodes if node.type in {"File", "CodeFile", "ConfigFile", "GeneratedFile", "VendorFile", "LockFile"}]
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for edge in payload.edges:
        outgoing[edge.source].append(edge)
        incoming[edge.target].append(edge)

    (output_dir / "index.md").write_text(_index(), encoding="utf-8")
    (output_dir / "graph_summary.md").write_text(_summary(payload, nodes_by_type, edges_by_type), encoding="utf-8")
    (output_dir / "entrypoints.md").write_text(_entrypoints(graph), encoding="utf-8")
    (output_dir / "modules.md").write_text(_node_table("Modules", nodes_by_type.get("Module", [])), encoding="utf-8")
    (output_dir / "packages.md").write_text(_node_table("Packages", nodes_by_type.get("Package", [])), encoding="utf-8")
    (output_dir / "functions.md").write_text(_node_table("Functions", nodes_by_type.get("Function", [])), encoding="utf-8")
    (output_dir / "classes.md").write_text(_node_table("Classes", nodes_by_type.get("Class", [])), encoding="utf-8")
    (output_dir / "dependencies.md").write_text(_dependencies(nodes_by_type), encoding="utf-8")
    (output_dir / "tests.md").write_text(_tests(nodes_by_type, payload.edges), encoding="utf-8")
    (output_dir / "risks.md").write_text(_risks(graph), encoding="utf-8")
    (output_dir / "tags.md").write_text(_tags(graph), encoding="utf-8")
    (output_dir / "entities.md").write_text(_entities(nodes_by_type), encoding="utf-8")
    (output_dir / "projects.md").write_text(_projects(nodes_by_type), encoding="utf-8")
    (output_dir / "runnable_scripts.md").write_text(_node_table("Runnable Scripts", nodes_by_type.get("RunnableScript", [])), encoding="utf-8")
    (output_dir / "agent_start_here.md").write_text(_agent_start(files, graph), encoding="utf-8")
    (output_dir / "file_cards.md").write_text(_file_cards(files, outgoing, incoming), encoding="utf-8")
    return output_dir


def _index() -> str:
    links = "\n".join(f"- [{name.removesuffix('.md').replace('_', ' ').title()}]({name})" for name in NOTE_FILES)
    return f"# Graph Notes\n\n{links}\n- [File Cards](file_cards.md)\n"


def _summary(payload, nodes_by_type: dict, edges_by_type: Counter) -> str:
    lines = [
        "# Graph Summary",
        "",
        f"- Nodes: `{len(payload.nodes)}`",
        f"- Edges: `{len(payload.edges)}`",
        "",
        "## Node Types",
        "",
    ]
    for node_type, nodes in sorted(nodes_by_type.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"- {node_type}: {len(nodes)}")
    lines.extend(["", "## Edge Types", ""])
    for edge_type, count in edges_by_type.most_common():
        lines.append(f"- {edge_type}: {count}")
    return "\n".join(lines) + "\n"


def _entrypoints(graph) -> str:
    rows = ["# Entrypoints", "", "| File | Entrypoint | Confidence |", "| --- | --- | --- |"]
    for item in query_entrypoints(graph):
        rows.append(f"| `{markdown_escape(item['file'])}` | {markdown_escape(item['entrypoint'])} | {item['confidence']:.2f} |")
    if len(rows) == 4:
        rows.append("| - | No entrypoints detected. | - |")
    return "\n".join(rows) + "\n"


def _risks(graph) -> str:
    rows = ["# Risks", "", "| Path | Risk | Type | Reason |", "| --- | --- | --- | --- |"]
    for item in query_risks(graph):
        rows.append(
            f"| `{markdown_escape(item['path'])}` | {markdown_escape(item['risk'])} | {item['type']} | {markdown_escape(item['reason'])} |"
        )
    if len(rows) == 4:
        rows.append("| - | No risks detected. | - | - |")
    return "\n".join(rows) + "\n"


def _tags(graph) -> str:
    rows = ["# Tags", "", "| Tag | Count |", "| --- | ---: |"]
    for item in query_tags(graph):
        rows.append(f"| {markdown_escape(item['tag'])} | {item['count']} |")
    return "\n".join(rows) + "\n"


def _node_table(title: str, nodes: list) -> str:
    rows = [f"# {title}", "", "| Label | Type | Path |", "| --- | --- | --- |"]
    for node in nodes:
        rows.append(f"| {markdown_escape(node.label)} | {node.type} | `{markdown_escape(node.properties.get('path') or node.properties.get('current_path'))}` |")
    if len(rows) == 4:
        rows.append("| - | - | - |")
    return "\n".join(rows) + "\n"


def _dependencies(nodes_by_type: dict) -> str:
    nodes = [*nodes_by_type.get("ExternalDependency", []), *nodes_by_type.get("Import", [])]
    return _node_table("Dependencies", nodes)


def _tests(nodes_by_type: dict, edges: list) -> str:
    tests = nodes_by_type.get("Test", [])
    targets = {edge.source: edge.target for edge in edges if edge.type == "TESTS"}
    rows = ["# Tests", "", "| Test | Target Node |", "| --- | --- |"]
    for node in tests:
        rows.append(f"| `{markdown_escape(node.label)}` | `{targets.get(node.id, '-')}` |")
    if len(rows) == 4:
        rows.append("| - | - |")
    return "\n".join(rows) + "\n"


def _entities(nodes_by_type: dict) -> str:
    nodes = []
    for node_type in ["Person", "Organization", "Place", "Date", "Entity"]:
        nodes.extend(nodes_by_type.get(node_type, []))
    return _node_table("Entities", nodes)


def _projects(nodes_by_type: dict) -> str:
    nodes = []
    for node_type in ["Project", "Component", "Feature", "Cluster"]:
        nodes.extend(nodes_by_type.get(node_type, []))
    return _node_table("Projects And Clusters", nodes)


def _agent_start(files: list, graph) -> str:
    entrypoints = query_entrypoints(graph)
    risks = query_risks(graph)[:10]
    modules = query_modules(graph)[:10]
    lines = [
        "# Agent Start Here",
        "",
        "Read these artifacts first:",
        "",
        "- `.librarian/manifest.json`",
        "- `.librarian/agent_context.md`",
        "- `.librarian/graph.json`",
        "- `.librarian/graph_notes/entrypoints.md`",
        "- `.librarian/graph_notes/risks.md`",
        "",
        "## Likely Entrypoints",
        "",
    ]
    for item in entrypoints[:10]:
        lines.append(f"- `{item['file']}`: {item['entrypoint']}")
    if not entrypoints:
        lines.append("- No entrypoints detected.")
    lines.extend(["", "## Important Modules", ""])
    for item in modules:
        lines.append(f"- {item['type']} `{item['label']}` ({item['import_count']} imports)")
    lines.extend(["", "## Risks", ""])
    for item in risks:
        lines.append(f"- `{item['path']}`: {item['risk']}")
    if not risks:
        lines.append("- No risks detected.")
    return "\n".join(lines) + "\n"


def _file_cards(files: list, outgoing: dict, incoming: dict) -> str:
    lines = ["# File Cards", ""]
    for node in sorted(files, key=lambda item: item.properties.get("current_path", item.label)):
        properties = node.properties
        lines.extend(
            [
                f"## `{properties.get('current_path', node.label)}`",
                "",
                f"- Original path: `{properties.get('original_path', '-')}`",
                f"- Current path: `{properties.get('current_path', '-')}`",
                f"- Proposed path: `{properties.get('proposed_path', '-')}`",
                f"- Type: {node.type}",
                f"- Language: {properties.get('detected_language') or '-'}",
                f"- Hash: `{properties.get('content_hash') or '-'}`",
                f"- Tags: {', '.join(properties.get('tags') or []) or '-'}",
                f"- Classification: {properties.get('classification', {}).get('domain', '-')}/{properties.get('classification', {}).get('category', '-')}",
                f"- Summary: {properties.get('summary') or '-'}",
                f"- Developer notes: {'; '.join(properties.get('developer_notes') or []) or '-'}",
                f"- Entities: {properties.get('entities') or {}}",
                f"- Outgoing relations: {len(outgoing[node.id])}",
                f"- Incoming backlinks: {len(incoming[node.id])}",
                "",
            ]
        )
    return "\n".join(lines)
