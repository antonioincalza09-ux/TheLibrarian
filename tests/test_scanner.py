from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.scanner import scan_directory


class ScannerTests(unittest.TestCase):
    def test_scanner_builds_inventory_and_skips_internal_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "inbox").mkdir(parents=True, exist_ok=True)
            (root / "inbox" / "report.pdf").write_text("content", encoding="utf-8")
            (root / ".the_librarian" / "manifests").mkdir(parents=True, exist_ok=True)
            (root / ".the_librarian" / "manifests" / "rollback.json").write_text("{}", encoding="utf-8")
            (root / ".thelibrarian" / "jobs" / "example").mkdir(parents=True, exist_ok=True)
            (root / ".thelibrarian" / "jobs" / "example" / "job.json").write_text("{}", encoding="utf-8")

            inventory = scan_directory(root)

            self.assertEqual(inventory.total_files, 1)
            self.assertEqual(inventory.files[0].relative_path, "inbox/report.pdf")
            self.assertEqual(inventory.files[0].extension, ".pdf")
            self.assertEqual(inventory.warnings, [])


if __name__ == "__main__":
    unittest.main()
