from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.librarian.agent.context_builder import build_agent_context
from src.librarian.agent.prompt_pack_builder import generate_agent_runbooks
from src.librarian.agent.runnable_helpers import generate_graph_scripts
from src.librarian.developer_runtime import initialize_runtime, regenerate_runtime, write_explanation
from src.librarian.docs_exporter import explain_workspace, write_markdown_notes, write_runbooks
from src.librarian.graph.builder import build_graph
from src.librarian.graph.cypher_exporter import export_cypher
from src.librarian.graph.exporters import export_graph_json, export_graphml, export_sqlite_index, export_turtle
from src.librarian.graph.graph_queries import (
    query_dependencies,
    query_duplicates,
    query_entrypoints,
    query_modules,
    query_orphans,
    query_risks,
    query_tags,
    query_tests,
)
from src.librarian.graph.markdown_exporter import export_markdown_notes
from src.librarian.graph.validators import validate_librarian_workspace
from src.librarian.mover import apply_plan, rollback_plan
from src.librarian.planner import build_plan
from src.librarian.reports.report_builder import build_graph_report
from src.librarian.scanner import build_manifest, scan_workspace
from src.librarian.sidecars import collect_sidecar_status, read_manifest, write_sidecars


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="librarian", description="Developer-first offline workspace librarian.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser("scan", help="Recursively scan a workspace.")
    scan.add_argument("path")
    scan.add_argument("--write", action="store_true")

    mark = subcommands.add_parser("mark", help="Generate sidecar metadata and manifest.")
    mark.add_argument("path")

    plan = subcommands.add_parser("plan", help="Generate a dry-run organization plan.")
    plan.add_argument("path")

    apply = subcommands.add_parser("apply", help="Apply the current safe plan.")
    apply.add_argument("path")

    rollback = subcommands.add_parser("rollback", help="Rollback applied operations using the append-only log.")
    rollback.add_argument("path")

    status = subcommands.add_parser("status", help="Show workspace status.")
    status.add_argument("path")

    dev = subcommands.add_parser("dev", help="Developer runtime utilities.")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True)
    for name in ("init", "index", "explain", "runbook"):
        command = dev_sub.add_parser(name)
        command.add_argument("path")

    graph = subcommands.add_parser("graph", help="Knowledge graph utilities.")
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    for name in ("validate", "build", "report", "index"):
        command = graph_sub.add_parser(name)
        command.add_argument("path")
    export = graph_sub.add_parser("export")
    export.add_argument("path")
    export.add_argument("--format", choices=["json", "graphml", "cypher", "markdown", "turtle", "sqlite"], required=True)
    query = graph_sub.add_parser("query")
    query.add_argument("path")
    query.add_argument(
        "--kind",
        choices=["entrypoints", "risks", "modules", "tags", "dependencies", "tests", "duplicates", "orphans"],
        required=True,
    )

    agent = subcommands.add_parser("agent", help="Agent-friendly runtime utilities.")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    for name in ("context", "runbook", "scripts"):
        command = agent_sub.add_parser(name)
        command.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "scan": _handle_scan,
        "mark": _handle_mark,
        "plan": _handle_plan,
        "apply": _handle_apply,
        "rollback": _handle_rollback,
        "status": _handle_status,
        "dev": _handle_dev,
        "graph": _handle_graph,
        "agent": _handle_agent,
    }
    return handlers[args.command](args)


def _handle_scan(args: argparse.Namespace) -> int:
    scan = scan_workspace(args.path)
    payload = scan.model_dump(mode="json")
    if args.write:
        output_path = Path(args.path).resolve() / ".librarian" / "scan.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def _handle_mark(args: argparse.Namespace) -> int:
    scan = scan_workspace(args.path)
    manifest = build_manifest(scan)
    counts = write_sidecars(args.path, manifest)
    sidecar_stats = collect_sidecar_status(args.path, manifest)
    manifest = build_manifest(scan, marked_files=counts["marked_files"], marked_directories=counts["marked_directories"], sidecar_stats=sidecar_stats)
    write_sidecars(args.path, manifest)
    print(json.dumps(manifest.model_dump(mode="json"), indent=2))
    return 0


def _handle_plan(args: argparse.Namespace) -> int:
    manifest = _ensure_manifest(args.path)
    plan = build_plan(args.path, manifest)
    print(json.dumps(plan.model_dump(mode="json"), indent=2))
    return 0


def _handle_apply(args: argparse.Namespace) -> int:
    operations = apply_plan(args.path)
    print(json.dumps([operation.model_dump(mode="json") for operation in operations], indent=2))
    return 0


def _handle_rollback(args: argparse.Namespace) -> int:
    operations = rollback_plan(args.path)
    print(json.dumps([operation.model_dump(mode="json") for operation in operations], indent=2))
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    manifest = _ensure_manifest(args.path)
    sidecar_stats = collect_sidecar_status(args.path, manifest)
    operations_log = Path(args.path).resolve() / ".librarian" / "logs" / "operations.jsonl"
    applied_operations = 0
    rollback_available = False
    if operations_log.exists():
        applied_operations = len([line for line in operations_log.read_text(encoding="utf-8").splitlines() if '"status": "applied"' in line])
        rollback_available = applied_operations > 0
    payload = {
        "file_totals": manifest.counts.files,
        "directory_totals": manifest.counts.directories,
        "file_marked": manifest.counts.marked_files,
        "directory_marked": manifest.counts.marked_directories,
        "file_unreadable": manifest.counts.unreadable_files,
        "sidecars_missing": sidecar_stats["missing_sidecars"],
        "sidecars_orphan": sidecar_stats["orphan_sidecars"],
        "operations_applied": applied_operations,
        "rollback_available": rollback_available,
        "errors": manifest.errors,
        "warnings": manifest.warnings,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _handle_dev(args: argparse.Namespace) -> int:
    manifest = _ensure_manifest(args.path)
    if args.dev_command == "init":
        initialize_runtime(args.path, manifest)
        print(str(Path(args.path).resolve() / ".librarian"))
        return 0
    if args.dev_command == "index":
        regenerate_runtime(args.path, manifest)
        print(str(Path(args.path).resolve() / ".librarian" / "notes" / "index.md"))
        return 0
    if args.dev_command == "explain":
        explanation = explain_workspace(manifest)
        write_explanation(args.path, manifest)
        print(explanation)
        return 0
    if args.dev_command == "runbook":
        write_runbooks(args.path, manifest)
        print(str(Path(args.path).resolve() / ".librarian" / "runbooks" / "index.md"))
        return 0
    raise ValueError(f"Unknown dev command: {args.dev_command}")


def _handle_graph(args: argparse.Namespace) -> int:
    if args.graph_command == "validate":
        report = validate_librarian_workspace(args.path)
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        return 0 if report.ok else 1

    graph = build_graph(args.path)
    if args.graph_command == "build":
        output_path = export_graph_json(graph, args.path)
        payload = {
            "graph_json": str(output_path),
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
        }
        print(json.dumps(payload, indent=2))
        return 0

    if args.graph_command == "export":
        if args.format == "json":
            output_path = export_graph_json(graph, args.path)
        elif args.format == "graphml":
            output_path = export_graphml(graph, args.path)
        elif args.format == "cypher":
            output_path = export_cypher(graph, args.path)
        elif args.format == "markdown":
            output_path = export_markdown_notes(graph, args.path)
        elif args.format == "turtle":
            output_path = export_turtle(graph, args.path)
        elif args.format == "sqlite":
            output_path = export_sqlite_index(graph, args.path)
        else:
            raise ValueError(f"Unknown graph export format: {args.format}")
        print(str(output_path))
        return 0

    if args.graph_command == "index":
        export_graph_json(graph, args.path)
        output_path = export_sqlite_index(graph, args.path)
        print(str(output_path))
        return 0

    if args.graph_command == "report":
        export_graph_json(graph, args.path)
        report_path = build_graph_report(args.path, graph)
        print(str(report_path))
        return 0

    if args.graph_command == "query":
        query_handlers = {
            "entrypoints": query_entrypoints,
            "risks": query_risks,
            "modules": query_modules,
            "tags": query_tags,
            "dependencies": query_dependencies,
            "tests": query_tests,
            "duplicates": query_duplicates,
            "orphans": query_orphans,
        }
        payload = query_handlers[args.kind](graph)
        print(json.dumps(payload, indent=2))
        return 0

    raise ValueError(f"Unknown graph command: {args.graph_command}")


def _handle_agent(args: argparse.Namespace) -> int:
    if args.agent_command == "context":
        context = build_agent_context(args.path)
        print(json.dumps(context, indent=2))
        return 0
    if args.agent_command == "runbook":
        paths = generate_agent_runbooks(args.path)
        print(json.dumps([str(path) for path in paths], indent=2))
        return 0
    if args.agent_command == "scripts":
        graph = build_graph(args.path)
        export_graph_json(graph, args.path)
        paths = generate_graph_scripts(args.path)
        print(json.dumps([str(path) for path in paths], indent=2))
        return 0
    raise ValueError(f"Unknown agent command: {args.agent_command}")


def _ensure_manifest(path: str | Path):
    manifest_path = Path(path).resolve() / ".librarian" / "manifest.json"
    if manifest_path.exists():
        return read_manifest(path)
    scan = scan_workspace(path)
    manifest = build_manifest(scan)
    counts = write_sidecars(path, manifest)
    sidecar_stats = collect_sidecar_status(path, manifest)
    manifest = build_manifest(scan, marked_files=counts["marked_files"], marked_directories=counts["marked_directories"], sidecar_stats=sidecar_stats)
    write_sidecars(path, manifest)
    return manifest
