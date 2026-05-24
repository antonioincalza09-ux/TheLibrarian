from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models import ExecutionResult, Inventory, ManifestOperation, OrganizationPlan, PlanEntry
from src.security import normalize_relative_path, resolve_root


APP_VERSION = "0.1.0"
RUNTIME_DIRECTORY = Path(".thelibrarian")
MANIFEST_DIRECTORY = RUNTIME_DIRECTORY / "manifests"
REPORT_DIRECTORY = RUNTIME_DIRECTORY / "reports"
PLAN_DIRECTORY = RUNTIME_DIRECTORY / "plans"


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

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest_path = _unique_path(manifest_directory, f"rollback-{timestamp}", ".json")
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


def write_plan_artifact(root: str | Path, plan: OrganizationPlan) -> Path:
    resolved_root = resolve_root(root)
    plan_directory = resolved_root / PLAN_DIRECTORY
    plan_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    plan_path = _unique_path(plan_directory, f"plan-{timestamp}", ".json")
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    return plan_path


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
    requested_path = Path(name)
    if requested_path.name != name:
        raise ValueError(f"Report name must not include directories: {name}")
    report_path = report_directory / name
    if report_path.exists():
        report_path = _unique_path(report_directory, report_path.stem, report_path.suffix)
    report_path.write_text(content, encoding="utf-8")
    return report_path


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate
