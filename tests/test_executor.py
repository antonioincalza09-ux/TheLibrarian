from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.executor import execute_plan
from src.planner import build_plan
from src.scanner import scan_directory
from src.security import SafetyError


class ExecutorTests(unittest.TestCase):
    def test_dry_run_does_not_move_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            execution = execute_plan(root, plan)

            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents" / "report.pdf").exists())
            self.assertTrue(execution.dry_run)
            self.assertIsNone(execution.manifest_path)
            self.assertEqual(execution.applied_count, 0)

    def test_apply_moves_files_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "inbox" / "report.pdf"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("content", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            execution = execute_plan(root, plan, dry_run=False)
            destination = root / "Documents" / "inbox" / "report.pdf"

            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            self.assertEqual(execution.applied_count, 1)
            self.assertIsNotNone(execution.manifest_path)

            manifest_path = Path(execution.manifest_path or "")
            self.assertTrue(manifest_path.exists())

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["operations"][0]["source"], "inbox/report.pdf")
            self.assertEqual(manifest_payload["operations"][0]["destination"], "Documents/inbox/report.pdf")
            self.assertEqual(
                manifest_payload["operations"][0]["rollback"],
                {
                    "source": "Documents/inbox/report.pdf",
                    "destination": "inbox/report.pdf",
                },
            )

    def test_executor_rejects_destination_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            plan.entries[0].destination = "../escape/report.pdf"

            with self.assertRaises(SafetyError):
                execute_plan(root, plan, dry_run=False)


if __name__ == "__main__":
    unittest.main()

