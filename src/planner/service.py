from __future__ import annotations

from pathlib import PurePosixPath

from src.models import DEFAULT_CATEGORY_DIRECTORIES, FileRecord, Inventory, OrganizationPlan, PlanEntry
from src.providers.types import ClassificationProvider, ClassificationResult, ProviderContext, ProviderError


AMBIGUOUS_EXTENSIONS = {".json", ".xml", ".yml", ".yaml"}
KNOWN_CATEGORY_DIRECTORIES = set(DEFAULT_CATEGORY_DIRECTORIES)
REVIEW_CATEGORY = "Review"
SKILLS_CONTEXT_DIRECTORY = "Skills"
SKILL_DEFINITION_NAMES = {"skill.md", "heartbeat.md"}
SKILL_METADATA_NAMES = {"_meta.json", "origin.json", "manifest.json"}
SKILL_CONTEXT_MARKERS = {".clawhub", "references", "scripts", "tests", "test", "assets", "templates"}
BROAD_OR_CONTEXT_DIRECTORIES = KNOWN_CATEGORY_DIRECTORIES | {SKILLS_CONTEXT_DIRECTORY}
DOCUMENT_CONTEXT_DIRECTORIES = {
    "Agents",
    "Financial",
    "General",
    "Knowledge",
    "Manuals",
    "Notes",
    "Presentations",
    "Protocols",
    "Reports",
    "Testing",
    "Text",
    "Workflows",
}
DOCUMENT_CONTEXT_KEYWORDS = (
    ("Testing", ("test", "testing", "qa", "accessibility", "benchmark", "performance", "evidence", "reality-check")),
    ("Financial", ("finance", "financial", "invoice", "receipt", "budget", "tax", "bank", "statement")),
    ("Agents", ("agent", "orchestrator", "assistant")),
    ("Workflows", ("workflow", "sequence", "sequencer", "pipeline", "process", "procedure", "operation")),
    ("Knowledge", ("knowledge", "graph", "ontology", "registry", "mapping", "index")),
    ("Protocols", ("protocol", "policy", "rules", "runbook")),
    ("Manuals", ("manual", "guide", "how-to", "handbook", "readme")),
    ("Reports", ("report", "summary", "analysis", "audit", "review")),
    ("Notes", ("note", "notes", "memo", "meeting", "journal")),
)

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

    if category == "Documents":
        return document_destination_for(source)

    if parts and parts[0] in KNOWN_CATEGORY_DIRECTORIES:
        parts = parts[1:]

    if not parts:
        parts = (source_path.name,)

    return PurePosixPath(category, *parts).as_posix()


def document_destination_for(source: str) -> str:
    source_path = PurePosixPath(source)
    parts = source_path.parts

    if parts and parts[0] == "Documents":
        stripped_parts = parts[1:]
        if stripped_parts and stripped_parts[0] in DOCUMENT_CONTEXT_DIRECTORIES:
            return source_path.as_posix()
        parts = stripped_parts
    elif parts and parts[0] in KNOWN_CATEGORY_DIRECTORIES:
        parts = parts[1:]

    if not parts:
        parts = (source_path.name,)

    context = _document_context_for(parts, source_path.suffix.lower())
    return PurePosixPath("Documents", context, *parts).as_posix()


def _document_context_for(parts: tuple[str, ...], extension: str) -> str:
    searchable = " ".join(part.lower().replace("_", "-") for part in parts)

    for context, keywords in DOCUMENT_CONTEXT_KEYWORDS:
        if any(keyword in searchable for keyword in keywords):
            return context

    if extension in {".ppt", ".pptx"}:
        return "Presentations"
    if extension in {".txt", ".rtf"}:
        return "Text"
    if extension in {".md"}:
        return "Notes"
    return "General"


def contextual_destination_for(
    file_record: FileRecord,
    category: str,
    *,
    skill_workspace: bool = False,
    skill_names: set[str] | None = None,
) -> tuple[str, str | None]:
    source_path = PurePosixPath(file_record.relative_path)
    parts = source_path.parts

    if parts and parts[0] == SKILLS_CONTEXT_DIRECTORY:
        return file_record.relative_path, "File is already inside the contextual Skills workspace."

    context_parts = parts[1:] if parts and parts[0] in BROAD_OR_CONTEXT_DIRECTORIES else parts
    known_skill_names = skill_names or set()
    if not _looks_like_skill_context(
        context_parts,
        file_record,
        skill_workspace=skill_workspace,
        skill_names=known_skill_names,
    ):
        return destination_for(file_record.relative_path, category), None

    skill_name, remainder = _skill_name_and_remainder(context_parts, file_record)
    function_directory = _skill_function_directory(remainder, file_record, category)
    destination_name = _contextual_destination_name(remainder, file_record)
    destination = PurePosixPath(SKILLS_CONTEXT_DIRECTORY, skill_name, function_directory, destination_name).as_posix()
    reason = f"Contextual skill workspace grouping under {SKILLS_CONTEXT_DIRECTORY}/{skill_name}/{function_directory}."
    return destination, reason


def _looks_like_skill_context(
    parts: tuple[str, ...],
    file_record: FileRecord,
    *,
    skill_workspace: bool,
    skill_names: set[str],
) -> bool:
    normalized_name = file_record.name.lower()
    lowered_parts = {part.lower() for part in parts}

    if parts and parts[0] in skill_names:
        return True
    if normalized_name in SKILL_DEFINITION_NAMES or normalized_name in SKILL_METADATA_NAMES:
        return True
    if any(part in SKILL_CONTEXT_MARKERS for part in lowered_parts):
        return True
    if len(parts) >= 2 and any(part in {"references", "scripts", "tests", "test"} for part in lowered_parts):
        return True
    if skill_workspace and len(parts) == 1 and file_record.extension.lower() == ".md":
        return True
    return False


def _inventory_looks_like_skill_workspace(inventory: Inventory) -> bool:
    root_name = PurePosixPath(str(inventory.root).replace("\\", "/")).name.lower()
    if root_name in {"skills", "skill"}:
        return True
    return any(
        file_record.name.lower() in SKILL_DEFINITION_NAMES
        or ".clawhub" in PurePosixPath(file_record.relative_path).parts
        for file_record in inventory.files
    )


def _skill_context_names(inventory: Inventory) -> set[str]:
    names: set[str] = set()

    for file_record in inventory.files:
        parts = PurePosixPath(file_record.relative_path).parts
        context_parts = parts[1:] if parts and parts[0] in BROAD_OR_CONTEXT_DIRECTORIES else parts
        if len(context_parts) >= 2 and file_record.name.lower() in SKILL_DEFINITION_NAMES:
            names.add(context_parts[-2])
        if ".clawhub" in context_parts:
            marker_index = context_parts.index(".clawhub")
            if marker_index > 0:
                names.add(context_parts[marker_index - 1])

    return names


def _skill_name_and_remainder(parts: tuple[str, ...], file_record: FileRecord) -> tuple[str, tuple[str, ...]]:
    normalized_name = file_record.name.lower()
    if len(parts) == 1:
        return PurePosixPath(file_record.name).stem, (file_record.name,)
    if parts and parts[0].lower() in {"manuals", "docs", "documentation"}:
        return parts[0], parts[1:] or (file_record.name,)
    if normalized_name in SKILL_DEFINITION_NAMES and len(parts) >= 2:
        return parts[-2], (file_record.name,)
    return parts[0], parts[1:] or (file_record.name,)


def _skill_function_directory(parts: tuple[str, ...], file_record: FileRecord, category: str) -> str:
    lowered_parts = [part.lower() for part in parts]
    normalized_name = file_record.name.lower()
    extension = file_record.extension.lower()

    if normalized_name in SKILL_DEFINITION_NAMES:
        return "Definition"
    if normalized_name in SKILL_METADATA_NAMES or ".clawhub" in lowered_parts:
        return "Metadata"
    if any(part in {"scripts", "src", "source"} for part in lowered_parts) or category == "Code":
        return "Source"
    if any(part in {"tests", "test"} for part in lowered_parts):
        return "Tests"
    if any(part in {"references", "reference", "manuals", "docs", "documentation"} for part in lowered_parts):
        return "References"
    if any(part in {"assets", "images", "media", "templates"} for part in lowered_parts) or category == "Media":
        return "Assets"
    if extension in {".json", ".toml", ".yml", ".yaml", ".ini", ".cfg"}:
        return "Config"
    return "Documentation" if extension == ".md" else "Artifacts"


def _contextual_destination_name(parts: tuple[str, ...], file_record: FileRecord) -> str:
    lowered_parts = [part.lower() for part in parts]

    for marker in ("scripts", "src", "source", "references", "reference", "tests", "test", "assets", "images", "media", "templates"):
        if marker in lowered_parts:
            marker_index = lowered_parts.index(marker)
            tail = parts[marker_index + 1 :]
            if tail:
                return PurePosixPath(*tail).as_posix()

    if ".clawhub" in lowered_parts:
        marker_index = lowered_parts.index(".clawhub")
        tail = parts[marker_index + 1 :]
        if tail:
            return PurePosixPath(*tail).as_posix()

    return file_record.name


def _valid_provider_result(result: ClassificationResult, known_sources: set[str]) -> bool:
    return (
        result.source in known_sources
        and result.category in KNOWN_CATEGORY_DIRECTORIES
        and 0 <= result.confidence <= 1
        and bool(result.reason.strip())
    )


def _classification_index(
    inventory: Inventory,
    provider: ClassificationProvider | None,
    context: ProviderContext | None,
) -> tuple[dict[str, ClassificationResult], list[str], str]:
    active_provider = provider
    provider_name = active_provider.name if active_provider else "deterministic"
    known_sources = set(inventory.path_index())
    warnings: list[str] = []
    deterministic_results = {
        file_record.relative_path: ClassificationResult(
            source=file_record.relative_path,
            category=classify_file(file_record.extension, file_record.name)[0],
            confidence=classify_file(file_record.extension, file_record.name)[1],
            reason=classify_file(file_record.extension, file_record.name)[2],
        )
        for file_record in inventory.files
    }

    if active_provider is None:
        return deterministic_results, warnings, provider_name

    try:
        results = active_provider.classify(inventory, context or ProviderContext())
    except (ProviderError, ValueError, KeyError, TypeError) as exc:
        warnings.append(f"Provider '{provider_name}' failed; deterministic fallback used. {exc}")
        return deterministic_results, warnings, "deterministic"

    index: dict[str, ClassificationResult] = {}

    for result in results:
        if _valid_provider_result(result, known_sources):
            index[result.source] = result
        else:
            warnings.append(f"Invalid provider classification for '{result.source}' routed to deterministic fallback.")

    for source in known_sources:
        index.setdefault(source, deterministic_results[source])

    return index, warnings, provider_name


def build_plan(
    inventory: Inventory,
    provider: ClassificationProvider | None = None,
    context: ProviderContext | None = None,
) -> OrganizationPlan:
    occupied_paths = set(inventory.path_index())
    reserved_destinations: set[str] = set()
    entries: list[PlanEntry] = []
    classification_index, provider_warnings, provider_name = _classification_index(inventory, provider, context)
    skill_workspace = _inventory_looks_like_skill_workspace(inventory)
    skill_names = _skill_context_names(inventory)
    warnings: list[str] = list(provider_warnings)

    for file_record in inventory.files:
        classification = classification_index[file_record.relative_path]
        category = classification.category
        confidence = classification.confidence
        reason = classification.reason
        destination, context_reason = contextual_destination_for(
            file_record,
            category,
            skill_workspace=skill_workspace,
            skill_names=skill_names,
        )
        if context_reason:
            reason = f"{reason} {context_reason}"
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

    return OrganizationPlan(root=inventory.root, entries=entries, warnings=warnings, provider=provider_name)
