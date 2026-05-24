from __future__ import annotations

from pathlib import PurePosixPath

from src.models import DEFAULT_CATEGORY_DIRECTORIES, Inventory, OrganizationPlan, PlanEntry


AMBIGUOUS_EXTENSIONS = {".json", ".xml", ".yml", ".yaml"}
KNOWN_CATEGORY_DIRECTORIES = set(DEFAULT_CATEGORY_DIRECTORIES)
REVIEW_CATEGORY = "Review"

CATEGORY_BY_EXTENSION = {
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".txt": "Documents",
    ".rtf": "Documents",
    ".md": "Documents",
    ".odt": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".jpg": "Media",
    ".jpeg": "Media",
    ".png": "Media",
    ".gif": "Media",
    ".webp": "Media",
    ".svg": "Media",
    ".mp3": "Media",
    ".wav": "Media",
    ".flac": "Media",
    ".mp4": "Media",
    ".mov": "Media",
    ".avi": "Media",
    ".mkv": "Media",
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".tsx": "Code",
    ".jsx": "Code",
    ".css": "Code",
    ".html": "Code",
    ".toml": "Code",
    ".ini": "Code",
    ".cfg": "Code",
    ".sh": "Code",
    ".ps1": "Code",
    ".bat": "Code",
    ".java": "Code",
    ".c": "Code",
    ".cpp": "Code",
    ".h": "Code",
    ".hpp": "Code",
    ".cs": "Code",
    ".go": "Code",
    ".rs": "Code",
    ".php": "Code",
    ".sql": "Code",
    ".zip": "Archives",
    ".rar": "Archives",
    ".7z": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".bz2": "Archives",
    ".xz": "Archives",
    ".csv": "Data",
    ".tsv": "Data",
    ".xls": "Data",
    ".xlsx": "Data",
    ".parquet": "Data",
    ".sqlite": "Data",
    ".db": "Data",
    ".exe": "Apps",
    ".msi": "Apps",
    ".dmg": "Apps",
    ".pkg": "Apps",
    ".deb": "Apps",
    ".rpm": "Apps",
    ".appimage": "Apps",
}


def classify_file(extension: str, filename: str) -> tuple[str, float, str]:
    normalized_extension = extension.lower()
    normalized_name = filename.lower()

    if normalized_extension in AMBIGUOUS_EXTENSIONS:
        return REVIEW_CATEGORY, 0.35, f"Ambiguous extension '{normalized_extension}' routed to Review."

    if normalized_extension in CATEGORY_BY_EXTENSION:
        category = CATEGORY_BY_EXTENSION[normalized_extension]
        return category, 0.92, f"Matched extension '{normalized_extension}' to {category}."

    if any(token in normalized_name for token in ("setup", "installer", "install")):
        return "Apps", 0.7, "Filename suggests an installer or application package."

    if not normalized_extension:
        return REVIEW_CATEGORY, 0.25, "File has no extension, so it was routed to Review."

    return REVIEW_CATEGORY, 0.2, f"Unknown extension '{normalized_extension}' routed to Review."


def destination_for(source: str, category: str) -> str:
    source_path = PurePosixPath(source)
    parts = source_path.parts

    if parts and parts[0] in KNOWN_CATEGORY_DIRECTORIES:
        parts = parts[1:]

    if not parts:
        parts = (source_path.name,)

    return PurePosixPath(category, *parts).as_posix()


def build_plan(inventory: Inventory) -> OrganizationPlan:
    occupied_paths = set(inventory.path_index())
    reserved_destinations: set[str] = set()
    entries: list[PlanEntry] = []
    warnings: list[str] = []

    for file_record in inventory.files:
        category, confidence, reason = classify_file(file_record.extension, file_record.name)
        destination = destination_for(file_record.relative_path, category)
        status = "planned"
        warning: str | None = None

        if destination == file_record.relative_path:
            status = "already_organized"
        elif destination in occupied_paths or destination in reserved_destinations:
            status = "skipped_conflict"
            warning = f"Destination already exists: {destination}"
        else:
            reserved_destinations.add(destination)

        entry = PlanEntry(
            source=file_record.relative_path,
            destination=destination,
            reason=reason,
            confidence=confidence,
            category=category,
            status=status,
            warning=warning,
        )
        entries.append(entry)

        if warning:
            warnings.append(f"{file_record.relative_path}: {warning}")

    return OrganizationPlan(root=inventory.root, entries=entries, warnings=warnings)

