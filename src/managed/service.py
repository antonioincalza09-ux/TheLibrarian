from __future__ import annotations

import json
import os
import re
from pathlib import Path

from src.config import RuntimeConfig
from src.jobs import JobRunner, JobStore
from src.jobs.models import JobRecord
from src.jsonio import read_inventory, read_plan
from src.managed.kpi import calculate_kpi
from src.managed.models import (
    ManagedCleanupRecommendation,
    ManagedCleanupSession,
    ManagedCleanupStage,
)
from src.managed.report import build_managed_report, render_managed_report_markdown
from src.policy_packs import get_policy_pack
from src.policies.models import PolicyEvaluation
from src.security import SafetyError, resolve_root


MANAGED_DIRECTORY = Path(".thelibrarian") / "managed"
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def start_managed_cleanup(
    root: str | Path,
    *,
    client_name: str,
    operator_name: str,
    pack_id: str,
    config: RuntimeConfig | None = None,
) -> ManagedCleanupSession:
    resolved_root = resolve_root(root)
    pack = get_policy_pack(pack_id)
    runner = JobRunner(resolved_root, config=config or RuntimeConfig())
    job = runner.run(dry_run=True, policy_name=pack.recommended_policy, pack_id=pack.id)
    session = ManagedCleanupSession.create(
        root=str(resolved_root),
        client_name=client_name,
        operator_name=operator_name,
        pack_id=pack.id,
        job_id=job.job_id,
    )
    session.stage = ManagedCleanupStage.COMPLETED
    session.recommendations = [
        ManagedCleanupRecommendation(
            id=recommendation.id,
            title=recommendation.title,
            description=recommendation.description,
            priority="normal",
        )
        for recommendation in pack.managed_service_recommendations
    ]
    session.artifacts = _job_artifacts(job)
    session.kpi = _kpi_from_job(resolved_root, job)
    session.summary = (
        f"Dry-run managed cleanup completed for {client_name}: "
        f"{session.kpi.files_scanned} file(s) scanned, {session.kpi.planned_moves} move(s) planned."
    )
    _write_session_artifacts(resolved_root, session, pack)
    return session


def load_managed_session(root: str | Path, session_id: str) -> ManagedCleanupSession:
    path = _session_directory(root, session_id) / "session.json"
    if not path.exists():
        raise SafetyError(f"Unknown managed cleanup session: {session_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SafetyError("Managed cleanup session is not a JSON object.")
    return ManagedCleanupSession.from_dict(payload)


def list_managed_sessions(root: str | Path) -> list[ManagedCleanupSession]:
    directory = resolve_root(root) / MANAGED_DIRECTORY
    if not directory.exists():
        return []
    sessions: list[ManagedCleanupSession] = []
    for session_json in directory.glob("*/session.json"):
        try:
            sessions.append(ManagedCleanupSession.from_dict(json.loads(session_json.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    sessions.sort(key=lambda session: session.updated_at, reverse=True)
    return sessions


def regenerate_managed_report(root: str | Path, session_id: str) -> ManagedCleanupSession:
    resolved_root = resolve_root(root)
    session = load_managed_session(resolved_root, session_id)
    pack = get_policy_pack(session.pack_id)
    try:
        job = JobStore(resolved_root).load(session.job_id)
        session.artifacts.update(_job_artifacts(job))
        session.kpi = _kpi_from_job(resolved_root, job)
    except SafetyError:
        pass
    _write_session_artifacts(resolved_root, session, pack)
    return session


def _job_artifacts(job: JobRecord) -> dict[str, str]:
    artifacts = {
        "job": str(Path(job.root) / ".thelibrarian" / "jobs" / job.job_id / "job.json"),
    }
    for name in ("inventory_path", "plan_path", "policy_path", "manifest_path", "report_path", "verification_path"):
        value = getattr(job, name)
        if value:
            artifacts[name.removesuffix("_path")] = str(value)
    return artifacts


def _kpi_from_job(root: Path, job: JobRecord):
    if not job.inventory_path or not job.plan_path:
        raise SafetyError("Managed cleanup job is missing inventory or plan artifacts.")
    inventory = read_inventory(job.inventory_path)
    plan = read_plan(job.plan_path)
    policy = None
    if job.policy_path:
        payload = json.loads(Path(job.policy_path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            policy = PolicyEvaluation.from_dict(payload)
    return calculate_kpi(inventory=inventory, plan=plan, policy=policy, job=job)


def _session_directory(root: str | Path, session_id: str) -> Path:
    if not session_id or "/" in session_id or "\\" in session_id or ".." in session_id or not _SAFE_SESSION_ID.match(session_id):
        raise SafetyError(f"Invalid managed cleanup session id: {session_id}")
    resolved_root = resolve_root(root)
    directory = (resolved_root / MANAGED_DIRECTORY / session_id).resolve(strict=False)
    try:
        directory.relative_to((resolved_root / MANAGED_DIRECTORY).resolve(strict=False))
    except ValueError as exc:
        raise SafetyError("Managed cleanup path escapes the assigned root.") from exc
    return directory


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary_path, path)


def _write_session_artifacts(root: Path, session: ManagedCleanupSession, pack) -> None:
    directory = _session_directory(root, session.session_id)
    report = build_managed_report(session, pack)
    session.artifacts.update(
        {
            "session": str(directory / "session.json"),
            "report_json": str(directory / "report.json"),
            "report_md": str(directory / "report.md"),
        }
    )
    report.artifacts = dict(session.artifacts)
    _write_json(directory / "session.json", session.to_dict())
    _write_json(directory / "report.json", report.to_dict())
    (directory / "report.md").write_text(render_managed_report_markdown(session, report, pack), encoding="utf-8")
