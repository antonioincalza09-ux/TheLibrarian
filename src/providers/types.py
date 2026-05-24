from __future__ import annotations

from dataclasses import dataclass

from src.models import Inventory


@dataclass(slots=True)
class ProviderContext:
    model: str = ""
    endpoint: str = ""
    privacy_mode: str = "metadata-only"


@dataclass(slots=True)
class ClassificationResult:
    source: str
    category: str
    reason: str
    confidence: float


class ProviderError(RuntimeError):
    pass


class ClassificationProvider:
    name = "base"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        raise NotImplementedError
