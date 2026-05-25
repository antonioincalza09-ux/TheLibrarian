from __future__ import annotations

from src.models import Inventory
from src.providers.remote_client import build_metadata_payload, post_remote_classification, resolve_remote_settings
from src.providers.types import ClassificationProvider, ClassificationResult, ProviderContext, ProviderError


class RemoteCompatibleProvider(ClassificationProvider):
    name = "remote-compatible"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        settings = resolve_remote_settings(
            context,
            default_endpoint="",
            default_model="",
            default_api_key_env="THELIBRARIAN_REMOTE_API_KEY",
            endpoint_env="THELIBRARIAN_REMOTE_ENDPOINT",
            model_env="THELIBRARIAN_REMOTE_MODEL",
            api_key_env_env="THELIBRARIAN_REMOTE_API_KEY_ENV",
            timeout_env="THELIBRARIAN_REMOTE_TIMEOUT_SECONDS",
        )
        payload = build_metadata_payload(inventory)
        response = post_remote_classification(settings, payload)
        return _parse_remote_results(response)


class AntonioManagedProvider(ClassificationProvider):
    name = "antonio-managed"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        settings = resolve_remote_settings(
            context,
            default_endpoint="https://api.thelibrarian.example/v1",
            default_model="managed-classifier",
            default_api_key_env="THELIBRARIAN_MANAGED_API_KEY",
            endpoint_env="THELIBRARIAN_MANAGED_ENDPOINT",
            model_env="THELIBRARIAN_MANAGED_MODEL",
            api_key_env_env="THELIBRARIAN_MANAGED_API_KEY_ENV",
            timeout_env="THELIBRARIAN_MANAGED_TIMEOUT_SECONDS",
        )
        payload = build_metadata_payload(inventory)
        response = post_remote_classification(settings, payload)
        return _parse_remote_results(response)


def _parse_remote_results(payload: dict[str, object]) -> list[ClassificationResult]:
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ProviderError("Remote provider response did not include a results list.")
    results: list[ClassificationResult] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ProviderError("Remote provider result row was not an object.")
        try:
            results.append(
                ClassificationResult(
                    source=str(row["source"]),
                    category=str(row["category"]),
                    reason=str(row["reason"]),
                    confidence=float(row["confidence"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Remote provider returned a malformed classification row.") from exc
    return results
