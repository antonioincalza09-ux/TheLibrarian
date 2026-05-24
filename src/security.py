from __future__ import annotations

from pathlib import Path, PurePosixPath


class SafetyError(ValueError):
    """Raised when a requested path violates organizer safety constraints."""


def resolve_root(root: str | Path) -> Path:
    resolved_root = Path(root).expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise SafetyError(f"Assigned root must be a directory: {resolved_root}")
    return resolved_root


def normalize_relative_path(path_value: str) -> str:
    normalized = PurePosixPath(path_value.replace("\\", "/"))

    if normalized.is_absolute():
        raise SafetyError(f"Absolute paths are not allowed: {path_value}")

    if ".." in normalized.parts:
        raise SafetyError(f"Relative path escapes the assigned root: {path_value}")

    parts = [part for part in normalized.parts if part not in ("", ".")]
    if not parts:
        raise SafetyError("Relative path must target a file inside the assigned root.")

    return PurePosixPath(*parts).as_posix()


def resolve_relative_path(root: str | Path, relative_path: str, *, must_exist: bool) -> Path:
    resolved_root = resolve_root(root)
    normalized_path = normalize_relative_path(relative_path)
    candidate = (resolved_root / Path(normalized_path)).resolve(strict=must_exist)

    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise SafetyError(f"Path escapes the assigned root: {relative_path}") from exc

    return candidate

