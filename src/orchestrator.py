from __future__ import annotations

from pathlib import Path

from src.config import RuntimeConfig
from src.executor import execute_plan
from src.models import OrganizerRun
from src.planner import build_plan
from src.providers import ProviderContext, get_provider
from src.reporter import render_plan_report
from src.scanner import scan_directory


def organize_directory(
    root: str | Path,
    *,
    dry_run: bool = True,
    config: RuntimeConfig | None = None,
) -> OrganizerRun:
    runtime_config = config or RuntimeConfig(dry_run=dry_run)
    inventory = scan_directory(root)
    provider = get_provider(runtime_config.provider)
    context = ProviderContext(
        model=runtime_config.model,
        endpoint=runtime_config.endpoint,
        privacy_mode=runtime_config.privacy_mode,
    )
    plan = build_plan(inventory, provider=provider, context=context)
    execution = execute_plan(root, plan, dry_run=dry_run)
    report = render_plan_report(inventory, plan, execution)
    return OrganizerRun(inventory=inventory, plan=plan, execution=execution, report=report)
