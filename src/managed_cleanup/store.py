from __future__ import annotations

import json
import os
from pathlib import Path

from src.managed_cleanup.models import CleanupSession, validate_cleanup_session_id
from src.models import utc_now_iso
from src.security import SafetyError, resolve_root


MANAGED_CLEANUP_DIRECTORY = Path(".thelibrarian") / "managed-cleanups"


class CleanupStore:
    def __init__(self, root: str | Path) -> None:
        self.root = resolve_root(root)
        self.cleanup_directory = self.root / MANAGED_CLEANUP_DIRECTORY

    def create(self, *, provider: str, policy_pack_id: str, dry_run: bool = True) -> CleanupSession:
        session = CleanupSession.create(
            root=str(self.root),
            provider=provider,
            policy_pack_id=policy_pack_id,
            dry_run=dry_run,
        )
        self.session_directory(session.session_id).mkdir(parents=True, exist_ok=False)
        self.save(session)
        return session

    def session_directory(self, session_id: str) -> Path:
        normalized = validate_cleanup_session_id(session_id)
        candidate = (self.cleanup_directory / normalized).resolve(strict=False)
        try:
            candidate.relative_to(self.cleanup_directory.resolve(strict=False))
        except ValueError as exc:
            raise SafetyError(f"Cleanup session path escapes the assigned root: {session_id}") from exc
        return candidate

    def artifact_path(self, session_id: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise SafetyError(f"Invalid cleanup artifact name: {filename}")
        return self.session_directory(session_id) / filename

    def save(self, session: CleanupSession) -> None:
        session.updated_at = utc_now_iso()
        session_directory = self.session_directory(session.session_id)
        session_directory.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(session_directory / "cleanup_session.json", session.to_dict())

    def load(self, session_id: str) -> CleanupSession:
        path = self.artifact_path(session_id, "cleanup_session.json")
        if not path.exists():
            raise SafetyError(f"Unknown cleanup session: {session_id}")
        return CleanupSession.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[CleanupSession]:
        if not self.cleanup_directory.exists():
            return []
        sessions: list[CleanupSession] = []
        for session_json in self.cleanup_directory.glob("*/cleanup_session.json"):
            try:
                sessions.append(CleanupSession.from_dict(json.loads(session_json.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        sessions.sort(key=lambda session: session.updated_at, reverse=True)
        return sessions

    def write_json_artifact(self, session_id: str, filename: str, payload: dict[str, object]) -> Path:
        path = self.artifact_path(session_id, filename)
        self._atomic_write_json(path, payload)
        return path

    def read_json_artifact(self, session_id: str, filename: str) -> dict[str, object]:
        path = self.artifact_path(session_id, filename)
        if not path.exists():
            raise SafetyError(f"Missing cleanup artifact: {filename}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SafetyError(f"Cleanup artifact is not a JSON object: {filename}")
        return payload

    def _atomic_write_json(self, path: Path, payload: dict[str, object]) -> None:
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary_path, path)
