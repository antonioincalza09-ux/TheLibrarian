from __future__ import annotations

from src.providers.deterministic import DeterministicProvider
from src.providers.ollama import OllamaProvider
from src.providers.openai_compatible import OpenAICompatibleProvider
from src.providers.types import ClassificationProvider


PROVIDER_FACTORIES = {
    "deterministic": DeterministicProvider,
    "ollama": OllamaProvider,
    "openai-compatible": OpenAICompatibleProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def available_providers() -> list[str]:
    return ["deterministic", "ollama", "openai-compatible"]


def get_provider(name: str) -> ClassificationProvider:
    normalized = name.strip().lower()
    if normalized not in PROVIDER_FACTORIES:
        raise ValueError(f"Unknown provider: {name}")
    return PROVIDER_FACTORIES[normalized]()
