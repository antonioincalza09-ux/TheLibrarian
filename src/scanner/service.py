from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from src.models import FileRecord, Inventory
from src.security import resolve_root


SKIPPED_DIRECTORY_NAMES = {".git", ".the_librarian", "__pycache__"}


def scan_directory(root: str | Path) -> Inventory:
    resolved_root = resolve_root(root)
    files: list[FileRecord] = []
    warnings: list[str] = []

    for current_directory, directory_names, file_names in os.walk(resolved_root, topdown=True, followlinks=False):
        current_path = Path(current_directory)
        pruned_directories: list[str] = []

        for directory_name in directory_names:
            directory_path = current_path / directory_name
            if directory_name in SKIPPED_DIRECTORY_NAMES:
                continue
            if directory_path.is_symlink():
                relative_directory = directory_path.relative_to(resolved_root).as_posix()
                warnings.append(f"Skipped symlink directory: {relative_directory}")
                continue
            pruned_directories.append(directory_name)

        directory_names[:] = pruned_directories

        for file_name in file_names:
            file_path = current_path / file_name
            if file_path.is_symlink():
                relative_file = file_path.relative_to(resolved_root).as_posix()
                warnings.append(f"Skipped symlink file: {relative_file}")
                continue

            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(resolved_root)
            parent = relative_path.parent.as_posix() if relative_path.parent != Path(".") else "."
            file_stat = file_path.stat(follow_symlinks=False)
            modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc).isoformat()

            files.append(
                FileRecord(
                    relative_path=relative_path.as_posix(),
                    name=file_path.name,
                    size_bytes=file_stat.st_size,
                    modified_at=modified_at,
                    extension=file_path.suffix.lower(),
                    parent=parent,
                )
            )

    files.sort(key=lambda item: item.relative_path)
    warnings.sort()
    return Inventory(root=str(resolved_root), files=files, warnings=warnings)
