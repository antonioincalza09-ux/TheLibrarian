from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.models import OrganizationPlan, utc_now_iso
from src.policies.models import PolicyConfig, PolicyDecisionStatus, PolicyEvaluation, PolicyMode


_SAFE_POLICY_PACK_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(slots=True)
class NamingConvention:
    name: str
    pattern: str
    example: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NamingConvention":
        return cls(name=str(payload["name"]), pattern=str(payload["pattern"]), example=str(payload["example"]))


@dataclass(slots=True)
class KPIProfile:
    review_threshold_percent: int
    target_automation_percent: int
    risk_tolerance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KPIProfile":
        return cls(
            review_threshold_percent=int(payload["review_threshold_percent"]),
            target_automation_percent=int(payload["target_automation_percent"]),
            risk_tolerance=str(payload["risk_tolerance"]),
        )


@dataclass(slots=True)
class ManagedServiceRecommendation:
    id: str
    title: str
    description: str
    suggested_frequency: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManagedServiceRecommendation":
        return cls(
            id=str(payload["id"]),
            title=str(payload["title"]),
            description=str(payload["description"]),
            suggested_frequency=str(payload["suggested_frequency"]),
        )


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
    id: str
    name: str
    version: str
    industry: str = ""
    description: str = ""
    tier: str = "free"
    recommended_policy: str = "dry_run_only"
    use_cases: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    folder_templates: list[str] = field(default_factory=list)
    naming_conventions: list[NamingConvention] = field(default_factory=list)
    sensitive_directories: list[str] = field(default_factory=list)
    high_risk_categories: list[str] = field(default_factory=list)
    kpi_profile: KPIProfile | None = None
    managed_service_recommendations: list[ManagedServiceRecommendation] = field(default_factory=list)
    policy: PolicyConfig | None = None
    tags: tuple[str, ...] = ()
    rules: tuple[PolicyPackRule, ...] = ()
    kpi_targets: dict[str, float] = field(default_factory=dict)
    source: str = "builtin"
    created_at: str = field(default_factory=utc_now_iso)

    @property
    def pack_id(self) -> str:
        return self.id

    def __post_init__(self) -> None:
        validate_policy_pack_id(self.id)
        if self.policy is None:
            self.policy = _policy_from_recommended_policy(self.recommended_policy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pack_id": self.id,
            "name": self.name,
            "version": self.version,
            "industry": self.industry,
            "description": self.description,
            "tier": self.tier,
            "recommended_policy": self.recommended_policy,
            "use_cases": list(self.use_cases),
            "categories": list(self.categories),
            "folder_templates": list(self.folder_templates),
            "naming_conventions": [item.to_dict() for item in self.naming_conventions],
            "sensitive_directories": list(self.sensitive_directories),
            "high_risk_categories": list(self.high_risk_categories),
            "kpi_profile": self.kpi_profile.to_dict() if self.kpi_profile else None,
            "managed_service_recommendations": [
                item.to_dict() for item in self.managed_service_recommendations
            ],
            "policy": self.policy.to_dict() if self.policy else None,
            "tags": list(self.tags),
            "rules": [rule.to_dict() for rule in self.rules],
            "kpi_targets": dict(self.kpi_targets),
            "source": self.source,
            "created_at": self.created_at,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "pack_id": self.id,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "industry": self.industry,
            "tier": self.tier,
            "source": self.source,
            "policy_mode": self.policy.mode.value if self.policy else self.recommended_policy,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyPack":
        pack_id = str(payload.get("id", payload.get("pack_id", "")))
        recommended_policy = str(
            payload.get(
                "recommended_policy",
                dict(payload.get("policy", {})).get("mode", PolicyMode.DRY_RUN_ONLY.value),
            )
        )
        policy_payload = payload.get("policy")
        return cls(
            id=pack_id,
            name=str(payload["name"]),
            version=str(payload["version"]),
            industry=str(payload.get("industry", "")),
            description=str(payload.get("description", "")),
            tier=str(payload.get("tier", "free")),
            recommended_policy=recommended_policy,
            use_cases=[str(item) for item in payload.get("use_cases", [])],
            categories=[str(item) for item in payload.get("categories", [])],
            folder_templates=[str(item) for item in payload.get("folder_templates", [])],
            naming_conventions=[
                NamingConvention.from_dict(item)
                for item in payload.get("naming_conventions", [])
                if isinstance(item, dict)
            ],
            sensitive_directories=[str(item) for item in payload.get("sensitive_directories", [])],
            high_risk_categories=[str(item) for item in payload.get("high_risk_categories", [])],
            kpi_profile=(
                KPIProfile.from_dict(payload["kpi_profile"])
                if isinstance(payload.get("kpi_profile"), dict)
                else None
            ),
            managed_service_recommendations=[
                ManagedServiceRecommendation.from_dict(item)
                for item in payload.get("managed_service_recommendations", [])
                if isinstance(item, dict)
            ],
            policy=PolicyConfig.from_dict(dict(policy_payload)) if isinstance(policy_payload, dict) else None,
            tags=tuple(str(item) for item in payload.get("tags", ())),
            rules=tuple(PolicyPackRule.from_dict(dict(item)) for item in payload.get("rules", ())),
            kpi_targets={str(key): float(value) for key, value in dict(payload.get("kpi_targets", {})).items()},
            source=str(payload.get("source", "builtin")),
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


def _policy_from_recommended_policy(recommended_policy: str) -> PolicyConfig:
    mode = PolicyMode(recommended_policy)
    return PolicyConfig(mode=mode, name=mode.value)


def _ratio(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total
