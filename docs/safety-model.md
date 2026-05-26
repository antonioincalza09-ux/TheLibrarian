# Safety Model

TheLibrarian treats user files as valuable and avoids irreversible operations.

## Invariants

- Never delete files.
- Never edit file contents.
- Never move files outside the assigned root.
- Dry-run is the default behavior.
- Apply requires a saved plan and explicit confirmation.
- Rollback requires a manifest and explicit confirmation.
- Existing destination files are never overwritten.
- Ambiguous or low-confidence files go to `Review/`.
- Symlinks and `.thelibrarian/` operational files are skipped during scanning.
- Job apply requires policy approval plus explicit confirmation.

## Threat Model

Provider output is untrusted. A provider can suggest category, reason, and confidence, but cannot directly decide a final filesystem path. Planner and executor validation remain authoritative.

Online providers operate in metadata-only mode. They must not receive file contents, snippets, hashes intended to identify private content, or absolute paths.

Policy packs are local JSON templates. They can configure a policy gate and conservative folder-template refinements, but they cannot bypass planner or executor validation.

Managed cleanup sessions are local dry-run previews. They do not apply moves, require no cloud service, and write only `.thelibrarian/managed/` or `.thelibrarian/managed-cleanups/` artifacts.

Execution rechecks every source and destination at apply time because the filesystem may have changed after planning.

## Job Policy Gate

Job autonomy is policy-driven. `dry_run_only` never auto-approves entries. `supervised_autonomy` auto-approves only high-confidence `Documents`, `Media`, and `Data` moves that avoid sensitive directories and collisions. `Code`, `Apps`, `Archives`, and `Review` require manual approval or are blocked.
