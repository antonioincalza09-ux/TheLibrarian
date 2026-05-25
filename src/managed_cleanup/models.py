from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from src.models import utc_now_iso


_SAFE_CLEANUP_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class CleanupStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class CleanupSession:
    session_id: str
    root: str
    created_at: str
    updated_at: str
    status: CleanupStatus
    dry_run: bool
    provider: str
    policy_pack_id: str
    service_mode: str = "local_stub"
    artifacts: dict[str, str] = field(default_factory=dict)
    kpis: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def create(
        cls,
        *,
        root: str,
        provider: str = "deterministic",
        policy_pack_id: str = "local_safe_review",
        dry_run: bool = True,
    ) -> "CleanupSession":
        now = utc_now_iso()
        return cls(
            session_id=uuid4().hex,
            root=root,
            created_at=now,
            updated_at=now,
            status=CleanupStatus.CREATED,
            dry_run=dry_run,
            provider=provider,
            policy_pack_id=policy_pack_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "root": self.root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "dry_run": self.dry_run,
            "provider": self.provider,
            "policy_pack_id": self.policy_pack_id,
            "service_mode": self.service_mode,
            "artifacts": dict(self.artifacts),
            "kpis": dict(self.kpis),
            "warnings": list(self.warnings),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CleanupSession":
        return cls(
            session_id=str(payload["session_id"]),
            root=str(payload["root"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            status=CleanupStatus(str(payload["status"])),
            dry_run=bool(payload.get("dry_run", True)),
            provider=str(payload.get("provider", "deterministic")),
            policy_pack_id=str(payload.get("policy_pack_id", "local_safe_review")),
            service_mode=str(payload.get("service_mode", "local_stub")),
            artifacts={str(key): str(value) for key, value in dict(payload.get("artifacts", {})).items()},
            kpis=dict(payload.get("kpis", {})),
            warnings=[str(item) for item in payload.get("warnings", [])],
            error=None if payload.get("error") is None else str(payload["error"]),
        )


def validate_cleanup_session_id(session_id: str) -> str:
    if not session_id or "/" in session_id or "\\" in session_id or ".." in session_id or not _SAFE_CLEANUP_ID.match(session_id):
        raise ValueError(f"Invalid cleanup session id: {session_id}")
    return session_id
