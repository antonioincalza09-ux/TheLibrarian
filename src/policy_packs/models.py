from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.models import OrganizationPlan, utc_now_iso
from src.policies.models import PolicyConfig, PolicyDecisionStatus, PolicyEvaluation


_SAFE_POLICY_PACK_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(slots=True)
class PolicyPackRule:
    name: str
    description: str
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyPackRule":
        return cls(
            name=str(payload["name"]),
            description=str(payload["description"]),
            severity=str(payload.get("severity", "info")),
        )


@dataclass(slots=True)
class PolicyPack:
    pack_id: str
    name: str
    version: str
    description: str
    policy: PolicyConfig
    tags: tuple[str, ...] = ()
    rules: tuple[PolicyPackRule, ...] = ()
    kpi_targets: dict[str, float] = field(default_factory=dict)
    source: str = "builtin"
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        validate_policy_pack_id(self.pack_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "policy": self.policy.to_dict(),
            "tags": list(self.tags),
            "rules": [rule.to_dict() for rule in self.rules],
            "kpi_targets": dict(self.kpi_targets),
            "source": self.source,
            "created_at": self.created_at,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "policy_mode": self.policy.mode.value,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyPack":
        return cls(
            pack_id=str(payload["pack_id"]),
            name=str(payload["name"]),
            version=str(payload["version"]),
            description=str(payload["description"]),
            policy=PolicyConfig.from_dict(dict(payload["policy"])),
            tags=tuple(str(item) for item in payload.get("tags", ())),
            rules=tuple(PolicyPackRule.from_dict(dict(item)) for item in payload.get("rules", ())),
            kpi_targets={str(key): float(value) for key, value in dict(payload.get("kpi_targets", {})).items()},
            source=str(payload.get("source", "local")),
            created_at=str(payload.get("created_at", utc_now_iso())),
        )


@dataclass(slots=True)
class PolicyPackKpi:
    total_entries: int
    planned_entries: int
    review_entries: int
    conflict_entries: int
    auto_approved: int
    requires_approval: int
    blocked: int
    approved_by_user: int

    @property
    def auto_approval_rate(self) -> float:
        return _ratio(self.auto_approved, self.total_entries)

    @property
    def review_rate(self) -> float:
        return _ratio(self.review_entries, self.total_entries)

    @property
    def blocked_rate(self) -> float:
        return _ratio(self.blocked, self.total_entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "planned_entries": self.planned_entries,
            "review_entries": self.review_entries,
            "conflict_entries": self.conflict_entries,
            "auto_approved": self.auto_approved,
            "requires_approval": self.requires_approval,
            "blocked": self.blocked,
            "approved_by_user": self.approved_by_user,
            "auto_approval_rate": round(self.auto_approval_rate, 4),
            "review_rate": round(self.review_rate, 4),
            "blocked_rate": round(self.blocked_rate, 4),
        }

    @classmethod
    def from_plan_and_evaluation(cls, plan: OrganizationPlan, evaluation: PolicyEvaluation) -> "PolicyPackKpi":
        summary = evaluation.summary()
        return cls(
            total_entries=len(plan.entries),
            planned_entries=len(plan.planned_entries),
            review_entries=len(plan.review_entries),
            conflict_entries=len(plan.conflict_entries),
            auto_approved=summary[PolicyDecisionStatus.AUTO_APPROVED.value],
            requires_approval=summary[PolicyDecisionStatus.REQUIRES_APPROVAL.value],
            blocked=summary[PolicyDecisionStatus.BLOCKED.value],
            approved_by_user=summary["approved_by_user"],
        )


def validate_policy_pack_id(pack_id: str) -> str:
    if not pack_id or "/" in pack_id or "\\" in pack_id or ".." in pack_id or not _SAFE_POLICY_PACK_ID.match(pack_id):
        raise ValueError(f"Invalid policy pack id: {pack_id}")
    return pack_id


def _ratio(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total
