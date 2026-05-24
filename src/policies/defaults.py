from __future__ import annotations

from src.policies.models import PolicyConfig, PolicyMode


def default_policy(policy_name: str | None = None) -> PolicyConfig:
    if policy_name in (None, "", PolicyMode.DRY_RUN_ONLY.value):
        return PolicyConfig(mode=PolicyMode.DRY_RUN_ONLY, name=PolicyMode.DRY_RUN_ONLY.value)
    if policy_name == PolicyMode.SUPERVISED_AUTONOMY.value:
        return PolicyConfig(mode=PolicyMode.SUPERVISED_AUTONOMY, name=PolicyMode.SUPERVISED_AUTONOMY.value)
    raise ValueError(f"Unknown policy: {policy_name}")

