from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.models import Inventory
from src.planner import build_plan
from src.providers import ProviderContext
from src.providers.deterministic import DeterministicProvider
from src.providers.openai_compatible import OpenAICompatibleProvider
from src.providers.types import ClassificationProvider, ClassificationResult, ProviderError
from src.scanner import scan_directory


class BrokenProvider(ClassificationProvider):
    name = "broken"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        raise ProviderError("offline")


class MalformedProvider(ClassificationProvider):
    name = "malformed"

    def classify(self, inventory: Inventory, context: ProviderContext) -> list[ClassificationResult]:
        return [
            ClassificationResult(
                source="../escape.txt",
                category="Documents",
                reason="unsafe",
                confidence=1.0,
            )
        ]


class ProviderTests(unittest.TestCase):
    def test_deterministic_provider_matches_planner_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            plan = build_plan(inventory, provider=DeterministicProvider(), context=ProviderContext())

            self.assertEqual(plan.entries[0].destination, "Documents/Reports/report.pdf")
            self.assertEqual(plan.provider, "deterministic")

    def test_provider_failure_falls_back_to_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            plan = build_plan(inventory, provider=BrokenProvider(), context=ProviderContext())

            self.assertEqual(plan.entries[0].destination, "Documents/Reports/report.pdf")
            self.assertIn("deterministic fallback", plan.warnings[0])

    def test_malformed_provider_response_routes_to_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "unknown.weird").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            plan = build_plan(inventory, provider=MalformedProvider(), context=ProviderContext())

            self.assertEqual(plan.entries[0].destination, "Review/unknown.weird")
            self.assertIn("Invalid provider classification", plan.warnings[0])

    def test_openai_compatible_provider_sends_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "secret.txt").write_text("this content must not be sent", encoding="utf-8")
            inventory = scan_directory(root)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                with mock.patch("src.providers.openai_compatible.post_json") as post_json:
                    post_json.return_value = {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"files":[{"source":"secret.txt","category":"Documents",'
                                        '"reason":"metadata","confidence":0.9}]}'
                                    )
                                }
                            }
                        ]
                    }
                    provider = OpenAICompatibleProvider()
                    provider.classify(inventory, ProviderContext(model="test", endpoint="http://example.test"))

            payload = post_json.call_args.args[1]
            sent_text = str(payload)
            self.assertIn("secret.txt", sent_text)
            self.assertNotIn("this content must not be sent", sent_text)


if __name__ == "__main__":
    unittest.main()
