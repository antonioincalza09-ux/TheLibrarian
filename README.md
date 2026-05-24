# TheLibrarian

TheLibrarian is a local agent project for safely organizing files inside an assigned directory according to usage logic, convenience, and traceable operations.

## Quickstart

Run from the repository:

```bash
python -m src.cli run C:\path\to\target
```

After installation, use the console command:

```bash
thelibrarian run C:\path\to\target
```

The default mode is always dry-run. The tool scans files, produces an inventory, builds a plan, writes a report under `.thelibrarian/reports/`, and does not move files unless an explicit saved plan is applied with confirmation.

## CLI Basics

```bash
thelibrarian scan C:\path\to\target --output inventory.json
thelibrarian plan C:\path\to\target --provider deterministic --output plan.json
thelibrarian apply C:\path\to\target --plan plan.json --confirm
thelibrarian rollback C:\path\to\target --manifest rollback.json --confirm
thelibrarian providers list
thelibrarian serve C:\path\to\target --host 127.0.0.1 --port 8765
```

See `docs/cli.md` for the full command reference.

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

The deterministic provider is always available. Optional providers can be configured for local Ollama or OpenAI-compatible APIs, while the deterministic rules remain the fallback.

## Initial Categories

- `Documents/`
- `Media/`
- `Code/`
- `Archives/`
- `Data/`
- `Apps/`
- `Review/`
