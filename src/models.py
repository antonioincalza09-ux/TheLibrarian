from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_CATEGORY_DIRECTORIES = (
    "Documents",
    "Media",
    "Code",
    "Archives",
    "Data",
    "Apps",
    "Review",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class FileRecord:
    relative_path: str
    name: str
    size_bytes: int
    modified_at: str
    extension: str
    parent: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Inventory:
    root: str
    files: list[FileRecord]
    warnings: list[str] = field(default_factory=list)
    scanned_at: str = field(default_factory=utc_now_iso)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files)

    def path_index(self) -> dict[str, FileRecord]:
        return {item.relative_path: item for item in self.files}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "scanned_at": self.scanned_at,
            "warnings": list(self.warnings),
            "summary": {
                "total_files": self.total_files,
                "total_bytes": self.total_bytes,
            },
            "files": [item.to_dict() for item in self.files],
        }


@dataclass(slots=True)
class PlanEntry:
    source: str
    destination: str
    reason: str
    confidence: float
    category: str
    status: str = "planned"
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence"] = round(self.confidence, 2)
        return payload


@dataclass(slots=True)
class OrganizationPlan:
    root: str
    entries: list[PlanEntry]
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now_iso)

    @property
    def planned_entries(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.status == "planned"]

    @property
    def already_organized_entries(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.status == "already_organized"]

    @property
    def conflict_entries(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.status == "skipped_conflict"]

    @property
    def review_entries(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.category == "Review"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "generated_at": self.generated_at,
            "warnings": list(self.warnings),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(slots=True)
class ManifestOperation:
    source: str
    destination: str
    reason: str
    confidence: float
    rollback_source: str
    rollback_destination: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "rollback": {
                "source": self.rollback_source,
                "destination": self.rollback_destination,
            },
        }


@dataclass(slots=True)
class ExecutionResult:
    root: str
    dry_run: bool
    applied_operations: list[ManifestOperation]
    skipped_entries: list[PlanEntry]
    warnings: list[str] = field(default_factory=list)
    manifest_path: str | None = None
    executed_at: str = field(default_factory=utc_now_iso)

    @property
    def applied_count(self) -> int:
        return len(self.applied_operations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dry_run": self.dry_run,
            "executed_at": self.executed_at,
            "manifest_path": self.manifest_path,
            "warnings": list(self.warnings),
            "applied_operations": [operation.to_dict() for operation in self.applied_operations],
            "skipped_entries": [entry.to_dict() for entry in self.skipped_entries],
        }


@dataclass(slots=True)
class OrganizerRun:
    inventory: Inventory
    plan: OrganizationPlan
    execution: ExecutionResult
    report: str

