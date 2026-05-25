# Dashboard

The local dashboard is served by `src.webapp` using only the Python standard library.

## Start

```powershell
thelibrarian serve ROOT --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765`.

## Sections

- Workflow strip: safe path from scan to plan, review, approval, apply, and rollback.
- Overview: live inventory and plan summary.
- Before / After Tree: two-level dry-run comparison of current scanned locations and planned destinations.
- Inventory: scanned metadata.
- Plan: proposed destinations with reason and confidence.
- Review: ambiguous, low-confidence, conflicted, or non-planned rows.
- Warnings: scanner and planner warnings.
- Jobs: checkpointed job records.
- Policy Packs: installed vertical packs plus selected pack detail, folder templates, and managed recommendations.
- Managed Cleanup: dry-run service sessions, client report paths, KPI cards, and local HTML report preview.
- Providers: active provider and metadata-only notice.
- Policy, Events, Manifest: selected job audit details.

## API

```text
GET  /api/packs
GET  /api/packs/{pack_id}
GET  /api/packs/recommend?industry=legal
GET  /api/plan?pack_id=studio_legale
POST /api/plan/save
GET  /api/managed
GET  /api/managed/{session_id}
GET  /api/managed/{session_id}/report-html
POST /api/managed/start?confirm=true
GET  /api/providers
GET  /api/providers/doctor?provider=remote-compatible
```

Existing job, root, inventory, plan, apply, and rollback endpoints remain available.

Selecting a Policy Pack in the dashboard can refresh the plan preview with pack-aware folder templates. This only changes the visible dry-run plan and saved plan artifact; it does not move files.

## Safety

Dashboard endpoints do not send file contents to providers. `POST /api/managed/start` only creates a dry-run job and report artifacts, and requires `confirm=true`. `GET /api/managed/{session_id}/report-html` serves only the generated report under `.thelibrarian/managed/<session_id>/report.html` for the current root. Apply and rollback remain separate confirmed workflows.

## Visual Direction

The dashboard should feel like an operational product for professionals rather than a developer console. Current UI polish favors:

- compact KPI cards over raw JSON where possible
- a visible safe workflow path before action buttons
- two-level before/after tree preview before any apply workflow
- pack detail and report preview panels for operator confidence
- status badges for stage, policy, review, and risk
- dense tables with filters for plan and review work
- no decorative remote assets, trackers, or external scripts

Future polish should keep the stdlib/local-first constraint until a frontend framework has a clear product reason.
