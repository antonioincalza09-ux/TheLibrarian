from __future__ import annotations

from pathlib import Path


def generate_agent_runbooks(root: str | Path) -> list[Path]:
    resolved_root = Path(root).resolve()
    runbooks_dir = resolved_root / ".librarian" / "runbooks"
    runbooks_dir.mkdir(parents=True, exist_ok=True)
    runbooks = {
        "agent_start_here.md": _agent_start_here(),
        "developer_start_here.md": _developer_start_here(),
        "how_to_query_graph.md": _how_to_query_graph(),
        "how_to_use_runnable_scripts.md": _how_to_use_runnable_scripts(),
    }
    written: list[Path] = []
    for name, content in runbooks.items():
        path = runbooks_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def _agent_start_here() -> str:
    return """# Agent Start Here

1. Read `.librarian/manifest.json`.
2. Read `.librarian/agent_context.md`.
3. Read `.librarian/graph_notes/entrypoints.md`.
4. Read `.librarian/graph_notes/risks.md`.
5. Use scripts only in read-only mode.
6. Do not modify original code unless the user explicitly asks.
7. Use sidecar YAML to understand file and directory context.
8. Use `.librarian/graph.json` to navigate dependencies, tags, entrypoints, and risks.
"""


def _developer_start_here() -> str:
    return """# Developer Start Here

The Librarian keeps source files untouched and writes metadata under `.librarian/` plus sidecar YAML files.

Useful first reads:

- `.librarian/README.librarian.md`
- `.librarian/graph_report.md`
- `.librarian/graph_notes/entrypoints.md`
- `.librarian/graph_notes/risks.md`
- `.librarian/agent_context.md`

Useful commands:

```powershell
librarian graph validate <path>
librarian graph build <path>
librarian graph report <path>
librarian agent scripts <path>
```

Extend the system by adding sidecar fields, improving static analyzers, or adding graph queries.
"""


def _how_to_query_graph() -> str:
    return """# How To Query The Graph

CLI examples:

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

Standalone examples:

```powershell
python .librarian/graph_scripts/query_entrypoints.py
python .librarian/graph_scripts/query_risks.py
python .librarian/graph_scripts/query_dependencies.py
python .librarian/graph_scripts/query_tests.py
```

Common tasks:

- Find entrypoints from `HAS_ENTRYPOINT` edges.
- Find risky files from `HAS_RISK` and `SHOULD_NOT_MODIFY` edges.
- Find imported modules from `IMPORTS` edges.
- Find tests from `Test` nodes and `TESTS` edges.
- Find untagged files by checking file nodes without `tags`.
- Find duplicates from `SIMILAR_TO` edges with `duplicate: true`.
- Inspect `.librarian/graph_index.sqlite` when a local SQL view is more convenient.
"""


def _how_to_use_runnable_scripts() -> str:
    return """# How To Use Runnable Scripts

Scripts under `.librarian/scripts/` and `.librarian/graph_scripts/` are standalone Python files.

They use only the standard library, read `.librarian/manifest.json` or `.librarian/graph.json`, and do not modify original files.

Examples:

```powershell
python .librarian/scripts/inspect_workspace.py
python .librarian/graph_scripts/query_graph_summary.py
python .librarian/graph_scripts/query_files_by_tag.py Code
```

Additional graph exports:

```powershell
librarian graph export <path> --format turtle
librarian graph index <path>
```
"""
