# CLI Reference

The official command is `thelibrarian`. During local development, every command can also be run as `python -m src.cli`.

## Commands

- `scan ROOT --output inventory.json`: scans a root directory and writes inventory JSON.
- `plan ROOT --provider deterministic|ollama|openai-compatible --output plan.json`: generates a dry-run organization plan.
- `run ROOT --provider PROVIDER --format text|json`: scans, plans, prints a report, and writes a report under `.thelibrarian/reports/`.
- `apply ROOT --plan plan.json --confirm`: applies a saved plan and writes a rollback manifest.
- `rollback ROOT --manifest manifest.json --confirm`: reverses operations recorded in a manifest when destinations are clear.
- `doctor [ROOT] --provider PROVIDER --format text|json`: checks installation, config, root permissions, provider readiness, Ollama reachability, and `OPENAI_API_KEY` presence.
- `providers list`: lists provider names.
- `providers doctor --provider PROVIDER --format text|json`: runs provider-specific readiness checks.
- `serve ROOT --host 127.0.0.1 --port 8765`: starts the local browser preview app.
- `job create ROOT`: creates a checkpointed job record without scanning.
- `job run ROOT`: creates and runs a dry-run checkpointed job.
- `job approve JOB_ID --root ROOT --confirm`: manually approves decisions that require approval.
- `job apply JOB_ID --root ROOT --confirm`: applies only policy-approved entries.
- `job rollback JOB_ID --root ROOT --confirm`: rolls back a job manifest.
- `job status JOB_ID --root ROOT`: prints one job record.
- `job list ROOT`: lists jobs under a root.
- `job events JOB_ID --root ROOT`: prints append-only job events.

## Safety Defaults

- `run` is dry-run only.
- `apply` requires both `--plan` and `--confirm`.
- `rollback` requires both `--manifest` and `--confirm`.
- Plans must belong to the assigned root.
- Destinations are revalidated at execution time.

## Output Formats

`scan`, `plan`, `run`, `apply`, `rollback`, `doctor`, and `providers doctor` support JSON output where useful. Human-readable output is intended for operators; JSON output is intended for automation and tests.

## Diagnostics

`doctor` returns a non-zero exit code when required checks fail. Optional checks can produce warnings, such as missing optional OpenAI credentials when the configured provider is deterministic.

Provider diagnostics avoid generation calls:

- Ollama: `GET /api/tags`.
- OpenAI-compatible: presence of `OPENAI_API_KEY`, then `GET /models`.
