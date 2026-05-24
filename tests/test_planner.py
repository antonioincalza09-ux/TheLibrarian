from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.planner import build_plan
from src.scanner import scan_directory


class PlannerTests(unittest.TestCase):
    def test_planner_routes_known_and_ambiguous_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            (root / "config.json").write_text("{}", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entries = {entry.source: entry for entry in plan.entries}

            self.assertEqual(entries["report.pdf"].destination, "Documents/report.pdf")
            self.assertEqual(entries["report.pdf"].status, "planned")
            self.assertEqual(entries["config.json"].destination, "Review/config.json")
            self.assertEqual(entries["config.json"].category, "Review")

    def test_planner_marks_conflicts_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            (root / "Documents").mkdir(parents=True, exist_ok=True)
            (root / "Documents" / "report.pdf").write_text("existing", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entry = next(item for item in plan.entries if item.source == "report.pdf")

            self.assertEqual(entry.status, "skipped_conflict")
            self.assertIn("Destination already exists", entry.warning or "")


if __name__ == "__main__":
    unittest.main()

