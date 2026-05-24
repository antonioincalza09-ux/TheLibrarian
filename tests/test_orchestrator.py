from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.orchestrator import organize_directory


class OrchestratorTests(unittest.TestCase):
    def test_report_contains_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "notes.txt").write_text("hello", encoding="utf-8")

            result = organize_directory(root)

            self.assertIn("Files scanned: 1", result.report)
            self.assertIn("Planned moves: 1", result.report)
            self.assertIn("Dry run: True", result.report)
            self.assertIn("notes.txt -> Documents/notes.txt", result.report)


if __name__ == "__main__":
    unittest.main()

