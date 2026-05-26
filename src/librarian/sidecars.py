from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.librarian.metadata import directory_sidecar_path, file_sidecar_path, manifest_to_payload, node_to_sidecar_payload
from src.librarian.rules.schema import Manifest, WorkspaceNode


def write_sidecars(root: str | Path, manifest: Manifest) -> dict[str, int]:
    resolved_root = Path(root).resolve()
    marked_files = 0
    marked_directories = 0
    for directory in manifest.directories:
        path = directory_sidecar_path(resolved_root, directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(node_to_sidecar_payload(directory), sort_keys=False, allow_unicode=False), encoding="utf-8")
        marked_directories += 1
    for file_node in manifest.files:
        path = file_sidecar_path(resolved_root, file_node)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(node_to_sidecar_payload(file_node), sort_keys=False, allow_unicode=False), encoding="utf-8")
        marked_files += 1
    manifest_path = resolved_root / ".librarian" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest_to_payload(manifest), indent=2), encoding="utf-8")
    return {"marked_files": marked_files, "marked_directories": marked_directories}


def collect_sidecar_status(root: str | Path, manifest: Manifest) -> dict[str, int]:
    resolved_root = Path(root).resolve()
    expected = {
        str(directory_sidecar_path(resolved_root, directory).resolve(strict=False))
        for directory in manifest.directories
    } | {
        str(file_sidecar_path(resolved_root, file_node).resolve(strict=False))
        for file_node in manifest.files
    }
    existing = {
        str(path.resolve(strict=False))
        for path in resolved_root.rglob("*.librarian.yaml")
        if ".librarian" not in path.parts
    }
    missing = len(expected - existing)
    orphan = len(existing - expected)
    return {"missing_sidecars": missing, "orphan_sidecars": orphan}


def read_manifest(root: str | Path) -> Manifest:
    manifest_path = Path(root).resolve() / ".librarian" / "manifest.json"
    return Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
