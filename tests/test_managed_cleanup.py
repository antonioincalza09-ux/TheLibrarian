from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cli import main
from src.config import RuntimeConfig
from src.managed_cleanup import get_cleanup_session, list_cleanup_sessions, run_cleanup_preview


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class ManagedCleanupTests(unittest.TestCase):
    def test_cleanup_preview_writes_artifacts_without_moving_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            session = run_cleanup_preview(
                root,
                config=RuntimeConfig(provider="deterministic"),
                policy_pack_id="supervised_documents",
            )

            session_directory = root / ".thelibrarian" / "managed-cleanups" / session.session_id
            self.assertEqual(session.status.value, "completed")
            self.assertTrue((session_directory / "cleanup_session.json").exists())
            self.assertTrue((session_directory / "inventory.json").exists())
            self.assertTrue((session_directory / "plan.json").exists())
            self.assertTrue((session_directory / "policy_decision.json").exists())
            self.assertTrue((session_directory / "kpi.json").exists())
            self.assertTrue((session_directory / "policy_pack.json").exists())
            self.assertTrue((session_directory / "report.txt").exists())
            self.assertEqual(session.kpis["files_scanned"], 1)
            self.assertEqual(session.kpis["auto_approved"], 1)
            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents" / "Reports" / "report.pdf").exists())

    def test_cleanup_sessions_can_be_listed_and_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")

            session = run_cleanup_preview(root)
            sessions = list_cleanup_sessions(root)
            loaded = get_cleanup_session(root, session.session_id)

            self.assertEqual(sessions[0].session_id, session.session_id)
            self.assertEqual(loaded.session_id, session.session_id)

    def test_cleanup_preview_cli_outputs_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")

            exit_code, output, _ = run_cli(
                [
                    "cleanup",
                    "preview",
                    str(root),
                    "--policy-pack",
                    "supervised_documents",
                    "--format",
                    "json",
                ]
            )
            payload = json.loads(output)

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["policy_pack_id"], "supervised_documents")
            self.assertIn("kpi", payload["artifacts"])

    def test_policy_pack_cli_export_and_show(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)

            export_exit, export_output, _ = run_cli(
                ["policy-packs", "export", "supervised_documents", str(root), "--format", "json"]
            )
            show_exit, show_output, _ = run_cli(
                ["policy-packs", "show", "supervised_documents", "--root", str(root), "--format", "json"]
            )
            export_payload = json.loads(export_output)
            show_payload = json.loads(show_output)

            self.assertEqual(export_exit, 0)
            self.assertEqual(show_exit, 0)
            self.assertTrue(Path(export_payload["path"]).exists())
            self.assertEqual(show_payload["source"], "local")


if __name__ == "__main__":
    unittest.main()
