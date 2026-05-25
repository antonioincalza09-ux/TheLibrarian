from __future__ import annotations

from pathlib import Path

from src.policy_packs.builtin import builtin_policy_packs
from src.policy_packs.loader import load_local_policy_packs
from src.policy_packs.models import PolicyPack


class PolicyPackRegistry:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = root

    def list(self) -> list[PolicyPack]:
        packs_by_id: dict[str, PolicyPack] = {}
        for pack in builtin_policy_packs():
            packs_by_id[pack.pack_id] = pack
        for pack in load_local_policy_packs(self.root):
            packs_by_id[pack.pack_id] = pack
        return sorted(packs_by_id.values(), key=lambda pack: pack.pack_id)

    def get(self, pack_id: str) -> PolicyPack:
        for pack in self.list():
            if pack.pack_id == pack_id:
                return pack
        raise ValueError(f"Unknown policy pack: {pack_id}")
