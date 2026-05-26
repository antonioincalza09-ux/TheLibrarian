from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.librarian.developer_runtime import initialize_runtime, regenerate_runtime, write_explanation
from src.librarian.docs_exporter import explain_workspace, write_markdown_notes, write_runbooks
from src.librarian.mover import apply_plan, rollback_plan
from src.librarian.planner import build_plan
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
