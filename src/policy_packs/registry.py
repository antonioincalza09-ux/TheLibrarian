from __future__ import annotations

import json
from pathlib import Path

from src.policy_packs.builtin import builtin_policy_packs
from src.policy_packs.loader import load_local_policy_packs, load_policy_pack, load_policy_packs_from_directory
from src.policy_packs.models import PolicyPack
from src.policy_packs.service import validate_policy_pack_registry


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def policy_pack_directory() -> Path:
    return _repository_root() / "data" / "policy_packs"


class PolicyPackRegistry:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = root

    def list(self) -> list[PolicyPack]:
        packs_by_id: dict[str, PolicyPack] = {}
        for pack in load_policy_packs_from_directory(policy_pack_directory()):
            packs_by_id[pack.id] = pack
        for pack in builtin_policy_packs():
            packs_by_id.setdefault(pack.pack_id, pack)
        for pack in load_local_policy_packs(self.root):
            packs_by_id[pack.pack_id] = pack
        packs = sorted(packs_by_id.values(), key=lambda pack: pack.pack_id)
        errors = validate_policy_pack_registry(packs)
        if errors:
            raise ValueError("Invalid policy pack registry: " + "; ".join(errors))
        return packs

    def get(self, pack_id: str) -> PolicyPack:
        normalized = pack_id.strip().lower()
        for pack in self.list():
            if pack.pack_id == normalized or pack.id == normalized:
                return pack
        raise ValueError(f"Unknown policy pack: {pack_id}")


def list_policy_packs(root: str | Path | None = None) -> list[PolicyPack]:
    return PolicyPackRegistry(root).list()


def get_policy_pack(pack_id: str, root: str | Path | None = None) -> PolicyPack:
    return PolicyPackRegistry(root).get(pack_id)


def recommend_policy_packs(industry: str) -> list[PolicyPack]:
    normalized = industry.strip().lower()
    return [pack for pack in list_policy_packs() if pack.industry.lower() == normalized]


def export_policy_pack(pack_id: str, output_path: str | Path) -> Path:
    pack = get_policy_pack(pack_id)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(pack.to_dict(), indent=2), encoding="utf-8")
    return destination


def validate_policy_pack_file(path: str | Path) -> list[str]:
    from src.policy_packs.service import validate_policy_pack

    return validate_policy_pack(load_policy_pack(path))
