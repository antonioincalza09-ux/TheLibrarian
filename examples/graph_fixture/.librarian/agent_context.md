# Agent Context

## Workspace

- Root: `C:\Users\batti\Documents\Codex\2026-05-27\apri-la-repository-antonioincalza09-ux-thelibrarian\examples\graph_fixture`
- Files: `12`
- Directories: `8`
- Languages: Python
- Domains: Code, Configuration, Documentation

## Where To Start

- `src/graph_fixture_app/main.py`
- `src/graph_fixture_app/main.py`
- `README.md`
- `poetry.lock`
- `pyproject.toml`
- `build/generated.py`
- `data/duplicate_a.txt`
- `data/duplicate_b.txt`
- `docs/overview.md`
- `tests/test_main.py`
- `vendor/library.py`
- `src/graph_fixture_app/__init__.py`
- `src/graph_fixture_app/utils.py`
- `.librarian/manifest.json`
- `.librarian/graph_notes/agent_start_here.md`
- `.librarian/graph_notes/risks.md`

## Entrypoints

- `src/graph_fixture_app/main.py`: function:main
- `src/graph_fixture_app/main.py`: guard:if __name__ == "__main__"

## Runnable Scripts

- `python .librarian/scripts/find_entrypoints.py`
- `python .librarian/scripts/find_unmarked.py`
- `python .librarian/scripts/inspect_workspace.py`
- `python .librarian/scripts/print_manifest_summary.py`
- `python .librarian/graph_scripts/query_dependencies.py`
- `python .librarian/graph_scripts/query_entrypoints.py`
- `python .librarian/graph_scripts/query_files_by_tag.py`
- `python .librarian/graph_scripts/query_graph_summary.py`
- `python .librarian/graph_scripts/query_orphans.py`
- `python .librarian/graph_scripts/query_risks.py`
- `python .librarian/graph_scripts/query_tests.py`

## Risks

- `vendor/library.py`: high risk
- `poetry.lock`: high risk
- `build/generated.py`: medium risk
- `vendor/library.py`: should not modify
- `tests/test_main.py`: should not modify
- `poetry.lock`: should not modify
- `build/generated.py`: should not modify
- `src/graph_fixture_app/__init__.py`: should not modify
- `src/graph_fixture_app/utils.py`: should not modify
- `src/graph_fixture_app/main.py`: should not modify

## Query Suggestions

- `librarian graph query <path> --kind entrypoints`
- `librarian graph query <path> --kind risks`
- `librarian graph query <path> --kind modules`
- `librarian graph query <path> --kind tags`

## Runtime Paths

- Manifest: `.librarian/manifest.json`
- Graph JSON: `.librarian/graph.json`
- Graph notes: `.librarian/graph_notes`
