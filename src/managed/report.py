from __future__ import annotations

from html import escape

from src.managed.models import ManagedCleanupReport, ManagedCleanupSession
from src.policy_packs.models import PolicyPack


def build_managed_report(session: ManagedCleanupSession, pack: PolicyPack) -> ManagedCleanupReport:
    kpi = session.kpi
    recommendations = list(session.recommendations)
    summary = (
        f"TheLibrarian analyzed {kpi.files_scanned} file(s), planned {kpi.planned_moves} reversible move(s), "
        f"and identified {kpi.manual_review_moves} item(s) for human review. "
        f"No files were moved during this managed cleanup session."
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
        f"- **{recommendation.title}** ({recommendation.priority}): {recommendation.description}"
        for recommendation in report.recommendations
    ) or "- No recommendations generated."
    artifact_lines = "\n".join(
        f"| {name} | `{path}` |" for name, path in sorted(report.artifacts.items())
    ) or "| none | No artifacts. |"
    readiness = _readiness_label(kpi)
    risk_posture = _risk_posture(kpi)
    next_step = "Review the generated plan with the client, resolve review items, then decide whether to run a confirmed apply workflow."
    if kpi.manual_review_moves == 0 and kpi.blocked_moves == 0 and kpi.planned_moves > 0:
        next_step = "Review the plan summary with the client, then use the existing apply workflow only with explicit confirmation."

    return f"""# TheLibrarian Managed Cleanup Report

## Service Snapshot

- Client: {session.client_name}
- Operator: {session.operator_name}
- Root: `{session.root}`
- Session: `{session.session_id}`
- Stage: {session.stage.value}
- Policy pack: {pack.name} (`{pack.id}`)
- Industry: {pack.industry or "general"}
- Report posture: dry-run only, no file movement

## Executive Summary

{report.summary}

## Client Outcome

- Readiness: {readiness}
- Risk posture: {risk_posture}
- Estimated time saved: {kpi.estimated_minutes_saved} minute(s)
- Rollback status: {"available after confirmed apply" if not kpi.rollback_available else "available"}

## KPI Snapshot

| Metric | Value |
| --- | ---: |
| Files scanned | {kpi.files_scanned} |
| Total bytes scanned | {kpi.total_bytes_scanned} |
| Planned moves | {kpi.planned_moves} |
| Auto-approved moves | {kpi.auto_approved_moves} |
| Manual review moves | {kpi.manual_review_moves} |
| Blocked moves | {kpi.blocked_moves} |
| Review category count | {kpi.review_category_count} |
| Conflict count | {kpi.conflict_count} |
| Already organized count | {kpi.already_organized_count} |
| Applied moves | {kpi.applied_moves} |
| Verified moves | {kpi.verified_moves} |
| Safety score | {kpi.safety_score}/100 |
| Organization score | {kpi.organization_score}/100 |
| Automation score | {kpi.automation_score}/100 |
| Risk score | {kpi.risk_score}/100 |

## Review And Risk

- Items requiring human review: {kpi.manual_review_moves}
- Blocked items: {kpi.blocked_moves}
- Destination conflicts: {kpi.conflict_count}
- Files routed to Review: {kpi.review_category_count}

Review items are expected in a safety-first workflow. They indicate that TheLibrarian avoided guessing where the confidence or risk profile was not strong enough.

## Recommended Actions

{recommendation_lines}

## Artifact Map

| Artifact | Path |
| --- | --- |
{artifact_lines}

## Safety Appendix

- This managed workflow is dry-run only.
- No files were moved during this report run.
- No file contents were modified.
- No file contents were sent to providers.
- Provider output is treated as untrusted and validated before use.
- Apply still requires the existing explicit confirmation and rollback manifest workflow.
- Rollback artifacts are created only after a confirmed apply.

## Policy Pack

- Pack: {pack.name} (`{pack.id}`)
- Industry: {pack.industry}
- Tier: {pack.tier}
- Recommended policy: {pack.recommended_policy}

## Next Steps

{next_step}
"""


def render_managed_report_html(session: ManagedCleanupSession, report: ManagedCleanupReport, pack: PolicyPack) -> str:
    kpi = report.kpi
    readiness = _readiness_label(kpi)
    risk_posture = _risk_posture(kpi)
    next_step = "Review the generated plan with the client, resolve review items, then decide whether to run a confirmed apply workflow."
    if kpi.manual_review_moves == 0 and kpi.blocked_moves == 0 and kpi.planned_moves > 0:
        next_step = "Review the plan summary with the client, then use the existing apply workflow only with explicit confirmation."
    recommendation_items = "\n".join(
        f"<li><strong>{_html(recommendation.title)}</strong> "
        f"<span class=\"pill\">{_html(recommendation.priority)}</span>"
        f"<p>{_html(recommendation.description)}</p></li>"
        for recommendation in report.recommendations
    ) or "<li>No recommendations generated.</li>"
    artifact_rows = "\n".join(
        f"<tr><th>{_html(name)}</th><td><code>{_html(path)}</code></td></tr>"
        for name, path in sorted(report.artifacts.items())
    ) or "<tr><th>none</th><td>No artifacts.</td></tr>"
    metric_rows = "\n".join(
        f"<tr><th>{_html(label)}</th><td>{_html(value)}</td></tr>"
        for label, value in [
            ("Files scanned", kpi.files_scanned),
            ("Planned moves", kpi.planned_moves),
            ("Manual review moves", kpi.manual_review_moves),
            ("Blocked moves", kpi.blocked_moves),
            ("Destination conflicts", kpi.conflict_count),
            ("Estimated minutes saved", f"{kpi.estimated_minutes_saved:g}"),
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TheLibrarian Managed Cleanup Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17201c;
      --muted: #63736d;
      --line: #d8dfd7;
      --panel: #ffffff;
      --soft: #f5f8f2;
      --accent: #2f684e;
      --blue: #1d5565;
      --warn: #9c6a14;
      font-family: "Aptos", "Segoe UI", Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #eef3eb; color: var(--ink); }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 18px 48px; }}
    header {{ border: 1px solid var(--line); background: var(--panel); padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; line-height: 1.1; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }}
    p {{ line-height: 1.55; }}
    .muted {{ color: var(--muted); }}
    .snapshot, .cards, .two-col {{ display: grid; gap: 12px; }}
    .snapshot {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 18px; }}
    .card, section {{ border: 1px solid var(--line); background: var(--panel); padding: 16px; }}
    .card strong {{ display: block; font-size: 12px; color: var(--muted); text-transform: uppercase; }}
    .card span {{ display: block; margin-top: 8px; font-size: 24px; font-weight: 760; }}
    .two-col {{ grid-template-columns: minmax(0, 1fr) minmax(280px, 0.7fr); margin-top: 12px; }}
    section {{ margin-top: 12px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #edf1ea; padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ color: #3c4b45; width: 42%; }}
    code {{ overflow-wrap: anywhere; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li + li {{ margin-top: 10px; }}
    .pill {{ display: inline-block; margin-left: 6px; padding: 2px 7px; border: 1px solid #e4d2a7; background: #fff9ea; color: var(--warn); font-size: 12px; font-weight: 700; }}
    .safety {{ border-left: 4px solid var(--accent); }}
    @media print {{
      body {{ background: white; }}
      main {{ max-width: none; padding: 0; }}
      header, section, .card {{ break-inside: avoid; }}
    }}
    @media (max-width: 760px) {{
      .snapshot, .two-col {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">Privacy-first file organization copilot</p>
      <h1>TheLibrarian Managed Cleanup Report</h1>
      <p>{_html(report.summary)}</p>
      <div class="snapshot" aria-label="Report summary">
        <div class="card"><strong>Readiness</strong><span>{_html(readiness)}</span></div>
        <div class="card"><strong>Risk</strong><span>{_html(risk_posture)}</span></div>
        <div class="card"><strong>Safety</strong><span>{_html(kpi.safety_score)}/100</span></div>
        <div class="card"><strong>Planned</strong><span>{_html(kpi.planned_moves)}</span></div>
      </div>
    </header>

    <div class="two-col">
      <section>
        <h2>Service Snapshot</h2>
        <table>
          <tr><th>Client</th><td>{_html(session.client_name)}</td></tr>
          <tr><th>Operator</th><td>{_html(session.operator_name)}</td></tr>
          <tr><th>Root</th><td><code>{_html(session.root)}</code></td></tr>
          <tr><th>Session</th><td><code>{_html(session.session_id)}</code></td></tr>
          <tr><th>Policy pack</th><td>{_html(pack.name)} (<code>{_html(pack.id)}</code>)</td></tr>
          <tr><th>Report posture</th><td>Dry-run only, no file movement</td></tr>
        </table>
      </section>
      <section>
        <h2>KPI Snapshot</h2>
        <table>{metric_rows}</table>
      </section>
    </div>

    <section>
      <h2>Recommended Actions</h2>
      <ul>{recommendation_items}</ul>
    </section>

    <section>
      <h2>Artifact Map</h2>
      <table>{artifact_rows}</table>
    </section>

    <section class="safety">
      <h2>Safety Appendix</h2>
      <ul>
        <li>This managed workflow is dry-run only.</li>
        <li>No files were moved during this report run.</li>
        <li>No file contents were modified or sent to providers.</li>
        <li>Apply still requires explicit confirmation and rollback manifest workflow.</li>
      </ul>
    </section>

    <section>
      <h2>Next Steps</h2>
      <p>{_html(next_step)}</p>
    </section>
  </main>
</body>
</html>
"""


def _readiness_label(kpi) -> str:
    if kpi.blocked_moves > 0:
        return "Needs operator review before any apply"
    if kpi.manual_review_moves > 0 or kpi.review_category_count > 0 or kpi.conflict_count > 0:
        return "Ready for client review"
    if kpi.planned_moves > 0:
        return "Ready for apply consideration"
    return "No cleanup action needed"


def _risk_posture(kpi) -> str:
    if kpi.risk_score >= 50 or kpi.blocked_moves > 0:
        return "High"
    if kpi.risk_score >= 20 or kpi.manual_review_moves > 0 or kpi.conflict_count > 0:
        return "Medium"
    return "Low"


def _html(value) -> str:
    return escape(str(value), quote=True)
