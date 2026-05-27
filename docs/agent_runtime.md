# Agent Runtime

The agent runtime gives developers and AI agents a compact, read-only way to inspect a workspace.

## Commands

```powershell
librarian agent context <path>
librarian agent runbook <path>
librarian agent scripts <path>
```

## Agent Context

`librarian agent context <path>` writes:

```text
.librarian/agent_context.md
.librarian/agent_context.json
```

The JSON file includes workspace summary, top files and directories, entrypoints, risks, runnable scripts, graph artifact paths, recommended first reads, warnings, and suggested queries.

## Runbooks

`librarian agent runbook <path>` writes:

```text
.librarian/runbooks/agent_start_here.md
.librarian/runbooks/developer_start_here.md
.librarian/runbooks/how_to_query_graph.md
.librarian/runbooks/how_to_use_runnable_scripts.md
```

Agents should read `manifest.json`, `agent_context.md`, `graph_notes/entrypoints.md`, and `graph_notes/risks.md` first. Source files remain read-only unless the user explicitly asks for edits.

## Runnable Graph Scripts

`librarian agent scripts <path>` writes standard-library-only Python scripts:

```text
.librarian/graph_scripts/query_graph_summary.py
.librarian/graph_scripts/query_entrypoints.py
.librarian/graph_scripts/query_risks.py
.librarian/graph_scripts/query_dependencies.py
.librarian/graph_scripts/query_tests.py
.librarian/graph_scripts/query_files_by_tag.py
.librarian/graph_scripts/query_orphans.py
```

Run them directly:

```powershell
python .librarian/graph_scripts/query_graph_summary.py
python .librarian/graph_scripts/query_entrypoints.py
python .librarian/graph_scripts/query_risks.py
python .librarian/graph_scripts/query_dependencies.py
python .librarian/graph_scripts/query_tests.py
```

The scripts read `.librarian/graph.json`, print concise output, handle missing or invalid graph files, and do not modify original files.

## Query Surface

The CLI can query common graph views directly:

```powershell
librarian graph query <path> --kind entrypoints
librarian graph query <path> --kind risks
librarian graph query <path> --kind modules
librarian graph query <path> --kind tags
librarian graph query <path> --kind dependencies
librarian graph query <path> --kind tests
librarian graph query <path> --kind duplicates
librarian graph query <path> --kind orphans
```
