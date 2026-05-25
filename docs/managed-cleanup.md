# Managed Cleanup

Managed Cleanup is the filesystem-based foundation for offering TheLibrarian as an assisted cleanup service. It remains local and dry-run first.

## Managed Session Workflow

```powershell
thelibrarian managed start ROOT --client "Acme SRL" --operator "Antonio" --pack studio_legale
thelibrarian managed list ROOT
thelibrarian managed show SESSION_ID --root ROOT
thelibrarian managed report SESSION_ID --root ROOT
```

`managed start` creates a dry-run job, attaches a policy pack, calculates KPI, and writes reports. It never moves user files.

Managed sessions are stored under:

```text
.thelibrarian/managed/<session_id>/
  session.json
  report.json
  report.md
```

The related job remains under `.thelibrarian/jobs/<job_id>/` and contains inventory, plan, policy decision, policy pack, report, and events.

## Cleanup Preview Compatibility

The earlier local cleanup preview workflow remains available:

```powershell
thelibrarian cleanup preview ROOT --policy-pack supervised_documents
thelibrarian cleanup list ROOT
thelibrarian cleanup status SESSION_ID --root ROOT
thelibrarian cleanup report SESSION_ID --root ROOT
```

Cleanup preview sessions are written under:

```text
.thelibrarian/managed-cleanups/<session_id>/
```

They include `cleanup_session.json`, `inventory.json`, `plan.json`, `policy_decision.json`, `kpi.json`, `policy_pack.json`, and `report.txt`.

## KPI

The managed KPI includes files scanned, bytes scanned, planned moves, auto-approved moves, manual review moves, blocked moves, conflicts, already-organized count, applied moves, verified moves, rollback availability, safety score, organization score, automation score, risk score, and estimated minutes saved.

Scores are deterministic and model-free. They are meant for operational triage and client reporting, not legal/compliance guarantees.

## Safety

- Managed sessions are dry-run only in this version.
- No file contents are modified.
- No file contents are sent to providers.
- Apply still uses the existing explicit confirmation and rollback manifest workflow.
- Session IDs are validated to block path traversal.
