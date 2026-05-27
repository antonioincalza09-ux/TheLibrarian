# How To Use Runnable Scripts

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
