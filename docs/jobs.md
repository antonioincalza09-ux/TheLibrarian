# Job Engine

The Job Engine is the first step toward safe long-running autonomy. It records checkpointed work under the assigned root so a future background runner can resume, inspect, or audit a directory organization task.

## Commands

```bash
thelibrarian job create C:\target
thelibrarian job run C:\target
thelibrarian job status JOB_ID --root C:\target
thelibrarian job list C:\target
thelibrarian job events JOB_ID --root C:\target
```

`job create` creates a record only. `job run` creates and executes a dry-run job synchronously. It scans, plans, writes artifacts, and leaves user files in place.

## Artifacts

Each job is stored under:

```text
.thelibrarian/jobs/<job_id>/
```

The current artifacts are:

- `job.json`: current job state, phase, counters, paths, and error state.
- `inventory.json`: scanned metadata.
- `plan.json`: generated organization plan.
- `report.txt`: human-readable report.
- `events.ndjson`: append-only event log.

## Current Limits

- There is no daemon, watcher, scheduler, or background thread yet.
- CLI `job run` is dry-run only.
- Non-dry-run jobs move to `awaiting_approval` unless internal code explicitly passes `allow_apply=True`.
- No policy engine is implemented yet; `policy_name` is stored for future use.

## Safety Invariants

- Job artifacts stay inside the assigned root.
- Job IDs are validated to block traversal.
- Scanner skips `.thelibrarian/` so runtime artifacts are not reorganized.
- Provider output remains untrusted and is still validated by the planner.
- Apply and rollback remain explicit, auditable operations.

