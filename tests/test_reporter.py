from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.models import ManifestOperation
from src.planner import build_plan
from src.reporter import write_manifest, write_plan_artifact, write_report
from src.scanner import scan_directory


class ReporterArtifactTests(unittest.TestCase):
    def test_runtime_artifacts_use_thelibrarian_directory_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            plan = build_plan(scan_directory(root))

            report_path = write_report(root, "run.txt", "report")
            plan_path = write_plan_artifact(root, plan)
            manifest_path = write_manifest(
                root,
                [
                    ManifestOperation(
                        source="report.pdf",
                        destination="Documents/Reports/report.pdf",
                        reason="test",
                        confidence=1.0,
                        rollback_source="Documents/Reports/report.pdf",
                        rollback_destination="report.pdf",
                    )
                ],
                [],
            )

            self.assertEqual(report_path.parent, root / ".thelibrarian" / "reports")
            self.assertEqual(plan_path.parent, root / ".thelibrarian" / "plans")
            self.assertEqual(manifest_path.parent, root / ".thelibrarian" / "manifests")
            self.assertFalse((root / ".the_librarian").exists())

    def test_report_and_plan_artifacts_do_not_overwrite_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            plan = build_plan(scan_directory(root))

            first_report = write_report(root, "run.txt", "first")
            second_report = write_report(root, "run.txt", "second")
            first_plan = write_plan_artifact(root, plan)
            second_plan = write_plan_artifact(root, plan)

            self.assertNotEqual(first_report, second_report)
            self.assertEqual(first_report.read_text(encoding="utf-8"), "first")
            self.assertEqual(second_report.read_text(encoding="utf-8"), "second")
            self.assertNotEqual(first_plan, second_plan)


if __name__ == "__main__":
    unittest.main()
