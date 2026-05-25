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

    if normalized == "remote-compatible":
        return _diagnose_remote(
            active_context,
            required=required,
            provider_label="remote-compatible",
            default_endpoint="",
            default_model="",
            default_api_key_env="THELIBRARIAN_REMOTE_API_KEY",
            endpoint_env="THELIBRARIAN_REMOTE_ENDPOINT",
            model_env="THELIBRARIAN_REMOTE_MODEL",
            api_key_env_env="THELIBRARIAN_REMOTE_API_KEY_ENV",
            timeout_env="THELIBRARIAN_REMOTE_TIMEOUT_SECONDS",
        )

    if normalized == "antonio-managed":
        return _diagnose_remote(
            active_context,
            required=required,
            provider_label="antonio-managed",
            default_endpoint="https://api.thelibrarian.example/v1",
            default_model="managed-classifier",
            default_api_key_env="THELIBRARIAN_MANAGED_API_KEY",
            endpoint_env="THELIBRARIAN_MANAGED_ENDPOINT",
            model_env="THELIBRARIAN_MANAGED_MODEL",
            api_key_env_env="THELIBRARIAN_MANAGED_API_KEY_ENV",
            timeout_env="THELIBRARIAN_MANAGED_TIMEOUT_SECONDS",
        )

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


def _diagnose_remote(
    context: ProviderContext,
    *,
    required: bool,
    provider_label: str,
    default_endpoint: str,
    default_model: str,
    default_api_key_env: str,
    endpoint_env: str,
    model_env: str,
    api_key_env_env: str,
    timeout_env: str,
) -> list[DiagnosticCheck]:
    endpoint = context.endpoint or os.getenv(endpoint_env, default_endpoint)
    model = context.model or os.getenv(model_env, default_model)
    api_key_env = os.getenv(api_key_env_env) or default_api_key_env
    api_key = os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY")
    timeout = os.getenv(timeout_env, "20")
    checks = [
        DiagnosticCheck("provider", "ok", f"{provider_label} provider is available."),
        DiagnosticCheck("privacy", "ok", "metadata-only payload is enforced; file contents and absolute paths are not sent."),
    ]

    checks.append(
        DiagnosticCheck("endpoint", "ok" if endpoint else _failure_status(required), endpoint or f"{endpoint_env} is not set.")
    )
    checks.append(DiagnosticCheck("model", "ok" if model else _failure_status(required), model or f"{model_env} is not set."))
    checks.append(DiagnosticCheck("api_key_env", "ok", api_key_env))
    checks.append(
        DiagnosticCheck(
            "api_key",
            "ok" if api_key else _failure_status(required),
            "API key is present." if api_key else f"{api_key_env} is not set.",
        )
    )
    try:
        seconds = int(timeout)
        timeout_status = "ok" if seconds > 0 else _failure_status(required)
    except ValueError:
        timeout_status = _failure_status(required)
    checks.append(DiagnosticCheck("timeout", timeout_status, f"{timeout} second(s)"))
    checks.append(DiagnosticCheck("reachability", "warning", "Remote reachability is not checked by doctor to avoid mandatory cloud calls."))
    return checks
