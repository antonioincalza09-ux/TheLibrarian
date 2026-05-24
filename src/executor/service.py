from __future__ import annotations

import shutil
from pathlib import Path

from src.models import ExecutionResult, ManifestOperation, OrganizationPlan, PlanEntry
from src.reporter import write_manifest
from src.security import SafetyError, resolve_relative_path, resolve_root


def execute_plan(
    root: str | Path,
    plan: OrganizationPlan,
    *,
    dry_run: bool = True,
) -> ExecutionResult:
    resolved_root = resolve_root(root)
    plan_root = resolve_root(plan.root)

    if resolved_root != plan_root:
        raise SafetyError("Plan root does not match the assigned root.")

    skipped_entries = [entry for entry in plan.entries if entry.status != "planned"]
    warnings = list(plan.warnings)
    applied_operations: list[ManifestOperation] = []

    if dry_run:
        return ExecutionResult(
            root=str(resolved_root),
            dry_run=True,
            applied_operations=applied_operations,
            skipped_entries=skipped_entries,
            warnings=warnings,
            manifest_path=None,
        )

    for entry in plan.entries:
        if entry.status != "planned":
            continue

        source_path = resolve_relative_path(resolved_root, entry.source, must_exist=True)
        destination_path = resolve_relative_path(resolved_root, entry.destination, must_exist=False)

        if destination_path.exists():
            runtime_conflict = PlanEntry(
                source=entry.source,
                destination=entry.destination,
                reason=entry.reason,
                confidence=entry.confidence,
                category=entry.category,
                status="skipped_conflict",
                warning="Destination already exists at execution time.",
            )
            skipped_entries.append(runtime_conflict)
            warnings.append(f"{entry.source}: destination already exists at execution time.")
            continue

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))

        applied_operations.append(
            ManifestOperation(
                source=entry.source,
                destination=entry.destination,
                reason=entry.reason,
                confidence=entry.confidence,
                rollback_source=entry.destination,
                rollback_destination=entry.source,
            )
        )

    manifest_path = None
    if applied_operations:
        manifest_path = str(write_manifest(resolved_root, applied_operations, skipped_entries))

    return ExecutionResult(
        root=str(resolved_root),
        dry_run=False,
        applied_operations=applied_operations,
        skipped_entries=skipped_entries,
        warnings=warnings,
        manifest_path=manifest_path,
    )

