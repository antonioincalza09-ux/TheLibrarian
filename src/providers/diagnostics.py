from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from src.providers.http_json import get_json
from src.providers.types import ProviderContext, ProviderError


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def diagnose_provider(
    provider_name: str,
    context: ProviderContext | None = None,
    *,
    required: bool = True,
) -> list[DiagnosticCheck]:
    normalized = provider_name.strip().lower().replace("_", "-")
    active_context = context or ProviderContext()

    if normalized == "deterministic":
        return [
            DiagnosticCheck("provider", "ok", "deterministic provider is built in."),
            DiagnosticCheck("privacy", "ok", "metadata-only mode is enforced before planning."),
        ]

    if normalized == "ollama":
        return _diagnose_ollama(active_context, required=required)

    if normalized == "openai-compatible":
        return _diagnose_openai_compatible(active_context, required=required)

    return [DiagnosticCheck("provider", "error", f"unknown provider: {provider_name}")]


def _failure_status(required: bool) -> str:
    return "error" if required else "warning"


def _diagnose_ollama(context: ProviderContext, *, required: bool) -> list[DiagnosticCheck]:
    endpoint = context.endpoint or "http://127.0.0.1:11434"
    checks = [
        DiagnosticCheck("provider", "ok", "ollama provider is configured."),
        DiagnosticCheck("endpoint", "ok", endpoint),
    ]

    try:
        payload = get_json(f"{endpoint.rstrip('/')}/api/tags", timeout=5)
    except ProviderError as exc:
        checks.append(
            DiagnosticCheck(
                "ollama_reachable",
                _failure_status(required),
                f"Ollama is not reachable at {endpoint}: {exc}",
            )
        )
        return checks

    models = payload.get("models")
    if isinstance(models, list):
        checks.append(DiagnosticCheck("ollama_reachable", "ok", f"Ollama is reachable; {len(models)} model(s) listed."))
    else:
        checks.append(
            DiagnosticCheck(
                "ollama_reachable",
                _failure_status(required),
                "Ollama responded, but /api/tags did not return a models list.",
            )
        )
    return checks


def _diagnose_openai_compatible(context: ProviderContext, *, required: bool) -> list[DiagnosticCheck]:
    endpoint = context.endpoint or "https://api.openai.com/v1"
    api_key = os.getenv("OPENAI_API_KEY")
    checks = [
        DiagnosticCheck("provider", "ok", "openai-compatible provider is configured."),
        DiagnosticCheck("endpoint", "ok", endpoint),
    ]

    if not api_key:
        checks.append(
            DiagnosticCheck(
                "openai_api_key",
                _failure_status(required),
                "OPENAI_API_KEY is not set.",
            )
        )
        return checks

    checks.append(DiagnosticCheck("openai_api_key", "ok", "OPENAI_API_KEY is present."))

    try:
        payload = get_json(
            f"{endpoint.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
    except ProviderError as exc:
        checks.append(
            DiagnosticCheck(
                "openai_compatible_reachable",
                _failure_status(required),
                f"OpenAI-compatible endpoint is not reachable at {endpoint}: {exc}",
            )
        )
        return checks

    models = payload.get("data")
    if isinstance(models, list):
        checks.append(
            DiagnosticCheck(
                "openai_compatible_reachable",
                "ok",
                f"OpenAI-compatible endpoint is reachable; {len(models)} model(s) listed.",
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                "openai_compatible_reachable",
                _failure_status(required),
                "OpenAI-compatible endpoint responded, but /models did not return a data list.",
            )
        )
    return checks
