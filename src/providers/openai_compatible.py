from __future__ import annotations

import json
import os

from src.models import Inventory
from src.providers.http_json import post_json
from src.providers.types import ClassificationProvider, ClassificationResult, ProviderContext, ProviderError


class OpenAICompatibleProvider(ClassificationProvider):
    name = "openai-compatible"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is required for the openai-compatible provider.")

        endpoint = context.endpoint or "https://api.openai.com/v1"
        model = context.model or "gpt-4.1-mini"
        response = post_json(
            f"{endpoint.rstrip('/')}/chat/completions",
            {
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Classify file metadata into Documents, Media, Code, Archives, "
                            "Data, Apps, or Review. Return JSON only with files array. "
                            "Use metadata only and never request file contents."
                        ),
                    },
                    {"role": "user", "content": json.dumps([item.to_dict() for item in inventory.files])},
                ],
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        try:
            content = response["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI-compatible response had no message content.") from exc
        if not isinstance(content, str):
            raise ProviderError("OpenAI-compatible response content was not text.")
        return _parse_results(content)


def _parse_results(text: str) -> list[ClassificationResult]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError("OpenAI-compatible model returned invalid JSON.") from exc

    rows = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ProviderError("OpenAI-compatible model returned no files list.")

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
