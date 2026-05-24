from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cli import main


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_scan_outputs_inventory_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")

            exit_code, output, _ = run_cli(["scan", str(root)])

            payload = json.loads(output)
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["summary"]["total_files"], 1)

    def test_plan_writes_required_entry_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            plan_path = root / "plan.json"
            (root / "report.pdf").write_text("content", encoding="utf-8")

            exit_code, _, _ = run_cli(["plan", str(root), "--output", str(plan_path)])
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            entry = payload["entries"][0]

            self.assertEqual(exit_code, 0)
            self.assertEqual({"source", "destination", "reason", "confidence"} <= set(entry), True)

    def test_apply_without_confirm_refuses_to_move(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            plan_path = root / "plan.json"
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")
            run_cli(["plan", str(root), "--output", str(plan_path)])

            exit_code, _, _ = run_cli(["apply", str(root), "--plan", str(plan_path)])

            self.assertEqual(exit_code, 2)
            self.assertTrue(source.exists())

    def test_apply_with_saved_plan_and_confirm_moves_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            plan_path = root / "plan.json"
            (root / "report.pdf").write_text("content", encoding="utf-8")
            run_cli(["plan", str(root), "--output", str(plan_path)])

            exit_code, _, _ = run_cli(["apply", str(root), "--plan", str(plan_path), "--confirm"])

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "Documents" / "report.pdf").exists())

    def test_run_defaults_to_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            exit_code, _, _ = run_cli(["run", str(root), "--format", "json"])

            self.assertEqual(exit_code, 0)
            self.assertTrue(source.exists())

    def test_run_writes_report_to_configured_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            config_path = root / "config.toml"
            (root / "report.pdf").write_text("content", encoding="utf-8")
            config_path.write_text(
                "[thelibrarian]\noutput_directory = \".thelibrarian/custom-reports\"\n",
                encoding="utf-8",
            )

            exit_code, _, _ = run_cli(["--config", str(config_path), "run", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(any((root / ".thelibrarian" / "custom-reports").glob("run-*.txt")))


if __name__ == "__main__":
    unittest.main()
