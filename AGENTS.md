# File Organizer Agent Instructions

This project builds a local file organization agent.

## Operating Principles

- Treat user files as valuable and irreplaceable.
- Do not delete files.
- Do not modify file contents unless the user explicitly asks.
- Do not move files outside the assigned root directory.
- Prefer dry-run output before any filesystem change.
- If classification is uncertain, place the file in `Review/`.
- Every applied operation must be logged in a manifest that can support rollback.
- Keep logic modular and testable.

## Architecture

- `src/scanner/`: reads directory structure, file metadata, and lightweight file signals.
- `src/classifier/`: assigns categories and confidence scores.
- `src/planner/`: creates a proposed destination plan.
- `src/executor/`: applies approved plans safely.
- `src/reporter/`: writes human-readable reports and JSON manifests.

## Expected Agent Output

For every organization run, produce:

- directory inventory summary
- proposed folder structure
- move plan with source, destination, reason, and confidence
- ambiguous file list
- warnings and skipped files
- JSON manifest path if changes are applied

## Development Rules

- Add or update tests for behavior changes.
- Keep new rules documented in `docs/file-organization-rules.md`.
- Record material design decisions in `docs/decision-log.md`.
- Preserve existing style and structure.
- Favor small, reviewable changes on short-lived branches.

