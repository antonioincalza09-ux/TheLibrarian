from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from src.models import utc_now_iso


class JobStatus(StrEnum):
    CREATED = "created"
    SCANNING = "scanning"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPLYING = "applying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    ROLLED_BACK = "rolled_back"


class JobPhase(StrEnum):
    CREATED = "created"
    SCANNING = "scanning"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPLYING = "applying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class JobConfig:
    root: str
    dry_run: bool = True
    provider: str = "deterministic"
    model: str = ""
    endpoint: str = ""
    policy_name: str | None = None
    privacy_mode: str = "metadata-only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dry_run": self.dry_run,
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.endpoint,
            "policy_name": self.policy_name,
            "privacy_mode": self.privacy_mode,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobConfig":
        return cls(
            root=str(payload["root"]),
            dry_run=bool(payload.get("dry_run", True)),
            provider=str(payload.get("provider", "deterministic")),
            model=str(payload.get("model", "")),
            endpoint=str(payload.get("endpoint", "")),
            policy_name=None if payload.get("policy_name") is None else str(payload["policy_name"]),
            privacy_mode=str(payload.get("privacy_mode", "metadata-only")),
        )


@dataclass(slots=True)
class JobEvent:
    timestamp: str
    status: JobStatus
    phase: JobPhase
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "status": self.status.value,
            "phase": self.phase.value,
            "message": self.message,
            "data": self.data,
        }

    @classmethod
    def create(
        cls,
        *,
        status: JobStatus,
        phase: JobPhase,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> "JobEvent":
        return cls(
            timestamp=utc_now_iso(),
            status=status,
            phase=phase,
            message=message,
            data=data or {},
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobEvent":
        return cls(
            timestamp=str(payload["timestamp"]),
            status=JobStatus(str(payload["status"])),
            phase=JobPhase(str(payload["phase"])),
            message=str(payload["message"]),
            data=dict(payload.get("data", {})),
        )


@dataclass(slots=True)
class JobRecord:
    job_id: str
    root: str
    created_at: str
    updated_at: str
    status: JobStatus
    phase: JobPhase
    dry_run: bool
    provider: str
    policy_name: str | None = None
    inventory_path: str | None = None
    plan_path: str | None = None
    policy_path: str | None = None
    manifest_path: str | None = None
    report_path: str | None = None
    verification_path: str | None = None
    error: str | None = None
    counters: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "root": self.root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "phase": self.phase.value,
            "dry_run": self.dry_run,
            "provider": self.provider,
            "policy_name": self.policy_name,
            "inventory_path": self.inventory_path,
            "plan_path": self.plan_path,
            "policy_path": self.policy_path,
            "manifest_path": self.manifest_path,
            "report_path": self.report_path,
            "verification_path": self.verification_path,
            "error": self.error,
            "counters": dict(self.counters),
        }

    @classmethod
    def create(cls, *, root: str, dry_run: bool = True, provider: str = "deterministic", policy_name: str | None = None) -> "JobRecord":
        now = utc_now_iso()
        return cls(
            job_id=uuid4().hex,
            root=root,
            created_at=now,
            updated_at=now,
            status=JobStatus.CREATED,
            phase=JobPhase.CREATED,
            dry_run=dry_run,
            provider=provider,
            policy_name=policy_name,
            counters={
                "scanned": 0,
                "planned": 0,
                "applied": 0,
                "skipped": 0,
                "verified": 0,
            },
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=str(payload["job_id"]),
            root=str(payload["root"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            status=JobStatus(str(payload["status"])),
            phase=JobPhase(str(payload["phase"])),
            dry_run=bool(payload.get("dry_run", True)),
            provider=str(payload.get("provider", "deterministic")),
            policy_name=None if payload.get("policy_name") is None else str(payload["policy_name"]),
            inventory_path=None if payload.get("inventory_path") is None else str(payload["inventory_path"]),
            plan_path=None if payload.get("plan_path") is None else str(payload["plan_path"]),
            policy_path=None if payload.get("policy_path") is None else str(payload["policy_path"]),
            manifest_path=None if payload.get("manifest_path") is None else str(payload["manifest_path"]),
            report_path=None if payload.get("report_path") is None else str(payload["report_path"]),
            verification_path=None if payload.get("verification_path") is None else str(payload["verification_path"]),
            error=None if payload.get("error") is None else str(payload["error"]),
            counters={str(key): int(value) for key, value in dict(payload.get("counters", {})).items()},
        )
