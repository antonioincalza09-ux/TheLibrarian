from __future__ import annotations

import re
from pathlib import Path

from src.librarian.rules.schema import Classification, DirectoryAnalysis, FileKind


PROJECT_ROOT_FILES = {"pyproject.toml", "package.json", "go.mod", "cargo.toml", "pom.xml"}
LOCK_FILES = {"poetry.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "cargo.lock", "pdm.lock"}
GENERATED_DIRECTORIES = {"dist", "build", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache", "coverage"}
VENDOR_DIRECTORIES = {"node_modules", "vendor", ".venv", "venv"}
SKIP_DIRECTORIES = {".git", ".librarian", ".thelibrarian", ".the_librarian"}
DOCUMENT_EXTENSIONS = {".md", ".txt", ".pdf", ".doc", ".docx", ".rtf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}
DATA_EXTENSIONS = {".csv", ".tsv", ".parquet", ".sqlite", ".db", ".jsonl"}
CONFIG_EXTENSIONS = {".toml", ".yaml", ".yml", ".ini", ".cfg", ".env"}
SOURCE_LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".sh": "Shell",
}
RISKY_FILENAMES = {"settings.py", ".env", ".env.local", "secrets.yml"}


def detect_language(path: Path) -> str | None:
    name = path.name.lower()
    if name == "dockerfile":
        return "Dockerfile"
    if name in {"makefile"}:
        return "Make"
    return SOURCE_LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


def detect_file_kind(path: Path, mime_type: str) -> FileKind:
    extension = path.suffix.lower()
    if detect_language(path):
        return "source_code"
    if extension in DOCUMENT_EXTENSIONS:
        return "document"
    if extension in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return "image"
    if extension in AUDIO_EXTENSIONS or mime_type.startswith("audio/"):
        return "audio"
    if extension in VIDEO_EXTENSIONS or mime_type.startswith("video/"):
        return "video"
    if extension in ARCHIVE_EXTENSIONS:
        return "archive"
    if extension in DATA_EXTENSIONS:
        return "data"
    if extension in CONFIG_EXTENSIONS or path.name.lower() in PROJECT_ROOT_FILES | LOCK_FILES:
        return "config"
    return "unknown"


def is_generated_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & GENERATED_DIRECTORIES) or path.name.endswith((".min.js", ".pyc"))


def is_vendor_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & VENDOR_DIRECTORIES)


def is_lock_file(path: Path) -> bool:
    return path.name.lower() in LOCK_FILES


def path_tokens(path: Path) -> list[str]:
    text = " ".join(path.parts).lower()
    return [token for token in re.split(r"[^a-z0-9]+", text) if token]


def classify_file(path: Path, file_kind: FileKind) -> Classification:
    tokens = set(path_tokens(path))
    if {"invoice", "fattura", "receipt"} & tokens:
        return Classification(domain="Finance", category="Receipts", confidence=0.92, reason="Matched finance keywords.")
    if {"contract", "agreement", "contratto"} & tokens:
        return Classification(domain="Legal", category="Contracts", confidence=0.92, reason="Matched legal keywords.")
    if {"cv", "resume"} & tokens:
        return Classification(domain="People", category="CV", confidence=0.9, reason="Matched resume keywords.")
    if {"meeting", "minutes", "verbale"} & tokens:
        return Classification(domain="Work", category="Meetings", confidence=0.88, reason="Matched meeting keywords.")
    if file_kind == "source_code":
        if "test" in tokens or path.name.lower().startswith("test_") or path.stem.lower().endswith("_test"):
            return Classification(domain="Code", category="Tests", confidence=0.96, reason="Looks like a test file.")
        return Classification(domain="Code", category="Project", confidence=0.9, reason="Recognized source code.")
    if file_kind == "config":
        return Classification(domain="Configuration", category="ProjectConfig", confidence=0.85, reason="Recognized config file.")
    if file_kind == "document":
        return Classification(domain="Documentation", category="Documents", confidence=0.7, reason="Recognized document type.")
    if file_kind == "data":
        return Classification(domain="Data", category="Datasets", confidence=0.78, reason="Recognized data file.")
    if file_kind == "image":
        return Classification(domain="Media", category="Images", confidence=0.82, reason="Recognized media file.")
    return Classification(domain="General", category="Unsorted", confidence=0.3, reason="No stronger offline signal found.")


def classify_directory(path: Path, child_names: list[str], dominant_languages: list[str], dominant_extensions: list[str]) -> DirectoryAnalysis:
    lowered_name = path.name.lower()
    lowered_children = {name.lower() for name in child_names}
    roles: list[str] = []
    reason = "Default conservative directory analysis."
    should_reorganize = True
    should_modify = False

    if lowered_name in GENERATED_DIRECTORIES:
        roles.append("generated")
        should_reorganize = False
        reason = "Generated directory."
    if lowered_name in VENDOR_DIRECTORIES:
        roles.append("vendor")
        should_reorganize = False
        reason = "Vendor directory."
    if lowered_name in {"tests", "test"}:
        roles.append("tests")
    if lowered_name in {"docs", "documentation"}:
        roles.append("docs")
    if lowered_name in {"assets", "static", "public"}:
        roles.append("assets")
    if lowered_name in {"src", "app", "lib"}:
        roles.append("source")
    if PROJECT_ROOT_FILES & lowered_children:
        roles.append("project_root")
        should_reorganize = False
        reason = "Looks like a codebase root; prefer logical views over physical moves."
    if not roles:
        roles.append("data" if any(ext in dominant_extensions for ext in [".csv", ".json"]) else "general")

    theme = dominant_languages[0] if dominant_languages else (roles[0].title() if roles else "General")
    return DirectoryAnalysis(
        dominant_extensions=dominant_extensions,
        dominant_languages=dominant_languages,
        possible_roles=roles,
        theme=theme,
        should_reorganize=should_reorganize,
        should_modify=should_modify,
        reason=reason,
    )


def risk_level_for(path: Path, file_kind: FileKind, generated_file: bool, vendor_file: bool, lock_file: bool) -> str:
    if vendor_file or lock_file or path.name.lower() in RISKY_FILENAMES:
        return "high"
    if generated_file or file_kind in {"archive", "video", "audio"}:
        return "medium"
    return "low"


def should_move_file(path: Path, file_kind: FileKind, generated_file: bool, vendor_file: bool, lock_file: bool, parent_roles: list[str]) -> bool:
    if generated_file or vendor_file or lock_file:
        return False
    if "project_root" in parent_roles or "source" in parent_roles or file_kind == "source_code":
        return False
    return file_kind in {"document", "image", "data", "archive", "unknown"}
