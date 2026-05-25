# TheLibrarian Managed Cleanup Report

## Service Snapshot

- Client: Acme SRL
- Operator: Antonio
- Root: `C:\Clients\Acme\Shared`
- Session: `sample-session`
- Stage: completed
- Policy pack: Studio Legale (`studio_legale`)
- Industry: legal
- Report posture: dry-run only, no file movement

## Executive Summary

TheLibrarian analyzed 128 file(s), planned 84 reversible move(s), and identified 19 item(s) for human review. No files were moved during this managed cleanup session.

## Client Outcome

- Readiness: Ready for client review
- Risk posture: Medium
- Estimated time saved: 61.0 minute(s)
- Rollback status: available after confirmed apply

## KPI Snapshot

| Metric | Value |
| --- | ---: |
| Files scanned | 128 |
| Planned moves | 84 |
| Auto-approved moves | 65 |
| Manual review moves | 19 |
| Blocked moves | 0 |
| Safety score | 100/100 |
| Organization score | 72/100 |
| Automation score | 61/100 |
| Risk score | 24/100 |

## Review And Risk

- Items requiring human review: 19
- Blocked items: 0
- Destination conflicts: 3
- Files routed to Review: 11

Review items are expected in a safety-first workflow. They indicate that TheLibrarian avoided guessing where the confidence or risk profile was not strong enough.

## Recommended Actions

- **Initial Cleanup Audit** (normal): Review the current directory structure and generate a safe cleanup plan.
- **Guided Cleanup Session** (normal): Review risky files with the client before applying changes.
- **Monthly Directory Maintenance** (normal): Run recurring cleanup checks and resolve review items.

## Artifact Map

| Artifact | Path |
| --- | --- |
| job | `.thelibrarian/jobs/sample-job/job.json` |
| plan | `.thelibrarian/jobs/sample-job/plan.json` |
| policy | `.thelibrarian/jobs/sample-job/policy_decision.json` |
| report_md | `.thelibrarian/managed/sample-session/report.md` |
| report_html | `.thelibrarian/managed/sample-session/report.html` |

## Safety Appendix

- This managed workflow is dry-run only.
- No files were moved during this report run.
- No file contents were modified.
- No file contents were sent to providers.
- Provider output is treated as untrusted and validated before use.
- Apply still requires the existing explicit confirmation and rollback manifest workflow.
- Rollback artifacts are created only after a confirmed apply.

## Next Steps

Review the generated plan with the client, resolve review items, then decide whether to run a confirmed apply workflow.
