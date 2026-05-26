from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.librarian import __version__
from src.librarian.classifiers import (
    SKIP_DIRECTORIES,
    classify_file,
    detect_file_kind,
    detect_language,
    is_generated_path,
    is_lock_file,
    is_vendor_path,
    risk_level_for,
    should_move_file,
)
from src.librarian.code_analyzers.generic_code_analyzer import analyze_generic_code_file
from src.librarian.code_analyzers.python_analyzer import analyze_python_file
from src.librarian.directory_analyzer import analyze_directory
from src.librarian.fingerprint import detect_mime_type, sha256_path, sha256_text
from src.librarian.rules.schema import Manifest, ManifestCounts, ScanResult, WorkspaceNode


def scan_workspace(root: str | Path) -> ScanResult:
    resolved_root = Path(root).resolve()
    indexed_at = datetime.now(timezone.utc).isoformat()
    file_nodes: list[WorkspaceNode] = []
    directory_paths: list[Path] = []
    warnings: list[str] = []
    errors: list[str] = []

    for current_directory, directory_names, file_names in _walk_root(resolved_root):
        current_path = Path(current_directory)
        directory_paths.append(current_path)
        for file_name in sorted(file_names):
            if file_name.endswith(".librarian.yaml") or file_name == ".librarian.yaml":
                continue
            file_path = current_path / file_name
            node, warning = _scan_file(file_path, resolved_root, indexed_at)
            file_nodes.append(node)
            if warning:
                warnings.append(warning)

    directory_nodes: list[WorkspaceNode] = []
    for directory_path in sorted(directory_paths, key=lambda item: (len(item.parts), str(item))):
        relative = _relative_path(directory_path, resolved_root)
        analysis = analyze_directory(directory_path, resolved_root, file_nodes, directory_paths)
        node = WorkspaceNode(
            librarian_id=_librarian_id(relative, "directory"),
            type="directory",
            original_path=relative,
            current_path=relative,
            proposed_path=relative,
            name=directory_path.name or resolved_root.name,
            indexed_at=indexed_at,
            title=directory_path.name or resolved_root.name,
            summary=analysis.reason,
            human_description=f"Directory {relative} analyzed for structure and role.",
            developer_notes=[f"Roles: {', '.join(analysis.possible_roles)}"],
            tags=analysis.possible_roles,
            classification=classify_file(Path(relative), "config"),
            directory_analysis=analysis,
            depth=0 if relative == "." else len(Path(relative).parts),
            parent_path=None if relative == "." else str(Path(relative).parent).replace("\\", "/"),
            should_modify=analysis.should_modify,
            should_move=analysis.should_reorganize,
            risk_level="high" if "project_root" in analysis.possible_roles else "low",
        )
        directory_nodes.append(node)

    return ScanResult(
        workspace_root=str(resolved_root),
        generated_at=indexed_at,
        files=file_nodes,
        directories=directory_nodes,
        warnings=warnings,
        errors=errors,
    )


def build_manifest(scan: ScanResult, *, marked_files: int = 0, marked_directories: int = 0, sidecar_stats: dict[str, int] | None = None) -> Manifest:
    sidecar_stats = sidecar_stats or {}
    languages = sorted({node.detected_language for node in scan.files if node.detected_language})
    domains = sorted({node.classification.domain for node in scan.files if node.classification.domain})
    entrypoints = sorted(
        {
            f"{node.current_path}:{entrypoint}"
            for node in scan.files
            if node.code_metadata is not None
            for entrypoint in node.code_metadata.entrypoints
        }
    )
    counts = ManifestCounts(
        files=len(scan.files),
        directories=len(scan.directories),
        marked_files=marked_files,
        marked_directories=marked_directories,
        unreadable_files=len([node for node in scan.files if not node.readable]),
        missing_sidecars=sidecar_stats.get("missing_sidecars", 0),
        orphan_sidecars=sidecar_stats.get("orphan_sidecars", 0),
        applied_operations=sidecar_stats.get("applied_operations", 0),
    )
    return Manifest(
        workspace_root=scan.workspace_root,
        generated_at=scan.generated_at,
        librarian_version=__version__,
        files=scan.files,
        directories=scan.directories,
        counts=counts,
        detected_languages=languages,
        detected_domains=domains,
        entrypoints=entrypoints,
        warnings=scan.warnings,
        errors=scan.errors,
    )


def _scan_file(file_path: Path, root: Path, indexed_at: str) -> tuple[WorkspaceNode, str | None]:
    relative = _relative_path(file_path, root)
    mime_type = detect_mime_type(file_path)
    content_hash = sha256_path(file_path)
    readable = content_hash is not None
    read_error = None if readable else "Unreadable file."
    extension = file_path.suffix.lower()
    file_kind = detect_file_kind(file_path, mime_type)
    language = detect_language(file_path)
    generated_file = is_generated_path(file_path.relative_to(root))
    vendor_file = is_vendor_path(file_path.relative_to(root))
    lock_file = is_lock_file(file_path)
    risk_level = risk_level_for(file_path, file_kind, generated_file, vendor_file, lock_file)
    classification = classify_file(file_path, file_kind)
    code_metadata = None
    if file_kind == "source_code":
        if language == "Python":
            code_metadata = analyze_python_file(file_path, root)
        else:
            code_metadata = analyze_generic_code_file(file_path, language)
        code_metadata.generated_file = generated_file
        code_metadata.vendor_file = vendor_file
        code_metadata.lock_file = lock_file
        code_metadata.risk_level = risk_level
        code_metadata.should_modify = False
        code_metadata.should_move = False
    parent_roles = _parent_roles(file_path)
    try:
        stat = file_path.stat()
        size_bytes = stat.st_size
        created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        size_bytes = 0
        created_at = None
        modified_at = None

    should_move = should_move_file(file_path, file_kind, generated_file, vendor_file, lock_file, parent_roles)
    node = WorkspaceNode(
        librarian_id=_librarian_id(relative, "file"),
        type="file",
        original_path=relative,
        current_path=relative,
        proposed_path=relative,
        name=file_path.name,
        extension=extension or "",
        size_bytes=size_bytes,
        created_at=created_at,
        modified_at=modified_at,
        indexed_at=indexed_at,
        mime_type=mime_type,
        content_hash=content_hash,
        name_hash=sha256_text(file_path.name),
        readable=readable,
        read_error=read_error,
        file_kind=file_kind,
        detected_language=language,
        title=file_path.stem,
        summary=classification.reason,
        human_description=f"File {relative} classified as {classification.domain}/{classification.category}.",
        developer_notes=[] if code_metadata is None else [code_metadata.reason],
        tags=[classification.domain, classification.category],
        classification=classification,
        code_metadata=code_metadata,
        depth=len(Path(relative).parts),
        parent_path=str(Path(relative).parent).replace("\\", "/"),
        generated_file=generated_file,
        vendor_file=vendor_file,
        lock_file=lock_file,
        should_modify=False,
        should_move=should_move,
        risk_level=risk_level,
    )
    warning = None if readable else f"Unreadable file: {relative}"
    return node, warning


def _walk_root(root: Path):
    for current_directory, directory_names, file_names in __import__("os").walk(root, topdown=True):
        directory_names[:] = [
            directory_name
            for directory_name in sorted(directory_names)
            if directory_name.lower() not in SKIP_DIRECTORIES
        ]
        yield current_directory, directory_names, sorted(file_names)


def _relative_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return "." if str(relative) == "." else relative.as_posix()


def _librarian_id(relative_path: str, node_type: str) -> str:
    return sha256_text(f"{node_type}:{relative_path}")[:16]


def _parent_roles(file_path: Path) -> list[str]:
    lowered_parts = {part.lower() for part in file_path.parts}
    roles: list[str] = []
    if "tests" in lowered_parts or "test" in lowered_parts:
        roles.append("tests")
    if "src" in lowered_parts or "app" in lowered_parts or "lib" in lowered_parts:
        roles.append("source")
    if any(marker in lowered_parts for marker in ["node_modules", "vendor", ".venv"]):
        roles.append("vendor")
    if any(marker in lowered_parts for marker in ["dist", "build", "__pycache__"]):
        roles.append("generated")
    return roles
