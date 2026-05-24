from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from src.jobs.models import JobEvent, JobPhase, JobRecord, JobStatus
from src.models import utc_now_iso
from src.security import SafetyError, resolve_root


JOB_DIRECTORY = Path(".thelibrarian") / "jobs"
_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class JobStore:
    def __init__(self, root: str | Path) -> None:
        self.root = resolve_root(root)
        self.jobs_directory = self.root / JOB_DIRECTORY

    def create(self, *, dry_run: bool = True, provider: str = "deterministic", policy_name: str | None = None) -> JobRecord:
        job = JobRecord.create(root=str(self.root), dry_run=dry_run, provider=provider, policy_name=policy_name)
        self.job_directory(job.job_id).mkdir(parents=True, exist_ok=False)
        self.save(job)
        self.append_event(
            job.job_id,
            JobEvent.create(
                status=job.status,
                phase=job.phase,
                message="Job created.",
            ),
        )
        return job

    def job_directory(self, job_id: str) -> Path:
        normalized = self._validate_job_id(job_id)
        candidate = (self.jobs_directory / normalized).resolve(strict=False)
        try:
            candidate.relative_to(self.jobs_directory.resolve(strict=False))
        except ValueError as exc:
            raise SafetyError(f"Job path escapes the assigned root: {job_id}") from exc
        return candidate

    def artifact_path(self, job_id: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise SafetyError(f"Invalid job artifact name: {filename}")
        return self.job_directory(job_id) / filename

    def save(self, job: JobRecord) -> None:
        job.updated_at = utc_now_iso()
        job_directory = self.job_directory(job.job_id)
        job_directory.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(job_directory / "job.json", job.to_dict())

    def load(self, job_id: str) -> JobRecord:
        path = self.artifact_path(job_id, "job.json")
        if not path.exists():
            raise SafetyError(f"Unknown job: {job_id}")
        return JobRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[JobRecord]:
        if not self.jobs_directory.exists():
            return []
        jobs: list[JobRecord] = []
        for job_json in self.jobs_directory.glob("*/job.json"):
            try:
                jobs.append(JobRecord.from_dict(json.loads(job_json.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        jobs.sort(key=lambda job: job.updated_at, reverse=True)
        return jobs

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        phase: JobPhase | None = None,
        message: str | None = None,
        error: str | None = None,
        **fields: object,
    ) -> JobRecord:
        job = self.load(job_id)
        if status is not None:
            job.status = status
        if phase is not None:
            job.phase = phase
        if error is not None:
            job.error = error
        for field_name, value in fields.items():
            if not hasattr(job, field_name):
                raise ValueError(f"Unknown job field: {field_name}")
            setattr(job, field_name, value)
        self.save(job)
        if message:
            self.append_event(
                job.job_id,
                JobEvent.create(
                    status=job.status,
                    phase=job.phase,
                    message=message,
                    data={"error": error} if error else {},
                ),
            )
        return job

    def append_event(self, job_id: str, event: JobEvent) -> Path:
        events_path = self.artifact_path(job_id, "events.ndjson")
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict()) + "\n")
        return events_path

    def write_json_artifact(self, job_id: str, filename: str, payload: dict[str, object]) -> Path:
        path = self.artifact_path(job_id, filename)
        self._atomic_write_json(path, payload)
        return path

    def read_json_artifact(self, job_id: str, filename: str) -> dict[str, object]:
        path = self.artifact_path(job_id, filename)
        if not path.exists():
            raise SafetyError(f"Missing job artifact: {filename}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SafetyError(f"Job artifact is not a JSON object: {filename}")
        return payload

    def read_events(self, job_id: str) -> list[JobEvent]:
        events_path = self.artifact_path(job_id, "events.ndjson")
        if not events_path.exists():
            return []
        events: list[JobEvent] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(JobEvent.from_dict(json.loads(line)))
        return events

    def delete(self, job_id: str) -> None:
        job_directory = self.job_directory(job_id)
        if not job_directory.exists():
            raise SafetyError(f"Unknown job: {job_id}")
        shutil.rmtree(job_directory)

    def delete_all(self) -> int:
        if not self.jobs_directory.exists():
            return 0
        count = len([path for path in self.jobs_directory.iterdir() if path.is_dir()])
        shutil.rmtree(self.jobs_directory)
        return count

    def _validate_job_id(self, job_id: str) -> str:
        if not job_id or "/" in job_id or "\\" in job_id or ".." in job_id or not _SAFE_JOB_ID.match(job_id):
            raise SafetyError(f"Invalid job id: {job_id}")
        return job_id

    def _atomic_write_json(self, path: Path, payload: dict[str, object]) -> None:
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary_path, path)
