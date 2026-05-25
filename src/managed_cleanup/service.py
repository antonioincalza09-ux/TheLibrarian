from __future__ import annotations

from pathlib import Path

from src.config import RuntimeConfig
from src.jsonio import write_inventory, write_plan
from src.managed_cleanup.models import CleanupSession, CleanupStatus
from src.managed_cleanup.reports import render_cleanup_report
from src.managed_cleanup.store import CleanupStore
from src.policies import evaluate_policy
from src.planner import build_plan
from src.policy_packs import get_policy_pack, policy_pack_kpis
from src.providers import ProviderContext, get_provider
from src.scanner import scan_directory
from src.security import resolve_root


def run_cleanup_preview(
    root: str | Path,
    *,
    config: RuntimeConfig | None = None,
    policy_pack_id: str = "local_safe_review",
) -> CleanupSession:
    resolved_root = resolve_root(root)
    runtime_config = config or RuntimeConfig()
    store = CleanupStore(resolved_root)
    session = store.create(provider=runtime_config.provider, policy_pack_id=policy_pack_id, dry_run=True)

    try:
        session.status = CleanupStatus.RUNNING
        store.save(session)

        policy_pack = get_policy_pack(policy_pack_id, resolved_root)
        inventory = scan_directory(resolved_root)
        provider = get_provider(runtime_config.provider)
        context = ProviderContext(
            model=runtime_config.model,
            endpoint=runtime_config.endpoint,
            privacy_mode=runtime_config.privacy_mode,
        )
        plan = build_plan(inventory, provider=provider, context=context)
        evaluation = evaluate_policy(resolved_root, inventory, plan, policy_pack.policy)
        kpis = policy_pack_kpis(plan, evaluation).to_dict()
        kpis.update(
            {
                "files_scanned": inventory.total_files,
                "total_bytes": inventory.total_bytes,
                "policy_pack_id": policy_pack.pack_id,
            }
        )

        inventory_path = store.artifact_path(session.session_id, "inventory.json")
        plan_path = store.artifact_path(session.session_id, "plan.json")
        write_inventory(inventory_path, inventory)
        write_plan(plan_path, plan)
        policy_path = store.write_json_artifact(session.session_id, "policy_decision.json", evaluation.to_dict())
        kpi_path = store.write_json_artifact(session.session_id, "kpi.json", kpis)
        pack_path = store.write_json_artifact(session.session_id, "policy_pack.json", policy_pack.to_dict())

        session.status = CleanupStatus.COMPLETED
        session.kpis = kpis
        session.warnings = list(inventory.warnings) + list(plan.warnings)
        session.artifacts = {
            "inventory": str(inventory_path),
            "plan": str(plan_path),
            "policy_decision": str(policy_path),
            "kpi": str(kpi_path),
            "policy_pack": str(pack_path),
        }
        report = render_cleanup_report(session, policy_pack)
        report_path = store.artifact_path(session.session_id, "report.txt")
        report_path.write_text(report, encoding="utf-8")
        session.artifacts["report"] = str(report_path)
        store.save(session)
        return session
    except Exception as exc:
        session.status = CleanupStatus.FAILED
        session.error = str(exc)
        store.save(session)
        raise


def list_cleanup_sessions(root: str | Path) -> list[CleanupSession]:
    return CleanupStore(root).list()


def get_cleanup_session(root: str | Path, session_id: str) -> CleanupSession:
    return CleanupStore(root).load(session_id)
