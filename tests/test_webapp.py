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
            self.assertIn("Operations Dashboard", html)
            self.assertIn('id="downloadPlanBtn"', html)
            self.assertIn('id="planSearchInput"', html)
            self.assertIn('id="reviewCategoryFilter"', html)
            self.assertEqual(dashboard["inventory"]["summary"]["total_files"], 1)
            self.assertIn("jobs", dashboard)

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
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            session_directory = root / ".thelibrarian" / "managed" / session["session_id"]
            self.assertTrue(source.exists())
            self.assertTrue((session_directory / "session.json").exists())
            self.assertTrue((session_directory / "report.json").exists())
            self.assertTrue((session_directory / "report.md").exists())
            self.assertEqual(sessions["sessions"][0]["session_id"], session["session_id"])


if __name__ == "__main__":
    unittest.main()
