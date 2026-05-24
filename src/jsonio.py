from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models import Inventory, OrganizationPlan


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def read_inventory(path: str | Path) -> Inventory:
    return Inventory.from_dict(read_json(path))


def write_inventory(path: str | Path, inventory: Inventory) -> Path:
    return write_json(path, inventory.to_dict())


def read_plan(path: str | Path) -> OrganizationPlan:
    return OrganizationPlan.from_dict(read_json(path))


def write_plan(path: str | Path, plan: OrganizationPlan) -> Path:
    return write_json(path, plan.to_dict())
