from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.librarian.code_analyzers.python_analyzer import analyze_python_file
from src.librarian.mover import apply_plan, rollback_plan
from src.librarian.planner import build_plan
from src.librarian.scanner import build_manifest, scan_workspace
from src.librarian.sidecars import read_manifest, write_sidecars


def make_workspace(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / "node_modules").mkdir(parents=True)
    (root / "build").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    (root / "src" / "main.py").write_text(
        '"""Demo app."""\nimport json\nfrom src.helper import greet\n\n\ndef main():\n    print(greet("World"))\n\n\nif __name__ == "__main__":\n    main()\n',
        encoding="utf-8",
    )
    (root / "src" / "helper.py").write_text("def greet(name: str) -> str:\n    return f'Hello, {name}'\n", encoding="utf-8")
    (root / "tests" / "test_main.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (root / "docs" / "meeting_minutes.md").write_text("# Meeting Minutes\n", encoding="utf-8")
    (root / "invoice_2026.pdf").write_text("fake pdf", encoding="utf-8")
    (root / "build" / "bundle.min.js").write_text("console.log('x')", encoding="utf-8")
    (root / "node_modules" / "lib.js").write_text("module.exports = {}", encoding="utf-8")


class ScannerTests(unittest.TestCase):
    def test_scan_recursive_files_and_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)

            scan = scan_workspace(root)

            self.assertGreaterEqual(len(scan.files), 6)
            self.assertGreaterEqual(len(scan.directories), 5)
            self.assertIn("Python", {node.detected_language for node in scan.files if node.detected_language})

    def test_python_ast_analysis_and_entrypoint_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)

            metadata = analyze_python_file(root / "src" / "main.py", root)

            self.assertIn("json", metadata.imports["standard_library"])
            self.assertIn("function:main", metadata.entrypoints)
            self.assertIn('guard:if __name__ == "__main__"', metadata.entrypoints)

    def test_generated_vendor_and_test_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)

            scan = scan_workspace(root)
            node_index = {node.current_path: node for node in scan.files}

            self.assertTrue(node_index["build/bundle.min.js"].generated_file)
            self.assertTrue(node_index["node_modules/lib.js"].vendor_file)
            self.assertEqual(node_index["tests/test_main.py"].classification.category, "Tests")


class SidecarAndManifestTests(unittest.TestCase):
    def test_sidecar_file_directory_and_manifest_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)

            scan = scan_workspace(root)
            manifest = build_manifest(scan)
            write_sidecars(root, manifest)

            self.assertTrue((root / "invoice_2026.pdf.librarian.yaml").exists())
            self.assertTrue((root / "docs" / ".librarian.yaml").exists())
            self.assertTrue((root / ".librarian" / "manifest.json").exists())

    def test_plan_dry_run_and_collision_handling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            make_workspace(root)
            (root / "finance").mkdir()
            (root / "finance" / "receipts").mkdir(parents=True)
            (root / "finance" / "receipts" / "invoice-2026.pdf").write_text("existing", encoding="utf-8")

            scan = scan_workspace(root)
            manifest = build_manifest(scan)
            write_sidecars(root, manifest)
            plan = build_plan(root, manifest)
            invoice_entry = next(entry for entry in plan.entries if entry.source == "invoice_2026.pdf")

            self.assertTrue(invoice_entry.collision)
            self.assertFalse(invoice_entry.safe_to_move)

    def test_apply_safe_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "meeting_minutes.md").write_text("# Notes\n", encoding="utf-8")

            scan = scan_workspace(root)
            manifest = build_manifest(scan)
            write_sidecars(root, manifest)
            plan = build_plan(root, manifest)
            apply_operations = apply_plan(root, plan=plan)

            self.assertTrue((root / "work" / "meetings" / "meeting-minutes.md").exists())
            self.assertTrue(any(operation.status == "applied" for operation in apply_operations))

            rollback_operations = rollback_plan(root)

            self.assertTrue((root / "meeting_minutes.md").exists())
            self.assertTrue(any(operation.status == "rolled_back" for operation in rollback_operations))

    def test_directory_plan_apply_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "Receipts").mkdir()
            (root / "Receipts" / "invoice_2026.pdf").write_text("fake pdf", encoding="utf-8")
            (root / "Receipts" / "receipt_notes.txt").write_text("notes", encoding="utf-8")

            scan = scan_workspace(root)
            manifest = build_manifest(scan)
            write_sidecars(root, manifest)
            plan = build_plan(root, manifest)

            directory_entry = next(entry for entry in plan.entries if entry.node_type == "directory" and entry.source == "Receipts")
            self.assertTrue(directory_entry.safe_to_move)
            self.assertEqual(directory_entry.destination, "finance/receipts/receipts")

            apply_plan(root, plan=plan)
            self.assertTrue((root / "finance" / "receipts" / "receipts" / "invoice_2026.pdf").exists())
            self.assertFalse((root / "Receipts").exists())

            rollback_plan(root)
            self.assertTrue((root / "Receipts" / "invoice_2026.pdf").exists())
            self.assertFalse((root / "finance" / "receipts" / "receipts").exists())
