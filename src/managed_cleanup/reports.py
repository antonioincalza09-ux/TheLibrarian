from __future__ import annotations

from src.managed_cleanup.models import CleanupSession
from src.policy_packs.models import PolicyPack


def render_cleanup_report(session: CleanupSession, policy_pack: PolicyPack) -> str:
    kpis = session.kpis
    lines = [
        f"Managed cleanup session: {session.session_id}",
        f"Root: {session.root}",
        f"Status: {session.status.value}",
        f"Service mode: {session.service_mode}",
        f"Dry run: {session.dry_run}",
        f"Provider: {session.provider}",
        f"Policy pack: {policy_pack.pack_id} ({policy_pack.name} {policy_pack.version})",
        "",
        "KPI:",
        f"- Files scanned: {kpis.get('files_scanned', 0)}",
        f"- Planned moves: {kpis.get('planned_entries', 0)}",
        f"- Review entries: {kpis.get('review_entries', 0)}",
        f"- Conflicts: {kpis.get('conflict_entries', 0)}",
        f"- Auto approved: {kpis.get('auto_approved', 0)}",
        f"- Requires approval: {kpis.get('requires_approval', 0)}",
        f"- Blocked: {kpis.get('blocked', 0)}",
        f"- Auto approval rate: {kpis.get('auto_approval_rate', 0)}",
        f"- Review rate: {kpis.get('review_rate', 0)}",
        f"- Blocked rate: {kpis.get('blocked_rate', 0)}",
    ]
    if session.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in session.warnings)
    lines.append("")
    lines.append("No files were moved. This managed cleanup foundation is local and dry-run only.")
    return "\n".join(lines)
