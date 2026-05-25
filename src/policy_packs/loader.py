from __future__ import annotations

import json
from pathlib import Path

from src.policy_packs.models import PolicyPack, validate_policy_pack_id
from src.security import SafetyError, resolve_root


POLICY_PACK_DIRECTORY = Path(".thelibrarian") / "policy-packs"


def load_policy_pack(path: str | Path) -> PolicyPack:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Policy pack file must contain a JSON object.")
    return PolicyPack.from_dict(payload)


def load_local_policy_packs(root: str | Path | None = None) -> list[PolicyPack]:
    if root is None:
        return []
    resolved_root = resolve_root(root)
    directory = resolved_root / POLICY_PACK_DIRECTORY
    if not directory.exists():
        return []

    packs: list[PolicyPack] = []
    for path in sorted(directory.glob("*.json")):
        try:
            pack = load_policy_pack(path)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        packs.append(
            PolicyPack(
                pack_id=pack.pack_id,
                name=pack.name,
                version=pack.version,
                description=pack.description,
                policy=pack.policy,
                tags=pack.tags,
                rules=pack.rules,
                kpi_targets=pack.kpi_targets,
                source="local",
                created_at=pack.created_at,
            )
        )
    return packs


def write_local_policy_pack(root: str | Path, pack: PolicyPack) -> Path:
    resolved_root = resolve_root(root)
    pack_id = validate_policy_pack_id(pack.pack_id)
    directory = resolved_root / POLICY_PACK_DIRECTORY
    path = (directory / f"{pack_id}.json").resolve(strict=False)
    try:
        path.relative_to(directory.resolve(strict=False))
    except ValueError as exc:
        raise SafetyError(f"Policy pack path escapes the assigned root: {pack_id}") from exc

    directory.mkdir(parents=True, exist_ok=True)
    payload = pack.to_dict()
    payload["source"] = "local"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
