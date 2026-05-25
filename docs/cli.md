# CLI Reference

The official command is `thelibrarian`. During local development, every command can also be run as `python -m src.cli`.

## Commands

- `scan ROOT --output inventory.json`: scans a root directory and writes inventory JSON.
- `plan ROOT --provider deterministic|ollama|openai-compatible|remote-compatible|antonio-managed --output plan.json`: generates a dry-run organization plan.
- `run ROOT --provider PROVIDER --format text|json`: scans, plans, prints a report, and writes a report under `.thelibrarian/reports/`.
- `apply ROOT --plan plan.json --confirm`: applies a saved plan and writes a rollback manifest.
- `rollback ROOT --manifest manifest.json --confirm`: reverses operations recorded in a manifest when destinations are clear.
- `doctor [ROOT] --provider PROVIDER --format text|json`: checks installation, config, root permissions, provider readiness, Ollama reachability, and `OPENAI_API_KEY` presence.
- `providers list`: lists provider names.
- `providers doctor --provider PROVIDER --format text|json`: runs provider-specific readiness checks.
- `packs list|show|export|validate|recommend`: manages JSON vertical policy packs.
- `managed start ROOT --client NAME --operator NAME --pack PACK_ID`: creates a dry-run managed cleanup session and report.
- `managed list ROOT`: lists managed cleanup sessions.
- `managed show SESSION_ID --root ROOT`: shows one managed cleanup session.
- `managed report SESSION_ID --root ROOT`: regenerates a managed cleanup report.
- `serve ROOT --host 127.0.0.1 --port 8765`: starts the local browser preview app.
- `job create ROOT --pack PACK_ID`: creates a checkpointed job record without scanning.
- `job run ROOT --pack PACK_ID`: creates and runs a dry-run checkpointed job.
- `job approve JOB_ID --root ROOT --confirm`: manually approves decisions that require approval.
- `job apply JOB_ID --root ROOT --confirm`: applies only policy-approved entries.
- `job rollback JOB_ID --root ROOT --confirm`: rolls back a job manifest.
- `job status JOB_ID --root ROOT`: prints one job record.
- `job list ROOT`: lists jobs under a root.
- `job events JOB_ID --root ROOT`: prints append-only job events.
- `policy-packs list [--root ROOT]`: lists built-in and local policy packs.
- `policy-packs show PACK_ID [--root ROOT]`: prints a policy pack.
- `policy-packs export PACK_ID ROOT`: writes a pack under `.thelibrarian/policy-packs/`.
- `cleanup preview ROOT --policy-pack PACK_ID`: creates a local dry-run managed cleanup session.
- `cleanup list ROOT`: lists managed cleanup sessions.
- `cleanup status SESSION_ID --root ROOT`: prints one managed cleanup session.
- `cleanup report SESSION_ID --root ROOT`: prints the managed cleanup report.

## Safety Defaults

- `run` is dry-run only.
- `apply` requires both `--plan` and `--confirm`.
- `rollback` requires both `--manifest` and `--confirm`.
- Plans must belong to the assigned root.
- Destinations are revalidated at execution time.

## Output Formats

`scan`, `plan`, `run`, `apply`, `rollback`, `doctor`, `packs`, `managed`, and `providers doctor` support JSON output where useful. Human-readable output is intended for operators; JSON output is intended for automation and tests.

`policy-packs` and `cleanup` are local foundations for future template marketplace and managed service workflows. They do not authenticate, bill, sync, or call external services.

## Diagnostics

`doctor` returns a non-zero exit code when required checks fail. Optional checks can produce warnings, such as missing optional OpenAI credentials when the configured provider is deterministic.

Provider diagnostics avoid generation calls:

- Ollama: `GET /api/tags`.
- OpenAI-compatible: presence of `OPENAI_API_KEY`, then `GET /models`.
- Remote-compatible and Antonio-managed: endpoint, model, API-key environment name, API-key presence, timeout, and metadata-only posture without a mandatory cloud call.
