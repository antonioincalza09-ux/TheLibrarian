# Remote Providers

TheLibrarian can use remote AI classification without requiring Ollama or local model installation on the client PC.

## Providers

- `deterministic`: built-in fallback, always available.
- `ollama`: optional local offline endpoint.
- `openai-compatible`: Chat Completions compatible endpoint using `OPENAI_API_KEY`.
- `remote-compatible`: generic metadata-only classification endpoint.
- `antonio-managed`: stub for a future managed TheLibrarian service.

## Remote-Compatible Config

```toml
[provider]
name = "remote-compatible"
endpoint = "https://example.com/v1"
model = "classifier-model"
api_key_env = "THELIBRARIAN_REMOTE_API_KEY"
timeout_seconds = 20
```

Supported environment variables:

```text
THELIBRARIAN_PROVIDER=remote-compatible
THELIBRARIAN_REMOTE_ENDPOINT=https://example.com/v1
THELIBRARIAN_REMOTE_MODEL=classifier-model
THELIBRARIAN_REMOTE_API_KEY=...
THELIBRARIAN_REMOTE_API_KEY_ENV=THELIBRARIAN_REMOTE_API_KEY
THELIBRARIAN_REMOTE_TIMEOUT_SECONDS=20
```

`OPENAI_API_KEY` is accepted as a compatibility fallback only when the configured remote key variable is absent.

## Metadata-Only Payload

Remote providers receive only relative metadata:

```json
{
  "task": "classify_file_metadata",
  "categories": ["Documents", "Media", "Code", "Archives", "Data", "Apps", "Review", "Skills"],
  "files": [
    {
      "source": "relative/path.pdf",
      "name": "path.pdf",
      "extension": ".pdf",
      "size_bytes": 12345,
      "modified_at": "2026-05-25T00:00:00+00:00",
      "parent": "relative"
    }
  ]
}
```

The payload never includes file contents, previews, hashes, absolute paths, local root paths, usernames, API keys, or secrets.

## Fallback

Remote output is not trusted. The planner validates source, category, confidence, and reason. Malformed responses fall back to deterministic classification and add a warning instead of crashing the normal workflow.

## Diagnostics

```powershell
thelibrarian providers doctor --provider remote-compatible --format json
thelibrarian providers doctor --provider antonio-managed --format json
```

Remote diagnostics check endpoint, model, API-key environment name, API-key presence, timeout, and metadata-only posture. They do not require a live cloud call.
