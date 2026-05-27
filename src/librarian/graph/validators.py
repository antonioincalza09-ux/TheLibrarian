from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.librarian.metadata import directory_sidecar_path, file_sidecar_path
from src.librarian.rules.schema import Manifest, WorkspaceNode, WorkspacePlan
from src.librarian.sidecars import read_manifest
from src.librarian.graph.schema import ValidationFinding, ValidationReport


REQUIRED_NODE_FIELDS = ["librarian_id", "type", "original_path", "current_path", "name", "indexed_at"]
EXPECTED_RUNTIME_SCRIPTS = {
    "inspect_workspace.py",
    "print_manifest_summary.py",
    "find_entrypoints.py",
    "find_unmarked.py",
}
EXPECTED_NOTES = {"index.md", "files.md", "directories.md", "code.md", "entrypoints.md", "risks.md"}
WRITE_CALLS = {"write_text", "write_bytes", "unlink", "remove", "rmdir", "rename", "replace", "mkdir"}
WRITE_MODULE_CALLS = {"remove", "unlink", "rmdir", "removedirs", "renames", "rename"}
WRITE_MODULES = {"os", "shutil", "pathlib"}


def validate_librarian_workspace(root: str | Path) -> ValidationReport:
    resolved_root = Path(root).resolve()
    librarian_root = resolved_root / ".librarian"
    report = ValidationReport(workspace_root=str(resolved_root))
    manifest = _load_manifest(resolved_root, report)
    if manifest is None:
        return _write_report(resolved_root, report.finalize())

    files = list(manifest.files)
    directories = list(manifest.directories)
    all_nodes = [*files, *directories]
    _validate_manifest_nodes(report, all_nodes, files)
    _validate_sidecars(resolved_root, report, files, directories)
    _validate_relations(report, all_nodes)
    _validate_plan(librarian_root, report, all_nodes)
    _validate_runtime_artifacts(librarian_root, report)
    _validate_scripts(librarian_root, report)
    return _write_report(resolved_root, report.finalize())


def _load_manifest(root: Path, report: ValidationReport) -> Manifest | None:
    manifest_path = root / ".librarian" / "manifest.json"
    if not manifest_path.exists():
        _finding(report, "error", "missing_manifest", "Missing .librarian/manifest.json.", ".librarian/manifest.json")
        return None
    try:
        return read_manifest(root)
    except (OSError, ValidationError, ValueError) as exc:
        _finding(report, "error", "invalid_manifest", f"manifest.json is not valid: {exc}", ".librarian/manifest.json")
        return None


def _validate_manifest_nodes(report: ValidationReport, nodes: list[WorkspaceNode], files: list[WorkspaceNode]) -> None:
    ids = [node.librarian_id for node in nodes]
    for librarian_id, count in Counter(ids).items():
        if count > 1:
            _finding(report, "error", "duplicate_librarian_id", f"Duplicate librarian_id: {librarian_id}.", properties={"librarian_id": librarian_id})
    for node in nodes:
        payload = node.model_dump(mode="json")
        for field in REQUIRED_NODE_FIELDS:
            if payload.get(field) in {None, ""}:
                _finding(report, "error", "missing_required_field", f"Missing required field {field}.", node.current_path, {"field": field})
        if node.type not in {"file", "directory"}:
            _finding(report, "error", "invalid_node_type", f"Invalid node type: {node.type}.", node.current_path)
        if not node.original_path:
            _finding(report, "error", "missing_original_path", "original_path is required.", node.current_path)
        if node.type == "file" and node.readable and not node.content_hash:
            _finding(report, "error", "missing_content_hash", "Readable file is missing content_hash.", node.current_path)
        if node.current_path in {"", None}:
            _finding(report, "error", "missing_current_path", "current_path is required.", node.name)
    for file_node in files:
        actual_path = Path(report.workspace_root) / file_node.current_path
        if file_node.readable and actual_path.exists() and not file_node.content_hash:
            _finding(report, "error", "missing_readable_hash", "Readable file exists but has no content_hash.", file_node.current_path)


def _validate_sidecars(root: Path, report: ValidationReport, files: list[WorkspaceNode], directories: list[WorkspaceNode]) -> None:
    expected = {
        str(file_sidecar_path(root, file_node).resolve(strict=False)): file_node
        for file_node in files
    }
    expected.update(
        {
            str(directory_sidecar_path(root, directory).resolve(strict=False)): directory
            for directory in directories
        }
    )
    existing = [
        path
        for path in root.rglob("*.librarian.yaml")
        if ".librarian" not in path.parts
    ]
    existing_set = {str(path.resolve(strict=False)) for path in existing}
    for path_text, node in expected.items():
        if path_text not in existing_set:
            _finding(report, "warning", "missing_sidecar", "Expected sidecar is missing.", node.current_path)
    for path in existing:
        resolved = str(path.resolve(strict=False))
        if resolved not in expected:
            _finding(report, "error", "orphan_sidecar", "Sidecar does not correspond to a manifest node.", _display_path(path, root))
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            sidecar_node = WorkspaceNode.model_validate(payload)
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            _finding(report, "error", "invalid_sidecar_yaml", f"Invalid sidecar YAML: {exc}", _display_path(path, root))
            continue
        expected_node = expected[resolved]
        if sidecar_node.librarian_id != expected_node.librarian_id:
            _finding(report, "error", "sidecar_id_mismatch", "Sidecar librarian_id does not match manifest.", _display_path(path, root))
        if sidecar_node.current_path != expected_node.current_path:
            _finding(report, "error", "sidecar_current_path_mismatch", "Sidecar current_path does not match manifest.", _display_path(path, root))
        if sidecar_node.type != expected_node.type:
            _finding(report, "error", "sidecar_type_mismatch", "Sidecar type does not match manifest.", _display_path(path, root))


def _validate_relations(report: ValidationReport, nodes: list[WorkspaceNode]) -> None:
    ids = {node.librarian_id for node in nodes}
    paths = {node.current_path for node in nodes} | {node.original_path for node in nodes}
    for node in nodes:
        for relation in node.relations:
            if relation.target and relation.target not in ids and relation.target not in paths:
                _finding(
                    report,
                    "warning",
                    "unresolved_relation_target",
                    f"Relation target is not present in manifest: {relation.target}.",
                    node.current_path,
                    {"relation_type": relation.type, "target": relation.target},
                )


def _validate_plan(librarian_root: Path, report: ValidationReport, nodes: list[WorkspaceNode]) -> None:
    plan_path = librarian_root / "plan.json"
    if not plan_path.exists():
        return
    try:
        plan = WorkspacePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        _finding(report, "error", "invalid_plan", f"plan.json is not valid: {exc}", ".librarian/plan.json")
        return
    destinations = {entry.source: entry.destination for entry in plan.entries}
    for node in nodes:
        planned = destinations.get(node.current_path)
        if planned and node.proposed_path and node.proposed_path != planned:
            _finding(
                report,
                "warning",
                "proposed_path_plan_mismatch",
                f"proposed_path differs from plan destination: {node.proposed_path} != {planned}.",
                node.current_path,
            )
    directory_moves = {
        entry.source: entry.destination
        for entry in plan.entries
        if entry.node_type == "directory" and entry.source != entry.destination
    }
    for source, destination in directory_moves.items():
        if destination.startswith(f"{source}/"):
            _finding(report, "error", "directory_reorder_cycle", "Directory cannot be moved into its own descendant.", source)


def _validate_runtime_artifacts(librarian_root: Path, report: ValidationReport) -> None:
    readme = librarian_root / "README.librarian.md"
    if not readme.exists():
        _finding(report, "warning", "missing_runtime_readme", "Missing .librarian/README.librarian.md.", ".librarian/README.librarian.md")
    notes_dir = librarian_root / "notes"
    if not notes_dir.exists():
        _finding(report, "warning", "missing_notes_dir", "Missing .librarian/notes directory.", ".librarian/notes")
    else:
        existing = {path.name for path in notes_dir.glob("*.md")}
        for note_name in sorted(EXPECTED_NOTES - existing):
            _finding(report, "warning", "missing_main_note", f"Missing main note {note_name}.", f".librarian/notes/{note_name}")
    operations_path = librarian_root / "logs" / "operations.jsonl"
    if operations_path.exists():
        for index, line in enumerate(operations_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                _finding(report, "warning", "invalid_operations_log_line", f"Invalid operations.jsonl line {index}: {exc}", ".librarian/logs/operations.jsonl")


def _validate_scripts(librarian_root: Path, report: ValidationReport) -> None:
    scripts_dir = librarian_root / "scripts"
    if not scripts_dir.exists():
        return
    existing = {path.name for path in scripts_dir.glob("*.py")}
    if existing and not EXPECTED_RUNTIME_SCRIPTS <= existing:
        missing = sorted(EXPECTED_RUNTIME_SCRIPTS - existing)
        _finding(report, "warning", "missing_runtime_scripts", f"Missing runtime scripts: {', '.join(missing)}.", ".librarian/scripts")
    for script_path in scripts_dir.glob("*.py"):
        if not _script_is_read_only(script_path):
            _finding(report, "error", "script_may_modify_files", "Runtime helper script appears to modify files.", f".librarian/scripts/{script_path.name}")


def _script_is_read_only(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_CALLS:
                return False
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id in WRITE_MODULES and node.func.attr in WRITE_MODULE_CALLS:
                    return False
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and any(flag in str(node.args[1].value) for flag in ["w", "a", "+"]):
                    return False
    return True


def _write_report(root: Path, report: ValidationReport) -> ValidationReport:
    librarian_root = root / ".librarian"
    librarian_root.mkdir(parents=True, exist_ok=True)
    json_path = librarian_root / "validation_report.json"
    markdown_path = librarian_root / "validation_report.md"
    json_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return report


def _markdown_report(report: ValidationReport) -> str:
    lines = [
        "# Validation Report",
        "",
        f"- Workspace: `{report.workspace_root}`",
        f"- OK: `{report.ok}`",
        f"- Errors: `{report.counts.get('errors', 0)}`",
        f"- Warnings: `{report.counts.get('warnings', 0)}`",
        "",
        "| Severity | Code | Path | Message |",
        "| --- | --- | --- | --- |",
    ]
    for finding in report.findings:
        path = finding.path or "-"
        lines.append(f"| {finding.severity} | {finding.code} | `{path}` | {finding.message.replace('|', '\\|')} |")
    if not report.findings:
        lines.append("| info | clean | - | No validation findings. |")
    return "\n".join(lines) + "\n"


def _finding(
    report: ValidationReport,
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    report.findings.append(
        ValidationFinding(
            severity=severity,  # type: ignore[arg-type]
            code=code,
            message=message,
            path=path,
            properties=properties or {},
        )
    )


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
