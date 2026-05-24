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

## Threat Model

Provider output is untrusted. A provider can suggest category, reason, and confidence, but cannot directly decide a final filesystem path. Planner and executor validation remain authoritative.

Online providers operate in metadata-only mode. They must not receive file contents, snippets, hashes intended to identify private content, or absolute paths.

Execution rechecks every source and destination at apply time because the filesystem may have changed after planning.
