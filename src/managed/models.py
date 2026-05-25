from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from src.models import utc_now_iso


class ManagedCleanupStage(StrEnum):
    CREATED = "created"
    DIAGNOSING = "diagnosing"
    INVENTORY = "inventory"
    PLANNING = "planning"
    POLICY_REVIEW = "policy_review"
    CLIENT_APPROVAL = "client_approval"
    APPLY_READY = "apply_ready"
    APPLIED = "applied"
    VERIFIED = "verified"
    ROLLBACK_AVAILABLE = "rollback_available"
    COMPLETED = "completed"


@dataclass(slots=True)
class ManagedCleanupRecommendation:
    id: str
    title: str
    description: str
    priority: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManagedCleanupRecommendation":
        return cls(
            id=str(payload["id"]),
            title=str(payload["title"]),
            description=str(payload["description"]),
            priority=str(payload.get("priority", "normal")),
        )


@dataclass(slots=True)
class ManagedCleanupKPI:
    files_scanned: int = 0
    total_bytes_scanned: int = 0
    planned_moves: int = 0
    auto_approved_moves: int = 0
    manual_review_moves: int = 0
    blocked_moves: int = 0
    review_category_count: int = 0
    conflict_count: int = 0
    already_organized_count: int = 0
    applied_moves: int = 0
    verified_moves: int = 0
    rollback_available: bool = False
    safety_score: int = 100
    organization_score: int = 0
    automation_score: int = 0
    risk_score: int = 0
    estimated_minutes_saved: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManagedCleanupKPI":
        return cls(
            files_scanned=int(payload.get("files_scanned", 0)),
            total_bytes_scanned=int(payload.get("total_bytes_scanned", 0)),
            planned_moves=int(payload.get("planned_moves", 0)),
            auto_approved_moves=int(payload.get("auto_approved_moves", 0)),
            manual_review_moves=int(payload.get("manual_review_moves", 0)),
            blocked_moves=int(payload.get("blocked_moves", 0)),
            review_category_count=int(payload.get("review_category_count", 0)),
            conflict_count=int(payload.get("conflict_count", 0)),
            already_organized_count=int(payload.get("already_organized_count", 0)),
            applied_moves=int(payload.get("applied_moves", 0)),
            verified_moves=int(payload.get("verified_moves", 0)),
            rollback_available=bool(payload.get("rollback_available", False)),
            safety_score=int(payload.get("safety_score", 100)),
            organization_score=int(payload.get("organization_score", 0)),
            automation_score=int(payload.get("automation_score", 0)),
            risk_score=int(payload.get("risk_score", 0)),
            estimated_minutes_saved=float(payload.get("estimated_minutes_saved", 0.0)),
        )


@dataclass(slots=True)
class ManagedCleanupReport:
    session_id: str
    summary: str
    kpi: ManagedCleanupKPI
    recommendations: list[ManagedCleanupRecommendation]
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "kpi": self.kpi.to_dict(),
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
            "artifacts": dict(self.artifacts),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManagedCleanupReport":
        return cls(
            session_id=str(payload["session_id"]),
            summary=str(payload.get("summary", "")),
            kpi=ManagedCleanupKPI.from_dict(dict(payload.get("kpi", {}))),
            recommendations=[
                ManagedCleanupRecommendation.from_dict(item)
                for item in payload.get("recommendations", [])
                if isinstance(item, dict)
            ],
            artifacts={str(key): str(value) for key, value in dict(payload.get("artifacts", {})).items()},
        )


@dataclass(slots=True)
class ManagedCleanupSession:
    session_id: str
    root: str
    created_at: str
    updated_at: str
    client_name: str
    operator_name: str
    pack_id: str
    job_id: str
    stage: ManagedCleanupStage
    summary: str
    kpi: ManagedCleanupKPI
    recommendations: list[ManagedCleanupRecommendation]
    artifacts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        root: str,
        client_name: str,
        operator_name: str,
        pack_id: str,
        job_id: str,
    ) -> "ManagedCleanupSession":
        now = utc_now_iso()
        return cls(
            session_id=uuid4().hex,
            root=root,
            created_at=now,
            updated_at=now,
            client_name=client_name,
            operator_name=operator_name,
            pack_id=pack_id,
            job_id=job_id,
            stage=ManagedCleanupStage.CREATED,
            summary="Managed cleanup session created.",
            kpi=ManagedCleanupKPI(),
            recommendations=[],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "root": self.root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "client_name": self.client_name,
            "operator_name": self.operator_name,
            "pack_id": self.pack_id,
            "job_id": self.job_id,
            "stage": self.stage.value,
            "summary": self.summary,
            "kpi": self.kpi.to_dict(),
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
            "artifacts": dict(self.artifacts),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManagedCleanupSession":
        return cls(
            session_id=str(payload["session_id"]),
            root=str(payload["root"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            client_name=str(payload.get("client_name", "")),
            operator_name=str(payload.get("operator_name", "")),
            pack_id=str(payload.get("pack_id", "")),
            job_id=str(payload.get("job_id", "")),
            stage=ManagedCleanupStage(str(payload.get("stage", ManagedCleanupStage.CREATED.value))),
            summary=str(payload.get("summary", "")),
            kpi=ManagedCleanupKPI.from_dict(dict(payload.get("kpi", {}))),
            recommendations=[
                ManagedCleanupRecommendation.from_dict(item)
                for item in payload.get("recommendations", [])
                if isinstance(item, dict)
            ],
            artifacts={str(key): str(value) for key, value in dict(payload.get("artifacts", {})).items()},
        )
