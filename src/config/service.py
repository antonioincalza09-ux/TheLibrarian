from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RuntimeConfig:
    provider: str = "deterministic"
    model: str = ""
    endpoint: str = ""
    dry_run: bool = True
    output_directory: str = ".thelibrarian/reports"
    privacy_mode: str = "metadata-only"


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    if "thelibrarian" in payload and isinstance(payload["thelibrarian"], dict):
        return payload["thelibrarian"]
    return payload


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _apply_payload(config: RuntimeConfig, payload: dict[str, Any]) -> RuntimeConfig:
    updates: dict[str, object] = {}
    for field in ("provider", "model", "endpoint", "output_directory", "privacy_mode"):
        if field in payload and payload[field] is not None:
            updates[field] = str(payload[field])
    if "dry_run" in payload and payload["dry_run"] is not None:
        updates["dry_run"] = _coerce_bool(payload["dry_run"])
    return replace(config, **updates)


def load_config(
    *,
    root: str | Path | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> RuntimeConfig:
    config = RuntimeConfig()

    project_config = Path("thelibrarian.toml")
    config = _apply_payload(config, _load_toml(project_config))

    if root is not None:
        root_config = Path(root).expanduser() / ".thelibrarian" / "config.toml"
        config = _apply_payload(config, _load_toml(root_config))

    if config_path is not None:
        config = _apply_payload(config, _load_toml(Path(config_path).expanduser()))

    env_payload = {
        "provider": os.getenv("THELIBRARIAN_PROVIDER"),
        "model": os.getenv("THELIBRARIAN_MODEL"),
        "endpoint": os.getenv("THELIBRARIAN_ENDPOINT"),
        "privacy_mode": os.getenv("THELIBRARIAN_PRIVACY_MODE"),
        "output_directory": os.getenv("THELIBRARIAN_OUTPUT_DIRECTORY"),
        "dry_run": os.getenv("THELIBRARIAN_DRY_RUN"),
    }
    config = _apply_payload(config, {key: value for key, value in env_payload.items() if value is not None})

    if overrides:
        config = _apply_payload(config, overrides)

    if config.privacy_mode != "metadata-only":
        raise ValueError("Only metadata-only privacy mode is supported in this version.")

    return config
