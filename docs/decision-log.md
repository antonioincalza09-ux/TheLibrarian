# Decision Log

## 2026-05-24

- Started the project with a safety-first architecture.
- Chose dry-run as the default operating mode.
- Chose broad initial categories to keep the MVP understandable.
- Decided that ambiguous files go to `Review/` instead of being forced into a category.
- Chose to preserve each file's relative subpath beneath the target category to reduce collisions and keep rollback straightforward.
- Chose to write rollback manifests under `.the_librarian/manifests/` inside the assigned root and exclude that operational folder from future scans.
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
