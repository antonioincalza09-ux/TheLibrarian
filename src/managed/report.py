from __future__ import annotations

from src.managed.models import ManagedCleanupReport, ManagedCleanupSession
from src.policy_packs.models import PolicyPack


def build_managed_report(session: ManagedCleanupSession, pack: PolicyPack) -> ManagedCleanupReport:
    kpi = session.kpi
    recommendations = list(session.recommendations)
    summary = (
        f"Analyzed {kpi.files_scanned} file(s), planned {kpi.planned_moves} safe move(s), "
        f"and identified {kpi.manual_review_moves} item(s) needing review."
    )
    return ManagedCleanupReport(
        session_id=session.session_id,
        summary=summary,
        kpi=kpi,
        recommendations=recommendations,
        artifacts=dict(session.artifacts),
    )


def render_managed_report_markdown(session: ManagedCleanupSession, report: ManagedCleanupReport, pack: PolicyPack) -> str:
    kpi = report.kpi
    recommendation_lines = "\n".join(
        f"- {recommendation.title}: {recommendation.description}"
        for recommendation in report.recommendations
    ) or "- No recommendations generated."
    artifact_lines = "\n".join(f"- {name}: `{path}`" for name, path in sorted(report.artifacts.items())) or "- No artifacts."
    next_step = "Review the generated plan with the client before applying any move."
    if kpi.manual_review_moves == 0 and kpi.blocked_moves == 0 and kpi.planned_moves > 0:
        next_step = "Review the plan summary, then use the existing apply workflow with explicit confirmation."

    return f"""# TheLibrarian Managed Cleanup Report

## Client

- Client: {session.client_name}
- Operator: {session.operator_name}
- Root: `{session.root}`
- Session: `{session.session_id}`

## Executive Summary

{report.summary}

## KPI

- Files scanned: {kpi.files_scanned}
- Total bytes scanned: {kpi.total_bytes_scanned}
- Planned moves: {kpi.planned_moves}
- Auto-approved moves: {kpi.auto_approved_moves}
- Manual review moves: {kpi.manual_review_moves}
- Blocked moves: {kpi.blocked_moves}
- Review category count: {kpi.review_category_count}
- Conflict count: {kpi.conflict_count}
- Already organized count: {kpi.already_organized_count}
- Applied moves: {kpi.applied_moves}
- Verified moves: {kpi.verified_moves}
- Rollback available: {kpi.rollback_available}
- Safety score: {kpi.safety_score}/100
- Organization score: {kpi.organization_score}/100
- Automation score: {kpi.automation_score}/100
- Risk score: {kpi.risk_score}/100
- Estimated minutes saved: {kpi.estimated_minutes_saved}

## Recommended Actions

{recommendation_lines}

## Safety Notes

- This managed workflow is dry-run only.
- No file contents were modified.
- No file contents were sent to providers.
- Apply still requires the existing explicit confirmation and rollback manifest workflow.

## Policy Pack

- Pack: {pack.name} (`{pack.id}`)
- Industry: {pack.industry}
- Tier: {pack.tier}
- Recommended policy: {pack.recommended_policy}

## Artifacts

{artifact_lines}

## Next Steps

{next_step}
"""
