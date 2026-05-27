from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from src.librarian.agent.context_builder import build_agent_context
from src.librarian.agent.prompt_pack_builder import generate_agent_runbooks
from src.librarian.agent.runnable_helpers import generate_graph_scripts
from src.librarian.cli import main
from src.librarian.graph.builder import build_graph
from src.librarian.graph.cypher_exporter import export_cypher
from src.librarian.graph.exporters import export_graph_json, export_graphml, graph_to_payload
from src.librarian.graph.exporters import export_sqlite_index, export_turtle
from src.librarian.graph.graph_queries import query_entrypoints, query_modules, query_risks, query_tags
from src.librarian.graph.graph_queries import query_dependencies, query_duplicates, query_orphans, query_tests
from src.librarian.graph.markdown_exporter import export_markdown_notes
from src.librarian.graph.validators import validate_librarian_workspace
from src.librarian.reports.report_builder import build_graph_report


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "graph_fixture"


def copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "graph_fixture"
    shutil.copytree(FIXTURE, target, ignore=shutil.ignore_patterns("__pycache__", "*.sqlite"))
    return target


def test_validation_manifest_runtime_and_scripts_are_valid(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)

    report = validate_librarian_workspace(root)

    assert report.ok
    assert report.counts == {"errors": 0, "warnings": 0, "info": 0}
    assert (root / ".librarian" / "validation_report.json").exists()
    assert (root / ".librarian" / "validation_report.md").exists()
    assert not [finding for finding in report.findings if finding.code == "script_may_modify_files"]


def test_validation_detects_duplicate_ids_orphan_sidecars_and_missing_readme(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    manifest_path = root / ".librarian" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][1]["librarian_id"] = manifest["files"][0]["librarian_id"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / "orphan.librarian.yaml").write_text("librarian_id: orphan\ntype: file\n", encoding="utf-8")
    (root / ".librarian" / "README.librarian.md").unlink()

    report = validate_librarian_workspace(root)
    codes = {finding.code for finding in report.findings}

    assert not report.ok
    assert "duplicate_librarian_id" in codes
    assert "orphan_sidecar" in codes
    assert "missing_runtime_readme" in codes


def test_validation_detects_script_that_may_modify_files(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    script = root / ".librarian" / "scripts" / "danger.py"
    script.write_text("from pathlib import Path\nPath('x').write_text('bad')\n", encoding="utf-8")

    report = validate_librarian_workspace(root)

    assert "script_may_modify_files" in {finding.code for finding in report.findings}


def test_build_graph_contains_files_metadata_code_and_inferred_edges() -> None:
    graph = build_graph(FIXTURE)
    payload = graph_to_payload(graph)
    node_types = {node.type for node in payload.nodes}
    edge_types = {edge.type for edge in payload.edges}

    assert {"Directory", "Tag", "Function", "Class", "Module", "Entrypoint", "Test", "PromptPack"} <= node_types
    assert {"CONTAINS", "HAS_TAG", "DEFINES", "IMPORTS", "HAS_ENTRYPOINT", "TESTS", "SIMILAR_TO", "HAS_CONFIG"} <= edge_types
    assert any(node.type == "CodeFile" and node.properties.get("current_path") == "src/graph_fixture_app/main.py" for node in payload.nodes)
    assert any(edge.type == "SIMILAR_TO" and edge.properties.get("duplicate") for edge in payload.edges)
    assert any(edge.type == "SIMILAR_TO" and edge.properties.get("shared_tag") for edge in payload.edges)
    assert any(edge.type == "IMPORTS" and edge.target == "module:src.graph_fixture_app.utils" for edge in payload.edges)
    assert any(edge.type == "IMPORTS" and edge.properties.get("resolved_path") == "src/graph_fixture_app/utils.py" for edge in payload.edges)
    assert any(node.type == "Organization" and node.label == "OpenAI" for node in payload.nodes)


def test_graph_exports_json_graphml_cypher_and_markdown(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    graph = build_graph(root)

    json_path = export_graph_json(graph, root)
    graphml_path = export_graphml(graph, root)
    cypher_path = export_cypher(graph, root)
    notes_dir = export_markdown_notes(graph, root)
    turtle_path = export_turtle(graph, root)
    sqlite_path = export_sqlite_index(graph, root)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["nodes"]
    assert payload["edges"]
    ET.parse(graphml_path)
    cypher_text = cypher_path.read_text(encoding="utf-8")
    assert "MERGE (n:LibrarianNode:CodeFile" in cypher_text
    assert '\\"__main__\\"' in cypher_text
    assert "lib:HAS_ENTRYPOINT" in turtle_path.read_text(encoding="utf-8")
    with sqlite3.connect(sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] > 0
        assert connection.execute("SELECT COUNT(*) FROM edges WHERE type = 'IMPORTS'").fetchone()[0] > 0
    assert (notes_dir / "agent_start_here.md").exists()
    assert (notes_dir / "file_cards.md").exists()


def test_queries_report_agent_context_runbooks_and_scripts(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    graph = build_graph(root)
    export_graph_json(graph, root)

    assert query_entrypoints(graph)
    assert query_risks(graph)
    assert query_modules(graph)
    assert query_tags(graph)
    assert query_dependencies(graph)
    assert query_tests(graph)
    assert query_duplicates(graph)
    assert query_orphans(graph) == []

    report_path = build_graph_report(root, graph)
    context = build_agent_context(root)
    runbooks = generate_agent_runbooks(root)
    scripts = generate_graph_scripts(root)

    assert report_path.exists()
    assert (root / ".librarian" / "agent_context.md").exists()
    assert context["entrypoints"]
    assert {path.name for path in runbooks} >= {"agent_start_here.md", "developer_start_here.md"}
    assert {path.name for path in scripts} >= {"query_graph_summary.py", "query_entrypoints.py", "query_risks.py"}

    for script_name in [
        "query_graph_summary.py",
        "query_entrypoints.py",
        "query_risks.py",
        "query_dependencies.py",
        "query_tests.py",
    ]:
        completed = subprocess.run(
            [sys.executable, str(root / ".librarian" / "graph_scripts" / script_name)],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip()


def test_cli_acceptance_flow(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    commands = [
        ["graph", "validate", str(root)],
        ["graph", "build", str(root)],
        ["graph", "export", str(root), "--format", "json"],
        ["graph", "export", str(root), "--format", "graphml"],
        ["graph", "export", str(root), "--format", "cypher"],
        ["graph", "export", str(root), "--format", "markdown"],
        ["graph", "export", str(root), "--format", "turtle"],
        ["graph", "export", str(root), "--format", "sqlite"],
        ["graph", "report", str(root)],
        ["graph", "index", str(root)],
        ["graph", "query", str(root), "--kind", "entrypoints"],
        ["graph", "query", str(root), "--kind", "risks"],
        ["graph", "query", str(root), "--kind", "modules"],
        ["graph", "query", str(root), "--kind", "tags"],
        ["graph", "query", str(root), "--kind", "dependencies"],
        ["graph", "query", str(root), "--kind", "tests"],
        ["graph", "query", str(root), "--kind", "duplicates"],
        ["graph", "query", str(root), "--kind", "orphans"],
        ["agent", "context", str(root)],
        ["agent", "runbook", str(root)],
        ["agent", "scripts", str(root)],
    ]

    for command in commands:
        assert main(command) == 0
