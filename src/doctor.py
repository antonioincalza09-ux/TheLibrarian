from __future__ import annotations

import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.config import RuntimeConfig
from src.providers import ProviderContext, available_providers
from src.providers.diagnostics import DiagnosticCheck, diagnose_provider
from src.security import SafetyError, resolve_root


def build_doctor_report(root: str | Path | None, config: RuntimeConfig) -> dict[str, Any]:
    checks: list[DiagnosticCheck] = []
    checks.extend(_installation_checks())
    checks.extend(_config_checks(config))

    if root is not None:
        checks.extend(_root_checks(root))
    else:
        checks.append(DiagnosticCheck("root", "warning", "No root was provided, so root permissions were not checked."))

    context = ProviderContext(model=config.model, endpoint=config.endpoint, privacy_mode=config.privacy_mode)
    checks.extend(diagnose_provider(config.provider, context, required=True))

    if config.provider != "ollama":
        optional_context = ProviderContext(privacy_mode=config.privacy_mode)
        checks.extend(_prefixed("optional_ollama", diagnose_provider("ollama", optional_context, required=False)))
    if config.provider != "openai-compatible":
        optional_context = ProviderContext(privacy_mode=config.privacy_mode)
        checks.extend(_prefixed("optional_openai", diagnose_provider("openai-compatible", optional_context, required=False)))

    return {
        "status": _overall_status(checks),
        "python": sys.version.split()[0],
        "config": asdict(config),
        "root": None if root is None else str(Path(root).expanduser()),
        "checks": [check.to_dict() for check in checks],
    }


def _installation_checks() -> list[DiagnosticCheck]:
    checks = [
        DiagnosticCheck("python", "ok", f"Python {sys.version.split()[0]} is running."),
        DiagnosticCheck("module_import", "ok", "src.cli is importable."),
    ]
    command_path = shutil.which("thelibrarian")
    if command_path:
        checks.append(DiagnosticCheck("console_script", "ok", f"thelibrarian resolves to {command_path}."))
    else:
        checks.append(
            DiagnosticCheck(
                "console_script",
                "warning",
                "thelibrarian is not on PATH; use python -m src.cli or install with pip install -e .",
            )
        )
    return checks


def _config_checks(config: RuntimeConfig) -> list[DiagnosticCheck]:
    checks: list[DiagnosticCheck] = []
    if config.provider in available_providers():
        checks.append(DiagnosticCheck("config_provider", "ok", f"provider={config.provider}"))
    else:
        checks.append(DiagnosticCheck("config_provider", "error", f"unknown provider={config.provider}"))

    if config.privacy_mode == "metadata-only":
        checks.append(DiagnosticCheck("privacy_mode", "ok", "metadata-only"))
    else:
        checks.append(DiagnosticCheck("privacy_mode", "error", "only metadata-only privacy mode is supported."))

    if config.dry_run:
        checks.append(DiagnosticCheck("dry_run", "ok", "dry-run is enabled by default."))
    else:
        checks.append(DiagnosticCheck("dry_run", "warning", "dry-run is disabled in runtime config."))
    return checks


def _root_checks(root: str | Path) -> list[DiagnosticCheck]:
    try:
        resolved_root = resolve_root(root)
    except SafetyError as exc:
        return [DiagnosticCheck("root", "error", str(exc))]

    checks = [DiagnosticCheck("root", "ok", str(resolved_root))]
    if os.access(resolved_root, os.R_OK | os.X_OK):
        checks.append(DiagnosticCheck("root_readable", "ok", "root can be scanned."))
    else:
        checks.append(DiagnosticCheck("root_readable", "error", "root is not readable/searchable."))

    if os.access(resolved_root, os.W_OK):
        checks.append(DiagnosticCheck("root_writable", "ok", "root can hold .thelibrarian artifacts and approved moves."))
    else:
        checks.append(DiagnosticCheck("root_writable", "error", "root is not writable."))
    return checks


def _prefixed(prefix: str, checks: list[DiagnosticCheck]) -> list[DiagnosticCheck]:
    return [DiagnosticCheck(f"{prefix}_{check.name}", check.status, check.detail) for check in checks]


def _overall_status(checks: list[DiagnosticCheck]) -> str:
    if any(check.status == "error" for check in checks):
        return "error"
    if any(check.status == "warning" for check in checks):
        return "warning"
    return "ok"
