from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from src.config import load_config
from src.executor import execute_plan, rollback_manifest
from src.jobs import JobRunner, JobStore
from src.jsonio import read_plan, write_inventory, write_plan
from src.orchestrator import organize_directory
from src.planner import build_plan
from src.providers import ProviderContext, available_providers, get_provider
from src.reporter import render_plan_report, write_report
from src.scanner import scan_directory
from src.security import SafetyError, resolve_root
from src.webapp import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thelibrarian", description="Safety-first local file organizer.")
    parser.add_argument("--config", help="Optional TOML config file.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser("scan", help="Scan a root directory and produce an inventory.")
    scan.add_argument("root")
    scan.add_argument("--output")
    scan.add_argument("--format", choices=("text", "json"), default="json")

    plan = subcommands.add_parser("plan", help="Generate an organization plan.")
    plan.add_argument("root")
    plan.add_argument("--provider", choices=available_providers())
    plan.add_argument("--model")
    plan.add_argument("--endpoint")
    plan.add_argument("--output")
    plan.add_argument("--format", choices=("text", "json"), default="json")

    run = subcommands.add_parser("run", help="Scan, plan, and report without moving files by default.")
    run.add_argument("root")
    run.add_argument("--provider", choices=available_providers())
    run.add_argument("--model")
    run.add_argument("--endpoint")
    run.add_argument("--format", choices=("text", "json"), default="text")

    apply = subcommands.add_parser("apply", help="Apply a saved plan with explicit confirmation.")
    apply.add_argument("root")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--confirm", action="store_true")
    apply.add_argument("--format", choices=("text", "json"), default="text")

    rollback = subcommands.add_parser("rollback", help="Rollback an execution manifest with explicit confirmation.")
    rollback.add_argument("root")
    rollback.add_argument("--manifest", required=True)
    rollback.add_argument("--confirm", action="store_true")
    rollback.add_argument("--format", choices=("text", "json"), default="text")

    providers = subcommands.add_parser("providers", help="List or diagnose providers.")
    providers_sub = providers.add_subparsers(dest="providers_command", required=True)
    providers_sub.add_parser("list", help="List available providers.")
    doctor = providers_sub.add_parser("doctor", help="Check provider configuration.")
    doctor.add_argument("--provider", choices=available_providers(), default="deterministic")
    doctor.add_argument("--model")
    doctor.add_argument("--endpoint")

    web = subcommands.add_parser("serve", help="Start the local preview web app.")
    web.add_argument("root")
    web.add_argument("--provider", choices=available_providers())
    web.add_argument("--model")
    web.add_argument("--endpoint")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)

    job = subcommands.add_parser("job", help="Create and inspect checkpointed organization jobs.")
    job_sub = job.add_subparsers(dest="job_command", required=True)

    job_create = job_sub.add_parser("create", help="Create a job record without scanning.")
    job_create.add_argument("root")
    job_create.add_argument("--provider", choices=available_providers())
    job_create.add_argument("--model")
    job_create.add_argument("--endpoint")
    job_create.add_argument("--format", choices=("text", "json"), default="text")

    job_run = job_sub.add_parser("run", help="Create and run a dry-run checkpointed job.")
    job_run.add_argument("root")
    job_run.add_argument("--provider", choices=available_providers())
    job_run.add_argument("--model")
    job_run.add_argument("--endpoint")
    job_run.add_argument("--format", choices=("text", "json"), default="text")

    job_status = job_sub.add_parser("status", help="Show one job record.")
    job_status.add_argument("job_id")
    job_status.add_argument("--root", required=True)
    job_status.add_argument("--format", choices=("text", "json"), default="text")

    job_list = job_sub.add_parser("list", help="List jobs for a root.")
    job_list.add_argument("root")
    job_list.add_argument("--format", choices=("text", "json"), default="text")

    job_events = job_sub.add_parser("events", help="Show append-only events for one job.")
    job_events.add_argument("job_id")
    job_events.add_argument("--root", required=True)
    job_events.add_argument("--format", choices=("text", "json"), default="text")

    return parser


def _config_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "provider": getattr(args, "provider", None),
        "model": getattr(args, "model", None),
        "endpoint": getattr(args, "endpoint", None),
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _require_confirm(confirmed: bool, action: str) -> None:
    if not confirmed:
        raise SafetyError(f"{action} requires --confirm.")


def _plan_for_root(args: argparse.Namespace):
    config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
    inventory = scan_directory(args.root)
    provider = get_provider(config.provider)
    context = ProviderContext(model=config.model, endpoint=config.endpoint, privacy_mode=config.privacy_mode)
    return inventory, build_plan(inventory, provider=provider, context=context)


def _handle_scan(args: argparse.Namespace) -> int:
    inventory = scan_directory(args.root)
    if args.output:
        write_inventory(args.output, inventory)
    if args.format == "json":
        _print_json(inventory.to_dict())
    else:
        print(f"Root: {inventory.root}\nFiles scanned: {inventory.total_files}\nTotal bytes: {inventory.total_bytes}")
    return 0


def _handle_plan(args: argparse.Namespace) -> int:
    inventory, plan = _plan_for_root(args)
    if args.output:
        write_plan(args.output, plan)
    if args.format == "json":
        _print_json(plan.to_dict())
    else:
        print(render_plan_report(inventory, plan))
    return 0


def _handle_run(args: argparse.Namespace) -> int:
    config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
    result = organize_directory(args.root, dry_run=True, config=config)
    report_name = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.txt"
    write_report(args.root, report_name, result.report, output_directory=config.output_directory)
    if args.format == "json":
        _print_json(
            {
                "inventory": result.inventory.to_dict(),
                "plan": result.plan.to_dict(),
                "execution": result.execution.to_dict(),
            }
        )
    else:
        print(result.report)
    return 0


def _handle_apply(args: argparse.Namespace) -> int:
    _require_confirm(args.confirm, "Apply")
    plan = read_plan(args.plan)
    resolved_root = resolve_root(args.root)
    if resolve_root(plan.root) != resolved_root:
        raise SafetyError("Plan root does not match the assigned root.")
    execution = execute_plan(resolved_root, plan, dry_run=False)
    if args.format == "json":
        _print_json(execution.to_dict())
    else:
        print(f"Applied moves: {execution.applied_count}")
        if execution.manifest_path:
            print(f"Manifest: {execution.manifest_path}")
        for warning in execution.warnings:
            print(f"Warning: {warning}")
    return 0


def _handle_rollback(args: argparse.Namespace) -> int:
    _require_confirm(args.confirm, "Rollback")
    execution = rollback_manifest(args.root, args.manifest, confirm=True)
    if args.format == "json":
        _print_json(execution.to_dict())
    else:
        print(f"Rollback moves: {execution.applied_count}")
        for warning in execution.warnings:
            print(f"Warning: {warning}")
    return 0


def _handle_providers(args: argparse.Namespace) -> int:
    if args.providers_command == "list":
        for provider_name in available_providers():
            print(provider_name)
        return 0

    config = load_config(overrides=_config_overrides(args))
    provider = get_provider(config.provider)
    print(f"Provider: {provider.name}")
    print(f"Model: {config.model or '(default)'}")
    print(f"Endpoint: {config.endpoint or '(default)'}")
    print(f"Privacy: {config.privacy_mode}")
    return 0


def _handle_serve(args: argparse.Namespace) -> int:
    config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
    serve(args.root, host=args.host, port=args.port, config=config)
    return 0


def _print_job(job) -> None:
    print(f"Job: {job.job_id}")
    print(f"Root: {job.root}")
    print(f"Status: {job.status.value}")
    print(f"Phase: {job.phase.value}")
    print(f"Updated: {job.updated_at}")
    if job.inventory_path:
        print(f"Inventory: {job.inventory_path}")
    if job.plan_path:
        print(f"Plan: {job.plan_path}")
    if job.report_path:
        print(f"Report: {job.report_path}")
    if job.manifest_path:
        print(f"Manifest: {job.manifest_path}")
    if job.error:
        print(f"Error: {job.error}")


def _handle_job(args: argparse.Namespace) -> int:
    if args.job_command in {"create", "run"}:
        config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
        runner = JobRunner(args.root, config=config)
        if args.job_command == "create":
            job = runner.create_job(dry_run=True)
        else:
            job = runner.run(dry_run=True)

        if args.format == "json":
            _print_json(job.to_dict())
        else:
            _print_job(job)
        return 0

    if args.job_command == "status":
        job = JobStore(args.root).load(args.job_id)
        if args.format == "json":
            _print_json(job.to_dict())
        else:
            _print_job(job)
        return 0

    if args.job_command == "list":
        jobs = JobStore(args.root).list()
        if args.format == "json":
            _print_json({"jobs": [job.to_dict() for job in jobs]})
        else:
            for job in jobs:
                print(f"{job.job_id}\t{job.status.value}\t{job.phase.value}\t{job.updated_at}")
        return 0

    if args.job_command == "events":
        events = JobStore(args.root).read_events(args.job_id)
        if args.format == "json":
            _print_json({"events": [event.to_dict() for event in events]})
        else:
            for event in events:
                print(f"{event.timestamp}\t{event.status.value}\t{event.phase.value}\t{event.message}")
        return 0

    raise ValueError(f"Unknown job command: {args.job_command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "scan": _handle_scan,
        "plan": _handle_plan,
        "run": _handle_run,
        "apply": _handle_apply,
        "rollback": _handle_rollback,
        "providers": _handle_providers,
        "serve": _handle_serve,
        "job": _handle_job,
    }
    try:
        return handlers[args.command](args)
    except (SafetyError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
