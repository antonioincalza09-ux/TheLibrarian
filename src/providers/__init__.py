from src.providers.types import ClassificationProvider, ClassificationResult, ProviderContext, ProviderError


def available_providers() -> list[str]:
    from src.providers.registry import available_providers as _available_providers

    return _available_providers()


def get_provider(name: str) -> ClassificationProvider:
    from src.providers.registry import get_provider as _get_provider

    return _get_provider(name)


__all__ = [
    "ClassificationProvider",
    "ClassificationResult",
    "ProviderContext",
    "ProviderError",
    "available_providers",
    "get_provider",
]
