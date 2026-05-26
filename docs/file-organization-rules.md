# File Organization Rules

## Default Categories

- `Documents/`: PDFs, Word documents, text notes, presentations, then split into specific context folders.
- `Media/`: images, audio, video, design exports.
- `Code/`: source files, scripts, config files, development assets.
- `Archives/`: zip, rar, 7z, tar, gz, backups.
- `Data/`: CSV, Excel, JSON, XML, database exports.
- `Apps/`: installers, executables, packages.
- `Review/`: unknown, ambiguous, duplicate-risk, or low-confidence files.

## Document Context Folders

Documents should not stay in a flat generic bucket. When safe signals exist, route them to a more specific folder:

- `Documents/Reports/`: reports, summaries, reviews, audits, analyses.
- `Documents/Financial/`: finance, invoices, receipts, budgets, taxes, statements.
- `Documents/Testing/`: testing, QA, accessibility, benchmark, performance, evidence, reality-check material.
- `Documents/Agents/`: agent and orchestrator documentation.
- `Documents/Workflows/`: workflows, pipelines, procedures, operations, sequencers.
- `Documents/Knowledge/`: knowledge graphs, ontology notes, registries, mappings, indexes.
- `Documents/Protocols/`: protocols, policies, rules, runbooks.
- `Documents/Manuals/`: manuals, guides, how-to material, handbooks, README-like files.
- `Documents/Notes/`: markdown notes, memos, meetings, journals.
- `Documents/Presentations/`: slide decks.
- `Documents/Text/`: plain text without stronger context.
- `Documents/General/`: documents with no stronger contextual signal.

## Decision Signals

Use multiple signals before deciding:

- file extension
- filename
- parent folder
- modified date
- lightweight content hints when safe
- related filename patterns
- project/client/topic naming
- contextual workspace markers such as `SKILL.md`, `.clawhub/`, `scripts/`, `references/`, `tests/`, and `_meta.json`

## Contextual Skill Workspaces

When a root looks like a skill workspace, TheLibrarian groups files by usage and function before generic type folders.

Examples:

- `excel-xlsx/SKILL.md` -> `Skills/excel-xlsx/Definition/SKILL.md`
- `ontology/scripts/ontology.py` -> `Skills/ontology/Source/ontology.py`
- `ontology/references/schema.md` -> `Skills/ontology/References/schema.md`
- `excel-xlsx/_meta.json` -> `Skills/excel-xlsx/Metadata/_meta.json`
- `workflow-sequencer.md` -> `Skills/workflow-sequencer/Documentation/workflow-sequencer.md`

This contextual layout can also repair broad category layouts created by earlier runs, such as `Documents/<skill>/SKILL.md`, `Code/<skill>/scripts/...`, and `Review/<skill>/_meta.json`.

## Safety Behavior

- If source and destination conflict, do not overwrite automatically.
- If confidence is low, route to `Review/`.
- If a file appears to belong to multiple groups, choose the group that best preserves workflow convenience.
- Preserve relative grouping when files appear related.
- Preserve relative subpaths under top-level category folders to reduce collisions and simplify rollback.
- Skip symlinks and operational directories such as `.thelibrarian/` and the legacy `.the_librarian/` path to avoid self-organization and path escapes.
- Treat structured text formats with dual use, such as `.json`, `.xml`, `.yml`, and `.yaml`, as `Review/` in the MVP.
- In CLI chat mode, manual plan edits are allowed only on destination, reason, and confidence metadata. File contents are never modified.
- In CLI chat mode, added analysis directories must be descendants of the assigned root.
