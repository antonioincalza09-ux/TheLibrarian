# Architecture

TheLibrarian is organized around a small safety-first core.

## Data Flow

1. `scanner` reads metadata under the assigned root.
2. `providers` optionally classify metadata.
3. `planner` validates classification and builds destinations, including deterministic contextual layouts for skill workspaces and document subfolders.
4. `reporter` renders human-readable and JSON artifacts.
5. `executor` applies saved plans and writes rollback manifests.
6. `webapp` exposes a localhost operations dashboard backed by the same core.
7. `jobs` records checkpointed scan/plan/report work under `.thelibrarian/jobs/<job_id>/`.
8. `policies` evaluates plans before any job apply and records auditable decisions.
9. `doctor` runs install, config, root permission, and provider readiness checks.
10. `policy_packs` loads vertical JSON packs from `data/policy_packs/` and keeps compatibility with local reusable policy templates.
11. `managed` creates dry-run service sessions, KPI, and client reports.
12. `managed_cleanup` preserves the earlier local dry-run cleanup preview workflow.

## Provider Interface

Providers receive an `Inventory` and `ProviderContext`, then return per-file `source`, `category`, `reason`, and `confidence`.

The planner rejects unknown sources, unknown categories, invalid confidence values, and empty reasons. Invalid provider rows fall back to deterministic classification.

## Artifact Types

- Inventory JSON uses `Inventory.to_dict()`.
- Plan JSON uses `OrganizationPlan.to_dict()` and includes `provider`.
- Execution manifests include app version, root, operations, rollback paths, and skipped entries.
- Job JSON uses `JobRecord.to_dict()` and is updated atomically by the filesystem `JobStore`.
- Job events are append-only NDJSON lines in `events.ndjson`.
- Policy decisions are saved as `policy_decision.json` and include status, reason, risk score, and manual approval state.
- Policy packs are copied into jobs as `policy_pack.json` for auditability.
- Managed sessions write `session.json`, `report.json`, and `report.md`.
- Legacy cleanup preview sessions write `cleanup_session.json`, `inventory.json`, `plan.json`, `policy_decision.json`, `kpi.json`, `policy_pack.json`, and `report.txt`.

## Runtime Directories

- Reports are written under `.thelibrarian/reports/`.
- Saved plans are written under `.thelibrarian/plans/`.
- Rollback manifests are written under `.thelibrarian/manifests/`.
- Jobs are written under `.thelibrarian/jobs/<job_id>/`.
- Local policy pack exports are written under `.thelibrarian/policy-packs/`.
- Managed cleanup sessions are written under `.thelibrarian/managed/<session_id>/`.
- Cleanup preview sessions are written under `.thelibrarian/managed-cleanups/<session_id>/`.
- The scanner skips both `.thelibrarian/` and the legacy `.the_librarian/` directory name.

## Vertical Packs And Managed Cleanup

Policy packs are data-driven JSON files. They describe industry templates, recommended policy mode, KPI targets, and service recommendations. Jobs can attach a pack with `--pack`, but v1 does not yet let packs alter classification.

Managed cleanup builds on jobs: it creates a dry-run job, computes KPI from inventory, plan, policy decision, and job counters, then writes client-readable reports. It never applies changes automatically.
