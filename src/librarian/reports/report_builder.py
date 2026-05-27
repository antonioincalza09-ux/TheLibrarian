from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from src.librarian.graph.exporters import graph_to_payload
from src.librarian.graph.graph_queries import query_entrypoints, query_modules, query_risks, query_tags
from src.librarian.graph.validators import validate_librarian_workspace


def build_graph_report(root: str | Path, graph) -> Path:
    resolved_root = Path(root).resolve()
    report_path = resolved_root / ".librarian" / "graph_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = graph_to_payload(graph)
    validation_report = validate_librarian_workspace(resolved_root)

    nodes_by_type = Counter(node.type for node in payload.nodes)
    edges_by_type = Counter(edge.type for edge in payload.edges)
    tags = query_tags(graph)
    risks = query_risks(graph)
    entrypoints = query_entrypoints(graph)
    modules = query_modules(graph)
    file_nodes = [node for node in payload.nodes if node.type in {"File", "CodeFile", "ConfigFile", "GeneratedFile", "VendorFile", "LockFile"}]

    languages = Counter(node.properties.get("detected_language") for node in file_nodes if node.properties.get("detected_language"))
    domains = Counter(node.properties.get("classification", {}).get("domain") for node in file_nodes if node.properties.get("classification"))
    dense_directories = _dense_directories(file_nodes)
    duplicate_edges = [edge for edge in payload.edges if edge.type == "SIMILAR_TO" and edge.properties.get("duplicate")]
    low_confidence = [edge for edge in payload.edges if edge.confidence < 0.5]
    protected = [node for node in file_nodes if node.type in {"GeneratedFile", "VendorFile", "LockFile"} or node.properties.get("risk_level") == "high"]
    untagged = [node for node in file_nodes if not node.properties.get("tags")]

    lines = [
        "# Graph Report",
        "",
        f"- Nodes: `{len(payload.nodes)}`",
        f"- Edges: `{len(payload.edges)}`",
        f"- Validation errors: `{validation_report.counts.get('errors', 0)}`",
        f"- Validation warnings: `{validation_report.counts.get('warnings', 0)}`",
        "",
        "## Top Tags",
        *_bullets([f"{item['tag']}: {item['count']}" for item in tags[:12]]),
        "",
        "## Top Domains",
        *_bullets([f"{domain}: {count}" for domain, count in domains.most_common(12)]),
        "",
        "## Top Languages",
        *_bullets([f"{language}: {count}" for language, count in languages.most_common(12)]),
        "",
        "## File Duplicates",
        *_bullets([f"{edge.source} -> {edge.target}" for edge in duplicate_edges[:20]]),
        "",
        "## Dense Directories",
        *_bullets([f"{path}: {count} files" for path, count in dense_directories[:12]]),
        "",
        "## Entrypoints",
        *_bullets([f"`{item['file']}`: {item['entrypoint']}" for item in entrypoints[:20]]),
        "",
        "## Packages And Modules",
        *_bullets([f"{item['type']} `{item['label']}` ({item['import_count']} imports)" for item in modules[:20]]),
        "",
        "## External Dependencies",
        *_bullets([node.label for node in payload.nodes if node.type == "ExternalDependency"][:20]),
        "",
        "## Tests",
        *_bullets([node.label for node in payload.nodes if node.type == "Test"][:20]),
        "",
        "## Elements Without Tags",
        *_bullets([node.properties.get("current_path", node.label) for node in untagged[:20]]),
        "",
        "## Low Confidence Relationships",
        *_bullets([f"{edge.type}: {edge.source} -> {edge.target} ({edge.confidence:.2f})" for edge in low_confidence[:20]]),
        "",
        "## Do Not Modify / Protected Files",
        *_bullets([node.properties.get("current_path", node.label) for node in protected[:20]]),
        "",
        "## Clusters",
        *_bullets([node.label for node in payload.nodes if node.type == "Cluster"][:20]),
        "",
        "## Cleanup Suggestions",
        *_bullets(_cleanup_suggestions(duplicate_edges, untagged, low_confidence, risks)),
        "",
        "## Validation Findings",
        *_bullets([f"{finding.severity}: {finding.code} - {finding.path or '-'}" for finding in validation_report.findings[:30]]),
        "",
        "## Graph Shape",
        *_bullets([f"{node_type}: {count}" for node_type, count in nodes_by_type.most_common()[:20]]),
        "",
        "## Edge Shape",
        *_bullets([f"{edge_type}: {count}" for edge_type, count in edges_by_type.most_common()[:20]]),
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _dense_directories(file_nodes: list) -> list[tuple[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    for node in file_nodes:
        parent = node.properties.get("parent_path") or "."
        counts[parent] += 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _cleanup_suggestions(duplicate_edges: list, untagged: list, low_confidence: list, risks: list) -> list[str]:
    suggestions: list[str] = []
    if duplicate_edges:
        suggestions.append("Review duplicate content groups before reorganizing files.")
    if untagged:
        suggestions.append("Add or regenerate sidecar tags for untagged files.")
    if low_confidence:
        suggestions.append("Inspect low-confidence inferred relationships before relying on them.")
    if risks:
        suggestions.append("Read graph_notes/risks.md before modifying protected files.")
    return suggestions or ["No cleanup suggestions."]


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- None."]
