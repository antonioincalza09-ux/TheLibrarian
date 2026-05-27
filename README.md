# The Librarian

The Librarian is a developer-first offline CLI for understanding, annotating, and safely organizing a workspace without modifying original source code.

It scans files and directories recursively, writes human-readable sidecar metadata, exports Markdown notes and runbooks, generates runnable helper scripts, prepares machine-readable artifacts for future knowledge graphs, and applies only safe reversible moves.

## Core Principles

- Never modify original source code.
- Store metadata out-of-band in sidecars and runtime artifacts.
- Keep every action reversible, inspectable, and dry-run friendly.
- Analyze directories as first-class nodes, not only files.
- Prefer logical views over aggressive physical moves for codebases.
- When a non-code subtree is uniformly safe, plan and apply can move the whole directory tree together.
- Work fully offline.

## CLI Commands

```powershell
librarian scan <path>
librarian mark <path>
librarian plan <path>
librarian apply <path>
librarian rollback <path>
librarian status <path>
librarian dev init <path>
librarian dev index <path>
librarian dev explain <path>
librarian dev runbook <path>
librarian graph validate <path>
librarian graph build <path>
librarian graph export <path> --format json
librarian graph export <path> --format graphml
librarian graph export <path> --format cypher
librarian graph export <path> --format markdown
librarian graph export <path> --format turtle
librarian graph export <path> --format sqlite
librarian graph report <path>
librarian graph index <path>
librarian graph query <path> --kind entrypoints
librarian graph query <path> --kind risks
librarian graph query <path> --kind modules
librarian graph query <path> --kind tags
librarian graph query <path> --kind dependencies
librarian graph query <path> --kind tests
librarian graph query <path> --kind duplicates
librarian graph query <path> --kind orphans
librarian agent context <path>
librarian agent runbook <path>
librarian agent scripts <path>
```

## Expected Outputs

After `mark` and `dev init`, The Librarian generates:

```text
.librarian/
  manifest.json
  plan.json
  README.librarian.md
  notes/
  runbooks/
  scripts/
  logs/
  cache/
*.librarian.yaml
.librarian.yaml
```

The helper scripts are runnable directly:

```powershell
python .librarian/scripts/inspect_workspace.py
python .librarian/scripts/print_manifest_summary.py
python .librarian/scripts/find_entrypoints.py
python .librarian/scripts/find_unmarked.py
```

## Knowledge Graph

The Librarian can build an offline knowledge graph from the manifest, sidecar YAML, plan, notes, runbooks, and helper scripts.

```powershell
librarian graph validate .\examples\graph_fixture
librarian graph build .\examples\graph_fixture
librarian graph export .\examples\graph_fixture --format json
librarian graph export .\examples\graph_fixture --format graphml
librarian graph export .\examples\graph_fixture --format cypher
librarian graph export .\examples\graph_fixture --format markdown
librarian graph export .\examples\graph_fixture --format turtle
librarian graph index .\examples\graph_fixture
librarian graph report .\examples\graph_fixture
```

Generated graph artifacts live under `.librarian/`: `graph.json`, `graph.graphml`, `graph.cypher`, `graph.ttl`, `graph_index.sqlite`, `graph_notes/*.md`, `graph_report.md`, `validation_report.json`, and `validation_report.md`.

## Agent Runtime

The agent runtime gives developers and AI agents a compact starting point:

```powershell
librarian agent context .\examples\graph_fixture
librarian agent runbook .\examples\graph_fixture
librarian agent scripts .\examples\graph_fixture
```

It writes `.librarian/agent_context.md`, `.librarian/agent_context.json`, agent/developer runbooks, and standard-library-only scripts under `.librarian/graph_scripts/`.

## Quickstart

```powershell
python -m pip install -e .
librarian scan .\examples\sample_data --write
librarian mark .\examples\sample_data
librarian dev init .\examples\sample_data
librarian dev index .\examples\sample_data
librarian dev explain .\examples\sample_data
librarian dev runbook .\examples\sample_data
librarian plan .\examples\sample_data
librarian status .\examples\sample_data
```

## Design Notes

- Python source files are analyzed statically with `ast`; they are never imported or executed during analysis.
- Generic code files use conservative heuristics for imports, functions, classes, framework hints, and entrypoints.
- Project roots like `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, and `pom.xml` are treated conservatively.
- For codebases, the plan can be logical-only rather than a physical move.
- For non-code workspaces, `plan` can emit directory entries and `apply` can move an entire safe subtree in one reversible operation.

## Documentation

- [docs/metadata_schema.md](docs/metadata_schema.md)
- [docs/developer_runtime.md](docs/developer_runtime.md)
- [docs/graph_schema.md](docs/graph_schema.md)
- [docs/agent_runtime.md](docs/agent_runtime.md)

## Compatibility

The previous `thelibrarian` command is still present during transition. The new developer-first CLI entrypoint is `librarian`.
