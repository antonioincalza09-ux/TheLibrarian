# Developer Start Here

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
