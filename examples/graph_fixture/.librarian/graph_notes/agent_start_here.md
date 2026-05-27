# Agent Start Here

Read these artifacts first:

- `.librarian/manifest.json`
- `.librarian/agent_context.md`
- `.librarian/graph.json`
- `.librarian/graph_notes/entrypoints.md`
- `.librarian/graph_notes/risks.md`

## Likely Entrypoints

- `src/graph_fixture_app/main.py`: function:main
- `src/graph_fixture_app/main.py`: guard:if __name__ == "__main__"

## Important Modules

- Import `json` (1 imports)
- Module `src.graph_fixture_app.main` (1 imports)
- Module `src.graph_fixture_app.utils` (1 imports)
- Module `build.generated` (0 imports)
- Module `src.graph_fixture_app.__init__` (0 imports)
- Module `tests.test_main` (0 imports)
- Module `vendor.library` (0 imports)
- Package `build` (0 imports)
- Package `src.graph_fixture_app` (0 imports)
- Package `tests` (0 imports)

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
