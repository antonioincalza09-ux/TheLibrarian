from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.models import DEFAULT_CATEGORY_DIRECTORIES, Inventory
from src.providers.http_json import post_json
from src.providers.types import ProviderContext, ProviderError


REMOTE_CATEGORIES = [*DEFAULT_CATEGORY_DIRECTORIES, "Skills"]


@dataclass(slots=True)
class RemoteProviderSettings:
    endpoint: str
    model: str
    api_key_env: str
    api_key: str
    timeout_seconds: int = 20


def build_metadata_payload(inventory: Inventory) -> dict[str, object]:
    return {
        "task": "classify_file_metadata",
        "categories": list(REMOTE_CATEGORIES),
        "files": [
            {
                "source": file_record.relative_path,
                "name": file_record.name,
                "extension": file_record.extension,
                "size_bytes": file_record.size_bytes,
                "modified_at": file_record.modified_at,
                "parent": file_record.parent,
            }
            for file_record in inventory.files
        ],
    }


def resolve_remote_settings(
    context: ProviderContext,
    *,
    default_endpoint: str,
    default_model: str,
    default_api_key_env: str,
    endpoint_env: str,
    model_env: str,
    api_key_env_env: str,
    timeout_env: str,
) -> RemoteProviderSettings:
    api_key_env = os.getenv(api_key_env_env) or default_api_key_env
    api_key = os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY") or ""
    timeout_text = os.getenv(timeout_env, "20")
    try:
        timeout_seconds = max(1, int(timeout_text))
    except ValueError:
        timeout_seconds = 20
    return RemoteProviderSettings(
        endpoint=context.endpoint or os.getenv(endpoint_env, default_endpoint),
        model=context.model or os.getenv(model_env, default_model),
        api_key_env=api_key_env,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )


def post_remote_classification(settings: RemoteProviderSettings, payload: dict[str, object]) -> dict[str, Any]:
    if not settings.endpoint:
        raise ProviderError("Remote endpoint is required.")
    if not settings.model:
        raise ProviderError("Remote model is required.")
    if not settings.api_key:
        raise ProviderError(f"{settings.api_key_env} is required for remote classification.")

    request_payload = dict(payload)
    request_payload["model"] = settings.model
    return post_json(
        f"{settings.endpoint.rstrip('/')}/classifications",
        request_payload,
        headers={"Authorization": f"Bearer {settings.api_key}"},
        timeout=settings.timeout_seconds,
    )
