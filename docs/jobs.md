# Job Engine

The Job Engine is the first step toward safe long-running autonomy. It records checkpointed work under the assigned root so a future background runner can resume, inspect, or audit a directory organization task.

## Commands

```bash
thelibrarian job create C:\target
thelibrarian job run C:\target
thelibrarian job run C:\target --policy supervised_autonomy
thelibrarian job run C:\target --policy-pack supervised_documents
thelibrarian job run C:\target --pack studio_legale
thelibrarian job approve JOB_ID --root C:\target --confirm
thelibrarian job apply JOB_ID --root C:\target --confirm
thelibrarian job rollback JOB_ID --root C:\target --confirm
thelibrarian job status JOB_ID --root C:\target
thelibrarian job list C:\target
thelibrarian job events JOB_ID --root C:\target
```

`job create` creates a record only. `job run` creates and executes a dry-run job synchronously. It scans, plans, evaluates policy, writes artifacts, and leaves user files in place.

`--policy-pack PACK_ID` attaches a built-in, local, or vertical policy pack to the job and writes `policy_pack.json`. If `--policy` is omitted, the job uses the policy mode from the pack. If `--policy` is provided, it remains the explicit override. `--pack` remains supported as a short compatibility alias.

`job apply` requires `--confirm` and applies only policy-approved entries. `job approve` marks entries that require approval as manually approved, but blocked entries remain blocked. `job rollback` requires a manifest from a prior job apply.

## Artifacts

Each job is stored under:

```text
.thelibrarian/jobs/<job_id>/
```

The current artifacts are:

- `job.json`: current job state, phase, counters, paths, and error state.
- `inventory.json`: scanned metadata.
- `plan.json`: generated organization plan.
- `policy_decision.json`: policy evaluation, risk scores, approval status, and manual approval flags.
- `policy_pack.json`: optional policy pack snapshot when the job is created or run with `--policy-pack` or `--pack`.
- `report.txt`: human-readable report.
- `events.ndjson`: append-only event log.
- `verification.json`: apply summary written after a job apply.
- `rollback_verification.json`: rollback summary written after a job rollback.

## Current Limits

- There is no daemon, watcher, scheduler, or background thread yet.
- CLI `job run` is dry-run only.
- Only `dry_run_only` and `supervised_autonomy` policies exist.
- `supervised_autonomy` auto-approves only high-confidence `Documents`, `Media`, and `Data` entries that pass path and collision checks.
- No full autonomy, watch mode, scheduler, or policy DSL exists yet.

## Safety Invariants

- Job artifacts stay inside the assigned root.
- Job IDs are validated to block traversal.
- Scanner skips `.thelibrarian/` so runtime artifacts are not reorganized.
- Provider output remains untrusted and is still validated by the planner.
- Policy output is saved before apply and is treated as an auditable gate.
- Apply and rollback remain explicit, confirmed, auditable operations.
