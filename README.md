# TheLibrarian

TheLibrarian is a local agent project for safely organizing files inside an assigned directory according to usage logic, convenience, and traceable operations.

## Goal

Build a local agent that can scan a target directory, classify files, propose an organization plan, and optionally apply that plan with a reversible manifest.

## Quickstart

Install for local development:

```powershell
python -m pip install -e .
```

Run a safe dry-run from the repository:

```powershell
cd C:\Users\PC\Documents\TheLibrarian
python -m src.cli run "C:\path\to\target"
```

After installation, use the console command:

```powershell
thelibrarian run "C:\path\to\target"
```

The default mode is always dry-run. The tool scans files, produces an inventory, builds a plan, writes a report under `.thelibrarian/reports/`, and does not move files unless an explicit saved plan is applied with confirmation.

## Dashboard Workflow

Start the local dashboard against the directory you want to organize:

```powershell
cd C:\Users\PC\Documents\TheLibrarian
python -m src.cli serve "C:\path\to\target" --host 127.0.0.1 --port 8765
```

Open the browser at:

```text
http://127.0.0.1:8765
```

Recommended dashboard flow:

1. Check `Target Root` in the sidebar. You can paste a different directory and press `Set Directory`.
2. Press `Run Dry-Run Job` to scan, plan, evaluate policy, and write job artifacts without moving files.
3. Review `Plan`, `Review`, `Warnings`, `Policy`, and `Events`.
4. Filter or search `Plan` and `Review` when the plan is large. Use `Download JSON` for a browser export or `Save Plan` to write the current plan under `.thelibrarian/plans/`.
5. Use `Approve` only when you want to manually approve entries that require review.
6. Use `Apply` only when the selected job looks correct. Apply uses confirmed, policy-approved job entries and writes a rollback manifest.
7. Use `Rollback` to reverse an applied job when its manifest is available.
8. Use `Delete Job` or `Delete All Jobs` to remove dashboard job history for the current root. This deletes only `.thelibrarian/jobs/...` artifacts, not user files.

The dashboard never applies a freshly generated plan automatically. Apply, approval, rollback, root changes, and job deletion all require explicit confirmation.

## CLI Basics

```powershell
thelibrarian scan "C:\path\to\target" --output inventory.json
thelibrarian plan "C:\path\to\target" --provider deterministic --output plan.json
thelibrarian apply "C:\path\to\target" --plan plan.json --confirm
thelibrarian rollback "C:\path\to\target" --manifest rollback.json --confirm
thelibrarian providers list
thelibrarian providers doctor --provider ollama
thelibrarian packs list
thelibrarian packs show studio_legale
thelibrarian job run "C:\path\to\target" --pack studio_legale --provider deterministic
thelibrarian job run "C:\path\to\target" --policy-pack supervised_documents
thelibrarian managed start "C:\path\to\target" --client "Acme SRL" --operator "Antonio" --pack studio_legale
thelibrarian doctor "C:\path\to\target"
thelibrarian serve "C:\path\to\target" --host 127.0.0.1 --port 8765
thelibrarian job run "C:\path\to\target" --policy supervised_autonomy
thelibrarian policy-packs list
thelibrarian cleanup preview "C:\path\to\target" --policy-pack supervised_documents
```

See `docs/cli.md` for the full command reference.

## Safe Workflow

1. Run `thelibrarian doctor C:\path\to\target`.
2. Generate a plan with `thelibrarian plan C:\path\to\target --output C:\path\to\target\.thelibrarian\plans\plan.json`.
3. Review the plan JSON or the local web preview.
4. Apply only with `thelibrarian apply C:\path\to\target --plan C:\path\to\target\.thelibrarian\plans\plan.json --confirm`.
5. Roll back with the manifest written under `.thelibrarian/manifests/` if needed.

## Core Safety Rules

- Never delete files.
- Never edit file contents unless explicitly requested.
- Always support dry-run mode.
- Never move files outside the assigned root directory.
- Generate a human-readable plan before applying changes.
- Write a manifest for every applied operation.
- Put ambiguous files in `Review/` instead of guessing aggressively.
- Online model providers receive file metadata only, never file contents.

## Providers

The deterministic provider is always available. Optional providers can be configured for local Ollama, OpenAI-compatible APIs, generic remote-compatible APIs, or the future `antonio-managed` service stub. The deterministic rules remain the fallback.

Use `thelibrarian providers doctor --provider PROVIDER` for provider-specific checks. Ollama diagnostics probe `/api/tags`; OpenAI-compatible diagnostics check `OPENAI_API_KEY` and probe `/models`; remote diagnostics validate endpoint, model, API-key environment name, timeout, and metadata-only posture without requiring a cloud call.

## Policy Packs And Managed Cleanup

Policy packs live in `data/policy_packs/` as JSON. They define vertical templates, recommended policy mode, KPI targets, and managed-service recommendations without hardcoding industries in Python.

```powershell
thelibrarian packs list
thelibrarian packs recommend --industry healthcare
thelibrarian packs export studio_legale --output studio_legale.json
thelibrarian packs validate studio_legale.json
```

Managed cleanup creates a dry-run job, saves `policy_pack.json`, calculates KPI, and writes a client-readable report under `.thelibrarian/managed/<session_id>/`. It does not move files.

```powershell
thelibrarian managed start "C:\path\to\target" --client "Acme SRL" --operator "Antonio" --pack studio_legale
thelibrarian managed list "C:\path\to\target"
thelibrarian managed show SESSION_ID --root "C:\path\to\target"
```

## Suggested First Milestone

1. Scan a directory and produce an inventory.
2. Classify files into broad categories.
3. Generate a dry-run organization plan.
4. Apply the plan only after explicit confirmation.
5. Produce a rollback manifest.

## Organization Categories

- `Documents/`
- `Media/`
- `Code/`
- `Archives/`
- `Data/`
- `Apps/`
- `Review/`
- `Skills/` for contextual skill workspaces.

`Documents/` is further split into contextual subfolders such as `Reports`, `Financial`, `Testing`, `Agents`, `Workflows`, `Knowledge`, `Protocols`, `Manuals`, `Notes`, `Presentations`, `Text`, and `General`.

Skill workspaces are grouped by usage and function, for example:

```text
Skills/<skill>/Definition/SKILL.md
Skills/<skill>/Documentation/*.md
Skills/<skill>/Source/*.py
Skills/<skill>/References/*.md
Skills/<skill>/Metadata/*.json
```

## Policy Packs and Managed Cleanup

The project includes local foundations for future policy templates and managed cleanup workflows. These are file-based and do not call cloud services.

- `policy-packs list|show|export` inspects built-in packs and optional local packs under `.thelibrarian/policy-packs/`.
- `cleanup preview ROOT` creates a dry-run managed cleanup session under `.thelibrarian/managed-cleanups/<session_id>/`.
- Managed cleanup sessions write inventory, plan, policy decision, KPI, policy pack, and report artifacts without moving files.
