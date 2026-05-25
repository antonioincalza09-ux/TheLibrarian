# Architecture

TheLibrarian is a local-first file organization system built around safety, auditability, and product packaging for professionals and small businesses.

## System Boundaries

The current implementation is a Python application with no database and no required cloud service. Runtime state is stored under the assigned root in `.thelibrarian/`.

The major subsystems are:

- Core Engine: scanner, planner, executor, reporter, and shared models.
- CLI: operator interface exposed through `thelibrarian` and `python -m src.cli`.
- Local Web UI: stdlib HTTP dashboard served from `src.webapp`.
- Job Engine: checkpointed filesystem jobs under `.thelibrarian/jobs/<job_id>/`.
- Policy Engine: policy evaluation, approval status, risk scoring, and apply filtering.
- Policy Packs: JSON vertical templates from `data/policy_packs/` plus local template compatibility.
- Managed Service Foundation: dry-run service sessions, KPI, and client-readable reports under `.thelibrarian/managed/<session_id>/`.
- Provider Adapters: deterministic, Ollama, OpenAI-compatible, remote-compatible, and `antonio-managed` provider interfaces.

## Data Flow

1. `scanner` reads file metadata under the assigned root and skips operational directories.
2. `providers` optionally classify metadata. Remote-capable providers must remain metadata-only.
3. `planner` validates provider output, applies deterministic fallback when needed, and builds relative destinations.
   When a policy pack is attached, the planner may refine destinations with matching folder templates while staying inside known relative category roots.
4. `policies` evaluate planned entries before any job apply.
5. `reporter` writes human-readable reports, plans, and rollback manifests.
6. `executor` applies only confirmed plans and writes rollback artifacts.
7. `jobs` record checkpointed scan, plan, policy, report, and event artifacts.
8. `managed` creates dry-run client sessions from jobs and policy packs.
9. `webapp` exposes local dashboard endpoints over localhost.

## Runtime Directories

- `.thelibrarian/reports/`: operator reports.
- `.thelibrarian/plans/`: saved organization plans.
- `.thelibrarian/manifests/`: rollback manifests.
- `.thelibrarian/jobs/<job_id>/`: job state, events, inventory, plan, policy decision, policy pack copy, and job report.
- `.thelibrarian/managed/<session_id>/`: managed service session, report JSON, and report Markdown.
- `.thelibrarian/managed-cleanups/<session_id>/`: compatibility cleanup preview artifacts.
- `.thelibrarian/policy-packs/`: exported local policy pack templates.

The scanner skips `.thelibrarian/` and the legacy `.the_librarian/` directory name.

## Artifact Types

- Inventory JSON uses `Inventory.to_dict()`.
- Plan JSON uses `OrganizationPlan.to_dict()` and includes provider metadata.
- Execution manifests include app version, root, operations, rollback paths, and skipped entries.
- Job JSON uses `JobRecord.to_dict()` and is updated atomically by `JobStore`.
- Job events are append-only NDJSON lines.
- Policy decisions include status, reason, risk score, and manual approval state.
- Policy packs are copied into jobs as `policy_pack.json` for auditability.
- Managed sessions write `session.json`, `report.json`, `report.md`, and `report.html`.

## Product Architecture

The product has four intended packaging layers:

- Free Local: local CLI/dashboard, deterministic provider, dry-run planning, explicit apply/rollback.
- Pro Local: future local-only packaging for richer UI, advanced packs, professional exports, and batch workflows.
- Managed Service: operator-led cleanup sessions with KPI and client-readable reports.
- Team/Enterprise: future SaaS-ready architecture for shared templates, admin controls, licensing, SSO, billing, support, and optional metadata sync.

Only the local and managed-service foundations exist today. Billing, authentication, hosted dashboards, marketplace, and team administration are future architecture, not runtime features.

## Managed Vs Managed Cleanup

`src.managed` is the current product path for managed cleanup sessions. It builds on the job engine, policy packs, KPI, and client-facing reports.

`src.managed_cleanup` is a compatibility preview workflow from an earlier iteration. It remains available for existing commands, but new product work should prefer `managed`.

## Provider Trust Boundary

Provider output is never trusted as an execution command. Providers may suggest category, reason, and confidence. The planner validates those suggestions and the executor revalidates paths at apply time.

Remote-capable providers must not receive file contents, snippets, absolute paths, usernames, hashes intended to identify private files, API keys, or secrets. Malformed provider responses fall back to deterministic behavior and warnings.
