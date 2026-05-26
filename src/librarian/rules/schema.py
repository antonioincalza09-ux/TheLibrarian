from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]
NodeType = Literal["file", "directory"]
FileKind = Literal[
    "source_code",
    "document",
    "image",
    "audio",
    "video",
    "archive",
    "config",
    "data",
    "unknown",
]


class Classification(BaseModel):
    domain: str = "General"
    category: str = "Unsorted"
    confidence: float = 0.0
    reason: str = ""


class Relation(BaseModel):
    type: str
    target: str
    confidence: float = 0.0
    reason: str = ""


class SymbolDocstrings(BaseModel):
    module: str | None = None
    functions: dict[str, str] = Field(default_factory=dict)
    classes: dict[str, str] = Field(default_factory=dict)


class SymbolLocation(BaseModel):
    name: str
    line_start: int | None = None
    line_end: int | None = None


class CodeMetadata(BaseModel):
    language: str | None = None
    module_name: str | None = None
    package_name: str | None = None
    imports: dict[str, list[str]] = Field(
        default_factory=lambda: {"internal": [], "external": [], "standard_library": []}
    )
    symbols: dict[str, list[dict[str, Any]]] = Field(
        default_factory=lambda: {"functions": [], "classes": [], "methods": []}
    )
    docstrings: SymbolDocstrings = Field(default_factory=SymbolDocstrings)
    entrypoints: list[str] = Field(default_factory=list)
    framework_hints: list[str] = Field(default_factory=list)
    test_hints: list[str] = Field(default_factory=list)
    config_hints: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    generated_file: bool = False
    vendor_file: bool = False
    lock_file: bool = False
    should_modify: bool = False
    should_move: bool = False
    reason: str = ""


class DirectoryAnalysis(BaseModel):
    direct_file_count: int = 0
    direct_subdirectory_count: int = 0
    total_file_count: int = 0
    dominant_extensions: list[str] = Field(default_factory=list)
    dominant_languages: list[str] = Field(default_factory=list)
    recurring_name_tokens: list[str] = Field(default_factory=list)
    possible_roles: list[str] = Field(default_factory=list)
    theme: str = "General"
    should_reorganize: bool = False
    should_modify: bool = False
    reason: str = ""


class WorkspaceNode(BaseModel):
    librarian_id: str
    type: NodeType
    original_path: str
    current_path: str
    proposed_path: str | None = None
    name: str
    extension: str | None = None
    size_bytes: int | None = None
    created_at: str | None = None
    modified_at: str | None = None
    indexed_at: str
    mime_type: str | None = None
    content_hash: str | None = None
    name_hash: str | None = None
    readable: bool = True
    read_error: str | None = None
    file_kind: FileKind = "unknown"
    detected_language: str | None = None
    title: str = ""
    summary: str = ""
    human_description: str = ""
    developer_notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "people": [],
            "organizations": [],
            "places": [],
            "dates": [],
        }
    )
    classification: Classification = Field(default_factory=Classification)
    code_metadata: CodeMetadata | None = None
    directory_analysis: DirectoryAnalysis | None = None
    relations: list[Relation] = Field(default_factory=list)
    status: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    depth: int = 0
    parent_path: str | None = None
    generated_file: bool = False
    vendor_file: bool = False
    lock_file: bool = False
    should_modify: bool = False
    should_move: bool = False
    risk_level: RiskLevel = "low"


class ScanResult(BaseModel):
    workspace_root: str
    generated_at: str
    files: list[WorkspaceNode] = Field(default_factory=list)
    directories: list[WorkspaceNode] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ManifestCounts(BaseModel):
    files: int = 0
    directories: int = 0
    marked_files: int = 0
    marked_directories: int = 0
    unreadable_files: int = 0
    missing_sidecars: int = 0
    orphan_sidecars: int = 0
    applied_operations: int = 0


class Manifest(BaseModel):
    workspace_root: str
    generated_at: str
    librarian_version: str
    files: list[WorkspaceNode] = Field(default_factory=list)
    directories: list[WorkspaceNode] = Field(default_factory=list)
    counts: ManifestCounts = Field(default_factory=ManifestCounts)
    detected_languages: list[str] = Field(default_factory=list)
    detected_domains: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PlanMove(BaseModel):
    source: str
    destination: str
    node_type: NodeType = "file"
    reason: str
    confidence: float = 0.0
    safe_to_move: bool = False
    logical_only: bool = False
    collision: bool = False
    status: str = "planned"


class WorkspacePlan(BaseModel):
    workspace_root: str
    generated_at: str
    entries: list[PlanMove] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class OperationLog(BaseModel):
    timestamp: str
    action: Literal["move", "rollback"]
    source: str
    destination: str
    status: Literal["applied", "skipped", "rolled_back", "warning"]
    message: str = ""
