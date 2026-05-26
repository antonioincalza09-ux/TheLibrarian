# Decision Log

## 2026-05-24

- Started the project with a safety-first architecture.
- Chose dry-run as the default operating mode.
- Chose broad initial categories to keep the MVP understandable.
- Decided that ambiguous files go to `Review/` instead of being forced into a category.
- Chose to preserve each file's relative subpath beneath the target category to reduce collisions and keep rollback straightforward.
- Chose to write rollback manifests under `.thelibrarian/manifests/` inside the assigned root and exclude operational folders from future scans.
- Chose to skip symlinks in the MVP so the organizer never follows a path that could escape the assigned root.
- Chose `thelibrarian` as the standalone CLI entrypoint while keeping `python -m src.cli` and `python -m src.main` usable during development.
- Chose a provider plugin architecture with deterministic classification as the mandatory fallback.
- Chose metadata-only online provider behavior; file contents are never sent to model providers.
- Chose a CLI-first local web app as the first desktop path, served from localhost against a single assigned root.
- Chose explicit saved-plan confirmation for apply and explicit manifest confirmation for rollback.
- Chose a filesystem-based Job Engine under `.thelibrarian/jobs/<job_id>/` instead of a database for the first autonomy step.
- Chose synchronous checkpointed job runs before adding daemons, watchers, schedulers, or background threads.
- Chose append-only NDJSON events and atomic `job.json` replacement to keep jobs auditable and simple to resume later.
- Chose a minimal policy gate with `dry_run_only` and `supervised_autonomy` before allowing job apply.
- Chose `policy_decision.json` as the auditable bridge between planning, manual approval, and controlled apply.
- Chose to keep `Code`, `Apps`, `Archives`, and `Review` out of supervised auto-apply.
- Chose to evolve the localhost web app into a stdlib-only operations dashboard backed by the same job, policy, executor, and rollback APIs instead of adding a frontend framework for v1.
- Chose explicit dashboard root switching by path, with confirmation, so the local UI can target a new assigned root without adding browser filesystem permissions.
- Chose to allow dashboard job-history deletion only inside `.thelibrarian/jobs/`, leaving user files and rollback manifests untouched.
- Chose deterministic contextual destination planning for skill workspaces so related definitions, source scripts, references, tests, metadata, and loose skill markdown files are grouped under `Skills/<skill>/<function>/` instead of only by file extension.
- Chose to split `Documents/` into deterministic context subfolders such as `Reports`, `Financial`, `Testing`, `Agents`, `Workflows`, `Knowledge`, `Protocols`, `Manuals`, `Notes`, `Presentations`, `Text`, and `General` to avoid an overly generic document bucket.

## 2026-05-25

- Chose explicit runtime artifact folders under `.thelibrarian/reports/`, `.thelibrarian/plans/`, `.thelibrarian/manifests/`, and `.thelibrarian/jobs/`.
- Chose lightweight provider diagnostics: Ollama uses `/api/tags`, and OpenAI-compatible endpoints use `/models` after checking `OPENAI_API_KEY`.
- Chose a server-side plan save endpoint for the web UI so apply can continue to require a saved plan path.
- Chose dashboard-only Plan and Review filters plus browser-side plan JSON download; filtering changes only what is visible in the UI and never changes the saved or applied plan.
- Chose local file-based Policy Packs as the marketplace foundation, with built-in packs plus optional `.thelibrarian/policy-packs/` exports and no remote marketplace calls.
- Chose local dry-run Managed Cleanup sessions under `.thelibrarian/managed-cleanups/` as the managed service foundation, producing KPI and report artifacts without cloud services or apply behavior.
- Chose data-driven JSON policy packs under `data/policy_packs/` so vertical templates can evolve without scattering industry logic through Python.
- Chose to attach packs to jobs by copying `policy_pack.json` into the job directory and storing `pack_id` in `job.json`, while leaving classification unchanged for this step.
- Chose a filesystem-based Managed Cleanup foundation under `.thelibrarian/managed/<session_id>/` with KPI and client-readable reports, always dry-run by default.
- Chose `remote-compatible` and `antonio-managed` provider adapters for future hosted AI classification, with metadata-only payloads and deterministic fallback.
- Chose to extend the dashboard/API with policy packs, managed cleanup, KPI, and provider status without adding a frontend framework or enabling automatic apply.
- Chose `job create/run --policy-pack PACK_ID` as the explicit bridge from Policy Packs to Job Engine while keeping `--policy` as the manual override and `--pack` as a compatibility alias.
- Chose to add a local static HTML managed report next to Markdown and JSON so operators have a client-ready visual deliverable without remote assets or cloud services.
- Chose dashboard polish around workflow and KPI clarity instead of adding a frontend framework, preserving the stdlib-only local UI for this phase.
- Chose conservative policy-pack folder-template routing in the planner: packs can refine destinations only when the existing category and filename/path tokens match a safe relative template.
- Chose a two-level before/after dashboard preview so operators can see dry-run structure changes before saving, approving, or applying a plan.
- Chose a root-confined managed report HTML preview endpoint and iframe panel so operators can inspect client deliverables without opening files manually or loading remote assets.
- Chose to move policy pack detail into the dashboard so vertical templates are visible before an operator creates a job or managed session.

## 2026-05-26

- Chose a new `thelibrarian chat <root>` command to let operators discuss and revise planned moves in natural-language-like CLI prompts without directly editing JSON plans.
- Chose chat-scoped directory inclusion (`add-dir`/`aggiungi directory`) to explicitly focus analysis on selected subdirectories while keeping the root boundary enforced.
- Chose scripted chat commands (`--command` repeatable) to keep the interaction testable and automation-friendly.
- Chose folder-derived job names and job ids so operators see readable job references instead of opaque alphanumeric identifiers.
- Chose to expose the review chat inside the localhost dashboard as a first-class panel backed by the same server-side chat session used by the CLI workflow.
- Chose to allow safe whole-directory move planning and apply/rollback for non-code subtrees when every descendant file is movable, while keeping codebase-like trees logical-only.
