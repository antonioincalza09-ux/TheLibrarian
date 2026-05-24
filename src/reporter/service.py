from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models import ExecutionResult, Inventory, ManifestOperation, OrganizationPlan, PlanEntry
from src.security import normalize_relative_path, resolve_root


APP_VERSION = "0.1.0"
MANIFEST_DIRECTORY = Path(".the_librarian") / "manifests"
REPORT_DIRECTORY = Path(".the_librarian") / "reports"


def render_plan_report(
    inventory: Inventory,
    plan: OrganizationPlan,
    execution: ExecutionResult | None = None,
) -> str:
    lines = [
        f"Root: {inventory.root}",
        f"Files scanned: {inventory.total_files}",
        f"Total bytes: {inventory.total_bytes}",
        f"Provider: {plan.provider}",
        f"Planned moves: {len(plan.planned_entries)}",
        f"Already organized: {len(plan.already_organized_entries)}",
        f"Review targets: {len(plan.review_entries)}",
        f"Conflicts: {len(plan.conflict_entries)}",
    ]

    if inventory.warnings:
        lines.append(f"Scan warnings: {len(inventory.warnings)}")

    if plan.warnings:
        lines.append(f"Plan warnings: {len(plan.warnings)}")

    if execution is not None:
        lines.append(f"Dry run: {execution.dry_run}")
        lines.append(f"Applied moves: {execution.applied_count}")
        if execution.manifest_path:
            lines.append(f"Manifest: {execution.manifest_path}")

    lines.append("")
    lines.append("Plan details:")

    for entry in plan.entries:
        detail = (
            f"- [{entry.status}] {entry.source} -> {entry.destination} "
            f"(confidence {entry.confidence:.2f}) {entry.reason}"
        )
        if entry.warning:
            detail = f"{detail} Warning: {entry.warning}"
        lines.append(detail)

    return "\n".join(lines)


def write_manifest(
    root: str | Path,
    operations: list[ManifestOperation],
    skipped_entries: list[PlanEntry],
) -> Path:
    resolved_root = resolve_root(root)
    manifest_directory = resolved_root / MANIFEST_DIRECTORY
    manifest_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = manifest_directory / f"rollback-{timestamp}.json"
    payload = {
        "version": 1,
        "app_version": APP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(resolved_root),
        "operations": [operation.to_dict() for operation in operations],
        "skipped_entries": [entry.to_dict() for entry in skipped_entries],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def write_report(
    root: str | Path,
    name: str,
    content: str,
    *,
    output_directory: str | Path = REPORT_DIRECTORY,
) -> Path:
    resolved_root = resolve_root(root)
    report_directory = resolved_root / Path(normalize_relative_path(str(output_directory)))
    report_directory.mkdir(parents=True, exist_ok=True)
    report_path = report_directory / name
    report_path.write_text(content, encoding="utf-8")
    return report_path
