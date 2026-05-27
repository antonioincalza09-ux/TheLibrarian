from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.config import RuntimeConfig
from src.webapp import create_server


class WebAppTests(unittest.TestCase):
    def _write_librarian_manifest(self, root: Path, *, include_graph: bool = False) -> None:
        runtime = root / ".librarian"
        (runtime / "notes").mkdir(parents=True, exist_ok=True)
        (runtime / "runbooks").mkdir(parents=True, exist_ok=True)
        (runtime / "scripts").mkdir(parents=True, exist_ok=True)
        (runtime / "notes" / "index.md").write_text("# Notes\n", encoding="utf-8")
        (runtime / "runbooks" / "index.md").write_text("# Runbooks\n", encoding="utf-8")
        (runtime / "scripts" / "print_manifest_summary.py").write_text("print('ok')\n", encoding="utf-8")
        manifest = {
            "workspace_root": str(root),
            "generated_at": "2026-05-26T20:57:33+00:00",
            "librarian_version": "0.2.0",
            "files": [
                {
                    "name": "main.py",
                    "current_path": "src/app/main.py",
                    "original_path": "src/app/main.py",
                    "file_kind": "source_code",
                    "detected_language": "Python",
                    "summary": "Main app entrypoint.",
                    "risk_level": "low",
                    "size_bytes": 120,
                    "readable": True,
                    "generated_file": False,
                    "vendor_file": False,
                    "lock_file": False,
                    "should_modify": False,
                    "should_move": False,
                    "tags": ["Code", "Project"],
                    "classification": {"domain": "Code", "category": "Project", "confidence": 0.92},
                    "code_metadata": {
                        "language": "Python",
                        "entrypoints": ["function:main", 'guard:if __name__ == "__main__"'],
                        "framework_hints": ["Typer"],
                        "test_hints": [],
                        "imports": {"internal": ["src.app.utils"], "external": []},
                        "symbols": {"functions": [{"name": "main"}], "classes": [], "methods": []},
                    },
                },
                {
                    "name": "test_main.py",
                    "current_path": "tests/test_main.py",
                    "original_path": "tests/test_main.py",
                    "file_kind": "source_code",
                    "detected_language": "Python",
                    "summary": "Pytest entry.",
                    "risk_level": "medium",
                    "size_bytes": 90,
                    "readable": True,
                    "generated_file": False,
                    "vendor_file": False,
                    "lock_file": False,
                    "should_modify": False,
                    "should_move": False,
                    "tags": ["Code", "Tests"],
                    "classification": {"domain": "Code", "category": "Tests", "confidence": 0.7},
                    "code_metadata": {
                        "language": "Python",
                        "entrypoints": [],
                        "framework_hints": ["pytest"],
                        "test_hints": ["pytest"],
                        "imports": {"internal": ["src.app.main"], "external": []},
                        "symbols": {"functions": [{"name": "test_main"}], "classes": [], "methods": []},
                    },
                },
            ],
            "directories": [
                {
                    "name": "src",
                    "current_path": "src",
                    "human_description": "Source tree",
                    "directory_analysis": {
                        "possible_roles": ["source", "project_root"],
                        "direct_file_count": 0,
                        "direct_subdirectory_count": 1,
                        "total_file_count": 1,
                        "dominant_languages": ["Python"],
                        "dominant_extensions": [".py"],
                        "should_reorganize": False,
                    },
                }
            ],
            "entrypoints": ["src/app/main.py:function:main"],
            "warnings": [],
            "errors": [],
        }
        (runtime / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        if include_graph:
            graph = {
                "nodes": [
                    {"id": "src/app/main.py", "label": "main.py", "type": "file", "confidence": 0.9},
                    {"id": "tests/test_main.py", "label": "test_main.py", "type": "file", "confidence": 0.8},
                ],
                "edges": [
                    {"source": "src/app/main.py", "target": "tests/test_main.py", "type": "tested_by", "confidence": 0.8}
                ],
            }
            (runtime / "graph.json").write_text(json.dumps(graph), encoding="utf-8")

    def test_server_exposes_inventory_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                inventory = json.loads(urlopen(f"http://{host}:{port}/api/inventory", timeout=5).read())
                plan = json.loads(urlopen(f"http://{host}:{port}/api/plan", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(inventory["summary"]["total_files"], 1)
            self.assertEqual(plan["entries"][0]["destination"], "Documents/Reports/report.pdf")

    def test_dashboard_home_and_api_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            self._write_librarian_manifest(root, include_graph=True)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                html = urlopen(f"http://{host}:{port}/", timeout=5).read().decode("utf-8")
                dashboard = json.loads(urlopen(f"http://{host}:{port}/api/dashboard", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertIn('data-app="thelibrarian-dashboard"', html)
            self.assertIn('data-shell="librarian-dev-dashboard"', html)
            self.assertIn("Developer-first workspace dashboard", html)
            self.assertIn("Copy Agent Brief", html)
            self.assertIn("Overview", html)
            self.assertIn("Start Here", html)
            self.assertIn("Entrypoints", html)
            self.assertIn("Diagnostics", html)
            self.assertIn('id="downloadPlanBtn"', html)
            self.assertIn('id="workspaceName"', html)
            self.assertIn('id="page-overview"', html)
            self.assertIn('id="page-files"', html)
            self.assertIn('id="page-graph"', html)
            self.assertGreaterEqual(dashboard["inventory"]["summary"]["total_files"], 1)
            self.assertIn("librarian", dashboard)
            self.assertEqual(dashboard["librarian"]["overview"]["metrics"][0]["label"], "Files")
            self.assertIn("jobs", dashboard)
            self.assertIn("chat", dashboard)

    def test_librarian_dashboard_handles_missing_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                payload = json.loads(urlopen(f"http://{host}:{port}/api/librarian/dashboard", timeout=5).read())
                graph = json.loads(urlopen(f"http://{host}:{port}/api/librarian/graph-summary", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(payload["workspace"]["status"], "Needs Index")
            self.assertFalse(graph["available"])
            self.assertIn("missing", graph["empty_message"].lower())

    def test_librarian_dashboard_exposes_overview_and_filtered_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            self._write_librarian_manifest(root, include_graph=True)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                payload = json.loads(urlopen(f"http://{host}:{port}/api/librarian/dashboard", timeout=5).read())
                filtered = json.loads(urlopen(f"http://{host}:{port}/api/librarian/files?language=Python&risk=medium", timeout=5).read())
                scripts = json.loads(urlopen(f"http://{host}:{port}/api/librarian/scripts", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(payload["overview"]["status"], "Warnings")
            self.assertEqual(payload["overview"]["metrics"][0]["value"], 2)
            self.assertEqual(len(filtered["files"]), 1)
            self.assertEqual(filtered["files"][0]["path"], "tests/test_main.py")
            self.assertEqual(scripts["scripts"][0]["name"], "print_manifest_summary.py")

    def test_job_run_endpoint_creates_artifacts_without_moving_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                request = Request(
                    f"http://{host}:{port}/api/jobs/run",
                    data=json.dumps({"policy": "supervised_autonomy"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                job = json.loads(urlopen(request, timeout=5).read())
                dashboard = json.loads(urlopen(f"http://{host}:{port}/api/dashboard", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            job_directory = root / ".thelibrarian" / "jobs" / job["job_id"]
            self.assertEqual(job["status"], "completed")
            self.assertTrue((job_directory / "job.json").exists())
            self.assertTrue((job_directory / "inventory.json").exists())
            self.assertTrue((job_directory / "plan.json").exists())
            self.assertTrue((job_directory / "report.txt").exists())
            self.assertTrue((job_directory / "policy_decision.json").exists())
            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents" / "report.pdf").exists())
            self.assertEqual(dashboard["jobs"][0]["job_id"], job["job_id"])

    def test_apply_endpoint_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                with self.assertRaises(HTTPError) as error:
                    urlopen(f"http://{host}:{port}/api/apply", data=b"{}", timeout=5).read()
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(error.exception.code, 403)

    def test_job_apply_endpoint_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                run_request = Request(
                    f"http://{host}:{port}/api/jobs/run",
                    data=json.dumps({"policy": "supervised_autonomy"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                job = json.loads(urlopen(run_request, timeout=5).read())
                apply_request = Request(
                    f"http://{host}:{port}/api/jobs/{job['job_id']}/apply",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(apply_request, timeout=5).read()
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(error.exception.code, 403)

    def test_root_endpoint_switches_dashboard_target(self) -> None:
        with tempfile.TemporaryDirectory() as first_directory, tempfile.TemporaryDirectory() as second_directory:
            first_root = Path(first_directory)
            second_root = Path(second_directory)
            (first_root / "report.pdf").write_text("content", encoding="utf-8")
            (second_root / "report.pdf").write_text("content", encoding="utf-8")
            (second_root / "data.csv").write_text("data", encoding="utf-8")
            server = create_server(first_root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                before = json.loads(urlopen(f"http://{host}:{port}/api/dashboard", timeout=5).read())
                switch_request = Request(
                    f"http://{host}:{port}/api/root?confirm=true",
                    data=json.dumps({"root": str(second_root)}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                switched = json.loads(urlopen(switch_request, timeout=5).read())
                after = json.loads(urlopen(f"http://{host}:{port}/api/dashboard", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(before["inventory"]["summary"]["total_files"], 1)
            self.assertEqual(switched["root"], str(second_root.resolve()))
            self.assertEqual(after["root"], str(second_root.resolve()))
            self.assertEqual(after["inventory"]["summary"]["total_files"], 2)

    def test_delete_job_endpoint_removes_only_job_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                run_request = Request(
                    f"http://{host}:{port}/api/jobs/run",
                    data=json.dumps({"policy": "dry_run_only"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                job = json.loads(urlopen(run_request, timeout=5).read())
                job_directory = root / ".thelibrarian" / "jobs" / job["job_id"]
                delete_request = Request(
                    f"http://{host}:{port}/api/jobs/{job['job_id']}/delete?confirm=true",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                deleted = json.loads(urlopen(delete_request, timeout=5).read())
                jobs = json.loads(urlopen(f"http://{host}:{port}/api/jobs", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(deleted["deleted"], 1)
            self.assertFalse(job_directory.exists())
            self.assertEqual(jobs["jobs"], [])
            self.assertTrue(source.exists())

    def test_delete_all_jobs_endpoint_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                request = Request(
                    f"http://{host}:{port}/api/jobs/delete-all",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=5).read()
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(error.exception.code, 403)

    def test_plan_save_endpoint_writes_plan_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                request = Request(f"http://{host}:{port}/api/plan/save", data=b"{}", method="POST")
                payload = json.loads(urlopen(request, timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            plan_path = Path(payload["path"])
            self.assertTrue(plan_path.exists())
            self.assertEqual(plan_path.parent, root / ".thelibrarian" / "plans")
            self.assertEqual(payload["plan"]["entries"][0]["destination"], "Documents/Reports/report.pdf")

    def test_plan_endpoint_can_preview_policy_pack_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "contract.pdf").write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                plan = json.loads(urlopen(f"http://{host}:{port}/api/plan?pack_id=studio_legale", timeout=5).read())
                request = Request(
                    f"http://{host}:{port}/api/plan/save",
                    data=json.dumps({"pack_id": "studio_legale"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                saved = json.loads(urlopen(request, timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(plan["entries"][0]["destination"], "Documents/Contracts/contract.pdf")
            self.assertEqual(saved["plan"]["entries"][0]["destination"], "Documents/Contracts/contract.pdf")

    def test_chat_endpoint_updates_dashboard_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                for command in ("analizza", "piano", "sposta report.pdf Documents/General/finale.pdf"):
                    request = Request(
                        f"http://{host}:{port}/api/chat",
                        data=json.dumps({"command": command}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    urlopen(request, timeout=5).read()
                dashboard = json.loads(urlopen(f"http://{host}:{port}/api/dashboard", timeout=5).read())
                save_request = Request(
                    f"http://{host}:{port}/api/plan/save",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                saved = json.loads(urlopen(save_request, timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertTrue(dashboard["chat"]["has_plan"])
            self.assertIn("analizza", [item["content"] for item in dashboard["chat"]["history"] if item["role"] == "user"])
            self.assertEqual(dashboard["plan"]["entries"][0]["destination"], "Documents/General/finale.pdf")
            self.assertEqual(saved["plan"]["entries"][0]["destination"], "Documents/General/finale.pdf")

    def test_policy_pack_and_provider_api_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                packs = json.loads(urlopen(f"http://{host}:{port}/api/packs", timeout=5).read())
                pack = json.loads(urlopen(f"http://{host}:{port}/api/packs/studio_legale", timeout=5).read())
                recommended = json.loads(urlopen(f"http://{host}:{port}/api/packs/recommend?industry=healthcare", timeout=5).read())
                providers = json.loads(urlopen(f"http://{host}:{port}/api/providers", timeout=5).read())
                doctor = json.loads(urlopen(f"http://{host}:{port}/api/providers/doctor?provider=remote-compatible", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(len([pack for pack in packs["packs"] if pack.get("industry")]), 25)
        self.assertEqual(pack["id"], "studio_legale")
        self.assertIn("medical_clinic", {item["id"] for item in recommended["packs"]})
        self.assertIn("remote-compatible", providers["available"])
        self.assertEqual(doctor["provider"], "remote-compatible")
        self.assertNotIn("secret", json.dumps(doctor).lower())

    def test_managed_start_endpoint_requires_confirm_and_creates_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "contract.pdf"
            source.write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                request = Request(
                    f"http://{host}:{port}/api/managed/start?confirm=true",
                    data=json.dumps(
                        {
                            "client_name": "Acme SRL",
                            "operator_name": "Antonio",
                            "pack_id": "studio_legale",
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                session = json.loads(urlopen(request, timeout=5).read())
                sessions = json.loads(urlopen(f"http://{host}:{port}/api/managed", timeout=5).read())
                report_html = urlopen(
                    f"http://{host}:{port}/api/managed/{session['session_id']}/report-html",
                    timeout=5,
                ).read().decode("utf-8")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            session_directory = root / ".thelibrarian" / "managed" / session["session_id"]
            self.assertTrue(source.exists())
            self.assertTrue((session_directory / "session.json").exists())
            self.assertTrue((session_directory / "report.json").exists())
            self.assertTrue((session_directory / "report.md").exists())
            self.assertTrue((session_directory / "report.html").exists())
            self.assertIn("TheLibrarian Managed Cleanup Report", report_html)
            self.assertIn("No files were moved during this report run.", report_html)
            self.assertEqual(sessions["sessions"][0]["session_id"], session["session_id"])


if __name__ == "__main__":
    unittest.main()
