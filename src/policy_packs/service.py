from __future__ import annotations

from pathlib import Path

from src.models import OrganizationPlan
from src.policies.models import PolicyEvaluation
from src.policy_packs.loader import write_local_policy_pack
from src.policy_packs.models import PolicyPack, PolicyPackKpi
from src.policy_packs.registry import PolicyPackRegistry


def list_policy_packs(root: str | Path | None = None) -> list[PolicyPack]:
    return PolicyPackRegistry(root).list()


def get_policy_pack(pack_id: str, root: str | Path | None = None) -> PolicyPack:
    return PolicyPackRegistry(root).get(pack_id)


def export_policy_pack(pack_id: str, root: str | Path) -> Path:
    pack = get_policy_pack(pack_id, root)
    return write_local_policy_pack(root, pack)


def policy_pack_kpis(plan: OrganizationPlan, evaluation: PolicyEvaluation) -> PolicyPackKpi:
    return PolicyPackKpi.from_plan_and_evaluation(plan, evaluation)
