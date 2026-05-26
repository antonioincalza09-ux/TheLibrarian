# TheLibrarian

TheLibrarian is a privacy-first file organization copilot for professionals and small businesses.

It scans a local folder, builds an auditable organization plan, applies changes only after explicit confirmation, and keeps rollback artifacts for every applied move. The product direction is simple: help law firms, accountants, consultants, agencies, clinics, administrative offices, and small teams clean up messy file systems without giving up privacy, control, or reversibility.

## Why It Exists

Most file organization tools optimize for convenience first. TheLibrarian optimizes for trust first.

- Local-first by default: the assigned root stays on the user's machine.
- Privacy-first provider design: online providers receive metadata only, never file contents.
- Dry-run first: scanning, planning, jobs, dashboard previews, and managed sessions start without moving files.
- Reversible operations: apply requires confirmation and writes rollback manifests.
- Vertical workflows: policy packs describe professional folder templates, risk posture, KPI targets, and managed service recommendations.

## Current Status

TheLibrarian is an early safety-first Python product foundation, not a hosted SaaS release.

Implemented today:

- Installable CLI with `thelibrarian` entrypoint.
- Local dashboard served by the Python standard library.
- Deterministic, Ollama, OpenAI-compatible, remote-compatible, and `antonio-managed` provider adapters.
- Metadata-only remote provider posture.
- Filesystem-backed job engine under `.thelibrarian/jobs/`.
- Policy gate with `dry_run_only` and `supervised_autonomy`.
- JSON policy packs under `data/policy_packs/`, including vertical packs for professional use cases.
- Managed cleanup dry-run sessions under `.thelibrarian/managed/`.
- Client-readable managed reports in Markdown, JSON, and local HTML.
- Reports, KPI, audit artifacts, saved plans, manifests, and rollback workflow.

Future architecture is documented for licensing, billing, marketplace, hosted provider, and team administration, but those systems are not implemented yet.

## Safety Guarantees

TheLibrarian's core invariants are product features, not implementation details.

- Never delete user files.
- Never edit file contents.
- Never move files outside the assigned root.
- Never overwrite collisions.
- Ambiguous or low-confidence files go to `Review/`.
- Apply requires a saved plan, policy approval, and explicit confirmation.
- Rollback requires a manifest and explicit confirmation.
- Provider output is untrusted and validated before use.
- Online providers must operate metadata-only.

See [docs/security-privacy.md](docs/security-privacy.md) and [docs/safety-model.md](docs/safety-model.md).

## Quickstart

Install for local development:

```powershell
python -m pip install -e .
```

Run a safe dry-run:

```powershell
python -m src.cli run "C:\path\to\target"
```

After installation, use:

```powershell
thelibrarian run "C:\path\to\target"
```

The default mode is always dry-run. The command scans files, builds a plan, writes a report under `.thelibrarian/reports/`, and does not move files.

## Demo Workflow

1. Diagnose setup and provider readiness:

```powershell
thelibrarian doctor "C:\path\to\target"
```

2. Preview the folder in the local dashboard:

```powershell
thelibrarian serve "C:\path\to\target" --host 127.0.0.1 --port 8765
```

3. Run a vertical dry-run job:

```powershell
thelibrarian job run "C:\path\to\target" --pack studio_legale --provider deterministic
```

4. Start a managed cleanup session for a client-facing report:

```powershell
thelibrarian managed start "C:\path\to\target" --client "Acme SRL" --operator "Antonio" --pack studio_legale
```

5. Apply only after review and explicit confirmation:

```powershell
thelibrarian apply "C:\path\to\target" --plan "C:\path\to\target\.thelibrarian\plans\plan.json" --confirm
```

## Product Modes

These are product packaging directions. They are not billing gates in the current codebase.

| Mode | Current/Future | Intended Value |
| --- | --- | --- |
| Free Local | Current foundation | CLI, local dashboard, deterministic provider, dry-run planning, saved plans, apply/rollback with confirmation. |
| Pro Local | Future packaging | Better local UI, advanced policy packs, report export, richer batch jobs, professional presets. |
| Managed Service | Current foundation, not beta | Operator-led dry-run sessions, KPI, client-readable reports, vertical pack recommendations, audit artifacts. |
| Team/Enterprise | Future architecture | Shared templates, admin controls, policy governance, SSO, licensing, billing, support, optional metadata sync. |

## Vertical Policy Packs

Policy packs live in `data/policy_packs/` as JSON. They describe professional templates without hardcoding industries in Python.

In pack-aware jobs and dashboard previews, matching folder templates can refine destinations conservatively. For example, `studio_legale` can route `contract.pdf` to `Documents/Contracts/contract.pdf`, while ambiguous files still go to a review template such as `Review/NeedsHumanReview/`.

Current packs include legal, accounting, healthcare, agencies, real estate, education, logistics, manufacturing, hospitality, creative studios, and general office workflows.

```powershell
thelibrarian packs list
thelibrarian packs recommend --industry healthcare
thelibrarian packs show studio_legale
thelibrarian packs export studio_legale --output studio_legale.json
thelibrarian packs validate studio_legale.json
```

Policy packs can attach to jobs and managed sessions:

```powershell
thelibrarian job run "C:\path\to\target" --pack commercialista
thelibrarian managed start "C:\path\to\target" --client "Client Name" --operator "Operator Name" --pack commercialista
```

## Managed Cleanup

Managed cleanup is the foundation for a sellable service workflow. It creates a dry-run job, attaches a policy pack, computes KPI, and writes client-readable Markdown, JSON, and local HTML reports under `.thelibrarian/managed/<session_id>/`.

It does not move files. Apply remains a separate confirmed workflow.

```powershell
thelibrarian managed list "C:\path\to\target"
thelibrarian managed show SESSION_ID --root "C:\path\to\target"
thelibrarian managed report SESSION_ID --root "C:\path\to\target"
```

## Core Commands

```powershell
thelibrarian scan "C:\path\to\target" --output inventory.json
thelibrarian plan "C:\path\to\target" --provider deterministic --output plan.json
thelibrarian run "C:\path\to\target"
thelibrarian apply "C:\path\to\target" --plan plan.json --confirm
thelibrarian rollback "C:\path\to\target" --manifest rollback.json --confirm
thelibrarian providers list
thelibrarian providers doctor --provider remote-compatible
thelibrarian packs list
thelibrarian managed start "C:\path\to\target" --client "Acme SRL" --operator "Antonio" --pack studio_legale
thelibrarian serve "C:\path\to\target"
```

See [docs/cli.md](docs/cli.md) for the full command reference.

## Architecture And Product Docs

- [docs/architecture.md](docs/architecture.md): system architecture and boundaries.
- [docs/security-privacy.md](docs/security-privacy.md): buyer-readable safety and privacy posture.
- [docs/product/prd.md](docs/product/prd.md): product requirements and target personas.
- [docs/product/commercialization.md](docs/product/commercialization.md): packaging, upsell path, and go-to-market.
- [docs/product/roadmap.md](docs/product/roadmap.md): phased roadmap.
- [docs/product/ui-polish.md](docs/product/ui-polish.md): dashboard and report visual direction.
- [docs/policy-packs.md](docs/policy-packs.md): vertical policy pack model.
- [docs/managed-cleanup.md](docs/managed-cleanup.md): managed session workflow.
- [examples/managed-report-sample.md](examples/managed-report-sample.md): sample client-facing report.

## Current Limits

- No real billing.
- No authentication.
- No hosted SaaS dashboard.
- No remote marketplace.
- No database.
- No background daemon.
- No guarantee that every file is classified correctly; uncertain items are deliberately routed to review.

Those limits are intentional for the current phase. The product direction is professional and monetizable, but the implementation remains local-first, auditable, reversible, and conservative.
