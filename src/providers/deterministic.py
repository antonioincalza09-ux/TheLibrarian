from __future__ import annotations

from src.models import Inventory
from src.planner.service import classify_file
from src.providers.types import ClassificationProvider, ClassificationResult, ProviderContext


class DeterministicProvider(ClassificationProvider):
    name = "deterministic"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        results: list[ClassificationResult] = []
        for file_record in inventory.files:
            category, confidence, reason = classify_file(file_record.extension, file_record.name)
            results.append(
                ClassificationResult(
                    source=file_record.relative_path,
                    category=category,
                    reason=reason,
                    confidence=confidence,
                )
            )
        return results
