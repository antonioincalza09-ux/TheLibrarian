# Providers

Providers classify file metadata into the supported categories. They do not move files and they do not produce final paths. The planner owns destination generation and safety validation.

## Deterministic

`deterministic` is always available. It classifies by extension and filename signals, routes unknown or ambiguous files to `Review/`, and is the fallback for all provider failures.

## Ollama

`ollama` is an optional offline provider that calls a local Ollama server, defaulting to `http://127.0.0.1:11434` and model `llama3.1` when no config is supplied.

```bash
thelibrarian plan C:\target --provider ollama --model llama3.1
```

If Ollama is unavailable or returns malformed JSON, the planner uses deterministic fallback.

`thelibrarian providers doctor --provider ollama` checks the configured endpoint with `GET /api/tags`. It does not run a model generation.

## OpenAI-Compatible

`openai-compatible` calls a Chat Completions compatible endpoint. It requires `OPENAI_API_KEY`.

```bash
set OPENAI_API_KEY=...
thelibrarian plan C:\target --provider openai-compatible --endpoint https://api.openai.com/v1 --model gpt-4.1-mini
```

The provider receives metadata only: relative path, filename, extension, size, modified date, and parent folder. File contents are never sent.

`thelibrarian providers doctor --provider openai-compatible` verifies `OPENAI_API_KEY` and checks the endpoint with `GET /models`. It does not create chat completions.

## Remote-Compatible

`remote-compatible` calls a generic classification endpoint and is designed for client PCs that should not install local AI.

```bash
set THELIBRARIAN_PROVIDER=remote-compatible
set THELIBRARIAN_REMOTE_ENDPOINT=https://example.com/v1
set THELIBRARIAN_REMOTE_MODEL=classifier-model
set THELIBRARIAN_REMOTE_API_KEY=...
thelibrarian plan C:\target --provider remote-compatible
```

The payload is metadata-only and never includes file contents, absolute paths, local roots, usernames, hashes, or secrets. Malformed responses fall back to deterministic classification.

`thelibrarian providers doctor --provider remote-compatible --format json` checks endpoint, model, API-key environment name, key presence, timeout, and privacy posture without requiring a live cloud call.

## Antonio-Managed

`antonio-managed` is a stub for a future hosted managed-classifier service. It uses `THELIBRARIAN_MANAGED_API_KEY` by default and currently follows the same metadata-only/fallback behavior as `remote-compatible`.
