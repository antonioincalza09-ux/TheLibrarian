# Examples

## Dry-Run a Downloads Folder

```bash
thelibrarian run C:\Users\PC\Downloads
```

This prints a report and writes a copy under `.thelibrarian/reports/`.

## Generate a Plan with Ollama

```bash
thelibrarian plan C:\work\messy --provider ollama --model llama3.1 --output C:\work\messy\.thelibrarian\plan.json
```

If the provider is unavailable, deterministic fallback is used.

## Generate Metadata-Only Cloud Classifications

```bash
set OPENAI_API_KEY=...
thelibrarian plan C:\work\messy --provider openai-compatible --model gpt-4.1-mini --output plan.json
```

Only metadata is sent to the model.

## Open the Local Preview

```bash
thelibrarian serve C:\work\messy
```

Open `http://127.0.0.1:8765`.
