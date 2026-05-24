from __future__ import annotations

import json

from src.models import Inventory
from src.providers.http_json import post_json
from src.providers.types import ClassificationProvider, ClassificationResult, ProviderContext, ProviderError


class OllamaProvider(ClassificationProvider):
    name = "ollama"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        endpoint = context.endpoint or "http://127.0.0.1:11434"
        model = context.model or "llama3.1"
        payload = {
            "model": model,
            "stream": False,
            "prompt": _prompt(inventory),
            "format": "json",
        }
        response = post_json(f"{endpoint.rstrip('/')}/api/generate", payload)
        text = response.get("response")
        if not isinstance(text, str):
            raise ProviderError("Ollama response did not include a JSON response string.")
        return _parse_results(text)


def _prompt(inventory: Inventory) -> str:
    files = [item.to_dict() for item in inventory.files]
    return (
        "Classify these file metadata records into one category among "
        "Documents, Media, Code, Archives, Data, Apps, Review. "
        "Return JSON only: {\"files\":[{\"source\":\"...\",\"category\":\"...\","
        "\"reason\":\"...\",\"confidence\":0.0}]}. Do not infer from file contents. "
        f"Files: {json.dumps(files)}"
    )


def _parse_results(text: str) -> list[ClassificationResult]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError("Ollama model returned invalid JSON.") from exc

    rows = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ProviderError("Ollama model returned no files list.")

    return [
        ClassificationResult(
            source=str(row["source"]),
            category=str(row["category"]),
            reason=str(row["reason"]),
            confidence=float(row["confidence"]),
        )
        for row in rows
        if isinstance(row, dict)
    ]
