# Managed Cleanup

Managed Cleanup is a local, file-based foundation for future managed cleanup service workflows. It is not a beta service and does not call external infrastructure.

## Preview Command

```bash
thelibrarian cleanup preview C:\target --policy-pack supervised_documents
```

The command scans the root, builds a plan, evaluates the selected Policy Pack, computes KPI, and writes a human-readable report. It is dry-run only and does not move files.

## Artifacts

Each session is written under:

```text
.thelibrarian/managed-cleanups/<session_id>/
```

Artifacts:

- `cleanup_session.json`: session state and artifact paths.
- `inventory.json`: metadata-only scan result.
- `plan.json`: generated organization plan.
- `policy_decision.json`: policy gate output.
- `kpi.json`: operational KPI snapshot.
- `policy_pack.json`: policy pack used for the run.
- `report.txt`: operator-readable summary.

## KPI

Current KPI include scanned files, total bytes, planned entries, review entries, conflicts, auto-approved entries, entries requiring approval, blocked entries, and rates for auto approval, review, and blocking.

## Limits

- No cloud service.
- No telemetry.
- No authentication or billing.
- No background daemon.
- No apply behavior. Use existing job/apply workflows when explicit confirmed apply is needed.
