from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.librarian.developer_runtime import initialize_runtime, regenerate_runtime, write_explanation
from src.librarian.planner import build_plan
from src.librarian.scanner import build_manifest, scan_workspace
from src.librarian.sidecars import write_sidecars


def make_workspace(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "tool.py").write_text(
        '"""Tool."""\n\ndef main():\n    print("ok")\n\nif __name__ == "__main__":\n    main()\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")


class DeveloperRuntimeTests(unittest.TestCase):
    def test_readme_notes_runbooks_and_scripts_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)
            scan = scan_workspace(root)
            manifest = build_manifest(scan)
            write_sidecars(root, manifest)
            build_plan(root, manifest)

            initialize_runtime(root, manifest)
            regenerate_runtime(root, manifest)
            explain_path = write_explanation(root, manifest)

            self.assertTrue((root / ".librarian" / "README.librarian.md").exists())
            self.assertTrue((root / ".librarian" / "notes" / "index.md").exists())
            self.assertTrue((root / ".librarian" / "runbooks" / "how_to_inspect.md").exists())
            self.assertTrue((root / ".librarian" / "scripts" / "inspect_workspace.py").exists())
            self.assertTrue(explain_path.exists())

    def test_runnable_scripts_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)
            scan = scan_workspace(root)
            manifest = build_manifest(scan)
            write_sidecars(root, manifest)
            initialize_runtime(root, manifest)

            scripts = [
                "inspect_workspace.py",
                "print_manifest_summary.py",
                "find_entrypoints.py",
                "find_unmarked.py",
            ]
            for script_name in scripts:
                completed = subprocess.run(
                    ["python", str(root / ".librarian" / "scripts" / script_name)],
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, msg=f"{script_name} failed: {completed.stderr}")
