from __future__ import annotations

from pathlib import Path

from src.executor import execute_plan
from src.models import OrganizerRun
from src.planner import build_plan
from src.reporter import render_plan_report
from src.scanner import scan_directory


def organize_directory(root: str | Path, *, dry_run: bool = True) -> OrganizerRun:
    inventory = scan_directory(root)
    plan = build_plan(inventory)
    execution = execute_plan(root, plan, dry_run=dry_run)
    report = render_plan_report(inventory, plan, execution)
    return OrganizerRun(inventory=inventory, plan=plan, execution=execution, report=report)

