from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.models import utc_now_iso


class PolicyMode(StrEnum):
    DRY_RUN_ONLY = "dry_run_only"
    SUPERVISED_AUTONOMY = "supervised_autonomy"


class PolicyDecisionStatus(StrEnum):
    AUTO_APPROVED = "auto_approved"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"


@dataclass(slots=True)
class PolicyConfig:
    mode: PolicyMode = PolicyMode.DRY_RUN_ONLY
    name: str = "dry_run_only"
    auto_apply_categories: tuple[str, ...] = ("Documents", "Media", "Data")
    minimum_confidence: float = 0.92

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "name": self.name,
            "auto_apply_categories": list(self.auto_apply_categories),
            "minimum_confidence": self.minimum_confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyConfig":
        return cls(
            mode=PolicyMode(str(payload.get("mode", PolicyMode.DRY_RUN_ONLY.value))),
            name=str(payload.get("name", payload.get("mode", PolicyMode.DRY_RUN_ONLY.value))),
            auto_apply_categories=tuple(str(item) for item in payload.get("auto_apply_categories", ("Documents", "Media", "Data"))),
            minimum_confidence=float(payload.get("minimum_confidence", 0.92)),
        )


@dataclass(slots=True)
class PolicyDecision:
    source: str
    destination: str
    category: str
    confidence: float
    status: PolicyDecisionStatus
    reason: str
    risk_score: float
    approved_by_user: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "status": self.status.value,
            "reason": self.reason,
            "risk_score": round(self.risk_score, 2),
            "approved_by_user": self.approved_by_user,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyDecision":
        return cls(
            source=str(payload["source"]),
            destination=str(payload["destination"]),
            category=str(payload["category"]),
            confidence=float(payload["confidence"]),
            status=PolicyDecisionStatus(str(payload["status"])),
            reason=str(payload["reason"]),
            risk_score=float(payload["risk_score"]),
            approved_by_user=bool(payload.get("approved_by_user", False)),
        )


@dataclass(slots=True)
class PolicyEvaluation:
    root: str
    policy: PolicyConfig
    decisions: list[PolicyDecision]
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "generated_at": self.generated_at,
            "policy": self.policy.to_dict(),
            "summary": self.summary(),
            "decisions": [decision.to_dict() for decision in self.decisions],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyEvaluation":
        return cls(
            root=str(payload["root"]),
            generated_at=str(payload.get("generated_at", utc_now_iso())),
            policy=PolicyConfig.from_dict(dict(payload["policy"])),
            decisions=[PolicyDecision.from_dict(item) for item in payload.get("decisions", [])],
        )

    def summary(self) -> dict[str, int]:
        counts = {
            PolicyDecisionStatus.AUTO_APPROVED.value: 0,
            PolicyDecisionStatus.REQUIRES_APPROVAL.value: 0,
            PolicyDecisionStatus.BLOCKED.value: 0,
            "approved_by_user": 0,
        }
        for decision in self.decisions:
            counts[decision.status.value] += 1
            if decision.approved_by_user:
                counts["approved_by_user"] += 1
        return counts

