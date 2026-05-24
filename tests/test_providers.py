from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.models import Inventory
from src.planner import build_plan
from src.providers import ProviderContext
from src.providers.diagnostics import diagnose_provider
from src.providers.deterministic import DeterministicProvider
from src.providers.ollama import OllamaProvider
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

    def test_ollama_provider_parses_mocked_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            with mock.patch("src.providers.ollama.post_json") as post_json:
                post_json.return_value = {
                    "response": (
                        '{"files":[{"source":"report.pdf","category":"Documents",'
                        '"reason":"metadata","confidence":0.88}]}'
                    )
                }
                results = OllamaProvider().classify(
                    inventory,
                    ProviderContext(model="test-model", endpoint="http://ollama.test"),
                )

        self.assertEqual(results[0].source, "report.pdf")
        self.assertEqual(results[0].category, "Documents")
        self.assertEqual(post_json.call_args.args[0], "http://ollama.test/api/generate")

    def test_ollama_provider_unreachable_raises_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            with mock.patch("src.providers.ollama.post_json", side_effect=ProviderError("offline")):
                with self.assertRaises(ProviderError):
                    OllamaProvider().classify(inventory, ProviderContext(endpoint="http://ollama.test"))

    def test_ollama_diagnostics_uses_reachability_probe(self) -> None:
        with mock.patch("src.providers.diagnostics.get_json", return_value={"models": [{"name": "llama3.1"}]}):
            checks = diagnose_provider("ollama", ProviderContext(endpoint="http://ollama.test"), required=True)

        reachable = next(check for check in checks if check.name == "ollama_reachable")
        self.assertEqual(reachable.status, "ok")

    def test_openai_compatible_malformed_response_raises_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                with mock.patch("src.providers.openai_compatible.post_json", return_value={"choices": []}):
                    with self.assertRaises(ProviderError):
                        OpenAICompatibleProvider().classify(inventory, ProviderContext(endpoint="http://example.test"))

    def test_openai_unknown_category_routes_to_deterministic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                with mock.patch("src.providers.openai_compatible.post_json") as post_json:
                    post_json.return_value = {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"files":[{"source":"report.pdf","category":"Secrets",'
                                        '"reason":"bad category","confidence":0.9}]}'
                                    )
                                }
                            }
                        ]
                    }
                    plan = build_plan(
                        inventory,
                        provider=OpenAICompatibleProvider(),
                        context=ProviderContext(endpoint="http://example.test"),
                    )

        self.assertEqual(plan.entries[0].category, "Documents")
        self.assertIn("Invalid provider classification", plan.warnings[0])

    def test_openai_confidence_out_of_range_routes_to_deterministic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "unknown.weird").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                with mock.patch("src.providers.openai_compatible.post_json") as post_json:
                    post_json.return_value = {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"files":[{"source":"unknown.weird","category":"Documents",'
                                        '"reason":"bad confidence","confidence":1.5}]}'
                                    )
                                }
                            }
                        ]
                    }
                    plan = build_plan(
                        inventory,
                        provider=OpenAICompatibleProvider(),
                        context=ProviderContext(endpoint="http://example.test"),
                    )

        self.assertEqual(plan.entries[0].category, "Review")
        self.assertEqual(plan.entries[0].destination, "Review/unknown.weird")
        self.assertIn("Invalid provider classification", plan.warnings[0])


if __name__ == "__main__":
    unittest.main()
