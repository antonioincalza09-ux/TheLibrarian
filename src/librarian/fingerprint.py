from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path


def sha256_path(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def detect_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type:
        return mime_type
    return "application/octet-stream" if path.suffix else "unknown/unknown"
