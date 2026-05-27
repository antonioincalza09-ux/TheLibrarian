# Dashboard

The local dashboard is served by `src.webapp` using only the Python standard library.

## Start

```powershell
thelibrarian serve ROOT --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765`.

## Design Goal

The dashboard is the first operational surface for a developer or agent entering a workspace.

It is optimized to answer these questions quickly:

- What project am I looking at?
- Where should I start reading?
- Which files are important?
- Which files should I avoid touching?
- Where are the entrypoints and tests?
- Which scripts and runbooks can I execute safely?
- What data is missing, stale, or low-confidence?

## Layout

- Persistent left sidebar for navigation.
- Top header with workspace identity, status, and primary actions.
- Central content area with section-specific tables and cards.
- Right detail panel for inspecting selected files, risks, scripts, graph items, and operations.

## Primary Sections

- `Overview`: hero summary, metric cards, health summary, first reads, and protected files.
- `Start Here`: recommended reads, commands, runnable scripts, important files, and agent instructions.
- `Files`: searchable and filterable file inventory with path copy and graph jump actions.
- `Directories`: role-aware directory explorer with confidence and risk context.
- `Code`: languages, frameworks, modules, config files, entrypoints, and tests.
- `Graph`: graph summary, top connected nodes, node search, and entrypoint neighborhood.
- `Risks`: high-risk items, generated/vendor/lock signals, missing sidecars, and low-confidence items.
- `Runbooks`: generated Markdown runbooks with copyable commands and paths.
- `Scripts`: runnable helper scripts under `.librarian/scripts/`.
- `Operations`: timeline of append-only log activity.
- `Diagnostics`: artifact presence, parsing issues, stale index status, and next-step suggestions.

## Data Inputs

The dashboard degrades gracefully when some files are missing and reads from `.librarian` when available:

- `.librarian/manifest.json`
- `.librarian/graph.json`
- `.librarian/graph_report.md`
- `.librarian/validation_report.json`
- `.librarian/agent_context.json`
- `.librarian/plan.json`
- `.librarian/logs/operations.jsonl`
- `.librarian/notes/*.md`
- `.librarian/graph_notes/*.md`
- `.librarian/runbooks/*.md`
- `.librarian/scripts/*.py`

## API

Existing endpoints remain available for inventory, plan, jobs, managed cleanup, providers, and root switching.

Developer-first dashboard endpoints:

```text
GET /api/librarian/dashboard
GET /api/librarian/files
GET /api/librarian/directories
GET /api/librarian/entrypoints
GET /api/librarian/scripts
GET /api/librarian/risks
GET /api/librarian/graph-summary
GET /api/librarian/agent-brief
```

## Notes

- The dashboard never modifies source files directly.
- `Save plan artifact` writes plan JSON without applying moves.
- `Re-index` and `Copy Agent Context` are copy-first actions so the UI stays honest about what the current backend can execute itself.
- Graph visualization currently focuses on readable summaries and relationship tables; it reads `graph.json` when present but does not generate graph data on its own.
