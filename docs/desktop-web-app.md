# Local Web App

The local web app is a browser-based operations dashboard for the standalone application.

```bash
thelibrarian serve C:\target --host 127.0.0.1 --port 8765
```

The server exposes:

- `/`: browser UI.
- `/api/root`: returns or changes the dashboard target root. `POST` requires `confirm=true`.
- `/api/dashboard`: combined inventory, plan, job, policy, event, and manifest preview.
- `/api/inventory`: inventory JSON.
- `/api/plan`: plan JSON.
- `/api/plan/save`: saves the current generated plan under `.thelibrarian/plans/`.
- `/api/apply?confirm=true`: applies a saved plan path from JSON body.
- `/api/jobs/create`: creates a checkpointed job record.
- `/api/jobs/run`: runs a dry-run checkpointed job.
- `/api/jobs/<job_id>`: returns one job record.
- `/api/jobs/<job_id>/events`: returns append-only job events.
- `/api/jobs/<job_id>/policy`: returns the policy decision artifact.
- `/api/jobs/<job_id>/manifest`: returns the rollback manifest when available.
- `/api/jobs/<job_id>/approve?confirm=true`: approves review-required policy entries.
- `/api/jobs/<job_id>/apply?confirm=true`: applies policy-approved entries.
- `/api/jobs/<job_id>/rollback?confirm=true`: rolls back from the job manifest.
- `/api/jobs/<job_id>/delete?confirm=true`: deletes one job record and its job artifacts.
- `/api/jobs/delete-all?confirm=true`: deletes all job records for the current root.

The v1 dashboard shows Overview, Inventory, Plan, Review, Warnings, Jobs, Policy, Events, and Manifest views. It polls the local server for updates and exposes functional buttons for selecting the target directory, creating jobs, running dry-run jobs, approving policy decisions, applying approved entries, rolling back applied jobs, and deleting job history.

It does not auto-apply generated plans. Root changes, apply, job approval, rollback, and job deletion require explicit confirmation.

The server starts with an initial target root, and the UI can switch to another local directory by explicit path. Browser filesystem browsing is not implemented; the user enters the path manually. Every scan, plan, job, apply, and rollback operation is still resolved against the active root.

Deleting jobs removes only `.thelibrarian/jobs/<job_id>/` artifacts for the active root. It does not delete user files or rollback manifests written outside the job directory.
