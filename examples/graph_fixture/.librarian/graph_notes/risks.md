# Risks

| Path | Risk | Type | Reason |
| --- | --- | --- | --- |
| `vendor/library.py` | high risk | HAS_RISK | Risk level is recorded on the workspace node. |
| `poetry.lock` | high risk | HAS_RISK | Risk level is recorded on the workspace node. |
| `build/generated.py` | medium risk | HAS_RISK | Risk level is recorded on the workspace node. |
| `vendor/library.py` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
| `tests/test_main.py` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
| `poetry.lock` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
| `build/generated.py` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
| `src/graph_fixture_app/__init__.py` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
| `src/graph_fixture_app/utils.py` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
| `src/graph_fixture_app/main.py` | should not modify | SHOULD_NOT_MODIFY | Original source and protected files are read-only by default. |
