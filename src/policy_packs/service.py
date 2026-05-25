from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from src.models import OrganizationPlan
from src.policies.models import PolicyEvaluation
from src.policy_packs.loader import write_local_policy_pack
from src.policy_packs.models import PolicyPack, PolicyPackKpi


VALID_TIERS = {"free", "premium_stub", "managed_stub"}
VALID_RECOMMENDED_POLICIES = {"dry_run_only", "supervised_autonomy"}
_PACK_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def validate_policy_pack(pack: PolicyPack) -> list[str]:
    errors: list[str] = []
    if not pack.id:
        errors.append("id is required.")
    elif not _PACK_ID_PATTERN.fullmatch(pack.id):
        errors.append("id must be lowercase snake_case.")
    if not pack.name:
        errors.append("name is required.")
    if not pack.version:
        errors.append("version is required.")
    if pack.industry and pack.tier not in VALID_TIERS:
        errors.append(f"tier must be one of: {', '.join(sorted(VALID_TIERS))}.")
    if pack.industry and pack.recommended_policy not in VALID_RECOMMENDED_POLICIES:
        errors.append("recommended_policy must be dry_run_only or supervised_autonomy.")
    if pack.industry and not pack.categories:
        errors.append("categories must not be empty.")
    if pack.industry and not pack.folder_templates:
        errors.append("folder_templates must not be empty.")
    if pack.industry and not pack.managed_service_recommendations:
        errors.append("managed_service_recommendations must not be empty.")
    if pack.industry and pack.kpi_profile is None:
        errors.append("kpi_profile is required.")

    for template in pack.folder_templates:
        normalized = PurePosixPath(template.replace("\\", "/"))
        if "\\" in template:
            errors.append(f"folder template contains backslash: {template}")
        if normalized.is_absolute():
            errors.append(f"folder template must be relative: {template}")
        if ".." in normalized.parts:
            errors.append(f"folder template must not contain '..': {template}")
    return errors


def validate_policy_pack_registry(packs: list[PolicyPack]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for pack in packs:
        errors.extend(f"{pack.id}: {error}" for error in validate_policy_pack(pack))
        if pack.id in seen:
            errors.append(f"duplicate policy pack id: {pack.id}")
        seen.add(pack.id)
    return errors


def export_policy_pack_to_root(pack: PolicyPack, root: str | Path) -> Path:
    return write_local_policy_pack(root, pack)


def policy_pack_kpis(plan: OrganizationPlan, evaluation: PolicyEvaluation) -> PolicyPackKpi:
    return PolicyPackKpi.from_plan_and_evaluation(plan, evaluation)
