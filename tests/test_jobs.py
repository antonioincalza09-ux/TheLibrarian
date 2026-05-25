from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cli import main
from src.jobs import JobEvent, JobPhase, JobRunner, JobStatus, JobStore
from src.security import SafetyError


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class JobStoreTests(unittest.TestCase):
    def test_create_job_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            store = JobStore(root)

            job = store.create()

            self.assertEqual(job.status, JobStatus.CREATED)
            self.assertEqual(job.phase, JobPhase.CREATED)
            self.assertTrue((root / ".thelibrarian" / "jobs" / job.job_id / "job.json").exists())

    def test_save_and_load_job_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            store = JobStore(temp_directory)
            job = store.create(provider="deterministic")
            job.counters["scanned"] = 3
            store.save(job)

            loaded = store.load(job.job_id)

            self.assertEqual(loaded.job_id, job.job_id)
            self.assertEqual(loaded.root, str(Path(temp_directory).resolve()))
            self.assertEqual(loaded.counters["scanned"], 3)

    def test_update_status_and_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            store = JobStore(temp_directory)
            job = store.create()

            updated = store.update(
                job.job_id,
                status=JobStatus.SCANNING,
                phase=JobPhase.SCANNING,
                message="Scanning.",
            )

            self.assertEqual(updated.status, JobStatus.SCANNING)
            self.assertEqual(updated.phase, JobPhase.SCANNING)
            self.assertGreater(len(store.read_events(job.job_id)), 1)

    def test_events_are_append_only_ndjson(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            store = JobStore(temp_directory)
            job = store.create()
            store.append_event(
                job.job_id,
                JobEvent.create(status=JobStatus.PLANNING, phase=JobPhase.PLANNING, message="Planning."),
            )

            events_path = root_events_path(temp_directory, job.job_id)
            lines = events_path.read_text(encoding="utf-8").splitlines()

            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["message"], "Planning.")

    def test_job_id_path_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            store = JobStore(temp_directory)

            with self.assertRaises(SafetyError):
                store.load("../escape")


class JobRunnerTests(unittest.TestCase):
    def test_job_run_dry_run_creates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            job = JobRunner(root).run(dry_run=True)
            job_directory = root / ".thelibrarian" / "jobs" / job.job_id

            self.assertEqual(job.status, JobStatus.COMPLETED)
            self.assertTrue((job_directory / "job.json").exists())
            self.assertTrue((job_directory / "inventory.json").exists())
            self.assertTrue((job_directory / "plan.json").exists())
            self.assertTrue((job_directory / "policy_decision.json").exists())
            self.assertTrue((job_directory / "report.txt").exists())
            self.assertTrue((job_directory / "events.ndjson").exists())
            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents" / "Reports" / "report.pdf").exists())

    def test_job_run_with_pack_writes_policy_pack_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "contract.pdf"
            source.write_text("content", encoding="utf-8")

            job = JobRunner(root).run(dry_run=True, pack_id="studio_legale")
            job_directory = root / ".thelibrarian" / "jobs" / job.job_id
            pack_payload = json.loads((job_directory / "policy_pack.json").read_text(encoding="utf-8"))

            self.assertEqual(job.pack_id, "studio_legale")
            self.assertEqual(pack_payload["id"], "studio_legale")
            self.assertTrue(source.exists())

    def test_non_dry_run_without_allow_apply_awaits_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            job = JobRunner(root).run(dry_run=False)

            self.assertEqual(job.status, JobStatus.AWAITING_APPROVAL)
            self.assertEqual(job.phase, JobPhase.AWAITING_APPROVAL)
            self.assertIsNotNone(job.policy_path)
            self.assertTrue(source.exists())

    def test_job_apply_uses_auto_approved_policy_entries_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            document = root / "report.pdf"
            code = root / "script.py"
            document.write_text("content", encoding="utf-8")
            code.write_text("print('hello')", encoding="utf-8")

            job = JobRunner(root).run(dry_run=True, policy_name="supervised_autonomy")
            applied = JobRunner(root).apply(job.job_id)

            self.assertEqual(applied.status, JobStatus.COMPLETED)
            self.assertTrue((root / "Documents" / "Reports" / "report.pdf").exists())
            self.assertTrue(code.exists())
            self.assertFalse((root / "Code" / "script.py").exists())
            self.assertIsNotNone(applied.manifest_path)
            self.assertIsNotNone(applied.verification_path)

    def test_job_approve_then_apply_moves_requires_approval_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            job = JobRunner(root).run(dry_run=True)
            with self.assertRaises(SafetyError):
                JobRunner(root).apply(job.job_id)
            approved = JobRunner(root).approve(job.job_id)
            applied = JobRunner(root).apply(approved.job_id)

            self.assertEqual(applied.status, JobStatus.COMPLETED)
            self.assertTrue((root / "Documents" / "Reports" / "report.pdf").exists())

    def test_job_rollback_uses_job_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            job = JobRunner(root).run(dry_run=True, policy_name="supervised_autonomy")
            applied = JobRunner(root).apply(job.job_id)
            rolled_back = JobRunner(root).rollback(applied.job_id)

            self.assertEqual(rolled_back.status, JobStatus.ROLLED_BACK)
            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents" / "Reports" / "report.pdf").exists())

    def test_job_root_is_resolved_and_confined(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            job = JobStore(root / ".").create()

            self.assertEqual(job.root, str(root.resolve()))


class JobCliTests(unittest.TestCase):
    def test_job_create_does_not_modify_user_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")

            exit_code, output, _ = run_cli(["job", "create", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Status: created", output)
            self.assertTrue(source.exists())
            self.assertFalse((root / "Documents").exists())

    def test_job_run_and_status_are_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")

            run_exit, run_output, _ = run_cli(["job", "run", str(root), "--format", "json"])
            payload = json.loads(run_output)
            status_exit, status_output, _ = run_cli(
                ["job", "status", payload["job_id"], "--root", str(root), "--format", "json"]
            )
            status_payload = json.loads(status_output)

            self.assertEqual(run_exit, 0)
            self.assertEqual(status_exit, 0)
            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(status_payload["job_id"], payload["job_id"])

    def test_job_run_cli_with_pack_writes_pack_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "contract.pdf"
            source.write_text("content", encoding="utf-8")

            run_exit, run_output, _ = run_cli(
                ["job", "run", str(root), "--pack", "studio_legale", "--format", "json"]
            )
            payload = json.loads(run_output)

            self.assertEqual(run_exit, 0)
            self.assertEqual(payload["pack_id"], "studio_legale")
            self.assertTrue((root / ".thelibrarian" / "jobs" / payload["job_id"] / "policy_pack.json").exists())
            self.assertTrue(source.exists())

    def test_job_apply_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            run_exit, run_output, _ = run_cli(["job", "run", str(root), "--policy", "supervised_autonomy", "--format", "json"])
            payload = json.loads(run_output)

            apply_exit, _, stderr = run_cli(["job", "apply", payload["job_id"], "--root", str(root)])

            self.assertEqual(run_exit, 0)
            self.assertEqual(apply_exit, 2)
            self.assertIn("--confirm", stderr)

    def test_job_approve_and_apply_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")
            _, run_output, _ = run_cli(["job", "run", str(root), "--format", "json"])
            payload = json.loads(run_output)

            approve_exit, _, _ = run_cli(["job", "approve", payload["job_id"], "--root", str(root), "--confirm"])
            apply_exit, _, _ = run_cli(["job", "apply", payload["job_id"], "--root", str(root), "--confirm"])

            self.assertEqual(approve_exit, 0)
            self.assertEqual(apply_exit, 0)
            self.assertTrue((root / "Documents" / "Reports" / "report.pdf").exists())

    def test_job_rollback_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            source = root / "report.pdf"
            source.write_text("content", encoding="utf-8")
            _, run_output, _ = run_cli(["job", "run", str(root), "--policy", "supervised_autonomy", "--format", "json"])
            payload = json.loads(run_output)
            run_cli(["job", "apply", payload["job_id"], "--root", str(root), "--confirm"])

            rollback_exit, _, _ = run_cli(["job", "rollback", payload["job_id"], "--root", str(root), "--confirm"])

            self.assertEqual(rollback_exit, 0)
            self.assertTrue(source.exists())

    def test_job_list_shows_created_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            _, output, _ = run_cli(["job", "create", str(root)])
            job_id = next(line for line in output.splitlines() if line.startswith("Job: ")).split(": ", 1)[1]

            exit_code, list_output, _ = run_cli(["job", "list", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn(job_id, list_output)


def root_events_path(root: str | Path, job_id: str) -> Path:
    return Path(root) / ".thelibrarian" / "jobs" / job_id / "events.ndjson"


if __name__ == "__main__":
    unittest.main()
