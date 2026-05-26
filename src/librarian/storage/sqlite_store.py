from __future__ import annotations

import sqlite3
from pathlib import Path

from src.librarian.rules.schema import Manifest


def update_sqlite_index(root: str | Path, manifest: Manifest) -> Path:
    resolved_root = Path(root).resolve()
    db_path = resolved_root / ".librarian" / "cache" / "index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "create table if not exists files (librarian_id text primary key, current_path text, kind text, language text, risk text)"
        )
        connection.execute(
            "create table if not exists directories (librarian_id text primary key, current_path text, theme text, roles text)"
        )
        connection.execute("delete from files")
        connection.execute("delete from directories")
        connection.executemany(
            "insert into files values (?, ?, ?, ?, ?)",
            [
                (
                    node.librarian_id,
                    node.current_path,
                    node.file_kind,
                    node.detected_language or "",
                    node.risk_level,
                )
                for node in manifest.files
            ],
        )
        connection.executemany(
            "insert into directories values (?, ?, ?, ?)",
            [
                (
                    node.librarian_id,
                    node.current_path,
                    node.directory_analysis.theme if node.directory_analysis else "",
                    ",".join(node.directory_analysis.possible_roles if node.directory_analysis else []),
                )
                for node in manifest.directories
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return db_path
