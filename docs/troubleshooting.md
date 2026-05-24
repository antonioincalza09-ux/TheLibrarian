# Troubleshooting

## Provider Fails

The planner records a warning and falls back to deterministic classification. Check `thelibrarian providers doctor --provider PROVIDER`.

## OpenAI-Compatible Provider Has No Key

Set `OPENAI_API_KEY` in the environment before running the command.

## Ollama Is Unavailable

Start Ollama locally, check the configured endpoint, or use `--provider deterministic`.

## Apply Refuses to Run

Apply requires a saved plan and `--confirm`.

```bash
thelibrarian apply C:\target --plan plan.json --confirm
```

## Collision Warnings

TheLibrarian never overwrites destination files. Conflicted entries are skipped and left in place.

## Root Mismatch

Plans and manifests are tied to the root used when they were created. Re-run `plan` if the target root changed.
