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
  report.html
```

The related job remains under `.thelibrarian/jobs/<job_id>/` and contains inventory, plan, policy decision, policy pack, report, and events.

## Client-Readable Report

`report.md` is the portable source report, `report.json` is the structured artifact, and `report.html` is the client-ready visual export for browser review or printing. Reports are intended to be shared with a client or internal stakeholder after operator review. They include:

- service snapshot with client, operator, pack, stage, and dry-run posture
- executive summary
- client outcome and readiness label
- KPI snapshot
- review and risk summary
- recommended actions from the selected policy pack
- artifact map
- safety appendix
- next steps

The HTML report uses only local static markup and CSS. It does not load remote assets, scripts, trackers, or cloud services.

The dashboard can preview the latest generated HTML report through a root-confined local endpoint:

```text
GET /api/managed/<session_id>/report-html
```

Example report files are available in:

```text
examples/managed-report-sample.md
examples/managed-report-sample.json
```

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
- HTML reports are generated as local files with no external assets.
- Apply still uses the existing explicit confirmation and rollback manifest workflow.
- Session IDs are validated to block path traversal.
