# CLI Reference

The official command is `thelibrarian`. During local development, every command can also be run as `python -m src.cli`.

## Commands

- `scan ROOT --output inventory.json`: scans a root directory and writes inventory JSON.
- `plan ROOT --provider deterministic|ollama|openai-compatible --output plan.json`: generates a dry-run organization plan.
- `run ROOT --provider PROVIDER --format text|json`: scans, plans, prints a report, and writes a report under `.thelibrarian/reports/`.
- `apply ROOT --plan plan.json --confirm`: applies a saved plan and writes a rollback manifest.
- `rollback ROOT --manifest manifest.json --confirm`: reverses operations recorded in a manifest when destinations are clear.
- `providers list`: lists provider names.
- `providers doctor --provider PROVIDER`: prints provider runtime configuration.
- `serve ROOT --host 127.0.0.1 --port 8765`: starts the local browser preview app.

## Safety Defaults

- `run` is dry-run only.
- `apply` requires both `--plan` and `--confirm`.
- `rollback` requires both `--manifest` and `--confirm`.
- Plans must belong to the assigned root.
- Destinations are revalidated at execution time.

## Output Formats

`scan`, `plan`, `run`, `apply`, and `rollback` support JSON output where useful. Human-readable output is intended for operators; JSON output is intended for automation and tests.
