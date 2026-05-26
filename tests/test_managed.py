from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cli import main
from src.managed import load_managed_session, start_managed_cleanup
from src.security import SafetyError


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class ManagedCleanupTests(unittest.TestCase):
    def test_managed_start_creates_session_reports_and_does_not_move_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "contract.pdf"
            source.write_text("content", encoding="utf-8")

            session = start_managed_cleanup(
                root,
                client_name="Acme SRL",
                operator_name="Antonio",
                pack_id="studio_legale",
            )
            session_directory = root / ".thelibrarian" / "managed" / session.session_id

            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents" / "Reports" / "contract.pdf").exists())
            self.assertTrue((session_directory / "session.json").exists())
            self.assertTrue((session_directory / "report.json").exists())
            self.assertTrue((session_directory / "report.md").exists())
            self.assertTrue((session_directory / "report.html").exists())
            self.assertGreaterEqual(session.kpi.files_scanned, 1)
            self.assertIn("report_md", session.artifacts)
            self.assertIn("report_html", session.artifacts)
            report_markdown = (session_directory / "report.md").read_text(encoding="utf-8")
            report_html = (session_directory / "report.html").read_text(encoding="utf-8")
            report_json = json.loads((session_directory / "report.json").read_text(encoding="utf-8"))
            self.assertIn("## Service Snapshot", report_markdown)
            self.assertIn("## Client Outcome", report_markdown)
            self.assertIn("## KPI Snapshot", report_markdown)
            self.assertIn("## Artifact Map", report_markdown)
            self.assertIn("## Safety Appendix", report_markdown)
            self.assertIn("No files were moved during this report run.", report_markdown)
            self.assertIn("TheLibrarian Managed Cleanup Report", report_html)
            self.assertIn("Privacy-first file organization copilot", report_html)
            self.assertIn("No files were moved during this report run.", report_html)
            self.assertEqual(report_json["session_id"], session.session_id)
            self.assertIn("No files were moved", report_json["summary"])
            self.assertIn("report_html", report_json["artifacts"])

    def test_managed_cli_list_and_show(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "invoice.xlsx").write_text("content", encoding="utf-8")
            start_code, start_output, _ = run_cli(
                [
                    "managed",
                    "start",
                    str(root),
                    "--client",
                    "Acme SRL",
                    "--operator",
                    "Antonio",
                    "--pack",
                    "studio_legale",
                    "--format",
                    "json",
                ]
            )
            payload = json.loads(start_output)
            list_code, list_output, _ = run_cli(["managed", "list", str(root), "--format", "json"])
            show_code, show_output, _ = run_cli(
                ["managed", "show", payload["session_id"], "--root", str(root), "--format", "json"]
            )

        self.assertEqual(start_code, 0)
        self.assertEqual(list_code, 0)
        self.assertEqual(show_code, 0)
        self.assertEqual(json.loads(show_output)["session_id"], payload["session_id"])
        self.assertEqual(len(json.loads(list_output)["sessions"]), 1)

    def test_session_id_path_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            with self.assertRaises(SafetyError):
                load_managed_session(temp_directory, "../escape")


if __name__ == "__main__":
    unittest.main()
