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
