from __future__ import annotations

from collections import Counter
from typing import Any

from src.librarian.graph.exporters import graph_to_payload


def query_entrypoints(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    nodes = {node.id: node for node in payload.nodes}
    results: list[dict[str, Any]] = []
    for edge in payload.edges:
        if edge.type == "HAS_ENTRYPOINT":
            source = nodes.get(edge.source)
            target = nodes.get(edge.target)
            if source and target:
                results.append(
                    {
                        "file": source.properties.get("current_path", source.label),
                        "entrypoint": target.label,
                        "confidence": edge.confidence,
                    }
                )
    return results


def query_risks(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    nodes = {node.id: node for node in payload.nodes}
    results: list[dict[str, Any]] = []
    for edge in payload.edges:
        if edge.type in {"HAS_RISK", "SHOULD_NOT_MODIFY"}:
            source = nodes.get(edge.source)
            target = nodes.get(edge.target)
            if source and target:
                results.append(
                    {
                        "path": source.properties.get("current_path", source.label),
                        "risk": target.label,
                        "type": edge.type,
                        "reason": edge.reason,
                    }
                )
    return results


def query_modules(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    import_counts = Counter(edge.target for edge in payload.edges if edge.type == "IMPORTS")
    results: list[dict[str, Any]] = []
    for node in payload.nodes:
        if node.type in {"Module", "Package", "ExternalDependency", "Import"}:
            results.append({"id": node.id, "type": node.type, "label": node.label, "import_count": import_counts[node.id]})
    return sorted(results, key=lambda item: (-item["import_count"], item["type"], item["label"]))


def query_tags(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    tag_counts = Counter(edge.target for edge in payload.edges if edge.type == "HAS_TAG")
    tags = {node.id: node for node in payload.nodes if node.type == "Tag"}
    return [
        {"tag": node.label, "count": tag_counts[node_id]}
        for node_id, node in sorted(tags.items(), key=lambda item: (-tag_counts[item[0]], item[1].label))
    ]


def query_dependencies(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    nodes = {node.id: node for node in payload.nodes}
    results: list[dict[str, Any]] = []
    for edge in payload.edges:
        if edge.type != "IMPORTS":
            continue
        source = nodes.get(edge.source)
        target = nodes.get(edge.target)
        if source and target:
            results.append(
                {
                    "source": source.properties.get("current_path", source.label),
                    "dependency": target.label,
                    "dependency_type": target.type,
                    "resolved_path": edge.properties.get("resolved_path"),
                    "confidence": edge.confidence,
                }
            )
    return sorted(results, key=lambda item: (item["source"], item["dependency"]))


def query_tests(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    nodes = {node.id: node for node in payload.nodes}
    tests = {node.id: node for node in payload.nodes if node.type == "Test"}
    results: list[dict[str, Any]] = []
    for test_id, node in tests.items():
        targets = [edge.target for edge in payload.edges if edge.source == test_id and edge.type == "TESTS"]
        results.append(
            {
                "test": node.label,
                "targets": [nodes[target].properties.get("current_path", nodes[target].label) for target in targets if target in nodes],
            }
        )
    return results


def query_duplicates(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    nodes = {node.id: node for node in payload.nodes}
    results: list[dict[str, Any]] = []
    for edge in payload.edges:
        if edge.type == "SIMILAR_TO" and edge.properties.get("duplicate"):
            source = nodes.get(edge.source)
            target = nodes.get(edge.target)
            if source and target:
                results.append(
                    {
                        "source": source.properties.get("current_path", source.label),
                        "target": target.properties.get("current_path", target.label),
                        "confidence": edge.confidence,
                    }
                )
    return results


def query_orphans(graph) -> list[dict[str, Any]]:
    payload = graph_to_payload(graph)
    tagged = {edge.source for edge in payload.edges if edge.type == "HAS_TAG"}
    documented = {edge.source for edge in payload.edges if edge.type == "DOCUMENTED_BY"}
    file_types = {"File", "CodeFile", "ConfigFile", "GeneratedFile", "VendorFile", "LockFile"}
    return [
        {"path": node.properties.get("current_path", node.label), "type": node.type}
        for node in payload.nodes
        if node.type in file_types and node.id not in tagged and node.id not in documented
    ]
