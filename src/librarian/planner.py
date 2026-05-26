from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from src.librarian.rules.schema import Manifest, PlanMove, WorkspaceNode, WorkspacePlan


SAFE_BUCKETS = {
    "Documentation": "docs",
    "Finance": "finance",
    "Legal": "legal",
    "People": "people",
    "Work": "work",
    "Media": "media",
    "Data": "data",
    "General": "review",
}


def build_plan(root: str | Path, manifest: Manifest) -> WorkspacePlan:
    resolved_root = Path(root).resolve()
    existing_paths = {node.current_path for node in manifest.files} | {directory.current_path for directory in manifest.directories}
    planned_destinations: set[str] = set()
    entries: list[PlanMove] = []
    warnings: list[str] = []
    directory_entries, covered_files = _build_directory_entries(manifest, existing_paths, planned_destinations, warnings)
    entries.extend(directory_entries)

    for file_node in manifest.files:
        if file_node.current_path in covered_files:
            directory_destination = covered_files[file_node.current_path]
            relative_tail = PurePosixPath(file_node.current_path).relative_to(PurePosixPath(directory_destination["source"]))
            destination = PurePosixPath(directory_destination["destination"], relative_tail).as_posix()
            entries.append(
                PlanMove(
                    source=file_node.current_path,
                    destination=destination,
                    node_type="file",
                    reason="Covered by planned directory move.",
                    confidence=file_node.classification.confidence,
                    safe_to_move=False,
                    logical_only=False,
                    collision=False,
                    status="covered_by_directory",
                )
            )
            continue
        destination, logical_only, reason = propose_path(file_node, manifest)
        collision = not logical_only and (destination in existing_paths or destination in planned_destinations)
        safe_to_move = file_node.should_move and not collision and not logical_only and not file_node.vendor_file and not file_node.generated_file and not file_node.lock_file
        status = "logical_only" if logical_only else "planned"
        if collision:
            warnings.append(f"Collision detected for {file_node.current_path} -> {destination}")
            status = "collision"
        if safe_to_move:
            planned_destinations.add(destination)
        entries.append(
            PlanMove(
                source=file_node.current_path,
                destination=destination,
                node_type="file",
                reason=reason,
                confidence=file_node.classification.confidence,
                safe_to_move=safe_to_move,
                logical_only=logical_only,
                collision=collision,
                status=status,
            )
        )

    plan = WorkspacePlan(
        workspace_root=str(resolved_root),
        generated_at=datetime.now(timezone.utc).isoformat(),
        entries=entries,
        warnings=warnings,
    )
    plan_path = resolved_root / ".librarian" / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan.model_dump(mode="json"), indent=2), encoding="utf-8")
    return plan


def propose_path(file_node: WorkspaceNode, manifest: Manifest) -> tuple[str, bool, str]:
    current = PurePosixPath(file_node.current_path)
    if _belongs_to_project_root(current, manifest):
        return file_node.current_path, True, "Codebase root detected; keeping physical path stable and exposing logical view only."
    domain_bucket = SAFE_BUCKETS.get(file_node.classification.domain, "review")
    category = _slugify(file_node.classification.category or "unsorted")
    normalized_name = _normalized_filename(current.name)
    destination = PurePosixPath(domain_bucket, category, normalized_name).as_posix()
    return destination, False, f"Offline classification suggests bucket {domain_bucket}/{category}."


def propose_directory_path(directory_node: WorkspaceNode, manifest: Manifest) -> tuple[str, bool, str]:
    current = PurePosixPath(directory_node.current_path)
    analysis = directory_node.directory_analysis
    if analysis is None:
        return directory_node.current_path, True, "Missing directory analysis; keeping directory in place."
    if current == PurePosixPath("."):
        return directory_node.current_path, True, "Workspace root cannot be moved."
    if _belongs_to_project_root(current, manifest):
        return directory_node.current_path, True, "Codebase root detected; keeping directory in place."
    blocked_roles = {"source", "tests", "vendor", "generated", "cache", "project_root"}
    if any(role in blocked_roles for role in analysis.possible_roles):
        return directory_node.current_path, True, "Directory role is not safe for physical reorganization."
    descendant_files = _descendant_files(directory_node.current_path, manifest)
    movable_files = [
        node
        for node in descendant_files
        if node.should_move and not node.vendor_file and not node.generated_file and not node.lock_file
    ]
    if not descendant_files or len(movable_files) != len(descendant_files):
        return directory_node.current_path, True, "Directory contains mixed or protected files; using logical view only."
    domain_counts = Counter(node.classification.domain for node in movable_files)
    category_counts = Counter(node.classification.category for node in movable_files)
    domain_bucket = SAFE_BUCKETS.get(domain_counts.most_common(1)[0][0], "review")
    category = _slugify(category_counts.most_common(1)[0][0] or current.name)
    destination = PurePosixPath(domain_bucket, category, _slugify(current.name)).as_posix()
    return destination, False, "All descendant files are safe to move together as one directory."


def _belongs_to_project_root(path: PurePosixPath, manifest: Manifest) -> bool:
    parent_chain = [path.parent]
    while parent_chain[-1] != PurePosixPath(".") and str(parent_chain[-1]) != ".":
        parent_chain.append(parent_chain[-1].parent)
    directory_map = {directory.current_path: directory for directory in manifest.directories}
    for parent in parent_chain:
        key = "." if str(parent) == "." else parent.as_posix()
        node = directory_map.get(key)
        if node and node.directory_analysis and "project_root" in node.directory_analysis.possible_roles:
            return True
    return False


def _build_directory_entries(
    manifest: Manifest,
    existing_paths: set[str],
    planned_destinations: set[str],
    warnings: list[str],
) -> tuple[list[PlanMove], dict[str, dict[str, str]]]:
    entries: list[PlanMove] = []
    covered_files: dict[str, dict[str, str]] = {}
    covered_directories: set[str] = set()
    for directory_node in sorted(manifest.directories, key=lambda item: item.depth):
        if directory_node.current_path == ".":
            continue
        if any(_is_child_path(directory_node.current_path, ancestor) for ancestor in covered_directories):
            parent_source = next(ancestor for ancestor in covered_directories if _is_child_path(directory_node.current_path, ancestor))
            parent_destination = next(
                planned.destination
                for planned in entries
                if planned.node_type == "directory" and planned.source == parent_source
            )
            suffix = PurePosixPath(directory_node.current_path).relative_to(PurePosixPath(parent_source))
            entries.append(
                PlanMove(
                    source=directory_node.current_path,
                    destination=PurePosixPath(parent_destination, suffix).as_posix(),
                    node_type="directory",
                    reason="Covered by planned parent directory move.",
                    confidence=0.0,
                    safe_to_move=False,
                    logical_only=False,
                    collision=False,
                    status="covered_by_directory",
                )
            )
            continue
        destination, logical_only, reason = propose_directory_path(directory_node, manifest)
        collision = not logical_only and (destination in existing_paths or destination in planned_destinations)
        safe_to_move = directory_node.should_move and not logical_only and not collision and destination != directory_node.current_path
        status = "logical_only" if logical_only else "planned"
        if collision:
            warnings.append(f"Collision detected for directory {directory_node.current_path} -> {destination}")
            status = "collision"
        entry = PlanMove(
            source=directory_node.current_path,
            destination=destination,
            node_type="directory",
            reason=reason,
            confidence=0.95 if safe_to_move else 0.0,
            safe_to_move=safe_to_move,
            logical_only=logical_only,
            collision=collision,
            status=status,
        )
        entries.append(entry)
        if safe_to_move:
            planned_destinations.add(destination)
            covered_directories.add(directory_node.current_path)
            for file_node in _descendant_files(directory_node.current_path, manifest):
                covered_files[file_node.current_path] = {
                    "source": directory_node.current_path,
                    "destination": destination,
                }
    return entries, covered_files


def _descendant_files(directory_path: str, manifest: Manifest) -> list[WorkspaceNode]:
    prefix = f"{directory_path}/"
    return [node for node in manifest.files if node.current_path.startswith(prefix)]


def _is_child_path(path: str, ancestor: str) -> bool:
    return path.startswith(f"{ancestor}/")


def _normalized_filename(name: str) -> str:
    stem = PurePosixPath(name).stem
    suffix = PurePosixPath(name).suffix
    normalized = re.sub(r"[^A-Za-z0-9.-]+", "-", stem.strip()).strip("-").lower() or "unnamed"
    return f"{normalized}{suffix.lower()}"


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower() or "unsorted"
