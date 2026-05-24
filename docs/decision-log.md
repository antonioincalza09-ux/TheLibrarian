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
