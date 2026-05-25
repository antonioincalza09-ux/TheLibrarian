from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from src.config import load_config
from src.doctor import build_doctor_report
from src.executor import execute_plan, rollback_manifest
from src.jobs import JobRunner, JobStore
from src.jsonio import read_plan, write_inventory, write_plan
from src.managed import load_managed_session, list_managed_sessions, regenerate_managed_report, start_managed_cleanup
from src.managed_cleanup import get_cleanup_session, list_cleanup_sessions, run_cleanup_preview
from src.managed_cleanup.store import CleanupStore
from src.orchestrator import organize_directory
from src.policy_packs import (
    export_policy_pack,
    export_policy_pack_to_root,
    get_policy_pack,
    list_policy_packs,
    recommend_policy_packs,
    validate_policy_pack,
)
from src.policy_packs.loader import load_policy_pack
from src.planner import build_plan
from src.providers import ProviderContext, available_providers, get_provider
from src.providers.diagnostics import diagnose_provider
from src.reporter import render_plan_report, write_report
from src.scanner import scan_directory
from src.security import SafetyError, resolve_root
from src.webapp import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thelibrarian",
        description="Privacy-first file organization copilot for professionals and small businesses.",
    )
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
    doctor.add_argument("--format", choices=("text", "json"), default="text")

    packs = subcommands.add_parser("packs", help="List, inspect, export, and validate policy packs.")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)
    packs_list = packs_sub.add_parser("list", help="List installed policy packs.")
    packs_list.add_argument("--format", choices=("text", "json"), default="text")
    packs_show = packs_sub.add_parser("show", help="Show a policy pack.")
    packs_show.add_argument("pack_id")
    packs_show.add_argument("--format", choices=("text", "json"), default="text")
    packs_export = packs_sub.add_parser("export", help="Export a policy pack JSON file.")
    packs_export.add_argument("pack_id")
    packs_export.add_argument("--output", required=True)
    packs_validate = packs_sub.add_parser("validate", help="Validate a policy pack JSON file.")
    packs_validate.add_argument("path")
    packs_validate.add_argument("--format", choices=("text", "json"), default="text")
    packs_recommend = packs_sub.add_parser("recommend", help="Recommend policy packs by industry.")
    packs_recommend.add_argument("--industry", required=True)
    packs_recommend.add_argument("--format", choices=("text", "json"), default="text")

    managed = subcommands.add_parser("managed", help="Run managed cleanup dry-run sessions and reports.")
    managed_sub = managed.add_subparsers(dest="managed_command", required=True)
    managed_start = managed_sub.add_parser("start", help="Create a managed cleanup session and dry-run job.")
    managed_start.add_argument("root")
    managed_start.add_argument("--client", required=True)
    managed_start.add_argument("--operator", required=True)
    managed_start.add_argument("--pack", required=True)
    managed_start.add_argument("--provider", choices=available_providers())
    managed_start.add_argument("--model")
    managed_start.add_argument("--endpoint")
    managed_start.add_argument("--format", choices=("text", "json"), default="text")
    managed_report = managed_sub.add_parser("report", help="Regenerate a managed cleanup report.")
    managed_report.add_argument("session_id")
    managed_report.add_argument("--root", required=True)
    managed_report.add_argument("--format", choices=("text", "json"), default="text")
    managed_list = managed_sub.add_parser("list", help="List managed cleanup sessions.")
    managed_list.add_argument("root")
    managed_list.add_argument("--format", choices=("text", "json"), default="text")
    managed_show = managed_sub.add_parser("show", help="Show a managed cleanup session.")
    managed_show.add_argument("session_id")
    managed_show.add_argument("--root", required=True)
    managed_show.add_argument("--format", choices=("text", "json"), default="text")

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
    job_create.add_argument("--policy", choices=("dry_run_only", "supervised_autonomy"))
    job_create.add_argument("--pack")
    job_create.add_argument("--policy-pack")
    job_create.add_argument("--format", choices=("text", "json"), default="text")

    job_run = job_sub.add_parser("run", help="Create and run a dry-run checkpointed job.")
    job_run.add_argument("root")
    job_run.add_argument("--provider", choices=available_providers())
    job_run.add_argument("--model")
    job_run.add_argument("--endpoint")
    job_run.add_argument("--policy", choices=("dry_run_only", "supervised_autonomy"))
    job_run.add_argument("--pack")
    job_run.add_argument("--policy-pack")
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

    job_approve = job_sub.add_parser("approve", help="Manually approve policy decisions for one job.")
    job_approve.add_argument("job_id")
    job_approve.add_argument("--root", required=True)
    job_approve.add_argument("--confirm", action="store_true")
    job_approve.add_argument("--format", choices=("text", "json"), default="text")

    job_apply = job_sub.add_parser("apply", help="Apply policy-approved entries for one job.")
    job_apply.add_argument("job_id")
    job_apply.add_argument("--root", required=True)
    job_apply.add_argument("--confirm", action="store_true")
    job_apply.add_argument("--format", choices=("text", "json"), default="text")

    job_rollback = job_sub.add_parser("rollback", help="Rollback the manifest produced by one job.")
    job_rollback.add_argument("job_id")
    job_rollback.add_argument("--root", required=True)
    job_rollback.add_argument("--confirm", action="store_true")
    job_rollback.add_argument("--format", choices=("text", "json"), default="text")

    doctor_command = subcommands.add_parser("doctor", help="Check installation, root, config, and provider readiness.")
    doctor_command.add_argument("root", nargs="?")
    doctor_command.add_argument("--provider", choices=available_providers())
    doctor_command.add_argument("--model")
    doctor_command.add_argument("--endpoint")
    doctor_command.add_argument("--format", choices=("text", "json"), default="text")

    policy_packs = subcommands.add_parser("policy-packs", help="Inspect local policy pack templates.")
    policy_pack_sub = policy_packs.add_subparsers(dest="policy_pack_command", required=True)
    policy_pack_list = policy_pack_sub.add_parser("list", help="List built-in and local policy packs.")
    policy_pack_list.add_argument("--root")
    policy_pack_list.add_argument("--format", choices=("text", "json"), default="text")
    policy_pack_show = policy_pack_sub.add_parser("show", help="Show one policy pack.")
    policy_pack_show.add_argument("pack_id")
    policy_pack_show.add_argument("--root")
    policy_pack_show.add_argument("--format", choices=("text", "json"), default="text")
    policy_pack_export = policy_pack_sub.add_parser("export", help="Export a policy pack under .thelibrarian/policy-packs/.")
    policy_pack_export.add_argument("pack_id")
    policy_pack_export.add_argument("root")
    policy_pack_export.add_argument("--format", choices=("text", "json"), default="text")

    cleanup = subcommands.add_parser("cleanup", help="Run local managed cleanup preview sessions.")
    cleanup_sub = cleanup.add_subparsers(dest="cleanup_command", required=True)
    cleanup_preview = cleanup_sub.add_parser("preview", help="Create a dry-run managed cleanup session.")
    cleanup_preview.add_argument("root")
    cleanup_preview.add_argument("--provider", choices=available_providers())
    cleanup_preview.add_argument("--model")
    cleanup_preview.add_argument("--endpoint")
    cleanup_preview.add_argument("--policy-pack", default="local_safe_review")
    cleanup_preview.add_argument("--format", choices=("text", "json"), default="text")
    cleanup_list = cleanup_sub.add_parser("list", help="List managed cleanup sessions for a root.")
    cleanup_list.add_argument("root")
    cleanup_list.add_argument("--format", choices=("text", "json"), default="text")
    cleanup_status = cleanup_sub.add_parser("status", help="Show one managed cleanup session.")
    cleanup_status.add_argument("session_id")
    cleanup_status.add_argument("--root", required=True)
    cleanup_status.add_argument("--format", choices=("text", "json"), default="text")
    cleanup_report = cleanup_sub.add_parser("report", help="Print one managed cleanup report.")
    cleanup_report.add_argument("session_id")
    cleanup_report.add_argument("--root", required=True)

    return parser


def _config_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "provider": getattr(args, "provider", None),
        "model": getattr(args, "model", None),
        "endpoint": getattr(args, "endpoint", None),
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _overall_status(checks: list[dict[str, str]]) -> str:
    if any(check["status"] == "error" for check in checks):
        return "error"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    return "ok"


def _print_doctor_text(payload: dict[str, Any]) -> None:
    print(f"Status: {payload['status']}")
    for check in payload["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")


def _doctor_exit_code(payload: dict[str, Any]) -> int:
    return 2 if payload["status"] == "error" else 0


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


def _print_pack_rows(packs: list[Any]) -> None:
    for pack in packs:
        print(f"{pack.id:<24} {pack.industry:<16} {pack.tier:<14} {pack.name}")


def _handle_packs(args: argparse.Namespace) -> int:
    if args.packs_command == "list":
        packs = list_policy_packs()
        if args.format == "json":
            _print_json({"packs": [pack.to_dict() for pack in packs]})
        else:
            _print_pack_rows(packs)
        return 0

    if args.packs_command == "show":
        pack = get_policy_pack(args.pack_id)
        if args.format == "json":
            _print_json(pack.to_dict())
        else:
            _print_pack_rows([pack])
            print(pack.description)
            print("Folder templates:")
            for template in pack.folder_templates:
                print(f"- {template}")
        return 0

    if args.packs_command == "export":
        path = export_policy_pack(args.pack_id, args.output)
        print(str(path))
        return 0

    if args.packs_command == "validate":
        pack = load_policy_pack(args.path)
        errors = validate_policy_pack(pack)
        payload = {"valid": not errors, "pack_id": pack.id, "errors": errors}
        if args.format == "json":
            _print_json(payload)
        else:
            print("valid" if not errors else "invalid")
            for error in errors:
                print(f"- {error}")
        return 0 if not errors else 2

    if args.packs_command == "recommend":
        packs = recommend_policy_packs(args.industry)
        if args.format == "json":
            _print_json({"industry": args.industry, "packs": [pack.to_dict() for pack in packs]})
        else:
            _print_pack_rows(packs)
        return 0

    raise ValueError(f"Unknown packs command: {args.packs_command}")


def _print_managed_session(session) -> None:
    print(f"Session: {session.session_id}")
    print(f"Root: {session.root}")
    print(f"Client: {session.client_name}")
    print(f"Operator: {session.operator_name}")
    print(f"Pack: {session.pack_id}")
    print(f"Job: {session.job_id}")
    print(f"Stage: {session.stage.value}")
    print(f"Files scanned: {session.kpi.files_scanned}")
    print(f"Planned moves: {session.kpi.planned_moves}")
    print(f"Safety score: {session.kpi.safety_score}")
    print(f"Report: {session.artifacts.get('report_md', '(not written)')}")


def _handle_managed(args: argparse.Namespace) -> int:
    if args.managed_command == "start":
        config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
        session = start_managed_cleanup(
            args.root,
            client_name=args.client,
            operator_name=args.operator,
            pack_id=args.pack,
            config=config,
        )
        if args.format == "json":
            _print_json(session.to_dict())
        else:
            _print_managed_session(session)
        return 0

    if args.managed_command == "report":
        session = regenerate_managed_report(args.root, args.session_id)
        if args.format == "json":
            _print_json(session.to_dict())
        else:
            _print_managed_session(session)
        return 0

    if args.managed_command == "list":
        sessions = list_managed_sessions(args.root)
        if args.format == "json":
            _print_json({"sessions": [session.to_dict() for session in sessions]})
        else:
            for session in sessions:
                print(f"{session.session_id}\t{session.stage.value}\t{session.pack_id}\t{session.updated_at}\t{session.client_name}")
        return 0

    if args.managed_command == "show":
        session = load_managed_session(args.root, args.session_id)
        if args.format == "json":
            _print_json(session.to_dict())
        else:
            _print_managed_session(session)
        return 0

    raise ValueError(f"Unknown managed command: {args.managed_command}")


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
    context = ProviderContext(model=config.model, endpoint=config.endpoint, privacy_mode=config.privacy_mode)
    checks = [check.to_dict() for check in diagnose_provider(config.provider, context, required=True)]
    payload = {
        "status": _overall_status(checks),
        "provider": config.provider,
        "model": config.model,
        "endpoint": config.endpoint,
        "privacy_mode": config.privacy_mode,
        "checks": checks,
    }
    if args.format == "json":
        _print_json(payload)
    else:
        _print_doctor_text(payload)
    return _doctor_exit_code(payload)


def _handle_serve(args: argparse.Namespace) -> int:
    config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
    serve(args.root, host=args.host, port=args.port, config=config)
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
    payload = build_doctor_report(args.root, config)
    if args.format == "json":
        _print_json(payload)
    else:
        _print_doctor_text(payload)
    return _doctor_exit_code(payload)


def _print_job(job) -> None:
    print(f"Job: {job.job_id}")
    print(f"Root: {job.root}")
    print(f"Status: {job.status.value}")
    print(f"Phase: {job.phase.value}")
    if job.pack_id:
        print(f"Pack: {job.pack_id}")
    print(f"Updated: {job.updated_at}")
    if job.inventory_path:
        print(f"Inventory: {job.inventory_path}")
    if job.plan_path:
        print(f"Plan: {job.plan_path}")
    if job.policy_path:
        print(f"Policy: {job.policy_path}")
    if job.report_path:
        print(f"Report: {job.report_path}")
    if job.manifest_path:
        print(f"Manifest: {job.manifest_path}")
    if job.error:
        print(f"Error: {job.error}")


def _print_policy_pack(pack) -> None:
    print(f"Policy Pack: {pack.pack_id}")
    print(f"Name: {pack.name}")
    print(f"Version: {pack.version}")
    print(f"Source: {pack.source}")
    print(f"Policy: {pack.policy.name}")
    print(f"Mode: {pack.policy.mode.value}")
    print(f"Description: {pack.description}")
    if pack.tags:
        print(f"Tags: {', '.join(pack.tags)}")


def _print_cleanup_session(session) -> None:
    print(f"Cleanup: {session.session_id}")
    print(f"Root: {session.root}")
    print(f"Status: {session.status.value}")
    print(f"Dry run: {session.dry_run}")
    print(f"Provider: {session.provider}")
    print(f"Policy pack: {session.policy_pack_id}")
    print(f"Service mode: {session.service_mode}")
    for name, path in session.artifacts.items():
        print(f"{name}: {path}")
    if session.kpis:
        print(f"Files scanned: {session.kpis.get('files_scanned', 0)}")
        print(f"Planned moves: {session.kpis.get('planned_entries', 0)}")
        print(f"Requires approval: {session.kpis.get('requires_approval', 0)}")
        print(f"Auto approved: {session.kpis.get('auto_approved', 0)}")
        print(f"Blocked: {session.kpis.get('blocked', 0)}")
    if session.error:
        print(f"Error: {session.error}")


def _handle_policy_packs(args: argparse.Namespace) -> int:
    if args.policy_pack_command == "list":
        packs = list_policy_packs(args.root)
        if args.format == "json":
            _print_json({"policy_packs": [pack.summary() for pack in packs]})
        else:
            for pack in packs:
                print(f"{pack.pack_id}\t{pack.version}\t{pack.source}\t{pack.policy.mode.value}\t{pack.name}")
        return 0

    if args.policy_pack_command == "show":
        pack = get_policy_pack(args.pack_id, args.root)
        if args.format == "json":
            _print_json(pack.to_dict())
        else:
            _print_policy_pack(pack)
        return 0

    if args.policy_pack_command == "export":
        path = export_policy_pack_to_root(get_policy_pack(args.pack_id, args.root), args.root)
        payload = {"pack_id": args.pack_id, "path": str(path)}
        if args.format == "json":
            _print_json(payload)
        else:
            print(f"Exported policy pack: {path}")
        return 0

    raise ValueError(f"Unknown policy-packs command: {args.policy_pack_command}")


def _handle_cleanup(args: argparse.Namespace) -> int:
    if args.cleanup_command == "preview":
        config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
        session = run_cleanup_preview(args.root, config=config, policy_pack_id=args.policy_pack)
        if args.format == "json":
            _print_json(session.to_dict())
        else:
            _print_cleanup_session(session)
        return 0

    if args.cleanup_command == "list":
        sessions = list_cleanup_sessions(args.root)
        if args.format == "json":
            _print_json({"cleanups": [session.to_dict() for session in sessions]})
        else:
            for session in sessions:
                print(f"{session.session_id}\t{session.status.value}\t{session.policy_pack_id}\t{session.updated_at}")
        return 0

    if args.cleanup_command == "status":
        session = get_cleanup_session(args.root, args.session_id)
        if args.format == "json":
            _print_json(session.to_dict())
        else:
            _print_cleanup_session(session)
        return 0

    if args.cleanup_command == "report":
        report_path = CleanupStore(args.root).artifact_path(args.session_id, "report.txt")
        print(report_path.read_text(encoding="utf-8"))
        return 0

    raise ValueError(f"Unknown cleanup command: {args.cleanup_command}")


def _handle_job(args: argparse.Namespace) -> int:
    if args.job_command in {"create", "run"}:
        config = load_config(root=args.root, config_path=args.config, overrides=_config_overrides(args))
        runner = JobRunner(args.root, config=config)
        pack_id = _resolve_job_pack_id(args)
        if args.job_command == "create":
            job = runner.create_job(dry_run=True, policy_name=args.policy, pack_id=pack_id)
        else:
            job = runner.run(dry_run=True, policy_name=args.policy, pack_id=pack_id)

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

    if args.job_command == "approve":
        _require_confirm(args.confirm, "Job approval")
        job = JobRunner(args.root).approve(args.job_id)
        if args.format == "json":
            _print_json(job.to_dict())
        else:
            _print_job(job)
        return 0

    if args.job_command == "apply":
        _require_confirm(args.confirm, "Job apply")
        job = JobRunner(args.root).apply(args.job_id)
        if args.format == "json":
            _print_json(job.to_dict())
        else:
            _print_job(job)
        return 0

    if args.job_command == "rollback":
        _require_confirm(args.confirm, "Job rollback")
        job = JobRunner(args.root).rollback(args.job_id)
        if args.format == "json":
            _print_json(job.to_dict())
        else:
            _print_job(job)
        return 0

    raise ValueError(f"Unknown job command: {args.job_command}")


def _resolve_job_pack_id(args: argparse.Namespace) -> str | None:
    legacy_pack = getattr(args, "pack", None)
    policy_pack = getattr(args, "policy_pack", None)
    if legacy_pack and policy_pack and legacy_pack != policy_pack:
        raise ValueError("--pack and --policy-pack refer to different packs.")
    return policy_pack or legacy_pack


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
        "packs": _handle_packs,
        "managed": _handle_managed,
        "serve": _handle_serve,
        "job": _handle_job,
        "doctor": _handle_doctor,
        "policy-packs": _handle_policy_packs,
        "cleanup": _handle_cleanup,
    }
    try:
        return handlers[args.command](args)
    except (SafetyError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
