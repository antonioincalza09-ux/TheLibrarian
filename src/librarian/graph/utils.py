from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


def stable_id(prefix: str, value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.:/-]+", "-", value.strip()).strip("-")
    return f"{prefix}:{normalized or 'unknown'}"


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower() or "unknown"


def relative_posix(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return "." if str(relative) == "." else relative.as_posix()


def parent_path(path: str) -> str | None:
    if path == ".":
        return None
    parent = PurePosixPath(path).parent
    return "." if str(parent) == "." else parent.as_posix()


def as_json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def compact(value: str | None, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).replace("\n", " ").strip()
    return text or fallback


def markdown_escape(value: str | None) -> str:
    return compact(value).replace("|", "\\|")
