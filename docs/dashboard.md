# Dashboard

The local dashboard is served by `src.webapp` using only the Python standard library.

## Start

```powershell
thelibrarian serve ROOT --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765`.

## Sections

- Overview: live inventory and plan summary.
- Inventory: scanned metadata.
- Plan: proposed destinations with reason and confidence.
- Review: ambiguous, low-confidence, conflicted, or non-planned rows.
- Warnings: scanner and planner warnings.
- Jobs: checkpointed job records.
- Policy Packs: installed vertical packs.
- Managed Cleanup: dry-run service sessions and KPI.
- Providers: active provider and metadata-only notice.
- Policy, Events, Manifest: selected job audit details.

## API

```text
GET  /api/packs
GET  /api/packs/{pack_id}
GET  /api/packs/recommend?industry=legal
GET  /api/managed
GET  /api/managed/{session_id}
POST /api/managed/start?confirm=true
GET  /api/providers
GET  /api/providers/doctor?provider=remote-compatible
```

Existing job, root, inventory, plan, apply, and rollback endpoints remain available.

## Safety

Dashboard endpoints do not send file contents to providers. `POST /api/managed/start` only creates a dry-run job and report artifacts, and requires `confirm=true`. Apply and rollback remain separate confirmed workflows.
