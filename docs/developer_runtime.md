# Developer Runtime

`librarian dev init <path>` creates a developer-friendly runtime under `.librarian/`.

Expected layout:

```text
.librarian/
  manifest.json
  plan.json
  README.librarian.md
  runbooks/
    index.md
    how_to_inspect.md
    how_to_run_python_tools.md
    how_to_extend_classifiers.md
  notes/
    index.md
    files.md
    directories.md
    code.md
    entrypoints.md
    risks.md
    explain.md
  scripts/
    inspect_workspace.py
    print_manifest_summary.py
    find_entrypoints.py
    find_unmarked.py
  logs/
    operations.jsonl
  cache/
    index.sqlite
```

Principles:

- original files are never rewritten
- metadata is stored in sidecars and runtime artifacts
- all scripts in `.librarian/scripts/` use only Python standard library
- dry-run planning and runtime generation are reversible and inspectable

Recommended flow:

```powershell
librarian scan <path>
librarian mark <path>
librarian dev init <path>
librarian dev index <path>
librarian dev explain <path>
librarian dev runbook <path>
```

Generated scripts:

- `inspect_workspace.py`: prints basic manifest information
- `print_manifest_summary.py`: concise counts, languages, domains, and warnings
- `find_entrypoints.py`: prints likely entrypoints from manifest and sidecars
- `find_unmarked.py`: detects manifest entries without sidecars
