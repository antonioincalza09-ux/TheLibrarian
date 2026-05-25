from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.cli import build_parser, main


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_help_uses_product_positioning(self) -> None:
        output = build_parser().format_help()

        self.assertIn("Privacy-first file organization copilot", output)

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
            self.assertTrue((root / "Documents" / "Reports" / "report.pdf").exists())

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

    def test_doctor_outputs_installation_root_and_provider_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
                with mock.patch("src.providers.diagnostics.get_json", side_effect=[{"models": []}, {"data": []}]):
                    exit_code, output, _ = run_cli(["doctor", str(root), "--format", "json"])

            payload = json.loads(output)
            checks = {check["name"]: check for check in payload["checks"]}

            self.assertEqual(exit_code, 0)
            self.assertIn(payload["status"], {"ok", "warning"})
            self.assertEqual(checks["root_writable"]["status"], "ok")
            self.assertEqual(checks["config_provider"]["status"], "ok")

    def test_providers_doctor_runs_ollama_reachability_probe(self) -> None:
        with mock.patch("src.providers.diagnostics.get_json", return_value={"models": []}) as get_json:
            exit_code, output, _ = run_cli(
                [
                    "providers",
                    "doctor",
                    "--provider",
                    "ollama",
                    "--endpoint",
                    "http://ollama.test",
                    "--format",
                    "json",
                ]
            )

        payload = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(get_json.call_args.args[0], "http://ollama.test/api/tags")


if __name__ == "__main__":
    unittest.main()
