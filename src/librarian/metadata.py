from __future__ import annotations

from pathlib import Path

from src.librarian.rules.schema import Manifest, WorkspaceNode


def node_to_sidecar_payload(node: WorkspaceNode) -> dict:
    payload = node.model_dump(mode="json")
    payload["status"] = list(node.status)
    payload["errors"] = list(node.errors)
    return payload


def manifest_to_payload(manifest: Manifest) -> dict:
    return manifest.model_dump(mode="json")


def file_sidecar_path(root: Path, node: WorkspaceNode) -> Path:
    return root / f"{node.current_path}.librarian.yaml"


def directory_sidecar_path(root: Path, node: WorkspaceNode) -> Path:
    if node.current_path == ".":
        return root / ".librarian.yaml"
    return root / node.current_path / ".librarian.yaml"
