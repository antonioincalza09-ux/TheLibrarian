# TheLibrarian

TheLibrarian is a local agent project for safely organizing files inside an assigned directory according to usage logic, convenience, and traceable operations.

## Goal

Build a local agent that can scan a target directory, classify files, propose an organization plan, and optionally apply that plan with a reversible manifest.

## Core Safety Rules

- Never delete files.
- Never edit file contents unless explicitly requested.
- Always support dry-run mode.
- Never move files outside the assigned root directory.
- Generate a human-readable plan before applying changes.
- Write a manifest for every applied operation.
- Put ambiguous files in `Review/` instead of guessing aggressively.

## Suggested First Milestone

1. Scan a directory and produce an inventory.
2. Classify files into broad categories.
3. Generate a dry-run organization plan.
4. Apply the plan only after explicit confirmation.
5. Produce a rollback manifest.

## Initial Categories

- `Documents/`
- `Media/`
- `Code/`
- `Archives/`
- `Data/`
- `Apps/`
- `Review/`

