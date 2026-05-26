from __future__ import annotations

import json
from pathlib import Path

from src.librarian.metadata import file_sidecar_path
from src.librarian.rules.schema import Manifest, OperationLog, WorkspacePlan
from src.librarian.sidecars import read_manifest, write_sidecars


def apply_plan(root: str | Path, *, plan: WorkspacePlan | None = None) -> list[OperationLog]:
    resolved_root = Path(root).resolve()
    workspace_plan = plan or load_plan(resolved_root)
    operations: list[OperationLog] = []
    logs_path = resolved_root / ".librarian" / "logs" / "operations.jsonl"
    logs_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(resolved_root)
    file_index = {node.current_path: node for node in manifest.files}
    directory_index = {node.current_path: node for node in manifest.directories}
    covered_prefixes: list[str] = []

    for entry in workspace_plan.entries:
        source_path = resolved_root / entry.source
        destination_path = resolved_root / entry.destination
        if any(_is_descendant_or_same(entry.source, prefix) for prefix in covered_prefixes):
            operations.append(
                OperationLog(
                    timestamp=workspace_plan.generated_at,
                    action="move",
                    source=entry.source,
                    destination=entry.destination,
                    status="skipped",
                    message="Covered by applied directory move.",
                )
            )
            continue
        if not entry.safe_to_move:
            operations.append(
                OperationLog(
                    timestamp=workspace_plan.generated_at,
                    action="move",
                    source=entry.source,
                    destination=entry.destination,
                    status="skipped",
                    message=entry.reason,
                )
            )
            continue
        if not source_path.exists() or destination_path.exists():
            operations.append(
                OperationLog(
                    timestamp=workspace_plan.generated_at,
                    action="move",
                    source=entry.source,
                    destination=entry.destination,
                    status="warning",
                    message="Source missing or destination exists.",
                )
            )
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.replace(destination_path)
        _prune_empty_ancestors(source_path.parent, resolved_root)
        if entry.node_type == "directory":
            covered_prefixes.append(entry.source)
            file_index = _rewrite_file_index_for_directory_move(file_index, entry.source, entry.destination)
            directory_index = _rewrite_directory_index_for_directory_move(directory_index, entry.source, entry.destination)
        elif entry.source in file_index:
            node = file_index.pop(entry.source)
            old_sidecar = file_sidecar_path(resolved_root, node)
            node.current_path = entry.destination
            node.proposed_path = entry.destination
            new_sidecar = file_sidecar_path(resolved_root, node)
            if old_sidecar.exists():
                new_sidecar.parent.mkdir(parents=True, exist_ok=True)
                old_sidecar.replace(new_sidecar)
            file_index[entry.destination] = node
        operations.append(
            OperationLog(
                timestamp=workspace_plan.generated_at,
                action="move",
                source=entry.source,
                destination=entry.destination,
                status="applied",
                message=entry.reason,
            )
        )

    _append_operations(logs_path, operations)
    updated_manifest = manifest.model_copy(update={"files": list(file_index.values()), "directories": list(directory_index.values())})
    write_sidecars(resolved_root, updated_manifest)
    return operations


def rollback_plan(root: str | Path) -> list[OperationLog]:
    resolved_root = Path(root).resolve()
    logs_path = resolved_root / ".librarian" / "logs" / "operations.jsonl"
    if not logs_path.exists():
        return []
    lines = [json.loads(line) for line in logs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    move_entries = [OperationLog.model_validate(line) for line in lines if line.get("action") == "move" and line.get("status") == "applied"]
    rollback_operations: list[OperationLog] = []
    manifest = read_manifest(resolved_root)
    file_index = {node.current_path: node for node in manifest.files}
    directory_index = {node.current_path: node for node in manifest.directories}

    for entry in reversed(move_entries):
        current_path = resolved_root / entry.destination
        original_path = resolved_root / entry.source
        if not current_path.exists():
            rollback_operations.append(
                OperationLog(
                    timestamp=entry.timestamp,
                    action="rollback",
                    source=entry.destination,
                    destination=entry.source,
                    status="warning",
                    message="Cannot rollback missing file.",
                )
            )
            continue
        if original_path.exists():
            rollback_operations.append(
                OperationLog(
                    timestamp=entry.timestamp,
                    action="rollback",
                    source=entry.destination,
                    destination=entry.source,
                    status="warning",
                    message="Cannot rollback because original path is occupied.",
                )
            )
            continue
        original_path.parent.mkdir(parents=True, exist_ok=True)
        current_path.replace(original_path)
        _prune_empty_ancestors(current_path.parent, resolved_root)
        if _looks_like_directory_operation(entry, directory_index):
            file_index = _rewrite_file_index_for_directory_move(file_index, entry.destination, entry.source)
            directory_index = _rewrite_directory_index_for_directory_move(directory_index, entry.destination, entry.source)
        else:
            node = file_index.pop(entry.destination, None)
            if node is not None:
                old_sidecar = file_sidecar_path(resolved_root, node)
                node.current_path = entry.source
                node.proposed_path = entry.source
                new_sidecar = file_sidecar_path(resolved_root, node)
                if old_sidecar.exists():
                    new_sidecar.parent.mkdir(parents=True, exist_ok=True)
                    old_sidecar.replace(new_sidecar)
                file_index[entry.source] = node
        rollback_operations.append(
            OperationLog(
                timestamp=entry.timestamp,
                action="rollback",
                source=entry.destination,
                destination=entry.source,
                status="rolled_back",
                message="Rollback applied.",
            )
        )

    _append_operations(logs_path, rollback_operations)
    updated_manifest = manifest.model_copy(update={"files": list(file_index.values()), "directories": list(directory_index.values())})
    write_sidecars(resolved_root, updated_manifest)
    return rollback_operations


def load_plan(root: str | Path) -> WorkspacePlan:
    plan_path = Path(root).resolve() / ".librarian" / "plan.json"
    return WorkspacePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))


def _append_operations(path: Path, operations: list[OperationLog]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for operation in operations:
            handle.write(json.dumps(operation.model_dump(mode="json")) + "\n")


def _rewrite_file_index_for_directory_move(
    file_index: dict[str, object],
    source_prefix: str,
    destination_prefix: str,
) -> dict[str, object]:
    rewritten: dict[str, object] = {}
    for current_path, node in file_index.items():
        if current_path == source_prefix or current_path.startswith(f"{source_prefix}/"):
            suffix = current_path.removeprefix(source_prefix).lstrip("/")
            node.current_path = destination_prefix if not suffix else f"{destination_prefix}/{suffix}"
            node.proposed_path = node.current_path
            rewritten[node.current_path] = node
        else:
            rewritten[current_path] = node
    return rewritten


def _rewrite_directory_index_for_directory_move(
    directory_index: dict[str, object],
    source_prefix: str,
    destination_prefix: str,
) -> dict[str, object]:
    rewritten: dict[str, object] = {}
    for current_path, node in directory_index.items():
        if current_path == ".":
            rewritten[current_path] = node
            continue
        if current_path == source_prefix or current_path.startswith(f"{source_prefix}/"):
            suffix = current_path.removeprefix(source_prefix).lstrip("/")
            node.current_path = destination_prefix if not suffix else f"{destination_prefix}/{suffix}"
            node.proposed_path = node.current_path
            rewritten[node.current_path] = node
        else:
            rewritten[current_path] = node
    return rewritten


def _is_descendant_or_same(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _looks_like_directory_operation(entry: OperationLog, directory_index: dict[str, object]) -> bool:
    return entry.source in directory_index or entry.destination in directory_index


def _prune_empty_ancestors(start: Path, root: Path) -> None:
    current = start
    while current != root and current.exists():
        try:
            next(current.iterdir())
            break
        except StopIteration:
            current.rmdir()
            current = current.parent
