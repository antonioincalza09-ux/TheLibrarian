from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.librarian.graph._compat import iter_edges, iter_nodes
from src.librarian.graph.schema import GraphEdge, GraphNode, GraphPayload
from src.librarian.graph.utils import as_json_text


def graph_to_payload(graph) -> GraphPayload:
    nodes = [
        GraphNode(
            id=str(node_id),
            type=str(attrs.get("type", "Node")),
            label=str(attrs.get("label", node_id)),
            properties=dict(attrs.get("properties", {})),
        )
        for node_id, attrs in iter_nodes(graph)
    ]
    edges = [
        GraphEdge(
            source=str(attrs.get("source", source)),
            target=str(attrs.get("target", target)),
            type=str(attrs.get("type", "RELATED_TO")),
            confidence=float(attrs.get("confidence", 1.0)),
            reason=str(attrs.get("reason", "")),
            properties=dict(attrs.get("properties", {})),
        )
        for source, target, attrs in iter_edges(graph)
    ]
    nodes.sort(key=lambda item: (item.type, item.id))
    edges.sort(key=lambda item: (item.type, item.source, item.target))
    return GraphPayload(nodes=nodes, edges=edges)


def export_graph_json(graph, root: str | Path) -> Path:
    output_path = Path(root).resolve() / ".librarian" / "graph.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = graph_to_payload(graph).model_dump(mode="json")
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def export_graphml(graph, root: str | Path) -> Path:
    output_path = Path(root).resolve() / ".librarian" / "graph.graphml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    graphml = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
    keys = [
        ("node_label", "node", "label"),
        ("node_type", "node", "type"),
        ("node_properties", "node", "properties"),
        ("edge_type", "edge", "type"),
        ("edge_confidence", "edge", "confidence"),
        ("edge_reason", "edge", "reason"),
        ("edge_properties", "edge", "properties"),
    ]
    for key_id, scope, name in keys:
        ET.SubElement(graphml, "key", id=key_id, **{"for": scope, "attr.name": name, "attr.type": "string"})
    graph_element = ET.SubElement(graphml, "graph", edgedefault="directed")
    for node in graph_to_payload(graph).nodes:
        node_element = ET.SubElement(graph_element, "node", id=node.id)
        _data(node_element, "node_label", node.label)
        _data(node_element, "node_type", node.type)
        _data(node_element, "node_properties", as_json_text(node.properties))
    for index, edge in enumerate(graph_to_payload(graph).edges):
        edge_element = ET.SubElement(graph_element, "edge", id=f"e{index}", source=edge.source, target=edge.target)
        _data(edge_element, "edge_type", edge.type)
        _data(edge_element, "edge_confidence", str(edge.confidence))
        _data(edge_element, "edge_reason", edge.reason)
        _data(edge_element, "edge_properties", as_json_text(edge.properties))
    ET.ElementTree(graphml).write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def export_turtle(graph, root: str | Path) -> Path:
    output_path = Path(root).resolve() / ".librarian" / "graph.ttl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = graph_to_payload(graph)
    lines = [
        "@prefix lib: <https://thelibrarian.local/schema#> .",
        "@prefix node: <https://thelibrarian.local/node/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    for node in payload.nodes:
        subject = _iri(node.id)
        lines.extend(
            [
                f"{subject} a lib:{_ttl_name(node.type)} ;",
                f"  lib:id {_literal(node.id)} ;",
                f"  lib:label {_literal(node.label)} ;",
                f"  lib:properties {_literal(json.dumps(node.properties, sort_keys=True, ensure_ascii=False))} .",
                "",
            ]
        )
    for index, edge in enumerate(payload.edges):
        subject = _iri(f"edge/{index}")
        lines.extend(
            [
                f"{subject} a lib:{_ttl_name(edge.type)} ;",
                f"  lib:source {_iri(edge.source)} ;",
                f"  lib:target {_iri(edge.target)} ;",
                f"  lib:confidence \"{edge.confidence}\"^^xsd:decimal ;",
                f"  lib:reason {_literal(edge.reason)} ;",
                f"  lib:properties {_literal(json.dumps(edge.properties, sort_keys=True, ensure_ascii=False))} .",
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def export_sqlite_index(graph, root: str | Path) -> Path:
    output_path = Path(root).resolve() / ".librarian" / "graph_index.sqlite"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = graph_to_payload(graph)
    with sqlite3.connect(output_path) as connection:
        connection.execute("DROP TABLE IF EXISTS nodes")
        connection.execute("DROP TABLE IF EXISTS edges")
        connection.execute(
            """
            CREATE TABLE nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                properties_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                type TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT NOT NULL,
                properties_json TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO nodes (id, type, label, properties_json) VALUES (?, ?, ?, ?)",
            [
                (node.id, node.type, node.label, json.dumps(node.properties, sort_keys=True, ensure_ascii=False))
                for node in payload.nodes
            ],
        )
        connection.executemany(
            "INSERT INTO edges (source, target, type, confidence, reason, properties_json) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    edge.source,
                    edge.target,
                    edge.type,
                    edge.confidence,
                    edge.reason,
                    json.dumps(edge.properties, sort_keys=True, ensure_ascii=False),
                )
                for edge in payload.edges
            ],
        )
        connection.execute("CREATE INDEX idx_nodes_type ON nodes(type)")
        connection.execute("CREATE INDEX idx_edges_type ON edges(type)")
        connection.execute("CREATE INDEX idx_edges_source ON edges(source)")
        connection.execute("CREATE INDEX idx_edges_target ON edges(target)")
    return output_path


def _data(parent: ET.Element, key: str, value: Any) -> None:
    element = ET.SubElement(parent, "data", key=key)
    element.text = "" if value is None else str(value)


def _ttl_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character == "_" else "_" for character in value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"Node_{cleaned}"
    return cleaned


def _iri(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-_." else "_" for character in value)
    return f"node:{safe}"


def _literal(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")
    return f'"{text}"'
