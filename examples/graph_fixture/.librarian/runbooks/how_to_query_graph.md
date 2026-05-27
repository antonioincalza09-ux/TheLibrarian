# How To Query The Graph

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
