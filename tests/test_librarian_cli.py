from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.librarian.cli import main


def run_cli(args: list[str]) -> tuple[int, str]:
    import contextlib
    import io

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = main(args)
    return exit_code, stdout.getvalue()


def make_workspace(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text('def main():\n    return "ok"\n', encoding="utf-8")
    (root / "notes.md").write_text("# Notes\n", encoding="utf-8")


class LibrarianCliTests(unittest.TestCase):
    def test_full_cli_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)

            for args in [
                ["scan", str(root), "--write"],
                ["mark", str(root)],
                ["dev", "init", str(root)],
                ["dev", "index", str(root)],
                ["dev", "explain", str(root)],
                ["dev", "runbook", str(root)],
                ["plan", str(root)],
                ["apply", str(root)],
                ["status", str(root)],
                ["rollback", str(root)],
            ]:
                exit_code, output = run_cli(args)
                self.assertEqual(exit_code, 0, msg=f"command failed: {args}\n{output}")

            status_exit, status_output = run_cli(["status", str(root)])
            status_payload = json.loads(status_output)
            self.assertEqual(status_exit, 0)
            self.assertIn("file_totals", status_payload)
